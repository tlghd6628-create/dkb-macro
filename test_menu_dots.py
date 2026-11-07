"""Full-menu red dots on the saved 1366 menu frame and fake timetable. Not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_growth_signals as gs

MENU=Path(__file__).resolve().parent/'image_scope_20261104/f1/menu_hd.png'   # 짱군네 11-07 08:46, not in the repo

class Tiles(unittest.TestCase):
    @unittest.skipUnless(MENU.exists(),'saved menu frame not on this PC')
    def test_dotted_tiles_on_the_real_menu(self):
        import numpy as np,owner_text
        from PIL import Image
        owner_text.set_root(bootstrap.A)
        a=np.asarray(Image.open(MENU).convert('RGB'));x,y,w,h=gs.MENU_AREA
        tiles=gs.dotted_tiles(a,owner_text.read_area(None,a[y:y+h,x:x+w],left=x,top=y,minimum=.5))
        self.assertTrue({'단봉인해제','도술','기운발현','업적','화첩'}<=tiles,tiles)
        self.assertNotIn('성장',tiles)

class Jobs(unittest.TestCase):
    def test_only_switched_on_jobs_come_forward(self):
        state={'seal_release':{'status':'done'},'growth':{'status':'done'},'album':{'status':'done'}}
        plan=S(state=state,values={},commit=lambda:None)
        with patch('owner_timetable.planner',return_value=plan),patch('owner_timetable.enabled',side_effect=lambda job,values:job.key!='album'):
            moved=gs.bring_jobs(S(),['seal_release','growth','album','growth'])
        self.assertEqual(state['seal_release']['status'],'pending');self.assertEqual(state['growth']['status'],'pending')
        self.assertEqual(state['album']['status'],'done');self.assertEqual(len(moved),2)

if __name__=='__main__':unittest.main()
