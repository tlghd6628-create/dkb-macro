"""Read-only: save one frame of the game window. Sends no input."""
from pathlib import Path
import sys,json,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import win32gui
from PIL import Image
from project_adapter import protected_assets
import runtime_capture
import owner_window_scale
owner_window_scale.install()
OUT=Path(__file__).parent/'f1';OUT.mkdir(exist_ok=True)
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' and win32gui.GetWindowText(h).startswith('도깨비의세계') else None,None)
if len(found)!=1:raise SystemExit('window count')
frame=runtime_capture.capture(found[0],target)
name=sys.argv[1] if len(sys.argv)>1 else 'now'
Image.fromarray(frame).save(OUT/(name+'.png'));print(OUT/(name+'.png'),frame.shape);sys.stdout.flush();os._exit(0)
