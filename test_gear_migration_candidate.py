import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from owner_gear_migration_candidate import initialize_missing
from owner_gear_settings_candidate import Store

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.getcwd());self.addCleanup(self.temp.cleanup)
        self.flags={'auto_growth.equipment.enabled':True,'auto_growth.blessing.enabled':True,'auto_growth.taoist.enabled':True}
    def test_initializes_approved_goals_and_no_unspecified_aura(self):
        self.assertEqual(initialize_missing(self.temp.name,'s/c',self.flags),'initialized')
        d=Store(self.temp.name,'s/c').read()
        for grade in ('일반','희귀','영웅'):
            self.assertTrue(d['grades'][grade]['enabled']);self.assertEqual(d['grades'][grade]['enhance'],50)
            self.assertEqual(d['grades'][grade]['breakthrough'],2 if grade=='영웅' else 3)
            self.assertEqual(d['grades'][grade]['awaken'],1)
        self.assertTrue(all(v['enabled'] and v['enhance']==49 and v['breakthrough']==0 for v in d['blessings'].values()))
        self.assertEqual({k for k,v in d['skills'].items() if v['enabled']},{'파멸','강타'})
        self.assertFalse(d['skills']['강인']['enabled']);self.assertEqual(d['skills']['강인']['enhance'],19)
        self.assertEqual(d['skills']['파멸']['enhance'],49);self.assertEqual(d['skills']['강타']['enhance'],19)
        self.assertFalse(any(v['enabled'] for v in d['energies'].values()))
    def test_existing_saved_user_configuration_is_never_replaced(self):
        initialize_missing(self.temp.name,'s/c',self.flags);store=Store(self.temp.name,'s/c')
        d=store.read();d['grades']['일반']['enhance']=12;store.write(d)
        self.assertEqual(initialize_missing(self.temp.name,'s/c',self.flags),'existing_preserved')
        self.assertEqual(store.read()['grades']['일반']['enhance'],12)
    def test_missing_flags_and_different_character_do_not_guess(self):
        self.assertEqual(initialize_missing(self.temp.name,'s/c',{}),'hold_native_flags')
        self.assertFalse(Store(self.temp.name,'s/c').path.exists())
        self.assertEqual(initialize_missing(self.temp.name,'',self.flags),'hold_identity_or_settings')
    def test_existing_file_does_not_wait_for_stale_lock(self):
        self.assertEqual(initialize_missing(self.temp.name,'s/c',self.flags),'initialized')
        self.assertEqual(initialize_missing(self.temp.name,'s/c',{}),'existing_preserved')
        store=Store(self.temp.name,'s/c');lock=store.path.with_suffix(store.path.suffix+'.migration.lock')
        self.assertTrue(lock.exists())
    def test_os_lock_releases_without_deleting_lock_file(self):
        import msvcrt
        store=Store(self.temp.name,'s/c');store.path.parent.mkdir(parents=True)
        lock=store.path.with_suffix(store.path.suffix+'.migration.lock')
        fd=os.open(str(lock),os.O_CREAT|os.O_RDWR,0o600);os.write(fd,b'0');os.lseek(fd,0,os.SEEK_SET)
        msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        try:self.assertEqual(initialize_missing(self.temp.name,'s/c',self.flags),'hold_locked')
        finally:os.close(fd)
        self.assertEqual(initialize_missing(self.temp.name,'s/c',self.flags),'initialized')
        self.assertTrue(lock.exists())
    def test_child_process_exit_releases_migration_lock(self):
        import subprocess
        store=Store(self.temp.name,'s/c');store.path.parent.mkdir(parents=True)
        lock=store.path.with_suffix(store.path.suffix+'.migration.lock')
        code=("import os,sys,msvcrt,time; f=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR,0o600);"
              "os.write(f,b'0');os.lseek(f,0,0);msvcrt.locking(f,msvcrt.LK_NBLCK,1);"
              "print('locked',flush=True);time.sleep(20)")
        child=subprocess.Popen([sys.executable,'-B','-c',code,str(lock)],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'locked')
            self.assertEqual(initialize_missing(self.temp.name,'s/c',self.flags),'hold_locked')
        finally:
            child.terminate();child.wait(timeout=5)
            if child.stdout:child.stdout.close()
        self.assertEqual(initialize_missing(self.temp.name,'s/c',self.flags),'initialized')

if __name__=='__main__':unittest.main()
