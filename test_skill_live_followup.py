"""Actual Sky-rendered capture classification + fake observation consumers.

The root manually performed one +0→+1. These checks validate stored evidence
and display plumbing, not product input or native-PNG/live OCR acceptance.
"""
from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf8'))
import copy,time,tempfile,unittest
from unittest.mock import patch
from types import SimpleNamespace as S
import numpy as np
from PIL import Image
import owner_skill_growth_candidate as g
from owner_skill_goal import Pending
HERE=Path(__file__).parent;FOLDER=HERE/'live_growth_20261102'
def frame(name):return np.asarray(Image.open(FOLDER/(name+'.png')).convert('RGB')).copy()

class LiveButton(unittest.TestCase):
 def test_actual_native_capture_preserves_original_hash_and_recognition(self):
  import hashlib
  path=FOLDER/'skill_style_gangta1_native.png'
  self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'97f4059cfdedba8fc17b946ce9ff87ef0f2407318d879d0da2b8141e53f70f0f')
  f=frame('skill_style_gangta1_native')
  self.assertTrue(g.tab(f));self.assertTrue(g.selected(f,161));self.assertTrue(g.active(f))
 def test_saved_actual_ocr_experiment_keeps_numeric_confidence_at_point98(self):
  import json
  report=json.loads((HERE/'system_audit_20261102/skill_material_roi_experiment.json').read_text(encoding='utf8'))
  selected=[r for r in report if r['box']==list(g.RATIO) and r['mode']==('clahe' if r['source']=='sky' else 'original')]
  self.assertEqual({r['source'] for r in selected},{'sky','native'})
  for row in selected:
   first=g.number(row['pair'][0],'ratio');second=g.number(row['pair'][1],'ratio')
   self.assertEqual(first,second)
   self.assertEqual(first,(10,1) if row['source']=='sky' else (1069,100))
  filtered=json.loads((HERE/'system_audit_20261102/live_skill_sky_filtered_ocr.json').read_text(encoding='utf8'))
  after=next(r for r in filtered if r['source']=='skill_style_gangta1_after')
  ratio=after['comparisons'][2]
  self.assertEqual(g.number(ratio['first'],'ratio'),(9,1));self.assertEqual(g.number(ratio['second'],'ratio'),(9,1))
 def test_actual_ready_and_post_success_cursor_frames_remain_active(self):
  for name in ('skill_style_gangta0_ready1','skill_style_gangta0_ready2','skill_style_gangta1_after1','skill_style_gangta1_after2'):
   f=frame(name);self.assertTrue(g.tab(f));self.assertTrue(g.selected(f,161));self.assertTrue(g.active(f))
 def test_material_shortage_and_unknown_menu_remain_inactive(self):
  f=frame('skill_style_pamyeol16_material_hold');self.assertFalse(g.active(f))
  self.assertFalse(g.selected(f,283));self.assertTrue(g.selected(f,323))
  f=frame('skill_style_gangta1_after1');f[:36]=0;self.assertFalse(g.active(f))
 def test_mouse_fallback_requires_actual_bright_inner_edge(self):
  f=frame('skill_style_gangta1_after1');f[440:456,489:502]=0
  self.assertFalse(g.active(f))

class CurrentObserver(unittest.TestCase):
 def test_confirmed_enhancement_publishes_post_value_to_existing_display_api(self):
  from test_skill_growth_candidate import FakeUI,Ledger
  from owner_growth_current import observe_value,current_value
  with tempfile.TemporaryDirectory(dir=HERE/'test_scratch') as root:
   ui=FakeUI();ledger=Ledger();ui.ledger=ledger;seen=[]
   def observe(section,name,values):
    seen.append((section,name,dict(values)));observe_value(root,'configured-profile',section,name,values,verified=True)
   g.StyleGrowth(ui,ledger,lambda:True,observe).run('강타',1)
   self.assertEqual(current_value(root,'configured-profile','skills','강타','enhance'),'1')
   self.assertEqual(seen,[('skills','강타',{'enhance':0}),('skills','강타',{'enhance':1})])
 def test_visible_style_readings_reuse_raw_rows_without_more_ocr_or_input(self):
  f=frame('skill_style_gangta0_ready1');tick=time.monotonic();seen=[]
  rows=[{'text':'강타','score':.99,'y':161,'bounds':(741,154,776,171)}]
  ui=S(_owner_last_rows_raw=([f.copy(),f.copy()],[tick,tick],[[copy.deepcopy(rows),copy.deepcopy(rows)]]),
   _owner_last_rows_pair=([f.copy(),f.copy()],[tick,tick],[]))
  worker=g.StyleGrowth(ui,S(),lambda:True,lambda *a:seen.append(a))
  worker._publish_visible_styles();worker._publish_visible_styles()
  self.assertEqual(seen,[('skills','강타',{'enhance':0})])
 def test_mismatched_source_or_fresh_glyph_does_not_publish_false_current(self):
  f=frame('skill_style_gangta0_ready1');tick=time.monotonic();seen=[]
  row={'text':'강타','score':.99,'y':161,'bounds':(741,154,776,171)}
  other={**row,'text':'강타+1'}
  ui=S(_owner_last_rows_raw=([f,f],[tick,tick],[[[row],[other]]]),_owner_last_rows_pair=([f,f],[tick,tick],[]))
  worker=g.StyleGrowth(ui,S(),lambda:True,lambda *a:seen.append(a));worker._publish_visible_styles()
  self.assertEqual(seen,[])
  ui._owner_last_rows_raw=([f,f],[tick,tick],[[[row],[row]]]);changed=f.copy();changed[154:171,741:776]=0
  ui._owner_last_rows_pair=([f,changed],[tick,tick],[]);worker._publish_visible_styles();self.assertEqual(seen,[])
 def test_unknown_style_and_low_confidence_do_not_fill_zero(self):
  f=frame('skill_style_gangta0_ready1');tick=time.monotonic();seen=[]
  rows=[{'text':'강타','score':.4,'y':161,'bounds':(741,154,776,171)}]
  ui=S(_owner_last_rows_raw=([f,f],[tick,tick],[[rows,rows]]),_owner_last_rows_pair=([f,f],[tick,tick],[]))
  g.StyleGrowth(ui,S(),lambda:True,lambda *a:seen.append(a))._publish_visible_styles();self.assertEqual(seen,[])


class ChangingBalance(unittest.TestCase):
 def test_actual_saved_tight_balance_region_retains_confidence_and_income_direction(self):
  import json
  report=json.loads((HERE/'system_audit_20261102/skill_balance_roi_experiment.json').read_text(encoding='utf8'))
  for source,mode in (('skill_style_gangta0_ready','clahe'),('skill_style_gangta1_after','original')):
   # Recorded before the patch, against the box of that time.
   row=next(r for r in report if r['source']==source and r['box']==[405,5,43,25] and r['mode']==mode)
   self.assertTrue(g.nondecreasing_balance(*row['pair']))
   self.assertGreaterEqual(min(g.number(r,'balance') for r in row['pair']),10000)
 def test_two_confident_increasing_amounts_are_valid_but_decrease_or_weak_read_is_not(self):
  a=[{'text':'612.93K','score':.955}];b=[{'text':'613.01K','score':.978}]
  self.assertTrue(g.nondecreasing_balance(a,b));self.assertFalse(g.nondecreasing_balance(b,a))
  self.assertFalse(g.nondecreasing_balance([{'text':'612.93K','score':.89}],b))
  self.assertFalse(g.nondecreasing_balance([{'text':'unknown','score':.999}],b))
 def ui(self,latest='567.24K'):
  from test_skill_growth_candidate import FakeUI
  ui=FakeUI();ui.batch_calls=0
  def batch(specs):
   out=[]
   for spec in specs:
    rows=ui.rows(spec[0],language=spec[1],pair_minimum=spec[2])
    if spec[0]==g.BALANCE:
     rows=[{'text':'567.22K' if ui.batch_calls==0 else latest,'score':.999,'bounds':(386,0,448,30)}]
    out.append(rows)
   now=time.monotonic();frames=[ui.image.copy(),ui.image.copy()]
   raw=[[copy.deepcopy(r),copy.deepcopy(r)] for r in out]
   if ui.batch_calls==0:
    raw[-1][1][0]['text']='567.23K';out[-1]=copy.deepcopy(raw[-1][1])
   ui._owner_last_rows_pair=(frames,[now,now],out);ui._owner_last_rows_raw=(frames,[now,now],raw)
   ui.batch_calls+=1;return out
  ui.rows_batch=batch;return ui
 def test_current_balance_is_read_last_and_minimum_is_used(self):
  from test_skill_growth_candidate import Ledger
  ui=self.ui();ledger=Ledger();ui.ledger=ledger
  observation,proofs=g.StyleGrowth(ui,ledger,lambda:True)._observation('강타')
  self.assertEqual(observation['funds'],567210);self.assertEqual(ui.batch_calls,2)
  self.assertTrue(all(g._same(ui.image,p) for p in proofs));self.assertEqual(ui.actions,[])
 def test_latest_decrease_does_not_allow_resource_action(self):
  from test_skill_growth_candidate import Ledger
  ui=self.ui(latest='567.20K');ledger=Ledger();ui.ledger=ledger
  with self.assertRaisesRegex(Pending,'최신 엽전'):g.StyleGrowth(ui,ledger,lambda:True)._observation('강타')
  self.assertEqual(ui.actions,[])
 def test_other_center_icon_does_not_authorize_selected_list_row(self):
  from test_skill_growth_candidate import Ledger
  ui=self.ui();ledger=Ledger();ui.ledger=ledger;original=ui.rows_batch
  def wrong_center(specs):
   out=original(specs)
   if ui.batch_calls==2:
    frames,ticks,rows=ui._owner_last_rows_pair;other=frame('skill_style_pamyeol16_material_hold')
    for f in frames:f[94:116,378:411]=other[94:116,378:411]
   return out
  ui.rows_batch=wrong_center
  with self.assertRaisesRegex(Pending,'대상·비용·재료'):g.StyleGrowth(ui,ledger,lambda:True)._observation('강타')
  self.assertEqual(ui.actions,[])


class DynamicStyleIdentity(unittest.TestCase):
 def test_actual_native_emblem_binding_rejects_swapped_other_style(self):
  f=frame('skill_style_gangta1_native');ui=S(context=object())
  g.bind_style_identity(ui,'강타',[f,f],161)
  other=frame('skill_style_pamyeol16_material_hold');changed=f.copy();changed[94:116,378:411]=other[94:116,378:411]
  with self.assertRaisesRegex(Pending,'중앙 아이콘 변경'):g.bind_style_identity(ui,'강타',[changed,changed],161)
 def test_same_style_survives_actual_level_badge_and_cursor_changes(self):
  ui=S(context=object());before=[frame('skill_style_gangta0_ready'+str(i)) for i in (1,2)]
  after=[frame('skill_style_gangta1_after'+str(i)) for i in (1,2)]
  g.bind_style_identity(ui,'강타',before,161);g.bind_style_identity(ui,'강타',after,161)
 def test_cached_other_style_cannot_reuse_same_emblem_as_new_name(self):
  ui=S(context=object());frames=[frame('skill_style_gangta0_ready1')]*2
  g.bind_style_identity(ui,'강타',frames,161)
  with self.assertRaisesRegex(Pending,'다른 도술 계열'):g.bind_style_identity(ui,'파멸',frames,161)
  ui.context=object();g.bind_style_identity(ui,'강타',frames,161)
  self.assertEqual(set(ui._owner_style_bindings),{'강타'})
 def test_changed_selection_requires_changed_central_emblem(self):
  from test_skill_growth_candidate import FakeUI,Ledger
  ui=FakeUI();ledger=Ledger();ui.ledger=ledger;old_click=ui.click;ui.image[0,0,0]=0
  def clicked(x,y,proof):
   old_click(x,y,proof)
   if x==790:ui.image[0,0,0]=1
  ui.click=clicked
  with patch.object(g,'selected',side_effect=lambda f,y:bool(f[0,0,0])):
   with self.assertRaisesRegex(Pending,'아이콘이 바뀌지'):g.StyleGrowth(ui,ledger,lambda:True)._select('강타')
  self.assertNotIn((480,449),ui.actions)


class NativeSplitTransition(unittest.TestCase):
 """Replay actual native OCR rows against the original native pixel frame."""
 def ui(self,list_score=.9818199277,next_value=2):
  f=frame('skill_style_gangta1_native')
  class Replay:
   def __init__(self):self.context=S(checkpoint=lambda:None,wait=lambda _:None);self.actions=[];self.batch_calls=0
   def frame(self):return f.copy()
   def rows_batch(self,specs):
    known={
     g.LIST:[{'text':'강타+1','score':list_score,'y':161,'bounds':(735,150,779,173)}],
     g.TRANSITION:[{'text':'1','score':.8389030695,'bounds':(361,126,407,147)},
      {'text':'2 +','score':.9305774570,'bounds':(393,126,431,147)}],
     g.OPEN_CURRENT:[{'text':'1','score':.6,'bounds':(366,126,384,147)}],
     g.OPEN_NEXT:[{'text':str(next_value),'score':.9992757440,'bounds':(397,124,417,147)}],
     g.RATIO:[{'text':'9/1','score':.9907413125,'bounds':(381,393,407,413)}],
     g.PRICE:[{'text':'10,000','score':.9998505116,'bounds':(394,440,434,460)}],
     g.BALANCE:[{'text':'659.55K','score':.9822100997,'bounds':(404,9,448,27)}]}
    out=[copy.deepcopy(known[spec[0]]) for spec in specs];now=time.monotonic();frames=[f.copy(),f.copy()]
    self._owner_last_rows_pair=(frames,[now,now],out)
    self._owner_last_rows_raw=(frames,[now,now],[[copy.deepcopy(r),copy.deepcopy(r)] for r in out]);self.batch_calls+=1
    return out
  return Replay()
 def test_native_split_one_uses_strong_list_suffix_and_independent_next(self):
  ui=self.ui();out,proofs=g.StyleGrowth(ui,S(item={}),lambda:True)._observation('강타')
  self.assertEqual((out['level'],out['have'],out['need'],out['price'],out['funds']),(1,9,1,10000,659540))
  self.assertTrue(all(g._same(ui.frame(),p) for p in proofs));self.assertEqual(ui.actions,[])
 def test_lower_list_numeric_confidence_cannot_invent_missing_center_digit(self):
  ui=self.ui(list_score=.97)
  with self.assertRaisesRegex(Pending,'현재·다음'):g.StyleGrowth(ui,S(item={}),lambda:True)._observation('강타')
  self.assertEqual(ui.actions,[])
 def test_next_must_be_exactly_current_plus_one(self):
  ui=self.ui(next_value=3)
  with self.assertRaisesRegex(Pending,'개별 수치'):g.StyleGrowth(ui,S(item={}),lambda:True)._observation('강타')
  self.assertEqual(ui.actions,[])


if __name__=='__main__':unittest.main()
