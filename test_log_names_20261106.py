"""Old names in the compiled modules' log lines come out as the owner's names. No game input."""
from pathlib import Path
import logging,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap


class Names(unittest.TestCase):
    def setUp(self):
        self.old=logging.getLogRecordFactory()
        self.addCleanup(logging.setLogRecordFactory,self.old)
        import owner_main
        owner_main.rename_in_logs()
        self.records=[]
        handler=logging.Handler();handler.emit=self.records.append
        self.log=logging.getLogger('test.names');self.log.addHandler(handler);self.log.setLevel(logging.INFO)
        self.addCleanup(self.log.removeHandler,handler)
    def test_message_and_arguments(self):
        self.log.info('자동 기능 시작 · 가호 보상')
        self.log.info('자동 기능 시작 · %s','가호 보상')
        self.assertEqual([r.getMessage() for r in self.records],['자동 기능 시작 · 가호 일괄 획득']*2)
    def test_other_lines_stay(self):
        self.log.info('가호 소환10 없음 · %d',3)
        self.assertEqual(self.records[0].getMessage(),'가호 소환10 없음 · 3')
    def test_installing_twice_wraps_once(self):
        import owner_main
        factory=logging.getLogRecordFactory();owner_main.rename_in_logs()
        self.assertIs(logging.getLogRecordFactory(),factory)


if __name__=='__main__':unittest.main()
