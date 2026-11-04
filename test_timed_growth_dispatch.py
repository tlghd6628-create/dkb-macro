from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
import owner_timetable as t
class Tests(unittest.TestCase):
 def setUp(self):
  self.events=[];self.adapter=NS(mode='sub_quest',project=NS(root='unused'))
  self.plan=NS(state={'gear':{}},values={'auto_growth.equipment.enabled':True},reason=lambda key:None,begin=lambda key:self.events.append(('begin',key)),
   finish=lambda key,ok,**kw:self.events.append(('finish',key,ok,kw)),apply_outcome=lambda key,outcome:self.events.append(('outcome',key,outcome.kind)))
  self.label=t.BY_KEY['gear'].label
  self.patch=patch.multiple(t,planner=lambda a:self.plan,config=lambda r:{'jobs':{}})
  self.patch.start();self.addCleanup(self.patch.stop)
 def test_timed_default_growth_tracks_attempt_and_unverified_result(self):
  self.assertIsNone(t.scheduled_call(lambda:None,self.label,(),{},self.adapter,timed_dispatch=True))
  self.assertEqual(self.events,[('begin','gear'),('finish','gear',True,{'unverified':True})])
 def test_direct_quest_growth_milestone_preserves_original_bypass(self):
  self.adapter._owner_growth_milestone=45
  self.assertEqual(t.scheduled_call(lambda:'native',self.label,(),{},self.adapter),'native')
  self.assertEqual(self.events,[])
 def test_regular_story_growth_does_not_bypass_backoff(self):
  self.plan.reason=lambda key:'이전 결과 확인 대기'
  called=[]
  self.assertTrue(t.scheduled_call(lambda:called.append(True),self.label,(),{},self.adapter))
  self.assertEqual(called,[])
  self.assertEqual(self.events,[])
 def test_failed_timed_growth_is_backed_off(self):
  self.assertFalse(t.scheduled_call(lambda:False,self.label,(),{},self.adapter,timed_dispatch=True))
  self.assertEqual(self.events,[('begin','gear'),('finish','gear',False,{'unverified':False})])
 def test_pending_growth_result_is_not_processed_by_native_none(self):
  def native():self.adapter._owner_growth_pending_hold=True
  t.scheduled_call(native,self.label,(),{},self.adapter,timed_dispatch=True)
  self.assertEqual(self.events,[('begin','gear'),('outcome','gear','not_attempted')])
 def test_energy_continuation_is_processing_not_verified_completion(self):
  self.plan.state={'growth':{}};self.plan.values={'auto_growth.energy.enabled':True}
  self.adapter._owner_energy_outcome='목표 미설정 · 실행 건너뜀'
  result=t.scheduled_call(lambda:True,t.BY_KEY['growth'].label,(),{},self.adapter)
  self.assertTrue(result)
  self.assertEqual(self.events,[('begin','growth'),('finish','growth',True,{'unverified':True})])
if __name__=='__main__':unittest.main()
