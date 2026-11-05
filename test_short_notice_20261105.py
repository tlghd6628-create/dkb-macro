"""The short-of-coins message ends a growth press cleanly. Saved frames and fake input; never a game test."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys,tempfile,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
from PIL import Image
import owner_hd as hd
import owner_short_notice as notice
import owner_text
from owner_gear_decision_candidate import Observation
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_step_guard_candidate import Guard

FIXTURES=Path(__file__).resolve().parent/'image_scope_20261104'/'live_fixtures'


def frame_of(path):
 big=np.asarray(Image.open(path).convert('RGB'))[...,::-1].copy()
 frame=np.zeros((479,897,3),np.uint8).view(hd.HdFrame);frame.hi=big;frame.layout=hd._PLAIN
 return frame


class Reading(unittest.TestCase):
 def test_no_real_pixels_says_no(self):
  self.assertFalse(notice.shown(np.zeros((479,897,3),np.uint8)))
 def test_rows_decide(self):
  frame=SimpleNamespace(hi=np.zeros((768,1366,3),np.uint8))
  with patch.object(owner_text,'read',return_value=[dict(text='재화가 부족합니다.')]):self.assertTrue(notice.shown(frame))
  with patch.object(owner_text,'read',return_value=[dict(text='흑암 단도')]):self.assertFalse(notice.shown(frame))
 def test_a_reader_that_fails_leaves_the_older_checks(self):
  frame=SimpleNamespace(hi=np.zeros((768,1366,3),np.uint8))
  with patch.object(owner_text,'read',side_effect=RuntimeError):self.assertFalse(notice.shown(frame))
 def test_real_screens(self):
  owner_text.set_root(bootstrap.A)
  names=[('coins_short_blessing.png',True),('coins_short_gear_enhance.png',True),('coins_short_gear_awaken.png',True),('coins_short_toast.png',True),('coins_short_shop_popup.png',False)]
  seen=[(n,want) for n,want in names if (FIXTURES/n).exists()]
  if not seen:self.skipTest('screen photos are kept out of the repository')
  for name,want in seen:
   with self.subTest(name):self.assertEqual(notice.shown(frame_of(FIXTURES/name)),want)


def observation(level=3,sequence=1):
 return Observation(sequence,time.monotonic(),'c','i','s','일반',level,None,None,None,True,None)


class Reconcile(unittest.TestCase):
 def setUp(self):
  self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
  self.store=IntentStore(Path(self.dir.name)/'intent.json')
  self.store.begin({'kind':'enhance','before':observation(),'second':observation(sequence=2),'cost':None,'balance':None,'item_icon':None})
  self.store.mark_sent()
  self.reads=[]
 def guard(self):
  return Guard(SimpleNamespace(checkpoint=lambda:None),self.store,lambda:self.reads.append(1) or {'screen_proof':False})
 def test_message_closes_the_record_without_reading_values(self):
  self.assertEqual(self.guard().reconcile(short_notice=lambda:True),'short_of_coins')
  self.assertIsNone(self.store.pending());self.assertEqual(self.reads,[])
 def test_no_message_keeps_the_old_answer_and_the_record(self):
  self.assertEqual(self.guard().reconcile(short_notice=lambda:False),'hold_result_unknown')
  self.assertIsNotNone(self.store.pending())
 def test_without_a_reader_nothing_changes(self):
  self.assertEqual(self.guard().reconcile(),'hold_result_unknown')
  self.assertIsNotNone(self.store.pending())


class Skills(unittest.TestCase):
 def test_upgrade_ends_and_leaves_no_pending(self):
  from owner_skill_upgrade_candidate import SkillUpgrade,has_pending
  ledger=SimpleNamespace(item={},event=lambda *a,**k:None)
  class Port:
   ui=SimpleNamespace(context=SimpleNamespace(checkpoint=lambda:None,wait=lambda s:None),frame=lambda:None)
   def observe(self,name,kind,need_quote=False):
    out=dict(name=name,kind=kind,current=1)
    if need_quote:out.update(next=2,have=5,need=1,price=100)
    return out
   def commit(self,quote,prepare):prepare()
  with patch('owner_short_notice.shown',return_value=True):
   result=SkillUpgrade(Port(),ledger,lambda:True).run('강타','awaken',3)
  self.assertEqual(result['status'],'short_of_coins');self.assertFalse(has_pending(ledger))
 def test_style_loop_stops_at_the_first_short(self):
  import owner_skill_growth_candidate as g
  document={'grades':{},'skills':{'강타':{'enabled':True,'enhance':9},'연타':{'enabled':True,'enhance':9}},'individual':{}}
  ledger=SimpleNamespace(item={},event=lambda *a,**k:None);asked=[]
  def run(self,name,target,**k):
   asked.append(name);return {'status':'short_of_coins','style':name,'level':1}
  with patch.object(g.StyleGrowth,'run',run),patch.object(g.StyleGrowth,'_guard',lambda self:True),patch('owner_gear_settings_candidate.validate',lambda d:None):
   statuses=g.run_configured(SimpleNamespace(context=None),ledger,document,lambda:True,include_individual=False)
  self.assertEqual(asked,['강타']);self.assertEqual(statuses[0]['status'],'short_of_coins')


if __name__=='__main__':unittest.main()
