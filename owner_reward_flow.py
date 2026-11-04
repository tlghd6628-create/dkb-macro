"""Tighten the native reward flows through the objects they are handed.

The native run_*_rewards functions keep every decision, image and click path.
This only observes each click's result, drops clicks that cannot do anything,
ends fixed waits once the next screen has settled, and names the outcome.
"""
from pathlib import Path
import logging,threading,time
LOG=logging.getLogger('project_gui.DKB')
POPUPS=('체크_보상받기','체크_메인퀘_보상받기','체크_보물찾기_아이템획득')
BLANKS=((288,93),(286,19),(286,19))
LIST_BOX=(165,125,130,265)
BODY_TOP=204;BANNER_WAIT=1.5
CLAIMED,NOTHING,PARTIAL,FAILED='claimed','none','partial','failed'
LABELS={CLAIMED:'수령 완료',NOTHING:'보상 없음',PARTIAL:'일부 미확인',FAILED:'실패'}
EVIDENCE_LIMIT=60

def _popup_reader(profile):
    reader=getattr(_popup_reader,'reader',None)
    if reader is None or reader[0]!=str(profile):
        from roi_runtime import RoiDetector
        reader=_popup_reader.reader=(str(profile),RoiDetector(Path(profile),list(POPUPS)))
    return reader[1]

def popup(profile,frame):
    reader=_popup_reader(profile)
    return any(reader.find(name,frame,threshold=.9) for name in POPUPS)

def diff(a,b):
    import numpy as np
    return float(np.abs(a.astype('int16')-b.astype('int16')).mean()) if a.shape==b.shape else 255.

def closing(x,y):
    """The window's own exit and X. A press that only dismissed a receipt leaves
    these looking unchanged, so they must never count as a dead spot."""
    return x>=690 and y<=110

def patch(frame,x,y,radius=24):
    return frame[max(0,y-radius):y+radius,max(0,x-radius):x+radius].copy()

class Flow:
    def __init__(self,key,profile,root,context,capture):
        self.key,self.profile,self.root=key,profile,root
        self.context,self.capture=context,capture
        self.started=time.monotonic();self.seconds=dict(wait=0.,saved=0.,capture=0.,read=0.)
        self.counts=dict(clicks=0,claims=0,blank_sent=0,blank_skipped=0,repeat_skipped=0,no_change=0,scroll_skipped=0,captures=0)
        self.baseline=None;self.pending=None;self.skip_wait=False;self.spots={}
        self.list_before=None;self.list_end=False;self.dragging=False;self.unconfirmed=False;self.saved=0
        self.banner=False;self.rose=False
    def note_banner(self,frame):
        """One receipt on screen is one claim, whenever it was seen."""
        now=popup(self.profile,frame)
        if now and not self.banner:self.counts['claims']+=1;self.rose=True
        self.banner=now
        return now
    def await_banner(self,frame):
        # A receipt fades in after its click. Deciding before then skips the
        # dismissal, and the next click only dismisses the receipt instead.
        end=time.monotonic()+BANNER_WAIT
        while not self.note_banner(frame) and time.monotonic()<end:
            self.context.wait(.12);frame=self.frame()
        return frame
    def frame(self):
        started=time.monotonic();frame=self.capture()
        self.seconds['capture']+=time.monotonic()-started;self.counts['captures']+=1
        return frame
    def settle_click(self,frame):
        """Decide what the previous click did, from a fresh frame."""
        pending=self.pending
        if pending is None:return
        x,y,before,whole,_=pending;self.pending=None
        self.note_banner(frame)
        if self.rose:self.rose=False;self.spots.pop((x//8,y//8),None);return
        if diff(patch(frame,x,y),before)<3:
            self.spots[(x//8,y//8)]=before
            if self.reward_target(x,y):
                self.counts['no_change']+=1
                self.evidence('무변화',whole,frame,x,y)
        else:self.spots.pop((x//8,y//8),None)
    def reward_target(self,x,y):
        # A claim-all with nothing to claim stays as it was, and so does a tab
        # already selected. Only an item that looked claimable makes this unsure.
        return self.key not in ('mail','achievement') and not closing(x,y) and not (self.key=='event' and (x<300 or y<BODY_TOP))
    def evidence(self,reason,before,after,x,y):
        if self.saved>=4:return
        try:
            from PIL import Image
            folder=Path(self.root)/'logs/reward-evidence'
            if folder.exists() and sum(1 for _ in folder.iterdir())>=EVIDENCE_LIMIT:return
            stamp=time.strftime('%Y%m%dT%H%M%S')+'-%s-%d-%d'%(self.key,x,y);folder=folder/stamp;folder.mkdir(parents=True,exist_ok=True)
            Image.fromarray(before).save(folder/'before.png');Image.fromarray(after).save(folder/'after.png')
            (folder/'reason.txt').write_text(reason+' · %s · (%d,%d)'%(self.key,x,y),encoding='utf-8');self.saved+=1
        except OSError:pass
    def finish(self,result,failed=False):
        try:self.settle_click(self.frame())
        except Exception:pass
        c=self.counts;status=result.get('status') if isinstance(result,dict) else None
        if failed or (result is False and not c['claims']):state=FAILED
        elif c['no_change'] or self.unconfirmed or result is False or status=='PARTIAL':state=PARTIAL
        elif c['claims']:state=CLAIMED
        else:state=NOTHING
        s=self.seconds;total=time.monotonic()-self.started
        LOG.info('보상 처리 결과 · %s · %s · 총 %.1f초 · 대기 %.1f초(단축 %.1f초) · 캡처 %.1f초/%d회 · 판독 %.1f초 · 클릭 %d(수령 %d·무변화 %d) · 생략 공백 %d/반복 %d/스크롤 %d',
                 self.key,LABELS[state],total,s['wait'],s['saved'],s['capture'],c['captures'],s['read'],c['clicks'],c['claims'],c['no_change'],c['blank_skipped'],c['repeat_skipped'],c['scroll_skipped'])
        return state

class FlowContext:
    def __init__(self,flow):object.__setattr__(self,'_flow',flow)
    def __getattr__(self,name):return getattr(self._flow.context,name)
    def __setattr__(self,name,value):setattr(self._flow.context,name,value)
    def wait(self,seconds):
        flow=self._flow;real=flow.context;started=time.monotonic()
        if flow.skip_wait and seconds>=.3:
            flow.skip_wait=False;real.checkpoint();flow.seconds['saved']+=seconds;return
        if seconds<.5 or flow.baseline is None:
            real.wait(seconds);flow.seconds['wait']+=time.monotonic()-started;return
        # The next screen is often ready early. Leave only after it visibly
        # changed and held still; with no change, the full native wait stays.
        end=started+seconds;previous=None;baseline=flow.baseline
        while True:
            left=end-time.monotonic()
            if left<=0:break
            real.wait(min(.12,left))
            if time.monotonic()-started<.25:continue
            frame=flow.frame();flow.note_banner(frame)
            if previous is not None:
                # A receipt or a removed row is a small part of the frame, so
                # compare the change against the screen's own background motion.
                changed=diff(frame[::4,::4],baseline[::4,::4]);moving=diff(frame[::4,::4],previous[::4,::4])
                if changed>.5 and moving<min(.4,changed/3):
                    flow.seconds['saved']+=max(0,end-time.monotonic());flow.baseline=None;break
            previous=frame
        flow.seconds['wait']+=time.monotonic()-started

class FlowDetector:
    def __init__(self,flow,detector):object.__setattr__(self,'_flow',flow);object.__setattr__(self,'_real',detector)
    def __getattr__(self,name):return getattr(self._real,name)
    def __setattr__(self,name,value):
        # Native recovery re-binds find around whatever it was handed. Forwarding that
        # to the real object made real.find call this find again, forever (21:23 real run).
        if hasattr(type(self),name):object.__setattr__(self,name,value)
        else:setattr(self._real,name,value)
    def find(self,*a,**k):
        started=time.monotonic();hit=self._real.find(*a,**k)
        self._flow.seconds['read']+=time.monotonic()-started
        return hit

class FlowCapture:
    def __init__(self,flow):self._flow=flow
    def __call__(self):return self._flow.frame()
    def __getattr__(self,name):return getattr(self._flow.capture,name)

class FlowInputs:
    def __init__(self,flow,inputs):object.__setattr__(self,'_flow',flow);object.__setattr__(self,'_real',inputs)
    def __getattr__(self,name):return getattr(self._real,name)
    def __setattr__(self,name,value):
        if hasattr(type(self),name):object.__setattr__(self,name,value)
        else:setattr(self._real,name,value)
    def click(self,x,y,*a,**k):
        flow=self._flow;frame=flow.frame()
        blank=any(abs(x-u)<=4 and abs(y-v)<=4 for u,v in BLANKS);leaving=closing(x,y)
        if (blank or leaving) and flow.pending is not None:frame=flow.await_banner(frame)
        flow.settle_click(frame)
        # Blank clicks only dismiss a receipt. An open list underneath is not one.
        if blank and not flow.note_banner(frame):
            flow.counts['blank_skipped']+=1;flow.skip_wait=True;return None
        seen=None if leaving else flow.spots.get((x//8,y//8))
        if seen is not None and diff(patch(frame,x,y),seen)<3:
            # Already pressed here with no effect, and nothing has changed since.
            flow.counts['repeat_skipped']+=1;flow.skip_wait=True
            if flow.reward_target(x,y):flow.unconfirmed=True
            LOG.info('보상 클릭 생략 · 같은 대상 무변화 · (%d,%d)',x,y)
            return None
        flow.counts['blank_sent' if blank else 'clicks']+=1
        flow.baseline=frame
        if not blank and not leaving:flow.pending=(x,y,patch(frame,x,y),frame,time.monotonic())
        return self._real.click(x,y,*a,**k)
    def transaction(self,*a,**k):
        flow=self._flow;frame=flow.frame();x,y,w,h=LIST_BOX
        if flow.key=='event':
            if flow.list_before is not None and diff(frame[y:y+h,x:x+w],flow.list_before)<2:flow.list_end=True
            flow.list_before=frame[y:y+h,x:x+w].copy()
        if flow.list_end:
            flow.counts['scroll_skipped']+=1;flow.dragging=True;flow.skip_wait=True
            LOG.info('이벤트 목록 끝 확인 · 스크롤 후 변화 없음')
            return _Nothing()
        flow.dragging=False
        return self._real.transaction(*a,**k)
    def down(self,*a,**k):
        if not self._flow.dragging:return self._real.down(*a,**k)
    def up(self,*a,**k):
        if not self._flow.dragging:return self._real.up(*a,**k)
    def move(self,*a,**k):
        if not self._flow.dragging:return self._real.move(*a,**k)

class _Nothing:
    def __enter__(self):return self
    def __exit__(self,*a):return False

LOCAL=threading.local()
def current_adapter():return getattr(LOCAL,'adapter',None)
def owning(adapter):
    """Name the adapter that receives the outcome, for calls that do not pass it."""
    class Scope:
        def __enter__(self):self.previous=current_adapter();LOCAL.adapter=adapter
        def __exit__(self,*a):LOCAL.adapter=self.previous
    return Scope()

def tracked(key,function,adapter,args,kwargs):
    needed=('detector','capture','inputs','context')
    if args or any(name not in kwargs for name in needed):return function(*args,**kwargs)
    detector=kwargs['detector'];profile=getattr(detector,'profile',None)
    if profile is None:return function(*args,**kwargs)
    flow=Flow(key,profile,Path(profile).parents[1],kwargs['context'],kwargs['capture'])
    change=dict(kwargs,detector=FlowDetector(flow,detector),capture=FlowCapture(flow),inputs=FlowInputs(flow,kwargs['inputs']),context=FlowContext(flow))
    log=kwargs.get('user_log')
    if log is not None:
        def user_log(text):
            if '미확인' in str(text):flow.unconfirmed=True
            return log(text)
        change['user_log']=user_log
    failed=True;result=None
    try:
        result=function(**change);failed=False
        return result
    finally:
        state=flow.finish(result,failed=failed)
        if adapter is not None:adapter._owner_reward_last_outcome=state
