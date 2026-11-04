"""Fill preset 2 with the catalog's single-target deck, then go back to preset 1.

Uses the existing guarded SkillUI steps. A skill not learned yet is reported, never bought here.
"""
import logging
LOG=logging.getLogger('project_gui.DKB')

def configure(adapter,context,inputs):
    from owner_skill_ui import SkillUI
    from owner_skill_goal import Pending
    ui=SkillUI(adapter,context,inputs)
    # Stopped halfway, the game stays on this half-built deck: real power fell 151,740 to 123,852.
    adapter._owner_preset_two_open=True
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
    adapter._owner_preset_two_open=False
    context.checkpoint()
    ui.close_known()
    text='프리셋 2번 단일 덱 · 장착 %d칸 · 미완료 %s'%(len(placed),missing or '없음')
    LOG.info(text,extra={'gui_message':text,'state_transition':True})
    return not missing
