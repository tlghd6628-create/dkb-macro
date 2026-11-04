"""Synthetic UI/ledger purchase-path tests only; no game input."""
import sys,unittest,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_skill_ui
from owner_skill_ui import SkillUI
from owner_skill_goal import Pending,catalog
from owner_aoe_preset_candidate import SLOTS

REQUIRED=set(SLOTS)|{65}
ALL_COIN=set(int(k) for k,v in catalog()['skills'].items() if v['style'] in ('파멸','강타')) | REQUIRED
class Ledger:
    def __init__(self,step=5):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.character='character-a'
        self.path=Path(self.tmp.name)/'settings'/'owner-skill-goal.json'
        self.item={'story_step':step};self.events=[]
    def event(self,*a,**kw):self.events.append((a,kw))
class UI:
    purchase_required_and_learn=SkillUI.purchase_required_and_learn
    purchase_and_learn=SkillUI.purchase_and_learn
    configure_both=SkillUI.configure_both
    def __init__(self,owned):
        self.public=catalog();self.owned=set(owned);self.actions=[]
        self.context=type('C',(),{'checkpoint':lambda self:None})()
    def learn_available(self):self.actions.append('learn')
    def scan_owned(self):self.actions.append('scan');return set(self.owned)
    def close_known(self):self.actions.append('close')
    def enter_shop(self,style):self.actions.append(('shop',style));self.style=style
    def shop_rows(self,style):
        return [dict(id=sid,name=v['name'],y=100+sid) for sid,v in ((int(k),v) for k,v in self.public['skills'].items()) if v['style']==style]
    def buy_one(self,ledger,row,**kwargs):self.actions.append(('buy',row['id']));self.owned.add(row['id']);return True
    def learn_one(self,sid,ledger,**kwargs):self.actions.append(('learn_one',sid,kwargs));self.owned.add(sid);return True
    def drag(self,*args):self.actions.append('drag')

class Tests(unittest.TestCase):
    def test_before_story_no_actions(self):
        ui=UI(set())
        with self.assertRaises(Pending):ui.purchase_and_learn(Ledger(4))
        self.assertEqual(ui.actions,[])
    def test_all_owned_no_shopping(self):
        ui=UI(ALL_COIN);ledger=Ledger()
        result=ui.purchase_and_learn(ledger)
        self.assertEqual(result['status'],'partial');self.assertTrue(result['aoe_ready'])
        self.assertIn('파멸·강타',result['unresolved'][-1])
        self.assertFalse(any(isinstance(a,tuple) and a[0]=='buy' for a in ui.actions))
        self.assertEqual(ledger.item['owned_skills'],sorted(ALL_COIN))
    def test_only_missing_desired_approved_styles(self):
        ui=UI(ALL_COIN-{59,25});ledger=Ledger()
        result=ui.purchase_and_learn(ledger)
        self.assertTrue(result['aoe_ready']);self.assertEqual(result['status'],'partial')
        self.assertEqual([x for x in ui.actions if isinstance(x,tuple) and x[0]=='buy'],[('buy',59),('buy',25)])
        self.assertEqual([x for x in ui.actions if isinstance(x,tuple) and x[0]=='shop'],[('shop','파멸'),('shop','강타')])
    def test_missing_external_box_skill_remains_held(self):
        ui=UI(ALL_COIN-{84})
        result=ui.purchase_and_learn(Ledger());self.assertFalse(result['aoe_ready'])
        self.assertFalse(any(isinstance(a,tuple) and a[0]=='buy' for a in ui.actions))
    def test_unverified_gangin_path_blocks(self):
        ui=UI(ALL_COIN-{68})
        result=ui.purchase_and_learn(Ledger());self.assertFalse(result['aoe_ready'])
        self.assertFalse(any(isinstance(a,tuple) and a[0]=='buy' for a in ui.actions))
    def test_legacy_both_presets_never_runs(self):
        ui=UI(REQUIRED)
        with self.assertRaises(Pending):ui.configure_both(Ledger())
        self.assertEqual(ui.actions,[])
    def test_preset_two_selection_is_denied_before_ui_actions(self):
        ui=UI(REQUIRED)
        with self.assertRaises(Pending):SkillUI.select_preset(ui,2)
        self.assertEqual(ui.actions,[])
    def test_tutorial_only_specific_skill_no_bulk_learning(self):
        import numpy as np
        ui=UI(ALL_COIN-{catalog()['all_skill_names']['쇠뇌 사격']['id']})
        ui.open_story=lambda:None;ui.search=lambda x:None;ui.wait=lambda f:None
        ui.click=lambda *a:None;ui.word=lambda *a,**k:None
        ui.rows=lambda *a,**k:[];ui.frame=lambda:np.zeros((479,897,3),dtype=np.uint8)
        ui.context=type('C',(),{'wait':lambda self,x:None})()
        ui._owner_last_rows_pair=None
        with patch.object(owner_skill_ui,'selected_quest_box',return_value=(1,1,2,2)):
            with self.assertRaises(Pending):SkillUI.tutorial_objective(ui,Ledger(1))
        self.assertNotIn('learn',ui.actions)
        self.assertIn(('buy',39),ui.actions)
        self.assertIn(('learn_one',39,{'tutorial':True}),ui.actions)
        self.assertEqual([a for a in ui.actions if isinstance(a,tuple) and a[0]=='buy'],[('buy',39)])
    def test_forbidden_or_missing_icon_never_learns(self):
        ui=UI(ALL_COIN)
        with self.assertRaises(Pending):SkillUI.learn_one(ui,69,Ledger())
        with self.assertRaises(Pending):SkillUI.learn_one(ui,39,Ledger())
        self.assertEqual(ui.actions,[])
    def test_existing_approved_skill_is_not_relearned(self):
        ui=UI(ALL_COIN)
        self.assertTrue(SkillUI.learn_one(ui,68,Ledger()))
        self.assertEqual(ui.actions,['scan'])
    def test_recorded_tutorial_dialog_icon_is_specific(self):
        import numpy as np
        from PIL import Image
        archive=Path(r'C:\Users\홍이\Downloads\FC_프로그램\도깨비의세계\보관\개발이력_20261101_120213\owner\shop_skill_20261101\fixtures')
        first=np.asarray(Image.open(archive/'skill-learn-all-one-window.png').convert('RGB'))[30:509,1:898]
        dialog=np.asarray(Image.open(archive/'skill-learn-confirm-window.png').convert('RGB'))[30:509,1:898]
        self.assertTrue(owner_skill_ui.skill_screen(first))
        self.assertIsNotNone(owner_skill_ui.match(dialog,'learn-confirm',(378,148,150,28),.96))
        self.assertEqual(owner_skill_ui.identify_icon(first,(695,78,40,40)),39)
        self.assertTrue(owner_skill_ui.learn_confirm_for(dialog,39))
        self.assertFalse(owner_skill_ui.learn_confirm_for(dialog,59))
        self.assertFalse(owner_skill_ui.learn_confirm_for(first,39))
        self.assertEqual(owner_skill_ui.visible_crossbow_y(first),102)
        other=np.asarray(Image.open(archive/'skill-life-restored-window.png').convert('RGB'))[30:509,1:898]
        self.assertIsNone(owner_skill_ui.visible_crossbow_y(other))
        # Synthetic independent copies of one screenshot test routing, not
        # real capture freshness or an actual click.
        ui=UI(ALL_COIN);calls=[]
        ui.all_filter=lambda _:None;ui.drag=lambda *a:None
        def skill_rows():
            ui._owner_last_rows_pair=([first.copy(),first.copy()],[time.monotonic(),time.monotonic()],[[],[]])
            return []
        ui.skill_rows=skill_rows
        ui.click=lambda x,y,proof:calls.append(('click',y,proof(first)))
        ui.word=lambda *a,**k:calls.append(('name',a[0],k.get('exact')))
        self.assertEqual(SkillUI.find_skill(ui,39)['id'],39)
        self.assertEqual(calls,[('click',102,True),('name','쇠뇌 사격',True)])

if __name__=='__main__':unittest.main(verbosity=2)
