"""The 1366 감정표현 quest step. Fake words and inputs, and pc1's saved screens where kept; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import os,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_emote_real as e
import owner_hd as hd

TITLE='[5장] 반가운 재회'


def row(word,rx,ry):return dict(text=word,word=word,rx=rx,ry=ry)


class Requirement(unittest.TestCase):
    def run_it(self,rows):
        with patch.object(e,'words',return_value=rows):return e.requirement(NS(hi=1),TITLE)
    def test_the_emote_under_this_quest(self):
        need=self.run_it([row('비경탐험',1180,90),row('![5장]반가운재회',1168,153),row('감정표현중웃음사용하기',1200,184)])
        self.assertEqual((need[0],need[1]['ry']),('웃음',153))
    def test_another_quest_or_no_name_is_not_taken(self):
        self.assertIsNone(self.run_it([row('[6장]다른임무',1168,153),row('감정표현중웃음사용하기',1200,184)]))
        self.assertIsNone(self.run_it([row('[5장]반가운재회',1168,153),row('지정위치에서채팅-감정표현중',1200,184)]))
        self.assertIsNone(self.run_it([row('[5장]반가운재회',1168,153),row('몬스터처치',1200,184)]))


class Tracker(unittest.TestCase):
    def test_the_row_of_each_mode(self):
        rows=[row('비경탐험',1180,90),row('![5장]반가운재회',1168,153),row('감정표현중',1200,184),row('[외전]돌아오지않은약초꾼',1170,247)]
        with patch.object(e,'words',return_value=rows):
            self.assertEqual(e.tracker_title(NS(hi=1),'main_quest')['ry'],153);self.assertEqual(e.tracker_title(NS(hi=1),'sub_quest')['ry'],247)
        with patch.object(e,'words',return_value=rows[:1]):self.assertIsNone(e.tracker_title(NS(hi=1),'main_quest'))
    def test_only_the_selected_quest_row(self):
        rows=[row('①[첫걸음]도술구매',1170,153),row('①[외전]메마른늪의여흘1',1170,247)]
        with patch.object(e,'words',return_value=rows):
            self.assertEqual(e.tracker_title(NS(hi=1),'sub_quest','[첫걸음] 도술 구매')['ry'],153)
            self.assertIsNone(e.tracker_title(NS(hi=1),'sub_quest','[외전] 호랑이의 영혼'))


class Run(unittest.TestCase):
    def setUp(self):
        self.clicks=[];self.state=dict(chat=False,panel=False)
        def click_hit(hit):
            self.clicks.append(hit[:2])
            if hit[:2]==hd.real_hit(*e.CHAT_PREVIEW)[:2]:self.state['chat']=True
            if hit[:2]==hd.real_hit(*e.FACE_BUTTON)[:2]:self.state['panel']=True
        self.ui=NS(frame=lambda:NS(hi=np.zeros((768,1366,3),np.uint8)),context=NS(wait=lambda s:None,checkpoint=lambda:None),
                   service=NS(click_hit=click_hit),adapter=NS(project=NS(root='x')))
        self.book=NS(item={'quests':{'k':{'title':TITLE}}})
        self.reserved=[]
    def run_it(self,cards,remaining=0.):
        rate=NS(remaining=lambda:remaining,reserve=lambda key,target:self.reserved.append((key,target)))
        needs=iter([('웃음',row('[5장]반가운재회',1168,153)),None])
        with patch.object(e,'requirement',side_effect=lambda f,t:next(needs)),patch.object(e,'settle',return_value=True),\
             patch.object(e,'chat_open',side_effect=lambda f:self.state['chat']),patch.object(e,'panel_open',side_effect=lambda f:self.state['panel']),\
             patch.object(e,'words',return_value=cards),patch.object(e,'close_all',return_value=True),\
             patch('owner_emote_cooldown.Rate',lambda *a:rate),patch('owner_progression.state',return_value=NS(character='c')),\
             patch('owner_hunt_rules_candidate.configured_identity',return_value='s'):
            return e.run(self.ui,self.book,'k')
    def test_walk_then_chat_then_face_then_the_card(self):
        self.assertTrue(self.run_it([row('웃음',449,594),row('부끄',542,593)]))
        self.assertEqual(self.clicks,[hd.real_hit(1168,153)[:2],hd.real_hit(*e.CHAT_PREVIEW)[:2],hd.real_hit(*e.FACE_BUTTON)[:2],
                                      hd.real_hit(449,594-e.CARD_ABOVE_WORD)[:2]])
        self.assertEqual(self.reserved,[('k','웃음')])
    def test_a_card_lower_down_is_scrolled_to(self):
        seen=iter([[row('웃음',449,594)],[row('웃음',449,560)],[row('화남',448,670)]])
        wheels=[];self.ui.wheel=lambda *a,**k:wheels.append(a)
        rate=NS(remaining=lambda:0.,reserve=lambda key,target:self.reserved.append((key,target)))
        needs=iter([('화남',row('[외전]항아리를옮긴자8',1168,153)),None])
        with patch.object(e,'requirement',side_effect=lambda f,t:next(needs)),patch.object(e,'settle',return_value=True),             patch.object(e,'chat_open',side_effect=lambda f:self.state['chat']),patch.object(e,'panel_open',side_effect=lambda f:self.state['panel']),             patch.object(e,'words',side_effect=lambda f,box,*a:next(seen)),patch.object(e,'close_all',return_value=True),             patch('owner_emote_cooldown.Rate',lambda *a:rate),patch('owner_progression.state',return_value=NS(character='c')),             patch('owner_hunt_rules_candidate.configured_identity',return_value='s'):
            self.assertTrue(e.run(self.ui,self.book,'k'))
        self.assertEqual(len(wheels),2);self.assertEqual(self.reserved,[('k','화남')])
    def test_no_card_presses_nothing_and_spends_no_attempt(self):
        self.assertFalse(self.run_it([row('부끄',542,593)]));self.assertEqual(self.reserved,[])
    def test_within_the_minute_waits(self):
        self.assertFalse(self.run_it([row('웃음',449,594)],remaining=30.));self.assertEqual(self.clicks,[])


class Saved(unittest.TestCase):
    """pc1 11-06 13:40 frames, kept out of the repository: DKB_EMOTE_FRAMES names their folder."""
    def frame(self,name):
        folder=os.environ.get('DKB_EMOTE_FRAMES')
        if not folder or not Path(folder,name+'.png').exists():self.skipTest('local frames only')
        from PIL import Image
        return NS(hi=np.asarray(Image.open(Path(folder,name+'.png')).convert('RGB')))
    def test_tracker_chat_and_panel(self):
        f=self.frame('r_trk');need=e.requirement(f,TITLE);self.assertEqual(need[0],'웃음');self.assertEqual(round(need[1]['ry']),153)
        f=self.frame('r_c7');self.assertTrue(e.chat_open(f));self.assertTrue(e.panel_open(f))
        f=self.frame('r_emo2');self.assertFalse(e.chat_open(f));self.assertFalse(e.panel_open(f))


if __name__=='__main__':unittest.main()
