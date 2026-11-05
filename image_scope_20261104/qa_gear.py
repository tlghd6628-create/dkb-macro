"""Self-QA for a test character: put a slot in a known state, so the program's own recovery can be checked.
Usage: qa_gear.py NAME unequip SLOT... | NAME look
Program must be stopped: while it runs, it passes only its own input. Skips any scene first. Never equips."""
from pathlib import Path
import ctypes,json,os,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
user=ctypes.windll.user32;user.SetProcessDPIAware()
import win32gui
from PIL import Image
from project_adapter import protected_assets
from project_adapter.main_quest import StateROIs
from project_adapter import market_inventory as native
from project_adapter.secret_exploration import AUTO_NAMES
from roi_runtime import RoiDetector
import runtime_capture
import owner_startup_stage as st
import owner_progression as op
from owner_worn_stats import popup
from owner_equipment_boxes import SLOTS,inspect
from owner_special_contexts import NAMES
OUT=Path(__file__).parent/'f1'
target=json.loads(protected_assets.read_text(bootstrap.A/'profiles/DKB/config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' else None,None)
h=found[0]
def cap():return runtime_capture.capture(h,target)
def front():
    user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);win32gui.SetForegroundWindow(h);time.sleep(.3)
def key(vk):
    user.keybd_event(vk,0,0,0);time.sleep(.06);user.keybd_event(vk,0,2,0)
def click(x,y):
    ox,oy=win32gui.ClientToScreen(h,(0,0));user.SetCursorPos(ox+x,oy+y);time.sleep(.1)
    user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0)
slots=StateROIs(bootstrap.A/'profiles/DKB',mode='main_quest')
det=RoiDetector(bootstrap.A/'profiles/DKB',list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES,*native.INVENTORY_USE_NAMES])))
def to_field(limit=90):
    end=time.time()+limit
    while time.time()<end:
        f=cap()
        if op.inventory_parts(f)==(True,True) or st.scene(det,f)=='field':return True
        k=st.known_dialog(slots,f,f)
        if k=='skip':key(0x1b);time.sleep(.8)
        elif k:
            hit=slots.match(k,f).get('hit');click(hit[0],hit[1]);time.sleep(1.2)
        else:time.sleep(1)
    return False
front()
name=sys.argv[1];action=sys.argv[2]
print('field',to_field())
if op.inventory_parts(cap())!=(True,True):
    key(0x49);time.sleep(1.4)
f=cap();print('before',inspect(f));Image.fromarray(f).save(OUT/(name+'_before.png'))
if action=='unequip':
    for part in sys.argv[3:]:
        x,y,w,ht=SLOTS[part];click(x+w//2,y+ht//2);time.sleep(.8)
        f=cap()
        if not popup(f):print(part,'no worn detail');Image.fromarray(f).save(OUT/(name+'_'+part+'.png'));continue
        click(484,363);time.sleep(1.2)
        f=cap()
        if popup(f):click(510,106);time.sleep(.6)
        print(part,'unequip sent')
f=cap();print('after',inspect(f));Image.fromarray(f).save(OUT/(name+'_after.png'))
key(0x49);time.sleep(.8)
sys.stdout.flush();os._exit(0)
