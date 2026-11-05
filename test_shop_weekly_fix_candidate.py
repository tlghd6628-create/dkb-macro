"""Weekly shop purchase fix: saved 2026-11-05 product frames + fake input only. No game attach.

Run (from the folder that holds the patched copies):
  python -c "import sys,runpy;sys.path.insert(0,'.');sys.argv=['t'];runpy.run_path('test_shop_weekly_fix_candidate.py',run_name='__main__')"
"""
exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import sys,json,tempfile,time,unittest,logging
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path[:1]:sys.path.insert(0,str(HERE))
import numpy as np
from PIL import Image
import owner_shop_runtime_candidate as runtime,owner_membership,owner_progression,owner_quest_preflight,owner_skill_ui
from owner_shop_settings_candidate import ShopSettingsStore,ShopSettings,DEFAULT_COIN_RESERVE
from owner_shop_reader_candidate import find_visible_row
from owner_shop_transaction_candidate import Hold
import owner_timetable
FRAMES=[np.asarray(Image.open(HERE/f'live_fixtures/remote_shop_list_20261105_{n}.png').convert('RGB')) for n in (1,2)]
WANTED=('천요석','강타 도술 강화 요령서','강인 도술 강화 요령서','파멸 도술 강화 요령서')

class _Store(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'settings').mkdir()
  (self.root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'무이2','character_name':'홍짱군'}),encoding='utf8')
  self.profile=runtime.configured_identity(self.root);self.store=ShopSettingsStore(self.root,self.profile)
 def enable_wanted(self,*,master=True,reserve=None):
  doc=self.store.read_document()
  for row in doc['items']:
   if row['shop']=='remote' and row['name'] in WANTED:row.update(enabled=True,mode='max')
  self.store.write(doc['items'],reserve,enabled=master)

class Settings(_Store):
 def test_real_file_shape_master_off_reserve_null_is_the_installed_state(self):
  # Mirrors settings/owner-shop-settings-2a6715f4a2d11f31df0c102a.json as found on 2026-11-05.
  self.enable_wanted(master=False,reserve=None)
  doc=self.store.read_document();self.assertIs(doc['enabled'],False);self.assertIsNone(doc['coin_reserve'])
  self.assertFalse(owner_timetable.shop_selection_enabled(self.root))
  self.assertFalse(owner_timetable.enabled(owner_timetable.BY_KEY['shop'],{'owner_shop.enabled':owner_timetable.shop_selection_enabled(self.root)}))
  with self.assertLogs('project_gui.DKB',level='INFO') as logs:
   self.assertEqual(runtime.dispatch_configured(NS(project=NS(root=self.root)),NS(checkpoint=lambda:None),None),{'status':'no_selection','reason':'설정 상품 구매 사용 꺼짐'})
  self.assertTrue(any('설정 상품 구매 사용 꺼짐' in line for line in logs.output))
 def test_master_on_makes_the_timetable_job_enabled(self):
  self.enable_wanted(master=True,reserve=None)
  self.assertTrue(owner_timetable.shop_selection_enabled(self.root))
  self.assertTrue(owner_timetable.enabled(owner_timetable.BY_KEY['shop'],{'owner_shop.enabled':True}))
class FakeUI:
 def __init__(self,journal):self.journal=journal;self.events=[];self.last_text_frame=np.zeros((479,897,3),dtype=np.uint8);self.context=NS(wait=lambda *a:None,checkpoint=lambda:None)
 def normal(self):return True
 def click(self,x,y,proof):
  if not proof(self.last_text_frame):raise Hold('proof rejected')
  self.events.append({490:'cart',408:'close_popup',507:'add_all',489:'add_one'}.get(x,'open_item'))
 def wait(self,predicate,**kw):pass
 def click_word(self,*a,**k):self.events.append('commit')

class ReserveNull(_Store):
 def go(self,item):
  progress=NS(character='observed-hash',observed=0.)
  def refresh(*args):progress.observed=time.monotonic();return True
  def quote(used):return {'name':item,'click_y':387,'row_proof':lambda f:True,'unit_price':50000,'remaining':10-used,'used':used,'limit':10,'kind':'observed_weekly_quote'}
  balance={'lower':1880000,'upper':1900000,'frame_ids':['a','b']}
  journal=runtime._journal(self.root);ui=FakeUI(journal)
  with patch.object(owner_membership,'paid',return_value=True),patch.object(owner_membership,'open_remote',return_value=ui),patch.object(owner_skill_ui,'SkillUI',return_value=ui),patch.object(owner_quest_preflight,'read_power',side_effect=refresh),patch.object(owner_progression,'state',return_value=progress),patch.object(runtime,'_find_quote',side_effect=[quote(0),quote(10)]),patch.object(runtime,'_total',side_effect=[0,500000,500000,0]),patch.object(runtime,'_popup',return_value=(0,lambda f:True)),patch.object(runtime,'_paired',return_value=True),patch.object(runtime,'_close_known_shop'),patch.object(runtime,'_same_cart',return_value=True):
   return runtime.buy_remote_one(NS(project=NS(root=self.root)),NS(checkpoint=lambda:None),None,item),ui
 def test_master_off_still_holds_each_item(self):
  self.enable_wanted(master=False,reserve=None)
  with self.assertRaises(Hold):self.go('강타 도술 강화 요령서')

class RealFrames(unittest.TestCase):
 """Lossless product frames saved by the program on 2026-11-05 06:12 (remote 잡화 상점, 구매 tab)."""
 def test_frames_are_client_sized_and_differ(self):
  for f in FRAMES:self.assertEqual(f.shape,(479,897,3))
  self.assertFalse(np.array_equal(*FRAMES))
 def test_remote_title_and_empty_cart_pass_on_both_frames(self):
  for f in FRAMES:
   self.assertIsNotNone(owner_membership.hit(f,'remote-shop-title',(35,4,110,30)))
   self.assertTrue(runtime._asset_match(f,'cart-empty',(330,315,242,36)))
 def test_header_coin_found_in_widened_box_only(self):
  for f in FRAMES:
   self.assertFalse(runtime._asset_match(f,'header-coin',(393,8,16,17)))
   self.assertTrue(runtime._asset_match(f,'header-coin',(386,5,26,23)))
 def test_png_variant_is_not_a_threshold_change(self):
  # The original JPEG-cut asset alone still fails these frames; the variant adds a lossless sample at the same .97.
  import cv2
  needle=np.asarray(Image.open(HERE/'assets/shop-rows/cart-empty.png').convert('RGB'))
  for f in FRAMES:
   self.assertLess(float(cv2.matchTemplate(f[315:351,330:572],needle,cv2.TM_CCOEFF_NORMED).max()),.97)
 def test_known_limit_coin_and_weekly_proofs_are_row_phase_specific(self):
  # Documented, NOT fixed here: read_weekly_quote's coin/weekly templates only reach .97 on the
  # row they were cut from (fixture y=111). On these product frames every visible row stays below.
  import cv2
  root=REPO_ASSETS=Path(runtime.__file__).parent/'assets/shop-rows'
  coin=np.asarray(Image.open(root/'coin.png').convert('RGB'));weekly=np.asarray(Image.open(root/'weekly.png').convert('RGB'))
  for y in (157,295,387):
   for f in FRAMES:
    self.assertLess(float(cv2.matchTemplate(f[y+15:y+27,49:62],coin,cv2.TM_CCOEFF_NORMED)[0][0]),.97)
    self.assertLess(float(cv2.matchTemplate(f[y+29:y+39,49:94],weekly,cv2.TM_CCOEFF_NORMED)[0][0]),.97)
 def test_visible_known_rows_agree_across_the_pair(self):
  for name,y in (('영웅 장비 강화 비법서',157),('전설 가호의 정수',295),('연타 도술 강화 요령서',387)):
   self.assertEqual([find_visible_row(f,name) for f in FRAMES],[y,y])
 def test_wanted_items_are_not_template_proved_on_the_first_page(self):
  # 강타 is cut off at the bottom; 파멸·강인·천요석 are below the fold. They go through find_ocr_row, not templates.
  for name in WANTED:
   self.assertEqual([find_visible_row(f,name) for f in FRAMES],[None,None])
if __name__=='__main__':unittest.main(verbosity=2)
