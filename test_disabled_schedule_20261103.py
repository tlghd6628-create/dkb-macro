"""Inactive appointments must retain history without occupying active time."""
import unittest,tempfile,copy
from pathlib import Path
from datetime import datetime,timedelta
from types import SimpleNamespace as S
from unittest.mock import patch,Mock
import bootstrap
import owner_timetable as t

class Disabled(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.at=datetime(2026,11,3,12,40,tzinfo=t.KST);p=t.Planner.__new__(t.Planner);self.p=p
  p.root=Path(self.temp.name);p.identity='test';p.cfg={'enabled':True,'jobs':{},'jitter_seconds':0,'seed':'trial'}
  p.values={'auto_growth.equipment.enabled':True};p.commit=Mock();p.state={
   'gear':{'status':'processed','result_unverified':True,'period':t.period(t.BY_KEY['gear'],self.at),'ended_at':(self.at-timedelta(minutes=2)).isoformat(),'attempts':1},
   'weekly_dungeon':{'status':'pending','period':t.period(t.BY_KEY['weekly_dungeon'],self.at),'at':self.at.isoformat(),'budget_minutes':320}}
  self.before=copy.deepcopy(p.state['weekly_dungeon'])
  self.patch=patch.object(t,'busy_windows',return_value=[]);self.patch.start();self.addCleanup(self.patch.stop)
  self.ident=patch('owner_hunt_rules_candidate.configured_identity',return_value='configured-character');self.ident.start();self.addCleanup(self.ident.stop)
 def store(self,*a):return S(path=self.p.root/'missing',read=lambda:{'recheck_minutes':1})
 def test_disabled_dungeon_does_not_push_growth_retry_five_hours(self):
  with patch('owner_gear_settings_candidate.Store',side_effect=self.store):self.assertTrue(self.p.repeat_growth(self.at))
  self.assertEqual(t.parse_at(self.p.state['gear']['at']),self.at)
  self.assertEqual(self.p.state['weekly_dungeon'],self.before)
 def test_enabled_dungeon_still_blocks_the_growth_slot(self):
  self.p.values[t.BY_KEY['weekly_dungeon'].setting]=True
  with patch('owner_gear_settings_candidate.Store',side_effect=self.store):self.p.repeat_growth(self.at)
  self.assertGreaterEqual(t.parse_at(self.p.state['gear']['at']),self.at+timedelta(minutes=320))
 def test_finish_does_not_move_a_disabled_jobs_historical_appointment(self):
  self.p.finish('gear',True,self.at,unverified=False)
  self.assertEqual(self.p.state['weekly_dungeon'],self.before)
 def test_repeat_reads_configured_profile_not_human_schedule_label(self):
  seen=[]
  def store(root,identity):seen.append(identity);return self.store()
  with patch('owner_gear_settings_candidate.Store',side_effect=store):
   self.p.repeat_growth(self.at)
   self.assertEqual(self.p.recheck_minutes(),1)
  self.assertEqual(seen,['configured-character','configured-character'])

if __name__=='__main__':unittest.main()
