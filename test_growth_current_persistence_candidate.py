"""Display-only persisted last observations; no game action authorizations."""
import unittest,tempfile,json,importlib.util
from pathlib import Path
import bootstrap
import owner_growth_current as subject


class Tests(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  subject._LOADED.discard(str(self.root.resolve()))
 def test_partial_skill_fields_merge_instead_of_erasing(self):
  self.assertTrue(subject.observe_value(self.root,'p1','skills','파멸',{'enhance':49},verified=True))
  self.assertTrue(subject.observe_value(self.root,'p1','skills','파멸',{'breakthrough':2},verified=True))
  self.assertEqual(subject.current_value(self.root,'p1','skills','파멸','enhance'),'49')
  self.assertEqual(subject.current_value(self.root,'p1','skills','파멸','breakthrough'),'2')
 def test_display_does_not_expire_between_twenty_minute_visits(self):
  subject.observe_value(self.root,'p1','energies','생명',{'stage':3},verified=True)
  self.assertEqual(subject.current_value(self.root,'p1','energies','생명','stage',now=10**10),'3')
  self.assertIsNotNone(subject.last_observed_at(self.root,'p1'))
 def test_new_module_instance_recovers_values_and_exact_scope(self):
  subject.observe_value(self.root,'p1','skills','강타',{'enhance':19},verified=True)
  spec=importlib.util.spec_from_file_location('isolated_growth_display',subject.__file__);fresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(fresh)
  self.assertEqual(fresh.current_value(self.root,'p1','skills','강타','enhance'),'19')
  self.assertEqual(fresh.current_value(self.root,'p2','skills','강타','enhance'),'—')
  self.assertEqual(fresh.current_value(self.root/'another','p1','skills','강타','enhance'),'—')
 def test_equipment_fields_merge_but_grade_change_does_not_inherit(self):
  base={'character':'p1','item_identity':'icon:item','grade':'일반','enhancement':40,'verified_fields':['enhancement']}
  subject.observe(self.root,base)
  subject.observe(self.root,dict(base,awakening=1,verified_fields=['awakening']))
  self.assertEqual(subject.current(self.root,'p1','일반','enhance'),'40');self.assertEqual(subject.current(self.root,'p1','일반','awaken'),'1')
  subject.observe(self.root,dict(base,grade='희귀',enhancement=0))
  self.assertEqual(subject.current(self.root,'p1','희귀','enhance'),'0');self.assertEqual(subject.current(self.root,'p1','희귀','awaken'),'—')
 def test_unverified_values_cannot_enter_display_cache(self):
  self.assertFalse(subject.observe_value(self.root,'p1','skills','강타',{'enhance':19}))
  self.assertEqual(subject.current_value(self.root,'p1','skills','강타','enhance'),'—')
 def test_verified_replacement_can_remove_old_item_without_other_scope_loss(self):
  old={'character':'p1','item_identity':'old-weapon','grade':'희귀','enhancement':40,'awakening':1,'verified_fields':['enhancement','awakening']}
  subject.observe(self.root,old);subject.observe(self.root,dict(old,character='p2'))
  subject.observe(self.root,dict(old,item_identity='new-weapon',enhancement=0,awakening=None,verified_fields=['enhancement']))
  self.assertTrue(subject.invalidate_item(self.root,'p1','old-weapon'))
  self.assertEqual(subject.current(self.root,'p1','희귀','enhance'),'0');self.assertEqual(subject.current(self.root,'p1','희귀','awaken'),'—')
  self.assertEqual(subject.current(self.root,'p2','희귀','enhance'),'40')
  self.assertEqual(subject.current(self.root,'p2','희귀','awaken'),'1')
 def test_delayed_old_grade_invalidation_never_removes_replacement(self):
  row={'character':'p1','item_identity':'same-visual-token','grade':'일반','enhancement':40,'verified_fields':['enhancement']}
  subject.observe(self.root,row)
  subject.observe(self.root,dict(row,grade='희귀',enhancement=0))
  self.assertFalse(subject.invalidate_item(self.root,'p1','same-visual-token',grade='일반'))
  self.assertEqual(subject.current(self.root,'p1','희귀','enhance'),'0')
 def test_corrupt_or_cross_scope_disk_record_does_not_leak(self):
  path=self.root/'settings/owner-growth-current.json';path.parent.mkdir()
  path.write_text(json.dumps({'version':1,'values':[{'character':'other','section':'skills','key':'파멸','values':{'enhance':49},'at_epoch':1000}],'equipment':[]}),encoding='utf8')
  self.assertEqual(subject.current_value(self.root,'mine','skills','파멸','enhance'),'—')
  self.assertEqual(subject.current_value(self.root,'other','skills','파멸','enhance'),'49')


if __name__=='__main__':unittest.main()
