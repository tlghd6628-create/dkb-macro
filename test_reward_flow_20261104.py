"""Reward flow on real captured frames with fake inputs. These checks are not live claims."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import shutil,threading,time,unittest
from types import SimpleNamespace as S
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
from biol_base.session import Context
import owner_reward_flow as flow
import owner_reward_visual_guard as guard
guard.install()
import project_adapter.event_rewards as ev,project_adapter.mail_rewards as ml
from owner_reward_cycle import Ledger,INTERVAL,RECHECK,RECHECK_LIMIT

F=Path(__file__).resolve().parent/'fixtures_image_scope'
def load(name):return np.array(Image.open(F/(name+'.png')).convert('RGB'))
PROFILE=bootstrap.A/'profiles/DKB'
FAKE_ROOT=bootstrap.T/'test_scratch/no-reward-evidence'

class Rec:
    def __init__(self,log=None,name='inputs'):self.log=log if log is not None else [];self.name=name
    def __getattr__(self,n):return Rec(self.log,self.name+'.'+n)
    def __call__(self,*a,**k):
        if not self.name.endswith('require_ready'):self.log.append((self.name,a))
        return self
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def __bool__(self):return True
class Cap:
    def __init__(self,get):self.get=get
    def __call__(self):return self.get()
    def __getattr__(self,n):return lambda *a,**k:True
def context():
    c=Context(threading.Event(),threading.Event());c.wait=lambda s:None;return c
def make(key,frame,profile=PROFILE):
    shutil.rmtree(FAKE_ROOT,ignore_errors=True);current=[frame];log=[]
    f=flow.Flow(key,profile,FAKE_ROOT,context(),Cap(lambda:current[0]))
    return f,flow.FlowInputs(f,Rec(log)),current,log
def clicks(log):return [a for n,a in log if n=='inputs.click']

class Popup(unittest.TestCase):
    def test_real_receipt_banner_is_recognised_by_existing_image(self):
        self.assertTrue(flow.popup(PROFILE,load('mail_popup')))
    def test_no_banner_on_plain_mail_or_event(self):
        for n in('mail_open','mail_after','event_new','event_claimed'):self.assertFalse(flow.popup(PROFILE,load(n)),n)

class RealFailures1618(unittest.TestCase):
    """16:18-16:19 real TEST: a dotted row never clicked, an achievement window left open."""
    def test_dot_one_pixel_off_centre_is_still_a_dot(self):
        self.assertIn((593,286),guard.notice_dots(load('event_row_dot')))
    def test_exit_is_never_skipped_as_a_dead_spot(self):
        f,i,cur,log=make('achievement',load('mail_after'))
        i.click(875,20);i.click(875,20);i.click(875,20)
        self.assertEqual(len(clicks(log)),3);self.assertEqual(f.counts['repeat_skipped'],0)
        self.assertEqual(f.finish('COMPLETED'),flow.NOTHING)
    def test_late_receipt_is_waited_for_and_dismissed(self):
        f,i,cur,log=make('achievement',load('mail_after'));i.click(830,445)
        def appears(seconds):cur[0]=load('mail_popup')
        f.context.wait=appears
        i.click(286,19)
        self.assertEqual(clicks(log),[(830,445),(286,19)]);self.assertEqual(f.counts['claims'],1)
        self.assertEqual(f.finish('COMPLETED'),flow.CLAIMED)
    def test_one_receipt_counts_once_while_it_stays_up(self):
        f,i,cur,log=make('achievement',load('mail_popup'))
        i.click(286,19);i.click(286,19);self.assertEqual(f.counts['claims'],1)
    def test_selected_day_tab_is_not_an_unclaimed_reward(self):
        f,i,cur,log=make('event',load('event_row_dot'));i.click(355,195);i.click(355,195)
        self.assertEqual(clicks(log),[(355,195)]);self.assertEqual(f.finish('COMPLETED'),flow.NOTHING)
    def test_achievement_claim_all_with_nothing_is_none(self):
        f,i,cur,log=make('achievement',load('mail_after'));i.click(829,443)
        self.assertEqual(f.finish('COMPLETED'),flow.NOTHING)
    def test_no_wait_without_a_click_to_settle(self):
        f,i,cur,log=make('mail',load('mail_after'))
        def never(seconds):raise AssertionError('no receipt can be pending')
        f.context.wait=never
        i.click(286,19);self.assertEqual(clicks(log),[])

class Inputs(unittest.TestCase):
    def test_blank_click_needs_a_receipt(self):
        f,i,cur,log=make('mail',load('mail_after'));i.click(286,19)
        self.assertEqual(clicks(log),[]);self.assertEqual(f.counts['blank_skipped'],1)
    def test_a_run_of_blank_clicks_lets_one_through(self):
        """짱군네 03:14 (11-07): 20 blanks skipped and the mail never found 나가기. With 나가기 hidden, every fifth goes."""
        f,i,cur,log=make('mail',load('event_claimed'))
        for _ in range(10):i.click(286,19)
        self.assertEqual(clicks(log),[(286,19),(286,19)]);self.assertEqual(f.counts['blank_skipped'],8)
        i.click(836,455);f.pending=None
        for _ in range(4):i.click(286,19)
        self.assertEqual(len(clicks(log)),3)
    def test_blank_clicks_stay_skipped_while_the_exit_shows(self):
        f,i,cur,log=make('mail',load('mail_after'))
        for _ in range(10):i.click(286,19)
        self.assertEqual(clicks(log),[])
    def test_blank_click_goes_when_the_receipt_is_up(self):
        f,i,cur,log=make('mail',load('mail_popup'));i.click(286,19);self.assertEqual(clicks(log),[(286,19)])
    def test_claim_with_banner_counts_as_received(self):
        f,i,cur,log=make('mail',load('mail_open'));i.click(836,455);cur[0]=load('mail_popup')
        self.assertEqual(f.finish('COMPLETED'),flow.CLAIMED)
    def test_claim_all_with_nothing_is_none_not_unsure(self):
        f,i,cur,log=make('mail',load('mail_after'));i.click(836,455);self.assertEqual(f.finish('COMPLETED'),flow.NOTHING)
    def test_same_target_without_change_is_pressed_once(self):
        frame=load('event_claimed');f,i,cur,log=make('event',frame)
        i.click(684,282);i.click(684,282);i.click(684,282)
        self.assertEqual(clicks(log),[(684,282)]);self.assertEqual(f.counts['repeat_skipped'],2)
        self.assertEqual(f.finish(None),flow.PARTIAL)
    def test_claim_all_on_another_tab_is_pressed_again(self):
        """pc1 11-06: an empty 서신 tab, then 시스템 with five mails; the same 모두 받기 was skipped there."""
        empty=load('mail_after');f,i,cur,log=make('mail',empty)
        i.click(836,455)
        other=empty.copy();other[60:400,10:600]=255-other[60:400,10:600]  # another tab's list; the button is untouched
        cur[0]=other;i.click(836,455)
        self.assertEqual(clicks(log),[(836,455),(836,455)]);self.assertEqual(f.counts['repeat_skipped'],0)
    def test_target_that_changed_may_be_pressed_again(self):
        f,i,cur,log=make('event',load('event_claimed'));i.click(583,260)
        cur[0]=load('event_attendance');i.click(583,260);self.assertEqual(len(clicks(log)),2)
    def test_unmoved_list_ends_the_scroll(self):
        frame=load('event_claimed');f,i,cur,log=make('event',frame)
        with i.transaction():i.down('mouse','left');i.move(1,1);i.up('mouse','left')
        with i.transaction():i.down('mouse','left');i.move(1,1);i.up('mouse','left')
        self.assertEqual(f.counts['scroll_skipped'],1)
        self.assertEqual([n for n,_ in log].count('inputs.down'),1)
    def test_evidence_only_for_failures_and_bounded(self):
        f,i,cur,log=make('event',load('event_claimed'));i.click(684,282);f.finish(None)
        self.assertEqual(len(list((FAKE_ROOT/'logs/reward-evidence').iterdir())),1)
        f,i,cur,log=make('mail',load('mail_open'));i.click(836,455);cur[0]=load('mail_popup');f.finish(None)
        self.assertFalse((FAKE_ROOT/'logs/reward-evidence').exists())

class Waits(unittest.TestCase):
    def wait_run(self,frames,seconds=1.):
        f,i,cur,log=make('mail',frames[0]);real=f.context;clock=[0.]
        real.wait=lambda s:clock.__setitem__(0,clock[0]+s)
        seq=iter(frames[1:]);last=[frames[-1]]
        f.capture=Cap(lambda:next(seq,last[0]));f.baseline=frames[0]
        original=time.monotonic;flow.time.monotonic=lambda:clock[0]
        try:flow.FlowContext(f).wait(seconds)
        finally:flow.time.monotonic=original
        return clock[0],f
    def test_settled_new_screen_ends_the_wait_early(self):
        spent,f=self.wait_run([load('mail_open')]+[load('mail_after')]*12)
        self.assertLess(spent,.8);self.assertGreater(f.seconds['saved'],.2)
    def test_no_change_keeps_the_full_native_wait(self):
        spent,f=self.wait_run([load('mail_after')]*12);self.assertGreaterEqual(spent,.99);self.assertEqual(f.seconds['saved'],0)

class NativeFlows(unittest.TestCase):
    def test_original_mail_flow_on_real_frames(self):
        frames={'open':load('mail_open'),'popup':load('mail_popup'),'after':load('mail_after')};cur=['open'];shutil.rmtree(FAKE_ROOT,ignore_errors=True)
        log=[]
        class Inp(Rec):
            def click(self,x,y,*a,**k):
                log.append(('inputs.click',(x,y)))
                if (x,y)==(836,455) and cur[0]=='open':cur[0]='popup'
                elif cur[0]=='popup' and abs(x-286)<5:cur[0]='after'
        d=RoiDetector(PROFILE,list(ml.NAMES));ad=S(project=None)
        r=flow.tracked('mail',ml.run_mail_rewards,ad,(),dict(enabled=True,detector=d,capture=Cap(lambda:frames[cur[0]]),inputs=Inp(log),context=context(),user_log=lambda t:None))
        sent=clicks(log);self.assertIn((836,455),sent);self.assertEqual(ad._owner_reward_last_outcome,flow.CLAIMED)
        self.assertLessEqual(sum(1 for c in sent if abs(c[0]-286)<5),1)

class MissionQuota(unittest.TestCase):
    def ui(self,frame,text):
        import owner_mission_ui as mu
        return S(frame=lambda:frame,context=S(wait=lambda s:None),rows=lambda box,**k:[{'text':text,'score':.999}])
    def test_new_label_counts_up(self):
        import owner_mission_ui as mu
        self.assertEqual(mu.remaining_on_screen(self.ui(load('mission_used'),'5/5')),0)
        self.assertEqual(mu.remaining_on_screen(self.ui(load('mission_fresh'),'0/5')),5)
    def test_unreadable_count_stays_unknown(self):
        import owner_mission_ui as mu
        self.assertIsNone(mu.remaining_on_screen(self.ui(load('mission_used'),'?')))
    def test_instant_left_reads_only_its_own_line(self):
        import owner_mission_ui as mu
        # The real OCR text, misreads included.
        self.assertEqual(mu.instant_left(S(rows=lambda box,**k:[{'text':'멤버실 즉시 완료 남은 윗수 0/5','score':.873}])),0)
        self.assertIsNone(mu.instant_left(S(rows=lambda box,**k:[{'text':'수락','score':.99}])))
    def test_two_reads_must_agree(self):
        import owner_mission_ui as mu
        reads=iter(['5/5','4/5']);frame=load('mission_used')
        ui=S(frame=lambda:frame,context=S(wait=lambda s:None),rows=lambda box,**k:[{'text':next(reads),'score':.9}])
        self.assertIsNone(mu.remaining_on_screen(ui))

class ProductPath(unittest.TestCase):
    """TEST and the cycle reach the native function with no dispatcher adapter set."""
    def scoped(self,key='mail'):
        import owner_rewards
        seen={}
        def native(*,enabled,detector,capture,inputs,context,user_log=None):
            seen.update(inputs=inputs,context=context);return 'COMPLETED'
        return owner_rewards.reward_scope(native,key),seen
    def call(self,run):
        frame=load('mail_after')
        return run(enabled=True,detector=RoiDetector(PROFILE,list(ml.NAMES)),capture=Cap(lambda:frame),inputs=Rec(),context=context())
    def test_direct_call_goes_through_the_flow(self):
        run,seen=self.scoped();self.call(run)
        self.assertIsInstance(seen['inputs'],flow.FlowInputs);self.assertIsInstance(seen['context'],flow.FlowContext)
    def test_outcome_reaches_the_owning_adapter(self):
        run,seen=self.scoped();adapter=S()
        with flow.owning(adapter):self.call(run)
        self.assertEqual(adapter._owner_reward_last_outcome,flow.NOTHING);self.assertIsNone(flow.current_adapter())
    def test_direct_call_skips_the_recent_scan_cache(self):
        run,seen=self.scoped();adapter=S()
        with flow.owning(adapter):self.call(run);seen.clear();self.call(run)
        self.assertIn('inputs',seen)

class Candidates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=ev.EventGlowDetector(RoiDetector(PROFILE,list(ev.NAMES)))
    def test_attendance_takes_the_marked_day_not_the_gold_prize(self):
        boxes=self.g.boxes(load('event_attendance'))
        self.assertEqual(len(boxes),1);l,t,r,b=boxes[0][1];self.assertTrue(l<=583<=r and t<=260<=b)
    def test_claimed_attendance_offers_nothing(self):
        self.assertEqual(self.g.boxes(load('event_claimed')),[])
    def test_locked_gold_point_prize_is_not_offered(self):
        self.assertEqual(self.g.boxes(load('event_mission_claimed')),[])
    def test_real_pass_rim_without_a_dot_is_still_offered(self):
        boxes=self.g.boxes(load('event_pass'))
        self.assertEqual([tuple(int(v) for v in b) for _,b in boxes],[(379,244,414,278)])
    def test_red_art_is_not_a_dot(self):
        self.assertEqual(guard.notice_dots(load('event_banner')),[])
    def test_candidate_box_is_the_native_image_size(self):
        e=self.g.base.entries[ev.REWARD];l,t,r,b=self.g.boxes(load('event_attendance'))[0][1]
        self.assertEqual((r-l,b-t),(e['w'],e['h']))

class Cadence(unittest.TestCase):
    def book(self):
        root=bootstrap.T/'test_scratch/no-reward-ledger';shutil.rmtree(root,ignore_errors=True);(root/'settings').mkdir(parents=True)
        return Ledger(root,'s/c')
    def run_once(self,book,state,at):
        book.record('k','running',at);book.record('k',state,at)
    def test_success_and_nothing_keep_three_hours(self):
        book=self.book()
        for state in(flow.CLAIMED,flow.NOTHING):
            self.run_once(book,state,1000.)
            self.assertFalse(book.due('k',1000.+RECHECK));self.assertTrue(book.due('k',1000.+INTERVAL))
    def test_unsure_gets_a_bounded_early_look(self):
        book=self.book();at=1000.
        for attempt in range(RECHECK_LIMIT):
            self.run_once(book,flow.PARTIAL,at);self.assertTrue(book.due('k',at+RECHECK),attempt);at+=RECHECK
        self.run_once(book,flow.PARTIAL,at)
        self.assertFalse(book.due('k',at+RECHECK));self.assertTrue(book.due('k',at+INTERVAL))
    def test_success_clears_the_recheck_count(self):
        book=self.book();self.run_once(book,flow.FAILED,1000.);self.run_once(book,flow.FAILED,2000.);self.run_once(book,flow.CLAIMED,3000.)
        self.assertEqual(book.rows['k'].get('rechecks',0),0)
        self.run_once(book,flow.PARTIAL,4000.);self.assertTrue(book.due('k',4000.+RECHECK))

if __name__=='__main__':unittest.main()
