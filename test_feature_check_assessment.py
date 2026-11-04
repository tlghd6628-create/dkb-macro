import bootstrap
import unittest
from owner_feature_check_status_candidate import assessment,summarize,status

class Assessment(unittest.TestCase):
 def observed(self,finding='ready'):
  return dict(id='gear_enhance',stage='action_ready',finding=finding,result='확인 필요',
              screen_verified=True,values_verified=True,decision_verified=False)
 def test_complete_current_conditions_are_normal_without_spending(self):
  row=self.observed();self.assertEqual(assessment(row)['outcome'],'normal')
  row['values_verified']=False;self.assertEqual(assessment(row)['outcome'],'unverified')
 def test_goal_and_shortage_are_waiting_only_with_actual_readings(self):
  for finding,stage in (('goal_reached','action_ready'),('game_limit','action_ready'),('materials_short','values')):
   row=dict(self.observed(finding),stage=stage)
   self.assertEqual(assessment(row)['outcome'],'waiting')
   row['screen_verified']=False;self.assertEqual(assessment(row)['outcome'],'unverified')
 def test_menu_and_saved_schedule_are_not_gameplay_readiness(self):
  row=self.observed('decision_not_probed');self.assertEqual(assessment(row)['outcome'],'unverified')
  row=dict(id='tower',stage='action_ready',finding='scheduled',result='확인 필요',diagnostic={'committed':False})
  self.assertEqual(assessment(row)['outcome'],'unverified')
 def test_config_off_is_excluded_not_a_recognition_error(self):
  row=dict(stage='config',finding='settings_off',result='확인 필요')
  self.assertEqual(assessment(row)['outcome'],'excluded')
  row['assessment']=assessment(row);self.assertTrue(status(row).startswith('제외'))
 def test_an_actual_reading_failure_is_an_error(self):
  self.assertEqual(assessment(dict(self.observed('values_unreadable'),stage='values'))['outcome'],'error')
 def test_counts_cover_every_row_once(self):
  rows=[self.observed(),self.observed('goal_reached'),dict(stage='config',finding='settings_off'),
        dict(stage='contract',finding='contract_error'),dict(stage='action_ready',finding='projection_only')]
  counts=summarize(rows)
  self.assertEqual(sum(counts.values()),len(rows));self.assertEqual(set(counts.values()),{1})

if __name__=='__main__':unittest.main()
