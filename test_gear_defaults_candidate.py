import sys, unittest, tempfile, copy, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_gear_settings_candidate import DEFAULT, validate, Store
from owner_growth_policy_candidate import GEAR_TARGETS, SKILL_REINFORCEMENT_TARGETS

class Defaults(unittest.TestCase):
 def test_settings_and_policy_share_the_same_targets(self):
  validate(DEFAULT)
  for grade,target in GEAR_TARGETS.items():
   self.assertEqual((DEFAULT['grades'][grade]['enhance'],DEFAULT['grades'][grade]['breakthrough'],DEFAULT['grades'][grade]['awaken']),
                    (target.enhance,target.breakthrough,target.awakening))
  self.assertEqual(DEFAULT['grades']['영웅']['breakthrough'],2)
 def test_skill_defaults_are_separate_and_customizable(self):
  self.assertEqual({k:SKILL_REINFORCEMENT_TARGETS[k] for k in ('파멸','강타','강인')},{'파멸':49,'강타':19,'강인':19})
  self.assertEqual(len(SKILL_REINFORCEMENT_TARGETS),12)
  with tempfile.TemporaryDirectory() as root:
   store=Store(root,'server / character');value=store.read()
   value['skills']['파멸']={'enabled':True,'enhance':48}
   store.write(value)
   self.assertEqual(store.read()['skills']['파멸'],{'enabled':True,'enhance':48,'breakthrough':0})
   self.assertEqual(store.read()['grades'],DEFAULT['grades'])
 def test_old_equipment_settings_survive_skill_defaults(self):
  with tempfile.TemporaryDirectory() as root:
   store=Store(root,'server / character');store.path.parent.mkdir(parents=True)
   old=copy.deepcopy(DEFAULT)
   for section in ('skills','individual','album','blessings','energies'):old.pop(section)
   old['grades']['희귀']['enhance']=37
   store.path.write_text(json.dumps(old,ensure_ascii=False),encoding='utf-8')
   loaded=store.read()
   self.assertEqual(loaded['grades']['희귀']['enhance'],37)
   self.assertEqual(loaded['skills'],DEFAULT['skills'])
   self.assertEqual(loaded['album'],{'mode':'조각 등록만'})
   self.assertEqual(loaded['blessings']['5번'],{'enabled':False,'enhance':49,'breakthrough':0})
   self.assertIsNone(loaded['energies']['홍염']['stage'])
   # 높은 등급 우선 장착 (11-06) reads as off on an old document.
   self.assertEqual(loaded['blessing_equip'],{'enabled':True,'priorities':[],'higher':False})
   self.assertNotIn('skills',json.loads(store.path.read_text(encoding='utf-8')))
 def test_invalid_skill_settings_rejected(self):
  value=copy.deepcopy(DEFAULT);value['skills']['파멸']['enhance']=True
  with self.assertRaises(ValueError):validate(value)
  value=copy.deepcopy(DEFAULT);del value['skills']['기동']
  with self.assertRaises(ValueError):validate(value)
  value=copy.deepcopy(DEFAULT);value['album']['mode']='임의'
  with self.assertRaises(ValueError):validate(value)
  value=copy.deepcopy(DEFAULT);value['energies']['생명']['enabled']=True
  with self.assertRaises(ValueError):validate(value)
 def test_three_style_settings_migrate_without_changing_custom_values(self):
  with tempfile.TemporaryDirectory() as root:
   store=Store(root,'server / character');store.path.parent.mkdir(parents=True)
   old=copy.deepcopy(DEFAULT)
   old['skills']={k:old['skills'][k] for k in ('파멸','강타','강인')}
   old['skills']['파멸']={'enabled':True,'enhance':44}
   store.path.write_text(json.dumps(old,ensure_ascii=False),encoding='utf-8')
   loaded=store.read()
   self.assertEqual(loaded['skills']['파멸'],{'enabled':True,'enhance':44,'breakthrough':0})
   self.assertEqual(loaded['skills']['제압'],{'enabled':False,'enhance':0,'breakthrough':0})
   self.assertEqual(len(loaded['skills']),12)

if __name__=='__main__':unittest.main()
