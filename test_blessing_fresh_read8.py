import bootstrap
import unittest,time
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from owner_blessing_native_candidate import BlessingObserver

class FreshRead(unittest.TestCase):
 def setup_observer(self,changed=False):
  observer=object.__new__(BlessingObserver)
  frame=np.zeros((479,897,3),dtype=np.uint8)
  observer.context=NS(checkpoint=lambda:None,wait=lambda n:None)
  observer.service=NS(check=lambda:None,capture=lambda:frame.copy())
  observer.identity='test';observer.item='icon';observer.sequence=0;observer.root=bootstrap.A
  observer._state=lambda f:{'slot':3,'level':30,'active':False,'button':None,'opening':False}
  observer._same_read_view=lambda *a:not changed
  observer.clock=iter((0.,2.,2.1,2.2,2.4,2.5)).__next__
  return observer
 def test_slow_ocr_requires_new_frames_before_returning_values(self):
  observer=self.setup_observer()
  result=observer.read_pair(False,publish=False)
  self.assertTrue(result['screen_proof']);self.assertGreater(result['second'].captured_at,2.)
  self.assertGreater(result['first'].sequence,2);self.assertIsNotNone(observer._fresh_read_view)
 def test_changed_new_frame_is_not_retimestamped_as_a_success(self):
  # Both the first pair and its one retry are slow, and both new frames differ.
  observer=self.setup_observer(changed=True)
  observer.clock=iter((0.,2.,2.1,10.,12.,12.1)).__next__
  self.assertFalse(observer.read_pair(False,publish=False)['screen_proof'])
  self.assertIsNone(observer._fresh_read_view)
 def test_one_whole_new_pair_may_settle_a_title_still_fading_in(self):
  observer=self.setup_observer(changed=True)
  observer.clock=iter((0.,2.,2.1,10.,10.2,10.3,10.4,10.5)).__next__
  result=observer.read_pair(False,publish=False)
  self.assertTrue(result['screen_proof']);self.assertEqual(result['first'].captured_at,10.)
 def test_final_guard_rejects_expired_revalidated_values(self):
  observer=self.setup_observer();result=observer.read_pair(True,publish=False)
  observer.clock=lambda:8.
  self.assertFalse(observer.verify_final(np.zeros((479,897,3),dtype=np.uint8),result,'enhance'))

if __name__=='__main__':unittest.main()
