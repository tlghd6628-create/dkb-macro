import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from datetime import datetime,timezone
from retry_preinput_growth_0302 import transform
class Tests(unittest.TestCase):
 def fixture(self):return {'characters':{'A':{'gear':{'status':'failed','attempts':2,
  'started_at':'2026-11-02T03:02:50.805627+09:00','ended_at':'2026-11-02T03:02:53.507577+09:00'},
  'other':{'status':'processed'}}}}
 def test_one_exact_failure_is_retained_and_retried_without_completion(self):
  old=self.fixture();new,name=transform(old,datetime.now(timezone.utc))
  self.assertEqual(name,'A');row=new['characters']['A']['gear']
  self.assertEqual(row['status'],'pending');self.assertEqual(row['attempts'],1)
  self.assertEqual(row['maintenance_retries'][0]['original_failure'],old['characters']['A']['gear'])
  self.assertEqual(new['characters']['A']['other'],old['characters']['A']['other'])
  with self.assertRaises(ValueError):transform(new,datetime.now(timezone.utc))
 def test_completed_or_other_failure_never_changes(self):
  old=self.fixture();old['characters']['A']['gear']['status']='processed'
  with self.assertRaises(ValueError):transform(old,datetime.now(timezone.utc))
if __name__=='__main__':unittest.main()
