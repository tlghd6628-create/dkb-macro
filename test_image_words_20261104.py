"""The printed-word finder and the change record. Real saved pages with a stubbed reader; no input."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import json,tempfile,unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
import owner_image_scope as scope

F=Path(__file__).resolve().parent/'fixtures_image_scope'
def load(name):return np.array(Image.open(F/(name+'.png')).convert('RGB'))
PROFILE=bootstrap.A/'profiles/DKB'
DAILY='버튼_임무_일일탭'
def word(text,score=.95,box=(218,44,243,61)):return {'text':text,'score':score,'box':box}

class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=RoiDetector(PROFILE,list(scope.WORDS));cls.mission=load('words_mission');cls.plain=load('plain_new')
    def setUp(self):
        scope.LOCAL.words={};scope.note.__dict__.pop('seen',None)
        patcher=patch.object(scope,'note');self.note=patcher.start();self.addCleanup(patcher.stop)
    def find(self,rows,name=DAILY,frame=None,threshold=.9,flt=None):
        with patch.object(scope,'_read_words',return_value=rows) as read:
            hit=scope.word_hit(self.d,name,self.mission if frame is None else frame,threshold,flt)
        return hit,read

class Finding(Base):
    def test_the_word_inside_its_window_is_found(self):
        hit,_=self.find([word('일일')]);self.assertEqual(hit,(230,52,(218,44,243,61)))
        self.note.assert_called_once()
    def test_no_window_means_no_read_at_all(self):
        hit,read=self.find([word('일일')],frame=self.plain)
        self.assertIsNone(hit);read.assert_not_called()
    def test_a_weak_read_is_refused(self):
        self.assertIsNone(self.find([word('일일',.79)])[0])
    def test_two_of_the_same_word_are_refused(self):
        self.assertIsNone(self.find([word('일일'),word('일일',box=(300,44,330,61))])[0])
    def test_a_misread_word_is_refused(self):
        self.assertIsNone(self.find([word('일입')])[0])
    def test_a_box_outside_the_zone_is_refused(self):
        self.assertIsNone(self.find([word('일일',box=(800,400,840,430))])[0])
    def test_the_caller_filter_still_decides(self):
        self.assertIsNone(self.find([word('일일')],flt=lambda frame,hit:False)[0])
    def test_a_strict_caller_is_left_alone(self):
        hit,read=self.find([word('일일')],threshold=.99)
        self.assertIsNone(hit);read.assert_not_called()
    def test_an_unlisted_button_is_never_read(self):
        d=RoiDetector(PROFILE,['버튼_가호_소환탭'])
        with patch.object(scope,'_read_words') as read:
            self.assertIsNone(scope.word_hit(d,'버튼_가호_소환탭',self.mission,.9,None))
        read.assert_not_called()

class Misreads(Base):
    def test_a_known_misread_counts_as_its_word(self):
        d=RoiDetector(PROFILE,['버튼_임무_전래동화탭'])
        with patch.object(scope,'_read_words',return_value=[word('전래등화',.97,(378,45,420,61))]):
            self.assertIsNotNone(scope.word_hit(d,'버튼_임무_전래동화탭',self.mission,.9,None))
    def test_a_misread_of_another_word_does_not(self):
        self.assertIsNone(self.find([word('전래등화',.97)])[0])
    def test_it_cannot_create_a_duplicate_pass(self):
        d=RoiDetector(PROFILE,['버튼_임무_전래동화탭'])
        rows=[word('전래등화',.97,(378,45,420,61)),word('전래동화',.97,(300,45,340,61))]
        with patch.object(scope,'_read_words',return_value=rows):
            self.assertIsNone(scope.word_hit(d,'버튼_임무_전래동화탭',self.mission,.9,None))

class RaidAdmit(unittest.TestCase):
    """The real match-entry window after the patch made it taller."""
    NAMES=('체크_레이드_매칭입장','버튼_레이드_매칭입장확인','버튼_레이드_일괄소모','버튼_레이드_일괄소모2')
    @classmethod
    def setUpClass(cls):
        scope.install()
        cls.d=RoiDetector(PROFILE,list(cls.NAMES));cls.window=load('raid_admit');cls.plain=load('plain_new');cls.mission=load('words_mission')
    def test_each_moved_image_is_found_on_the_real_window(self):
        for name,spot in zip(self.NAMES,((425,132),(498,325),(526,268),(526,268))):
            self.assertEqual(self.d.find(name,self.window,threshold=.95)[2][:2],spot,name)
    def test_nothing_spends_without_the_window(self):
        for frame in (self.plain,self.mission):
            for name in self.NAMES:self.assertIsNone(self.d.find(name,frame,threshold=.9),name)
    def test_they_stay_in_the_spending_list(self):
        for name in ('체크_레이드_매칭입장','버튼_레이드_매칭입장확인'):self.assertTrue(scope.committed(name))

class RaidEntered(unittest.TestCase):
    """A real raid after the patch: the native mark scored .82, so AUTO was never pressed."""
    @classmethod
    def setUpClass(cls):
        scope.install();cls.d=RoiDetector(PROFILE,['체크_레이드진입'])
    def test_found_inside_the_raid(self):
        self.assertIsNotNone(self.d.find('체크_레이드진입',load('raid_inside'),threshold=.95))
    def test_not_found_on_the_entry_window_or_the_field(self):
        for name in ('raid_admit','plain_new','words_mission','hunt_field'):
            self.assertIsNone(self.d.find('체크_레이드진입',load(name),threshold=.95),name)

class Table(unittest.TestCase):
    def test_nothing_that_spends_is_listed(self):
        for name in scope.WORDS:self.assertFalse(scope.committed(name),name)
    def test_state_buttons_are_not_listed(self):
        for name in ('버튼_우편탭_모두받기','버튼_보스_필드보스탭','버튼_길라잡이_보상받기','버튼_문파_활동보상'):
            self.assertNotIn(name,scope.WORDS)
    def test_every_entry_belongs_to_a_known_window(self):
        for name,(text,key,zone) in scope.WORDS.items():self.assertIn(key,scope.WINDOWS,name)

class Polling(Base):
    def test_unchanged_pixels_reuse_the_read(self):
        with patch.object(scope,'_read_words',return_value=[word('일일')]) as read:
            for _ in range(5):self.assertIsNotNone(scope.word_hit(self.d,DAILY,self.mission,.9,None))
        self.assertEqual(read.call_count,1)
    def test_changing_pixels_cannot_read_more_than_the_limit(self):
        clock=[100.0]
        def changed(n):
            frame=self.mission.copy();frame[50,230,0]=n;return frame
        with patch.object(scope,'_read_words',return_value=[word('일일')]) as read,patch.object(scope.time,'monotonic',lambda:clock[0]):
            for n in range(5):scope.word_hit(self.d,DAILY,changed(n),.9,None)
            self.assertEqual(read.call_count,1)
            clock[0]+=scope.WORD_EVERY
            scope.word_hit(self.d,DAILY,changed(9),.9,None)
            self.assertEqual(read.call_count,2)
    def test_a_reader_failure_is_a_plain_miss(self):
        with patch.object(scope,'_read_words',side_effect=RuntimeError('x')):
            self.assertIsNone(scope.word_hit(self.d,DAILY,self.mission,.9,None))

class Record(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
        self.path=Path(self.dir.name)/'logs/image-health.json';self.path.parent.mkdir()
        scope.note.__dict__.pop('seen',None)
        patcher=patch.object(scope,'_health_path',lambda:self.path);patcher.start();self.addCleanup(patcher.stop)
    def test_a_new_button_is_written_once_a_day(self):
        with patch('pathlib.Path.replace',autospec=True,side_effect=Path.replace) as replace:
            for _ in range(5):scope.note('p','버튼_우편','moved')
        self.assertEqual(replace.call_count,1)
        day=next(iter(json.loads(self.path.read_text(encoding='utf-8')).values()))
        self.assertEqual(day,{'moved':['버튼_우편']})
    def test_no_program_folder_writes_nothing(self):
        gone=Path(self.dir.name)/'absent/logs/image-health.json'
        with patch.object(scope,'_health_path',lambda:gone):scope.note('p','버튼_우편','moved')
        self.assertFalse(gone.exists())
    def test_old_days_fall_off(self):
        self.path.write_text(json.dumps({'2020-01-%02d'%n:{} for n in range(1,21)}),encoding='utf-8')
        scope.note('p','버튼_우편','moved')
        self.assertEqual(len(json.loads(self.path.read_text(encoding='utf-8'))),scope.HEALTH_DAYS)
    def test_summary_names_what_could_not_be_found(self):
        self.path.write_text(json.dumps({'2026-11-04':{'moved':['a','b'],'word':['c'],'drift':['버튼_우편']}}),encoding='utf-8')
        line=scope.health_summary(self.path)
        self.assertIn('위치 보정 2개',line);self.assertIn('글자 보정 1개',line);self.assertIn('못 찾음 1개',line);self.assertIn('버튼_우편',line)
    def test_summary_is_silent_when_nothing_changed(self):
        self.path.write_text('{}',encoding='utf-8');self.assertIsNone(scope.health_summary(self.path))
        self.assertIsNone(scope.health_summary(Path(self.dir.name)/'absent.json'))
    def test_a_damaged_file_is_not_fatal(self):
        self.path.write_text('not json',encoding='utf-8');self.assertIsNone(scope.health_summary(self.path))
        scope.note('p','버튼_우편','moved')

if __name__=='__main__':unittest.main()
