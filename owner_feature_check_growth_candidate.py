"""Non-committing facades over the shared production readers."""

def read_enhancement(service, context, *, done=()):
    """Read one equipped gear item's grade and enhancement, without upgrading.

    The caller must already be on the equipment enhancement tab and own the
    only input worker. This may select an equipped item using the existing
    native selection routine; it never invokes a growth action. Unknown or
    inconsistent evidence is returned as unverified, not an inferred value.
    """
    from owner_native_contracts import pool_for
    from project_adapter import market_inventory as native
    from owner_gear_native_observer_candidate import Observer, Hold

    def unknown(reason):
        return {'verified':False,'decision_verified':False,'grade':None,'enhancement':None,'screen':'장비 강화 수치 미확인',
                'detail':str(reason)[:200]+' · 강화 실행 없음'}

    original=service.detector
    try:
        service.detector=pool_for(service).get('gear')
        # Observer enforces matching preselection equipment, grade, equipped
        # mark and same-item icon before calling the native selector.
        reader=Observer(service,context,'diagnostic',native,None,None)
        _,_,frame=reader.capture()
        if not service.detector.find(native.GROWTH_EQUIPMENT_TAB,frame,threshold=.95):
            return unknown('장비 성장 화면 확인 필요')
        rows=reader.items(frame)
        selected=native._growth_selected_slot(frame,rows)
        candidates=[row for row in rows if row.get('equipped') is True
                    and row.get('equipped_state')=='장착'
                    and row.get('grade') in ('흰','파랑','보라')
                    and type(row.get('index')) is int and row['index']!=selected and row['index'] not in done]
        if not candidates:
            if done:return {'verified':False,'exhausted':True}
            return unknown('선택 전 장착 장비와 등급 확인 필요')
        ticket=reader.prepare_and_select(candidates[0]['index'])
        # Reuse the product's final raw-crop reader and its fresh-glyph
        # revalidation; the native seed reader may briefly return4 for41.
        pair=reader.read_result_pair()
        if pair.get('screen_proof') is not True:return unknown(reader.last_reason)
        level=pair['second'].enhancement
        # Readiness comes from the exact read_pair the Guard uses before input.
        reader.minimum_level=level
        checked=reader.read_pair(True)
        ready=checked.get('screen_proof') is True and checked.get('active_pair_verified') is True
        materials=None
        if not ready:
            from owner_growth_reading import material_status
            found=[]
            for _ in range(2):
                _,_,current=reader.capture()
                found.append(material_status(native,service.detector,current,service.adapter.project.root))
                context.wait(.12)
            materials=found[0] if found[0]==found[1] else None
        service._owner_checker_gear=reader
        worn=sum(1 for row in rows if row.get('equipped') is True and row.get('equipped_state')=='장착')
        reader.checker_targets={'read':1,'total':worn,'unit':'장비'}
        return {'verified':True,'decision_verified':False,'screen':'장착 장비 강화 수치 확인',
                'detail':f"{ticket['grade']} +{level} · 실제 강화 실행 없음",
                'index':candidates[0]['index'],'grade':ticket['grade'],'enhancement':level,'materials':materials,'native_ready':ready,
                'hold_reason':None if ready else reader.last_reason,'targets':reader.checker_targets}
    except Hold as exc:
        return unknown(exc)
    finally:
        service.detector=original


def empty_extra_list(service,context,kind):
    """An explicit empty eligible-list is a condition, never stage zero."""
    import re
    from tools.ocr_support import get_paddle_engine
    from owner_progression import resized
    from owner_gear_extra_runtime_candidate import tab_selected
    from owner_gear_native_observer_candidate import Observer
    from project_adapter import market_inventory as native
    box=(710,275,173,20);frames=[]
    def has_item(frame):
        # Native returns every grid cell, including empty background cells.
        return any(row.get('equipped') is True or row.get('grade') in ('흰','파랑','보라','노랑')
                   for row in native.inspect_growth_equipment(service.detector,frame))
    engine=get_paddle_engine(service.adapter.project.root,language='korean')
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if (not tab_selected(frame,kind) or not service.detector.find(native.GROWTH_EQUIPMENT_TAB,frame,threshold=.95)
            or has_item(frame)):return False
        exact=[]
        for page in engine.predict(resized(frame,box)):
            for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
                if re.sub(r'[\s.!·]+','',str(text))=='등록할수있는대상이없습니다' and float(score)>=.92:exact.append(text)
        if len(exact)!=1:return False
        frames.append(frame.copy());context.wait(.08)
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if (not tab_selected(frame,kind) or has_item(frame)
            or not Observer._same_number_pixels(frames[-1],frame,box)):return False
        context.wait(.08)
    return True


def read_extra(service,context,kind):
    """Inspect an already selected same worn item, without material selection."""
    from owner_native_contracts import pool_for
    from owner_gear_extra_runtime_candidate import ExtraObserver
    source=getattr(service,'_owner_checker_gear',None)
    if source is None or source.service is not service or source.context is not context:
        return {'verified':False,'detail':'먼저 장비 강화 항목에서 같은 장착 장비의 현재값 확인 필요'}
    original=service.detector
    try:
        service.detector=pool_for(service).get('gear_extra')
        observer=ExtraObserver(source,kind)
        pair=observer.read_pair(resources=False,publish=False)
        if pair.get('screen_proof') is not True:
            if empty_extra_list(service,context,kind):
                return {'verified':False,'empty_verified':True,'detail':'등록 가능한 장비 없음 두 화면 확인 · 현재 돌파/각성 단계는 미확인'}
            return {'verified':False,'detail':observer.last_reason}
        value=pair['second'].awakening if kind=='awaken' else pair['second'].breakthrough
        if type(value) is not int:return {'verified':False,'detail':'현재 단계 판독 실패'}
        maximum=pair.get('maximum_reached') is True
        levels=getattr(source,'last_levels',())
        needs_enhancement=(kind=='breakthrough' and value==0 and len(levels)==2 and levels[0]==levels[1]
                           and type(levels[0]) is int and levels[0]<50)
        ready=False
        if not maximum and not needs_enhancement:
            checked=observer.read_pair(resources=True,publish=False)
            same=(checked.get('screen_proof') is True and checked['second'].grade==pair['second'].grade
                  and (checked['second'].awakening if kind=='awaken' else checked['second'].breakthrough)==value)
            ready=bool(same and checked.get('active_pair_verified') is True)
        return {'verified':True,'grade':pair['second'].grade,'current':value,'ready':ready,'maximum':maximum,
                'needs_enhancement':needs_enhancement,'observed_enhancement':levels[-1] if levels else None,
                'targets':getattr(source,'checker_targets',None)}
    finally:service.detector=original


def read_blessing(service,context,character,*,position=0):
    """Select one proven worn blessing and read it; no enhance/open/confirm."""
    import time
    from owner_native_contracts import pool_for
    from project_adapter import market_inventory as native
    from owner_blessing_native_candidate import worn_candidates,BlessingObserver
    original=service.detector
    missing=object();old_index=getattr(service,'growth_selected_index',missing);old_confirmed=getattr(service,'growth_selection_confirmed',missing)
    try:
        service.detector=pool_for(service).get('blessing')
        context.checkpoint();service.check();a=service.capture();at=time.monotonic();context.wait(.12)
        context.checkpoint();service.check();b=service.capture();bt=time.monotonic()
        first=worn_candidates(native,service.detector,a);second=worn_candidates(native,service.detector,b)
        if ([(r['index'],r['slot']) for r in first]!=[(r['index'],r['slot']) for r in second]
                or not second or not 0<bt-at<=1.5 or time.monotonic()-bt>1.5):
            return {'verified':False,'detail':'장착 가호 두 화면 일치 확인 실패'}
        if position>=len(second):return {'verified':False,'exhausted':True}
        row=second[position];slot=row['slot'];x,y=native._click_xy(slot)
        left,top,w,h=(slot[k] for k in ('cell_x','cell_y','cell_w','cell_h'))
        if not left<=x<left+w or not top<=y<top+h:return {'verified':False,'detail':'가호 선택 위치 확인 실패'}
        from owner_blessing_native_candidate import reveal_unselected
        def check():context.checkpoint();service.check()
        b=reveal_unselected(service,context,native,b,row,check)
        if b is None:return {'verified':False,'detail':'이미 선택된 가호의 아이콘 확인 실패'}
        # Native worn list and the fresh item icon must remain paired at input.
        context.checkpoint();service.check();fresh=service.capture()
        fresh_rows=worn_candidates(native,service.detector,fresh)
        same=next((r for r in fresh_rows if r['index']==row['index']),None)
        # Selecting a list item is reversible; re-prove the worn cell here,
        # then BlessingObserver independently proves the selected centre icon.
        # Animated full-cell backgrounds are not an item identity.
        if same is None or same['slot']!=row['slot']:
            return {'verified':False,'detail':'가호 선택 직전 아이템 변경'}
        service.click_hit((x,y,(left,top,left+w,top+h)));context.wait(.25)
        rows=native.inspect_growth_equipment(service.detector,b,blessing=True)
        observer=BlessingObserver(service,context,character,native,b,rows,row)
        pair=observer.read_pair(False,publish=False)
        if pair.get('screen_proof') is not True:
            proof=getattr(observer,'diagnostic_pair',None)
            if proof:
                from pathlib import Path
                from datetime import datetime
                from PIL import Image
                folder=Path(service.adapter.project.root)/'logs/feature-checks/screens';folder.mkdir(parents=True,exist_ok=True)
                stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                for index,frame in enumerate(proof):Image.fromarray(frame).save(folder/(stamp+f'-blessing-pair-{index}.png'))
            return {'verified':False,'detail':'가호 판독: '+getattr(observer,'last_reason','칸·현재 강화 수치 확인 필요')}
        state=observer.last_state
        return {'verified':True,'slot':str(state['slot'])+'번','level':state['level'],'ready':state['active'] is True,
                'materials':state.get('materials'),'targets':{'read':1,'total':len(second),'unit':'가호'}}
    finally:
        service.detector=original
        for key,value in (('growth_selected_index',old_index),('growth_selection_confirmed',old_confirmed)):
            if value is missing:
                if hasattr(service,key):delattr(service,key)
            else:setattr(service,key,value)


def read_styles(service,context,inputs):
    """Read paired visible style levels on the existing enhancement tab."""
    import time
    from owner_skill_ui import SkillUI
    from owner_skill_growth_candidate import LIST,tab,named_row,_same_pixels,refresh_evidence
    from owner_growth_policy_candidate import SKILL_REINFORCEMENT_TARGETS
    ui=SkillUI(service.adapter,context,inputs)
    frame=ui.frame()
    if not tab(frame):return {'verified':False,'detail':'도술 계열 강화 탭 미선택'}
    # A read-only list can retain independently agreeing rows without making
    # an unrelated OCR line a prerequisite for every other visible style.
    # Numeric foreground pixels are still re-proved below; no input follows.
    def agreement(first,second):
        for name in SKILL_REINFORCEMENT_TARGETS:
            try:
                row,a=named_row(first,name);other,b=named_row(second,name)
                if a==b and 0<=a<=50 and abs(row.get('y',0)-other.get('y',0))<=4:return True
            except Exception:continue
        return False
    ui.rows_batch([(LIST,'korean',.80,'original',None,agreement)])
    raw=getattr(ui,'_owner_last_rows_raw',None);pair=getattr(ui,'_owner_last_rows_pair',None)
    if not raw or not pair:return {'verified':False,'detail':'도술 계열 두 화면 판독 실패'}
    frames,ticks,answers=raw;current,current_ticks,_=pair;levels={}
    if (len(frames)!=2 or len(current)!=2 or not answers or len(answers[0])!=2
            or not all(tab(f) for f in (*frames,*current))):
        return {'verified':False,'detail':'도술 강화 화면 또는 판독 시각 불일치'}
    proofs=[]
    for name in SKILL_REINFORCEMENT_TARGETS:
        try:
            _,a=named_row(answers[0][0],name);row,b=named_row(answers[0][1],name)
            bounds=row.get('bounds')
            if a!=b or type(a) is not int or not bounds or len(bounds)!=4:continue
            l,t,r,bottom=map(int,bounds)
            if not 0<=l<r<=897 or not 0<=t<bottom<=479:continue
            source=frames[-1][t:bottom,l:r];box=(l,t,r-l,bottom-t)
            if all(_same_pixels(f,box,source,'text') for f in (*frames,*current)):
                levels[name]=a;proofs.append((box,source.copy(),ticks[-1],'text'))
        except Exception:
            context.checkpoint()
    if levels and any(not 0<=time.monotonic()-tick<=3 for tick in current_ticks):
        refresh_evidence(ui,lambda:True,frames,ticks,proofs,tab)
    return {'verified':bool(levels),'levels':levels,
            'detail':(' / '.join(f'{name} {level}강' for name,level in levels.items()) if levels else '도술 계열 강화 수치 판독 실패')}
