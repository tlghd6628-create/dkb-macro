"""Skill styles short of materials rest until a wake. Fake adapter; not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from types import SimpleNamespace as S
import owner_skill_growth_candidate as sg
import owner_worn_growth as wg

class SkillRest(unittest.TestCase):
    def test_short_style_rests_and_a_wake_clears_it(self):
        adapter=S();ui=S(adapter=adapter)
        doc={'skills':{'강타':{'enabled':True},'파멸':{'enabled':True},'강인':{'enabled':False}}}
        self.assertFalse(sg.style_resting(ui,'강타'))
        sg.rest_style(ui,'강타');self.assertTrue(sg.style_resting(ui,'강타'));self.assertFalse(sg.all_styles_resting(adapter,doc))
        sg.rest_style(ui,'파멸');self.assertTrue(sg.all_styles_resting(adapter,doc))
        wg.wake(adapter);self.assertFalse(sg.style_resting(ui,'강타'))

if __name__=='__main__':unittest.main()
