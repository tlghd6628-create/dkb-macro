"""User-requested: answer the program's own two dialogs. 확인 on the blocked second launch, 예 on stop-and-close.
Then wait for the program's shutdown line. Touches only these two dialogs, never the game."""
from pathlib import Path
import time,win32gui,win32con
LOG=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\logs')/(time.strftime('%Y-%m-%d')+'.log')
start=LOG.stat().st_size
def press(title,button,text):
    tops=[]
    win32gui.EnumWindows(lambda h,_:tops.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='#32770' and win32gui.GetWindowText(h)==title else None,None)
    for h in tops:
        rows=[]
        win32gui.EnumChildWindows(h,lambda c,_:rows.append((c,win32gui.GetWindowText(c))),None)
        if any(text in t for _,t in rows):
            target=[c for c,t in rows if t.startswith(button)]
            if len(target)==1:
                win32gui.PostMessage(target[0],win32con.BM_CLICK,0,0);print('pressed',title,button);return True
    print('not found',title);return False
press('DKB','확인','이미 실행 중');time.sleep(1)
press('종료','예','정지하고 종료')
end=time.time()+60;done=False
while time.time()<end and not done:
    time.sleep(1)
    with LOG.open('rb') as f:f.seek(start);text=f.read().decode('utf-8','replace')
    done='종료' in text and ('shutdown' in text.lower() or '정상 종료' in text or '종료 완료' in text)
    tops=[]
    win32gui.EnumWindows(lambda h,_:tops.append(h) if win32gui.IsWindowVisible(h) and 'DKB · 도깨비' in win32gui.GetWindowText(h) else None,None)
    if not tops:done=True
print('closed',not tops)
print('\n'.join(l[11:110] for l in text.splitlines()[-4:]))
