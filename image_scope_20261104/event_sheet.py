"""View the saved event-flow frames from the 10:40 TEST at readable size."""
from pathlib import Path
from PIL import Image,ImageDraw
A=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\logs\scene-corpus\20261104')
ds=sorted(p for p in A.iterdir() if p.is_dir() and '20261104T104013'<=p.name<='20261104T104056')
W,H=598,320;cols=3;rows=(len(ds)+cols-1)//cols
sheet=Image.new('RGB',(W*cols,H*rows))
for i,p in enumerate(ds):
    im=Image.open(p/'screen.png').convert('RGB').resize((W,H));ImageDraw.Draw(im).text((3,3),p.name[9:15],fill=(255,255,0))
    sheet.paste(im,(i%cols*W,i//cols*H))
sheet.save(Path(__file__).parent/'event_sheet.png');print(len(ds),sheet.size)
