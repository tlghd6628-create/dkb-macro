"""Fill preset 2 with the catalog's single-target deck, then go back to preset 1.

Uses the existing guarded SkillUI steps. A skill not learned yet is reported, never bought here.
A stop in between leaves the game on preset 2, so a file says so until the next run has gone back.
"""
import logging
from pathlib import Path
LOG=logging.getLogger('project_gui.DKB')

SUBSTITUTES={'찌르기':'삼단 찌르기'}

def _flag(adapter):return Path(adapter.project.root)/'settings/owner-preset-return.flag'

def mark(adapter,on):
    """Failing to note this must not cost the raid or the deck it is noted for."""
    try:
        if on:_flag(adapter).write_text('1',encoding='ascii')
        else:_flag(adapter).unlink(missing_ok=True)
    except (OSError,AttributeError) as exc:LOG.warning('프리셋 복귀 표시 실패 · %s',exc)

def resume(adapter,context,inputs):
    """On the field at the start of a run: back to preset 1 if the last run was stopped on another."""
    flag=_flag(adapter)
    if not flag.exists():return False
    from owner_skill_ui import SkillUI
    from owner_skill_goal import Pending
    ui=SkillUI(adapter,context,inputs)
    try:
        ui.select_preset(1);context.checkpoint();ui.close_known()
    except Pending as exc:
        LOG.warning('프리셋 1번 복귀 보류 · %s',exc);return False
    flag.unlink(missing_ok=True)
    text='이전 중지로 남은 프리셋을 1번으로 복귀'
    LOG.info(text,extra={'gui_message':text,'state_transition':True})
    return True

def configure(adapter,context,inputs):
    from owner_skill_ui import SkillUI
    from owner_skill_goal import Pending
    # A half-built deck in a monster field killed the character while this menu was open (11-05 10:41).
    if adapter.run_town_return(context,inputs) is False:raise Pending('단일 덱 구성 전 마을 복귀 미확인')
    context.checkpoint()
    ui=SkillUI(adapter,context,inputs)
    # Stopped halfway, the game stays on this half-built deck: real power fell 151,740 to 123,852.
    mark(adapter,True)
    row=ui.public['presets']['single']
    slots=[s['id'] for s in row['slots']]
    order=[s['id'] for s in row['order']]
    order.insert(row['ultimate_at'],row['ultimate']['id'])
    ui.select_preset(2)
    context.checkpoint()
    placed=[];missing=[]
    def wear_each(sid):
        context.checkpoint()
        name=ui._skill_info(sid)['name']
        # The left panel slides when a row is picked, so an early pair of reads disagrees.
        for attempt in range(3):
            try:
                ui.wear(sid);placed.append(sid)
                LOG.info('프리셋 2번 장착 · %s',name);return True
            except Pending as exc:
                LOG.info('프리셋 2번 장착 재시도 · %s · %s',name,str(exc)[:60])
                # Missing twice from the owned list means not learned; a third whole pass only costs time.
                if attempt==1 and '찾지 못함' in str(exc):return False
                context.wait(.8)
        return False
    for sid in slots+[row['ultimate']['id']]:
        if wear_each(sid):continue
        # Not learned on this character. Keeps the deck full; the skill is never bought here.
        other=SUBSTITUTES.get(ui._skill_info(sid)['name'])
        other=ui.public['all_skill_names'][other]['id'] if other else None
        if other is not None and wear_each(other):
            LOG.info('프리셋 2번 대체 · %s 미학습 · %s 사용',ui._skill_info(sid)['name'],ui._skill_info(other)['name'])
            order=[other if s==sid else s for s in order];continue
        missing.append(ui._skill_info(sid)['name'])
    if not missing:
        ui.set_order(order)
    ui.select_preset(1)
    mark(adapter,False)
    context.checkpoint()
    ui.close_known()
    text='프리셋 2번 단일 덱 · 장착 %d칸 · 미완료 %s'%(len(placed),missing or '없음')
    LOG.info(text,extra={'gui_message':text,'state_transition':True})
    return not missing
