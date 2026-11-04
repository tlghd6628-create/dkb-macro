"""Saved values -> Telegram tables; no game input or real Telegram messages."""
import bootstrap
import copy,json,queue,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from PIL import Image
from io import BytesIO
import owner_growth_current as current
import owner_growth_report as report
import owner_telegram as bot
from owner_gear_settings_candidate import Store
from owner_telegram_ui import TelegramPanel

class Projection(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);(self.root/'settings').mkdir()
  self.set_character('첫캐릭터');self.scope=report.identity(self.root)[0]
 def set_character(self,name):
  (self.root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'테스트서버','character_name':name},ensure_ascii=False),encoding='utf-8')
 def values(self):
  document=Store(self.root,self.scope).read()
  document['skills']['파멸'].update(enabled=True,enhance=49,breakthrough=0)
  document['blessings']['1번'].update(enabled=True,enhance=49,breakthrough=0)
  document['individual']['생명의 흐름']={'enabled':True,'awaken':1,'breakthrough':None}
  Store(self.root,self.scope).write(document)
  current.observe_value(self.root,self.scope,'skills','파멸',{'enhance':19},verified=True)
  current.observe_value(self.root,self.scope,'blessings','1번',{'enhance':30,'breakthrough':0},verified=True)
  current.observe_value(self.root,self.scope,'individual','생명의 흐름',{'awaken':0},verified=True)
 def row(self,snapshot,section,name):
  return next(r for g in snapshot['groups'] if g['key']==section for r in g['rows'] if r['name']==name)
 def test_pc_and_telegram_share_same_values_zero_and_unknown_remain_distinct(self):
  self.values();snapshot=report.project(self.root)
  self.assertEqual(current.current_value(self.root,self.scope,'blessings','1번','enhance'),'30')
  self.assertEqual(self.row(snapshot,'blessings','1번')['current'],'30 / 0')
  self.assertEqual(self.row(snapshot,'skills','파멸')['current'],'19 / 미확인')
  self.assertEqual(self.row(snapshot,'skills','파멸')['target'],'49 / 0')
  self.assertEqual(self.row(snapshot,'individual','생명의 흐름')['current'],'0')
 def test_other_character_never_inherits_old_values_or_goals(self):
  self.values();self.set_character('다른캐릭터');snapshot=report.project(self.root)
  self.assertEqual(self.row(snapshot,'skills','파멸')['current'],'미확인 / 미확인')
  self.assertEqual(self.row(snapshot,'skills','파멸')['target'],'꺼짐')
  self.assertNotIn('첫캐릭터',snapshot['character'])
 def test_snapshot_is_detached_and_does_not_authorize_game_actions(self):
  self.values();snapshot=current.display_snapshot(self.root,self.scope)
  snapshot['values']['skills']['파멸']['values']['enhance']=999
  self.assertEqual(current.current_value(self.root,self.scope,'skills','파멸','enhance'),'19')
  self.assertTrue(snapshot['display_only'])
 def test_unchanged_query_creates_no_settings_and_does_not_write_cache(self):
  before=set(self.root.rglob('*'));report.project(self.root)
  self.assertEqual(set(self.root.rglob('*')),before)
 def test_latest_partial_read_does_not_make_older_field_seem_fresh(self):
  with patch('owner_growth_current.time.time',return_value=1762070400):
   current.observe_value(self.root,self.scope,'skills','파멸',{'breakthrough':1},verified=True)
  with patch('owner_growth_current.time.time',return_value=1762156800):
   current.observe_value(self.root,self.scope,'skills','파멸',{'enhance':49},verified=True)
  row=self.row(report.project(self.root),'skills','파멸')
  self.assertEqual(row['checked_at'],report._stamp(1762070400))
 def test_saved_values_are_visible_after_new_module_load(self):
  self.values();key=str(self.root.resolve());current._LOADED.discard(key)
  for token in list(current._VALUES):
   if token[0]==key:current._VALUES.pop(token)
  self.assertEqual(self.row(report.project(self.root),'blessings','1번')['current'],'30 / 0')
 def test_images_have_character_specific_values_and_bounded_pages(self):
  self.values();snapshot=report.project(self.root);pages=report.sheets(snapshot)
  self.assertTrue(pages)
  for raw,caption in pages:
   im=Image.open(BytesIO(raw));self.assertEqual(im.width,800);self.assertLess(im.height,2000)
  folder=bootstrap.T/'test_scratch/growth_report_preview';folder.mkdir(exist_ok=True)
  (folder/'가호.jpg').write_bytes(pages[0][0]);(folder/'도술.jpg').write_bytes(pages[1][0])
 def test_no_field_copy_changes_intent_or_receipt_files(self):
  self.values();p=self.root/'settings/sent-intent.json';p.write_bytes(b'pending-sent')
  report.sheets(report.project(self.root));self.assertEqual(p.read_bytes(),b'pending-sent')
 def test_different_blessing_in_same_slot_does_not_inherit_old_breakthrough(self):
  current.observe_value(self.root,self.scope,'blessings','1번',{'enhance':50,'breakthrough':2},verified=True,item_identity='itemA')
  current.observe_value(self.root,self.scope,'blessings','1번',{'enhance':0},verified=True,item_identity='itemB')
  self.assertEqual(self.row(report.project(self.root),'blessings','1번')['current'],'0 / 미확인')
 def test_same_blessing_partial_updates_preserve_its_other_verified_fields(self):
  current.observe_value(self.root,self.scope,'blessings','1번',{'enhance':50,'breakthrough':2},verified=True,item_identity='same-item')
  current.observe_value(self.root,self.scope,'blessings','1번',{'enhance':51},verified=True,item_identity='same-item')
  self.assertEqual(self.row(report.project(self.root),'blessings','1번')['current'],'51 / 2')

class Telegram(unittest.TestCase):
 def test_growth_request_keeps_owner_age_and_replay_router_guards(self):
  class Store:
   lock=threading.RLock()
   cfg=bot.Config(token='12345:'+('x'*30),enabled=True,chat_id=123,user_id=123)
   def snapshot(self):return copy.deepcopy(self.cfg)
   def acknowledge(self,ident):
    if ident<=self.cfg.offset:return False
    self.cfg.offset=ident;return True
  store=Store();router=bot.Router(store,started=100)
  def msg(n,chat=123,kind='private',date=101):
   return {'update_id':n,'message':{'chat':{'id':chat,'type':kind},'from':{'id':chat},'date':date,'text':'성장현황'}}
  self.assertEqual(router.handle(msg(1),now=102)['kind'],'growth')
  self.assertIsNone(router.handle(msg(1),now=102))
  self.assertIsNone(router.handle(msg(2,chat=456),now=102))
  self.assertIsNone(router.handle(msg(3,kind='group'),now=102))
  self.assertIsNone(router.handle(msg(4,date=100),now=200))
  numbered=msg(5);numbered['message']['text']='성장현황 2'
  self.assertEqual(router.handle(numbered,now=102)['page'],2)
  numbered=msg(6,chat=456);numbered['message']['text']='성장현황 2'
  self.assertIsNone(router.handle(numbered,now=102))
 def test_button_and_readonly_aliases(self):
  self.assertTrue(any('성장현황' in row for row in bot.KEYBOARD['keyboard']))
  for name in ('성장현황','현재값','/growth'):self.assertEqual(bot.COMMANDS[name],'growth')
 def panel(self):
  panel=object.__new__(TelegramPanel);panel.closed=False;panel.growth_busy=False;panel.events=queue.SimpleQueue()
  panel.gui=S(project=S(root=Path('not-used')),closed=threading.Event())
  panel.watch=[];panel.dialog=None
  return panel
 def test_authenticated_command_calls_readonly_report_not_start(self):
  panel=self.panel();service=Mock();panel.service=service;panel.store=S(snapshot=lambda:S(enabled=True,chat_id=123))
  panel.growth=Mock()
  with patch('owner_controls.run_command',side_effect=AssertionError('no game input')):
   panel.command(service,{'kind':'growth','chat_id':123})
  panel.growth.assert_called_once_with(service,123,page=1)
  panel.growth.reset_mock();panel.command(service,{'kind':'growth','chat_id':456});panel.growth.assert_not_called()
 def test_duplicate_busy_request_does_not_spawn_worker(self):
  panel=self.panel();panel.growth_busy=True;service=Mock()
  with patch('owner_telegram_ui.threading.Thread',side_effect=AssertionError('no duplicate')):
   panel.growth(service,123)
  service.reply.assert_called_once()
 def test_worker_queues_shared_snapshot_without_real_send(self):
  panel=self.panel();service=Mock();workers=[]
  class Thread:
   def __init__(self,target,**kwargs):workers.append(target)
   def start(self):pass
  with patch('owner_telegram_ui.threading.Thread',Thread),patch.object(report,'project',return_value={'identity':'charA'}),patch.object(report,'sheets',return_value=[(b'jpeg','caption')]):
   panel.growth(service,123);workers[0]()
  self.assertEqual(panel.events.get()[0],'growth');service.reply.assert_not_called()
 def test_changed_character_after_render_never_sends_other_character_image(self):
  panel=self.panel();service=Mock();panel.service=service
  panel.events.put(('growth',(service,123,'old-character',[(b'jpeg','caption')],'')))
  with patch.object(report,'identity',return_value=('new-character','new')):panel.poll()
  self.assertFalse(panel.growth_busy)
  service.reply.assert_called_once()
  self.assertNotIn('photo',service.reply.call_args.kwargs)
 def test_old_bot_service_result_is_discarded(self):
  panel=self.panel();old=Mock();panel.service=Mock()
  panel.events.put(('growth',(old,123,'char',[(b'jpeg','caption')],'')))
  panel.poll();old.reply.assert_not_called();panel.service.reply.assert_not_called()
 def test_matching_scope_sends_tables_to_current_authenticated_service(self):
  panel=self.panel();service=Mock();panel.service=service
  panel.events.put(('growth',(service,123,'char',[(b'jpeg','caption')],'')))
  with patch.object(report,'identity',return_value=('char','name')):panel.poll()
  service.reply.assert_called_once_with(123,'caption',photo=b'jpeg')
 def test_large_skill_report_is_bounded_and_explicitly_pageable(self):
  pages=[(b'jpg',str(i)) for i in range(30)]
  first=report.page_batch(pages)
  self.assertEqual(len(first),5);self.assertEqual(first[-1],(None,'다음: 성장현황 2'))
  self.assertEqual(report.page_batch(pages,2)[0][1],'4 · 2/8')
  self.assertIsNone(report.page_batch(pages,99)[0][0])

if __name__=='__main__':unittest.main()
