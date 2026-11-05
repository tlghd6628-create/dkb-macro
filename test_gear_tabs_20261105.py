"""Gear subtabs named by their words, on one saved frame and plain rows. Never a game test."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap,unittest
import numpy as np
from PIL import Image
import owner_gear_extra_runtime_candidate as extra


def row(text,y,score=.95):return {'text':text,'y':y,'score':score}
FOUR=[row('강화',80),row('돌파',114),row('각성',145),row('재조율',179)]
THREE=[row('강화',80),row('각성',114),row('재조율',145)]


class Words(unittest.TestCase):
 def setUp(self):
  saved=dict(extra.TABS);self.addCleanup(lambda:(extra.TABS.clear(),extra.TABS.update(saved)))
 def test_four_tabs(self):
  self.assertEqual(extra.tabs_from_rows(FOUR),{'enhance':70,'breakthrough':104,'awaken':135,'reroll':169})
 def test_three_tabs_put_reroll_where_awaken_used_to_be(self):
  found=extra.tabs_from_rows(THREE)
  self.assertNotIn('breakthrough',found);self.assertEqual(found['awaken'],104);self.assertEqual(found['reroll'],135)
 def test_an_unread_list_is_not_trusted(self):
  self.assertIsNone(extra.tabs_from_rows([row('강화',80)]));self.assertIsNone(extra.tabs_from_rows([row('강화',80),row('각성',114,.5)]))
 def test_the_bright_tab_follows_the_layout(self):
  frame=np.zeros((479,897,3),dtype=np.uint8);frame[135:155,14:73]=255
  self.assertTrue(extra.tab_selected(frame,'awaken'))
  extra.TABS.clear();extra.TABS.update(extra.tabs_from_rows(THREE))
  self.assertFalse(extra.tab_selected(frame,'awaken'));self.assertTrue(extra.tab_selected(frame,'reroll'))
  self.assertFalse(extra.tab_selected(frame,'breakthrough'))


if __name__=='__main__':unittest.main()
