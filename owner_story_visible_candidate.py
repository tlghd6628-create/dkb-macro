"""Read-only fast-path eligibility for an already visible active quest.

This does not alter the mission scanner or send input. The existing caller
must still invoke Groups.select/activate and preserve its ordinary fallback.
"""
import time

def visible_active(groups,keys):
    from owner_skill_ui import quest_screen
    from owner_story_groups import group_rows,dots,suitable,completed_root,glyph,likeness
    ui=groups.ui;active=groups.book.item.get('active')
    if not active or active not in keys or not groups.book.eligible(active,groups.power):return False
    expected=groups.book.item.get('quests',{}).get(active,{}).get('group_glyph')
    if not expected:return False
    def eligible_frame(frame):
        if not quest_screen(frame):return None
        dialogue=getattr(ui,'execution_dialogue',None)
        if callable(dialogue) and dialogue(frame):return None
        rows=group_rows(frame)
        matches=sorted(((likeness(expected,glyph(frame,r['y'])),r) for r in rows),key=lambda item:item[0],reverse=True)
        if not matches or matches[0][0]<.87:return None
        if len(matches)>1 and matches[0][0]-matches[1][0]<.04:return None
        row=matches[0][1]
        if not 108<=row.get('y',0)<=426:return None
        y=row['y']
        if completed_root(frame,y) or not dots(frame,y) or not suitable(frame,y):return None
        # Avoid changing the semantics of compacting other open roots.
        if any(r['open'] and abs(r['y']-y)>=3 for r in rows):return None
        return y
    ui.context.checkpoint();start=time.monotonic();a=eligible_frame(ui.frame())
    if a is None:return False
    ui.context.wait(.12);ui.context.checkpoint();b=eligible_frame(ui.frame())
    if b is None or abs(a-b)>=3 or time.monotonic()-start>3:return False
    # Require a third current observation; callers still use input guards.
    ui.context.checkpoint();c=eligible_frame(ui.frame())
    return bool(c is not None and abs(b-c)<3 and time.monotonic()-start<=3
                and groups.book.item.get('active')==active and groups.book.eligible(active,groups.power))
