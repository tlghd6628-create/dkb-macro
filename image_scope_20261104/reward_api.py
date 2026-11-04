"""Read-only: public shape of the native reward modules."""
from pathlib import Path
import sys,inspect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import project_adapter.event_rewards as ev,project_adapter.mail_rewards as ml,project_adapter.guide_rewards as gd,project_adapter.achievement_rewards as ac
for mod in (ev,ml,gd):
    print('==',mod.__name__)
    for k,v in vars(mod).items():
        if k.startswith('__'):continue
        if inspect.isclass(v):
            print(' class',k,getattr(v,'__module__',''),[ (n,str(inspect.signature(f))) for n,f in vars(v).items() if callable(f) and not n.startswith('__')] if v.__module__==mod.__name__ else '')
        elif callable(v):
            try:print(' fn',k,inspect.signature(v))
            except Exception:print(' fn',k)
        elif isinstance(v,(str,int,float,tuple,list,dict)):print(' val',k,v)
import os;sys.stdout.flush();os._exit(0)
