"""Saved frames, fake ports, isolated durable files; no actual game inputs."""
from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf8'))
import time,tempfile,copy,unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
import owner_skill_growth_candidate as g
import owner_skill_upgrade_candidate as u
from owner_skill_goal import Pending,Ledger

HERE=Path(__file__).parent
def image():return np.asarray(Image.open(HERE/'live_fixtures/skill_awaken_lifeflow_native_1.png').convert('RGB')).copy()
class Journal:
 def __init__(self):self.item={};self.events=[]
 def event(self,name,**kw):self.events.append((name,kw))
class Port:
 def __init__(self,current=0):
  self.current=current;self.actions=[];self.effect=True;self.fail_before=False;self.fail_after=False;self.have=100;self.funds=500000
  self.stop=False;self.ui=S(context=S(checkpoint=self.checkpoint,wait=lambda _:None))
 def checkpoint(self):
  if self.stop:raise Pending('user Stop')
 def observe(self,name,kind,*,need_quote=False):
  return dict(name=name,kind=kind,current=self.current,next=self.current+1,have=self.have,need=100,price=50000,funds=self.funds)
 def commit(self,observation,prepare):
  if self.fail_before:raise Pending('preinput')
  prepare();self.actions.append((observation['name'],observation['kind']))
  if self.effect:self.current+=1
  if self.fail_after:raise Pending('uncertain input')

class DurablePipeline(unittest.TestCase):
 def test_awaken_exact_next_result_and_no_repeat_at_goal(self):
  p=Port();l=Journal();w=u.SkillUpgrade(p,l,lambda:True)
  self.assertEqual(w.run('생명의 흐름','awaken',1)['status'],'target_reached')
  self.assertEqual(l.item['skill_upgrade_intents']['awaken:생명의 흐름']['status'],'confirmed')
  w.run('생명의 흐름','awaken',1);self.assertEqual(len(p.actions),1)
 def test_consecutive_breakthrough_does_not_repeat_enhancement(self):
  p=Port();l=Journal();seen=[]
  out=u.SkillUpgrade(p,l,lambda:True,lambda *a:seen.append(a)).run('파멸','breakthrough',3)
  self.assertEqual(out['current'],3);self.assertEqual(len(p.actions),3)
  self.assertTrue(all(x[1]=='breakthrough' for x in p.actions));self.assertEqual(seen[-1],('skills','파멸',{'breakthrough':3}))
 def test_material_shortage_does_not_prepare_or_click(self):
  for field in ('have',):
   p=Port();setattr(p,field,0);l=Journal()
   with self.assertRaises(Pending):u.SkillUpgrade(p,l,lambda:True).run('생명의 흐름','awaken',1)
   self.assertEqual(p.actions,[]);self.assertEqual(l.item.get('skill_upgrade_intents'),{})
 def test_unconfirmed_sent_input_never_replays(self):
  p=Port();p.effect=False;l=Journal();w=u.SkillUpgrade(p,l,lambda:True)
  with self.assertRaises(Pending):w.run('생명의 흐름','awaken',1)
  with self.assertRaises(Pending):w.run('생명의 흐름','awaken',1)
  self.assertEqual(len(p.actions),1);self.assertTrue(u.has_pending(l))
 def test_cold_restart_reconciles_only_exact_observed_increment(self):
  with tempfile.TemporaryDirectory(dir=HERE/'test_scratch') as folder:
   p=Port();p.fail_after=True;l=Ledger(folder,'paired-character',scope='configured-profile')
   with self.assertRaises(Pending):u.SkillUpgrade(p,l,lambda:True).run('生','awaken',1)
   restarted=Ledger(folder,'paired-character',scope='configured-profile')
   p.fail_after=False;out=u.SkillUpgrade(p,restarted,lambda:True).run('生','awaken',1)
   self.assertEqual(out['current'],1);self.assertEqual(len(p.actions),1)
   self.assertEqual(restarted.item['skill_upgrade_intents']['awaken:生']['status'],'observed_after')
 def test_restart_does_not_assume_unchanged_stage_means_no_consumption(self):
  l=Journal();l.item={'skill_upgrade_intents':{'awaken:A':{'status':'sent','before':0}}};p=Port()
  with self.assertRaises(Pending):u.SkillUpgrade(p,l,lambda:True).run('A','awaken',1)
  self.assertEqual(p.actions,[])
 def test_preinput_failure_can_retry_after_reading_again(self):
  p=Port();p.fail_before=True;l=Journal();w=u.SkillUpgrade(p,l,lambda:True)
  with self.assertRaises(Pending):w.run('A','awaken',1)
  self.assertEqual(l.item['skill_upgrade_intents']['awaken:A']['status'],'aborted_before_input')
  p.fail_before=False;self.assertEqual(w.run('A','awaken',1)['current'],1)
 def test_changed_identity_and_stop_propagate_before_resource_input(self):
  p=Port();l=Journal()
  with self.assertRaises(Pending):u.SkillUpgrade(p,l,lambda:False).run('A','awaken',1)
  p.stop=True
  with self.assertRaisesRegex(Pending,'Stop'):u.SkillUpgrade(p,l,lambda:True).run('A','awaken',1)
  self.assertEqual(p.actions,[])
 def test_bounded_loop_returns_partial_not_success(self):
  p=Port();l=Journal();out=u.SkillUpgrade(p,l,lambda:True).run('A','awaken',7,max_steps=2)
  self.assertEqual(out['status'],'partial');self.assertEqual(len(p.actions),2)
 def test_quote_wrong_skill_cannot_prepare(self):
  p=Port();l=Journal();original=p.observe
  def changed(name,kind,**kw):
   r=original(name,kind,**kw)
   if kw.get('need_quote'):r['name']='another skill'
   return r
  p.observe=changed
  with self.assertRaises(Pending):u.SkillUpgrade(p,l,lambda:True).run('A','awaken',1)
  self.assertEqual(p.actions,[])
 def test_missing_positive_next_stage_stays_held(self):
  p=Port();l=Journal();original=p.observe
  p.observe=lambda *a,**k:{**original(*a,**k),'next':None}
  with self.assertRaises(Pending):u.SkillUpgrade(p,l,lambda:True).run('A','breakthrough',1)
  self.assertEqual(p.actions,[])
 def test_another_skill_pending_receipt_prevents_new_consumption(self):
  p=Port();l=Journal();l.item={'skill_upgrade_intents':{'awaken:A':{'status':'sent','name':'A','kind':'awaken','before':0}}}
  with self.assertRaisesRegex(Pending,'다른 도술'):u.SkillUpgrade(p,l,lambda:True).run('B','awaken',1)
  self.assertEqual(p.actions,[]);self.assertEqual(l.item['skill_upgrade_intents']['awaken:A']['status'],'sent')
 def test_receipt_wrong_name_or_kind_never_confirms_another_skill(self):
  for key,field,value in (('awaken:A','name','B'),('awaken:A','kind','breakthrough')):
   p=Port(current=1);l=Journal();receipt={'status':'sent','name':'A','kind':'awaken','before':0};receipt[field]=value
   l.item={'skill_upgrade_intents':{key:receipt}}
   with self.assertRaisesRegex(Pending,'기록'):u.SkillUpgrade(p,l,lambda:True).run('A','awaken',1)
   self.assertEqual(p.actions,[]);self.assertEqual(receipt['status'],'sent')
 def test_character_and_configured_profile_keep_receipts_separate(self):
  with tempfile.TemporaryDirectory(dir=HERE/'test_scratch') as folder:
   a=Ledger(folder,'character-A',scope='server-profile-A');pa=Port();pa.effect=False
   with self.assertRaises(Pending):u.SkillUpgrade(pa,a,lambda:True).run('같은 도술','awaken',1)
   for character,scope in (('character-B','server-profile-A'),('character-A','server-profile-B')):
    other=Ledger(folder,character,scope=scope);p=Port()
    self.assertEqual(u.SkillUpgrade(p,other,lambda:True).run('같은 도술','awaken',1)['current'],1)
    self.assertEqual(len(p.actions),1)
   original=Ledger(folder,'character-A',scope='server-profile-A')
   self.assertTrue(u.has_pending(original));self.assertEqual(original.item['skill_upgrade_intents']['awaken:같은 도술']['status'],'sent')
 def test_other_style_unknown_enhancement_does_not_leak_into_next_style(self):
  from test_skill_growth_candidate import FakeUI,Ledger as FakeLedger
  ui=FakeUI();l=FakeLedger();ui.ledger=l;l.item={'style_growth_intents':{'파멸':{'status':'sent','before':16}}}
  with self.assertRaisesRegex(Pending,'다른 도술 계열'):g.StyleGrowth(ui,l,lambda:True).run('강타',1)
  self.assertNotIn((480,449),ui.actions);self.assertEqual(l.item['style_growth_intents']['파멸']['status'],'sent')
 def test_malformed_upgrade_receipt_holds_without_resource_input(self):
  for rows in ([],{'A':'broken'}):
   l=Journal();l.item={'skill_upgrade_intents':rows};p=Port()
   with self.assertRaisesRegex(Pending,'기록 형식'):u.SkillUpgrade(p,l,lambda:True).run('A','awaken',1)
   self.assertEqual(p.actions,[])
 def test_visit_deadline_returns_before_identity_expires_without_spending(self):
  from test_skill_growth_candidate import FakeUI,Ledger as FakeLedger
  ui=FakeUI();l=FakeLedger();ui.ledger=l;ui._owner_growth_deadline=time.monotonic()-1
  with self.assertRaisesRegex(Pending,'방문 시간 종료'):g.StyleGrowth(ui,l,lambda:True).run('강타',1)
  self.assertEqual(ui.actions,[])
  p=Port();p.ui._owner_growth_deadline=time.monotonic()-1
  with self.assertRaisesRegex(Pending,'방문 시간 종료'):u.SkillUpgrade(p,Journal(),lambda:True).run('A','awaken',1)
  self.assertEqual(p.actions,[])

class RealAssetsAndRefresh(unittest.TestCase):
 def test_default_port_uses_saved_identity_cost_and_ratio_then_holds_zero_fragments(self):
  f=image()
  class ReadUI:
   def __init__(self):self.context=S(checkpoint=lambda:None,wait=lambda _:None);self.actions=[]
   def frame(self):return f.copy()
   def rows_batch(self,specs):
    self._owner_last_rows_pair=([f.copy(),f.copy()],[time.monotonic()-7,time.monotonic()-6.88],[])
    answers=[{'text':'생명의 흐름','score':.999,'y':85,'bounds':(741,76,795,95)},
     {'text':'생명의 흐름','score':.999,'y':74,'bounds':(363,64,425,85)},
     {'text':'0/100','score':.999,'y':402,'bounds':(379,394,412,410)},
     {'text':'50,000','score':.999,'y':449,'bounds':(344,440,384,459)},
     {'text':'각성','score':.999,'y':449,'bounds':(413,440,443,459)}]
    return [[r] for r in answers[:len(specs)]]
   def click(self,*args):self.actions.append(args);raise AssertionError('zero material must not click')
  ui=ReadUI();p=u.SkillUpgradePort(ui,lambda:True)
  q=p.observe('생명의 흐름','awaken',need_quote=True)
  self.assertEqual((q['current'],q['have'],q['need'],q['price']),(0,0,100,50000))
  with self.assertRaisesRegex(Pending,'재료'):u.SkillUpgrade(p,Journal(),lambda:True).run('생명의 흐름','awaken',1)
  self.assertEqual(ui.actions,[])
 def test_real_zero_stage_and_insufficient_frame_not_a_spend_receipt(self):
  f=image();self.assertEqual(u.awaken_stage(f),0)
  self.assertTrue(g.awaken_red_zero100(f))
  self.assertTrue(g._fixed_template(f,'upgrade_coin.png','5da1e8d46c60a0fa1b25255b220ab2fa3a06ad288e5ec1d915e85a7ddc95982c',(322,443,14,14),.98))
 def test_only_identical_existing_next_star_recognized_on_current_side(self):
  # Derived classifier exercise, NOT a captured successful awakening.
  f=image();f[127:147,380:396]=0;f[131:141,382:392]=f[131:141,417:427]
  self.assertEqual(u.awaken_stage(f),1)
  no_label=f.copy();no_label[127:147,355:379]=0
  self.assertIsNone(u.awaken_stage(no_label))
  f[132:135,383:386]=0;self.assertIsNone(u.awaken_stage(f))
 def test_break_stage_requires_labeled_consecutive_pair(self):
  self.assertEqual(u.parse_break_stage([{'text':'0돌파 → 1돌파','score':.999}]),(0,1))
  for text in ('+50','0돌파 → 2돌파','50강 1돌파','돌파'):
   with self.assertRaises(Pending):u.parse_break_stage([{'text':text,'score':.999}])
 def test_slow_style_ocr_refreshes_only_unchanged_glyph_on_two_new_frames(self):
  from test_skill_growth_candidate import FakeUI,Ledger
  ui=FakeUI();l=Ledger();ui.ledger=l;f=ui.image.copy();box=(735,148,46,20)
  def batch(specs):
   ui._owner_last_rows_pair=([f.copy(),f.copy()],[time.monotonic()-8,time.monotonic()-7.88],[])
   return [[{'text':'강타','score':.99,'y':161,'bounds':(735,148,781,168)}]]
  ui.rows_batch=batch
  rows,proof=g.StyleGrowth(ui,l,lambda:True)._style_rows('강타')
  self.assertTrue(g._same(ui.frame(),proof));self.assertLess(time.monotonic()-proof[2],1)
  self.assertEqual(ui.actions,[])
 def test_slow_style_changed_fresh_glyph_rejects_without_input(self):
  from test_skill_growth_candidate import FakeUI,Ledger
  ui=FakeUI();l=Ledger();ui.ledger=l;f=ui.image.copy()
  def batch(specs):
   ui._owner_last_rows_pair=([f.copy(),f.copy()],[time.monotonic()-8,time.monotonic()-7.88],[])
   return [[{'text':'강타','score':.99,'y':161,'bounds':(735,148,781,168)}]]
  ui.rows_batch=batch;ui.image[148:168,735:781]=0
  with self.assertRaises(Pending):g.StyleGrowth(ui,l,lambda:True)._style_rows('강타')
  self.assertEqual(ui.actions,[])
 def test_source_pair_disagreement_or_changed_settings_cannot_refresh(self):
  f=image();box=(355,127,74,20);proof=(box,f[127:147,355:429].copy(),time.monotonic()-6,'text')
  ui=S(context=S(checkpoint=lambda:None,wait=lambda _:None),frame=lambda:f.copy())
  changed=f.copy();changed[127:147,355:429]=0
  with self.assertRaises(Pending):g.refresh_evidence(ui,lambda:True,[f,changed],[time.monotonic()-6,time.monotonic()-5.88],[proof],g.awakening_tab)
  with self.assertRaises(Pending):g.refresh_evidence(ui,lambda:False,[f,f],[time.monotonic()-6,time.monotonic()-5.88],[proof],g.awakening_tab)


class ActualCallerConnection(unittest.TestCase):
 def test_existing_individual_caller_supplies_ledger_to_real_step_coordinator(self):
  f=image();port=Port();journal=Journal()
  ui=S(context=S(checkpoint=lambda:None,wait=lambda _:None),frame=lambda:f.copy(),wait=lambda predicate:f.copy())
  document={'individual':{'생명의 흐름':{'enabled':True,'awaken':1}}}
  with patch.object(u,'SkillUpgradePort',return_value=port):
   out=g.inspect_configured_awaken(ui,document,lambda:True,lambda *a:None,ledger=journal)
  self.assertEqual(out[0]['status'],'target_reached');self.assertEqual(len(port.actions),1)
 @__import__('unittest.mock',fromlist=['patch']).patch('owner_growth_reading.BREAKTHROUGH_ENABLED',True)
 def test_existing_style_caller_dispatches_consecutive_breakthrough_coordinator(self):
  from owner_gear_settings_candidate import DEFAULT
  document=copy.deepcopy(DEFAULT);document['skills']['파멸'].update(enabled=True,enhance=49,breakthrough=3)
  port=Port();journal=Journal();ui=S(context=S(checkpoint=lambda:None))
  with patch.object(g.StyleGrowth,'run',return_value={'status':'target_reached','level':50}),patch.object(u,'SkillUpgradePort',return_value=port):
   out=g.run_configured(ui,journal,document,lambda:True)
  self.assertEqual(out[-1]['kind'],'breakthrough');self.assertEqual(out[-1]['current'],3);self.assertEqual(len(port.actions),3)
 def test_positive_breakthrough_goal_applies_plus_fifty_prerequisite(self):
  from test_skill_growth_candidate import FakeUI,Ledger
  ui=FakeUI();journal=Ledger();ui.ledger=journal
  out=g.StyleGrowth(ui,journal,lambda:True).run('강타',0,breakthrough_target=1,max_steps=1)
  self.assertEqual(out['status'],'partial');self.assertEqual(out['level'],1)
  self.assertEqual(ui.actions.count((480,449)),1)


if __name__=='__main__':unittest.main()
