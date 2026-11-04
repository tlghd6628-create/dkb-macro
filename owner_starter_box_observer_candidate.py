"""Read-only discovery of a *possible* native material-box icon.

No returned value authorizes opening, choosing or consuming anything. The
native image does not prove the selected item name or the contents of a box.
"""
from pathlib import Path
from functools import lru_cache

ICON='버튼_인벤토리_발현재료상자'
REGION='범위_인벤토리'

@lru_cache(maxsize=2)
def detector(profile):
 from roi_runtime import RoiDetector
 return RoiDetector(Path(profile),[ICON,REGION])

def observe(profile,first,second):
 """Find a stable icon in two already captured inventory frames; no inputs."""
 from owner_progression import inventory_parts
 import numpy as np
 if not isinstance(first,np.ndarray) or not isinstance(second,np.ndarray):return None
 if first is second or np.shares_memory(first,second):return None
 if first.shape!=(479,897,3) or second.shape!=(479,897,3):return None
 if inventory_parts(first)!=(True,True) or inventory_parts(second)!=(True,True):return None
 d=detector(str(profile))
 a=d.find(ICON,first,region=REGION,threshold=.97)
 b=d.find(ICON,second,region=REGION,threshold=.97)
 if not a or not b or a[2]!=b[2]:return None
 return {'status':'possible_material_box','bounds':tuple(b[2]),'action_authorized':False}
