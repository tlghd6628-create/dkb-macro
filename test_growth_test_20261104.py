"""Growth TEST wiring with fakes. Checks what reaches which entry, never a game action."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import threading,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_challenge_test as c
from owner_settings_layout import GROWTH_SWITCHES

VALUES={key:False for key in GROWTH_SWITCHES.values()}
VALUES.update({'auto_challenge.secret_exploration.enabled':True,'auto_rewards.mail.enabled':True,'auto_growth.equipment.enabled':False})

class Fake:
    seen={}
    def __init__(self):self.values=dict(VALUES);self.calls=[]
    def get_due_schedules(self):return ['boss']
    def run_album_rewards(self,context,inputs):
        self.calls.append(('album',dict(self.values)));return True
    def _run_auto_features(self,context,inputs,**kwargs):
        self.calls.append(('native',dict(self.values),kwargs,self.get_due_schedules()));return True

class Targets(unittest.TestCase):
    def test_every_growth_switch_has_a_test(self):
        for key in GROWTH_SWITCHES.values():self.assertIn(key,c.TARGETS)
    def test_each_page_opens_only_its_own_switch(self):
        for key in GROWTH_SWITCHES.values():
            shown=c.only(VALUES,key)
            self.assertEqual([k for k,v in shown.items() if v is True and k.endswith('.enabled')],[key])

class Execute(unittest.TestCase):
    def run_key(self,key,**patches):
        adapter=Fake();before=adapter.values
        result=c.execute(adapter,S(),S(),key)
        self.assertIs(adapter.values,before);self.assertEqual(adapter.get_due_schedules(),['boss'])
        return adapter,result
    def test_equipment_uses_the_native_dispatcher_alone(self):
        adapter,_=self.run_key('auto_growth.equipment.enabled')
        name,values,kwargs,due=adapter.calls[0]
        self.assertEqual(name,'native');self.assertTrue(values['auto_growth.equipment.enabled'])
        self.assertFalse(values['auto_challenge.secret_exploration.enabled']);self.assertFalse(values['auto_rewards.mail.enabled'])
        self.assertEqual(kwargs,dict(wait_for_hunt=False,potion_done=True,periodic_wait=False));self.assertEqual(due,[])
    def test_blessing_and_energy_use_it_too(self):
        for key in ('auto_growth.blessing.enabled','auto_growth.energy.enabled'):
            adapter,_=self.run_key(key);self.assertEqual(adapter.calls[0][0],'native');self.assertTrue(adapter.calls[0][1][key])
    def test_album_uses_its_own_entry(self):
        with patch('owner_quest_preflight.read_power') as read:
            adapter,result=self.run_key('auto_rewards.album.enabled')
        read.assert_called_once();self.assertEqual(adapter.calls[0][0],'album');self.assertIs(result,True)
    def test_style_reports_its_real_statuses(self):
        def run(adapter,context,inputs):
            adapter._owner_style_growth_outcome={'state':'processed_unverified','statuses':['파멸 목표 도달','강타 재료 부족']};return True
        with patch('owner_skill_growth_candidate.dispatch_after_native',run):
            adapter,result=self.run_key('auto_growth.taoist.enabled')
        self.assertEqual(adapter.calls,[]);self.assertIn('강타 재료 부족',result)
    def test_style_hold_is_named_not_a_pass(self):
        def run(adapter,context,inputs):
            adapter._owner_style_growth_outcome={'state':'held','reason':'도술 화면 미확인'};return True
        with patch('owner_skill_growth_candidate.dispatch_after_native',run):
            _,result=self.run_key('auto_growth.taoist.enabled')
        self.assertEqual(result,'보류 · 도술 화면 미확인')
    def test_gear_hold_is_named_not_a_pass(self):
        adapter=Fake()
        def native(self,context,inputs,**kwargs):
            self._owner_growth_pending_hold=True;return True
        with patch.object(Fake,'_run_auto_features',native):
            self.assertEqual(c.execute(adapter,S(),S(),'auto_growth.equipment.enabled'),'보류 · 실행 로그 확인')
    def test_settings_restored_after_a_failure(self):
        adapter=Fake();before=adapter.values
        def boom(self,context,inputs,**kwargs):raise RuntimeError('x')
        with patch.object(Fake,'_run_auto_features',boom),self.assertRaises(RuntimeError):
            c.execute(adapter,S(),S(),'auto_growth.equipment.enabled')
        self.assertIs(adapter.values,before);self.assertEqual(adapter.get_due_schedules(),['boss'])

class PairedRows(unittest.TestCase):
    """17:45 real hold: the same number scoring either side of a reader's own bar."""
    def row(self,text,score,x=380,y=130):return {'text':text,'score':score,'x':x,'y':y}
    def match(self,a,b,minimum=.9):
        from owner_skill_ui import paired_rows_match
        return paired_rows_match(a,b,minimum)
    def test_same_text_either_side_of_the_bar_agrees(self):
        self.assertTrue(self.match([self.row('1314',.91)],[self.row('1314',.89)]))
        self.assertTrue(self.match([self.row('1314',.89)],[self.row('1314',.91)]))
    def test_different_text_never_agrees(self):
        self.assertFalse(self.match([self.row('1314',.95)],[self.row('1315',.95)]))
        self.assertFalse(self.match([self.row('1314',.95)],[self.row('1315',.82)]))
    def test_text_that_vanishes_does_not_agree(self):
        self.assertFalse(self.match([self.row('1314',.95)],[]))
        self.assertFalse(self.match([],[self.row('1314',.95)]))
    def test_far_below_the_bar_is_not_the_same_reading(self):
        self.assertFalse(self.match([self.row('1314',.95)],[self.row('1314',.7)]))
    def test_two_weak_rows_are_not_evidence_of_anything(self):
        self.assertTrue(self.match([self.row('1314',.5)],[self.row('9999',.5)]))

class GlidingList(unittest.TestCase):
    """The list keeps moving after a drag: a read that disagrees is read again, spending nothing."""
    def worker(self,batch):
        import numpy as np,owner_skill_growth_candidate as g
        worker=g.StyleGrowth.__new__(g.StyleGrowth)
        worker.guard=lambda:True;worker._guard=lambda:None
        frame=np.zeros((479,897,3),dtype=np.uint8)
        worker.ui=S(rows_batch=batch,frame=lambda:frame,context=S(wait=lambda seconds:None),_owner_last_rows_pair=([frame,frame],[0,0],None))
        return worker,g
    def test_a_disagreeing_pair_is_read_again(self):
        calls=[]
        def batch(specs):
            calls.append(specs)
            if len(calls)<3:raise self.g.Pending('도술 두 화면 판독 불일치: (704, 65, 170, 370)')
            return [[]]
        worker,self.g=self.worker(batch)
        with patch.object(self.g,'tab',lambda frame:True):self.assertEqual(worker._style_rows('파멸'),([],None))
        self.assertEqual(len(calls),3)
    def test_a_list_that_never_agrees_still_holds(self):
        def batch(specs):raise self.g.Pending('도술 두 화면 판독 불일치: (704, 65, 170, 370)')
        worker,self.g=self.worker(batch)
        with self.assertRaises(self.g.Pending):worker._style_rows('파멸')
    def test_another_reason_is_not_retried(self):
        calls=[]
        def batch(specs):
            calls.append(specs);raise self.g.Pending('도술 일괄 판독 응답 확인 필요')
        worker,self.g=self.worker(batch)
        with self.assertRaises(self.g.Pending):worker._style_rows('파멸')
        self.assertEqual(len(calls),1)
    def test_settling_stops_as_soon_as_the_list_is_still(self):
        worker,g=self.worker(None)
        self.assertTrue(worker._settle_list())

class ShimmeringDigit(unittest.TestCase):
    """Two real 파멸 opening pages: the centre 19 shimmers, the rest of the proof stays still."""
    BOUNDS={'list':(734,311,785,335),'current':(366,125,389,149),'next':(396,124,422,149),'ratio':(371,394,417,411),'price':(390,440,438,459)}
    def load(self,name):
        import numpy as np
        from PIL import Image
        return np.array(Image.open(Path(__file__).resolve().parent/'fixtures_image_scope'/(name+'.png')).convert('RGB'))
    def proof(self,frame,label):
        l,t,r,b=self.BOUNDS[label];return (l,t,r-l,b-t),frame[t:b,l:r].copy()
    def test_only_the_current_digit_moves(self):
        import owner_skill_growth_candidate as g
        a,b=self.load('skill_opening_a'),self.load('skill_opening_b')
        for label,mode in (('list','text'),('next','gold'),('ratio','text'),('price','text')):
            box,source=self.proof(a,label);self.assertTrue(g._same_pixels(b,box,source,mode),label)
        box,source=self.proof(a,'current');self.assertFalse(g._same_pixels(b,box,source,'text'))
    def observe(self,level='19',next_digit='20'):
        import time,owner_skill_growth_candidate as g
        a,b=self.load('skill_opening_a'),self.load('skill_opening_b')
        row=lambda text,score,label:{'text':text,'score':score,'x':0,'y':323,'bounds':self.BOUNDS[label]}
        rows=[[row('파멸+'+level,.95,'list')],[row(level,.99,'current')],[row(next_digit,.99,'next')],[row('833/200',.99,'ratio')],[row('600,000',.99,'price')]]
        frames=iter([a,b]*20)
        ui=S(context=S(wait=lambda seconds:None,checkpoint=lambda:None),frame=lambda:next(frames))
        def batch(specs):
            ui._owner_last_rows_pair=([a,b],[time.monotonic()]*2,rows);ui._owner_last_rows_raw=None;return rows
        ui.rows_batch=batch
        worker=g.StyleGrowth.__new__(g.StyleGrowth);worker.ui=ui;worker.guard=lambda:True;worker._guard=lambda:None
        return worker._observation('파멸',opening=True,use_balance=False)
    def test_the_opening_page_passes_with_the_digit_still_read(self):
        obs,proofs=self.observe()
        self.assertEqual(obs['level'],19)
        self.assertNotIn((366,125,23,24),[proof[0] for proof in proofs])
        self.assertIn((396,124,26,25),[proof[0] for proof in proofs])
    def test_a_wrong_next_digit_still_holds(self):
        import owner_skill_growth_candidate as g
        with self.assertRaises(g.Pending):self.observe(next_digit='21')

class Emblem(unittest.TestCase):
    def test_a_confirmed_step_learns_the_emblem_again_from_a_settled_read(self):
        import inspect,owner_skill_growth_candidate as g
        source=inspect.getsource(g.StyleGrowth.run)
        self.assertLess(source.index('bindings.pop(name,None)'),source.index("intents[name].update(status='confirmed'"))
        self.assertGreater(source.index('bindings.pop(name,None)'),source.index('new!=current+1'))
        self.assertNotIn('bind_style_identity',source[source.index('bindings.pop(name,None)'):])

class MidStep(unittest.TestCase):
    """Two real 파멸 pages at 20>>21. The whole transition reads weakly, each digit reads well."""
    BOUNDS={'list':(734,311,785,335),'current':(366,125,389,149),'next':(396,124,422,149),'ratio':(371,394,417,411),'price':(390,440,438,459)}
    def load(self,name):
        import numpy as np
        from PIL import Image
        return np.array(Image.open(Path(__file__).resolve().parent/'fixtures_image_scope'/(name+'.png')).convert('RGB'))
    def observe(self,list_text='파멸+20',list_score=.93,current='20',next_digit='21',next_score=.96):
        import time,owner_skill_growth_candidate as g
        a,b=self.load('skill_midstep_a'),self.load('skill_midstep_b')
        row=lambda text,score,label:{'text':text,'score':score,'x':0,'y':323,'bounds':self.BOUNDS[label]}
        rows=[[row(list_text,list_score,'list')],[row('2021 +',.85,'current')],[row('25/7',.99,'ratio')],[row('140,000',.99,'price')]]
        split=[[row(current,.99,'current')],[row(next_digit,next_score,'next')]]
        frames=iter([a,b]*20)
        ui=S(context=S(wait=lambda seconds:None,checkpoint=lambda:None),frame=lambda:next(frames))
        def batch(specs):
            answer=split if len(specs)==2 else rows
            ui._owner_last_rows_pair=([a,b],[time.monotonic()]*2,answer);ui._owner_last_rows_raw=None;return answer
        ui.rows_batch=batch
        worker=g.StyleGrowth.__new__(g.StyleGrowth);worker.ui=ui;worker.guard=lambda:True;worker._guard=lambda:None
        return worker._observation('파멸',opening=False,use_balance=False),g
    def test_three_separate_reads_agree(self):
        (obs,proofs),_=self.observe()
        self.assertEqual(obs['level'],20)
        boxes=[proof[0] for proof in proofs]
        self.assertIn((396,124,26,25),boxes);self.assertNotIn((366,125,23,24),boxes)
    def test_any_read_saying_otherwise_holds(self):
        import owner_skill_growth_candidate as g
        for kwargs in (dict(next_digit='22'),dict(current='19'),dict(next_score=.8),dict(list_score=.85)):
            with self.assertRaises(g.Pending,msg=str(kwargs)):self.observe(**kwargs)

class Balance(unittest.TestCase):
    def read(self,text):
        import owner_skill_growth_candidate as g
        return g.number([{'text':text,'score':.95}],'balance')
    def test_real_forms_read(self):
        self.assertEqual(self.read('1.14M'),1130000);self.assertEqual(self.read('856.93K'),856920);self.assertEqual(self.read('999'),998)
    def test_a_lost_decimal_point_is_refused(self):
        import owner_skill_growth_candidate as g
        for text in ('114M','14M','856K','-1.14M','#1.14M'):
            with self.assertRaises(g.Pending,msg=text):self.read(text)

class UnreadBalance(unittest.TestCase):
    """The commit guard still requires the lit button; only the balance read is dropped."""
    def test_active_is_part_of_the_commit_guard(self):
        import inspect,owner_skill_growth_candidate as g
        source=inspect.getsource(g.StyleGrowth.run)
        self.assertIn('and active(frame)',source);self.assertIn("obs['funds'] is not None",source)
    def test_balance_is_only_dropped_after_it_alone_failed(self):
        import inspect,owner_skill_growth_candidate as g
        self.assertIn('str(BALANCE) in str(exc)',inspect.getsource(g.StyleGrowth.run))

class MaterialShort(unittest.TestCase):
    """Real style pages: 3/5 and 0/1 in red, and 833/200 in white."""
    def load(self,name):
        import numpy as np
        from PIL import Image
        return np.array(Image.open(Path(__file__).resolve().parent/'fixtures_image_scope'/(name+'.png')).convert('RGB'))
    def test_red_counts_are_a_shortage(self):
        import owner_skill_growth_candidate as g
        for name in ('skill_short_red3','skill_short_red0'):self.assertTrue(g.material_short(self.load(name)),name)
    def test_a_white_count_is_not(self):
        import owner_skill_growth_candidate as g
        self.assertFalse(g.material_short(self.load('skill_enough')))
    def test_a_shortage_is_not_retried_as_a_misread(self):
        import owner_skill_growth_candidate as g
        self.assertFalse(any(word in '강타 도술 재료 부족 · 입력 없음' for word in g.STYLE_READ_MISSES))

class Ui(unittest.TestCase):
    def test_a_test_button_sits_beside_each_growth_switch(self):
        import tkinter as tk
        from tkinter import ttk
        from owner_gear_settings_candidate import GearSettings
        root=tk.Tk();root.withdraw();self.addCleanup(root.destroy)
        fake=S(window=root,feature_vars={},switches=S(initial={'equipment':False},editable={'equipment':True}))
        fake.test_request=Mock()
        area=ttk.Frame(root);GearSettings.feature_switch(fake,area,'equipment')
        buttons=[w for line in area.winfo_children() for w in line.winfo_children() if isinstance(w,ttk.Button)]
        self.assertEqual(len(buttons),1);buttons[0].invoke()
        self.assertEqual(fake.test_request.call_args[0][0],'equipment')

if __name__=='__main__':unittest.main()
