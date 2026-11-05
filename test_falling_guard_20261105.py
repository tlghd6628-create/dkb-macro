"""Falling battle stop after repeated deaths, with fakes only. Never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,logging,tempfile,unittest
from types import SimpleNamespace as S
import owner_falling_guard as fg


class Stop(Exception):pass


def flow_class():
 class Flow:
  entries=0
  def __init__(self,adapter):self.adapter=adapter
  def enter(self):
   Flow.entries+=1;return 'entered'
 return Flow


class Count(unittest.TestCase):
 def test_deaths_soon_after_entering_add_up(self):
  now=[0.];d=fg.Deaths(lambda:now[0])
  for _ in range(3):
   d.entering();now[0]+=60;d.died()
  self.assertEqual(d.count,3)
 def test_surviving_starts_over(self):
  now=[0.];d=fg.Deaths(lambda:now[0])
  d.entering();now[0]+=60;d.died();d.entering();now[0]+=fg.SURVIVED;d.died()
  self.assertEqual(d.count,1)
 def test_the_log_line_counts(self):
  d=fg.Deaths();counter=fg.Counter(d)
  counter.filter(logging.LogRecord('x',20,'',0,'낙화 사망 확인 · 1/20회',None,None))
  counter.filter(logging.LogRecord('x',20,'',0,'물약구매 시작',None,None))
  self.assertEqual(d.count,1)


class Enter(unittest.TestCase):
 def setUp(self):
  self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup);root=Path(self.dir.name);(root/'settings').mkdir()
  self.deaths=fg.Deaths();self.cls=flow_class();self.day=['2026-11-05']
  fg.guard(self.cls,Stop,self.deaths,day=lambda:self.day[0])
  self.flow=self.cls(S(project=S(root=root),values={fg.LIMIT_KEY:'2회'}))
 def test_enters_until_the_limit_then_stops_for_the_day(self):
  self.assertEqual(self.flow.enter(),'entered')
  self.deaths.count=2
  with self.assertRaises(Stop):self.flow.enter()
  self.assertEqual(self.cls.entries,1)
  # A later try the same day, with the count already cleared, is still refused.
  with self.assertRaises(Stop):self.flow.enter()
  self.assertEqual(self.cls.entries,1)
 def test_next_game_day_enters_again(self):
  self.deaths.count=2
  with self.assertRaises(Stop):self.flow.enter()
  self.day[0]='2026-11-06'
  self.assertEqual(self.flow.enter(),'entered')


class Limit(unittest.TestCase):
 def test_values(self):
  self.assertEqual(fg.limit_of({fg.LIMIT_KEY:'5회'}),5);self.assertEqual(fg.limit_of({}),3);self.assertEqual(fg.limit_of({fg.LIMIT_KEY:'x'}),3)
 def test_field_goes_under_the_switch(self):
  count={'id':'auto_schedule.boss_raid.entry_count','type':'combo','choices':[],'capability':'raid'}
  schema={'tabs':[{'groups':[{'fields':[{'id':fg.SWITCH,'capability':'fall'},{'id':'other'},count]}]}]}
  fg.add_fields(schema);fg.add_fields(schema)
  ids=[f['id'] for f in schema['tabs'][0]['groups'][0]['fields']]
  self.assertEqual(ids[:3],[fg.SWITCH,fg.LIMIT_KEY,'other']);self.assertEqual(ids.count(fg.LIMIT_KEY),1)


if __name__=='__main__':unittest.main()
