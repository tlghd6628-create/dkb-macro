"""단 봉인해제 and 단각 교환. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_seal_shop as s


def row(word,x,y):return dict(word=word,text=word,rx=x,ry=y)


class Settings(unittest.TestCase):
    def test_defaults_list_every_item_unchecked(self):
        with tempfile.TemporaryDirectory() as root:
            store=s.SealShopStore(root,'홍짱군');document,_=store.snapshot()
            self.assertEqual(len(document['items']),26);self.assertFalse(any(r['enabled'] for r in document['items']))
            rows=document['items'];rows[0]['enabled']=True;rows[0].update(mode='quantity',quantity=5)
            store.write(rows,enabled=True)
            again=store.read_document()
            self.assertEqual(again['items'][0],{'name':'요혼석','enabled':True,'mode':'quantity','quantity':5})
    def test_a_row_added_to_the_catalogue_shows_up(self):
        with tempfile.TemporaryDirectory() as root:
            store=s.SealShopStore(root,'홍짱군');rows=s.initial_rows()[:3];store.write(rows)
            self.assertEqual(len(store.read_document()['items']),26)
    def test_duplicates_refused(self):
        with self.assertRaises(ValueError):s.validate([dict(name='요혼석',enabled=True,mode='max',quantity=1)]*2)


class Reading(unittest.TestCase):
    def test_counts_under_their_orbs(self):
        rows=[row('정기단',364,611),row('574',364,629),row('영기단',523,611),row('6',523,629),row('천지단',683,611),row('0',683,629)]
        with patch.object(s,'words',return_value=rows):
            self.assertEqual(s.dan_counts(None),{'정기단':(574,364),'영기단':(6,523),'천지단':(0,683)})
    def test_shop_rows_need_name_price_and_limit(self):
        rows=[row('요혼석',101,132),row('10',111,153),row('도사일일한정:(0/100)',140,173),
              row('엽전',94,280),row('0',90,301),row('10',112,301),row('TOK',58,318),row('도사일일한정(0/100)',142,321),row('가호주머니',101,676),row('50',111,697),row('도사주간한정:(7/10)',140,717),
              row('여명의정수',105,428)]
        with patch.object(s,'words',return_value=rows):found=s.shop_rows(None)
        self.assertEqual(found['요혼석'],dict(ry=132,price=10,period='일일',used=0,limit=100))
        self.assertEqual(found['가호주머니'],dict(ry=676,price=50,period='주간',used=7,limit=10))
        self.assertEqual(found['엽전'],dict(ry=280,price=10,period='일일',used=0,limit=100))
        self.assertNotIn('여명의정수',found)
    def test_balance_is_the_first_number(self):
        with patch.object(s,'words',return_value=[row('1,487',740,28),row('20',623,28)]):self.assertEqual(s.balance(None),20)
    def test_skip_box_tick(self):
        hi=np.zeros((768,1366,3),np.uint8);x,y,w,h=s.SKIP_BOX
        self.assertFalse(s.skip_ticked(NS(hi=hi)))
        hi[y+8:y+11,x+7:x+10]=170;self.assertFalse(s.skip_ticked(NS(hi=hi)))
        hi[y+6:y+16,x+6:x+10]=170;self.assertTrue(s.skip_ticked(NS(hi=hi)))


class Unseal(unittest.TestCase):
    """pc2 홍짱군 08:27: the box held 6 with 492 정기단, one pass of 6 and stop; the lone 1 under 영기단 unread."""
    def run_it(self,held,unread=()):
        held=dict(held);taps=[];state={'orb':None,'amount':6}
        r=s.Run.__new__(s.Run);r.context=NS(wait=lambda x:None)
        r.tab=lambda box,word:None;r.tick_skip=lambda:True;r.frame=lambda:'f'
        r.counts=lambda name,tries=3:{n:(c,100+i) for i,(n,c) in enumerate(held.items()) if n not in unread}
        def tap(x,y,wait=1.):
            taps.append((x,y))
            if y==s.ORB_Y:state['orb']=[n for i,n in enumerate(held) if 100+i==x][0]
            if (x,y)==s.AMOUNT_MAX:state['amount']=min(held[state['orb']],100);state['armed']=True
            if (x,y)==(700,700) and state.pop('armed',False):held[state['orb']]-=state['amount']
        r.tap=tap
        r.word_at=lambda f,box,want:{'word':want,'rx':700,'ry':700}
        r.until=lambda test,seconds=8.:'f'
        def fake_words(frame,box,minimum=.55):
            return [{'word':str(state['amount']),'rx':0,'ry':0}] if box==s.AMOUNT else []
        with patch.object(s,'words',fake_words),patch.object(s,'dan_heads',lambda f:{n:100+i for i,n in enumerate(held)}):
            return r.unseal(),held
    def test_max_is_pressed_and_every_pass_runs(self):
        done,held=self.run_it({'정기단':492,'영기단':0})
        self.assertEqual(done,{'정기단':492});self.assertEqual(held['정기단'],0)
    def test_an_unread_count_is_taken_from_the_filled_amount(self):
        done,held=self.run_it({'정기단':0,'영기단':1},unread=('영기단',))
        self.assertEqual(done,{'영기단':1})


class Wanted(unittest.TestCase):
    seen=dict(price=10,used=3,limit=10)
    def test_max_is_the_room_and_the_coins(self):
        self.assertEqual(s.wanted(dict(mode='max',quantity=1),self.seen,1000),7)
        self.assertEqual(s.wanted(dict(mode='max',quantity=1),self.seen,45),4)
    def test_a_target_counts_what_was_bought_this_period(self):
        self.assertEqual(s.wanted(dict(mode='quantity',quantity=5),self.seen,1000),2)
        self.assertEqual(s.wanted(dict(mode='quantity',quantity=2),self.seen,1000),0)
        self.assertEqual(s.wanted(dict(mode='max',quantity=1),dict(self.seen,used=10),1000),0)


class Wiring(unittest.TestCase):
    def test_job_at_four(self):
        from owner_timetable import BY_KEY
        job=BY_KEY['seal_release'];self.assertEqual((job.setting,job.clock),(s.KEY,'04:00'))
    def test_test_button_and_page(self):
        from owner_challenge_test import TARGETS,SEAL
        from owner_settings_console import category
        from owner_settings_theme import NAV_GROUPS
        self.assertEqual(TARGETS[s.KEY][1],SEAL);self.assertEqual(category(s.KEY),'단 봉인해제')
        self.assertIn('단 봉인해제',NAV_GROUPS[0][1])
    def test_the_native_pass_only_waits(self):
        import project_adapter.seal_release as native
        original=native.run_seal_release
        try:
            s.install()
            self.assertIs(native.run_seal_release(None,None,None),True)
            self.assertTrue(native.run_seal_release._owner_seal)
        finally:native.run_seal_release=original


if __name__=='__main__':unittest.main()
