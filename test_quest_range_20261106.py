"""A stuck quest loosens the auto-combat range (제자리 off, 30m) before pressing auto-progress again, and a plain quest
line no longer warns as an emote. Fake frames and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch,Mock
import sys,time,unittest,logging
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_mission_controller as mc
import owner_emote_dispatch as emote


class Stuck(unittest.TestCase):
    def ui(self):
        frame=np.zeros((479,897,3),np.uint8)
        calls=[]
        ui=NS(frame=lambda:frame,opened=False,normal=lambda:True,adapter=NS(mode='sub_quest',project=NS(root='r')),context=NS(),inputs=NS(),
              open=lambda mode:calls.append(('open',mode)),start_selected=lambda:calls.append('start'),service=None)
        idle={'crop':frame[18:100,12:95].mean(axis=2),'at':time.monotonic()-mc.IDLE_SECONDS-5}
        return ui,idle,calls
    def run_it(self,record):
        ui,idle,calls=self.ui()
        with patch('owner_start_menu.kind',return_value=None),patch('owner_boss_range.pending',return_value=record),\
             patch('owner_boss_range.loosen',side_effect=lambda *a:calls.append('loosen') or True):
            self.assertTrue(mc.restart_idle_quest(ui,idle))
        return calls
    def test_fixed_at_5m_is_loosened_before_auto_progress(self):
        # pc2 11-06: 0/10 for 7 minutes beside the wrong monster, the stuck press repeating every two minutes.
        self.assertEqual(self.run_it(None),['loosen',('open','sub_quest'),'start'])
    def test_already_loose_is_left_alone(self):
        self.assertEqual(self.run_it({'fixed':True,'range':True}),[('open','sub_quest'),'start'])
    def test_not_stuck_long_enough_does_nothing(self):
        ui,idle,calls=self.ui();idle['at']=time.monotonic()
        with patch('owner_start_menu.kind',return_value=None),patch('owner_boss_range.loosen') as loosen:
            self.assertFalse(mc.restart_idle_quest(ui,idle))
        loosen.assert_not_called();self.assertEqual(calls,[])


class EmoteNoise(unittest.TestCase):
    def read(self,a,b):
        rows=iter((a,b))
        ui=NS(rows=lambda *x,**k:next(rows),context=NS(wait=lambda s:None))
        with self.assertLogs('project_gui.DKB',level='DEBUG') as logs:
            logging.getLogger('project_gui.DKB').debug('start')
            result=emote.read_requirement(ui)
        return result,[line for line in logs.output if '감정 요구 판독 대조' in line]
    def test_a_plain_quest_line_does_not_warn(self):
        a=[{'text':'2전]메마른늪의 여흘3 적합','score':.97}];b=[{'text':'리전]메마른늙의 여흘3 적합','score':.96}]
        result,warned=self.read(a,b)
        self.assertIsNone(result);self.assertEqual(warned,[])
    def test_an_emote_line_that_does_not_settle_still_warns(self):
        a=[{'text':'감정 표현 기쁨','score':.97}];b=[{'text':'감정 표현 기뽐','score':.96}]
        with patch.object(emote,'parse_target',side_effect=lambda rows,**k:rows[0]['text'][-2:] if rows else None):
            result,warned=self.read(a,b)
        self.assertIsNone(result);self.assertEqual(len(warned),1)


if __name__=='__main__':unittest.main()
