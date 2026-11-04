"""Inclusive timings for reward routines; all waits/clicks retain semantics."""
from collections import Counter
from functools import wraps
import importlib
import json
import logging
from pathlib import Path
import sys
import threading
import time

LOCAL=threading.local()
WRITE_LOCK=threading.Lock()


def active():return getattr(LOCAL,'stack',())


def snapshot(stats,event):
    return {'time':time.time(),'stage':stats['stage'],'event':event,
            'elapsed_ms':round((time.perf_counter()-stats['start'])*1000,3),
            'capture_calls':stats['capture_calls'],'capture_ms':round(stats['capture_seconds']*1000,3),
            'wait_calls':sum(stats['waits'].values()),'requested_wait_seconds':dict(stats['waits']),
            'wait_ms':round(stats['wait_seconds']*1000,3),'milestones':stats['milestones'][-15:],
            'inclusive_nested_timings':True,'behavior_changed':False}


def write(stats,event):
    path=stats['path']
    try:
        body=json.dumps(snapshot(stats,event),ensure_ascii=False)+'\n'
        with WRITE_LOCK:
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists() and path.stat().st_size>2_000_000:path.replace(path.with_name('reward-performance.previous.jsonl'))
            with path.open('a',encoding='utf-8') as stream:stream.write(body)
        stats['last_write']=time.monotonic()
    except OSError:pass


def metric(kind,elapsed,requested=None):
    for stats in active():
        if kind=='capture':stats['capture_calls']+=1;stats['capture_seconds']+=elapsed
        else:
            stats['wait_seconds']+=elapsed;stats['waits'][str(round(float(requested),4))]+=1
        if time.monotonic()-stats['last_write']>=5:write(stats,'progress')


def capture_timer(capture):
    if getattr(capture,'_owner_performance',False):return capture
    @wraps(capture)
    def call(*args,**kwargs):
        started=time.perf_counter()
        try:return capture(*args,**kwargs)
        finally:metric('capture',time.perf_counter()-started)
    call._owner_performance=True
    return call


def wrap(function,stage,path):
    @wraps(function)
    def call(*args,**kwargs):
        stats={'stage':stage,'path':Path(path),'start':time.perf_counter(),'last_write':0,
               'capture_calls':0,'capture_seconds':0.,'wait_seconds':0.,'waits':Counter(),'milestones':[]}
        if not hasattr(LOCAL,'stack'):LOCAL.stack=[]
        LOCAL.stack.append(stats);write(stats,'begin')
        if callable(kwargs.get('capture')):kwargs=dict(kwargs,capture=capture_timer(kwargs['capture']))
        try:return function(*args,**kwargs)
        finally:
            write(stats,'end');LOCAL.stack.pop()
    call._owner_performance=True
    return call


class Milestones(logging.Handler):
    def emit(self,record):
        if not active():return
        try:
            message=record.getMessage()
            if any(word in message for word in ('이벤트','화첩','업적','우편','길라잡이')):
                from owner_incidents import safe
                for stats in active():
                    stats['milestones'].append({'elapsed_ms':round((time.perf_counter()-stats['start'])*1000,3),'message':safe(message,300)})
                    stats['milestones']=stats['milestones'][-25:]
        except Exception:pass


def install(gui):
    if getattr(gui,'_owner_performance',False):return
    from biol_base.session import Context
    if not getattr(Context.wait,'_owner_performance',False):
        ordinary_wait=Context.wait
        @wraps(ordinary_wait)
        def wait(self,seconds,*args,**kwargs):
            if not active():return ordinary_wait(self,seconds,*args,**kwargs)
            started=time.perf_counter()
            try:return ordinary_wait(self,seconds,*args,**kwargs)
            finally:metric('wait',time.perf_counter()-started,seconds)
        wait._owner_performance=True;Context.wait=wait
    targets={
        'guide_rewards':('run_guide_rewards',),
        'event_rewards':('run_event_rewards',),
        'event_periodic_rewards':('run_periodic_rewards',),
        'achievement_rewards':('run_achievement_rewards','run_album_rewards','run_blessing_rewards'),
        'mail_rewards':('run_mail_rewards',)}
    replacements=[]
    for name,functions in targets.items():
        module=importlib.import_module('project_adapter.'+name)
        for name in functions:
            original=getattr(module,name,None)
            if callable(original) and not getattr(original,'_owner_performance',False):
                replacements.append((original,wrap(original,module.__name__+'.'+name,gui.project.root/'logs/reward-performance.jsonl')))
    # Cython callers retain ordinary imported module globals; replace aliases
    # by object identity as well, without rewriting native machine code.
    for name,module in tuple(sys.modules.items()):
        if name.startswith('project_adapter') and module is not None:
            for key,value in tuple(vars(module).items()):
                replacement=next((wrapped for original,wrapped in replacements if value is original),None)
                if replacement is not None:setattr(module,key,replacement)
    handler=Milestones();gui.logger.addHandler(handler)
    gui.root.bind('<Destroy>',lambda event:gui.logger.removeHandler(handler) if event.widget is gui.root else None,add='+')
    gui._owner_performance=True
