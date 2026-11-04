"""Saved-image matching; thresholds were tuned on these same limited cases."""
import sys,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from roi_runtime import RoiDetector
import project_adapter.market_inventory as native
from owner_gear_identity_candidate import IconIdentity

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=bootstrap.A/'logs/scene-corpus/20261101'
        ids=['20261101T162238-a1295f7d','20261101T162240-7afa44af','20261101T162242-cdf1cd68','20261101T162244-75f3203c','20261101T162248-0042c2bf']
        cls.frames=[np.asarray(Image.open(root/i/'screen.png').convert('RGB')).copy() for i in ids]
        cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_EQUIPMENT_NAMES))
    def reader(self):return IconIdentity(native,self.detector)
    def test_five_sample_transitions_unique_target(self):
        for pre,post,index in ((1,2,9),(1,3,9),(2,0,8),(3,0,8),(1,4,1)):
            with self.subTest(pre=pre,post=post,index=index):
                r=self.reader();identity=r(self.frames[pre],index,False)
                self.assertIsNotNone(identity);self.assertEqual(r(self.frames[post],index,True),identity)
    def test_wrong_selected_and_reordered_grid_hold(self):
        r=self.reader();self.assertIsNotNone(r(self.frames[1],9,False))
        self.assertIsNone(r(self.frames[4],9,True))
        changed=self.frames[2].copy();changed[80:100,750:770]=0
        self.assertIsNone(r(changed,9,True))
    def test_small_icon_render_variation_does_not_require_exact_bytes(self):
        pre=self.frames[1].copy();r=self.reader();token=r(pre,9,False)
        rows=native.inspect_growth_equipment(self.detector,pre)
        s=next(row['slot'] for row in rows if row['index']==9)
        changed=pre.copy();x=s['cell_x']+10;y=s['cell_y']+10
        changed[y,x]=np.minimum(changed[y,x].astype(np.int16)+1,255).astype(np.uint8)
        self.assertIsNotNone(token);self.assertEqual(r(changed,9,False),token)
        self.assertEqual(r(self.frames[2],9,True),token)
    def test_duplicate_competitor_cannot_pass(self):
        pre=self.frames[1].copy();rows=native.inspect_growth_equipment(self.detector,pre)
        a=next(r['slot'] for r in rows if r['index']==9);b=next(r['slot'] for r in rows if r['index']==6)
        x,y=a['cell_x']+8,a['cell_y']+8;u,v=b['cell_x']+8,b['cell_y']+8
        pre[v:v+18,u:u+18]=pre[y:y+18,x:x+18]
        post=self.frames[2].copy();post[v:v+18,u:u+18]=pre[v:v+18,u:u+18]
        r=self.reader();self.assertIsNotNone(r(pre,9,False));self.assertIsNone(r(post,9,True))

if __name__=='__main__':unittest.main()
