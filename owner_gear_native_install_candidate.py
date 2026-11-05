"""Opt-in per-item wrappers for the existing native growth routes.

Actual game execution is not verified; uncertain readings stop the action.
"""
from functools import wraps
import time
from owner_gear_native_observer_candidate import Hold
from owner_gear_execution_candidate import configured_targets,run_configured_step,reconcile_configured_step
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_settings_candidate import Store

_candidate_cursor={}
_candidate_continuation={}

def _legacy_intent_icon(service,native,before,pending):
    """Recover only an exact historical hash from nearby archived frames."""
    import hashlib
    from datetime import datetime,timedelta
    from pathlib import Path
    import numpy as np
    from PIL import Image
    stamp=pending.get('sent_at_epoch') or pending.get('created_at_epoch')
    if type(stamp) not in (int,float):return None
    try:
        when=datetime.fromtimestamp(stamp);index=int(before.slot.rsplit(':',1)[1])
        corpus=Path(service.adapter.project.root)/'logs/scene-corpus'/when.strftime('%Y%m%d')
        earliest=when-timedelta(minutes=5)
        folders=[]
        for path in corpus.glob(when.strftime('%Y%m%dT')+'*'):
            try:at=datetime.strptime(path.name[:15],'%Y%m%dT%H%M%S')
            except ValueError:continue
            if earliest<=at<=when:folders.append(path)
        for folder in sorted(folders,reverse=True)[:100]:
            path=folder/'screen.png'
            if not path.is_file():continue
            try:
                frame=np.asarray(Image.open(path).convert('RGB'))
                if frame.shape!=(479,897,3):continue
                rows=native.inspect_growth_equipment(service.detector,frame)
                row=next((r for r in rows if r.get('index')==index),None)
                if not row:continue
                slot=row['slot'];x,y=slot['cell_x']+8,slot['cell_y']+8;crop=frame[y:y+18,x:x+18]
                if crop.shape==(18,18,3) and 'icon:'+hashlib.sha256(crop.tobytes()).hexdigest()==before.item:
                    return crop.copy()
            except (OSError,ValueError,KeyError,TypeError):continue
    except (ValueError,OSError,OverflowError,TypeError,AttributeError):pass
    return None

def _report(service,message):
    log=getattr(service,'log',None)
    if callable(log):log(message)
    elif callable(getattr(log,'info',None)):log.info(message)

def _same_stable_icon(left,right):
    import numpy as np
    if not isinstance(left,np.ndarray) or not isinstance(right,np.ndarray) or left.shape!=(18,18,3) or right.shape!=left.shape:return False
    mask=np.ones((18,18),dtype=bool);mask[9:,9:]=False
    return bool(np.array_equal(left[mask],right[mask]))


def _post_equip_preference(frame,candidates,request):
    """Prioritize the freshly equipped icon, never authorize its growth."""
    import base64,json,cv2,numpy as np
    if not isinstance(request,dict) or request.get('verified_as')!='same_item':return None
    try:
        token=json.loads(request['candidate_item'])
        reference=np.frombuffer(base64.b64decode(token['icon_rgb'],validate=True),np.uint8).reshape((20,20,3))
    except (KeyError,TypeError,ValueError):return None
    scores=[]
    for row in candidates:
        if {'흰':'일반','파랑':'희귀','보라':'영웅'}.get(row.get('grade'))!=request.get('candidate_grade'):continue
        s=row['slot'];x,y=s['cell_x']+8,s['cell_y']+8;icon=frame[y:y+18,x:x+18]
        if icon.shape!=(18,18,3):continue
        score=float(cv2.minMaxLoc(cv2.matchTemplate(reference,icon[1:17,1:17],cv2.TM_CCOEFF_NORMED))[1])
        if np.isfinite(score):scores.append((score,row['index']))
    scores.sort(reverse=True)
    if not scores or scores[0][0]<.97 or (len(scores)>1 and scores[0][0]-scores[1][0]<.02):return None
    return scores[0][1]


def native_readers_factory(service,context,identity,targets,*,observation_sink=None):
    """Find one unselected, worn, configured gear cell using native detection.

    Index is a grid location, not proof of weapon/bracelet/ring priority.
    """
    from project_adapter import market_inventory as native
    from owner_gear_native_observer_candidate import Observer
    from owner_gear_extra_runtime_candidate import ensure_enhance_tab
    ensure_enhance_tab(service,context)
    observer=Observer(service,context,identity,native,None,None,observation_sink=observation_sink)
    _,_,frame=observer.capture();rows=observer.items(frame)
    selected=native._growth_selected_slot(frame,rows)
    grade_map={'흰':'일반','파랑':'희귀','보라':'영웅'}
    continuation=_candidate_continuation.get(identity)
    previous_observer=getattr(service.adapter,'_owner_growth_observer',None)
    if (continuation and continuation[0]==selected and continuation[2]==Store(service.adapter.project.root,identity).revision()
        and previous_observer is not None and isinstance(getattr(previous_observer,'ticket',None),dict) and previous_observer.context is context
        and previous_observer.character==identity and previous_observer.ticket.get('identity')==continuation[1]):
        # A selected tile hides its own E/grade badge. Temporarily select an
        # independently confirmed different worn tile, then re-prove the
        # priority tile from two unselected frames before any resource input.
        _,stamp_a,first=observer.capture();context.wait(.12);_,stamp_b,second=observer.capture()
        if (0<stamp_b-stamp_a<=1.5 and observer.clock()-stamp_b<=1.5 and
            previous_observer.identity_reader(first,selected,True)==continuation[1] and
            previous_observer.identity_reader(second,selected,True)==continuation[1]):
            first_rows=observer.items(first);second_rows=observer.items(second)
            for row in second_rows:
                before=next((r for r in first_rows if r.get('index')==row.get('index')),None)
                if (row.get('index')!=selected and before and row.get('equipped') is True and before.get('equipped') is True
                    and row.get('equipped_state')=='장착' and before.get('equipped_state')=='장착'
                    and row.get('grade') in grade_map and before.get('grade')==row.get('grade') and before.get('slot')==row.get('slot')):
                    context.checkpoint();service.check();native.select_growth_equipment(service,row)
                    _,_,frame=observer.capture();rows=observer.items(frame);selected=native._growth_selected_slot(frame,rows)
                    if selected!=row['index']:raise Hold('장비 목록 선택 확인 필요')
                    break
    candidates=[r for r in rows if type(r.get('index')) is int and r['index']!=selected
                and r.get('equipped') is True and r.get('equipped_state')=='장착'
                and targets.get(grade_map.get(r.get('grade')),{}).get('enabled') is True]
    # Worn items that showed a dim button this visit are not offered again (1→10→1 ended a visit before the white gear).
    skipped=getattr(service,'_owner_gear_no_stones',frozenset())
    candidates=[r for r in candidates if r['index'] not in skipped]
    # The lowest item of a grade costs the least, so a dim button there means the whole grade is short.
    short=getattr(service,'_owner_gear_short_grades',frozenset())
    candidates=[r for r in candidates if grade_map.get(r.get('grade')) not in short]
    if not candidates:
        # Every item looked at this visit stood at its goal: the one quiet end that finishes a level band.
        if skipped and not short:service.adapter._owner_growth_item_seen=context
        raise Hold('장착 장비 또는 선택 전 등급 확인 필요')
    # Rotate across visible worn cells between calls; list order is not a
    # reliable equipment-category or inventory identity indicator.
    priority={}
    saved=getattr(service.adapter,'_owner_gear_worn_frames',None)
    if isinstance(saved,dict) and saved.get('identity')==identity and saved.get('context') is context:
        try:
            stamp=saved.get('captured_monotonic')
            if type(stamp) in (int,float) and 0<=observer.clock()-stamp<=120:
                from owner_gear_priority_candidate import priority_indices,PRIORITY
                context.wait(.12);_,_,fresh=observer.capture()
                if native._growth_selected_slot(fresh,observer.items(fresh))==selected:
                    matched=priority_indices(saved.get('frames'),(frame,fresh),rows,saved.get('verified_worn'))
                    priority={matched[p]:i for i,p in enumerate(PRIORITY) if p in matched}
        except (TypeError,ValueError,KeyError,AttributeError):priority={}
    from owner_gear_levels import ceiling_for,levels_of,lowest_first
    levels=levels_of(service.adapter.project.root,frame,candidates,getattr(service,'_owner_gear_seen_levels',None),selected)
    candidates=lowest_first(candidates,levels,priority)
    preferred=_post_equip_preference(frame,candidates,getattr(service.adapter,'_owner_post_equip_target',None))
    chosen=next((r for r in candidates if r['index']==preferred),None) or candidates[0]
    service._owner_gear_chosen_lowest=chosen is candidates[0]
    service._owner_gear_ceiling=ceiling_for(chosen,candidates,levels)
    _report(service,f"강화 순서 · 칸별 수치={levels} · 고른 칸={chosen['index']} · 이번 상한={service._owner_gear_ceiling}")
    return observer,chosen['index']


def pending_readers_factory(service,context,identity,pending,*,identity_check=None):
    """Reselect only one uniquely matching equipped item from a sent intent."""
    import base64,hashlib,cv2,numpy as np
    from project_adapter import market_inventory as native
    from owner_gear_native_observer_candidate import Observer
    before=pending.get('before')
    if pending.get('kind')!='enhance' or before is None or before.character!=identity:
        raise Hold('이전 각성·돌파 결과는 별도 확인 필요')
    from owner_gear_extra_runtime_candidate import ensure_enhance_tab
    ensure_enhance_tab(service,context,identity_check=identity_check)
    observer=Observer(service,context,identity,native,None,None)
    service.adapter._owner_growth_pending_observer=observer
    _,_,frame=observer.capture();rows=observer.items(frame)
    selected=native._growth_selected_slot(frame,rows);matched=[]
    grades={'흰':'일반','파랑':'희귀','보라':'영웅'}
    try:saved_index=int(before.slot.rsplit(':',1)[1])
    except (ValueError,AttributeError,IndexError):saved_index=None
    if selected is not None and selected!=saved_index:
        raise Hold('다른 장비가 선택돼 이전 대상 확인 필요')
    alternative_icon=None
    if selected is not None and selected==saved_index:
        # Selection alone has no resource effect. Reveal the previously selected
        # tile by selecting another independently confirmed worn tile first.
        _,at_a,first=observer.capture();context.wait(.12);_,at_b,second=observer.capture()
        if not 0<at_b-at_a<=1.5 or observer.clock()-at_b>1.5:raise Hold('재확인 전 화면 지연')
        first_rows=observer.items(first);second_rows=observer.items(second)
        if native._growth_selected_slot(first,first_rows)!=selected or native._growth_selected_slot(second,second_rows)!=selected:
            raise Hold('재확인 전 선택 화면 변경')
        alternative=None
        for row in second_rows:
            old=next((r for r in first_rows if r.get('index')==row.get('index')),None)
            if (row.get('index')!=selected and old and row.get('equipped') is True and old.get('equipped') is True
                and row.get('equipped_state')=='장착' and old.get('equipped_state')=='장착'
                and row.get('grade') in grades and old.get('grade')==row.get('grade') and old.get('slot')==row.get('slot')):
                alternative=row;break
        if alternative is None:raise Hold('재확인용 다른 착용 장비 미확인')
        slot=alternative['slot'];x,y=slot['cell_x']+8,slot['cell_y']+8
        alternative_icon=second[y:y+18,x:x+18].copy()
        context.checkpoint();service.check()
        if callable(identity_check) and identity_check() is not True:raise Hold('캐릭터 또는 설정 변경')
        native.select_growth_equipment(service,alternative)
        _,_,frame=observer.capture();rows=observer.items(frame);selected=native._growth_selected_slot(frame,rows)
        if selected!=alternative['index']:raise Hold('재확인용 장비 선택 미확인')
    reference=None
    encoded=pending.get('item_icon')
    if isinstance(encoded,str):
        try:reference=np.frombuffer(base64.b64decode(encoded,validate=True),dtype=np.uint8).reshape((18,18,3))
        except (ValueError,TypeError):reference=None
        if reference is not None and 'icon:'+hashlib.sha256(reference.tobytes()).hexdigest()!=before.item:
            raise Hold('이전 강화 아이콘 기록이 일치하지 않음')
    previous=getattr(service.adapter,'_owner_growth_observer',None)
    if reference is None and previous is not None and getattr(previous,'character',None)==identity and isinstance(getattr(previous,'ticket',None),dict) and previous.ticket.get('identity')==before.item:
        old_pre=getattr(previous.identity_reader,'pre',None);old_rows=getattr(previous.identity_reader,'pre_rows',())
        old_row=next((r for r in old_rows if r.get('index')==saved_index),None)
        if isinstance(old_pre,np.ndarray) and old_row:
            s=old_row['slot'];x,y=s['cell_x']+8,s['cell_y']+8;crop=old_pre[y:y+18,x:x+18]
            if crop.shape==(18,18,3):reference=crop
    if reference is None:
        reference=_legacy_intent_icon(service,native,before,pending)
    if alternative_icon is not None and (reference is None or _same_stable_icon(reference,alternative_icon)):
        raise Hold('다른 장착 장비와 아이콘 구분 필요')
    for row in rows:
        if row.get('index')==selected:continue
        s=row.get('slot') or {};x=s.get('cell_x',-100)+8;y=s.get('cell_y',-100)+8
        icon=frame[y:y+18,x:x+18]
        if icon.shape!=(18,18,3):continue
        exact='icon:'+hashlib.sha256(icon.tobytes()).hexdigest()==before.item
        similar=False
        if reference is not None:
            delta=float(np.abs(reference.astype(np.float32)-icon.astype(np.float32)).mean())
            score=float(cv2.matchTemplate(reference,icon,cv2.TM_CCOEFF_NORMED)[0,0])
            similar=delta<=2.0 and np.isfinite(score) and score>=.99
            # +40→+41 is drawn into the bottom-right of the old 18x18 icon.
            # The other 243 pixels were exactly unchanged in both original
            # saved frames. Compare those pixels EXACTLY, with all visible
            # candidates in the uniqueness test; never lower similarity.
            similar=similar or _same_stable_icon(reference,icon)
        if exact or similar:matched.append(row)
    if item_gone(pending,rows,matched):
        # A second fresh look: one frame must not end a spending record.
        context.wait(.2);_,_,again=observer.capture();rows_again=observer.items(again)
        if rows_again and not any(_row_shows(again,row,before,reference) for row in rows_again):raise ItemGone('이전 강화 장비가 목록에 없음')
    if len(matched)!=1:raise Hold('이전 강화 장비를 유일하게 재확인하지 못함')
    if (matched[0].get('equipped') is not True or matched[0].get('equipped_state')!='장착'
        or grades.get(matched[0].get('grade'))!=before.grade):
        raise Hold('이전 강화 장비 장착 또는 등급 미확인')
    observer.logical_identity=before.item
    if type(before.enhancement) is int and before.enhancement>=0:observer.minimum_level=before.enhancement
    return observer,matched[0]['index']


ITEM_GONE_AFTER=3600
class ItemGone(Hold):
    """The item of an old, sent enhancement is no longer owned (dismantled, sold)."""

def item_gone(pending,rows,matched,*,now=None):
    """An hour on, no result can still arrive, and only a full list can show it is gone."""
    sent=pending.get('sent_at_epoch')
    return (not matched and bool(rows) and pending.get('phase')=='sent' and type(sent) in (int,float)
            and (time.time() if now is None else now)-sent>=ITEM_GONE_AFTER)

def _row_shows(frame,row,before,reference):
    import hashlib,numpy as np
    s=row.get('slot') or {}
    if 'cell_x' not in s or 'cell_y' not in s:return True
    x,y=s['cell_x']+8,s['cell_y']+8
    icon=frame[y:y+18,x:x+18]
    if icon.shape!=(18,18,3):return True
    if 'icon:'+hashlib.sha256(icon.tobytes()).hexdigest()==before.item:return True
    return reference is not None and (_same_stable_icon(reference,icon) or float(np.abs(reference.astype(np.float32)-icon.astype(np.float32)).mean())<=2.0)

def wrap(original,identity_resolver,readers_factory,*,clock=None,blessing_runner=None):
    @wraps(original)
    def guarded(service,*,blessing=False,_tried=frozenset()):
        context=service.context;context.checkpoint();service.check()
        if getattr(service.adapter,'_owner_worn_growth_context',None) is context:return False  # done by way of the bag
        if getattr(service,'_owner_gear_visit_started',None) is None:
            service._owner_gear_short_grades=frozenset();service._owner_gear_seen_levels={}
        try:
            root=service.adapter.project.root
            identity=identity_resolver(service)
            if not isinstance(identity,str) or not identity.strip():return False
            settings=Store(root,identity)
            document,revision=settings.snapshot()
            targets=document['grades']
        except (ValueError,OSError,TypeError,KeyError,AttributeError):return False
        if blessing:
            if getattr(service.adapter,'_owner_growth_reconcile_only',False) is True:return True
            if revision=='missing':return original(service,blessing=True)
            blessing_targets=document['blessings']
            if not any(row.get('enabled') is True for row in blessing_targets.values()):return False
            if not callable(blessing_runner):return False
            def current():return Store(root,identity).revision()==revision and identity_resolver(service)==identity
            return bool(blessing_runner(service,context,identity,blessing_targets,settings_check=current))
        if revision=='missing':
            if getattr(service.adapter,'_owner_growth_reconcile_only',False) is True:return False
            return original(service,blessing=False)
        reconcile_only=getattr(service.adapter,'_owner_growth_reconcile_only',False) is True
        if not any(row.get('enabled') is True for row in targets.values()) and not reconcile_only:
            # No grade is switched on, so a level band has nothing to come back for.
            service.adapter._owner_growth_item_seen=context
            return False
        if not callable(readers_factory) and not reconcile_only:return False
        try:
            settings_path=Store(root,identity).path
            intent_path=settings_path.with_name(settings_path.stem+'-intent.json')
            intent=IntentStore(intent_path);pending=intent.pending()
            if pending is not None and pending.get('phase')=='prepared':
                intent.abort_prepared('이전 실행의 입력 전 준비 기록');pending=None
            if pending is None and reconcile_only:return True
            if pending is not None:
                before=pending.get('before')
                if before is not None and before.slot.startswith('blessing:'):
                    # Blessing and ordinary equipment share the durable ledger.
                    # Never interpret a blessing icon as a worn weapon/armour.
                    if not callable(blessing_runner):
                        service.adapter._owner_growth_pending_hold=True
                        _report(service,'이전 가호 성장 결과 확인 경로가 필요합니다');return False
                    def current():return Store(root,identity).revision()==revision and identity_resolver(service)==identity
                    blessing_runner(service,context,identity,document['blessings'],settings_check=current,reconcile_only=True)
                    if intent.pending() is not None:
                        service.adapter._owner_growth_pending_hold=True
                        _report(service,'이전 가호 성장 결과 확인 보류');return False
                    return True
                if pending.get('kind') in ('awaken','breakthrough'):
                    # The outer extra decorator restores this exact item and
                    # reads its current stage; enhancement must not steal it.
                    service.adapter._owner_growth_pending_hold=True
                    _report(service,'이전 각성·돌파 결과 확인 경로로 전달');return False
                try:
                    service.adapter._owner_growth_pending_observer=None
                    def current():return Store(root,identity).revision()==revision and identity_resolver(service)==identity
                    if current() is not True:raise Hold('캐릭터 또는 설정 변경')
                    old_observer,old_index=pending_readers_factory(service,context,identity,pending,identity_check=current)
                    old_ticket=old_observer.prepare_and_select(old_index,selection_check=current)
                    if old_ticket['grade']!=pending['before'].grade:
                        raise Hold('이전 강화 장비 증거 불일치')
                    result='hold_result_unknown'
                    for attempt in range(3):
                        context.checkpoint();service.check()
                        result=reconcile_configured_step(context,root,identity,old_observer.read_result_pair,clock=clock,before_complete=current)
                        _report(service,f"이전 강화 결과 판독 · 칸={old_index} · 수치={getattr(old_observer,'last_levels',[])} · 방식={getattr(old_observer,'last_reason','미확인')} · 결과={result} · 확인={attempt+1}")
                        if result!='hold_result_unknown':break
                        if attempt<2:context.wait(.2)
                    if result!='observed_progress':
                        service.adapter._owner_growth_pending_hold=True
                        from owner_gear_hold_capture_candidate import enqueue
                        enqueue(root,'pending-result',getattr(old_observer,'last_reason','미확인'),tuple(getattr(old_observer,'last_frames',())))
                        _report(service,'이전 강화 결과를 재확인하지 못해 새 입력을 보류합니다');return False
                except ItemGone as exc:
                    intent.close_absent(str(exc))
                    _report(service,'이전 강화 기록 종료 · 대상 장비가 더 이상 없음 · 1시간 이상 지난 기록')
                except (Hold,ValueError,OSError,TypeError,KeyError,AttributeError) as exc:
                    service.adapter._owner_growth_pending_hold=True
                    reason=str(exc)[:100] if isinstance(exc,Hold) else type(exc).__name__
                    held=getattr(service.adapter,'_owner_growth_pending_observer',None)
                    if held is not None:
                        from owner_gear_hold_capture_candidate import enqueue
                        enqueue(root,'pending-select',reason,tuple(getattr(held,'last_frames',())))
                    _report(service,'이전 강화 장비를 재확인하지 못해 새 입력을 보류합니다 · 원인='+reason);return False
                if reconcile_only:return True
            pair=readers_factory(service,context,identity,targets)
            if not isinstance(pair,tuple) or len(pair)!=2:return False
            observer,index=pair
            ceiling=getattr(service,'_owner_gear_ceiling',None)
            observer.prepare_and_select(index)
            service._owner_gear_last_observer=observer
            service.adapter._owner_growth_observer=observer
            # Each item advances only one guarded input at a time. A confirmed
            # increment can continue on the same item during this native pass;
            # any unreadable result stops immediately with the intent retained.
            deadline=time.monotonic()+20
            status='hold_time_limit'
            numeric_retry=False;rereads=0
            for _ in range(50):
                context.checkpoint();service.check()
                if time.monotonic()>=deadline:break
                def current():return Store(root,identity).revision()==revision and identity_resolver(service)==identity
                status=run_configured_step(service,context,root,identity,'enhance',observer.read_pair,observer.verify_final,clock=clock,settings_check=current)
                ticket=observer.ticket or {};grade=ticket.get('grade');goal=targets.get(grade,{}).get('enhance')
                _report(service,f"성장 목표 검사 · 칸={index} · 등급={grade} · 수치={getattr(observer,'last_levels',[])} · 목표={goal} · 결과={status} · 사유={getattr(observer,'last_reason','미확인')}")
                seen=getattr(service,'_owner_gear_seen_levels',None)
                if seen is None:seen=service._owner_gear_seen_levels={}
                if getattr(observer,'last_levels',None):seen[index]=max(observer.last_levels)
                if status in ('hold_screen_unverified','hold_observation','hold_final_preinput','hold_boundary_preinput'):
                    from owner_gear_hold_capture_candidate import enqueue
                    enqueue(root,'growth-'+status,getattr(observer,'last_reason','미확인'),tuple(getattr(observer,'last_frames',())))
                if (status in ('hold_screen_unverified','hold_boundary_preinput') and not numeric_retry
                    and getattr(observer,'last_reason',None)=='강화 수치 불일치' and intent.pending() is None):
                    # Selection animation produced actual1/16 at13:14:10.
                    # Re-read one entirely fresh pair; never combine numbers,
                    # relax confidence, or retry a sent resource operation.
                    numeric_retry=True;observer.use_raw_input_numbers=True;context.wait(.15)
                    continue
                # One digit read .83 just after an enhance and ended the visit (+3 on 11-05). No input was sent.
                if (status=='hold_screen_unverified' and rereads<4 and intent.pending() is None
                    and getattr(observer,'last_reason',None)=='강화 수치 판독 실패'):
                    rereads+=1;context.wait(.4)
                    continue
                if status!='pending_confirmation':break
                for attempt in range(6):
                    context.wait(.35 if attempt==0 else .30)
                    context.checkpoint();service.check()
                    status=reconcile_configured_step(context,root,identity,observer.read_result_pair,clock=clock,before_complete=current,short_notice=lambda:_coins_short(service))
                    _report(service,f"성장 결과 확인 · 칸={index} · 수치={getattr(observer,'last_levels',[])} · 결과={status} · 사유={getattr(observer,'last_reason','미확인')} · 확인={attempt+1}")
                    if status in ('observed_progress','short_of_coins'):break
                if status=='short_of_coins':
                    service._owner_gear_coins_short=True
                    _report(service,'장비 강화 재화 부족 · 이번 차례 종료')
                if status!='observed_progress':break
                # A real enhance happened. Reading a dim button no longer counts for the level band.
                service.adapter._owner_growth_item_seen=context
                reached=getattr(observer,'last_levels',None) or []
                if reached:seen[index]=max(reached)
                if ceiling is not None and reached and max(reached)>=ceiling:break
            if intent.pending() is not None:
                service.adapter._owner_growth_pending_hold=True
                from owner_gear_hold_capture_candidate import enqueue
                enqueue(root,'growth-pending',getattr(observer,'last_reason','미확인'),tuple(getattr(observer,'last_frames',())))
            if status=='observed_progress':
                _candidate_continuation[identity]=(index,observer.ticket['identity'],revision)
            else:
                _candidate_continuation.pop(identity,None)
            # A rare weapon with no stones has a dim button and sends nothing, and it used to
            # end the visit with white gear still ready. Each worn item gets one look.
            started=getattr(service,'_owner_gear_visit_started',None) or time.monotonic()
            def next_item(tried):
                service._owner_gear_visit_started=started
                service._owner_gear_no_stones=tried
                try:return guarded(service,_tried=tried)
                finally:
                    service._owner_gear_no_stones=frozenset();service._owner_gear_visit_started=None
                    service._owner_gear_short_grades=frozenset();service._owner_gear_seen_levels={}
            if (status=='hold_screen_unverified' and getattr(observer,'last_reason',None)=='재료 또는 실행 버튼 미확인'
                and intent.pending() is None and index not in _tried):
                _report(service,f"성장 재료 없음 · 칸={index} · 다음 착용 장비 확인")
                if getattr(service,'_owner_gear_chosen_lowest',False) and (observer.ticket or {}).get('grade'):
                    service._owner_gear_short_grades=getattr(service,'_owner_gear_short_grades',frozenset())|{observer.ticket['grade']}
                return next_item(_tried|{index})
            # A turn ends just past the next lowest item, so stones spread across a grade.
            # The next visit reads the tiles again and picks up from the lowest.
            reached_turn=status=='observed_progress' and ceiling is not None
            if (status in ('observed_progress','hold_time_limit','hold_policy') and intent.pending() is None
                and (reached_turn or index not in _tried) and time.monotonic()-started<120):
                return next_item(_tried if reached_turn else _tried|{index})
            # Native caller result semantics are unverified; do not assert full
            # completion when one item advanced or an item was held.
            return False
        except (Hold,ValueError,OSError,TypeError,KeyError,AttributeError) as exc:
            # Without this line a quiet end looks the same as nothing left to do.
            _report(service,'장비 강화 대상 판단 종료 · '+(str(exc)[:100] if isinstance(exc,Hold) else type(exc).__name__))
            return False
    guarded._owner_gear_native_candidate=True
    return guarded


def _coins_short(service):
    from owner_short_notice import shown
    return shown(service.capture())


def _capture_extra_hold(service,root,phase,reason):
    """Keep the screen of an unresolved awakening/breakthrough result."""
    from owner_gear_hold_capture_candidate import enqueue
    try:enqueue(root,'extra-'+phase,str(reason),(service.capture().copy(),))
    except (OSError,ValueError,TypeError,AttributeError):pass


EXTRA_ITEMS_PER_PASS=12;EXTRA_PASS_SECONDS=120  # 11 worn slots; 8 never reached the last three

def wrap_extras_decorator(original_decorator,identity_resolver,extra_readers_factory=None,*,clock=None):
    """Keep custom targets from falling through to the native bulk extras.

    Optional factory(service, context, identity, targets, kind) must independently
    navigate/select and return (read_pair, verify_final), or None when unknown.
    The callback must be on the same input worker. Missing actual per-stage
    readers hold both extra stages; configured target values are not assumed.
    """
    @wraps(original_decorator)
    def decorate(original):
        native_batch=original_decorator(original)
        @wraps(original)
        def guarded(service,*args,**kwargs):
            # The blessing pass shares this entry and has no equipment extras.
            if kwargs.get('blessing'):return original(service,*args,**kwargs)
            context=service.context;context.checkpoint();service.check()
            if getattr(service.adapter,'_owner_worn_growth_context',None) is context:return False  # done by way of the bag
            try:
                root=service.adapter.project.root;identity=identity_resolver(service)
                if not isinstance(identity,str) or not identity.strip():return False
                document,revision=Store(root,identity).snapshot()
            except (ValueError,OSError,TypeError,KeyError,AttributeError):return False
            if revision=='missing':
                from owner_growth_reading import breakthrough_allowed
                # The native batch includes breakthrough, so it stays off too.
                return (native_batch if breakthrough_allowed() else original)(service,*args,**kwargs)
            path=Store(root,identity).path
            intent=IntentStore(path.with_name(path.stem+'-intent.json'))
            pending=intent.pending()
            if pending and pending.get('phase')=='prepared':
                intent.abort_prepared('이전 각성·돌파 입력 전 기록');pending=None
            reconcile_only=getattr(service.adapter,'_owner_growth_reconcile_only',False) is True
            if pending and pending.get('kind') in ('awaken','breakthrough'):
                resume=getattr(extra_readers_factory,'resume_pending',None)
                if not callable(resume):
                    service.adapter._owner_growth_pending_hold=True
                    _report(service,'이전 각성·돌파 대상 복원 경로 확인 필요');return False
                def current():return Store(root,identity).revision()==revision and identity_resolver(service)==identity
                pair=None
                try:
                    pair=resume(service,context,identity,document['grades'],pending,identity_check=current)
                    if not isinstance(pair,tuple) or len(pair)!=4 or not all(callable(x) for x in pair):
                        service.adapter._owner_growth_pending_hold=True;return False
                    outcome='hold_result_unknown'
                    for attempt in range(3):
                        context.checkpoint();service.check()
                        outcome=reconcile_configured_step(context,root,identity,pair[3],clock=clock,before_complete=current)
                        if outcome!='hold_result_unknown':break
                        if attempt<2:context.wait(.2)
                    _report(service,'이전 각성·돌파 결과 · '+outcome)
                    if outcome=='observed_failure':
                        finish=getattr(getattr(pair[3],'__self__',None),'finish_result',None)
                        if callable(finish):finish()
                    elif outcome!='observed_progress':
                        service.adapter._owner_growth_pending_hold=True
                        _capture_extra_hold(service,root,'resume-'+pending.get('kind',''),outcome);return False
                    service.adapter._owner_growth_pending_hold=False
                except (Hold,ValueError,OSError,TypeError,KeyError,AttributeError) as exc:
                    service.adapter._owner_growth_pending_hold=True
                    _report(service,'이전 각성·돌파 복원 보류 · '+str(exc)[:120]);return False
                finally:
                    if isinstance(pair,tuple) and len(pair)>=3 and callable(pair[2]):pair[2]()
                if reconcile_only:return True
            if reconcile_only:return original(service,*args,**kwargs)
            # Always invoke the separately guarded enhancement route; native
            # breakthrough/awakening batch is not called for custom settings.
            service._owner_gear_coins_short=False
            result=original(service,*args,**kwargs)
            if service._owner_gear_coins_short:
                _report(service,'장비 돌파·각성 건너뜀 · 재화 부족');return result
            targets=document['grades']
            if not callable(extra_readers_factory) or not any(r.get('enabled') is True for r in targets.values()):
                _report(service,'장비 돌파·각성 건너뜀 · 사용 등급 없음');return result
            if IntentStore(path.with_name(path.stem+'-intent.json')).pending() is not None:
                _report(service,'장비 돌파·각성 건너뜀 · 앞선 입력 결과 확인 대기');return result
            from owner_growth_reading import breakthrough_allowed
            service._owner_extra_tried={}
            pass_deadline=time.monotonic()+EXTRA_PASS_SECONDS
            for kind in ('awaken','breakthrough') if breakthrough_allowed() else ('awaken',):
                label={'awaken':'각성','breakthrough':'돌파'}[kind]
                # Each listed worn item once per pass: one at its goal must not end the rest.
                for turn in range(EXTRA_ITEMS_PER_PASS):
                    context.checkpoint();service.check()
                    if time.monotonic()>=pass_deadline:
                        _report(service,'장비 %s 이번 차례 시간 종료'%label);return result
                    try:pair=extra_readers_factory(service,context,identity,targets,kind)
                    except (Hold,ValueError,OSError,TypeError,KeyError,AttributeError) as exc:
                        _report(service,'장비 %s 대상 판단 종료 · %s'%(label,str(exc)[:100] if isinstance(exc,Hold) else type(exc).__name__+' '+str(exc)[:80]))
                        return result
                    if pair is False:continue
                    if pair is None:
                        _report(service,'장비 %s %s'%(label,'대상 없음' if turn==0 else '대상 확인 끝'));break
                    if not isinstance(pair,tuple) or len(pair) not in (2,3,4) or not all(callable(x) for x in pair):return result
                    # Never send an awakening without a separate post-result reader.
                    if kind=='awaken' and len(pair)!=4:return result
                    try:
                        def current():return Store(root,identity).revision()==revision and identity_resolver(service)==identity
                        deadline=time.monotonic()+30;after=None
                        for step in range(10):
                            context.checkpoint();service.check()
                            if time.monotonic()>=deadline:status='partial_time_limit';break
                            status=run_configured_step(service,context,root,identity,kind,pair[0],pair[1],clock=clock,settings_check=current)
                            if status!='pending_confirmation':
                                reader_owner=getattr(pair[0],'__self__',None)
                                last_pair=getattr(reader_owner,'last_pair',None)
                                if last_pair and isinstance(last_pair[0],dict) and last_pair[0].get('maximum'):
                                    status='game_cap_reached'
                                break
                            sent=intent.pending();post_reader=pair[3] if len(pair)==4 else pair[0]
                            if kind=='breakthrough':
                                from owner_growth_reading import RESULT_SETTLE_SECONDS
                                context.wait(RESULT_SETTLE_SECONDS)
                            for attempt in range(3):
                                context.checkpoint();service.check()
                                after=reconcile_configured_step(context,root,identity,post_reader,clock=clock,before_complete=current,short_notice=lambda:_coins_short(service))
                                if after!='hold_result_unknown':break
                                if attempt<2:context.wait(.2)
                            if after=='short_of_coins':
                                status='short_of_coins';break
                            if after=='observed_failure':
                                # Same stage. Continue toward the goal from a fresh
                                # reading, within this pass's step and time limits.
                                finish=getattr(getattr(post_reader,'__self__',None),'finish_result',None)
                                if callable(finish):finish()
                                status='observed_failure';continue
                            if after!='observed_progress':
                                service.adapter._owner_growth_pending_hold=True
                                _capture_extra_hold(service,root,'result-'+kind,after);break
                            # Continue only after a REAL durable sent request was
                            # reconciled. A mocked callback/ordinary True is not
                            # authority for another material input.
                            if sent is None or intent.pending() is not None:break
                            reader_owner=getattr(post_reader,'__self__',None)
                            finish=getattr(reader_owner,'finish_result',None)
                            if callable(finish):finish()
                            status='observed_progress'
                        service.adapter._owner_gear_extra_outcome={'kind':kind,'status':status,
                            'result':after}
                        if status=='game_cap_reached':
                            service.adapter._owner_gear_extra_outcome['game_cap']=last_pair[0]['current']
                        reader_owner=getattr(pair[0],'__self__',None)
                        _report(service,'장비 각성·돌파 목표 처리 · '+str(service.adapter._owner_gear_extra_outcome)+' · 사유='+str(getattr(reader_owner,'last_reason','미확인')))
                    finally:
                        if len(pair)>=3:pair[2]()
                    # Never progress with pending input.
                    if intent.pending() is not None or status.endswith('pending'):return result
                    if status=='short_of_coins':
                        _report(service,'장비 %s 재화 부족 · 이번 차례 종료'%label);return result
            return result
        return guarded
    decorate._owner_gear_extras_candidate=True
    return decorate


def _rebind_aliases(modules,old,new):
    """Rebind direct Python module aliases, not compiled closure internals."""
    if old is new:return
    for module in modules or ():
        values=getattr(module,'__dict__',{})
        for name,value in tuple(values.items()):
            if value is old:setattr(module,name,new)


def install(native_module,identity_resolver,readers_factory=None,*,clock=None,extra_module=None,extra_readers_factory=None,alias_modules=(),blessing_runner=None):
    from owner_gear_levels import install_real_rows
    install_real_rows(native_module)
    if not getattr(native_module.run_growth_equipment,'_owner_gear_native_candidate',False):
        original=native_module.run_growth_equipment
        guarded=wrap(original,identity_resolver,readers_factory,clock=clock,blessing_runner=blessing_runner)
        # The native entry calls its extras only after a native PARTIAL result, and this route
        # returns a plain bool, so they never ran. Native run_equipment_extras(service) stays
        # untouched for the native route (no settings file); configured targets run here.
        if extra_module is not None:
            guarded=wrap_extras_decorator(lambda route:route,identity_resolver,extra_readers_factory,clock=clock)(guarded)
            guarded._owner_gear_native_candidate=True
        native_module.run_growth_equipment=guarded
        _rebind_aliases(alias_modules,original,guarded)
    else:
        current=native_module.run_growth_equipment
        _rebind_aliases(alias_modules,getattr(current,'__wrapped__',current),current)
