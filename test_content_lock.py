"""Closed content on a saved 1366 full menu and fake stores. Not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import shutil,time,unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_content_lock as cl

MENU=Path(__file__).resolve().parent/'image_scope_20261104/f1/menu_hd.png'   # 짱군네 11-07 08:46, not in the repo
ROOT=bootstrap.T/'test_scratch/content-lock'

class Tiles(unittest.TestCase):
    @unittest.skipUnless(MENU.exists(),'saved menu frame not on this PC')
    def test_dim_labels_are_closed_on_the_real_menu(self):
        import numpy as np,owner_text
        from PIL import Image
        owner_text.set_root(bootstrap.A)
        a=np.asarray(Image.open(MENU).convert('RGB'));x,y,w,h=cl.MENU_AREA
        found=cl.tiles(a,owner_text.read_area(None,a[y:y+h,x:x+w],left=x,top=y,minimum=.5))
        self.assertIs(found['비경탐험'],False);self.assertIs(found['승천의탑'],False)
        self.assertIs(found['보스토벌'],True);self.assertIs(found['임무'],True)
    def test_jobs_from_tiles(self):
        self.assertEqual(cl.closed_jobs({'비경탐험':False,'승천의탑':True,'보스토벌':True},False),{'daily_dungeon','daily24_dungeon','raid'})
        self.assertEqual(cl.closed_jobs({'비경탐험':True,'승천의탑':True,'보스토벌':True},True),set())
        self.assertEqual(cl.closed_jobs({'보스토벌':False},None),{'raid'})

class Gate(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(ROOT,ignore_errors=True);(ROOT/'settings').mkdir(parents=True)
        self.ad=S(project=S(root=ROOT));self.looks=[]
        self.p=[patch.object(cl,'_who',lambda r:'무이2|짱군네'),patch.object(cl,'_level',lambda a:50),
                patch.object(cl,'look',lambda a,c,i:self.looks.append(1) or {'daily_dungeon','raid'})]
        for one in self.p:one.start()
    def tearDown(self):
        for one in self.p:one.stop()
    def job(self,key):return S(key=key,label=key)
    def test_closed_job_is_passed_over_and_the_menu_read_once(self):
        self.assertTrue(cl.gate(self.ad,self.job('raid'),None,None))
        self.assertTrue(cl.gate(self.ad,self.job('daily_dungeon'),None,None))
        self.assertIsNone(cl.gate(self.ad,self.job('tower'),None,None))
        self.assertEqual(len(self.looks),1)
    def test_other_jobs_never_read_the_menu(self):
        self.assertIsNone(cl.gate(self.ad,self.job('mail'),None,None));self.assertEqual(self.looks,[])
    def test_a_finished_quest_drops_the_record(self):
        cl.gate(self.ad,self.job('raid'),None,None);self.assertTrue(cl.forget(self.ad))
        self.assertIsNone(cl.kept(self.ad));cl.gate(self.ad,self.job('raid'),None,None);self.assertEqual(len(self.looks),2)
    def test_old_record_or_level_up_reads_again(self):
        cl.gate(self.ad,self.job('raid'),None,None)
        self.assertIsNone(cl.kept(self.ad,now=time.time()+7*3600))
        with patch.object(cl,'_level',lambda a:51):self.assertIsNone(cl.kept(self.ad))

if __name__=='__main__':unittest.main()
