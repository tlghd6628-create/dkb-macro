"""User-authorized: choose an option in a settings combobox with the keyboard. Usage: pick_combo.py TAB_Y X Y DOWN_OR_UP COUNT NAME"""
from pathlib import Path
import sys,time,ctypes,os
import win32gui
from PIL import ImageGrab
user=ctypes.windll.user32;user.SetProcessDPIAware()
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and '세부설정' in win32gui.GetWindowText(h) and win32gui.GetClassName(h)=='TkTopLevel' else None,None)
h=found[0];user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);win32gui.SetForegroundWindow(h);time.sleep(.3)
tab,x,y,way,count,name=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]),sys.argv[4],int(sys.argv[5]),sys.argv[6]
def click(px,py):
    l,t,_,_=win32gui.GetWindowRect(h);user.SetCursorPos(l+px,t+py);time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0);time.sleep(.5)
def key(vk):user.keybd_event(vk,0,0,0);time.sleep(.05);user.keybd_event(vk,0,2,0);time.sleep(.15)
click(78,tab);click(x,y)
for _ in range(count):key(0x28 if way=='down' else 0x26)
key(0x0D);time.sleep(.5)
ImageGrab.grab(win32gui.GetWindowRect(h),all_screens=True).save(Path(__file__).parent/'gui'/(name+'.png'));print('picked');sys.stdout.flush();os._exit(0)
