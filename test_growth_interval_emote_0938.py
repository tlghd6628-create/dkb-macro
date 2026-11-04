"""Focused saved-frame/config/fake-input checks, never game operations."""
import copy,tempfile,unittest
from datetime import datetime,timedelta
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import owner_timetable as t
import owner_emote_dispatch as emote
from owner_gear_settings_candidate import Store,DEFAULT,validate
from owner_skill_goal import Pending

class IntervalTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.at=datetime(2026,11,2,9,40,tzinfo=t.KST)
  self.p=t.Planner.__new__(t.Planner);self.p.root=self.root;self.p.identity='char'
  self.p.values={'auto_growth.equipment.enabled':True};self.p.cfg={'enabled':True,'jobs':{}}
  self.p.state={'gear':{'period':t.period(t.BY_KEY['gear'],self.at),'status':'processed','attempts':1,'result_unverified':True,'ended_at':self.at.isoformat()}}
  self.p.commit=lambda:None
 def test_old_setting_defaults_and_custom_survives_new_store(self):
  d=copy.deepcopy(DEFAULT);d.pop('recheck_minutes');Store(self.root,'char').write(d)
  self.assertEqual(Store(self.root,'char').read()['recheck_minutes'],20)
  d['recheck_minutes']=37;Store(self.root,'char').write(d)
  self.assertEqual(Store(self.root,'char').read()['recheck_minutes'],37)
 def test_invalid_interval_rejected(self):
  for n in (0,-1,1441,True,'20',2.5):
   d=copy.deepcopy(DEFAULT);d['recheck_minutes']=n
   with self.assertRaises(ValueError):validate(d)
 def test_legacy_unverified_visit_rechecks_after_twenty_minutes_no_completion_claim(self):
  with patch.object(t,'busy_windows',return_value=[]):self.assertTrue(self.p.repeat_growth(self.at))
  r=self.p.state['gear'];self.assertEqual(t.parse_at(r['at']),self.at+timedelta(minutes=20));self.assertEqual(r['status'],'pending');self.assertEqual(r['attempts'],0)
  self.assertTrue(r['result_unverified'])
  with patch.object(t,'busy_windows',return_value=[]):self.assertFalse(self.p.repeat_growth(self.at+timedelta(minutes=2)))
 def test_custom_interval_change_reschedules_pending_visit(self):
  with patch.object(t,'busy_windows',return_value=[]):self.p.repeat_growth(self.at)
  d=Store(self.root,'char').read();d['recheck_minutes']=35;Store(self.root,'char').write(d)
  with patch.object(t,'busy_windows',return_value=[]):self.assertTrue(self.p.repeat_growth(self.at+timedelta(minutes=1)))
  self.assertEqual(t.parse_at(self.p.state['gear']['at']),self.at+timedelta(minutes=35))
 def test_disabled_wrong_day_or_failed_pending_result_not_reset(self):
  self.p.values['auto_growth.equipment.enabled']=False;self.assertFalse(self.p.repeat_growth(self.at))
  self.p.values['auto_growth.equipment.enabled']=True;self.p.cfg['jobs']['gear']={'weekdays':[1]}
  self.assertFalse(self.p.repeat_growth(self.at))
  self.p.cfg['jobs']={};self.p.state['gear']['status']='failed';self.p.state['gear']['attempts']=2
  self.assertFalse(self.p.repeat_growth(self.at));self.assertEqual(self.p.state['gear']['attempts'],2)
 def test_boss_and_other_appointment_windows_are_avoided(self):
  start=self.at+timedelta(minutes=20)
  self.p.state['mail']={'status':'pending','at':(start+timedelta(minutes=20)).isoformat()}
  with patch.object(t,'busy_windows',return_value=[(start,start+timedelta(minutes=20))]):self.p.repeat_growth(self.at)
  self.assertGreaterEqual(t.parse_at(self.p.state['gear']['at']),start+timedelta(minutes=23))
 def test_verified_target_completion_does_not_rearm(self):
  self.p.state['gear'].pop('result_unverified');self.assertFalse(self.p.repeat_growth(self.at))

class EmoteTests(unittest.TestCase):
 def test_actual_compact_quoted_known_requirement_without_scrolled_prefix(self):
  from owner_emote_requirements import parse_target
  self.assertEqual(parse_target([{'text':"'황당' 사용하기",'score':.999}]),'황당')
  self.assertEqual(parse_target([{'text':'졸기 사용하기','score':.999}]),'졸기')
  self.assertIsNone(parse_target([{'text':"'물약' 사용하기",'score':.999}]))
  self.assertIsNone(parse_target([{'text':"'황당' 사용하기",'score':.90}]))
 def test_unknown_requirement_compares_meaning_not_marquee_geometry(self):
  rows=iter([[{'text':'채팅 감정표현 중 ‘기쁨’ 사용하기','score':.999,'bounds':(732,146,870,158)}],
             [{'text':'채팅 감정표현 중 ‘기쁨’ 사용하기','score':.999,'bounds':(736,147,874,159)}]])
  ui=S(rows=lambda *a,**kw:next(rows),context=S(wait=lambda _:None))
  self.assertEqual(emote.read_requirement(ui),('기쁨',147))
 def test_temporary_unreadable_requirements_do_not_permanently_defer_quest(self):
  ui=S(rows=lambda *a,**kw:(_ for _ in ()).throw(Pending('marquee changed')),context=S(wait=lambda _:None))
  self.assertIsNone(emote.read_requirement(ui))
 def test_different_requirements_and_low_confidence_never_authorize(self):
  rows=iter([[{'text':'감정표현 중 기쁨 사용하기','score':.999}], [{'text':'감정표현 중 황당 사용하기','score':.999}]])
  ui=S(rows=lambda *a,**kw:next(rows),context=S(wait=lambda _:None));self.assertIsNone(emote.read_requirement(ui))

if __name__=='__main__':unittest.main()
