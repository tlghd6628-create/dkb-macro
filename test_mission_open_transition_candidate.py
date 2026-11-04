import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
from owner_mission_ui import MissionUI,Pending

class Tests(unittest.TestCase):
 def ui(self,wait,button=lambda *a,**k:None):
  actions=[]
  ui=S(frame=lambda:'field',adapter=S(exit_sleep_mode=lambda *a:None),context=object(),inputs=object(),key=lambda k:actions.append(k),click=lambda *a:actions.append('tab'),wait=wait,service=S(button=button,detector=S(find=lambda *a,**k:True)))
  return ui,actions
 def test_delayed_J_screen_does_not_click_or_toggle_again(self):
  calls=[]
  def wait(pred,*a):
   calls.append(1)
   if len(calls)==1:raise Pending('transition')
   self.assertTrue(pred('quest'));return 'quest'
  def button(*a,**k):raise AssertionError('late-open mission must not receive menu input')
  ui,actions=self.ui(wait,button)
  with patch('owner_mission_ui.quest_screen',side_effect=lambda f:f=='quest'):MissionUI.open(ui,'sub_quest')
  self.assertEqual(actions,[0x4a,'tab']);self.assertEqual(ui.opened,'quest')
 def test_missing_native_button_is_rechecked_by_existing_pending_policy(self):
  replies=iter([Pending('transition'),'field'])
  def wait(*a):
   v=next(replies)
   if isinstance(v,BaseException):raise v
   return v
  def button(*a,**k):raise RuntimeError('버튼 미감지: 버튼_전체매뉴')
  ui,actions=self.ui(wait,button)
  with patch('owner_mission_ui.quest_screen',return_value=False),self.assertRaises(Pending):MissionUI.open(ui,'sub_quest')
  self.assertEqual(actions,[0x4a])
 def test_other_runtime_errors_and_cancellation_are_not_hidden(self):
  def wait(*a):raise Pending('transition')
  ui,_=self.ui(wait)
  with patch('owner_mission_ui.quest_screen',return_value=False),self.assertRaises(Pending):MissionUI.open(ui,'sub_quest')
  class Cancelled(BaseException):pass
  ui,_=self.ui(lambda *a:(_ for _ in ()).throw(Cancelled()))
  with patch('owner_mission_ui.quest_screen',return_value=False),self.assertRaises(Cancelled):MissionUI.open(ui,'sub_quest')

if __name__=='__main__':unittest.main()
