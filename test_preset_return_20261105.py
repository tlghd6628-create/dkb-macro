"""Preset 1 return after a stop, and the skill list reader, with fakes only. Never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,tempfile,unittest
from types import SimpleNamespace as S
from unittest.mock import patch,Mock
import owner_skill_ui
from owner_skill_goal import Pending
from owner_single_preset import resume,_flag


class Return(unittest.TestCase):
 def setUp(self):
  self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup);root=Path(self.dir.name);(root/'settings').mkdir()
  self.adapter=S(project=S(root=root));self.context=S(checkpoint=lambda:None);self.ui=Mock()
 def test_no_flag_touches_nothing(self):
  with patch.object(owner_skill_ui,'SkillUI',side_effect=AssertionError('no input')):
   self.assertFalse(resume(self.adapter,self.context,None))
 def test_flag_goes_back_then_clears(self):
  _flag(self.adapter).write_text('1')
  with patch.object(owner_skill_ui,'SkillUI',return_value=self.ui):self.assertTrue(resume(self.adapter,self.context,None))
  self.ui.select_preset.assert_called_once_with(1);self.ui.close_known.assert_called_once();self.assertFalse(_flag(self.adapter).exists())
 def test_failed_return_keeps_the_flag_for_the_next_run(self):
  _flag(self.adapter).write_text('1');self.ui.select_preset.side_effect=Pending('메뉴')
  with patch.object(owner_skill_ui,'SkillUI',return_value=self.ui):self.assertFalse(resume(self.adapter,self.context,None))
  self.assertTrue(_flag(self.adapter).exists())


def row(text,y,score=.95,x=760):return {'text':text,'y':y,'x':x,'score':score}


class Rows(unittest.TestCase):
 def ui(self,*reads):
  reads=iter(reads);holder=S(public={'all_skill_names':{'사격':{'id':1},'찌르기':{'id':2}}},context=S(wait=lambda *_:None))
  def batch(specs):holder._owner_last_rows_raw=([None,None],[0,0],[next(reads)]);return [[]]
  holder.rows_batch=batch
  return holder
 def read(self,holder):return owner_skill_ui.SkillUI.skill_rows(holder)
 def test_stray_text_in_one_frame_does_not_hold_the_list(self):
  found=self.read(self.ui(([row('사격',100),row('무의미',200)],[row('사격',100)])))
  self.assertEqual([r['id'] for r in found],[1])
 def test_a_low_score_in_the_other_frame_still_agrees(self):
  found=self.read(self.ui(([row('사격',100,.9)],[row('사격',101,.8)])))
  self.assertEqual(found,[])  # agreed, but this frame's own score is under the reader's floor
 def test_a_gliding_list_waits_until_names_agree(self):
  found=self.read(self.ui(([row('사격',100)],[row('사격',130)]),([row('사격',130)],[row('사격',130)])))
  self.assertEqual(found[0]['y'],130)
 def test_never_agreeing_is_still_pending(self):
  bad=([row('사격',100)],[row('찌르기',100)])
  with self.assertRaises(Pending):self.read(self.ui(*[bad]*8))


if __name__=='__main__':unittest.main()
