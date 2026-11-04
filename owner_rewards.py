"""Skip recently completed reward scans; shorten only proved stable buttons."""
from functools import wraps
import importlib,sys,threading,time
LOCAL=threading.local()
INTERVALS={'guide':120.,'event':300.,'mail':180.,'achievement':180.,'album':300.,'currency':300.}


def reward_scope(function,key,clock=time.monotonic):
    @wraps(function)
    def run(*args,**kwargs):
        adapter=args[0] if args else getattr(LOCAL,'adapter',None)
        if adapter is None:
            # TEST and the 3-hour cycle call this directly, past the dispatcher
            # that sets the adapter, and must not hit the recent-scan skip below.
            from owner_reward_flow import tracked,current_adapter
            return tracked(key,function,current_adapter(),args,kwargs)
        cache=getattr(adapter,'_owner_reward_completed',None)
        if cache is None:cache={};adapter._owner_reward_completed=cache
        now=clock()
        if key in cache and now-cache[key]<INTERVALS[key]:
            import logging
            logging.getLogger('project_gui.DKB').info('최근 보상 확인 완료 · %s · 재검사 간격 대기',key)
            return True
        previous=getattr(LOCAL,'reward',None);LOCAL.reward=key
        try:
            from owner_reward_flow import tracked
            result=tracked(key,function,adapter,args,kwargs)
            if result is not False:
                cache[key]=clock()
                if key in ('mail','event'):adapter._owner_inventory_completed=-1e30
            return result
        finally:LOCAL.reward=previous
    run._owner_reward_policy=True
    return run


def stable_button(service,name):
    """Prove the same target twice. The native click rechecks it again."""
    import numpy as np
    before=service.capture();first=service.detector.find(name,before,threshold=.94)
    if first is None:return False
    service.context.wait(.08);service.check()
    after=service.capture();second=service.detector.find(name,after,threshold=.94)
    if second is None or max(abs(int(a)-int(b)) for a,b in zip(first[:2],second[:2]))>1:return False
    x1,y1,x2,y2=first[2]
    if x2<=x1 or y2<=y1:return False
    a=before[y1:y2,x1:x2];b=after[y1:y2,x1:x2]
    return a.shape==b.shape and a.size>0 and float(np.abs(a.astype('int16')-b.astype('int16')).mean())<1.0


def install(gui):
    if getattr(gui,'_owner_rewards',False):return
    from owner_reward_visual_guard import install as install_visual_guard
    install_visual_guard()
    from project_adapter._entry import Adapter
    # Establish the owning adapter also for native keyword-only reward calls.
    if not getattr(Adapter._run_auto_features,'_owner_reward_adapter',False):
        ordinary=Adapter._run_auto_features
        @wraps(ordinary)
        def features(adapter,*args,**kwargs):
            previous=getattr(LOCAL,'adapter',None);LOCAL.adapter=adapter
            try:return ordinary(adapter,*args,**kwargs)
            finally:LOCAL.adapter=previous
        features._owner_reward_adapter=True;Adapter._run_auto_features=features
    targets={
        'guide_rewards':('run_guide_rewards','guide'),
        'event_rewards':('run_event_rewards','event'),
        'mail_rewards':('run_mail_rewards','mail'),
        'achievement_rewards':('run_achievement_rewards','achievement')}
    replacements=[]
    for module,(name,key) in targets.items():
        original=getattr(importlib.import_module('project_adapter.'+module),name)
        if not getattr(original,'_owner_reward_policy',False):replacements.append((original,reward_scope(original,key)))
    # The native dispatcher reads gold and coin after every town return. Nothing
    # here uses the values, and the menus it opens cost about ten seconds.
    original=importlib.import_module('project_adapter.currency_snapshot').run_currency_snapshot
    if not getattr(original,'_owner_reward_policy',False):
        def skip_currency(adapter,context,inputs):return True
        skip_currency._owner_reward_policy=True
        replacements.append((original,skip_currency))
    original=importlib.import_module('project_adapter.achievement_rewards').run_album_rewards
    if not getattr(original,'_owner_reward_policy',False):replacements.append((original,reward_scope(original,'album')))
    for name,module in tuple(sys.modules.items()):
        if name.startswith('project_adapter') and module is not None:
            for key,value in tuple(vars(module).items()):
                replacement=next((b for a,b in replacements if value is a),None)
                if replacement is not None:setattr(module,key,replacement)
    from project_adapter.town_services import TownServices
    if not getattr(TownServices.button,'_owner_stable_button',False):
        ordinary_button=TownServices.button
        @wraps(ordinary_button)
        def button(service,name,*,wait_before_click=.5,required=True):
            if getattr(LOCAL,'reward',None) and wait_before_click==.5 and stable_button(service,name):
                wait_before_click=.12
            return ordinary_button(service,name,wait_before_click=wait_before_click,required=required)
        button._owner_stable_button=True;TownServices.button=button
    gui._owner_rewards=True
