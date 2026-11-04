"""Existing blessing-tab navigation. No equipment or reward action."""
import time
from owner_blessing_equip_candidate import selected_filter

def wait_pair(service,context,predicate,*,timeout=3.0):
    """Wait for two fresh confirmations after navigation, without more input."""
    deadline=time.monotonic()+timeout;confirmed=0
    while True:
        context.checkpoint();service.check()
        confirmed=confirmed+1 if predicate(service.capture()) else 0
        if confirmed>=2:return True
        remaining=deadline-time.monotonic()
        if remaining<=0:return False
        context.wait(min(.12,remaining))

def select_category(service,context,category,*,settings_check):
    from project_adapter import achievement_rewards as native
    if type(category) is not int or category not in range(1,6) or not callable(settings_check):return False
    name=native.BLESSING_TABS[category-1];hits=[];start=time.monotonic();already=[]
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if not service.detector.find(native.BLESSING_CHECK,frame,threshold=.95):return False
        already.append(selected_filter(frame))
        hit=service.detector.find(name,frame,threshold=.95)
        if not hit:return False
        hits.append(hit);context.wait(.12)
    if hits[0]!=hits[1] or time.monotonic()-start>1.5 or settings_check() is not True:return False
    if already==[category,category]:return True
    context.checkpoint();service.check();frame=service.capture()
    if not service.detector.find(native.BLESSING_CHECK,frame,threshold=.95):return False
    hit=service.detector.find(name,frame,threshold=.95)
    if hit!=hits[1] or settings_check() is not True:return False
    service.click_hit(hit);context.wait(.2)
    start=time.monotonic();selected=[]
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if not service.detector.find(native.BLESSING_CHECK,frame,threshold=.95):return False
        selected.append(selected_filter(frame));context.wait(.12)
    return selected==[category,category] and time.monotonic()-start<=1.5

def scan_one(service,context,identity,category,order,*,settings_check):
    """Scan one category on an already open native blessing menu.

    A result is a policy/verification status, never a full-content success.
    Caller's same-worker context owns menu entry and final field restoration.
    """
    from owner_blessing_equip_candidate import scan_filtered,_paired_rows,BlessingNavigationError,equip_hit,compare_worn_mark,reconcile_worn_detail
    from pathlib import Path
    from PIL import Image
    import numpy as np,cv2
    if select_category(service,context,category,settings_check=settings_check) is not True:return 'hold_filter'
    status=scan_filtered(service,context,identity,category,order,settings_check=settings_check)
    context.checkpoint();service.check();first=service.capture();context.wait(.12)
    context.checkpoint();service.check();second=service.capture()
    def finish_pending():
        if status!='pending_confirmation':return status
        # Do not leave a known successful equip waiting for tomorrow's slot.
        # This only inspects the independently worn item; never equips again.
        return reconcile_worn_detail(service,context,identity,category,settings_check=settings_check)
    if _paired_rows(service,context,category) is not None and equip_hit(first) is None and equip_hit(second) is None:return finish_pending()
    if (selected_filter(first)!=category or selected_filter(second)!=category or
        equip_hit(first) is None or equip_hit(second) is None or not compare_worn_mark(first) or not compare_worn_mark(second)):
        raise BlessingNavigationError('가호 상세 화면 복귀 확인 필요')
    try:needle=np.asarray(Image.open(Path(__file__).with_name('owner_blessing_assets_candidate')/'compare_close_button.png').convert('RGB'))
    except OSError:raise BlessingNavigationError('가호 상세 닫기 이미지 확인 필요')
    def close_hit(frame):
        area=frame[96:117,577:599]
        if needle.shape!=(11,12,3) or area.shape[0]<11 or area.shape[1]<12:return None
        _,score,_,pos=cv2.minMaxLoc(cv2.matchTemplate(area,needle,cv2.TM_CCOEFF_NORMED))
        if score<.96:return None
        x,y=577+pos[0],96+pos[1];return (x+6,y+5,(x,y,x+12,y+11))
    a,b=close_hit(first),close_hit(second)
    if a is None or a!=b:raise BlessingNavigationError('가호 상세 닫기 위치 확인 필요')
    context.checkpoint();service.check();fresh=service.capture()
    if close_hit(fresh)!=b or selected_filter(fresh)!=category or not compare_worn_mark(fresh):
        raise BlessingNavigationError('가호 상세 화면이 바뀌어 보류합니다')
    service.click_hit(b);context.wait(.2)
    if _paired_rows(service,context,category) is None:raise BlessingNavigationError('가호 목록 복귀 확인 필요')
    return finish_pending()

def run_blessing_equipment(adapter,context,inputs,identity,order,*,settings_check,service_factory=None):
    """Open, inspect eligible categories and restore field on the owner worker.

    The native reward/summon routine is not invoked here. Integration must
    prevent that routine's unchecked equip behavior while retaining any desired
    separately verified reward behavior. Outcomes mean processing, not success.
    """
    import json
    from owner_blessing_equip_candidate import _intent_path,BlessingNavigationError
    from owner_blessing_priority_candidate import validate_order
    from project_adapter import achievement_rewards as native
    from owner_special_contexts import NAMES as SCENE_NAMES
    from project_adapter.secret_exploration import AUTO_NAMES
    from owner_startup_stage import scene
    from project_adapter.town_services import TownServices
    if not isinstance(identity,str) or not identity.strip() or not callable(settings_check) or settings_check() is not True:
        return {'state':'hold_identity','categories':{}}
    validate_order(order)
    path=_intent_path(adapter.project.root,identity);pending=None
    if path.exists():
        try:pending=json.loads(path.read_text(encoding='utf8')).get('pending')
        except (OSError,ValueError,AttributeError):return {'state':'hold_history','categories':{}}
    categories=list(range(1,6))
    if pending is not None:
        if not isinstance(pending,dict):return {'state':'hold_history','categories':{}}
        slot=(pending.get('candidate') or {}).get('slot')
        if type(slot) is not int or slot not in categories:return {'state':'hold_history','categories':{}}
        categories=[slot]
    names=list(dict.fromkeys([*native.BLESSING_NAMES,'버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파',
             '체크_던전진행중','버튼_던전_나가기',*SCENE_NAMES,*AUTO_NAMES]))
    service=(service_factory or TownServices)(adapter,context,inputs,names)
    def pair(predicate):
        context.checkpoint();service.check();a=predicate(service.capture());context.wait(.12)
        context.checkpoint();service.check();b=predicate(service.capture())
        return bool(a and b)
    def menu(frame):return sum(bool(service.detector.find(x,frame,threshold=.95)) for x in ('버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파'))>=2
    def blessing(frame):return bool(service.detector.find(native.BLESSING_CHECK,frame,threshold=.95))
    def field(frame):return not menu(frame) and not blessing(frame) and scene(service.detector,frame)=='field'
    if not pair(field):return {'state':'hold_field','categories':{}}
    context.checkpoint();service.check();service.button('버튼_전체매뉴',wait_before_click=.1,required=True);context.wait(.15)
    if not wait_pair(service,context,menu):raise BlessingNavigationError('전체 메뉴 화면 확인 필요')
    if not pair(lambda frame:bool(service.detector.find(native.BLESSING_ENTRY,frame,threshold=.95))):
        context.checkpoint();service.check();service.key(0x1b);context.wait(.25)
        if not wait_pair(service,context,field):raise BlessingNavigationError('전체 메뉴 종료 후 필드 확인 필요')
        return {'state':'hold_entry','categories':{}}
    context.checkpoint();service.check()
    if settings_check() is not True:
        service.key(0x1b);context.wait(.25)
        if not wait_pair(service,context,field):raise BlessingNavigationError('전체 메뉴 종료 후 필드 확인 필요')
        return {'state':'hold_settings','categories':{}}
    service.button(native.BLESSING_ENTRY,wait_before_click=.1,required=True);context.wait(.2)
    if not wait_pair(service,context,blessing):raise BlessingNavigationError('가호 메뉴 확인 필요')
    results={};navigable=True
    try:
        from owner_blessing_equip_candidate import _paired_rows
        for category in categories:
            context.checkpoint();service.check()
            if settings_check() is not True:break
            navigable=False
            if not select_category(service,context,category,settings_check=settings_check):
                status='hold_filter'
            else:
                row_pair=_paired_rows(service,context,category)
                if row_pair is None:status='hold_filter'
                else:
                    candidates=[row for row in row_pair[1] if row.get('equipped') is False and row.get('equipped_state')=='미장착' and row.get('grade') in ('흰','파랑','보라')]
                    # Reconcile a pending receipt even if the list has no new candidates.
                    count=1 if pending is not None else max(1,min(len(candidates),20))
                    for _ in range(count):
                        status=scan_one(service,context,identity,category,order,settings_check=settings_check)
                        if status!='hold_policy':break
            navigable=True
            results[str(category)]=status
            if (status.startswith('hold_') and status!='hold_policy') or status=='pending_confirmation':break
    finally:
        # Don't send a close input after cancellation or on an unknown popup.
        context.checkpoint();service.check()
        if not navigable:raise BlessingNavigationError('가호 상세 화면이 불확실해 종료 입력을 보류합니다')
        if not pair(blessing):raise BlessingNavigationError('가호 메뉴 종료 화면 확인 필요')
        if not pair(lambda frame:bool(service.detector.find('버튼_나가기',frame,threshold=.95))):
            raise BlessingNavigationError('가호 메뉴 종료 버튼 확인 필요')
        service.button('버튼_나가기',wait_before_click=.1,required=True);context.wait(.25)
        if not wait_pair(service,context,field):raise BlessingNavigationError('가호 종료 후 필드 확인 필요')
    return {'state':'processed_unverified','categories':results}
