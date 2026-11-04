import tempfile,unittest,time,types,shutil
from pathlib import Path
from unittest.mock import patch
import owner_energy_box_runtime_candidate as e
from owner_energy_legacy_reconcile_candidate import LEGACY_AT,LEGACY_BEFORE,LEGACY_CHARACTER,LEGACY_RECEIPT,LEGACY_DIR
R=Path('C:/Users/홍이/Downloads/FC_프로그램/도깨비의세계/테스트/DKB_로컬개발용_v0.9.3.1_20261031/vendor/DKB_Auto/logs/energy-claim-evidence')/LEGACY_DIR
class Context:
 def checkpoint(self):pass
class Port:
 def __init__(self):self.calls=[]
 def current_detail(self,guard):
  self.calls.append('read_detail');assert guard();t=time.monotonic();return dict(verified=True,boxes=48,frame_ids=['fresh-a','fresh-b'],captured_at=[t-.01,t])
 def close_known(self):self.calls.append('close')
class Tests(unittest.TestCase):
 def test_reconcile_entry_never_calls_commit(self):
  with tempfile.TemporaryDirectory(dir=str(Path(__file__).parent)) as root:
   root=Path(root);d=root/'logs'/'energy-claim-evidence'/LEGACY_DIR;d.parent.mkdir(parents=True);shutil.copytree(R,d)
   j=e.Journal(root,LEGACY_RECEIPT);v=j.read();v['pending']=dict(phase='sent',name='여명',quantity=1,boxes_before=49,before_frame_ids=LEGACY_BEFORE,at=LEGACY_AT)
   v['manual_observations']=[dict(event_id='20261102-manual-life-one',name='생명',quantity=1,balancing_only=True)];j.save(v)
   ctx=Context();p=types.SimpleNamespace(character=LEGACY_CHARACTER,level=50,observed=time.monotonic());port=Port()
   a=types.SimpleNamespace(project=types.SimpleNamespace(root=root),_owner_progression_observation=(ctx,p.observed,p.character),_owner_energy_box_port_factory=lambda *args:port)
   import owner_progression,owner_hunt_rules_candidate,owner_skill_goal
   with patch.object(owner_progression,'state',return_value=p),patch.object(owner_hunt_rules_candidate,'configured_identity',return_value='scope'),patch.object(owner_skill_goal,'runtime_ledger',return_value=types.SimpleNamespace(receipt_key=LEGACY_RECEIPT)):
    self.assertEqual(e.run_after_inventory(a,ctx,None),'confirmed')
   self.assertEqual(port.calls,['read_detail','close']);self.assertEqual(j.read()['confirmed']['여명'],1);self.assertIsNone(j.read()['pending'])
 def test_nonlegacy_pending_never_constructs_port(self):
  with tempfile.TemporaryDirectory(dir=str(Path(__file__).parent)) as root:
   root=Path(root);j=e.Journal(root,LEGACY_RECEIPT);v=j.read();v['pending']=dict(phase='sent',name='몽환',quantity=1,operation_id='new-op')
   v['manual_observations']=[dict(event_id='20261102-manual-life-one',name='생명',quantity=1,balancing_only=True)];j.save(v)
   ctx=Context();p=types.SimpleNamespace(character=LEGACY_CHARACTER,level=50,observed=time.monotonic())
   def no_port(*args):raise AssertionError('수령 대기 중 인벤토리 접근 금지')
   a=types.SimpleNamespace(project=types.SimpleNamespace(root=root),_owner_progression_observation=(ctx,p.observed,p.character),_owner_energy_box_port_factory=no_port)
   import owner_progression,owner_hunt_rules_candidate,owner_skill_goal
   with patch.object(owner_progression,'state',return_value=p),patch.object(owner_hunt_rules_candidate,'configured_identity',return_value='scope'),patch.object(owner_skill_goal,'runtime_ledger',return_value=types.SimpleNamespace(receipt_key=LEGACY_RECEIPT)):
    self.assertEqual(e.run_after_inventory(a,ctx,None),'new_reward_evidence_pending')
   self.assertEqual(j.read()['pending']['operation_id'],'new-op')
if __name__=='__main__':unittest.main()
