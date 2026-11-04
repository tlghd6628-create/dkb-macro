"""Shared growth readings and goal decisions for the runtime and the checker.

Readers take a frame and never send input. Decisions are pure. The Guard, the
per-feature observers and the checker all answer "is this below its goal" and
"is the material/button state usable" here, so they cannot disagree.
"""
MATERIAL_ENOUGH='재료 충분';MATERIAL_SHORT='재료 부족'
KNOWN_MATERIALS=(MATERIAL_ENOUGH,MATERIAL_SHORT)
BUTTON_THRESHOLD=.95
BUTTON_BRIGHTNESS=(.90,1.30)
# Owner decision 2026-11-02: a stage that rose is success, the same stage is
# failure, and work continues to the configured goal. No failure screen or
# material count is needed. False stops new breakthrough input only.
BREAKTHROUGH_ENABLED=True
# The panel can still show the old stage just after a click. Wait this long
# first, so an attempt still animating is not read as a failure.
RESULT_SETTLE_SECONDS=1.5


def breakthrough_allowed():return BREAKTHROUGH_ENABLED is True


def material_status(native,detector,frame,root,detail=None):
    """The native detail result, then the shared original-region quantity reader."""
    status=detail.get('materials') if isinstance(detail,dict) else None
    if status in KNOWN_MATERIALS or root is None:return status
    from owner_growth_material_contract import inspect_materials
    result=inspect_materials(native,detector,frame,root)
    found=result.get('status') if isinstance(result,dict) else None
    return found if found in KNOWN_MATERIALS else status


def exec_button(detector,names,frame):
    """Exactly one native action button; brightness separates active from dimmed."""
    hits=[(name,hit) for name,hit in ((name,detector.find(name,frame,threshold=BUTTON_THRESHOLD)) for name in names) if hit]
    if len(hits)!=1:return {'name':None,'hit':None,'unique':False,'active':False}
    name,hit=hits[0];x1,y1,x2,y2=hit[2];patch=frame[y1:y2,x1:x2]
    reference=detector.templates.get(name);active=False
    if patch.size and reference is not None and reference.size and reference.mean()>0:
        active=BUTTON_BRIGHTNESS[0]<=float(patch.mean()/reference.mean())<=BUTTON_BRIGHTNESS[1]
    return {'name':name,'hit':hit,'unique':True,'active':bool(active)}


def goal_state(target,level,field='enhance'):
    """goal_missing | goal_off | goal_invalid | goal_reached | below"""
    if not isinstance(target,dict):return 'goal_missing'
    if target.get('enabled') is not True:return 'goal_off'
    goal=target.get(field)
    if type(goal) is not int or goal<0:return 'goal_invalid'
    return 'goal_reached' if level>=goal else 'below'


def enhance_decision(target,level,*,ready,materials):
    """(stage, finding) for one verified current value. Pure; no input."""
    state=goal_state(target,level)
    if state=='goal_off':return 'config','goal_off'
    if state!='below':return 'action_ready',state
    if ready is True:return 'action_ready','ready'
    if materials==MATERIAL_SHORT:return 'values','materials_short'
    return 'values','materials_unreadable'


FINDING_ORDER=('values_unreadable','materials_unreadable','goal_invalid','goal_missing','ready','materials_short',
               'enhancement_required','game_limit','goal_reached','goal_off')


def worst_row(rows):
    """The row a whole feature's verdict must show: a problem hides nothing."""
    rank=lambda row:FINDING_ORDER.index(row['finding']) if row.get('finding') in FINDING_ORDER else len(FINDING_ORDER)
    return min(rows,key=rank)


def extra_decision(target,level,*,field,maximum=False,needs_enhancement=False,ready=False):
    """(stage, finding) for awakening/breakthrough on one verified stage."""
    state=goal_state(target,level,field)
    if state=='goal_off':return 'config','goal_off'
    if state!='below':return 'action_ready',state
    if maximum is True:return 'action_ready','game_limit'
    if needs_enhancement is True:return 'action_ready','enhancement_required'
    if ready is True:return 'action_ready','ready'
    return 'values','materials_unreadable'
