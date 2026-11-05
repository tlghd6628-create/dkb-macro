"""The 요령서 and 도술 choice boxes are found on the real frame, wherever the tile sits, and nothing else answers."""
import os,sys
from pathlib import Path
here=Path(__file__).resolve().parent
root=Path(os.environ['DKB_ROOT']);a=root/'vendor/DKB_Auto';b=root/'vendor/BIOL_Project_Base/1.1.0';rt=root/'vendor/BIOL_Runtime/1.1.0'
sys.dont_write_bytecode=True
sys.path[:0]=[str(here),str(a),str(b/'tools'),str(b),str(rt/'code')]
os.environ.update(MDT_SHARED_APP_ROOT=str(a),MDT_RUNTIME_PRODUCT='DKB',MDT_SHARED_RUNTIME_HOME=str(rt.parent),MDT_SHARED_BIOL_DLL=str(rt/'native/BIOL_OCR.dll'))
os.chdir(a)
import numpy as np
from PIL import Image
import owner_hd,owner_skill_box as box
owner_hd.install_reading()

base=np.full((768,1366,3),40,np.uint8)
assert box.box_cell(owner_hd.make_frame(base),'manual-box') is None
for asset,(rx,ry) in (('manual-box',(1136,154)),('manual-box',(1254,686)),('choice-box',(1195,391))):
    real=base.copy();cut=box.reference(asset+'-real');h,w=cut.shape[:2]
    real[ry:ry+h,rx:rx+w]=cut
    frame=owner_hd.make_frame(real)
    x,y=box.box_cell(frame,asset)
    # Whichever anchor this frame's map gives, a click on the answer lands back on the tile.
    back=owner_hd.to_real_point(x,y)
    assert abs(back[0]-(rx+w//2))<=2 and abs(back[1]-(ry+h//2))<=2,(asset,x,y,back)
    other='choice-box' if asset=='manual-box' else 'manual-box'
    assert box.box_cell(frame,other) is None,other

saved=Path(r'C:\Users\user\dkb-macro\image_scope_20261104\hd_frames\pc2_bag_consumables_hd.png')
if saved.exists():
    frame=owner_hd.make_frame(np.asarray(Image.open(saved).convert('RGB')))
    assert box.box_cell(frame,'manual-box')==(766,106),box.box_cell(frame,'manual-box')
    assert box.box_cell(frame,'choice-box')==(803,106),box.box_cell(frame,'choice-box')
print('ok')
