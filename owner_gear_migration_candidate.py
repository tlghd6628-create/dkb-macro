"""Initialize only user-approved growth goals for one identified character.

Call explicitly with verified native flat settings; never runs on import.
Existing user settings are preserved and missing/nonboolean flags stop migration.
"""
import copy,os
from owner_gear_settings_candidate import Store,DEFAULT

def initialize_missing(root,identity,native_values):
    if not isinstance(identity,str) or not identity.strip():return 'hold_identity_or_settings'
    store=Store(root,identity)
    _,revision=store.snapshot()
    if revision!='missing':return 'existing_preserved'
    if not isinstance(native_values,dict):return 'hold_identity_or_settings'
    keys=('auto_growth.equipment.enabled','auto_growth.blessing.enabled','auto_growth.taoist.enabled')
    if any(type(native_values.get(k)) is not bool for k in keys):return 'hold_native_flags'
    store.path.parent.mkdir(parents=True,exist_ok=True)
    lock=store.path.with_suffix(store.path.suffix+'.migration.lock')
    # Persistent file with an OS-held byte lock: the OS releases it on crash.
    # Never delete it, avoiding races between processes opening different files.
    import msvcrt
    fd=os.open(str(lock),os.O_RDWR|os.O_CREAT,0o600)
    if os.fstat(fd).st_size==0:
        os.lseek(fd,0,os.SEEK_SET);os.write(fd,b'0')
    os.lseek(fd,0,os.SEEK_SET)
    try:msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
    except OSError:os.close(fd);return 'hold_locked'
    try:
        _,revision=store.snapshot()
        if revision!='missing':return 'existing_preserved'
        result=copy.deepcopy(DEFAULT)
        for row in result['grades'].values():row['enabled']=native_values[keys[0]]
        for row in result['blessings'].values():row['enabled']=native_values[keys[1]]
        for name,row in result['skills'].items():
            row['enabled']=native_values[keys[2]] and name in ('파멸','강타')
        # Aura target stages were not specified, so no aura is enabled.
        store.write(result,expected_revision='missing')
        return 'initialized'
    finally:
        os.lseek(fd,0,os.SEEK_SET)
        try:msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
        finally:os.close(fd)
