import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_hunt_rules_candidate import HuntRules
class Cases(unittest.TestCase):
 def test_settings_survive_restart_and_are_character_scoped(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
   HuntRules(root,'a').store([{'power':120000,'slot':2}],3);self.assertEqual(HuntRules(root,'a').read(),[{'power':120000,'slot':2}]);self.assertEqual(HuntRules(root,'a').stationary(),3);self.assertEqual(HuntRules(root,'b').read(),[]);self.assertIsNone(HuntRules(root,'b').stationary())
 def test_invalid_data_never_overwrites_settings(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
   obj=HuntRules(root,'a');obj.store([{'power':120000,'slot':2}]);before=obj.path.read_bytes()
   with self.assertRaises(ValueError):obj.store([{'power':120000,'slot':2},{'power':120000,'slot':3}])
   self.assertEqual(obj.path.read_bytes(),before)
 def test_corrupt_file_is_untouched(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
   p=Path(root)/'settings/owner-hunt-rules.json';p.parent.mkdir();p.write_text('bad')
   with self.assertRaises(ValueError):HuntRules(root,'a')
   self.assertEqual(p.read_text(),'bad')
class Destinations(unittest.TestCase):
    """One selected source for every mode: never both."""
    def rules(self,rules,fixed,enabled=True):
        from owner_hunt_rules_candidate import HuntRules
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        root=Path(directory.name);(root/'settings').mkdir()
        item=HuntRules(root,'c');item.store(rules,fixed,enabled=enabled);return HuntRules(root,'c')
    def pick(self,item,power):
        from owner_growth_policy_candidate import choose_hunt_rule
        return choose_hunt_rule(power,item.destinations())['slot']
    def test_a_met_threshold_goes_first(self):
        item=self.rules([{'power':110000,'slot':1},{'power':140000,'slot':3}],2)
        self.assertEqual(self.pick(item,150000),3);self.assertEqual(self.pick(item,120000),1)
    def test_under_every_threshold_the_fixed_spot_is_not_mixed_in(self):
        from owner_growth_policy_candidate import choose_hunt_rule
        self.assertIsNone(choose_hunt_rule(90000,self.rules([{'power':110000,'slot':1}],2).destinations()))
    def test_a_file_with_both_ticked_and_rules_reads_as_power(self):
        self.assertEqual(self.rules([{'power':110000,'slot':1}],2).source(),'power')
    def test_a_file_with_both_ticked_and_no_rules_reads_as_fixed(self):
        item=self.rules([],2);self.assertEqual(item.source(),'fixed');self.assertEqual(item.destinations(),[{'power':0,'slot':2}])
    def test_fixed_source_ignores_written_rules(self):
        item=self.rules([{'power':110000,'slot':1}],2);item.store([{'power':110000,'slot':1}],2,enabled=False,fixed_enabled=True)
        self.assertEqual(item.destinations(),[{'power':0,'slot':2}]);self.assertEqual(item.stored(),[{'power':110000,'slot':1}])
    def test_power_rules_switched_off_leave_the_stationary_spot(self):
        self.assertEqual(self.pick(self.rules([{'power':110000,'slot':1}],2,enabled=False),150000),2)
    def test_a_zero_rule_is_not_duplicated(self):
        item=self.rules([{'power':0,'slot':3}],2);self.assertEqual(item.destinations(),[{'power':0,'slot':3}])
    def test_the_fixed_switch_off_drops_the_fixed_spot(self):
        from owner_hunt_rules_candidate import HuntRules
        item=self.rules([{'power':110000,'slot':1}],2);item.store([{'power':110000,'slot':1}],2,enabled=True,fixed_enabled=False)
        item=HuntRules(item.path.parents[1],'c');self.assertEqual(item.destinations(),[{'power':110000,'slot':1}]);self.assertEqual(item.stationary(),2)
    def test_old_files_keep_the_fixed_spot_on(self):
        self.assertTrue(self.rules([],2).fixed_enabled())
    def test_nothing_set_means_no_destination(self):
        self.assertEqual(self.rules([],None).destinations(),[])
    def test_every_mode_reads_the_same_rule(self):
        source=(Path(__file__).resolve().parent/'owner_mission_controller.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('configured.destinations()'),3);self.assertNotIn("rules=configured.read()",source)

if __name__=='__main__':unittest.main()
