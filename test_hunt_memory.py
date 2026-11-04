from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import json,tempfile,unittest,time
from types import SimpleNamespace as NS
from owner_hunt_memory import HuntMemory,record_death,blocked_saved,set_route,saved_key,guide_excluded

class Tests(unittest.TestCase):
 def setup_root(self,root):
  p=Path(root)/'settings';p.mkdir()
  (p/'manager_identity.json').write_text(json.dumps({'server_name':'서버','character_name':'캐릭터'}),encoding='utf-8')
 def test_death_hold_survives_restart_unknown_power_never_releases(self):
  with tempfile.TemporaryDirectory(dir=T) as root:
   self.setup_root(root);m=HuntMemory(root,'live-a');m.died('slot:2@120000',100000);self.assertFalse(m.blocked('slot:2@120000',100000))
   m.died('slot:2@120000',100000);m=HuntMemory(root,'live-a')
   self.assertTrue(m.blocked('slot:2@120000',None));self.assertTrue(m.blocked('slot:2@120000',200000))
   m.accept_fresh(120000,time.time()+1)
   self.assertTrue(m.blocked('slot:2@120000',137999));self.assertFalse(m.blocked('slot:2@120000',138000))
 def test_different_profile_and_character_are_separate(self):
  with tempfile.TemporaryDirectory(dir=T) as root:
   self.setup_root(root);m=HuntMemory(root,'a');m.died('guide:84500',100000);m.died('guide:84500',100000)
   self.assertTrue(m.blocked('guide:84500',100000));self.assertFalse(HuntMemory(root,'b').blocked('guide:84500',100000))
 def test_only_actual_route_records_deaths_and_sets_fallback(self):
  with tempfile.TemporaryDirectory(dir=T) as root:
   self.setup_root(root);a=NS(project=NS(root=root),_owner_progression=NS(character='a',power=103000,observed=time.monotonic()))
   self.assertIsNone(record_death(a));set_route(a,saved_key({'power':0,'slot':2}),'저장 위치 2')
   self.assertEqual(record_death(a),1);self.assertFalse(getattr(a,'_owner_hunt_fallback_due',False))
   self.assertEqual(record_death(a),2);self.assertTrue(a._owner_hunt_fallback_due)
   self.assertTrue(blocked_saved(a,{'power':0,'slot':2},103000))
 def test_failed_guide_is_excluded_without_modifying_power(self):
  with tempfile.TemporaryDirectory(dir=T) as root:
   self.setup_root(root);a=NS(project=NS(root=root),_owner_progression=NS(character='a',power=103000,observed=time.monotonic()))
   m=HuntMemory(root,'a');m.died('guide:84500',103000);m.died('guide:84500',103000)
   self.assertEqual(guide_excluded(a,103000),{84500});self.assertEqual(a._owner_progression.power,103000)

if __name__=='__main__':unittest.main()
