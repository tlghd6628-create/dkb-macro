"""User-authorized single steps in the open shop: `click X Y NAME [wait]` or `shot NAME`.
Refuses the purchase button and the popup's confirm button, so nothing can be bought here."""
from pathlib import Path
import sys,time,ctypes,os
args=sys.argv[1:]
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
kernel=ctypes.windll.kernel32
fg=win32gui.GetForegroundWindow()
if fg!=H:
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4)
if args[0]=='click':
    x,y=int(args[1]),int(args[2])
    if (730<=x<=795 and 430<=y<=470) or (450<=x<=525 and 290<=y<=315):raise SystemExit('refused: purchase or confirm')
    click(x,y);time.sleep(float(args[4]) if len(args)>4 else 1.2);save(args[3],grab())
elif args[0]=='shot':save(args[1],grab())
elif args[0]=='key':key(int(args[1],16));time.sleep(1.5);save(args[2],grab())
elif args[0]=='drag':
    x,y0,y1=int(args[1]),int(args[2]),int(args[3]);front();sx,sy=win32gui.ClientToScreen(H,(x,y0));user.SetCursorPos(sx,sy);time.sleep(.1);user.mouse_event(2,0,0,0,0)
    steps=12
    for i in range(1,steps+1):
        sx2,sy2=win32gui.ClientToScreen(H,(x,y0+(y1-y0)*i//steps));user.SetCursorPos(sx2,sy2);time.sleep(.03)
    time.sleep(.2);user.mouse_event(4,0,0,0,0);time.sleep(1);save(args[4],grab())
sys.stdout.flush();os._exit(0)
