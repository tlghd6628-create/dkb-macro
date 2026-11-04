"""The program's own F3, then wait for its stopped line."""
from pathlib import Path
import time,ctypes,sys,os
LOG=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\logs')/(time.strftime('%Y-%m-%d')+'.log')
size=LOG.stat().st_size;user=ctypes.windll.user32
user.keybd_event(0x72,0,0,0);time.sleep(.06);user.keybd_event(0x72,0,2,0)
end=time.time()+40
while time.time()<end:
    with LOG.open('rb') as f:f.seek(size);t=f.read().decode('utf-8','replace')
    if '상태: 정지' in t:print('stopped');break
    time.sleep(.5)
else:print('no stop line');print(t[-300:])
sys.stdout.flush();os._exit(0)
