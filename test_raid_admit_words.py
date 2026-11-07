"""매칭 입장 popup by its words at 1366x768. Fake frames and fake reads; not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
import numpy as np
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_real_marks as m
import owner_image_scope as scope

TITLE={'text':'매칭 입장','x':448,'y':139,'rx':682,'ry':223}
OK={'text':'확인','x':511,'y':330,'rx':778,'ry':529}
NO={'text':'취소','x':381,'y':330,'rx':580,'ry':529}


def reads(title,buttons):
    def read(root,frame,box,**kw):return title if box==m.RAID_ADMIT_TITLE else buttons
    return read


class RaidAdmit(unittest.TestCase):
    def frame(self):return S(hi=np.zeros((768,1366,3),np.uint8),layout=None)
    def run_with(self,title,buttons,fn):
        with patch('owner_text.read',side_effect=reads(title,buttons)),\
             patch('owner_text.logical_bounds',side_effect=lambda r,f:(r['x']-5,r['y']-5,r['x']+5,r['y']+5)):
            return fn(self.frame())
    def test_confirm_is_the_ok_word(self):
        self.assertEqual(self.run_with([TITLE],[NO,OK],m.raid_admit_confirm),(511,330,(506,325,516,335)))
    def test_title_answers(self):
        self.assertEqual(self.run_with([TITLE],[NO,OK],m.raid_admit_title)[:2],(448,139))
    def test_cancel_alone_is_never_taken(self):
        self.assertIsNone(self.run_with([TITLE],[NO],m.raid_admit_confirm))
    def test_without_title_nothing(self):
        self.assertIsNone(self.run_with([{'text':'레이드','x':1,'y':1}],[NO,OK],m.raid_admit_confirm))
        self.assertIsNone(self.run_with([],[NO,OK],m.raid_admit_title))
    def test_old_frame_reads_nothing(self):
        with patch('owner_text.read',side_effect=AssertionError('no read')):
            self.assertIsNone(m.raid_admit_confirm(S()))
    def test_wired_as_real_words(self):
        self.assertEqual(scope.REAL_WORDS['체크_레이드_매칭입장'],'raid_admit_title')
        self.assertEqual(scope.REAL_WORDS['버튼_레이드_매칭입장확인'],'raid_admit_confirm')


class Matching(unittest.TestCase):
    def run_with(self,rows):
        with patch('owner_text.read',return_value=rows),             patch('owner_text.logical_bounds',return_value=(1,2,3,4)):
            return m.raid_matching(S(hi=np.zeros((768,1366,3),np.uint8),layout=None))
    def test_queue_panel_answers(self):
        rows=[{'text':'산신마루','x':790,'y':57},{'text':'레이드','x':791,'y':77},{'text':'대기시간00:05경과','x':791,'y':115}]
        self.assertEqual(self.run_with(rows),(791,115,(1,2,3,4)))
    def test_other_panel_is_not_the_queue(self):
        self.assertIsNone(self.run_with([{'text':'레이드','x':1,'y':1}]))
        self.assertIsNone(self.run_with([{'text':'대기시간00:05경과','x':1,'y':1}]))


class RaidFind(unittest.TestCase):
    """The raid's own find falls back to the words only for its queue, popup and 확인."""
    def setUp(self):
        import project_adapter.boss_raid as raid
        import owner_raid_tickets as t
        self.raid,self.t=raid,t
    def test_words_after_the_picture_misses(self):
        f=S(hi=np.zeros((768,1366,3),np.uint8))
        with patch('owner_real_marks.raid_admit_confirm',return_value=(511,330,(1,2,3,4))):
            self.assertEqual(self.t.word_find(self.raid,self.raid.CONFIRM,f),(511,330,(1,2,3,4)))
        with patch('owner_real_marks.raid_matching',return_value=(791,115,(1,2,3,4))):
            self.assertEqual(self.t.word_find(self.raid,self.raid.MATCHING,f)[:2],(791,115))
    def test_other_names_and_old_frames_read_nothing(self):
        with patch('owner_text.read',side_effect=AssertionError('no read')):
            self.assertIsNone(self.t.word_find(self.raid,self.raid.MATCH,S(hi=np.zeros((2,2,3),np.uint8))))
            self.assertIsNone(self.t.word_find(self.raid,self.raid.CONFIRM,S()))
    def test_a_failed_read_is_a_miss(self):
        with patch('owner_real_marks.raid_admit_title',side_effect=RuntimeError('ocr')):
            self.assertIsNone(self.t.word_find(self.raid,self.raid.ADMIT,S(hi=np.zeros((2,2,3),np.uint8))))


class LateAdmit(unittest.TestCase):
    def flow(self,frames):
        clicks=[];waits=[]
        ctx=S(checkpoint=lambda:None,wait=lambda s:waits.append(s))
        f=S(context=ctx,service=S(capture=lambda:frames.pop(0) if frames else None),click=lambda n,h:clicks.append((n,h)))
        return f,clicks
    def test_popup_that_shows_late_is_confirmed_once(self):
        import project_adapter.boss_raid as raid,owner_raid_tickets as t
        f,clicks=self.flow(['a','b','c'])
        with patch.object(t,'word_find',side_effect=[None,None,(511,330,(1,2,3,4))]):
            self.assertTrue(t.admit_late(f,raid,1))
        self.assertEqual(clicks,[(raid.CONFIRM,(511,330,(1,2,3,4)))])
    def test_no_popup_gives_up(self):
        import project_adapter.boss_raid as raid,owner_raid_tickets as t
        f,clicks=self.flow([])
        with patch.object(t,'word_find',return_value=None),patch.object(t,'ADMIT_LATE',0.05):
            self.assertFalse(t.admit_late(f,raid,1))
        self.assertEqual(clicks,[])

    def test_native_press_miss_falls_to_the_late_look(self):
        import project_adapter.boss_raid as raid,owner_raid_tickets as t
        t.install()
        f=raid.RaidFlow.__new__(raid.RaidFlow);clicks=[]
        f.context=S(checkpoint=lambda:None,wait=lambda s:None);f.service=S(capture=lambda:'F')
        f.detect=lambda *a,**k:None;f.click=lambda n,h:clicks.append(n);f._owner_bulk=True
        with patch.object(t,'word_find',return_value=(511,330,(1,2,3,4))):
            self.assertIsNone(raid.RaidFlow.press(f,raid.CONFIRM,3,1,alternatives=(raid.CONFIRM2,)))
        self.assertEqual(clicks,[raid.CONFIRM])
        with patch.object(t,'word_find',return_value=None),patch.object(t,'ADMIT_LATE',0.05):
            with self.assertRaises(raid.RaidPending):raid.RaidFlow.press(f,raid.CONFIRM,3,1)
        with patch.object(t,'admit_late',side_effect=AssertionError('only confirms')):
            with self.assertRaises(raid.RaidPending):raid.RaidFlow.press(f,raid.MATCH,3,1)


if __name__=='__main__':unittest.main()
