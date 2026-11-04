"""Offline evidence wiring checks; no GUI, game, input or server access."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bootstrap
import base64,json,queue,sqlite3,tempfile,threading,unittest,zipfile
from datetime import datetime,timezone
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from PIL import Image
import owner_scene_archive as scenes
import owner_manual_diagnostics as manual
from owner_reward_action_test import OneAction


class Scope(unittest.TestCase):
    def test_nested_and_exception_restore_worker_context(self):
        before=getattr(scenes.LOCAL,'owner',None);source=getattr(scenes.LOCAL,'source',None)
        with scenes.capture_scope('outer','ctx'):
            with self.assertRaises(RuntimeError):
                with scenes.capture_scope('inner','ctx2','reward_test'):
                    self.assertEqual(scenes.LOCAL.owner,('inner','ctx2'))
                    self.assertEqual(scenes.LOCAL.source,'reward_test')
                    raise RuntimeError('fixture')
            self.assertEqual(scenes.LOCAL.owner,('outer','ctx'))
            self.assertEqual(scenes.LOCAL.source,'runtime_capture')
        self.assertEqual(scenes.LOCAL.owner,before);self.assertEqual(scenes.LOCAL.source,source)

    def test_test_preparation_and_native_action_share_existing_capture_scope(self):
        adapter=object();ctx=S(checkpoint=Mock(),run_action=Mock());events=queue.Queue();observations=[]
        def existing(*args):observations.append((scenes.LOCAL.owner,scenes.LOCAL.source));return True
        with patch('owner_reward_action_test.prepare',side_effect=existing),patch('owner_reward_action_test.execute',side_effect=existing):
            OneAction(adapter,'auto_rewards.mail.enabled',None,events).run(ctx,None)
        self.assertEqual(observations,[((adapter,ctx),'reward_test')]*2)
        self.assertIsNone(scenes.LOCAL.owner)

    def test_cancelled_test_restores_capture_scope(self):
        from biol_base.session import Cancelled
        ctx=S(checkpoint=Mock(),run_action=Mock())
        with patch('owner_reward_action_test.prepare',side_effect=Cancelled('fixture')):
            with self.assertRaises(Cancelled):OneAction(object(),'auto_rewards.mail.enabled',None,queue.Queue()).run(ctx,None)
        self.assertIsNone(scenes.LOCAL.owner)

    def test_worker_local_is_not_inherited_by_another_thread(self):
        found=[]
        with scenes.capture_scope('adapter','context','reward_test'):
            thread=threading.Thread(target=lambda:found.append(getattr(scenes.LOCAL,'owner',None)))
            thread.start();thread.join(1)
        self.assertEqual(found,[None])


class Transmission(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'app/vendor/DKB_Auto';(self.root/'logs').mkdir(parents=True)
        (self.root/'logs/2026-11-03.log').write_text('2026-11-03 23:00:00,000 INFO fixture\n',encoding='utf8')
        self.device={'device':'test-device','alias':'test','token':'fake-only'}
        self.folder=self.root/'logs/scene-corpus';self.folder.mkdir()
        with self.db() as db:db.execute('CREATE TABLE scenes (relative_dir TEXT, observed_at TEXT)')
    def db(self):return sqlite3.connect(self.folder/'index.sqlite3')
    def scene(self,n=0,*,game_only=True,size=(897,479),relative=None):
        relative=relative or ('20261103/20261103T2300%02d-%08x'%(n,n))
        path=self.folder/relative;path.mkdir(parents=True)
        Image.new('RGB',size,(n,30,40)).save(path/'screen.png')
        (path/'observation.json').write_text(json.dumps({'game_only':game_only,'source':'reward_test',
            'observed_at':'2026-11-03T23:00:00','password':'secret-fixture','recent_events':[{'message':'test'}]}),encoding='utf8')
        with self.db() as db:db.execute('INSERT INTO scenes VALUES (?,?)',(relative,'%04d'%n))
        return path
    def make(self):return manual.create_snapshot(self.root,{'status':'stopped'},self.device,moment=datetime(2026,11,3,14,5,tzinfo=timezone.utc))
    def test_scene_metadata_picture_and_acknowledged_upload(self):
        path=self.scene();original=(path/'observation.json').read_bytes();job,archive=self.make()
        with zipfile.ZipFile(archive) as z:
            receipt=json.loads(z.read('summary.json'))
            self.assertEqual(receipt['scene_evidence']['screens'],1)
            self.assertEqual(receipt['incidents'],[])
            self.assertEqual(receipt['pictures'][0]['evidence_kind'],'retained_scene')
            detail=json.loads(z.read(receipt['details'][0]['entry']))
            self.assertEqual(detail['observation']['password'],'[REDACTED]')
            self.assertEqual(detail['observation']['source'],'reward_test')
            self.assertIsNone(z.testzip())
        sent=[]
        def sender(route,data,token):
            sent.append((route,data))
            return {'accepted':[e['id'] for e in data['events']]} if route=='/v1/events' else {'sha256':data['sha256'],'stored':True}
        for _ in range(15):
            state=manual.send_step(self.root,job,self.device,sender)
            if state['phase']=='sent':break
        self.assertEqual(state['phase'],'sent');self.assertEqual(state['picture_cursor'],1)
        self.assertEqual((path/'observation.json').read_bytes(),original)
        self.assertEqual(sum(route=='/v1/attachment' for route,_ in sent),1)

    def test_invalid_metadata_and_non_game_images_skip_without_losing_logs(self):
        self.scene(0,game_only=False);self.scene(1,size=(1920,1080))
        path=self.scene(2);(path/'observation.json').write_text('{broken',encoding='utf8')
        _,archive=self.make()
        with zipfile.ZipFile(archive) as z:
            receipt=json.loads(z.read('summary.json'));self.assertEqual(receipt['pictures'],[])
            self.assertEqual(receipt['log_lines'],1);self.assertEqual(receipt['scene_evidence']['skipped'],3)

    def test_bounded_recent_thirty_and_no_full_folder_scan(self):
        for n in range(32):self.scene(n)
        _,archive=self.make()
        with zipfile.ZipFile(archive) as z:
            receipt=json.loads(z.read('summary.json'));self.assertEqual(len(receipt['pictures']),30)
            dirs=[json.loads(z.read(d['entry']))['scene_relative_dir'] for d in receipt['details']]
            self.assertFalse(any(p.endswith('-00000000') or p.endswith('-00000001') for p in dirs))

    def test_corrupt_index_and_traversal_do_not_abort_diagnostic(self):
        with self.db() as db:db.execute('INSERT INTO scenes VALUES (?,?)',('../../outside','9999'))
        _,archive=self.make()
        with zipfile.ZipFile(archive) as z:self.assertEqual(json.loads(z.read('summary.json'))['scene_evidence']['skipped'],1)
        (self.folder/'index.sqlite3').write_bytes(b'broken')
        _,archive=self.make()
        with zipfile.ZipFile(archive) as z:
            receipt=json.loads(z.read('summary.json'));self.assertEqual(receipt['log_lines'],1)
            self.assertEqual(receipt['scene_evidence']['reason'],'scene index unavailable')


class InventoryEntry(unittest.TestCase):
    def service(self,hit=None):return S(capture=Mock(return_value='frame'),detector=S(entries={'버튼_인벤토리':{}},find=Mock(return_value=hit)))
    def test_missing_explicit_ordinary_icon_reuses_existing_key_entry(self):
        from owner_progression import open_inventory_entry
        ordinary=Mock();service=self.service()
        with patch('owner_progression.open_inventory_by_key',return_value=True) as key:
            self.assertTrue(open_inventory_entry(service,ordinary,click_button='버튼_인벤토리',timeout=10))
        key.assert_called_once_with(service);ordinary.assert_not_called()
    def test_visible_icon_and_different_explicit_entry_keep_original(self):
        from owner_progression import open_inventory_entry
        for service,kw in ((self.service((1,2,())),{'click_button':'버튼_인벤토리'}),
                           (self.service(),{'click_button':'other-original-entry'})):
            ordinary=Mock(return_value=True)
            with patch('owner_progression.open_inventory_by_key') as key:self.assertTrue(open_inventory_entry(service,ordinary,**kw))
            ordinary.assert_called_once_with(service,**kw);key.assert_not_called()
    def test_failed_key_proof_does_not_fall_through_to_click(self):
        from owner_progression import open_inventory_entry
        ordinary=Mock()
        with patch('owner_progression.open_inventory_by_key',side_effect=RuntimeError('fixture')):
            with self.assertRaisesRegex(RuntimeError,'fixture'):open_inventory_entry(self.service(),ordinary,click_button='버튼_인벤토리')
        ordinary.assert_not_called()


if __name__=='__main__':unittest.main()
