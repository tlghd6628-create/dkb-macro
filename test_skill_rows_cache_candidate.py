"""No game input: synthetic OCR and frame captures test cache semantics."""
import sys,time,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_skill_ui as mod

class Engine:
 def __init__(self):self.calls=0
 def predict(self,roi):
  self.calls+=1
  return [{'rec_texts':['확인'],'rec_scores':[.99],
           'rec_polys':[np.array([[40,40],[60,40],[60,60],[40,60]])]}]

class Tests(unittest.TestCase):
 def setUp(self):
  self.eng=Engine();self.calls=0;self.image=np.zeros((479,897,3),dtype=np.uint8)
  self.ui=object.__new__(mod.SkillUI);self.ui.read_worker=None
  self.ui.context=SimpleNamespace(wait=lambda sec:time.sleep(.001),checkpoint=lambda:None,stop=threading.Event())
  self.ui.adapter=SimpleNamespace(project=SimpleNamespace(root='fake-root'))
  self.ui._owner_batch_warmed={'korean':self.eng,'number':self.eng}
  def frame():self.calls+=1;return self.image.copy()
  self.ui.frame=frame
  self.get=patch('tools.ocr_support.get_paddle_engine',side_effect=lambda *a,**k:self.eng)
  self.resize=patch('owner_progression.resized',side_effect=lambda frame,box:frame)
  self.get.start();self.resize.start();self.addCleanup(self.get.stop);self.addCleanup(self.resize.stop)
 def test_two_fresh_captures_with_exact_reuse(self):
  a=self.ui.rows((10,10,10,10));self.assertEqual(self.calls,2);self.assertEqual(self.eng.calls,1)
  b=self.ui.rows((10,10,10,10));self.assertEqual(self.calls,4);self.assertEqual(self.eng.calls,1);self.assertEqual(a,b)
  # A consumer mutating its result cannot modify a subsequent cache hit.
  a[0]['text']='다름';self.assertEqual(self.ui.rows((10,10,10,10))[0]['text'],'확인')
 def test_gray_retry_is_opt_in_and_keeps_raw_pair_and_cache_separate(self):
  self.image[:,:,0]=180;self.image[:,:,1]=80
  seen=[];original=self.eng.predict
  self.eng.predict=lambda image:(seen.append(image.copy()) or original(image))
  self.ui.rows((10,10,10,10));self.ui.rows((10,10,10,10),text_mode='gray')
  self.assertEqual(len(seen),2);self.assertTrue(np.array_equal(seen[1][:,:,0],seen[1][:,:,1]))
  self.assertFalse(np.array_equal(seen[0][:,:,0],seen[0][:,:,1]))
  self.assertTrue(np.array_equal(self.ui._owner_last_rows_pair[0][0],self.image))
  self.ui.rows((10,10,10,10));self.assertEqual(self.eng.calls,2)
 def test_pixel_language_and_roi_changes_miss(self):
  self.ui.rows((10,10,10,10));self.image[10,10,0]=1
  self.ui.rows((10,10,10,10));self.assertEqual(self.eng.calls,2)
  self.ui.rows((10,10,10,10),language='number');self.assertEqual(self.eng.calls,3)
  self.ui.rows((11,10,10,10));self.assertEqual(self.eng.calls,4)
 def test_different_fresh_frames_still_require_ocr_agreement(self):
  def frame():
   self.calls+=1;img=self.image.copy();img[10,10,0]=self.calls%2;return img
  self.ui.frame=frame
  def predict(img):
   self.eng.calls+=1
   return [{'rec_texts':['다름' if img[10,10,0] else '확인'],
            'rec_scores':[.99],'rec_polys':[np.array([[40,40],[60,40],[60,60],[40,60]])]}]
  self.eng.predict=predict
  with self.assertRaises(mod.Pending):self.ui.rows((10,10,10,10))
  self.assertEqual(self.calls,2);self.assertEqual(self.eng.calls,2)
 def test_new_model_and_context_do_not_reuse(self):
  self.ui.rows((10,10,10,10));old=self.eng;self.eng=Engine()
  self.ui.rows((10,10,10,10));self.assertEqual(old.calls,1);self.assertEqual(self.eng.calls,1)
  self.ui.context=SimpleNamespace(wait=lambda sec:time.sleep(.001),checkpoint=lambda:None,stop=threading.Event())
  self.ui.rows((10,10,10,10));self.assertEqual(self.eng.calls,2)
 def test_stop_close_discards_cache_before_any_input(self):
  self.ui.rows((10,10,10,10));self.ui.context.stop.set();self.ui.close_known()
  self.assertIsNone(self.ui._owner_rows_cache);self.assertIsNone(self.ui._owner_rows_context)
 def test_lru_and_bytes_bounded(self):
  cache=mod.ExactRowsCache(max_entries=2,max_bytes=1000);engine=object()
  for n in range(3):
   frame=np.full((2,2,3),n,dtype=np.uint8);key=cache.key(frame,(0,0,2,2),'x',engine);cache.put(key,[{'text':'x'}])
  self.assertEqual(len(cache.data),2);self.assertLessEqual(cache.bytes,1000)
  huge=mod.ExactRowsCache(max_entries=64,max_bytes=4);key=huge.key(np.zeros((2,2,3),dtype=np.uint8),(0,0,2,2),'x',engine)
  huge.put(key,[{'text':'x'}]);self.assertEqual(len(huge.data),0)
 def test_batch_uses_only_two_captures_and_separate_rois(self):
  out=self.ui.rows_batch([((10,10,10,10),'korean',.9),((20,20,10,10),'number',.9)])
  self.assertEqual(self.calls,2);self.assertEqual(len(out),2);self.assertEqual(self.eng.calls,2)
  self.ui.rows_batch([((10,10,10,10),'korean',.9),((20,20,10,10),'number',.9)])
  self.assertEqual(self.calls,4);self.assertEqual(self.eng.calls,2)
 def test_batch_changed_frame_text_fails_pair(self):
  def frame():
   self.calls+=1;img=self.image.copy();img[10,10,0]=self.calls%2;return img
  self.ui.frame=frame
  def predict(img):
   self.eng.calls+=1
   return [{'rec_texts':['다름' if img[10,10,0] else '확인'], 'rec_scores':[.99],
            'rec_polys':[np.array([[40,40],[60,40],[60,60],[40,60]])]}]
  self.eng.predict=predict
  with self.assertRaises(mod.Pending):self.ui.rows_batch([((10,10,10,10),'korean',.9)])
  self.assertEqual(self.calls,2)
 def test_batch_initializes_before_first_capture(self):
  self.ui._owner_batch_warmed={};order=[];capture=self.ui.frame
  self.ui.frame=lambda:(order.append('capture') or capture())
  predict=self.eng.predict
  def marked(image):order.append('ocr');return predict(image)
  self.eng.predict=marked
  self.ui.rows_batch([((10,10,10,10),'korean',.9)])
  self.assertEqual(order[0],'ocr');self.assertEqual(self.calls,2)
 def test_batch_raw_observation_metadata_does_not_change_action_filter_or_run_extra_ocr(self):
  out=self.ui.rows_batch([((10,10,10,10),'korean',.9,'original',lambda row:False)])
  self.assertEqual(out,[[]]);self.assertEqual(self.calls,2);self.assertEqual(self.eng.calls,1)
  frames,ticks,raw=self.ui._owner_last_rows_raw
  self.assertEqual(len(frames),2);self.assertEqual(raw[0][0][0]['text'],'확인')
  raw[0][0][0]['text']='not cached'
  self.assertEqual(self.ui.rows((10,10,10,10))[0]['text'],'확인')
  self.assertIsNone(self.ui._owner_last_rows_raw)
 def test_explicit_balance_agreement_can_accept_income_but_not_decrease(self):
  from owner_skill_growth_candidate import nondecreasing_balance
  def frame():
   self.calls+=1;img=self.image.copy();img[10,10,0]=self.calls%2;return img
  self.ui.frame=frame
  def predict(img):
   self.eng.calls+=1
   return [{'rec_texts':['612.93K' if img[10,10,0] else '613.01K'], 'rec_scores':[.99],
    'rec_polys':[np.array([[40,40],[60,40],[60,60],[40,60]])]}]
  self.eng.predict=predict
  result=self.ui.rows_batch([((10,10,10,10),'number',.90,'original',None,nondecreasing_balance)])
  self.assertEqual(result[0][0]['text'],'613.01K');self.assertEqual(self.eng.calls,2)
  self.calls=1
  with self.assertRaises(mod.Pending):self.ui.rows_batch([((10,10,10,10),'number',.90,'original',None,nondecreasing_balance)])
 def test_numeric_alternate_runs_only_after_failed_original_on_same_frames(self):
  from owner_skill_growth_candidate import numeric_pair_verifier
  def predict(img):
   self.eng.calls+=1
   return [{'rec_texts':['10/1'],'rec_scores':[.95 if self.eng.calls==1 else .999],
    'rec_polys':[np.array([[40,40],[60,40],[60,60],[40,60]])]}]
  self.eng.predict=predict
  result=self.ui.rows_batch([((10,10,10,10),'number',.98,'original_or_clahe',None,numeric_pair_verifier('ratio'))])
  self.assertEqual(result[0][0]['text'],'10/1');self.assertEqual(self.eng.calls,2);self.assertEqual(self.calls,2)
  # A healthy original pair performs one inference for equal cached frames.
  self.image[10,10,0]=5;self.eng.calls=1
  result=self.ui.rows_batch([((10,10,10,10),'number',.98,'original_or_clahe',None,numeric_pair_verifier('ratio'))])
  self.assertEqual(self.eng.calls,2);self.assertEqual(self.calls,4)
 def test_red_count_is_read_through_the_brightest_channel(self):
  from owner_skill_growth_candidate import numeric_pair_verifier
  def frame():
   self.calls+=1;img=self.image.copy();img[10,10,0]=self.calls%2;return img
  self.ui.frame=frame;modes=[]
  def predict(img):
   self.eng.calls+=1;modes.append(self.eng.calls)
   return [{'rec_texts':['/5' if self.eng.calls<=4 else '3/5'],'rec_scores':[.999],
    'rec_polys':[np.array([[40,40],[60,40],[60,60],[40,60]])]}]
  self.eng.predict=predict
  rows=self.ui.rows_batch([((10,10,10,10),'number',.98,'original_or_clahe',None,numeric_pair_verifier('ratio'))])
  self.assertEqual(rows[0][0]['text'],'3/5');self.assertEqual(len(modes),6)
 def test_conflicting_high_confidence_alternates_cannot_select_convenient_value(self):
  from owner_skill_growth_candidate import numeric_pair_verifier
  def frame():
   self.calls+=1;img=self.image.copy();img[10,10,0]=self.calls%2;return img
  self.ui.frame=frame
  def predict(img):
   self.eng.calls+=1
   return [{'rec_texts':['11/1' if self.eng.calls==2 else '10/1'],'rec_scores':[.999],
    'rec_polys':[np.array([[40,40],[60,40],[60,60],[40,60]])]}]
  self.eng.predict=predict
  with self.assertRaises(mod.Pending):self.ui.rows_batch([((10,10,10,10),'number',.98,'original_or_clahe',None,numeric_pair_verifier('ratio'))])
  self.assertEqual(self.eng.calls,6);self.assertEqual(self.calls,2)

if __name__=='__main__':unittest.main(verbosity=2)
