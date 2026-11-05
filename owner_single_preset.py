"""Fill preset 2 with the catalog's single-target deck, then go back to preset 1.

Uses the existing guarded SkillUI steps. A skill not learned yet is reported, never bought here.
A stop in between leaves the game on preset 2, so a file says so until the next run has gone back.
"""
import logging
from pathlib import Path
LOG=logging.getLogger('project_gui.DKB')

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
    ui=SkillUI(adapter,context,inputs)
    # Stopped halfway, the game stays on this half-built deck: real power fell 151,740 to 123,852.
    mark(adapter,True)
    row=ui.public['presets']['single']
    slots=[s['id'] for s in row['slots']]
    order=[s['id'] for s in row['order']]
    order.insert(row['ultimate_at'],row['ultimate']['id'])
    ui.select_preset(2)
    context.checkpoint()
    unlocked=ui.unlocked();placed=[];missing=[]
    for index,sid in enumerate(slots):
        context.checkpoint()
        if index not in unlocked:missing.append(('잠긴 칸',index));continue
        # The left panel slides when a slot or row is picked, so an early pair of reads disagrees.
        for attempt in range(4):
            try:ui.equip(sid,index);placed.append(sid);break
            except Pending as exc:
                if attempt==3:missing.append((sid,str(exc)[:40]))
                context.wait(.8)
    if not missing:
        ui.set_order(order)
    ui.select_preset(1)
    mark(adapter,False)
    context.checkpoint()
    ui.close_known()
    text='프리셋 2번 단일 덱 · 장착 %d칸 · 미완료 %s'%(len(placed),missing or '없음')
    LOG.info(text,extra={'gui_message':text,'state_transition':True})
    return not missing
