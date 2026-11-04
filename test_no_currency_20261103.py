"""The currency read is gone; the rest of the real native dispatcher order stays. Fake inputs, never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import inspect,threading,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from biol_base.session import Context
import owner_rewards
import project_adapter._entry as entry
import project_adapter.currency_snapshot as snapshot
import project_adapter.secret_folktale as folktale

KEY='auto_challenge.secret_folktale_5h.enabled'

class Currency(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.reader=snapshot.CurrencyReader
  owner_rewards.install(S())
 def run_dispatch(self,values,mode,wait):
  calls=[]
  context=Context(threading.Event(),threading.Event())
  context.run_action=lambda name,operation:(calls.append(name),operation())[1]
  class Real:
   _run_auto_features=entry.Adapter._run_auto_features
   project=S(app_id='DKB',code='DKB',root=bootstrap.T/'test_scratch/no-test-reservations')
   def get_due_schedules(self):return []
   def run_town_return(self,*a,**k):calls.append('town');return True
   def run_mail_rewards(self,*a,**k):calls.append('mail');return True
   def __getattr__(self,name):raise AttributeError('fixture has no '+name)
  adapter=Real();adapter.values=values;adapter.mode=mode
  entered=Mock(return_value=True)
  with patch.object(snapshot,'CurrencyReader',side_effect=AssertionError('currency read')) as reader,patch.object(folktale,'run_folktale_exploration',entered):
   inspect.unwrap(entry.Adapter._run_auto_features)(adapter,context,Mock(),wait_for_hunt=wait,potion_done=True,periodic_wait=False)
  reader.assert_not_called()
  return calls,entered
 def test_dungeon_goes_from_town_straight_to_entry(self):
  calls,entered=self.run_dispatch({KEY:True},'auto_mode',True)
  self.assertIn('town',calls);entered.assert_called_once()
  self.assertEqual(entered.call_args.kwargs,{'kind':'5h'})
  self.assertLess(calls.index('town'),calls.index('auto_challenge.secret_folktale_5h'))
 def test_reward_only_run_is_unchanged(self):
  calls,_=self.run_dispatch({'auto_rewards.mail.enabled':True},'sub_quest',False)
  self.assertIn('mail',calls)
 def test_the_step_reports_done_without_touching_the_game(self):
  context,inputs=Mock(),Mock()
  self.assertIs(snapshot.run_currency_snapshot(Mock(),context,inputs),True)
  self.assertEqual(context.mock_calls,[]);self.assertEqual(inputs.mock_calls,[])
 def test_second_install_keeps_it_off(self):
  owner_rewards.install(S())
  self.assertTrue(snapshot.run_currency_snapshot._owner_reward_policy)

if __name__=='__main__':unittest.main()
