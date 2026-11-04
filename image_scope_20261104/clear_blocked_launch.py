"""Dismiss the program's own "already running" notices left by blocked launches. Refuses any other dialog."""
import time,win32gui,win32con
def notices():
    tops=[]
    def each(h,_):
        if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='#32770' and win32gui.GetWindowText(h)=='DKB':
            rows=[]
            win32gui.EnumChildWindows(h,lambda c,_:rows.append(win32gui.GetWindowText(c)),None)
            if any('이미 실행 중' in t for t in rows):tops.append(h)
    win32gui.EnumWindows(each,None);return tops
for _ in range(5):
    rows=notices()
    if not rows:break
    for h in rows:win32gui.PostMessage(h,win32con.WM_COMMAND,win32con.IDOK,0)
    time.sleep(2)
print('left',len(notices()))
