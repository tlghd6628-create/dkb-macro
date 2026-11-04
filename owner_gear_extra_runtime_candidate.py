"""Bounded equipment awakening/breakthrough with durable result recovery.

Uses the original growth tabs, inventory detector, material checks and input
worker. A readable target is required before every resource input. Only the
exact base→single-diamond glyph validated by before/after evidence means0→1;
an unfamiliar symbolic transition never supplies a guessed numerical stage.
"""
from dataclasses import replace
from pathlib import Path
import base64,hashlib,time
import cv2
import numpy as np
from owner_gear_awaken_reader_candidate import read_explicit_stage,read_success_overlay,read_failure_overlay,asset_score,FAILURE_NOTICE_BOX
from owner_gear_decision_candidate import Observation


def tab_selected(frame,kind):
    if getattr(frame,'shape',None)!=(479,897,3):return False
    positions={'enhance':67,'breakthrough':101,'awaken':135}
    if kind not in positions:return False
    means={name:float(frame[y:y+20,14:73].mean()) for name,y in positions.items()}
    return means[kind]>=180 and all(means[kind]-v>=50 for name,v in means.items() if name!=kind)


def ensure_enhance_tab(service,context,*,identity_check=None):
    """Normalize a KNOWN equipment growth subtab, without resource inputs.

    The native list reader uses the enhancement list. Awakening/breakthrough
    hide terminal items, so their empty lists cannot locate a saved intent.
    """
    from owner_gear_native_observer_candidate import Hold
    from project_adapter import market_inventory as native
    from owner_native_contracts import pool_for
    detector=pool_for(service).get('gear')
    kinds=[]
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if not detector.find('체크_성장',frame,threshold=.95) or not detector.find(native.GROWTH_EQUIPMENT_TAB,frame,threshold=.95):
            raise Hold('장비 성장 메뉴 재확인 필요')
        found=[kind for kind in ('enhance','awaken','breakthrough') if tab_selected(frame,kind)]
        if len(found)!=1:raise Hold('장비 성장 하위탭 재확인 필요')
        kinds.append(found[0]);context.wait(.08)
    if kinds[0]!=kinds[1]:raise Hold('장비 성장 하위탭 변경')
    if kinds[-1]=='enhance':return
    context.checkpoint();service.check()
    if callable(identity_check) and identity_check() is not True:raise Hold('캐릭터 또는 설정 변경')
    # The known native enhancement subtab. This is a navigation coordinate,
    # not an item, material, or resource-confirmation button.
    service.click_hit((43,77,(14,67,73,87)));context.wait(.15)
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if not tab_selected(frame,'enhance') or not detector.find('체크_성장',frame,threshold=.95):
            raise Hold('장비 강화탭 복귀 확인 필요')
        context.wait(.08)


_STATIC_BOXES=((312,120,476,149),(330,384,462,409),(385,438,445,460),(460,438,496,460))
def same_static(first,second):
    """Only labelled foreground, never the animated transparent background."""
    if getattr(first,'shape',None)!=(479,897,3) or getattr(second,'shape',None)!=(479,897,3):return False
    def ink(frame,box):
        l,t,r,b=box;patch=frame[t:b,l:r];hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
        return (patch.min(axis=2)>155)|((hsv[:,:,0]>12)&(hsv[:,:,0]<40)&(hsv[:,:,1]>100)&(hsv[:,:,2]>150))
    if int(ink(first,_STATIC_BOXES[0]).sum())<3:return False
    return all(np.array_equal(ink(first,box),ink(second,box)) for box in _STATIC_BOXES)


def _reference(source):
    reader=source.identity_reader;pre=getattr(reader,'pre',None)
    row=next((r for r in getattr(reader,'pre_rows',()) if r.get('index')==source.ticket.get('index')),None)
    if not isinstance(pre,np.ndarray) or not row:return None
    slot=row.get('slot') or {};x=slot.get('cell_x',-100)+8;y=slot.get('cell_y',-100)+8
    icon=pre[y:y+18,x:x+18]
    return icon.copy() if icon.shape==(18,18,3) else None


def matching_item(source,frame,detector):
    """Find a unique original item in the visible native extra list."""
    from owner_gear_native_install_candidate import _same_stable_icon
    icon=_reference(source)
    if icon is None:return None
    rows=source.native.inspect_growth_equipment(detector,frame);matched=[]
    for row in rows:
        s=row.get('slot') or {};x=s.get('cell_x',-100)+8;y=s.get('cell_y',-100)+8
        patch=frame[y:y+18,x:x+18]
        if patch.shape!=icon.shape:continue
        if np.array_equal(patch,icon) or _same_stable_icon(icon,patch):matched.append(row)
    return matched[0] if len(matched)==1 else None


class ExtraObserver:
    def __init__(self,source,kind,*,stage_reader=read_explicit_stage,clock=time.monotonic):
        self.source=source;self.service=source.service;self.context=source.context
        self.native=source.native;self.kind=kind;self.clock=clock;self.stage_reader=stage_reader
        self.last_reason='각성·돌파 단계 미확인';self.last_pair=None
        self.icon=_reference(source)
        # A new extra intent's token must match its own saved icon bytes. A
        # recovered enhancement may carry an older logical token; that token
        # is valid for its old result, not a new extra's restart photograph.
        self.item=(getattr(source,'_owner_extra_pending_item',None)
                   or ('icon:'+hashlib.sha256(self.icon.tobytes()).hexdigest() if self.icon is not None else source.ticket['identity']))
        recent=list(getattr(source,'last_frames',()))
        self.center_reference=recent[-1][97:117,383:403].copy() if recent and getattr(recent[-1],'shape',None)==(479,897,3) else None
    def _guard(self):self.context.checkpoint();self.service.check()
    def _same_item(self,frame):
        # Independent centre/list comparison from the original observer.
        from owner_gear_awaken_observer_candidate import AwakeningObserver
        if AwakeningObserver(self.source)._same_item(frame):return True
        # Awakening needs an identical duplicate. Such an icon is legitimately
        # tied with the worn target. Keep the existing visual thresholds for
        # every DIFFERENT icon, and additionally prove the central worn-E.
        if self.icon is None or asset_score(frame,'extra_center_worn_e',(404,89,413,98))<.965:return False
        from owner_gear_native_install_candidate import _same_stable_icon
        center=cv2.resize(frame[97:117,383:403],(18,18),interpolation=cv2.INTER_AREA)
        own=float(cv2.matchTemplate(self.icon,center,cv2.TM_CCOEFF_NORMED)[0,0]);others=[]
        reader=self.source.identity_reader;pre=getattr(reader,'pre',None)
        if not isinstance(pre,np.ndarray):return False
        for row in getattr(reader,'pre_rows',()):
            s=row.get('slot') or {};x=s.get('cell_x',-100)+8;y=s.get('cell_y',-100)+8;patch=pre[y:y+18,x:x+18]
            if patch.shape!=(18,18,3):return False
            if np.array_equal(patch,self.icon) or _same_stable_icon(patch,self.icon):continue
            others.append(float(cv2.matchTemplate(patch,center,cv2.TM_CCOEFF_NORMED)[0,0]))
        return bool(np.isfinite(own) and own>=.80 and all(np.isfinite(v) and own-v>=.30 for v in others))
    def prepare_material(self):
        """Select one positively matching unworn duplicate, never auto-select."""
        if self.kind!='awaken' or getattr(self.source,'_owner_extra_pending_item',None):return
        from owner_gear_native_install_candidate import _same_stable_icon
        candidates=[]
        for _ in range(2):
            self._guard();frame=self.service.capture();state=self._state(frame,resources=False)
            if not state or state['current']!=0 or state['maximum']:return
            material=self.native.inspect_growth_materials(self.service.detector,frame)
            if material.get('status')=='재료 충분':return
            if material.get('status')!='재료 부족':return
            rows=self.native.inspect_growth_equipment(self.service.detector,frame);matches=[]
            for row in rows:
                if row.get('equipped') is True or row.get('equipped_state')!='미장착':continue
                grade={'흰':'일반','파랑':'희귀','보라':'영웅'}.get(row.get('grade'))
                if grade!=self.source.ticket['grade']:continue
                s=row.get('slot') or {};x=s.get('cell_x',-100)+8;y=s.get('cell_y',-100)+8;icon=frame[y:y+18,x:x+18]
                if icon.shape!=(18,18,3):continue
                if np.array_equal(icon,self.icon) or _same_stable_icon(icon,self.icon):matches.append(row)
            # Several duplicate materials are allowed; choose the first stable
            # grid row, not all cards or the game's unrestricted auto-select.
            if not matches:return
            candidates.append(sorted(matches,key=lambda r:r['index'])[0]);self.context.wait(.12)
        if candidates[0]!=candidates[1]:return
        row=candidates[1];slot=row['slot'];x,y=self.native._click_xy(slot)
        l,t,w,h=(slot[k] for k in ('cell_x','cell_y','cell_w','cell_h'))
        if not l<=x<l+w or not t<=y<t+h:return
        self._guard();self.service.click_hit((x,y,(l,t,l+w,t+h)));self.context.wait(.2)
    def _state(self,frame,*,resources=True):
        from project_adapter import growth_equipment_extra as extra
        if not resources and self.kind=='breakthrough':
            overlay=read_success_overlay(Path(self.service.adapter.project.root),frame)
            if overlay and self._overlay_same_item(frame):
                return dict(overlay,enhancement=None,active=False,button=extra.BREAK_BUTTON,maximum=False)
            failed=read_failure_overlay(Path(self.service.adapter.project.root),frame)
            if failed and self._overlay_same_item(frame):
                return dict(failed,current=None,next=None,enhancement=None,active=False,button=extra.BREAK_BUTTON,maximum=False)
        if not tab_selected(frame,self.kind) or not self._same_item(frame):return None
        result=self.stage_reader(Path(self.service.adapter.project.root),frame,self.kind)
        if not isinstance(result,dict):return None
        current,following=result.get('current'),result.get('next')
        maximum=result.get('maximum') is True
        if (type(current) is not int or current<0 or type(following) is not int
            or following!=(current if maximum else current+1)):return None
        enhancement=None
        if self.kind=='breakthrough':
            #50 is the INITIAL unlock requirement. An observed current
            # breakthrough>0 proves it has already passed; do not require the
            # post-breakthrough enhancement display to return to50 again.
            if current==0 and resources:
                levels=getattr(self.source,'last_levels',())
                if len(levels)!=2 or levels[0]!=50 or levels[1]!=50:return None
                if not 0<=self.clock()-self.source.ticket.get('captured_at',-1e30)<=180:return None
                enhancement=50
        active=False
        button=extra.AWAKE_BUTTON if self.kind=='awaken' else extra.BREAK_BUTTON
        if resources and not maximum:
            material=(self.native.inspect_growth_materials(self.service.detector,frame) if self.kind=='awaken'
                      else extra.inspect_breakthrough_materials(self.service.detector,frame))
            hit=self.service.detector.find(button,frame,threshold=.95)
            if isinstance(material,dict) and material.get('status')=='재료 충분' and hit:
                l,t,r,b=hit[2];patch=frame[t:b,l:r];ref=self.service.detector.templates.get(button)
                active=bool(patch.size and ref is not None and ref.size and ref.mean()>0 and .90<=patch.mean()/ref.mean()<=1.30)
        return {'current':current,'next':following,'enhancement':enhancement,'active':active,'button':button,'maximum':maximum}
    def _overlay_same_item(self,frame):
        if self.center_reference is None:return False
        patch=frame[215:255,426:473]
        needle=cv2.resize(self.center_reference,(18,18),interpolation=cv2.INTER_AREA)
        own=float(cv2.minMaxLoc(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED))[1])
        if not np.isfinite(own) or own<.80:return False
        # The centre reference was proved against the original worn target.
        # Compare different visible item types as competitors at the same size.
        from owner_gear_native_install_candidate import _same_stable_icon
        reader=self.source.identity_reader;pre=getattr(reader,'pre',None)
        if not isinstance(pre,np.ndarray):return False
        for row in getattr(reader,'pre_rows',()):
            s=row.get('slot') or {};x=s.get('cell_x',-100)+8;y=s.get('cell_y',-100)+8;ref=pre[y:y+18,x:x+18]
            if ref.shape!=(18,18,3):return False
            if np.array_equal(ref,self.icon) or _same_stable_icon(ref,self.icon):continue
            score=float(cv2.minMaxLoc(cv2.matchTemplate(patch,ref,cv2.TM_CCOEFF_NORMED))[1])
            if not np.isfinite(score) or own-score<.30:return False
        return True
    def _fresh_view(self,frame,state,proof):
        if state.get('overlay_success'):
            boxes=((386,189,511,207),(411,255,488,278),(421,446,474,460))
            from owner_gear_native_observer_candidate import Observer
            return bool(self._overlay_same_item(frame) and all(Observer._same_number_pixels(proof,frame,(l,t,r-l,b-t)) for l,t,r,b in boxes))
        if state.get('overlay_failure'):
            from owner_gear_native_observer_candidate import Observer
            return bool(self._overlay_same_item(frame) and all(Observer._same_number_pixels(proof,frame,(l,t,r-l,b-t)) for l,t,r,b in (FAILURE_NOTICE_BOX,(421,446,474,460))))
        return tab_selected(frame,self.kind) and self._same_item(frame) and same_static(frame,proof)
    def read_pair(self,resources=True,*,publish=True):
        states=[];frames=[]
        for _ in range(2):
            self._guard();frame=self.service.capture().copy();state=self._state(frame,resources=resources)
            if state is None:self.last_reason='선택 장비·현재/다음 단계 두 화면 확인 필요';return {'screen_proof':False}
            states.append(state);frames.append(frame);self.context.wait(.12)
        if states[0]!=states[1]:self.last_reason='각성·돌파 단계 또는 재료 변경';return {'screen_proof':False}
        # OCR may be slow. Two new exact static regions must re-prove the
        # classified state; the original OCR capture is never re-timestamped.
        fresh=[];ticks=[]
        for _ in range(2):
            self._guard();f=self.service.capture().copy();tick=self.clock()
            if not self._fresh_view(f,states[-1],frames[-1]):
                self.last_reason='각성·돌파 최종 화면 변경';return {'screen_proof':False}
            fresh.append(f);ticks.append(tick);self.context.wait(.08)
        if not 0<ticks[1]-ticks[0]<=1.5 or not 0<=self.clock()-ticks[0]<=1.5:return {'screen_proof':False}
        state=states[-1];obs=[]
        for tick in ticks:
            self.source.sequence+=1
            obs.append(Observation(self.source.sequence,tick,self.source.character,self.item,'growth-slot:'+str(self.source.ticket['index']),
                self.source.ticket['grade'],state['enhancement'],state['current'] if self.kind=='breakthrough' else None,
                state['current'] if self.kind=='awaken' else None,None,state['active'] if self.kind=='breakthrough' else None,
                state['active'] if self.kind=='awaken' else None))
        out={'screen_proof':True,'first':obs[0],'second':obs[1],'resource_mode':'native_active','action_mode':self.kind,
             'active_pair_verified':state['active'],'button_name':state['button'],
             'maximum_reached':bool(state['maximum']),'game_cap':state['current'] if state['maximum'] else None,
             'result_failed':state.get('overlay_failure') is True,
             'item_icon':base64.b64encode(self.icon.tobytes()).decode('ascii') if self.icon is not None else None}
        self.last_pair=(state,fresh[-1],ticks[-1]);self.last_reason='명시된 단계·동일 장비·재료 두 화면 확인'
        try:
            from owner_growth_current import observe
            field='breakthrough' if self.kind=='breakthrough' else 'awakening'
            if publish:
                observe(self.service.adapter.project.root,{'character':self.source.character,'item_identity':self.item,
                    'grade':self.source.ticket['grade'],field:state['current'],'verified_fields':[field],
                    'item_icon':base64.b64encode(self.icon.tobytes()).decode('ascii') if self.icon is not None else None})
        except (OSError,ValueError,TypeError):pass # display never authorizes input
        return out
    def read_result_pair(self):
        # A breakthrough animation precedes its result. Wait without input,
        # while still checking Stop at every iteration, instead of retrying a
        # resource button or treating the transitional scene as completion.
        end=self.clock()+8
        for _ in range(40):
            self._guard();frame=self.service.capture()
            root=Path(self.service.adapter.project.root)
            if tab_selected(frame,self.kind) or (self.kind=='breakthrough' and (read_success_overlay(root,frame) or read_failure_overlay(root,frame))):
                return self.read_pair(False)
            if self.clock()>=end:return {'screen_proof':False}
            self.context.wait(.2)
        return {'screen_proof':False}
    def finish_result(self):
        if not self.last_pair or not (self.last_pair[0].get('overlay_success') or self.last_pair[0].get('overlay_failure')):return
        goal=self.last_pair[0]['current'];views=[];shown='overlay_success' if self.last_pair[0].get('overlay_success') else 'overlay_failure'
        for _ in range(2):
            self._guard();frame=self.service.capture()
            if tab_selected(frame,self.kind):
                self.context.wait(.08);self._guard()
                if not tab_selected(self.service.capture(),self.kind):raise RuntimeError('돌파 결과 복귀 화면 재확인 필요')
                self.last_pair=None;return
            state=self._state(frame,resources=False)
            if not state or not state.get(shown) or state['current']!=goal:
                raise RuntimeError('돌파 결과 창 재확인 필요 · 원래 작업 복귀 보류')
            views.append(frame);self.context.wait(.08)
        self._guard();self.service.click_hit((448,452,(421,446,474,460)));self.context.wait(.25)
        for _ in range(2):
            self._guard();frame=self.service.capture()
            if not tab_selected(frame,self.kind):raise RuntimeError('돌파 결과 창 종료 후 성장 화면 확인 필요')
            self.context.wait(.08)
        self.last_pair=None
    def verify_final(self,frame,latest,kind):
        if kind!=self.kind or not self.last_pair:return False
        state,proof,stamp=self.last_pair
        return bool(state['active'] and 0<=self.clock()-stamp<=1.5 and tab_selected(frame,kind) and self._same_item(frame)
            and same_static(frame,proof))


class _TabNative:
    """The native list readers, with a plain cell click for selection.

    Native select_growth_equipment belongs to the enhance list. The extra tabs
    use the same grid, selected here the way this module always has.
    """
    def __init__(self,native):self._native=native
    def __getattr__(self,name):return getattr(self._native,name)
    def select_growth_equipment(self,service,row):
        from owner_gear_native_observer_candidate import Hold
        slot=row['slot'];x,y=self._native._click_xy(slot)
        l,t,w,h=(slot[k] for k in ('cell_x','cell_y','cell_w','cell_h'))
        if not (l<=x<l+w and t<=y<t+h):raise Hold('장비 칸 위치 확인 필요')
        service.click_hit((x,y,(l,t,l+w,t+h)))


_TAB_HITS={'breakthrough':(43,111,(14,101,73,121)),'awaken':(43,145,(14,135,73,155))}
def open_tab(service,context,kind):
    """The left subtab by its known box, as ensure_enhance_tab does. Navigation only.

    service.button only knows the names its TownServices was built with, and raised
    KeyError for these tabs on the first real run.
    """
    service.click_hit(_TAB_HITS[kind]);context.wait(.3)


def tab_source(service,context,identity,targets,kind,tab):
    """Pick the next worn item from this tab's own list; selection only, no resource input.

    Finished items leave the enhance list, so an item at +50 can only be found here.
    """
    from project_adapter import market_inventory as native
    from owner_gear_native_observer_candidate import Observer
    context.checkpoint();service.check()
    tried=getattr(service,'_owner_extra_tried',None)
    if not isinstance(tried,dict):tried=service._owner_extra_tried={}
    done=tried.setdefault(kind,set())
    if not tab_selected(service.capture(),kind):
        open_tab(service,context,kind)
    elif done:
        # Selecting an item narrows this list to that item. Leaving the tab restores it.
        service.click_hit((43,77,(14,67,73,87)));context.wait(.3)
        open_tab(service,context,kind)
    source=Observer(service,context,identity,_TabNative(native),None,None)
    # The list slides in after the tab changes. Read it once two frames agree.
    def shape(rows):return [(r.get('index'),r.get('grade'),r.get('equipped'),r.get('equipped_state')) for r in rows]
    first=second=None;rows=[]
    for _ in range(15):
        _,_,first=source.capture();context.wait(.2);_,_,second=source.capture()
        rows=source.items(second)
        if tab_selected(first,kind) and tab_selected(second,kind) and shape(source.items(first))==shape(rows):break
    else:
        return None
    grades={'흰':'일반','파랑':'희귀','보라':'영웅'}
    earlier={r.get('index'):r for r in source.items(first)}
    selected=native._growth_selected_slot(second,rows)
    from owner_gear_native_install_candidate import _report
    _report(service,'장비 %s 목록 · 착용 %d칸 · 이번에 본 칸 %s'%(kind,sum(r.get('equipped') is True for r in rows),sorted(done)))
    def wanted(row):
        old=earlier.get(row.get('index'))
        rule=targets.get(grades.get(row.get('grade')),{})
        return (type(row.get('index')) is int and row['index']!=selected and row['index'] not in done
                and old is not None and old.get('slot')==row.get('slot') and old.get('grade')==row.get('grade')
                and row.get('equipped') is True and row.get('equipped_state')=='장착'
                and old.get('equipped') is True and rule.get('enabled') is True and rule.get(kind,0)>=1)
    chosen=next((row for row in rows if wanted(row)),None)
    if chosen is None:return None
    done.add(chosen['index'])
    source.prepare_and_select(chosen['index'])
    context.wait(.25)
    # ExtraObserver keeps the centre icon of the last frame: it must show this item.
    source.capture()
    return source


def factory(service,context,identity,targets,kind,*,source=None,stage_reader=read_explicit_stage):
    """Navigate and select with native assets. Never sends a resource input."""
    if kind not in ('awaken','breakthrough'):return None
    from project_adapter import market_inventory as native,growth_equipment_extra as extra
    from owner_native_contracts import pool_for
    tab=extra.AWAKE_TAB if kind=='awaken' else extra.BREAK_TAB
    original=service.detector
    service.detector=pool_for(service).get('gear_extra')
    observer=None
    # False: this one item could not be confirmed, the rest of the list still gets its turn.
    skip=None if source is not None else False
    def cleanup():
        try:
            if observer is not None:observer.finish_result()
        finally:service.detector=original
    try:
        if source is None:source=tab_source(service,context,identity,targets,kind,tab)
        if source is None or source.context is not context or source.service is not service or source.character!=identity:
            cleanup();return None
        ticket=source.ticket
        goal='awaken' if kind=='awaken' else 'breakthrough'
        if not isinstance(ticket,dict) or targets.get(ticket.get('grade'),{}).get(goal,0)<1:
            cleanup();return None
        context.checkpoint();service.check();before=service.capture()
        # A prior extra may already have selected this same item. Comparison
        # uses its known centre, not a hidden selected-cell E/grade badge.
        probe=ExtraObserver(source,kind,stage_reader=stage_reader)
        if not (source.identity_reader(before,ticket['index'],True)==ticket['identity'] or probe._same_item(before)):
            from owner_gear_native_install_candidate import _report
            from owner_gear_hold_capture_candidate import enqueue
            _report(service,'장비 %s 선택 확인 안 됨 · 칸 %s'%(kind,ticket['index']))
            enqueue(service.adapter.project.root,'extra-select',kind,(before.copy(),))
            cleanup();return skip
        # Pressing the selected tab again could reset the list's selection.
        if not tab_selected(before,kind):
            open_tab(service,context,kind)
        pair=[];already_selected=[]
        for _ in range(2):
            context.checkpoint();service.check();frame=service.capture();row=matching_item(source,frame,service.detector)
            if not tab_selected(frame,kind):cleanup();return skip
            same=probe._same_item(frame)
            if row is None and not same:cleanup();return skip
            pair.append(row);already_selected.append(same);context.wait(.12)
        if already_selected!=[True,True]:
            if already_selected!=[False,False] or pair[0]!=pair[1]:cleanup();return skip
            row=pair[1];slot=row['slot'];x,y=native._click_xy(slot)
            l,t,w,h=(slot[k] for k in ('cell_x','cell_y','cell_w','cell_h'))
            if not l<=x<l+w or not t<=y<t+h:cleanup();return skip
            context.checkpoint();service.check();service.click_hit((x,y,(l,t,l+w,t+h)));context.wait(.2)
        observer=ExtraObserver(source,kind,stage_reader=stage_reader)
        observer.prepare_material()
        service.adapter._owner_growth_extra_observer=observer
        return observer.read_pair,observer.verify_final,cleanup,observer.read_result_pair
    except BaseException:cleanup();raise


def resume_factory(service,context,identity,targets,pending,*,identity_check=None):
    """Restore a sent extra's exact item before read-only reconciliation."""
    if pending.get('kind') not in ('awaken','breakthrough'):return None
    from owner_gear_native_install_candidate import pending_readers_factory
    # Reuse the existing icon/grade/worn-item recovery as a locator only. No
    # enhancement action is called and the durable original record is intact.
    view=dict(pending,kind='enhance');before=pending['before']
    view['before']=replace(before,enhancement=before.enhancement if type(before.enhancement) is int else 0)
    source,index=pending_readers_factory(service,context,identity,view,identity_check=identity_check)
    source.prepare_and_select(index,selection_check=identity_check)
    source.logical_identity=before.item
    source._owner_extra_pending_item=before.item
    service.adapter._owner_growth_observer=source
    return factory(service,context,identity,targets,pending['kind'],source=source)


factory.resume_pending=resume_factory
