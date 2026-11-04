"""User-authorized: build the slider assets from saved frames, then close the open panel with its 확인. 5m is already set."""
from pathlib import Path
import sys,time,os,shutil
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
kernel=ctypes.windll.kernel32
C=Path(__file__).parents[1];assets=C/'assets/hunt-range';fix=C/'fixtures_image_scope'
load=lambda n:np.array(Image.open(OUT/(n+'.png')).convert('RGB'))
low,high,opened=load('sl_left'),load('sl_max'),load('cog_open')
Image.fromarray(low[350:366,668:698]).save(assets/'five-m.png');Image.fromarray(high[350:366,668:698]).save(assets/'thirty-m.png')
Image.fromarray(opened[436:462,722:798]).save(assets/'confirm.png')
for src_name,dst in (('cog_before','hunt_field'),('cog_open','hunt_open'),('sl_left','hunt_low'),('sl_max','hunt_high')):
    shutil.copyfile(OUT/(src_name+'.png'),fix/(dst+'.png'))
band=lambda f:int(f[352:364,722:860].mean(axis=(0,2)).argmax())+722
print('handle low',band(low),'high',band(high))
fg=win32gui.GetForegroundWindow()
if fg!=H:
    a=kernel.GetCurrentThreadId();b=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,b,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
    finally:user.AttachThreadInput(a,b,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4)
click(760,448);time.sleep(1.5);f=grab();save('sl_closed',f);print('field',field(f),flush=True)
sys.stdout.flush();os._exit(0)
