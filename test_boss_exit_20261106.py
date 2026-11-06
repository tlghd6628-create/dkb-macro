"""Field boss exit by words. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_boss_exit as e


class Exit(unittest.TestCase):
    def test_exit_then_confirm(self):
        clicks=[];reads={e.EXIT_WORD:[dict(word='나가기',rx=35,ry=163)],e.QUESTION:[dict(word='필드보스지역에서퇴장하시겠습니까?',rx=683,ry=375)],e.CONFIRM:[dict(word='확인',rx=765,ry=444)]}
        service=NS(capture=lambda:NS(hi=1),click_hit=lambda hit:clicks.append(hit[:2]))
        with patch.object(e,'words',side_effect=lambda f,box:reads[box]):
            self.assertTrue(e.press_exit(service,NS(wait=lambda s:None)))
        self.assertEqual(len(clicks),2)
    def test_no_question_no_confirm(self):
        clicks=[];reads={e.EXIT_WORD:[dict(word='나가기',rx=35,ry=163)],e.QUESTION:[],e.CONFIRM:[dict(word='확인',rx=765,ry=444)]}
        service=NS(capture=lambda:NS(hi=1),click_hit=lambda hit:clicks.append(hit[:2]))
        with patch.object(e,'words',side_effect=lambda f,box:reads[box]):
            self.assertFalse(e.press_exit(service,NS(wait=lambda s:None)))
        self.assertEqual(len(clicks),1)
    def test_waits_pass_through_and_try_only_after_ninety_seconds(self):
        waited=[];tries=[]
        context=NS(wait=lambda s:waited.append(s),stop='x')
        with patch.object(e,'press_exit',side_effect=lambda s,c:tries.append(1)),patch.object(e.time,'monotonic',side_effect=[0,10,95,100,111]):
            leaving=e.Leaving(context,None)
            leaving.wait(1);leaving.wait(1);leaving.wait(1);leaving.wait(1)
        self.assertEqual(waited,[1,1,1,1]);self.assertEqual(tries,[1,1]);self.assertEqual(leaving.stop,'x')


if __name__=='__main__':unittest.main()
