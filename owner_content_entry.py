"""Use the native dispatcher without its unnecessary initial town trip.

Only the first preparatory action is omitted. The native feature, policy,
same Session worker, death/recovery returns and later actions remain intact.
"""
import logging,threading

LOG=logging.getLogger('project_gui.DKB')
SETTINGS=frozenset((
    'auto_schedule.daily_quest.enabled','auto_schedule.weekly_quest.enabled',
    'auto_challenge.ascension_tower.enabled','auto_schedule.field_boss.enabled',
    'auto_schedule.falling_battle.enabled','auto_schedule.folktale.enabled',
    'auto_schedule.artifact_charm.enabled','auto_schedule.boss_raid.enabled',
    'auto_challenge.treasure_hunt.enabled',
    'auto_challenge.secret_exploration.enabled','auto_challenge.secret_exploration_always.enabled',
    'auto_challenge.secret_folktale_5h.enabled','auto_challenge.secret_folktale.enabled',
    'auto_growth.spirit_training.enabled',
))

def invoke(native,adapter,context,inputs,*,setting,**kwargs):
    """Skip exactly the native initial common.run_town_return action.

    This is not a replacement town-return method: after the first action,
    even a subsequent town return uses the original action policy unchanged.
    Unknown call order is not guessed. Other callers keep the original flow.
    """
    if setting not in SETTINGS:return native(adapter,context,inputs,**kwargs)
    original=context.run_action
    had='run_action' in vars(context);owner=threading.get_ident();first=True
    def action(key,operation,*args,**options):
        nonlocal first
        if threading.get_ident()==owner and first:
            first=False
            if key=='common.run_town_return':
                context.checkpoint()
                text='콘텐츠 입장 준비 · 마을귀환 생략 · 현재 위치에서 기존 입장 절차 진행'
                LOG.info(text,extra={'gui_message':text,'state_transition':True})
                return True
        return original(key,operation,*args,**options)
    context.run_action=action
    try:return native(adapter,context,inputs,**kwargs)
    finally:
        if had:context.run_action=original
        else:del context.run_action

def prepare_test_window(gui):
    """Same explicit-request window preparation as F1, without starting play."""
    gui.preparation_gate()
    gui.game_window.require_ready()

