"""Opt-in per-aura stage targets on the existing native input worker.

Unknown title, stage, active button or result holds; no bulk native loop is
called for configured targets. No execution happens on import.
"""
from functools import wraps
from pathlib import Path
import re,time
import logging
import cv2
import numpy as np
from PIL import Image
from owner_gear_decision_candidate import Observation
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_settings_candidate import Store
from owner_gear_step_guard_candidate import Guard

NAMES=('생명','여명','몽환','홍염')
PANEL_TOP=(680,40,838,125)
ASSETS=Path(__file__).with_name('owner_energy_assets_candidate')
class NavigationError(RuntimeError):pass

def _continued(adapter,outcome):
    """Tell the native worker to continue, while retaining partial status."""
    adapter._owner_energy_outcome=outcome
    logging.getLogger('project_gui.DKB').info('기운 발현 결과 · %s',outcome)
    return True

def visible_stage(frame):
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return None
    refs=[]
    try:
        for p in sorted(ASSETS.glob('diamond_*.png')):refs.append(np.asarray(Image.open(p).convert('RGB')))
    except OSError:return None
    if not refs or any(ref.shape!=(20,20,3) for ref in refs):return None
    visible=[];selected=[]
    for i in range(8):
        patch=frame[49+33*i:69+33*i,864:884]
        if patch.shape!=(20,20,3):return None
        score=max(float(cv2.matchTemplate(patch,ref,cv2.TM_CCOEFF_NORMED)[0,0]) for ref in refs)
        if score>=.80:
            visible.append(i+1);hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
            gold=((hsv[:,:,0]>5)&(hsv[:,:,0]<30)&(hsv[:,:,1]>80)&(hsv[:,:,2]>100))
            if int(gold.sum())>=100:selected.append(i+1)
    if not visible or visible!=list(range(1,max(visible)+1)) or selected!=[max(visible)]:return None
    return selected[0]

def read_text(root,frame):
    if getattr(frame,'hi',None) is not None:
        from owner_growth_words import read_energy_title
        return read_energy_title(root,frame)
    from tools.ocr_support import get_paddle_engine
    engine=get_paddle_engine(root,language='korean')
    # The patch moved this block down 45px. Read the whole panel top and go by what
    # the words say, so another move needs no new coordinates. Exactly one of each.
    x1,y1,x2,y2=PANEL_TOP;crop=frame[y1:y2,x1:x2]
    if crop.size==0:return None
    image=cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_LINEAR);words=[]
    for page in engine.predict(image):
        for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
            if float(score)>=.90:words.append(re.sub(r'\s+','',str(text)))
    joined=''.join(words)
    titles=re.findall(r'(생명|여명|몽환|홍염)의기운발현([1-9][0-9]?)단계',joined);levels=re.findall(r'레벨([0-9]{1,3})',joined)
    if len(titles)!=1 or len(levels)!=1:return None
    stage=int(titles[0][1]);lv=int(levels[0])
    if visible_stage(frame)!=stage:return None
    return {'name':titles[0][0],'stage':stage,'level':lv}

class EnergyObserver:
    def __init__(self,service,context,identity,name,target,*,text_reader=read_text,clock=time.monotonic):
        self.service=service;self.context=context;self.identity=identity;self.name=name;self.target=target
        self.reader=text_reader;self.clock=clock;self.sequence=0;self.word_hit=None
    def state(self,frame):
        from project_adapter import achievement_rewards as native
        info=self.reader(Path(self.service.adapter.project.root),frame)
        if not isinstance(info,dict) or info.get('name')!=self.name:return None
        stage,level=info.get('stage'),info.get('level')
        if type(stage) is not int or stage<1 or type(level) is not int or level<0:return None
        if getattr(frame,'hi',None) is not None:return self._word_state(native,frame,info,stage)
        # Red numerator is a definite shortage. A non-red counter alone is
        # never enough; one positively detected native active action is needed.
        hsv=cv2.cvtColor(frame[411:437,730:790],cv2.COLOR_RGB2HSV)
        red=((hsv[:,:,0]<8)|(hsv[:,:,0]>172))&(hsv[:,:,1]>100)&(hsv[:,:,2]>120)
        candidates=[]
        for name in (native.ENERGY_ACTIVE,native.ENERGY_BREAKTHROUGH):
            hit=self.service.detector.find(name,frame,threshold=.95)
            if hit:candidates.append((name,hit))
        button=None;active=False
        if len(candidates)==1 and int(red.sum())<3:
            button,hit=candidates[0];x1,y1,x2,y2=hit[2];patch=frame[y1:y2,x1:x2]
            reference=self.service.detector.templates.get(button)
            if patch.size and reference is not None and reference.size and reference.mean()>0:
                ratio=float(patch.mean()/reference.mean());active=.90<=ratio<=1.30
        from owner_growth_reading import breakthrough_allowed
        if button==native.ENERGY_BREAKTHROUGH and not breakthrough_allowed():active=False
        return dict(info,active=bool(active and stage<self.target),button=button)
    def _word_state(self,native,frame,info,stage):
        """The button's word and the count under the panel, off the real frame. Nothing unclear can turn active on."""
        from owner_growth_reading import breakthrough_allowed
        from owner_growth_words import read_energy_action
        action=read_energy_action(Path(self.service.adapter.project.root),frame)
        button={'active':native.ENERGY_ACTIVE,'breakthrough':native.ENERGY_BREAKTHROUGH}.get(action['kind'])
        active=bool(button and action['lit'] and action['enough'] is True and stage<self.target)
        if button==native.ENERGY_BREAKTHROUGH and not breakthrough_allowed():active=False
        self.word_hit=action['hit']
        said=(info['name'],stage,info.get('level'),action['kind'],action['lit'],action['enough'],active)
        if said!=getattr(self,'_said',None):
            self._said=said
            logging.getLogger('project_gui.DKB').info('기운 글자 판독 · %s %d단계 레벨 %s · 버튼 %s · 켜짐 %s · 재료 %s · 입력 가능=%s',*said)
        return dict(info,active=active,button=button)
    def read_pair(self):
        observations=[];states=[]
        for _ in range(2):
            self.context.checkpoint();self.service.check();frame=self.service.capture();stamp=self.clock()
            state=self.state(frame)
            if state is None:return {'screen_proof':False}
            self.sequence+=1;states.append(state)
            observations.append(Observation(self.sequence,stamp,self.identity,'energy:'+self.name,'energy:'+self.name,
                self.name,state['level'],state['stage'],None,state['active'],None,None))
            self.context.wait(.12)
        a,b=observations
        if states[0]!=states[1] or not 0<b.captured_at-a.captured_at<=2.5 or self.clock()-a.captured_at>2.5:return {'screen_proof':False}
        try:
            from owner_growth_current import observe_value
            observe_value(self.service.adapter.project.root,self.identity,'energies',self.name,{'stage':a.breakthrough},verified=True)
        except Exception:pass  # display-only, never execution authority
        return {'screen_proof':True,'first':a,'second':b,'resource_mode':'native_active',
                'active_pair_verified':states[0]['active'],'button_name':states[0]['button']}
    def verify_final(self,frame,latest):
        state=self.state(frame);prior=latest.get('second')
        return bool(state and isinstance(prior,Observation) and state['active'] and
                    state['stage']==prior.breakthrough and state['level']==prior.enhancement and
                    state['button']==latest.get('button_name'))

def settle_pending(observer,intents,context,*,attempts=1):
    """Finish a sent input from a fresh reading; False keeps its record.

    Stage or level rose: success. Both unchanged: that manifestation failed.
    A lower value or another item is not explained by either and stays held.
    """
    before=intents.pending()['before']
    for attempt in range(attempts):
        if attempt:context.wait(.5)
        pair=observer.read_pair()
        if pair.get('screen_proof') is not True:continue
        a,b=pair['first'],pair['second']
        if not all(getattr(a,k)==getattr(before,k)==getattr(b,k) for k in ('character','item','slot','grade')):return False
        if a.breakthrough!=b.breakthrough or a.enhancement!=b.enhancement:continue
        if a.breakthrough>before.breakthrough or (a.breakthrough==before.breakthrough and a.enhancement>before.enhancement):
            intents.complete('observed_progress');return True
        if a.breakthrough==before.breakthrough and a.enhancement==before.enhancement:
            logging.getLogger('project_gui.DKB').info('기운 발현 실패 · %s · 단계·레벨 유지',before.grade)
            intents.complete('observed_failure');return True
        return False
    return False


ENERGY_SECONDS=60


def run_energy(service,context,identity,targets,*,text_reader=read_text,settings_check=None):
    """Process selected tab only; caller owns navigation and cleanup."""
    from project_adapter import achievement_rewards as native
    store=Store(service.adapter.project.root,identity);path=store.path.with_name(store.path.stem+'-energy-intent.json')
    intents=IntentStore(path);pending=intents.pending()
    if pending and pending.get('phase')=='prepared':intents.abort_prepared('기운 입력 전 기록');pending=None
    result_only=getattr(service.adapter,'_owner_growth_reconcile_only',False) is True
    if result_only and not pending:return False
    # At 1366 a tab switch and its reads took most of 20 s, so 몽환 (85 materials, 100%) was never reached after 여명
    # was short (짱군네 11-07 15:14). The guard's identity holds a reading for 180 s.
    deadline=time.monotonic()+ENERGY_SECONDS
    for index,name in enumerate(NAMES):
        if time.monotonic()>=deadline:return False
        target=targets.get(name,{})
        if target.get('enabled') is not True or type(target.get('stage')) is not int:continue
        if pending and pending['before'].grade!=name:continue
        context.checkpoint();service.check()
        # The selected tab's template may be absent while its title is visible.
        # Reuse it rather than requiring an unnecessary re-click.
        frame=service.capture();current=text_reader(Path(service.adapter.project.root),frame)
        if not isinstance(current,dict) or current.get('name')!=name:
            real=getattr(frame,'hi',None) is not None
            hit=None
            if real:
                from owner_growth_words import energy_tab
                hit=energy_tab(Path(service.adapter.project.root),frame,name)
            if hit:service.click_hit(hit)
            else:service.button(native.ENERGY_TABS[index],wait_before_click=.1,required=True)
            context.wait(.15)
            # Reading takes longer than the tab takes to draw at this size, but the panel slides in first.
            shown=None
            for _ in range(6 if real else 0):
                context.checkpoint();service.check()
                shown=text_reader(Path(service.adapter.project.root),service.capture())
                if isinstance(shown,dict) and shown.get('name')==name:break
                context.wait(.25)
            # 15:38: after 여명, 몽환 (85 materials) was passed with no line at all. Say what the tab showed.
            if real and not(isinstance(shown,dict) and shown.get('name')==name):
                logging.getLogger('project_gui.DKB').info('기운 탭 판독 안 됨 · %s · 읽은 값 %s',name,shown)
        observer=EnergyObserver(service,context,identity,name,target['stage'],text_reader=text_reader)
        if pending:
            if not settle_pending(observer,intents,context):return False
            pending=None
            if result_only:return False
        def one(latest,mark_sent):
            context.checkpoint();service.check();frame=service.capture()
            if not observer.verify_final(frame,latest):raise RuntimeError('기운 입력 직전 화면 미확인')
            if callable(settings_check) and settings_check() is not True:raise RuntimeError('기운 설정 또는 캐릭터가 바뀌었습니다')
            button=latest.get('button_name')
            if button not in (native.ENERGY_ACTIVE,native.ENERGY_BREAKTHROUGH):raise RuntimeError('기운 버튼 미확인')
            # On a real frame the words verify_final just read on this same frame name the place.
            hit=observer.word_hit if getattr(frame,'hi',None) is not None else service.detector.find(button,frame,threshold=.95)
            if not hit:raise RuntimeError('기운 버튼 미확인')
            context.checkpoint();service.check();mark_sent();context.checkpoint();service.check()
            if callable(settings_check) and settings_check() is not True:raise RuntimeError('기운 설정 또는 캐릭터가 바뀌었습니다')
            service.click_hit(hit)
        # Stage<target is separately verified by observer; the native action
        # raises an inner level or transitions to the next stage.
        guard=Guard(context,intents,observer.read_pair)
        for _ in range(50):
            context.checkpoint();service.check()
            if time.monotonic()>=deadline:return False
            outcome=guard.run_one('enhance',{name:{'enabled':True,'enhance':9999}},one)
            if outcome!='pending_confirmation':break
            # The pot animation hides the panel, and it may not have begun yet.
            from owner_growth_reading import RESULT_SETTLE_SECONDS
            context.wait(RESULT_SETTLE_SECONDS)
            if not settle_pending(observer,intents,context,attempts=6):return False
    return False

def install(module,identity_resolver,*,alias_modules=()):
    from owner_gear_native_install_candidate import _rebind_aliases
    original=module.run_energy_entry
    if getattr(original,'_owner_energy_target_candidate',False):
        _rebind_aliases(alias_modules,getattr(original,'__wrapped__',original),original);return
    @wraps(original)
    def guarded(adapter,context,inputs,*,process=False):
        if not process:return original(adapter,context,inputs,process=False)
        adapter._owner_energy_outcome=None
        identity=identity_resolver(adapter)
        if not isinstance(identity,str) or not identity.strip():return _continued(adapter,'캐릭터 확인 필요')
        try:document,revision=Store(adapter.project.root,identity).snapshot()
        except (ValueError,OSError,TypeError,KeyError,AttributeError):return _continued(adapter,'설정 확인 필요')
        if revision=='missing':
            from owner_growth_reading import breakthrough_allowed
            # The native routine may press its own breakthrough button.
            if not breakthrough_allowed():return _continued(adapter,'설정 확인 필요')
            return original(adapter,context,inputs,process=True)
        targets=document['energies']
        if not any(v.get('enabled') is True for v in targets.values()):return _continued(adapter,'목표 미설정 · 실행 건너뜀')
        from project_adapter.town_services import TownServices
        from owner_special_contexts import NAMES as SCENE_NAMES
        from project_adapter.secret_exploration import AUTO_NAMES
        from owner_native_contracts import region_names,find_energy_entry
        names=['버튼_전체매뉴',*region_names('energy',module=module),
               '버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파','체크_던전진행중','버튼_던전_나가기',
               *SCENE_NAMES,*AUTO_NAMES]
        service=TownServices(adapter,context,inputs,names)
        def field_pair():
            from owner_startup_stage import scene
            context.checkpoint();service.check();first=scene(service.detector,service.capture())
            context.wait(.12);context.checkpoint();service.check();second=scene(service.detector,service.capture())
            return first=='field' and second=='field'
        def menu_pair():
            anchors=('버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파')
            def match(f):return sum(bool(service.detector.find(n,f,threshold=.95)) for n in anchors)>=2
            context.checkpoint();service.check();first=match(service.capture());context.wait(.12)
            context.checkpoint();service.check();return first and match(service.capture())
        def energy_pair():
            context.checkpoint();service.check();start=time.monotonic();first=read_text(Path(adapter.project.root),service.capture())
            context.wait(.12);context.checkpoint();service.check();second=read_text(Path(adapter.project.root),service.capture())
            return first is not None and first==second and time.monotonic()-start<=3
        def energy_title():
            # The pot's animation can keep two panel reads apart (15:14: '안전하게 닫지 못했습니다' on the 기운 page);
            # the page's own title beside the back arrow says the same on two looks.
            from owner_startup_stage import menu_title
            context.checkpoint();service.check();first=menu_title(service.capture())
            context.wait(.12);context.checkpoint();service.check();second=menu_title(service.capture())
            return '기운' in first and '기운' in second
        def close_energy():
            if not energy_pair() and not energy_title():raise NavigationError('기운 화면을 안전하게 닫지 못했습니다')
            context.checkpoint();service.check();service.click_hit((21,19,(16,14,27,24)));context.wait(.25)
            # 20:05 real run: a failed attempt's effect was still playing and the back
            # press did not take. Wait it out, and press again only on the same page.
            for attempt in range(10):
                if field_pair():return
                context.wait(.5)
                if attempt==3 and energy_pair():
                    context.checkpoint();service.check();service.click_hit((21,19,(16,14,27,24)));context.wait(.25)
            raise NavigationError('기운 화면 종료 후 필드 복귀를 확인하지 못했습니다')
        context.checkpoint();service.check();service.button('버튼_전체매뉴',wait_before_click=.1,required=True)
        context.wait(.15);context.checkpoint();service.check();frame=service.capture()
        entry=find_energy_entry(service.detector,frame,module=module)
        # A quest cutscene or arrival can delay or swallow the menu click.
        for _ in range(5):
            if entry is not None:break
            context.wait(.3);context.checkpoint();service.check()
            entry=find_energy_entry(service.detector,service.capture(),module=module)
        if entry is None:
            if not menu_pair():
                if field_pair():return _continued(adapter,'전체 메뉴가 열리지 않음 · 다음 확인')
                raise NavigationError('전체 메뉴 상태 미확인 · 기운 항목 탐색 중단')
            context.checkpoint();service.check();service.key(0x1b);context.wait(.25)
            if not field_pair():raise NavigationError('전체 메뉴 종료 후 필드 복귀를 확인하지 못했습니다')
            return _continued(adapter,'진입 버튼 확인 필요')
        service.button(entry,wait_before_click=.1,required=True);context.wait(.2)
        def settings_check():return Store(adapter.project.root,identity).revision()==revision and identity_resolver(adapter)==identity
        try:
            run_energy(service,context,identity,targets,settings_check=settings_check)
            return _continued(adapter,'처리 종료 · 완료 여부 미확인')
        finally:close_energy()
    guarded._owner_energy_target_candidate=True;module.run_energy_entry=guarded
    _rebind_aliases(alias_modules,original,guarded)
