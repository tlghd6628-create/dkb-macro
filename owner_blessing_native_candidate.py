"""Per-slot blessing growth through the existing input worker.

No batch fallback. A worn badge, selected icon, exact slot title, level and
native button are independently checked before a single action. No live game
input is performed during import or tests.
"""
from pathlib import Path
import hashlib,logging,re,time
import cv2
import numpy as np
from owner_gear_decision_candidate import Observation
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_settings_candidate import Store
from owner_gear_step_guard_candidate import Guard

_cursor={}
LOG=logging.getLogger('project_gui.DKB')
SETTLE_READS=8;RESULT_READS=8;TITLE_TOLERANCE=.01;REREADS=3
# One real frame takes five word reads, up to 2.8 s while the game runs (5562 ms a pair on 22:24), and nothing can read two inside 1.5 s.
# Each pair must still agree, and verify_final still reads a new frame right before the press.
PIXEL_PROOF_SECONDS=1.5;WORD_PROOF_SECONDS=12;PIXEL_BUDGET_SECONDS=20;WORD_BUDGET_SECONDS=45

def proof_seconds(frame):
    return WORD_PROOF_SECONDS if getattr(frame,'hi',None) is not None else PIXEL_PROOF_SECONDS

def same_white_text(source,current,box,tolerance=0.):
    """Exact white glyph proof, excluding the golden animated selection rim.

    `tolerance` is for the long title only: the scenery behind it flips a pixel
    (1 of 322 on the real screen), far fewer than a different slot digit changes.
    """
    x,y,w,h=box;a=source[y:y+h,x:x+w];b=current[y:y+h,x:x+w]
    if a.shape!=(h,w,3) or b.shape!=a.shape:return False
    masks=[]
    for patch in (a,b):
        hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
        white=((hsv[:,:,1]<60)&(hsv[:,:,2]>170)).astype(np.uint8)
        count,labels,stats,_=cv2.connectedComponentsWithStats(white,8)
        text=np.zeros(white.shape,dtype=bool)
        for index in range(1,count):
            l,t,cw,ch,area=stats[index]
            if 5<=ch<=18 and 1<=cw<=30 and area>=3:text|=labels==index
        masks.append(text)
    left,right=masks;both=left&right
    return bool(int(left.sum())>=3 and int((left^right).sum())<=int(left.sum())*tolerance and both.any()
                and float(np.abs(a[both].astype(float)-b[both].astype(float)).mean())<=5)

def worn_candidates(native,detector,frame):
    """Existing native badge template with paired colour and glyph evidence."""
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return []
    rows=native.inspect_growth_equipment(detector,frame,blessing=True)
    needle=detector.templates.get(native.GROWTH_EQUIPMENT_MARK)
    if needle is None or needle.shape!=(7,5,3):return []
    found=[]
    for row in rows:
        if row.get('equipped') is True and row.get('equipped_state')=='장착':
            found.append(row);continue
        if row.get('equipped_state')=='미장착':continue
        s=row['slot'];x,y,w,h=(s[k] for k in ('x','y','w','h'))
        area=frame[max(0,y-3):y+h+3,max(0,x-3):x+w+3]
        if area.shape[0]<7 or area.shape[1]<5:continue
        _,score,_,pos=cv2.minMaxLoc(cv2.matchTemplate(area,needle,cv2.TM_CCOEFF_NORMED))
        px,py=pos;glyph=area[py:py+7,px:px+5]
        hsv=cv2.cvtColor(glyph,cv2.COLOR_RGB2HSV)
        orange=int(((hsv[:,:,0]>=5)&(hsv[:,:,0]<=30)&(hsv[:,:,1]>70)&(hsv[:,:,2]>90)).sum())
        bright=int((hsv[:,:,2]>170).sum())
        if score>=.60 and orange>=20 and bright>=12:found.append(row)
    return found

def worn_unchanged(now,before,selected_index):
    """The selected tile draws a check over its worn badge, so only it may drop out."""
    others=[row for row in before if row[0]!=selected_index]
    seen=[(r['index'],r['slot']) for r in now]
    return [row for row in seen if row[0]!=selected_index]==others and len(seen)>=len(others)

def selected_matches(native,detector,pre,rows,index,current):
    if not isinstance(current,np.ndarray) or current.shape!=(479,897,3):return False
    # Search within the actual center icon; its position and scale vary slightly.
    center=current[87:127,373:413]
    if center.shape!=(40,40,3):return False
    scores=[];cells={}
    for row in rows:
        s=row['slot'];x,y=s['cell_x']+8,s['cell_y']+8;cell=pre[y:y+18,x:x+18]
        if cell.shape!=(18,18,3):return False
        score=float(cv2.minMaxLoc(cv2.matchTemplate(center,cell,cv2.TM_CCOEFF_NORMED))[1])
        if not np.isfinite(score):return False
        scores.append((row['index'],score));cells[row['index']]=cell
    own=next((score for i,score in scores if i==index),None)
    if own is None or own<.74:return False
    # An identically drawn second item cannot be separated by its icon. Only
    # the game's own selected-tile mark on this frame can tell them apart.
    twins=[i for i,_ in scores if i!=index and same_icon(cells[index],cells[i])]
    others=[score for i,score in scores if i!=index and i not in twins]
    if twins:
        selected=getattr(native,'_growth_selected_slot',None)
        if not callable(selected) or selected(current,rows)!=index:return False
    elif not others:return False
    return bool(not others or own-max(others)>=.30)

def same_icon(left,right):
    delta=float(np.abs(left.astype(np.float32)-right.astype(np.float32)).mean())
    if delta>2.0:return False
    score=float(cv2.matchTemplate(left,right,cv2.TM_CCOEFF_NORMED)[0,0])
    return bool(np.isfinite(score) and score>=.99)

def reveal_unselected(service,context,native,frame,row,check):
    """The selected tile draws a check mark over its icon, which is the reference.

    Selecting another tile has no resource effect. Returns a frame showing the
    row's own icon, or None when it cannot be revealed.
    """
    selected=getattr(native,'_growth_selected_slot',None)
    rows=native.inspect_growth_equipment(service.detector,frame,blessing=True)
    if not callable(selected) or selected(frame,rows)!=row['index']:return frame
    other=next((r for r in rows if r['index']!=row['index']),None)
    if other is None:return None
    s=other['slot'];x,y=native._click_xy(s)
    check();service.click_hit((x,y,(s['cell_x'],s['cell_y'],s['cell_x']+s['cell_w'],s['cell_y']+s['cell_h'])));context.wait(.25)
    check();fresh=service.capture()
    return None if selected(fresh,native.inspect_growth_equipment(service.detector,fresh,blessing=True))==row['index'] else fresh

def read_slot_title(root,frame):
    """Read only a visible `장식1`…`장식5` title; unknown stays unknown."""
    from tools.ocr_support import get_paddle_engine
    crop=frame[59:88,327:460]
    if crop.shape!=(29,133,3):return None
    image=cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
    engine=get_paddle_engine(root,language='korean');found=[]
    for page in engine.predict(image):
        for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
            text=re.sub(r'\s+','',str(text))
            match=re.search(r'장식([1-5])$',text)
            if match and float(score)>=.75:found.append(int(match.group(1)))
    return found[0] if len(found)==1 else None

class BlessingObserver:
    keep_item=False;word_hit=None  # keep_item: a record sent under its icon is being settled
    def __init__(self,service,context,identity,native,pre,rows,row,slot_reader=read_slot_title,*,clock=time.monotonic):
        self.service=service;self.context=context;self.identity=identity;self.native=native
        self.last_reason='장착 가호 선택 확인 필요'
        self.pre=pre;self.rows=rows;self.row=row;self.slot_reader=slot_reader;self.clock=clock;self.sequence=0;self.last_state=None;self._fresh_read_view=None
        s=row['slot'];x,y=s['cell_x']+8,s['cell_y']+8
        self.item='blessing-icon:'+hashlib.sha256(pre[y:y+18,x:x+18].tobytes()).hexdigest()
        import base64
        self.item_icon=base64.b64encode(pre[y:y+18,x:x+18].tobytes()).decode('ascii')
        import json
        root=Path(service.adapter.project.root)
        self.root=root;self.config=json.loads((root/'profiles/DKB/ocr_regions.json').read_text(encoding='utf-8'))['regions']['OCR_성장_장비레벨']
    def _word_state(self,frame):
        """Who, what level and what the next step takes, from the words on a real frame. The game's own mark on the
        list says the selected tile is the one pressed; the words then name it, so nothing compares icons."""
        from owner_growth_reading import MATERIAL_ENOUGH,MATERIAL_SHORT
        from owner_growth_words import read_blessing
        panel,reason=read_blessing(self.root,frame)
        if panel is None:
            self.last_reason=reason;return None
        selected=getattr(self.native,'_growth_selected_slot',None)
        if not callable(selected) or selected(frame,self.rows)!=self.row['index']:
            self.last_reason='선택 가호 목록 표시 불일치';return None
        names=self.native.GROWTH_BLESSING_EXEC_BUTTONS
        name={'강화':names[0],'개방':names[1]}.get(panel['word']);opening=name==names[1];level=panel['level']
        materials=MATERIAL_ENOUGH if panel['enough'] is True else MATERIAL_SHORT if panel['enough'] is False else None
        # A step that opens the next tier can show no counter, but a count that is short stays short.
        material=(level%10==9 and materials!=MATERIAL_SHORT) if opening else materials==MATERIAL_ENOUGH
        active=bool(name and panel['lit'] and type(panel['cost']) is int and panel['cost']>0 and panel['next']==level+1 and material)
        self.word_hit=panel['hit']
        said=(panel['identity'],level,panel['next'],panel['word'],panel['cost'],materials,active)
        if said!=getattr(self,'_said',None):
            self._said=said
            LOG.info('가호 글자 판독 · %s · %s→%s · %s %s · %s · 입력 가능=%s',panel['name']+str(panel['slot']),level,panel['next'],panel['word'],panel['cost'],materials,active)
        return {'slot':panel['slot'],'level':level,'active':active,'button':name,'opening':opening,'materials':materials,
                'identity':panel['identity'],'cost':panel['cost']}
    def _state(self,frame):
        self.context.checkpoint();self.service.check()
        if getattr(frame,'hi',None) is not None:return self._word_state(frame)
        if not selected_matches(self.native,self.service.detector,self.pre,self.rows,self.row['index'],frame):
            self.last_reason='선택 가호 중앙·목록 아이콘 일치 미확인';return None
        slot=self.slot_reader(self.root,frame)
        if type(slot) is not int or slot not in range(1,6):
            self.last_reason='가호 장착칸 제목 판독 실패';return None
        # Native detail accepts the independently verified selected index.
        self.service.growth_selected_index=self.row['index'];self.service.growth_selection_confirmed=True
        detail=self.native.read_growth_equipment_detail(self.service,frame,self.config,item=self.row)
        level=detail.get('enhancement') if isinstance(detail,dict) else None
        if type(level) is not int or level<0:
            self.last_reason='가호 현재 강화 수치 판독 실패';return None
        from owner_growth_reading import material_status,exec_button,MATERIAL_ENOUGH
        materials=material_status(self.native,self.service.detector,frame,self.root,detail)
        names=self.native.GROWTH_BLESSING_EXEC_BUTTONS
        button=exec_button(self.service.detector,names,frame)
        if button['unique'] is not True:
            # A read material state stays known even without a unique button.
            return {'slot':slot,'level':level,'active':False,'button':None,'opening':False,'materials':materials}
        name=button['name'];opening=name==names[1]
        material=(level%10==9) if opening else materials==MATERIAL_ENOUGH
        return {'slot':slot,'level':level,'active':bool(button['active'] and material),'button':name,'opening':opening,
                'materials':materials}
    def _same_read_view(self,frame,source,state):
        """Re-prove classified text on a NEW frame without repeating OCR."""
        if getattr(frame,'hi',None) is not None:
            # A reading of unchanged pixels comes back at once, so the words themselves are the proof.
            self.last_view_reason='글자 재확인';now=self._word_state(frame)
            return bool(now) and {k:v for k,v in now.items() if k!='materials'}=={k:v for k,v in state.items() if k!='materials'}
        self.last_view_reason='선택 가호 아이콘'
        if not selected_matches(self.native,self.service.detector,self.pre,self.rows,self.row['index'],frame):return False
        # The slot title occupies70..79. The old crop also contained the
        # icon's pulsing top rim at87 and falsely invalidated unchanged text.
        boxes=[(327,65,133,18)]
        def number_box(f):
            hit=self.service.detector.find(self.config['template_roi'],f,region=self.config['search_roi'],threshold=self.config.get('threshold',.85))
            return None if not hit else (hit[2][2]+self.config['rel_x'],hit[2][3]+self.config['rel_y'],self.config['w'],self.config['h'])
        numeric=number_box(source)
        self.last_view_reason='강화 수치 위치'
        if numeric is None or number_box(frame)!=numeric:return False
        boxes.append(numeric)
        # Only an action depends on the quantity text. A proven shortage sends
        # no input, so its partly coloured counter cannot invalidate the reading.
        if state['active'] and not state['opening']:
            entry=self.service.detector.entries.get('범위_성장_장비_재료수량',{})
            box=tuple(entry.get(k) for k in ('x','y','w','h'))
            if not all(type(v) is int for v in box):return False
            boxes.append(box)
        for index,box in enumerate(boxes):
            self.last_view_reason=('장착칸 제목','현재 강화 글자','재료 수량 글자')[index]
            if not same_white_text(source,frame,box,TITLE_TOLERANCE if index==0 else 0.):return False
        if state['active']:
            hit=self.service.detector.find(state['button'],source,threshold=.95)
            current=self.service.detector.find(state['button'],frame,threshold=.95)
            self.last_view_reason='실행 버튼 위치'
            if not hit or current!=hit:return False
            l,t,r,b=hit[2]
            self.last_view_reason='실행 버튼 상태'
            if not np.array_equal(source[t:b,l:r],frame[t:b,l:r]):return False
        return True
    def read_pair(self,require_resource=True,*,publish=True):
        obs=[];states=[];frames=[];self._fresh_read_view=None;self.diagnostic_pair=();started=time.monotonic()
        for _ in range(2):
            self.context.checkpoint();self.service.check();frame=self.service.capture();stamp=self.clock()
            state=self._state(frame)
            if state is None:
                self.diagnostic_pair=(*(f.copy() for f in frames[-1:]),frame.copy());return {'screen_proof':False}
            self.sequence+=1;states.append(state);frames.append(frame.copy())
            # Words name the item, unless a record sent under its icon is being settled.
            item=self.item if self.keep_item else state.get('identity',self.item)
            obs.append(Observation(self.sequence,stamp,self.identity,item,'blessing:'+str(state['slot']),
                str(state['slot'])+'번',state['level'],None,None,state['active'],None,None))
            self.context.wait(.12)
        a,b=obs
        self.last_timings={'initial_pair_ms':round((time.monotonic()-started)*1000,1)}
        # Material text alone cannot invalidate the reading: `active` already
        # carries every material state that can lead to an input.
        if {k:v for k,v in states[0].items() if k!='materials'}!={k:v for k,v in states[1].items() if k!='materials'}:
            self.last_reason='가호 두 화면의 칸·수치·버튼 불일치';self.diagnostic_pair=tuple(f.copy() for f in frames)
            return {'screen_proof':False}
        limit=proof_seconds(frames[-1])
        if not 0<b.captured_at-a.captured_at<=limit or self.clock()-a.captured_at>limit:
            from dataclasses import replace
            self.last_timings['refreshed_after_ocr']=True
            refreshed=[]
            for before in obs:
                self.context.checkpoint();self.service.check();current=self.service.capture();tick=self.clock()
                if not self._same_read_view(current,frames[-1],states[-1]):
                    if not getattr(self,'_view_retried',False):
                        # The first read after a selection is slow and catches the
                        # title still fading in. One whole new pair decides it.
                        self._view_retried=True;self.context.wait(.3)
                        return self.read_pair(require_resource,publish=publish)
                    self.last_reason='가호 새 화면: '+getattr(self,'last_view_reason','선택·칸·수치 변경')
                    self.diagnostic_pair=(frames[-1].copy(),current.copy())
                    return {'screen_proof':False}
                self.sequence+=1;refreshed.append(replace(before,sequence=self.sequence,captured_at=tick));self.context.wait(.08)
            a,b=refreshed
            if not 0<b.captured_at-a.captured_at<=limit or self.clock()-a.captured_at>limit:
                self.last_reason='가호 새 화면 재검증 시간 초과';return {'screen_proof':False}
            self._fresh_read_view=(current.copy(),states[-1],b.captured_at)
        self.last_state=dict(states[1])
        try:
            from owner_growth_current import observe_value
            if publish:
                observe_value(self.root,self.identity,'blessings',a.grade,
                              {'enhance':a.enhancement},verified=True,item_identity=a.item)
        except Exception:pass  # display-only, never execution authority
        if not require_resource:return {'screen_proof':True,'first':a,'second':b}
        state=states[0]
        return {'screen_proof':True,'first':a,'second':b,'resource_mode':'native_active',
                'active_pair_verified':state['active'],'button_name':state['button'],'opening':state['opening'],
                'item_icon':getattr(self,'item_icon',None)}
    def verify_final(self,frame,latest,kind):
        if kind!='enhance':return False
        if self._fresh_read_view is not None:
            proof,state,stamp=self._fresh_read_view;second=latest.get('second')
            return bool(state['active'] and 0<=self.clock()-stamp<=proof_seconds(frame) and isinstance(second,Observation)
                        and second.enhancement==state['level'] and second.grade==str(state['slot'])+'번'
                        and state['button']==latest.get('button_name') and state['opening']==latest.get('opening')
                        and self._same_read_view(frame,proof,state))
        state=self._state(frame);second=latest.get('second')
        if state and 'identity' in state and not self.keep_item and (state['identity']!=getattr(second,'item',None) or state.get('cost')!=(self.last_state or {}).get('cost')):return False
        return bool(state and isinstance(second,Observation) and state['active'] and state['level']==second.enhancement
                    and str(state['slot'])+'번'==second.grade and state['button']==latest.get('button_name')
                    and state['opening']==latest.get('opening'))

def _pending_matches(pending,rows,frame):
    """Worn rows showing the sent item's icon, by its exact hash or saved icon."""
    import base64
    from owner_gear_native_install_candidate import _same_stable_icon
    reference=None;encoded=pending.get('item_icon')
    if isinstance(encoded,str):
        try:reference=np.frombuffer(base64.b64decode(encoded,validate=True),dtype=np.uint8).reshape((18,18,3))
        except (ValueError,TypeError):reference=None
    matches=[]
    for row in rows:
        s=row['slot'];x,y=s['cell_x']+8,s['cell_y']+8;icon=frame[y:y+18,x:x+18]
        exact='blessing-icon:'+hashlib.sha256(icon.tobytes()).hexdigest()==pending['before'].item
        if exact or (reference is not None and icon.shape==(18,18,3) and _same_stable_icon(reference,icon)):matches.append(row)
    return matches

class PreInputHold(RuntimeError):
    """The last look before a press did not hold up. Nothing was sent, so this is a read to retry, not a failure."""


def _named_by_words(pending):
    return str(getattr(pending.get('before'),'item','')).startswith('blessing-words:')


def _shown_words(root,frame):
    """(the name of what the panel shows, reason), for finding the tile a sent step belongs to."""
    if getattr(frame,'hi',None) is None:return None,'실제 화면 없음'
    from owner_growth_words import read_blessing
    panel,reason=read_blessing(root,frame)
    return (panel['identity'],None) if panel else (None,reason)


def _ordered_rows(rows,previous):
    return [row for row in rows if row['index']>previous]+[row for row in rows if row['index']<=previous]


def _growth_status(observer,targets,status):
    state=observer.last_state
    if not state:return status
    from owner_growth_reading import goal_state
    goal=targets.get(str(state['slot'])+'번',{})
    decision=goal_state(goal,state['level'])
    if decision=='goal_off':return 'disabled'
    if decision=='goal_reached':
        # A configured breakthrough is not silently treated as accomplished.
        if goal.get('breakthrough',0)>0:return 'hold_breakthrough_screen_unverified'
        return 'targets_met'
    if status=='hold_policy' and not state['active']:return 'hold_material_or_button'
    return status


def run_blessing(service,context,identity,targets,*,slot_reader=read_slot_title,settings_check=None,reconcile_only=False):
    """Visit each verified worn item; reconcile every input before continuing.

    Preserve the native caller's False return contract. The separate outcome
    records current/target/confirmed actions and is never a completion guess.
    """
    from project_adapter import market_inventory as native
    from owner_native_contracts import pool_for
    outcome={'state':'hold_identity','slots':{},'actions':0,'confirmed':0}
    service.adapter._owner_blessing_growth_outcome=outcome
    if not isinstance(identity,str) or not identity.strip():return False
    if not isinstance(targets,dict):outcome['state']='hold_settings';return False
    store=Store(service.adapter.project.root,identity)
    path=store.path.with_name(store.path.stem+'-intent.json');intents=IntentStore(path)
    pending=intents.pending()
    if pending and pending.get('phase')=='prepared':
        intents.abort_prepared('가호 입력 전 준비 기록');pending=None
    if pending and (pending.get('kind')!='enhance' or not pending['before'].slot.startswith('blessing:') or pending['before'].character!=identity):
        outcome['state']='hold_other_growth_pending';return False
    if reconcile_only and not pending:outcome['state']='nothing_pending';return True
    if not pending and not any(isinstance(goal,dict) and goal.get('enabled') is True for goal in targets.values()):
        outcome['state']='disabled';return False
    def current():
        context.checkpoint();service.check()
        if callable(settings_check) and settings_check() is not True:raise RuntimeError('가호 설정 또는 캐릭터 변경')
    def current_check():current();return True
    original=service.detector
    missing=object();old_index=getattr(service,'growth_selected_index',missing);old_confirmed=getattr(service,'growth_selection_confirmed',missing)
    service.detector=pool_for(service).get('blessing')
    root=service.adapter.project.root
    def hold(state,reason,frames=()):
        """Keep the exact stage and its screens on the running path too."""
        from owner_outcome import report,Outcome,NOT_ATTEMPTED
        from owner_gear_hold_capture_candidate import enqueue
        outcome['state']=state;outcome['reason']=reason
        enqueue(root,'blessing-'+state,reason,tuple(frames))
        report(service.adapter,'gear',Outcome(NOT_ATTEMPTED,'가호 '+reason,stage=state))
        LOG.warning('가호 성장 보류 · %s · %s',state,reason)
        return False
    try:
        # The common entry opens on the equipment tab, whose list is not this one.
        current();hit=service.detector.find(native.GROWTH_BLESSING_TAB,service.capture(),threshold=.9)
        click=getattr(service,'click_hit',None)
        if hit and callable(click):
            click(hit);context.wait(.6)
        # The list draws in after a tab change: the same two-frame proof, a little later.
        for attempt in range(SETTLE_READS):
            current();a=service.capture();stamp_a=time.monotonic();context.wait(.12)
            current();b=service.capture();stamp_b=time.monotonic()
            first=worn_candidates(native,service.detector,a);second=worn_candidates(native,service.detector,b)
            aa=[(r['index'],r['slot']) for r in first];bb=[(r['index'],r['slot']) for r in second]
            if aa==bb and second and 0<stamp_b-stamp_a<=proof_seconds(b) and time.monotonic()-stamp_b<=proof_seconds(b):break
            if attempt<SETTLE_READS-1:context.wait(.3)
        else:
            return hold('hold_worn_list','장착 가호 두 화면 불일치',(a,b))
        if pending and _named_by_words(pending):
            # Its name shows only once selected, so each worn tile is looked at. Selecting spends nothing.
            selected=list(second)
        elif pending:
            matches=_pending_matches(pending,second,b)
            if len(matches)!=1:
                # A restart may leave this item selected, hiding its icon.
                shown=reveal_unselected(service,context,native,b,{'index':next((r['index'] for r in second),0)},current) if not matches else None
                if shown is not None and shown is not b:
                    b=shown;stamp_b=time.monotonic();matches=_pending_matches(pending,second,b)
            if len(matches)!=1:return hold('hold_pending_item','이전 입력 대상 가호 유일 확인 실패',(a,b))
            selected=[matches[0]]
        else:
            selected=_ordered_rows(second,_cursor.get(identity,0))
        outcome['state']='processing'
        for offset,row in enumerate(selected):
            current()
            if offset:
                # The previous item may have changed its printed level. Reuse
                # only its stable icon and recheck the whole current worn list.
                a=service.capture();stamp_a=time.monotonic();context.wait(.12);current();b=service.capture();stamp_b=time.monotonic()
                now_a=worn_candidates(native,service.detector,a);now_b=worn_candidates(native,service.detector,b)
                previous=selected[offset-1]['index']
                if not worn_unchanged(now_a,aa,previous) or not worn_unchanged(now_b,aa,previous):
                    return hold('hold_worn_list','장착 가호 목록 변경',(a,b))
            if not 0<stamp_b-stamp_a<=proof_seconds(b) or time.monotonic()-stamp_b>proof_seconds(b):
                return hold('hold_worn_list','장착 가호 화면 시각 초과',(a,b))
            slot=row['slot'];x,y=native._click_xy(slot);left,top,w,h=(slot[k] for k in ('cell_x','cell_y','cell_w','cell_h'))
            if not (left<=x<left+w and top<=y<top+h):return hold('hold_selection','가호 선택 위치 확인 실패',(b,))
            b=reveal_unselected(service,context,native,b,row,current)
            if b is None:return hold('hold_selection','이미 선택된 가호의 아이콘 확인 실패',(a,))
            current();service.click_hit((x,y,(left,top,left+w,top+h)));context.wait(.25)
            _cursor[identity]=row['index']
            rows=native.inspect_growth_equipment(service.detector,b,blessing=True)
            observer=BlessingObserver(service,context,identity,native,b,rows,row,slot_reader)
            observer.keep_item=bool(pending) and not _named_by_words(pending)
            def result_after_glow():
                # The icon flashes for about a second after a real enhancement.
                # Same result reader on fresh frames; never a second resource input.
                result='hold_result_unknown'
                for attempt in range(RESULT_READS):
                    current()
                    result=Guard(context,intents,lambda:observer.read_pair(False),fresh_seconds=proof_seconds(b)).reconcile(before_complete=current_check)
                    if result!='hold_result_unknown':break
                    if attempt<RESULT_READS-1:context.wait(.35)
                return result
            if pending:
                if _named_by_words(pending):
                    current();context.wait(.3);shown,_=_shown_words(root,service.capture())
                    if shown!=pending['before'].item:continue  # not this tile; nothing was sent to it
                result=result_after_glow()
                if result!='observed_progress':outcome['state']=result;return False
                pending=None;outcome['confirmed']+=1
                if reconcile_only:outcome['state']='observed_progress';return True
            def click(latest,mark_sent):
                current();frame=service.capture()
                if not observer.verify_final(frame,latest,'enhance'):raise PreInputHold('가호 입력 직전 확인 실패')
                if not current_check():raise RuntimeError('가호 설정 또는 캐릭터 변경')
                name=latest.get('button_name')
                if name not in native.GROWTH_BLESSING_EXEC_BUTTONS:raise PreInputHold('가호 실행 버튼 확인 필요')
                # On a real frame the words verify_final just read on this same frame name the place.
                hit=observer.word_hit if getattr(frame,'hi',None) is not None else service.detector.find(name,frame,threshold=.95)
                if not hit:raise PreInputHold('가호 실행 버튼 미확인')
                current();mark_sent();current();service.click_hit(hit);outcome['actions']+=1
            guard=Guard(context,intents,observer.read_pair,fresh_seconds=proof_seconds(b))
            deadline=time.monotonic()+(WORD_BUDGET_SECONDS if getattr(b,'hi',None) is not None else PIXEL_BUDGET_SECONDS);status='budget_wait';rereads=0
            for _ in range(50):
                current()
                if time.monotonic()>=deadline:break
                try:status=guard.run_one('enhance',targets,click)
                except PreInputHold as exc:
                    observer.last_reason=str(exc);status='hold_boundary_preinput'
                # The number redraws after a step (37 read as 3). Nothing was sent
                # on that read; look again before giving up this item.
                on_words=getattr(b,'hi',None) is not None
                if rereads<REREADS and (status=='hold_screen_unverified' and (outcome['confirmed'] or on_words) or status=='hold_boundary_preinput' and on_words):
                    rereads+=1;context.wait(.5);continue
                if status!='pending_confirmation':break
                rereads=0
                context.wait(.35)
                status=result_after_glow()
                if status!='observed_progress':
                    outcome['state']=status;return False
                outcome['confirmed']+=1
            state=observer.last_state or {}
            outcome['slots'][str(row['index'])]={'state':_growth_status(observer,targets,status),'slot':state.get('slot'),
                'current':state.get('level'),'target':targets.get(str(state.get('slot'))+'번',{}),
                'reason':getattr(observer,'last_reason',''),'timings':getattr(observer,'last_timings',{})}
            if status in ('hold_screen_unverified','hold_observation','hold_boundary_preinput'):
                # Later items still get their turn; this stage stays reported.
                from owner_outcome import report,Outcome,NOT_ATTEMPTED
                from owner_gear_hold_capture_candidate import enqueue
                reason=getattr(observer,'last_reason','화면 확인 필요')
                enqueue(root,'blessing-'+status,reason,tuple(getattr(observer,'diagnostic_pair',())))
                report(service.adapter,'gear',Outcome(NOT_ATTEMPTED,'가호 '+reason,stage=status))
        if pending:return hold('hold_pending_item','이전 입력 대상 가호 글자 확인 실패',(b,))
        outcome['state']='processed_unverified'
        return False
    finally:
        if outcome['state']=='processing':outcome['state']='interrupted_unverified'
        LOG.info('가호 성장 결과 · %s',outcome)
        service.detector=original
        for name,old in (('growth_selected_index',old_index),('growth_selection_confirmed',old_confirmed)):
            if old is missing:
                try:delattr(service,name)
                except AttributeError:pass
            else:setattr(service,name,old)
