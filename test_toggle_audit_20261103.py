"""Disabled boundary calls, native schema persistence; no game operations."""
import bootstrap,json,unittest,tempfile
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
from owner_clan_field_help import add_switch,SWITCH
from tools.gui_settings import SettingsModel,fields

class Switches(unittest.TestCase):
 def test_help_switch_defaults_off_and_reuses_native_save(self):
  schema=json.loads((bootstrap.A/'profiles/DKB/config/gui-schema.json').read_text(encoding='utf8'))
  add_switch(schema);add_switch(schema)
  self.assertEqual(sum(f['id']==SWITCH for f in fields(schema)),1)
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   model=SettingsModel(schema,Path(temp)/'settings.json',capabilities=lambda:{f['capability'] for f in fields(schema)})
   self.assertFalse(model.values[SWITCH]);self.assertTrue(model.editable(model.items[SWITCH]))
   model.save(model.mode,dict(model.values,**{SWITCH:True}))
   loaded=SettingsModel(schema,Path(temp)/'settings.json',capabilities=lambda:{f['capability'] for f in fields(schema)})
   self.assertTrue(loaded.values[SWITCH])
 def test_each_inventory_wrapper_stops_before_original_or_screen_when_off(self):
  import owner_inventory,owner_equipment_boxes,owner_starter_choice_candidate,owner_equip_runtime_install_candidate
  from project_adapter import market_inventory as inv
  from project_adapter._entry import Adapter
  for mod in (owner_inventory,owner_equipment_boxes,owner_starter_choice_candidate,owner_equip_runtime_install_candidate):
   def original(*args,**kwargs):raise AssertionError('disabled original invoked')
   with self.subTest(module=mod.__name__),patch.object(inv,'run_inventory_use',original),patch.object(Adapter,'run_inventory_use',original):
    gui=S(logger=S(info=lambda *a:None,debug=lambda *a:None))
    mod.install(gui)
    adapter=S(values={'auto_rewards.inventory_use.enabled':False})
    self.assertIs(inv.run_inventory_use(adapter,None,None),False)

if __name__=='__main__':unittest.main()
