"""User-authorized: measure the open auto-hunt panel from saved frames, then close it with its X. Changes no value."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
A=C=None
s2=np.array(Image.open(OUT/'cog_scroll2.png').convert('RGB'));o=np.array(Image.open(OUT/'cog_open.png').convert('RGB'))
def m(f,x,y,w=30,h=10):return round(float(f[y-h//2:y+h//2,x-w//2:x+w//2].mean()),1)
print('scrolled fixed off/on',m(s2,710,295),m(s2,822,295),'range off/on',m(s2,800,330),m(s2,851,330),'attack off/on',m(s2,710,412),m(s2,822,412))
print('manner',m(s2,680,240),m(s2,745,240),m(s2,840,240))
assets=Path(__file__).parents[1]/'assets/hunt-range';assets.mkdir(exist_ok=True)
Image.fromarray(s2[46:60,652:714]).save(assets/'panel-title.png')
Image.fromarray(s2[264:278,668:752]).save(assets/'fixed-label.png')
Image.fromarray(s2[322:338,668:726]).save(assets/'range-label.png')
Image.fromarray(s2[350:366,672:692]).save(assets/'five-m.png')
Image.fromarray(np.vstack([s2[46:60,652:714],np.zeros((4,62,3),'uint8')])).save(OUT/'x_title.png')
Image.fromarray(s2[255:375,650:890]).resize((720,360),Image.LANCZOS).save(OUT/'range_zoom.png')
click(883,53);time.sleep(1.2);f=grab();save('cog_closed',f);print('field',field(f),flush=True)
sys.stdout.flush();os._exit(0)
