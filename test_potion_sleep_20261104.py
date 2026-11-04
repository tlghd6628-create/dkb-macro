"""Native orchestrator and saved real frames with fake action bodies. No game input."""
import inspect,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
from PIL import Image
from unittest.mock import Mock,patch
from types import SimpleNamespace as S
from test_challenge_test_20261104 import context,real
import owner_membership as member
import owner_image_scope as scope
from roi_runtime import RoiDetector

HERE=Path(__file__).resolve().parent
PROFILE=bootstrap.A/'profiles/DKB'
BUTTON='버튼_절전모드바로진입'
def frame(name):return np.array(Image.open(HERE/'fixtures_image_scope'/name).convert('RGB'))

class Potion(unittest.TestCase):
    def native(self,**values):
        order=[];adapter=real(values,order=order);ran=[];adapter.mode='auto_mode'
        with patch.object(member,'paid',return_value=True):
            member.without_potion_town(inspect.unwrap(type(adapter)._run_auto_features),adapter,context(ran),Mock())
        return order,ran
    def test_real_native_start_buys_without_town(self):
        order,ran=self.native(**{'common.potion_and_favorite.enabled':True})
        self.assertNotIn('run_town_return',order)
        self.assertEqual([n for n in order if n in ('run_potion_purchase','run_favorite_hunt')],['run_potion_purchase','run_favorite_hunt'])
        self.assertNotIn('common.run_town_return',ran);self.assertIn('common.potion.purchase',ran)
    def test_non_member_keeps_both_trips(self):
        order=[];adapter=real({'common.potion_and_favorite.enabled':True},order=order);adapter.mode='auto_mode'
        with patch.object(member,'paid',return_value=False):
            member.without_potion_town(inspect.unwrap(type(adapter)._run_auto_features),adapter,context([]),Mock())
        self.assertEqual(order.count('run_town_return'),2)
    def test_a_job_that_may_need_town_gets_the_held_trip_first(self):
        calls=[];ctx=context(calls);home=Mock(return_value=True);adapter=S(project=S(root='x'),run_potion_purchase=Mock())
        def native(a,c,i):
            c.run_action('common.run_town_return',home);home.assert_not_called()
            c.run_action('auto_rewards.market_inventory',lambda:None)
        with patch.object(member,'paid',return_value=True):member.without_potion_town(native,adapter,ctx,None)
        home.assert_called_once();self.assertEqual(calls,['common.run_town_return','auto_rewards.market_inventory'])
    def test_action_is_restored_after_an_error(self):
        ctx=context();original=ctx.run_action
        def native(*a):raise RuntimeError('fixture')
        with patch.object(member,'paid',return_value=True),self.assertRaisesRegex(RuntimeError,'fixture'):
            member.without_potion_town(native,S(project=S(root='x')),ctx,None)
        self.assertIs(ctx.run_action,original)

class Sleep(unittest.TestCase):
    def test_button_found_on_the_real_field(self):
        made=scope.glyph_hit(BUTTON,frame('hunt_field.png'),None)
        self.assertIsNotNone(made);self.assertLess(abs(made[0]-707),3);self.assertLess(abs(made[1]-448),3)
    def test_button_absent_on_the_sleep_screen(self):
        self.assertIsNone(scope.glyph_hit(BUTTON,frame('sleep_screen.png'),None))
    def test_candidate_filter_can_refuse(self):
        self.assertIsNone(scope.glyph_hit(BUTTON,frame('hunt_field.png'),lambda f,m:False))
    def test_the_real_failed_resume_frame_names_the_sleep_screen(self):
        d=RoiDetector(PROFILE,['체크_절전모드중'])
        self.assertTrue(d.find('체크_절전모드중',frame('sleep_screen.png'),threshold=.95))
        self.assertFalse(d.find('체크_절전모드중',frame('hunt_field.png'),threshold=.95))

if __name__=='__main__':unittest.main()
