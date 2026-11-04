"""Isolated durable state and fake input; no UI/game actions."""
import contextlib,copy,json,tempfile,time,unittest,ast
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import owner_quest_position_recovery as r
import owner_quest_emote_candidate as nav
import owner_emote_dispatch as d
from owner_skill_goal import Pending
from owner_emote_cooldown import Rate
from test_diagnostic_0913_recovery import RecoveryTests,REASON

class RecoveryDurability(unittest.TestCase):
 setup_case=RecoveryTests.setup_case
 bindings=RecoveryTests.bindings
 def pending(self,ui,b,phase='intent'):
  self.row['position_recovery']={'phase':phase,'at':time.time()-90,'reason':REASON,'character':'char','scope':'scope'}
  self.row['block']={'reason':'condition','functional_hold':True,'detail':'자리 정체 복구 확인 필요 · exact root'}
  b.item['active']=None
 def test_legacy_intent_reconciles_paired_town_without_repeating_home(self):
  ui,b=self.setup_case();self.pending(ui,b);self.adapter.run_town_return=lambda *a:self.fail('must not replay Home')
  with self.bindings():self.assertIs(r.resume_pending(ui,b),True)
  self.assertEqual(self.row['position_recovery']['phase'],'restarted_unverified')
  self.assertEqual(self.row['position_recovery']['town_proof'],'paired_native_town_label')
  self.assertNotIn('block',self.row);self.assertEqual(len(self.row['position_recovery_hold_history']),1)
  self.assertFalse(self.row['completed']);self.assertEqual(self.row['deaths'],1)
 def test_missing_root_retains_at_town_and_cooldown_then_resumes_after_restart(self):
  from owner_mission_policy import QuestBook
  ui,b=self.setup_case();self.pending(ui,b)
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   first=QuestBook(temp,'char');first.item.update(copy.deepcopy(b.item));first.commit()
   with self.bindings(select=False):self.assertFalse(r.resume_pending(ui,first))
   resumed=QuestBook(temp,'char');record=resumed.item['quests']['q']['position_recovery']
   self.assertEqual(record['phase'],'at_town');self.assertIsNone(resumed.item['active'])
   self.calls.clear()
   with self.bindings():self.assertFalse(r.resume_pending(ui,resumed))
   self.assertEqual(self.calls,[])
   record['root_checked_at']=time.time()-62;resumed.commit()
   with self.bindings():self.assertTrue(r.resume_pending(ui,resumed))
   self.assertEqual(QuestBook(temp,'char').item['quests']['q']['deaths'],1)
   self.assertNotIn('home',self.calls)
 def test_no_town_does_not_retry_home_or_open_any_quest(self):
  ui,b=self.setup_case();self.pending(ui,b)
  with self.bindings(town=False):self.assertFalse(r.resume_pending(ui,b))
  self.assertEqual(self.calls,[]);self.assertEqual(self.row['position_recovery']['phase'],'intent')
 def test_completed_receipt_and_active_other_are_never_replaced(self):
  ui,b=self.setup_case();self.pending(ui,b);self.row['completed']=True;before=copy.deepcopy(b.item)
  with self.bindings():self.assertFalse(r.resume_pending(ui,b))
  self.assertEqual(b.item,before)
  self.row['completed']=False;b.item['active']='other';b.item['quests']['other']={'title':'other'}
  with self.bindings():self.assertFalse(r.resume_pending(ui,b))
  self.assertEqual(self.calls,[]);self.assertEqual(b.item['active'],'other')
 def test_mismatched_scope_or_pair_never_sends_auto(self):
  ui,b=self.setup_case();self.pending(ui,b);self.row['position_recovery']['scope']='foreign'
  with self.bindings():self.assertFalse(r.resume_pending(ui,b))
  self.assertNotIn('auto',self.calls);self.assertNotIn('home',self.calls)
  self.row['position_recovery']['scope']='scope'
  with self.bindings(),patch('owner_story_groups.Groups',return_value=S(locate=lambda key:None)):
   self.assertFalse(r.resume_pending(ui,b))
  self.assertEqual(self.row['position_recovery']['phase'],'at_town');self.assertNotIn('auto',self.calls)
 def test_unknown_auto_result_never_replays_and_stop_propagates(self):
  ui,b=self.setup_case()
  def stop_auto():raise Pending('AUTO uncertain')
  ui.start_selected=stop_auto
  with self.bindings():
   with self.assertRaises(Pending):r.recover(ui,b,'q',REASON)
  self.assertEqual(self.row['position_recovery']['phase'],'restart_intent')
  self.calls.clear()
  with self.bindings():
   with self.assertRaises(Pending):r.recover(ui,b,'q',REASON)
  self.assertEqual(self.calls,[])
  self.pending(ui,b)
  class Stop(BaseException):pass
  self.ctx.checkpoint=lambda:(_ for _ in ()).throw(Stop())
  with self.bindings():
   with self.assertRaises(Stop):r.resume_pending(ui,b)
  self.assertEqual(self.calls,[])
 def test_recent_emote_does_not_trigger_home_or_become_recovery_success(self):
  ui,b=self.setup_case();self.pending(ui,b);self.row['emote_attempt']={'at':time.time()-20}
  with self.bindings():self.assertFalse(r.resume_pending(ui,b))
  self.assertNotIn('home',self.calls);self.assertNotIn('auto',self.calls);self.assertIn('block',self.row)
 def test_root_rechecks_are_bounded_but_not_permanently_poisoned(self):
  ui,b=self.setup_case();self.pending(ui,b,'at_town')
  rec=self.row['position_recovery'];rec.update(root_attempts=2,root_window_at=time.time()-100)
  with self.bindings():self.assertFalse(r.resume_pending(ui,b))
  self.assertNotIn('open-current',self.calls)
  rec['root_window_at']=time.time()-901
  with self.bindings():self.assertTrue(r.resume_pending(ui,b))
  self.assertNotIn('home',self.calls)

class CleanupResult(unittest.TestCase):
 def enter(self,cm):
  value=cm.__enter__();self.addCleanup(cm.__exit__,None,None,None);return value
 def worker(self,*,send_error=None,cleanup_error=None):
  temp=self.enter(tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch'));root=Path(temp)
  row={'title':'동굴에서 들린 소리'};book=S(item={'active':'q','quests':{'q':row}},commit=lambda:None)
  class UI:
   def __init__(self):self.kind='menu';self.adapter=S(project=S(root=root),_owner_emote_requested='q');self.inputs=S();self.context=S(checkpoint=lambda:None,wait=lambda _:None);self.actions=[]
   def frame(self):return self.kind
   def normal(self):return self.kind=='field'
   def normal_frame(self,f):return f=='field'
   def rows(self,*a,**kw):return [{'text':'[외전]동굴에서들린소리4','score':.999}]
   def click(self,x,y,proof):
    assert proof(self.kind);self.actions.append((x,y))
    if send_error:raise send_error
   def wheel(self,*a,**kw):raise AssertionError('no scroll required')
  ui=UI()
  class Detector:
   def find(self,n,f,threshold):return (1,1,(0,0,2,2)) if n=='체크_채팅창' and f=='menu' else None
  def cleanup(u,_):
   if cleanup_error:raise cleanup_error
   u.kind='field'
  stack=self.enter(contextlib.ExitStack())
  for cm in (patch.object(d,'known_goal',return_value=('황당',146)),patch.object(d,'target_zone',return_value=True),patch.object(d,'empty_chat',return_value=True),patch.object(d,'panel',side_effect=lambda f:f=='menu'),patch.object(d,'card_hit',return_value=(397,440)),patch.object(d,'close_chat',side_effect=cleanup),patch.object(d,'chat_detector',return_value=Detector()),patch('owner_progression.state',return_value=S(character='char')),patch('owner_hunt_rules_candidate.configured_identity',return_value='scope')):stack.enter_context(cm)
  return ui,book,row,root
 def test_successful_send_survives_cleanup_failure_and_next_input_is_blocked(self):
  ui,b,row,root=self.worker(cleanup_error=Pending('close unavailable'))
  self.assertIs(d.run(ui,b,'q'),True);self.assertEqual(ui.actions,[(397,440)])
  rec=json.loads(nav._marker_path(root).read_text(encoding='utf8'));self.assertEqual(rec['phase'],'cleanup_pending')
  self.assertEqual(rec['attempt']['phase'],'input_intent_unverified');self.assertGreater(Rate(root,'scope','char').remaining(),60)
  with patch.object(nav,'normalize_after_stop',side_effect=Pending('typed input')):
   with self.assertRaises(nav.EmoteCleanupPending):d.run(ui,b,'q')
  self.assertEqual(ui.actions,[(397,440)])
 def test_original_pending_is_not_replaced_by_cleanup_error(self):
  original=Pending('original send uncertain');ui,b,row,root=self.worker(send_error=original,cleanup_error=RuntimeError('secondary close'))
  with self.assertRaises(Pending) as caught:d.run(ui,b,'q')
  self.assertIs(caught.exception,original)
  self.assertEqual(json.loads(nav._marker_path(root).read_text(encoding='utf8'))['primary_error'],str(original))
  self.assertEqual(row['emote_attempt']['phase'],'input_intent_unverified')
 def test_stop_during_send_is_not_converted_to_cleanup_failure(self):
  class Stop(BaseException):pass
  stop=Stop('stop');ui,b,row,root=self.worker(send_error=stop,cleanup_error=RuntimeError('close'))
  with self.assertRaises(Stop) as caught:d.run(ui,b,'q')
  self.assertIs(caught.exception,stop);self.assertEqual(len(ui.actions),1)
 def test_cleanup_stop_always_propagates(self):
  from biol_base.session import Cancelled
  ui,b,row,root=self.worker(cleanup_error=Cancelled('actual stop'))
  with self.assertRaises(Cancelled):d.run(ui,b,'q')
  self.assertEqual(row['emote_attempt']['phase'],'input_intent_unverified')
 def test_cleanup_gate_does_not_convert_actual_stop_to_failure(self):
  from biol_base.session import Cancelled
  ui,b,row,root=self.worker(cleanup_error=Pending('close'));d.run(ui,b,'q')
  with patch.object(nav,'normalize_after_stop',side_effect=Cancelled('actual stop')):
   with self.assertRaises(Cancelled):nav.require_cleanup_closed(ui)
 def test_cleanup_gate_normalizes_only_once_and_keeps_rate_receipt(self):
  ui,b,row,root=self.worker(cleanup_error=Pending('close'))
  d.run(ui,b,'q');before=copy.deepcopy(row)
  def normalized(*a,**kw):nav.save_navigation(root,'scope','closed');ui.kind='field';return True
  with patch.object(nav,'normalize_after_stop',side_effect=normalized) as fix:
   nav.require_cleanup_closed(ui);nav.require_cleanup_closed(ui)
  self.assertEqual(fix.call_count,1);self.assertEqual(row,before);self.assertEqual(len(ui.actions),1)
 def test_record_save_failure_also_preserves_result_but_volatile_gate_blocks(self):
  ui,b,row,root=self.worker(cleanup_error=Pending('close'));original=d.save_navigation
  def save(*a,**kw):
   if a[2]=='cleanup_pending':raise OSError('disk')
   return original(*a,**kw)
  with patch.object(d,'save_navigation',side_effect=save):self.assertIs(d.run(ui,b,'q'),True)
  with self.assertRaises(nav.EmoteCleanupPending):nav.require_cleanup_closed(ui)
 def test_cleanup_scope_mismatch_keeps_pending_even_if_field_now_visible(self):
  ui,b,row,root=self.worker(cleanup_error=Pending('close'));d.run(ui,b,'q')
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='foreign'):
   with self.assertRaises(nav.EmoteCleanupPending):nav.require_cleanup_closed(ui)
  self.assertEqual(json.loads(nav._marker_path(root).read_text(encoding='utf8'))['phase'],'cleanup_pending')
 def test_controller_fences_native_step_and_pending_error_path(self):
  p=Path(__file__).parent/'owner_mission_controller.py';tree=ast.parse(p.read_text(encoding='utf8'))
  run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
  gates=[n.lineno for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='require_cleanup_closed']
  self.assertGreaterEqual(len(gates),3)
  handler=next(n for n in ast.walk(run) if isinstance(n,ast.ExceptHandler) and isinstance(n.type,ast.Name) and n.type.id=='EmoteCleanupPending')
  self.assertTrue(any(isinstance(n,ast.Raise) for n in handler.body))

if __name__=='__main__':unittest.main()
