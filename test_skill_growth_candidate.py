"""Saved screenshots + fake OCR/input only; no game input or upgrade."""
import sys,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
from PIL import Image
import owner_skill_growth_candidate as g
from owner_skill_goal import Pending

HERE=Path(__file__).resolve().parent
def frame(name):return np.asarray(Image.open(HERE/'live_fixtures'/name).convert('RGB'))[31:510,1:898].copy()

class Ledger:
 def __init__(self):self.item={};self.events=[]
 def event(self,name,**kwargs):self.events.append((name,kwargs))
class FakeUI:
 def __init__(self):
  self.image=frame('skill_growth_strike0_1.jpg');self.level=0;self.have='10/1';self.actions=[];self.ledger=None
  self.context=SimpleNamespace(checkpoint=lambda:None,wait=lambda _:None)
 def frame(self):return self.image.copy()
 def rows(self,box,**kwargs):
  self.last_text_frame=self.image.copy();self.last_text_tick=time.monotonic()
  self._owner_last_rows_pair=([self.image.copy(),self.image.copy()],[time.monotonic(),time.monotonic()],[[],[]])
  if box==g.LIST:return [{'text':'강타'+('+'+str(self.level) if self.level else ''),'score':.95,'y':161}]
  if box==g.TRANSITION:return [{'text':f'-{self.level}{self.level+1}+','score':.95}]
  if box==g.OPEN_CURRENT:return [{'text':str(self.level),'score':.99}]
  if box==g.OPEN_NEXT:return [{'text':str(self.level+1),'score':.99}]
  if box==g.RATIO:return [{'text':self.have,'score':.995}]
  if box==g.PRICE:return [{'text':'10,000','score':.999}]
  if box==g.BALANCE:return [{'text':'567.22K','score':.93}]
  raise AssertionError('unexpected OCR region')
 def click(self,x,y,proof):
  if not proof(self.image):raise Pending('input guard rejected')
  if (x,y)==(480,449):
   assert next(iter(self.ledger.item['style_growth_intents'].values()))['status']=='sent'
   self.level+=1
  self.actions.append((x,y))
 def drag(self,*a):self.actions.append('scroll')

class Tests(unittest.TestCase):
 def test_observed_screens_reject_other_tabs_and_insufficient_button(self):
  good=frame('skill_growth_strike0_1.jpg');short=frame('skill_growth_ruin16_1.jpg')
  self.assertTrue(g.tab(good));self.assertTrue(g.selected(good,161));self.assertTrue(g.active(good))
  self.assertTrue(g.tab(short));self.assertTrue(g.selected(short,323));self.assertFalse(g.active(short))
  self.assertFalse(g.tab(frame('skill_awaken_list_1.jpg')))
  self.assertFalse(g.tab(frame('blessing_growth_20261101.jpg')))
  for name in ('skill_open_death9_native_1.png','skill_open_death9_native_2.png'):
   im=np.asarray(Image.open(HERE/'live_fixtures'/name).convert('RGB'))
   self.assertTrue(g.tab(im));self.assertTrue(g.selected(im,80));self.assertTrue(g.open_button(im))
   self.assertTrue(all(not g.selected(im,y) for y in (121,161,202,242,283,323,363,404)))
  self.assertFalse(g.open_button(good))
 def test_awaken_identity_uses_existing_icon_and_refuses_other_views(self):
  for name in ('skill_awaken_lifeflow_1.jpg','skill_awaken_lifeflow_2.jpg'):
   image=frame(name)
   self.assertTrue(g.awakening_tab(image));self.assertTrue(g.awaken_selected(image,85))
   self.assertEqual(g.awaken_center_icon(image),84)
   image[83:140,365:425]=0
   self.assertIsNone(g.awaken_center_icon(image))
  self.assertIsNone(g.awaken_center_icon(frame('skill_growth_strike0_1.jpg')))
 def test_observed_zero_awaken_and_red_zero100_are_narrow(self):
  frames=[np.asarray(Image.open(HERE/'live_fixtures'/f'skill_awaken_lifeflow_native_{i}.png').convert('RGB')).copy() for i in (1,2)]
  self.assertTrue(all(g.awaken_zero_stage(f) and g.awaken_red_zero100(f) for f in frames))
  self.assertEqual(g.inspect_awaken_selected(frames,'생명의 흐름'),{'name':'생명의 흐름','awaken':0,'insufficient_zero100':True})
  self.assertIsNone(g.inspect_awaken_selected(frames,'공간 결계'))
  changed=frames[1].copy();changed[396:409,380:390]=0
  self.assertFalse(g.awaken_red_zero100(changed))
  changed=frames[1].copy();changed[127:147,355:429]=0
  self.assertIsNone(g.inspect_awaken_selected([frames[0],changed],'생명의 흐름'))
  changed=frames[1].copy();changed[132:135,379:382]=(0,190,255)
  self.assertFalse(g.awaken_zero_stage(changed))
  opening=np.asarray(Image.open(HERE/'live_fixtures/skill_open_death9_native_1.png').convert('RGB'))
  self.assertTrue(g.awaken_unselected(opening));self.assertFalse(g.awaken_zero_stage(opening))
 def test_open_foreground_proofs_handle_animation_and_reject_glyph_change(self):
  first=np.asarray(Image.open(HERE/'live_fixtures/skill_open_death9_native_1.png').convert('RGB'))
  second=np.asarray(Image.open(HERE/'live_fixtures/skill_open_death9_native_2.png').convert('RGB'))
  for box,mode in [((365,123,20,25),'text'),((397,123,23,25),'gold'),((368,394,51,17),'text')]:
   x,y,w,h=box;source=first[y:y+h,x:x+w].copy()
   self.assertTrue(g._same_pixels(second,box,source,mode))
   altered=second.copy();crop=altered[y:y+h,x:x+w]
   if mode=='gold':
    hsv=__import__('cv2').cvtColor(crop,__import__('cv2').COLOR_RGB2HSV)
    yy,xx=np.argwhere((hsv[:,:,0]>=15)&(hsv[:,:,0]<=40)&(hsv[:,:,1]>120)&(hsv[:,:,2]>150))[0]
   else:
    gray=__import__('cv2').cvtColor(crop,__import__('cv2').COLOR_RGB2GRAY);yy,xx=np.argwhere(gray>120)[0]
   crop[yy,xx]=0
   self.assertFalse(g._same_pixels(altered,box,source,mode))
 def test_style_batch_returns_a_row_not_an_outer_list(self):
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  image=np.asarray(Image.open(HERE/'live_fixtures/skill_open_death9_native_1.png').convert('RGB')).copy()
  def rows_batch(specs):
   ui._owner_last_rows_pair=([image.copy(),image.copy()],[time.monotonic(),time.monotonic()],[])
   return [[{'text':'절명+9','score':.98,'y':80,'bounds':(735,68,781,92)}]]
  ui.rows_batch=rows_batch
  rows,proof=g.StyleGrowth(ui,ledger,lambda:True)._style_rows('절명')
  self.assertEqual(g.named_row(rows,'절명')[1],9);self.assertTrue(g._same(image,proof))
 def test_ratio_slash_required_and_unambiguous(self):
  self.assertEqual(g.number([{'text':'10/1','score':.994}],'ratio'),(10,1))
  self.assertEqual(g.number([{'text':'1,069/100','score':.997}],'ratio'),(1069,100))
  with self.assertRaises(Pending):g.number([{'text':'16','score':.999}],'ratio')
  with self.assertRaises(Pending):g.number([{'text':'10/1','score':.97}],'ratio')
  self.assertEqual(g.number([{'text':'567.22K','score':.93}],'balance'),567210)
  g.transition([{'text':'-01+','score':.934}],0)
  with self.assertRaises(Pending):g.transition([{'text':'-01+','score':.934}],9)
 def test_one_step_obeys_target_and_durable_intent(self):
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  self.assertEqual(g.StyleGrowth(ui,ledger,lambda:True).run('강타',1)['status'],'target_reached')
  self.assertEqual(ui.actions,['scroll','scroll','scroll',(790,161),(480,449)])
  self.assertEqual(ledger.item['style_growth_intents']['강타']['status'],'confirmed')
  self.assertEqual([e[0] for e in ledger.events],['style_growth_intent','style_growth_sent','style_growth_verified'])
 def test_no_spend_when_ratio_unknown_or_already_at_target(self):
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger;ui.have='16'
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:True).run('강타',1)
  self.assertNotIn((480,449),ui.actions)
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  self.assertEqual(g.StyleGrowth(ui,ledger,lambda:True).run('강타',0)['status'],'target_reached')
  self.assertNotIn((480,449),ui.actions)
 def test_prior_unknown_intent_or_changed_settings_stop(self):
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  ledger.item['style_growth_intents']={'강타':{'status':'intent','before':0}}
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:True).run('강타',5)
  self.assertNotIn((480,449),ui.actions)
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:False).run('강타',5)
  self.assertEqual(ui.actions,[])
 def test_boundary_does_not_assume_opening(self):
  ui=FakeUI();ui.level=9;ledger=Ledger();ui.ledger=ledger
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:True).run('강타',19)
  self.assertNotIn((480,449),ui.actions)
 def test_observed_opening_runs_only_below_target_and_rechecks(self):
  class OpenUI(FakeUI):
   def __init__(self):
    super().__init__();self.image=np.asarray(Image.open(HERE/'live_fixtures/skill_open_death9_native_1.png').convert('RGB')).copy();self.level=9;self.have='1,069/100'
   def rows(self,box,**kwargs):
    result=super().rows(box,**kwargs)
    if box==g.LIST:return [{'text':'절명+'+str(self.level),'score':.98,'y':80}]
    if box==g.PRICE:return [{'text':'200,000','score':.999}]
    return result
  ui=OpenUI();ledger=Ledger();ui.ledger=ledger
  result=g.StyleGrowth(ui,ledger,lambda:True).run('절명',10)
  self.assertEqual(result['status'],'target_reached');self.assertEqual(ui.actions.count((480,449)),1)
  self.assertEqual(ledger.item['style_growth_intents']['절명']['after'],10)
  ui=OpenUI();ledger=Ledger();ui.ledger=ledger
  self.assertEqual(g.StyleGrowth(ui,ledger,lambda:True).run('절명',9)['status'],'target_reached')
  self.assertNotIn((480,449),ui.actions)
 def test_refresh_requires_two_unchanged_actual_crops(self):
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  original=ui.frame;calls=[]
  def changed():
   calls.append(1);result=original()
   if len(calls)==3:result[g.PRICE[1]+3,g.PRICE[0]+3]^=255
   return result
  ui.frame=changed
  # One look for a red count comes first, then the two proof frames.
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:True)._observation('강타')
  self.assertEqual(len(calls),3)
  self.assertEqual(ui.actions,[])
 def test_batch_observation_and_changed_modal_are_blocked(self):
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  def batch(specs):
   out=[ui.rows(spec[0],language=spec[1],pair_minimum=spec[2]) for spec in specs]
   ui._owner_last_rows_pair=([ui.image.copy(),ui.image.copy()],[time.monotonic(),time.monotonic()],[])
   return out
  ui.rows_batch=batch
  obs,proof=g.StyleGrowth(ui,ledger,lambda:True)._observation('강타')
  # List row, ratio, price, coin glyph, emblem. The shimmering centre digit is read, not pixel-bound.
  self.assertEqual(obs['need'],1);self.assertEqual(len(proof),5)
  self.assertTrue(any(p[3]=='style_icon' for p in proof))
  def popup():
   img=ui.image.copy();img[69:91,12:77]=0;return img
  ui.frame=popup
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:True)._observation('강타')
  self.assertEqual(ui.actions,[])
 def test_presend_failure_is_retryable_but_sent_failure_is_not(self):
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  original=ui.click
  def fail_before(x,y,proof):
   if (x,y)==(480,449):raise Pending('before input')
   return original(x,y,proof)
  ui.click=fail_before
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:True).run('강타',1)
  self.assertEqual(ledger.item['style_growth_intents']['강타']['status'],'aborted_before_input')
  ui.click=original
  self.assertEqual(g.StyleGrowth(ui,ledger,lambda:True).run('강타',1)['status'],'target_reached')
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger;original=ui.click
  def fail_after(x,y,proof):
   if (x,y)==(480,449):
    self.assertTrue(proof(ui.image));raise Pending('input uncertain')
   return original(x,y,proof)
  ui.click=fail_after
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:True).run('강타',1)
  self.assertEqual(ledger.item['style_growth_intents']['강타']['status'],'sent')
  with self.assertRaises(Pending):g.StyleGrowth(ui,ledger,lambda:True).run('강타',1)
 def test_menu_cleanup_stop_unknown_and_revision_independent(self):
  import threading
  stop=threading.Event();ctx=SimpleNamespace(stop=stop,wait=lambda _:None,checkpoint=lambda:None)
  class Nav:
   def __init__(self):self.screen='growth';self.clicks=0
   def frame(self):return self.screen
   def normal_frame(self,frame):return frame=='field'
   def click(self,x,y,proof):
    if not proof(self.screen):raise Pending('guard')
    self.clicks+=1;self.screen='field'
   def wait(self,fn,seconds):
    if not fn(self.screen):raise Pending('timeout')
  det=SimpleNamespace(find=lambda name,frame,threshold: frame=='growth')
  ui=Nav();g._return_from_growth(ui,ctx,det,lambda:True);self.assertEqual(ui.clicks,1)
  ui=Nav();ui.screen='unknown'
  with patch.object(g.time,'monotonic',side_effect=iter(range(100))):
   with self.assertRaises(g.SkillGrowthNavigationError):g._return_from_growth(ui,ctx,det,lambda:True)
  self.assertEqual(ui.clicks,0)
  ui=Nav();frames=iter(['transition','transition','growth','growth'])
  def transition():
   if ui.screen=='field':return 'field'
   return next(frames,'growth')
  ui.frame=transition
  g._return_from_growth(ui,ctx,det,lambda:True);self.assertEqual(ui.clicks,1)
  ui=Nav();stop.set()
  with self.assertRaises(g.SkillGrowthNavigationError):g._return_from_growth(ui,ctx,det,lambda:True)
  self.assertEqual(ui.clicks,0)
  stop.clear();ui=Nav()
  def failed_capture():raise OSError('capture failed')
  ui.frame=failed_capture
  with self.assertRaises(g.SkillGrowthNavigationError):g._return_from_growth(ui,ctx,det,lambda:True)
 def test_individual_target_is_reported_as_held_not_completed(self):
  import copy
  from owner_gear_settings_candidate import DEFAULT
  document=copy.deepcopy(DEFAULT)
  document['individual']={'생명의 흐름':{'enabled':True,'awaken':1,'breakthrough':None}}
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger
  rows=g.run_configured(ui,ledger,document,lambda:True)
  self.assertEqual(rows[0]['status'],'held');self.assertEqual(rows[0]['individual'],'생명의 흐름')
  self.assertEqual(ui.actions,[])
 def test_selected_awaken_insufficient_is_read_without_resource_input(self):
  frames=[np.asarray(Image.open(HERE/'live_fixtures'/f'skill_awaken_lifeflow_native_{i}.png').convert('RGB')).copy() for i in (1,2)]
  class ReadUI:
   def __init__(self):self.context=SimpleNamespace(checkpoint=lambda:None,wait=lambda _:None);self.count=0;self.actions=[]
   def frame(self):self.count+=1;return frames[self.count%2].copy()
   def wait(self,fn):
    f=self.frame();assert fn(f);return f
   def click(self,x,y,proof):
    assert proof(self.frame());self.actions.append((x,y))
  ui=ReadUI();seen=[];document={'individual':{'생명의 흐름':{'enabled':True,'awaken':1},'공간 결계':{'enabled':True,'awaken':1}}}
  rows=g.inspect_configured_awaken(ui,document,lambda:True,lambda *a:seen.append(a))
  self.assertEqual(rows[0]['reason'],'각성 조각 0/100 · 재료 부족');self.assertEqual(rows[1]['status'],'held')
  self.assertEqual(seen,[('individual','생명의 흐름',{'awaken':0})]);self.assertEqual(ui.actions,[(755,220)])
 def test_name_fallback_needs_matching_list_title_and_selection(self):
  image=np.asarray(Image.open(HERE/'live_fixtures/skill_awaken_lifeflow_native_1.png').convert('RGB')).copy()
  class NameUI:
   def rows_batch(self,specs):
    self._owner_last_rows_pair=([image.copy(),image.copy()],[time.monotonic(),time.monotonic()],[])
    return [[{'text':'생명의 흐름','score':.99,'y':85,'bounds':(741,76,795,95)}],
            [{'text':'생명의 흐름','score':.99,'y':74,'bounds':(363,64,425,85)}]]
  result=g._inspect_awaken_name(NameUI(),'생명의 흐름',lambda:True)
  self.assertEqual(result,{'name':'생명의 흐름','awaken':0,'insufficient_zero100':True})
  altered=image.copy();altered[127:147,355:429]=0;image[:]=altered
  self.assertIsNone(g._inspect_awaken_name(NameUI(),'생명의 흐름',lambda:True))
 def test_awaken_search_scrolls_bounded_and_respects_stop(self):
  image=np.asarray(Image.open(HERE/'live_fixtures/skill_awaken_lifeflow_native_1.png').convert('RGB')).copy()
  class SearchUI:
   def __init__(self):self.page=5;self.actions=[];self.stopped=False;self.context=SimpleNamespace(checkpoint=self.checkpoint,wait=lambda _:None)
   def checkpoint(self):
    if self.stopped:raise Pending('중지')
   def frame(self):
    result=image.copy();result[0,0,0]=self.page;return result
   def drag(self,start,end,proof):
    assert proof(self.frame());self.actions.append((start,end))
    self.page=max(0,self.page-1) if end[1]>start[1] else min(15,self.page+1)
  ui=SearchUI()
  with patch.object(g,'_select_visible_awaken_icon',side_effect=lambda ui,name,guard:ui.page==12),\
       patch.object(g,'_select_visible_awaken_name',return_value=False),\
       patch.object(g,'_awaken_list_unchanged',side_effect=lambda a,b:a[0,0,0]==b[0,0,0]):
   self.assertTrue(g._seek_awaken(ui,'생명의 흐름',lambda:True))
   self.assertEqual(ui.page,12);self.assertLessEqual(len(ui.actions),40)
   ui.stopped=True
   with self.assertRaises(Pending):g._seek_awaken(ui,'다른 도술',lambda:True)
 def test_native_entry_does_not_run_style_before_outer_loop_finishes(self):
  from project_adapter import achievement_rewards
  calls=[]
  def native(*args,**kwargs):calls.append(('native',kwargs));return 'native-result'
  def extra(*args):calls.append(('style',));return []
  with patch.object(achievement_rewards,'run_growth_entry',native),patch.object(g,'run_after_native',extra):
   g.install(SimpleNamespace())
   self.assertEqual(achievement_rewards.run_growth_entry('adapter','context','inputs'),'native-result')
   self.assertEqual([c[0] for c in calls],['native'])
   calls.clear()
   self.assertEqual(achievement_rewards.run_growth_entry('adapter','context','inputs',equipment_test=True),'native-result')
   self.assertEqual([c[0] for c in calls],['native'])
 def test_post_native_dispatch_reports_unverified_and_respects_reconcile_only(self):
  calls=[];adapter=SimpleNamespace(values={'auto_growth.taoist.enabled':True})
  with patch.object(g,'run_after_native',side_effect=lambda *a:calls.append('style') or [{'status':'held'}]):
   self.assertTrue(g.dispatch_after_native(adapter,'context','inputs'))
   self.assertEqual(calls,['style']);self.assertEqual(adapter._owner_style_growth_outcome['state'],'processed_unverified')
   adapter._owner_growth_reconcile_only=True
   self.assertTrue(g.dispatch_after_native(adapter,'context','inputs'))
   self.assertEqual(calls,['style']);self.assertEqual(adapter._owner_style_growth_outcome['state'],'reconcile_only')
if __name__=='__main__':unittest.main(verbosity=2)
