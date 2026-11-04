"""Saved-game screenshot/OCR validation. Never attaches to the running game."""
exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf-8'))
import time,unittest
from types import SimpleNamespace as NS
from pathlib import Path
from PIL import Image
import numpy as np
from owner_skill_ui import SkillUI
from owner_shop_reader_candidate import read_weekly_quote
from owner_shop_runtime_candidate import _popup,_icon_name,_total,_find_quote
from owner_shop_transaction_candidate import Hold
from owner_progression import resized
from tools.ocr_support import get_paddle_engine

class SavedScreens(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p=Path(__file__).parent/'live_fixtures'
  cls.frames={s:np.asarray(Image.open(p/('remote_shop_'+s+'.jpg')).convert('RGB'))[31:510,1:898,:] for s in ('list_1','list_2','quantity_hero_1','quantity_hero_2','cart_hero_1','cart_hero_2')}
  cls.ui=SkillUI.__new__(SkillUI);cls.ui.adapter=NS(project=NS(root=A));cls.ui.context=NS(wait=time.sleep,checkpoint=lambda:None);cls.ui.read_worker=None
  list(get_paddle_engine(A,language='korean').predict(resized(cls.frames['list_1'],(40,111,145,45))))
  cls.ui.frame=lambda:cls.frames['list_1'].copy()
  cls.quote=read_weekly_quote(cls.ui,'영웅 장비 강화 비법서')
 def test_name_price_quota_and_zero_total(self):
  self.ui.frame=lambda:self.frames['list_1'].copy()
  self.assertEqual((self.quote['unit_price'],self.quote['used'],self.quote['limit']),(15000,0,50))
  self.assertEqual(_total(self.ui),0)
 def test_potion_buy_available_label_does_not_infer_reset(self):
  self.ui.frame=lambda:self.frames['list_1'].copy()
  quote=read_weekly_quote(self.ui,'1단 체력 회복 물약')
  self.assertEqual((quote['unit_price'],quote['remaining'],quote['limit'],quote['kind']),
                   (100,649,650,'observed_available_quote'))
 def test_known_list_entry_path_and_quote_on_saved_screenshot(self):
  self.ui.frame=lambda:self.frames['list_1'].copy()
  quote=_find_quote(self.ui,'영웅 장비 강화 비법서')
  self.assertEqual((quote['row_y'],quote['unit_price'],quote['remaining']),(111,15000,50))
 def test_popup_and_cart_both_frames_and_switched_item(self):
  icons=self.quote['icons'];name='영웅 장비 강화 비법서'
  for n in (1,2):
   popup=self.frames[f'quantity_hero_{n}'];cart=self.frames[f'cart_hero_{n}']
   self.assertEqual(_icon_name(popup,icons,'popup'),name);self.assertEqual(_icon_name(cart,icons,'cart'),name)
   self.ui.frame=lambda:popup.copy()
   with self.assertRaises(Hold):_popup(self.ui,15000,'전설 장비 강화 비법서',icons)
  self.ui.frame=lambda:self.frames['quantity_hero_1'].copy()
  self.assertEqual(_popup(self.ui,15000,name,icons)[0],116)
  with self.assertRaises(Hold):_popup(self.ui,50000,name,icons)
 def test_cart_total_from_actual_frame(self):
  self.ui.frame=lambda:self.frames['cart_hero_1'].copy()
  self.assertEqual(_total(self.ui),15000)
 def test_blessing_popup_is_never_accepted_as_equipment(self):
  icons=self.quote['icons'];p=Path(__file__).parent/'live_fixtures'
  for n in (1,2):
   frame=np.asarray(Image.open(p/f'remote_quantity_hero_blessing_{n}.jpg').convert('RGB'))[31:510,1:898,:]
   self.assertEqual(_icon_name(frame,icons,'popup'),'영웅 가호의 정수')
   self.ui.frame=lambda:frame.copy()
   with self.assertRaises(Hold):_popup(self.ui,15000,'영웅 장비 강화 비법서',icons)
  self.ui.frame=lambda:frame.copy()
  self.assertEqual(_popup(self.ui,15000,'영웅 가호의 정수',icons)[0],0)
if __name__=='__main__':unittest.main(verbosity=2)
