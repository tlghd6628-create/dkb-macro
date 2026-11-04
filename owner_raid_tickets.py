"""Read the raid reward ticket count as text.

The native "0 tickets" image moved in the patch, and its 0 and a 5 cannot be told
apart reliably by comparing pictures. The number itself is read twice instead.
A count that cannot be read stops before matching: no ticket decision on a guess.
"""
from functools import wraps
import copy,logging,re,threading,time

LOG=logging.getLogger('project_gui.DKB')
BOX=(763,405,28,13);SCORE=.85;WAIT=3.;READS=4
COUNT=re.compile(r'\s*(\d{1,2})\s*/\s*10\s*')
class TicketUnread(RuntimeError):pass

def parse(rows):
    found={int(m[1]) for text,score in rows if score>=SCORE for m in [COUNT.fullmatch(text)] if m and int(m[1])<=10}
    return next(iter(found)) if len(found)==1 else None

def read_once(root,frame,context):
    from tools.ocr_support import get_paddle_engine
    from owner_progression import resized,texts
    engine=get_paddle_engine(root,language='number');result=[];done=threading.Event()
    def work():
        # The brightest channel: plain reads gave "4710 (" for a real 4/10, this gives 4/10 at 1.0.
        try:
            import cv2
            result.extend(texts(engine.predict(cv2.cvtColor(resized(frame,BOX).max(axis=2),cv2.COLOR_GRAY2RGB))))
        except Exception as exc:LOG.info('레이드 티켓 판독 오류 · %s',type(exc).__name__)
        finally:done.set()
    threading.Thread(target=work,name='dkb-raid-ticket',daemon=True).start()
    end=time.monotonic()+WAIT
    while not done.is_set() and time.monotonic()<end:
        context.wait(.03);context.checkpoint()
    return parse(result) if done.is_set() else None

def tickets(flow,frame):
    """Two agreeing reads in a row. A read may time out while the model warms up."""
    root=flow.adapter.project.root;context=flow.context;last=None
    for attempt in range(READS):
        if attempt:
            context.wait(.1);frame=flow.service.capture()
        value=read_once(root,frame,context)
        if value is not None and value==last:return value
        last=value
    return None

COUNT_KEY='auto_schedule.boss_raid.entry_count';COUNT_MAX=10
COUNT_BOX=(465,268,30,16);PLUS=(516,276);MINUS=(444,276);STEP_WAIT=.25
CHECK_FILE='settings/owner-raid-count-check.json'
ONE_SCORE=.93;CHANGE=2.

def add_fields(schema):
    """The entry count takes the place of the ticket mode: one setting says how many tickets go in."""
    groups=[g for t in schema['tabs'] for g in t['groups']]
    entries={f['id']:(g,f) for g in groups for f in g['fields']}
    source='auto_schedule.boss_raid.reward_ticket'
    if source not in entries or COUNT_KEY in entries:return schema
    group,field=entries[source]
    made=copy.deepcopy(field);choices=['%d회'%n for n in range(1,COUNT_MAX+1)]
    made.update(id=COUNT_KEY,label='입장 횟수',choices=choices,default='1회',existing_default='1회',settings_only=True)
    made.pop('enabled_if',None)
    group['fields'][group['fields'].index(field)]=made
    return schema

def wanted(values):
    found=re.fullmatch(r'(\d{1,2})회',str(values.get(COUNT_KEY,'1회')))
    return min(COUNT_MAX,max(1,int(found[1]))) if found else 1

def _digit(frame):
    x,y,w,h=COUNT_BOX;return frame[y:y+h,x:x+w]
def shows_one(frame):
    """Compared as a picture: on the real window the reader took 3 for 8 and lost 1 entirely."""
    import cv2
    from owner_boss_range import ASSETS
    from PIL import Image
    import numpy as np
    needle=np.asarray(Image.open(ASSETS.parent/'image-scope/raid-count-one.png').convert('RGB'))
    return float(cv2.matchTemplate(_digit(frame),needle,cv2.TM_CCOEFF_NORMED)[0,0])>=ONE_SCORE
def changed(before,after):
    import numpy as np
    return float(np.abs(_digit(before).astype(int)-_digit(after).astype(int)).mean())>=CHANGE
def step(flow,spot):
    """One press. True only when the number on screen actually changed."""
    context,service=flow.context,flow.service
    context.checkpoint();before=service.capture();x,y=spot
    service.click_hit((x,y,(x-4,y-4,x+4,y+4)));context.wait(STEP_WAIT)
    return changed(before,service.capture())

def check_counter(flow,root):
    """One-shot, only when the marker file exists: prove + and - on the real window, end on 1.
    Spends nothing, because the count returns to 1 before 확인 is pressed."""
    from pathlib import Path
    marker=Path(root)/CHECK_FILE
    if not marker.exists():return
    marker.unlink()
    moved=[step(flow,spot) for spot in (PLUS,PLUS,MINUS,MINUS)]
    one=shows_one(flow.service.capture())
    LOG.info('레이드 입장 횟수 자가점검 · 변화 %s · 끝에 1 %s',moved,one)
    if not one:raise raid_pending('레이드 입장 횟수 자가점검 후 1 확인 실패 · 확인 안 누름')

def set_count(flow):
    """Start from a proved 1, then press + once per extra entry, seeing each press change the number.
    Never more than the tickets held. A press with no effect means the game's own limit: what was
    counted is what shows. Nothing is confirmed when the start cannot be proved."""
    want=1 if getattr(flow,'_owner_one_entry',False) else wanted(flow.adapter.values)
    known=getattr(flow,'_owner_ticket_read',None)
    if known:want=min(want,max(1,known[1]))
    if want<=1:
        check_counter(flow,flow.adapter.project.root);return 1
    if not shows_one(flow.service.capture()):raise raid_pending('레이드 입장 횟수 시작값 확인 필요 · 확인 안 누름')
    count=1
    for _ in range(want-1):
        if not step(flow,PLUS):break
        count+=1
    if count==want:LOG.info('레이드 입장 횟수 %d회',count)
    else:LOG.warning('레이드 입장 횟수 %d회까지만 가능 · 요청 %d회',count,want)
    return count

def raid_pending(text):
    import project_adapter.boss_raid as raid
    return raid.RaidPending(text)

def install():
    import project_adapter.boss_raid as raid
    if getattr(raid.RaidFlow.find,'_owner_raid_tickets',False):return
    ordinary=raid.RaidFlow.find
    @wraps(ordinary)
    def find(flow,name,frame,*args,**kwargs):
        if name!=raid.NO_TICKET:return ordinary(flow,name,frame,*args,**kwargs)
        # Only on the raid page, where the count is on screen.
        if ordinary(flow,raid.MATCH,frame) is None:return None
        crop=frame[BOX[1]:BOX[1]+BOX[3],BOX[0]:BOX[0]+BOX[2]].tobytes();known=getattr(flow,'_owner_ticket_read',None)
        count=known[1] if known and known[0]==crop else tickets(flow,frame)
        if count is None:raise raid.RaidPending('레이드 보상 티켓 수 판독 필요 · 매칭 안 함')
        if not known or known[1]!=count:LOG.info('레이드 보상 티켓 %d장',count)
        flow._owner_ticket_read=(crop,count)
        if count>0:return None
        LOG.info('레이드 보상 티켓 0장 · 입장 안 함')
        x,y,w,h=BOX
        return (x+w//2,y+h//2,(x,y,x+w,y+h))
    find._owner_raid_tickets=True;raid.RaidFlow.find=find
    # A raid needs the character free to reach it, the same as the world boss.
    fight=raid.RaidFlow.run
    @wraps(fight)
    def run(flow,stage,bulk):
        from owner_boss_range import loosen,restore
        # The entry count replaced the ticket mode, so an old saved "일괄소모" spends nothing extra.
        flow._owner_bulk=False
        loosen(flow.adapter,flow.context,flow.inputs)
        try:return fight(flow,stage,False)
        finally:
            if not flow.context.stop.is_set():restore(flow.adapter,flow.context,flow.inputs)
    raid.RaidFlow.run=run
    confirms=frozenset((raid.CONFIRM,raid.CONFIRM2))
    press_button=raid.RaidFlow.press;click_button=raid.RaidFlow.click
    @wraps(press_button)
    def press(flow,name,seconds=3,post=1,*,alternatives=()):
        if not getattr(flow,'_owner_bulk',True) and (name in confirms or confirms.intersection(alternatives)):set_count(flow)
        return press_button(flow,name,seconds,post,alternatives=alternatives)
    @wraps(click_button)
    def click(flow,name,hit):
        if not getattr(flow,'_owner_bulk',True) and name in confirms:set_count(flow)
        return click_button(flow,name,hit)
    raid.RaidFlow.press=press;raid.RaidFlow.click=click
