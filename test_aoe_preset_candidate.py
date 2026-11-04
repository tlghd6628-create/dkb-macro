"""Fake UI and saved frames only; never sends game input."""
import copy, json, unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_aoe_preset_candidate import configure_aoe,Hold,SLOTS,ORDER
HERE=Path(__file__).resolve().parent

class FakeUI:
    def __init__(self):self.actions=[];self.current=[None]*8;self.extra=set(range(8));self.bad=False
    def select_preset(self,n):self.actions.append(('select',n))
    def unlocked(self):return self.extra
    def equip(self,sid,index):self.actions.append(('equip',sid,index));self.current[index]=sid
    def set_order(self,order):self.actions.append(('order',tuple(order)))
    def current_slots(self,unlocked):return ([None]*8 if self.bad else self.current)
class FakeLedger:
    def __init__(self):self.records=[]
    def preset_receipt(self,*args,**kwargs):self.records.append((args,kwargs))

class AOE(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((HERE/'skill_assets_candidate/skill_catalog_candidate.json').read_text(encoding='utf-8'))
        self.ui=FakeUI();self.ledger=FakeLedger()
        self.proof={'character':'A','source':'game-screen','skill_id':59,'name':'연쇄 번개',
                    'frames':[{'id':'one','captured_monotonic':9.,'name_verified':True,'icon_verified':True},
                              {'id':'two','captured_monotonic':9.5,'name_verified':True,'icon_verified':True}]}
    def run_config(self,**kwargs):
        options={'character':'A','owned_verified':set(SLOTS),'read_icon_evidence':lambda:self.proof,
                 'backend_verified':True,'clock':lambda:10.0};options.update(kwargs)
        return configure_aoe(self.ui,self.ledger,self.data,**options)
    def enable_fake_proof(self):self.data['candidate_notes']['icon_59_game_match_verified']=True

    def test_real_candidate_is_held_without_ui_input(self):
        with self.assertRaises(Hold):self.run_config()
        self.assertEqual(self.ui.actions,[]);self.assertEqual(self.ledger.records,[])

    def test_synthetic_verified_configuration_only_touches_one(self):
        self.enable_fake_proof();self.assertTrue(self.run_config())
        self.assertEqual(self.ui.actions[0],('select',1))
        self.assertFalse(any(a[0]=='select' and a[1]==2 for a in self.ui.actions))
        self.assertEqual([x[1] for x in self.ui.actions if x[0]=='equip'],list(SLOTS))
        self.assertIn(('order',ORDER),self.ui.actions)
        self.assertEqual(self.ledger.records[0][0],('aoe',list(SLOTS),list(ORDER)))

    def test_locked_slots_hold_before_equipment(self):
        self.enable_fake_proof();self.ui.extra=set(range(7))
        with self.assertRaises(Hold):self.run_config()
        self.assertEqual(self.ui.actions,[('select',1)]);self.assertEqual(self.ledger.records,[])

    def test_stale_mismatch_duplicate_or_missing_owned_never_click(self):
        self.enable_fake_proof()
        tests=[{'clock':lambda:20.0},{'character':'B'},{'backend_verified':False},
               {'owned_verified':set(SLOTS)-{59}},{'read_icon_evidence':lambda:dict(self.proof,frames=[self.proof['frames'][0]]*2)}]
        for opts in tests:
            with self.subTest(opts=opts):
                with self.assertRaises(Hold):self.run_config(**opts)
        self.assertEqual(self.ui.actions,[])

    def test_failure_or_stop_never_writes_success(self):
        self.enable_fake_proof();self.ui.bad=True
        with self.assertRaises(Hold):self.run_config()
        self.assertEqual(self.ledger.records,[])
        self.ui=FakeUI();count=[0]
        def stop():
            count[0]+=1
            if count[0]==4:raise InterruptedError('stop')
        with self.assertRaises(InterruptedError):self.run_config(checkpoint=stop)
        self.assertEqual(self.ledger.records,[])

    def test_known_real_life_icon_is_not_lightning_evidence(self):
        import cv2,numpy as np
        from PIL import Image
        archive=Path(r'C:\Users\홍이\Downloads\FC_프로그램\도깨비의세계\보관\개발이력_20261101_120213\owner\shop_skill_20261101\fixtures')
        f=np.asarray(Image.open(archive/'skill-life-restored-window.png').convert('RGB').crop((1,30,898,509)))
        patch=f[76:121,694:735]
        def best(sid):
            image=np.asarray(Image.open(HERE/'skill_assets_candidate/icons'/f'{sid}.webp').convert('RGB'))
            scores=[]
            for width in (30,32,34):
                small=cv2.resize(image,(width,width),interpolation=cv2.INTER_AREA);m=width//5
                scores.append(float(cv2.minMaxLoc(cv2.matchTemplate(patch,small[m:-m,m:-m],cv2.TM_CCOEFF_NORMED))[1]))
            return max(scores)
        self.assertGreaterEqual(best(84),.90);self.assertLess(best(59),.90)

if __name__=='__main__':unittest.main()
