"""No-clan memory on fake calls. Not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import logging,shutil,unittest
from types import SimpleNamespace as S
import owner_clan_absent as ca

ROOT=bootstrap.T/'test_scratch/clan-absent'

class Absent(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(ROOT,ignore_errors=True);(ROOT/'settings').mkdir(parents=True)
        self.who=ca._who;ca._who=lambda root:'무이2|짱군네'
        self.ad=S(project=S(root=ROOT));self.calls=[];logging.getLogger('project_gui.DKB').setLevel(logging.INFO)
    def tearDown(self):ca._who=self.who
    def native(self,word):
        def run(adapter,context,inputs,**k):
            self.calls.append(1);logging.getLogger('project_gui.DKB').info('문파 보스 신청 · %s · 화면 정리',word);return False
        return ca.wrap(run)
    def test_no_clan_is_remembered_and_skipped_for_a_day(self):
        run=self.native('문파 없음')
        self.assertTrue(run(self.ad,None,None));self.assertTrue(run(self.ad,None,None))
        self.assertEqual(len(self.calls),1)
        import time
        self.assertFalse(ca.absent(ROOT,now=time.time()+25*3600))
    def test_a_clan_keeps_the_native_result(self):
        run=self.native('신청 완료')
        self.assertFalse(run(self.ad,None,None));self.assertFalse(ca.absent(ROOT))
    def test_another_character_is_not_skipped(self):
        self.native('문파 없음')(self.ad,None,None)
        ca._who=lambda root:'무이2|홍짱군';self.assertFalse(ca.absent(ROOT))

if __name__=='__main__':unittest.main()
