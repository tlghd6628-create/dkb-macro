"""Contact sheet of pre-update frames whose scene() reading changed, for review by eye."""
from pathlib import Path
import json
from PIL import Image,ImageDraw
D=Path(__file__).parent
A=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\logs\scene-corpus')
data=json.loads((D/'scene_slots.json').read_text(encoding='utf-8'))['changed']
rows=[('F>U',n) for n in data['pre|field|unknown']]+[('U>F',n) for n in data['pre|unknown|field']]
W,H=299,160;cols=5;n=(len(rows)+cols-1)//cols;sheet=Image.new('RGB',(W*cols,H*n))
for i,(tag,name) in enumerate(rows):
    im=Image.open(A/name[:8]/name/'screen.png').convert('RGB').resize((W,H));ImageDraw.Draw(im).text((3,3),tag+' '+name[4:15],fill=(255,255,0))
    sheet.paste(im,(i%cols*W,i//cols*H))
sheet.save(D/'changed_pre.png');print(len(rows))
