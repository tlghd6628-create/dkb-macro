"""Settings editors must use the same collision-safe configured identity."""
import json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import bootstrap
import owner_hunt_settings_candidate as module
from owner_hunt_rules_candidate import configured_identity

class Button:
    made=[]
    def __init__(self,*args,**kwargs):self.kw=kwargs;self.made.append(self)
    def configure(self,**kwargs):self.kw.update(kwargs)
    def place(self,**kwargs):pass
    def grid(self,**kwargs):pass
    def winfo_exists(self):return True

class Window:
    def __init__(self,*args,**kwargs):self.dead=False
    def winfo_exists(self):return True
    def title(self,*args):pass
    def resizable(self,*args):pass
    def destroy(self):self.dead=True
    def pack(self,**kwargs):pass

class EditorIdentity(unittest.TestCase):
    def test_growth_editor_uses_configured_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'settings').mkdir()
            (root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'A / B','character_name':'C'}),encoding='utf-8')
            window=Window();button=Button()
            gui=NS(open_details=lambda:None,settings_window=window,details_button=button,
                   visual_view=NS(widgets={}),project=NS(root=root),root=window,
                   session=NS(snapshot=lambda:{'status':'stopped','worker_alive':False}))
            calls=[]
            with patch.object(module.ttk,'Button',Button),patch.object(module.ttk,'Frame',Window),patch.object(module.tk,'Toplevel',Window),patch('owner_gear_settings_candidate.open_settings',side_effect=lambda *args:calls.append(args)):
                module.install(gui);button.kw['command']()
                next(b for b in Button.made if b.kw.get('text')=='성장 목표').kw['command']()
            self.assertEqual(calls[0][2],configured_identity(root))
            first=calls[0][2]
            (root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'A','character_name':'B / C'}),encoding='utf-8')
            self.assertNotEqual(first,configured_identity(root))

if __name__=='__main__':unittest.main()
