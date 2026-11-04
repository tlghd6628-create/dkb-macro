import json, tempfile, time, unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_image_perf_candidate import ImagePerf, summarize

class PerformanceAggregation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'perf.jsonl'

    def test_duration_age_outcome_grouping(self):
        result=summarize([('ocr','ok',18.3,33),('ocr','unreadable',23,None),
                          ('capture','stale',151,1600)],4)
        self.assertEqual(result['dropped_events'],4)
        self.assertEqual(result['groups']['ocr/ok']['duration_ms_buckets']['20'],1)
        self.assertEqual(result['groups']['ocr/ok']['frame_age_ms_buckets']['50'],1)
        self.assertEqual(result['groups']['capture/stale']['frame_age_ms_buckets']['2000'],1)

    def test_invalid_or_private_values_are_not_recorded(self):
        p=ImagePerf(self.path,start=False,clock=lambda:10)
        self.assertFalse(p.record('캐릭터 이름','ok',9))
        self.assertFalse(p.record('ocr','some OCR text',9))
        self.assertFalse(p.record([], 'ok',9))
        self.assertFalse(p.record('ocr','ok',11))
        self.assertFalse(p.record('ocr','ok',9,frame_at=11))
        self.assertEqual(p.queue.qsize(),0)

    def test_queue_full_drops_without_wait(self):
        p=ImagePerf(self.path,start=False,capacity=1,clock=lambda:10)
        self.assertTrue(p.record('capture','ok',9))
        self.assertFalse(p.record('ocr','ok',9))
        self.assertEqual(p._take_dropped(),1)

    def test_worker_output_has_only_aggregate_allowlisted_fields(self):
        p=ImagePerf(self.path,interval=.05)
        start=p.mark();self.assertTrue(p.record('ocr','unreadable',start,frame_at=start))
        self.assertTrue(p.close(timeout=1))
        line=json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(set(line),{'version','dropped_events','groups','window_end_unix'})
        self.assertEqual(line['groups']['ocr/unreadable']['count'],1)
        self.assertFalse(p.record('ocr','ok',p.mark()))

    def test_io_error_isolated_on_worker(self):
        blocker=self.path;blocker.write_text('x',encoding='utf-8')
        p=ImagePerf(blocker/'file',interval=.05)
        self.assertTrue(p.record('ocr','error',p.mark()))
        self.assertTrue(p.close(timeout=1))
        self.assertEqual(p.io_errors,1)

    def test_file_cap_preserves_existing_evidence(self):
        self.path.write_bytes(b'x'*1024)
        p=ImagePerf(self.path,start=False,max_bytes=1024)
        p._emit([('capture','ok',1,None)])
        self.assertTrue(p.file_limit_reached)
        self.assertEqual(self.path.read_bytes(),b'x'*1024)

if __name__=='__main__':unittest.main()
