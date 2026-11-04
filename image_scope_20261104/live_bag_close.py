"""User-authorized: close the inventory with the game's own I key, then prove the plain field is back."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
key(0x49);time.sleep(1.5);f=grab();save('bag_closed',f);print('field',field(f),flush=True)
sys.stdout.flush();os._exit(0)
