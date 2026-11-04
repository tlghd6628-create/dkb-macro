import unittest
from types import SimpleNamespace as S
from pathlib import Path
from PIL import Image
import numpy as np
import bootstrap
from owner_clan_field_help import attempt

class Tests(unittest.TestCase):
 def ui(self,changed=False):
  frame=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/field_clan_help_native.png').convert('RGB'));actions=[];calls=[]
  def capture():
   calls.append(1);f=frame.copy()
   if changed and len(calls)>1:f[385:414,10:40]=0
   return f
  def click(x,y,proof):
   self.assertTrue(proof(capture()));actions.append((x,y))
  return S(adapter=S(project=S(root=bootstrap.A,code='DKB'),values={'auto_rewards.clan_help.enabled':True}),context=S(input_depth=0,wait=lambda n:None),inputs=S(held=()),normal=lambda:True,frame=capture,click=click),actions
 def test_off_or_missing_switch_does_not_even_inspect_the_game(self):
  for values in ({},{'auto_rewards.clan_help.enabled':False}):
   ui,a=self.ui();ui.adapter.values=values
   ui.frame=lambda:(_ for _ in ()).throw(AssertionError('disabled help must not capture'))
   self.assertFalse(attempt(ui));self.assertEqual(a,[])
 def test_native_field_pair_only_free_help_location(self):
  ui,a=self.ui();self.assertTrue(attempt(ui));self.assertEqual(a,[(24,398)]);self.assertFalse(attempt(ui));self.assertEqual(len(a),1)
 def test_disappeared_button_and_nonfield_do_not_click(self):
  ui,a=self.ui(True);self.assertFalse(attempt(ui));self.assertEqual(a,[])
  ui,a=self.ui();ui.normal=lambda:False;self.assertFalse(attempt(ui));self.assertEqual(a,[])
 def test_held_input_does_not_click(self):
  ui,a=self.ui();ui.inputs.held=('key',);self.assertFalse(attempt(ui));self.assertEqual(a,[])

if __name__=='__main__':unittest.main()
