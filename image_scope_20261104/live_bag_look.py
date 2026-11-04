"""User-authorized: open the inventory with the game's own I key, save the gear page, close again.
Only navigation. Equips, uses and spends nothing."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
save('bag_before',grab())
key(0x49);time.sleep(1.5);save('bag_open',grab())
print('saved',flush=True);sys.stdout.flush();os._exit(0)
