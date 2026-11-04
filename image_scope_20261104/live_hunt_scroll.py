"""User-authorized: on the open auto-hunt panel, wheel down only, saving each state. Changes no value."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
front();sx,sy=win32gui.ClientToScreen(H,(760,260));user.SetCursorPos(sx,sy);time.sleep(.2)
for n in range(1,3):
    for _ in range(6):user.mouse_event(0x800,0,0,-120,0);time.sleep(.08)
    time.sleep(.6);save('cog_scroll%d'%n,grab())
sys.stdout.flush();os._exit(0)
