import bootstrap
import time,unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import owner_timetable as timetable
import owner_progression,owner_hunt_rules_candidate,owner_equipment_upgrade_candidate,owner_gear_settings_candidate

class GrowthDispatchTests(unittest.TestCase):
 def test_confirmed_request_dispatch_once_with_original_equipment_setting(self):
  progress=NS(character='hero',observed=time.monotonic());seen=[];saved=[]
  adapter=NS(project=NS(root='test'),values={'original':'preserved'},mode='sub_quest',exit_sleep_mode=lambda *args:None)
  plan=NS(values={'auto_growth.equipment.enabled':True,'auto_growth.blessing.enabled':True,'auto_growth.taoist.enabled':True})
  journal=NS(path=NS(exists=lambda:True),growth_request=lambda:{'slot':'무기','growth_request_id':'req'},mark_growth_dispatched=saved.append)
  ctx=NS(checkpoint=lambda:None)
  with patch.object(owner_hunt_rules_candidate,'configured_identity',return_value='server'),patch.object(owner_progression,'state',return_value=progress),patch.object(owner_equipment_upgrade_candidate,'Journal',return_value=journal),patch.object(owner_gear_settings_candidate,'Store',return_value=NS(read=lambda:{'grades':{'희귀':{'enabled':True}}})),patch.object(timetable,'busy_windows',return_value=[]),patch.object(timetable,'invoke',side_effect=lambda a,*args:seen.append(dict(a.values))):
   # 11-06: in a quest the follow-up growth waits for the quest's boundary (owner_job_timing).
   self.assertFalse(timetable.post_equip_growth(adapter,ctx,None,plan))
   import owner_job_timing
   with owner_job_timing.boundary():self.assertTrue(timetable.post_equip_growth(adapter,ctx,None,plan))
  self.assertEqual(saved,['req']);self.assertEqual(adapter.values,{'original':'preserved'})
  self.assertTrue(seen[0]['auto_growth.equipment.enabled']);self.assertFalse(seen[0]['auto_growth.blessing.enabled']);self.assertFalse(seen[0]['auto_growth.taoist.enabled'])
 def test_disabled_and_stale_do_not_dispatch(self):
  adapter=NS(project=NS(root='test'),values={},mode='sub_quest');ctx=NS(checkpoint=lambda:None)
  self.assertFalse(timetable.post_equip_growth(adapter,ctx,None,NS(values={'auto_growth.equipment.enabled':False})))
  with patch.object(owner_hunt_rules_candidate,'configured_identity',return_value='server'),patch.object(owner_progression,'state',return_value=NS(character='hero',observed=time.monotonic()-181)),patch.object(timetable,'invoke') as call:
   self.assertFalse(timetable.post_equip_growth(adapter,ctx,None,NS(values={'auto_growth.equipment.enabled':True})))
   call.assert_not_called()
 def test_failed_growth_keeps_request_and_restores_values(self):
  progress=NS(character='hero',observed=time.monotonic());saved=[]
  adapter=NS(project=NS(root='test'),values={'old':1},mode='sub_quest',exit_sleep_mode=lambda *args:None)
  plan=NS(values={'auto_growth.equipment.enabled':True})
  journal=NS(path=NS(exists=lambda:True),growth_request=lambda:{'slot':'무기','growth_request_id':'req'},mark_growth_dispatched=saved.append)
  with patch.object(owner_hunt_rules_candidate,'configured_identity',return_value='server'),patch.object(owner_progression,'state',return_value=progress),patch.object(owner_equipment_upgrade_candidate,'Journal',return_value=journal),patch.object(owner_gear_settings_candidate,'Store',return_value=NS(read=lambda:{'grades':{'희귀':{'enabled':True}}})),patch.object(timetable,'busy_windows',return_value=[]),patch.object(timetable,'invoke',return_value=False):
   import owner_job_timing
   with owner_job_timing.boundary():self.assertTrue(timetable.post_equip_growth(adapter,NS(checkpoint=lambda:None),None,plan))
  self.assertEqual(saved,[]);self.assertEqual(adapter.values,{'old':1})

if __name__=='__main__':unittest.main()
