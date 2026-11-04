"""Reproduce the real12:10 display-only tooltip failure with fake input.
No runtime input or resource operation is reached by this test."""
import unittest,tempfile
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch,Mock
import threading
from datetime import datetime,timedelta
import numpy as np
from PIL import Image
import bootstrap
from owner_chore_transition import ReadOnlyViewUnavailable,ChoreYield,unavailable_frame,unavailable_pair
import owner_worn_stats as w

class Unavailable(unittest.TestCase):
 def test_actual_failed_capture_is_unavailable_not_loading_or_completion(self):
  f=np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261103T031053Z-e4c09c90/screen.png').convert('RGB'))
  self.assertTrue(unavailable_frame(f));self.assertTrue(issubclass(ReadOnlyViewUnavailable,ChoreYield))
 def test_one_dark_frame_is_not_a_confirmed_pair(self):
  black=np.zeros((479,897,3),dtype='uint8');visible=np.full_like(black,60);seq=iter([black,visible])
  self.assertFalse(unavailable_pair(S(check=lambda:None,capture=lambda:next(seq)),S(checkpoint=lambda:None,wait=lambda n:None)))
  self.assertFalse(unavailable_frame(np.zeros((720,1280,3),dtype='uint8')))
  self.assertFalse(unavailable_frame(visible));self.assertFalse(unavailable_frame(None))
 def test_readonly_slot_yields_without_second_click_or_value_record_when_pixels_disappear(self):
  before=np.asarray(Image.open(Path(__file__).parent/'tooltip_followup/weapon.png').convert('RGB'))
  black=np.zeros_like(before);calls=[];n=[0]
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as tmp:
   adapter=S(project=S(root=Path(tmp)))
   def capture():
    n[0]+=1;return before.copy() if n[0]<=3 else black.copy()
   service=S(adapter=adapter,capture=capture,check=lambda:None,click_hit=lambda hit:calls.append(hit))
   context=S(checkpoint=lambda:None,wait=lambda n:None)
   with patch('owner_progression.inventory_parts',side_effect=lambda f:(True,True) if f is not None and f.any() else (False,False)),\
        patch('owner_equipment_boxes.agree',return_value={'무기':True}),patch('owner_ui_foreground.inventory_header',return_value='same character'),\
        patch('owner_inventory_filters.choose'),patch('owner_skill_ui.SkillUI',return_value=S()),\
        patch('tools.ocr_support.get_paddle_engine',return_value=S()),patch.object(w,'popup',return_value=False),\
        patch('owner_growth_current.observe',side_effect=AssertionError('no values may be recorded')):
    with self.assertRaises(ReadOnlyViewUnavailable):w.inspect_slot(service,context,S(),'profile','char','무기')
   self.assertEqual(len(calls),1);self.assertEqual(adapter._owner_worn_stats_cache,{})
 def test_timetable_retains_pending_without_failure_or_completion_and_backs_off(self):
  import owner_timetable as t
  at=datetime(2026,11,3,12,30,tzinfo=t.KST)
  row={'status':'pending','attempts':0,'at':at.isoformat()}
  def begin(key):row.update(status='running',attempts=row['attempts']+1)
  plan=S(reason=lambda key:None,state={'gear':row},begin=begin,commit=Mock(),finish=Mock(),values={'auto_growth.equipment.enabled':True})
  adapter=S(values={'auto_growth.equipment.enabled':True},_owner_timetable=plan,project=S(root=Path('never-opened')))
  context=S(stop=threading.Event(),checkpoint=lambda:None)
  with patch.object(t,'character_mismatch',return_value=False),patch.object(t,'now',return_value=at),patch.object(t,'config',return_value={'jobs':{}}):
   with self.assertRaises(ReadOnlyViewUnavailable):
    t.scheduled_call(Mock(side_effect=ReadOnlyViewUnavailable('무기')),t.BY_KEY['gear'].label,(),{},adapter,timed_dispatch=True,run_context=context)
  self.assertEqual(row['status'],'pending');self.assertEqual(row['attempts'],0)
  self.assertEqual(t.parse_at(row['at']),at+timedelta(seconds=10));plan.finish.assert_not_called()
 def test_known_field_after_tooltip_disappears_yields_without_another_click(self):
  with patch.object(w,'unavailable_pair',return_value=False),patch.object(w,'dialogue_pair',return_value=False):
   with self.assertRaises(ReadOnlyViewUnavailable):
    w.yield_readonly_if_interrupted(None,None,None,'무기',S(normal=lambda:True))
   # Unknown is not field or permission to dismiss anything. Caller keeps its
   # explicit unknown-popup RuntimeError fence, instead of blindly proceeding.
   self.assertIsNone(w.yield_readonly_if_interrupted(None,None,None,'무기',S(normal=lambda:False)))

if __name__=='__main__':unittest.main()
