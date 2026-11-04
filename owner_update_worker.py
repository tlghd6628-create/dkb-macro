"""Out-of-process atomic owner update, after cooperative GUI shutdown."""
from pathlib import Path
import ctypes,json,os,subprocess,sys,time,uuid,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_update_core import atomic,save,load,target,digest,verify_signed,verify_zip,UpdateError

def alive(pid):
    if type(pid) is not int or pid<=0:return False
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    handle=kernel.OpenProcess(0x100000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87:return False
        raise UpdateError('old process exit cannot be verified')
    try:return kernel.WaitForSingleObject(ctypes.c_void_p(handle),0)==258
    finally:kernel.CloseHandle(ctypes.c_void_p(handle))

def apply_files(root,bundle,doc,backup,write=atomic):
    """Verify everything before write; rollback only these explicit paths."""
    root=Path(root);backup=Path(backup);verify_zip(bundle,doc);plan=[]
    with zipfile.ZipFile(bundle) as z:
        for row in doc['files']:
            dest=target(root,row['path']);old=dest.read_bytes() if dest.is_file() else None
            plan.append((row['path'],dest,old,z.read(row['path'])))
    backup.mkdir(parents=True,exist_ok=False)
    for i,(name,dest,old,new) in enumerate(plan):
        if old is not None:atomic(backup/(str(i)+'.old'),old)
    receipt={'state':'prepared','sequence':doc['sequence'],'files':[{'path':n,'existed':o is not None,'old_sha256':digest(o) if o is not None else None,'new_sha256':digest(v)} for n,d,o,v in plan]}
    save(backup/'transaction.json',receipt)
    written=[]
    try:
        for name,dest,old,new in plan:
            written.append((dest,old));write(dest,new)
        receipt['state']='committed';save(backup/'transaction.json',receipt)
    except BaseException:
        for dest,old in reversed(written):
            if old is None:
                if dest.exists():dest.unlink()
            else:atomic(dest,old)
        receipt['state']='rolled_back';save(backup/'transaction.json',receipt)
        raise

def restart_intent(cache,control,job,sequence):
    intent=load(control.read_bytes()) if control.exists() else {}
    reopen=not intent.get('user_exit',False)
    resume=bool(reopen and job['was_running'] and intent.get('epoch')==job['epoch'] and intent.get('desired')=='running')
    if reopen:
        save(cache/'resume.json',{'nonce':job['nonce'],'epoch':intent.get('epoch'),
             'resume':resume,'expires':time.time()+600,'sequence':sequence,'mode':job['mode'],'profile':job['profile']})
    return reopen,resume

def main(job_path):
    import msvcrt
    job_path=Path(job_path).resolve();job=load(job_path.read_bytes());root=Path(job['root']).resolve()
    cache=root/'.owner-update';control=root/'vendor/DKB_Auto/settings/owner-update-control.json'
    if not job_path.is_relative_to(cache.resolve()):raise UpdateError('job outside update cache')
    trust=load((Path(__file__).parent/'owner_update_trust.json').read_bytes())
    baseline=load((root/'owner/owner_release.json').read_bytes())['sequence']
    current=load((cache/'current.json').read_bytes()) if (cache/'current.json').exists() else {'sequence':baseline}
    current['sequence']=max(baseline,current['sequence'])
    envelope=(job_path.parent/'release.json').read_bytes();doc=verify_signed(envelope,trust,current['sequence'])
    bundle=job_path.parent/'bundle.zip';verify_zip(bundle,doc)
    lock=open(cache/'apply.lock','a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    marker=cache/'applying.json'
    old_gone=False;applied=False;preserve_marker=False;reopen=False;success=False;backup=None
    try:
        save(marker,{'pid':os.getpid(),'sequence':doc['sequence']});save(job_path.parent/'ready.json',{'pid':os.getpid()})
        deadline=time.monotonic()+120
        while any(alive(pid) for pid in job['wait_pids']):
            if (job_path.parent/'cancel').exists() or time.monotonic()>deadline:raise UpdateError('update shutdown wait cancelled')
            time.sleep(.1)
        if (job_path.parent/'cancel').exists():raise UpdateError('update cancelled')
        old_gone=True
        backup=cache/'rollback'/(str(doc['sequence'])+'-'+job['nonce'])
        save(marker,{'pid':os.getpid(),'sequence':doc['sequence'],'version':doc['version'],'transaction':str(backup)})
        apply_files(root,bundle,doc,backup)
        applied=True
        save(cache/'current.json',{'sequence':doc['sequence'],'version':doc['version'],'applied_at':time.time()})
        reopen,resume=restart_intent(cache,control,job,doc['sequence'])
        save(cache/'last-result.json',{'ok':True,'sequence':doc['sequence'],'resume_requested':resume,'at':time.time()})
        success=True
    except BaseException as exc:
        rolled_back=False
        if old_gone and not applied:
            transaction=backup/'transaction.json' if backup else None
            rolled_back=transaction is None or not transaction.exists() or load(transaction.read_bytes()).get('state')=='rolled_back'
            if rolled_back:reopen,resume=restart_intent(cache,control,job,current['sequence'])
        preserve_marker=old_gone and not rolled_back
        save(cache/'last-result.json',{'ok':False,'error':str(exc),'blocked_sequence':doc['sequence'],
             'rolled_back':rolled_back,'old_program_reopen':reopen,'at':time.time()})
    finally:
        if marker.exists() and not preserve_marker:marker.unlink()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    if reopen:
        python=root/'vendor/BIOL_Runtime/1.1.0/python/pythonw.exe'
        subprocess.Popen([str(python),str(root/'owner/start.py')],cwd=str(root/'vendor/DKB_Auto'),creationflags=0x08000000)
    return 0 if success else 1

def recover(root,info):
    """Restore a dead writer's explicit transaction before a new GUI loads."""
    root=Path(root).resolve();cache=root/'.owner-update';folder=info.get('transaction')
    if not folder:return
    folder=Path(folder).resolve()
    if not folder.is_relative_to(cache/'rollback'):raise UpdateError('recovery transaction leaves cache')
    path=folder/'transaction.json'
    if not path.exists():return # Payload backup was not completed; no writes.
    doc=load(path.read_bytes());actions=[]
    if doc.get('state')=='rolled_back':return
    if doc.get('state') not in ('prepared','committed'):raise UpdateError('unknown recovery state')
    for i,row in enumerate(doc['files']):
        dest=target(root,row['path']);current=digest(dest.read_bytes()) if dest.is_file() else None
        if current not in (row['old_sha256'],row['new_sha256']):raise UpdateError('recovery target changed outside update')
        old=(folder/(str(i)+'.old')).read_bytes() if row['existed'] else None
        if (digest(old) if old is not None else None)!=row['old_sha256']:raise UpdateError('recovery backup differs')
        if doc['state']=='committed' and current!=row['new_sha256']:raise UpdateError('committed update is incomplete')
        actions.append((dest,old))
    if doc['state']=='committed':
        save(cache/'current.json',{'sequence':info['sequence'],'version':info['version'],'recovered_at':time.time()})
    else:
        for dest,old in actions:
            if old is None:
                if dest.exists():dest.unlink()
            else:atomic(dest,old)
        doc['state']='rolled_back';save(path,doc)
    save(cache/'last-result.json',{'recovered':True,'state':doc['state'],'at':time.time()})

def wait_for_update(root,seconds=125):
    """A manual launch waits for the exact active update worker, no input."""
    marker=Path(root)/'.owner-update/applying.json';deadline=time.monotonic()+seconds
    while marker.exists():
        info=load(marker.read_bytes())
        if not alive(info.get('pid')):
            recover(root,info);marker.unlink();return
        if time.monotonic()>deadline:raise UpdateError('update is still being applied')
        time.sleep(.1)

if __name__=='__main__':raise SystemExit(main(sys.argv[1]))
