"""Read-only OCR/selection checks. No game process, input, or purchase."""
exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf-8'))
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from owner_shop_reader_candidate import displayed_balance_interval,scan_current_town,balance_observation
from owner_shop_settings_candidate import ShopSettingsStore
from owner_shop_transaction_candidate import ShopJournal,Hold

class Reader(unittest.TestCase):
 def test_compact_bounds_and_invalid_formats(self):
  self.assertEqual(displayed_balance_interval('567.22K')['lower'],567210)
  self.assertEqual(displayed_balance_interval('5.42M')['lower'],5410000)
  self.assertEqual(displayed_balance_interval('100,000')['lower'],100000)
  for value in ('1.2','-1K','inf','12K9','NaN',None,'1,2,3K'):
   self.assertIsNone(displayed_balance_interval(value))
  self.assertIsNone(balance_observation([{'text':'1000','score':.99},{'text':'2000','score':.99}]))
  self.assertIsNone(balance_observation([{'text':'1000','score':float('nan')}]))
 def test_selected_only_and_pending_are_never_authorized(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);store=ShopSettingsStore(root,'server / char');doc=store.read_document()
   name='영웅 장비 강화 비법서';next(x for x in doc['items'] if x['shop']=='town' and x['name']==name)['enabled']=True
   store.write(doc['items'],doc['coin_reserve']);journal=ShopJournal(root/'settings/journal.json')
   calls=[]
   def rows(box,**kwargs):
    calls.append(box)
    if box==(32,0,110,34):return [{'text':'잡화상점','score':.99}]
    if box==(392,2,63,26):return [{'text':'5.42M','score':.99}]
    if box==(44,109,145,47):return [{'text':name,'score':.99}]
    return [{'text':'다른 물건','score':.99}]
   out=scan_current_town(SimpleNamespace(rows=rows),root,'server / char',journal)
   self.assertEqual(len(calls),8);self.assertEqual([x['name'] for x in out['items']],[name])
   self.assertEqual(out['balance_interval']['lower'],5410000);self.assertFalse(out['purchase_permitted'])
   self.assertFalse(out['items'][0]['purchase_permitted']);self.assertFalse(journal.path.exists())
 def test_wrong_heading_stops_before_scanning(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);store=ShopSettingsStore(root,'test');d=store.read_document();d['items'][0]['enabled']=True;store.write(d['items'],d['coin_reserve'])
   calls=[]
   def rows(box,**kw):calls.append(box);return [{'text':'도술 상점','score':.99}]
   with self.assertRaises(Hold):scan_current_town(SimpleNamespace(rows=rows),root,'test',ShopJournal(root/'j.json'))
   self.assertEqual(len(calls),1)
 def test_observed_items_are_added_per_shop_disabled_without_changing_existing_choices(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=ShopSettingsStore(Path(tmp),'profile');doc=store.read_document();doc['items'][0]['enabled']=True
   store.write(doc['items'],100000)
   self.assertEqual(store.merge_observed('remote',['미확인 새 품목','미확인 새 품목']),['미확인 새 품목'])
   saved=store.read_document();added=[r for r in saved['items'] if r['name']=='미확인 새 품목']
   self.assertEqual(len(added),1);self.assertEqual(added[0]['shop'],'remote');self.assertFalse(added[0]['enabled'])
   self.assertTrue(saved['items'][0]['enabled']);self.assertEqual(saved['coin_reserve'],100000)
 def test_dynamic_name_requires_unique_identical_high_confidence_pair(self):
  from owner_shop_reader_candidate import find_ocr_row
  frame=np.zeros((479,897,3),dtype=np.uint8)
  class UI:
   def __init__(self,answers):self.answers=answers
   def rows(self,*a,**kw):self._owner_last_rows_pair=([frame.copy(),frame.copy()],[1.,1.2],self.answers);return self.answers[1]
  hit={'text':'새로운 물건','score':.98,'y':120}
  self.assertEqual(find_ocr_row(UI([[hit],[hit]]),'새로운 물건')['y'],111)
  self.assertIsNone(find_ocr_row(UI([[hit],[dict(hit,score=.6)]]),'새로운 물건'))
  self.assertIsNone(find_ocr_row(UI([[hit,hit],[hit]]),'새로운 물건'))
  self.assertIsNone(find_ocr_row(UI([[hit],[dict(hit,text='다른 물건')]]),'새로운 물건'))
 def test_dynamic_quote_requires_fresh_row_and_never_authorizes_a_transaction(self):
  from PIL import Image
  from owner_shop_reader_candidate import read_weekly_quote
  from owner_shop_runtime_candidate import _icon_name
  frame=np.asarray(Image.open(Path(__file__).parent/'live_fixtures'/'remote_shop_list_1.jpg').convert('RGB'))[31:510,1:898,:]
  class UI:
   context=SimpleNamespace(wait=lambda *_:None)
   def frame(self):return frame.copy()
   def rows(self,box,**kwargs):
    rows=([{'text':'신규 상품','score':.99,'y':120}] if box==(44,61,153,370) else
          [{'text':'15,000','score':.99},{'text':'도사(0/50)','score':.99}])
    self._owner_last_rows_pair=([frame.copy(),frame.copy()],[1.,1.2],[rows,rows]);return rows
  quote=read_weekly_quote(UI(),'신규 상품')
  self.assertEqual((quote['unit_price'],quote['remaining']),(15000,50));self.assertTrue(quote['row_proof'](frame))
  popup=np.zeros((479,897,3),dtype=np.uint8)
  self.assertIsNone(_icon_name(popup,quote['icons'],'popup'))
 def test_runtime_method_uses_configured_profile_and_read_only_ui(self):
  import json,owner_shop_runtime_candidate as runtime,owner_skill_ui
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'settings').mkdir()
   (root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'S','character_name':'C'}),encoding='utf8')
   store=ShopSettingsStore(root,runtime.configured_identity(root));d=store.read_document();name=d['items'][0]['name'];d['items'][0]['enabled']=True;store.write(d['items'],d['coin_reserve'])
   def rows(box,**kwargs):
    if box==(32,0,110,34):return [{'text':'잡화상점','score':.99}]
    if box==(44,109,145,47):return [{'text':name,'score':.99}]
    return []
   adapter=SimpleNamespace(project=SimpleNamespace(root=root));context=SimpleNamespace(checkpoint=lambda:None)
   with patch.object(owner_skill_ui,'SkillUI',return_value=SimpleNamespace(rows=rows)):
    result=runtime.inspect_current_shop(adapter,context,None)
   self.assertEqual(result['items'][0]['name'],name);self.assertFalse(result['purchase_permitted'])
   self.assertFalse((root/'settings/owner-shop-journal.json').exists())
   (root/'settings/manager_identity.json').write_text('{}',encoding='utf8')
   with self.assertRaises(Hold):runtime.inspect_current_shop(adapter,context,None)
 def test_actual_remote_names_match_only_exact_observed_rows(self):
  import numpy as np
  from PIL import Image
  from owner_shop_reader_candidate import identify_shop_row,find_visible_row,OBSERVED_NAMES
  frames=[np.asarray(Image.open(Path(__file__).parent/'live_fixtures'/f'remote_shop_list_{n}.jpg').convert('RGB'))[31:510,1:898,:] for n in (1,2)]
  for frame in frames:
   for row,name in enumerate(OBSERVED_NAMES):
    self.assertEqual(identify_shop_row(frame,row),name);self.assertEqual(find_visible_row(frame,name),65+46*row)
  self.assertIsNone(identify_shop_row(np.zeros((479,897,3),dtype=np.uint8),1))
  # Synthetic vertical offset checks recognition only, not native scrolling.
  shifted=frames[0].copy();shifted[64:435,49:165]=0
  shifted[173:187,49:165]=frames[0][111:125,49:165]
  self.assertEqual(find_visible_row(shifted,'영웅 장비 강화 비법서'),173)
if __name__=='__main__':unittest.main(verbosity=2)
