import ast, pathlib, types, sys, time, unittest, logging
p=pathlib.Path(__file__).with_name('owner_mission_controller.py')
tree=ast.parse(p.read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='finish_dialogue_before_pick')
class Pending(RuntimeError): pass
m=types.ModuleType('owner_quest_clicks'); m.step=lambda runner,context,changes:runner.step()
ns={'time':time,'Pending':Pending,'LOG':logging.getLogger('test')};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),ns)
f=ns['finish_dialogue_before_pick']
class Cases(unittest.TestCase):
 def setUp(self):
  from unittest.mock import patch
  scoped=patch.dict(sys.modules, {'owner_quest_clicks':m});scoped.start();self.addCleanup(scoped.stop)
 def test_dialogue_then_clear(self):
  states=iter([True,True,True,False]);ui=types.SimpleNamespace(execution_dialogue_pair=lambda:next(states));ctx=types.SimpleNamespace(checkpoint=lambda:None,wait=lambda x:None);calls=[];runner=types.SimpleNamespace(step=lambda:calls.append(1))
  self.assertTrue(f(ui,ctx,runner));self.assertEqual(len(calls),2)
 def test_no_dialogue_no_input(self):
  self.assertFalse(f(types.SimpleNamespace(execution_dialogue_pair=lambda:False),None,None))
 def test_death_never_silently_discarded(self):
  ui=types.SimpleNamespace(execution_dialogue_pair=lambda:True);ctx=types.SimpleNamespace(checkpoint=lambda:None,wait=lambda x:None);runner=types.SimpleNamespace(step=lambda:'DEATH_RECOVERED')
  with self.assertRaises(Pending):f(ui,ctx,runner)
 def test_stop_propagates(self):
  ui=types.SimpleNamespace(execution_dialogue_pair=lambda:True);ctx=types.SimpleNamespace(checkpoint=lambda:(_ for _ in ()).throw(InterruptedError()),wait=lambda x:None)
  with self.assertRaises(InterruptedError):f(ui,ctx,None)
if __name__=='__main__':unittest.main()
