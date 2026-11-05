"""Generic tooltip/current-state tests; no actual input or resources."""
import bootstrap
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import tempfile,unittest,time
import numpy as np
from PIL import Image
import owner_worn_stats as w
import owner_growth_current as g

class Reader(unittest.TestCase):
 def setUp(self):self.frame=np.asarray(Image.open(Path(__file__).parent/'tooltip_followup/weapon.png').convert('RGB'))
 def engine(self,values,scores=None):
  source=iter(zip(values,scores or [.999]*4))
  def read(frame):
   value,score=next(source);return [{'rec_texts':[str(value)],'rec_scores':[score]}]
  return S(predict=read)
 def test_actual_user_tooltip_has_known_four_labels_and_worn_popup(self):
  self.assertTrue(w.popup(self.frame));self.assertEqual(len(w.table(self.frame)),4)
 def test_numeric_values_are_read_not_hardcoded(self):
  for values in ([50,5,3,1],[19,1,0,0],[49,5,2,3]):
   self.assertEqual(w.read(self.frame,self.engine(values)),dict(zip(w.FIELDS,values)))
 def test_unknown_numeric_fields_are_not_zero(self):
  result=w.read(self.frame,self.engine([50,5,'?',1],[.999,.999,.99,.999]))
  self.assertNotIn('breakthrough',result);self.assertEqual(result['enhance'],50)
 def test_low_confidence_and_trailing_garbage_do_not_become_values(self):
  result=w.read(self.frame,self.engine(['50','5','3배',1],[.97,.999,.999,.999]))
  self.assertNotIn('enhance',result);self.assertNotIn('breakthrough',result)
 def test_missing_or_wrong_order_labels_reject_table(self):
  frame=self.frame.copy();frame[295:310,390:418]=0
  self.assertIsNone(w.table(frame))
  self.assertIsNone(w.read(np.zeros_like(frame),self.engine([1,2,3,4])))
 def test_other_names_do_not_change_label_or_number_reading(self):
  frame=self.frame.copy();frame[97:117,380:510]=0
  self.assertEqual(w.read(frame,self.engine([7,0,0,0]))['enhance'],7)

class Persist(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def row(self,character='server/charA',slot='무기',grade='희귀'):
  return {'character':character,'item_identity':'worn-slot:'+slot,'slot':slot,'grade':grade,
   'enhancement':50,'opening':5,'breakthrough':3,'awakening':1,
   'verified_fields':['enhancement','opening','breakthrough','awakening']}
 def test_four_different_stats_and_slot_persist(self):
  self.assertTrue(g.observe(self.root,self.row()))
  self.assertEqual(g.equipped_rows(self.root,'server/charA')[0],('무기','희귀','50','3','1'))
  key=str(self.root.resolve());g._LOADED.discard(key)
  for token in list(g._READINGS):
   if token[0]==key:g._READINGS.pop(token)
  self.assertEqual(g.equipped_rows(self.root,'server/charA')[0],('무기','희귀','50','3','1'))
 def test_characters_and_slots_are_separate(self):
  g.observe(self.root,self.row())
  self.assertEqual(g.equipped_rows(self.root,'server/charB')[0][1],'미확인')
  self.assertEqual(dict((r[0],r) for r in g.equipped_rows(self.root,'server/charA'))['반지'][1],'미확인')
 def test_unverified_fields_not_saved_from_defaults(self):
  row=self.row();row['verified_fields']=['enhancement'];g.observe(self.root,row)
  result=g.equipped_rows(self.root,'server/charA')[0]
  self.assertEqual(result[2],'50');self.assertEqual(result[3:],('미확인','미확인'))
 def test_new_slot_snapshot_does_not_reuse_old_items_unknown_stats(self):
  g.observe(self.root,self.row())
  row=self.row();row.update(enhancement=0,verified_fields=['enhancement'],replace_values=True)
  g.observe(self.root,row);result=g.equipped_rows(self.root,'server/charA')[0]
  self.assertEqual(result[2:5],('0','미확인','미확인'))

if __name__=='__main__':unittest.main()
