"""Real OCR on real mission screens. Outside the guarded tests because the OCR engine starts a helper process."""
from pathlib import Path
import sys,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,numpy as np
from types import SimpleNamespace as S
from PIL import Image
import owner_mission_ui as mu
from tools.ocr_support import get_paddle_engine
from owner_progression import resized
F=Path(__file__).resolve().parents[1]/'fixtures_image_scope'
def ui(name):
    frame=np.array(Image.open(F/(name+'.png')).convert('RGB'))
    def rows(box,language='korean',**k):
        out=[]
        for page in get_paddle_engine(bootstrap.A,language=language).predict(resized(frame,box)):
            out+=[{'text':t,'score':s} for t,s in zip(page.get('rec_texts',()),page.get('rec_scores',()))]
        return out
    return S(frame=lambda:frame,context=S(wait=lambda s:None),rows=rows)
for name,want in (('mission_used',(0,0)),('mission_fresh',(5,5))):
    u=ui(name);got=(mu.remaining_on_screen(u),mu.instant_left(u));print(name,got,'OK' if got==want else 'WRONG, want %s'%(want,))
sys.stdout.flush();os._exit(0)
