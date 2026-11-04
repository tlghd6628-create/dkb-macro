"""Contact sheet of post-update saved frames, for viewing only."""
from pathlib import Path
import os
import numpy as np,sys
from PIL import Image,ImageDraw
A=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')/'vendor/DKB_Auto/logs/scene-corpus/20261104'
ds=sorted(p for p in A.iterdir() if p.is_dir() and p.name>='20261104T1000' and (p/'screen.png').exists())
W,H=299,160;cols=5;rows=(len(ds)+cols-1)//cols
sheet=Image.new('RGB',(W*cols,H*rows))
for i,p in enumerate(ds):
    im=Image.open(p/'screen.png').convert('RGB').resize((W,H));ImageDraw.Draw(im).text((3,3),p.name[9:15],fill=(255,255,0))
    sheet.paste(im,(i%cols*W,i//cols*H))
sheet.save(Path(__file__).parent/'post_contact.png');print(len(ds))
