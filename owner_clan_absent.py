"""A character with no clan skips the clan jobs for a day (짱군네, 11-07 03:26).

The native 문파 보스 신청 went back to town first, then found "문파 없음" and reported a failure, so the timetable
kept retrying it. The clan battles (신기 쟁탈전, 미혹의 정원) go through the same native function. Once it says there
is no clan, this character skips it for RECHECK_HOURS and then looks again, in case it joined one.
"""
from pathlib import Path
import logging,time
LOG=logging.getLogger('project_gui.DKB')
RECHECK_HOURS=24;WORD='문파 없음';FILE='settings/owner-clan-absent.json'


def _who(root):
    from owner_membership import _who as who
    return who(root)


def _data(root):
    from owner_timetable import read
    data=read(Path(root)/FILE,{})
    return data if isinstance(data,dict) else {}


def absent(root,now=None):
    who=_who(root)
    if not who:return False
    at=_data(root).get(who)
    now=time.time() if now is None else now
    return isinstance(at,(int,float)) and 0<=now-at<RECHECK_HOURS*3600


def mark(root,now=None):
    from owner_timetable import save
    who=_who(root)
    if not who:return
    data=dict(_data(root));data[who]=time.time() if now is None else now
    save(Path(root)/FILE,data)
    LOG.info('문파 없음 기억 · 문파 일정 %d시간 건너뜀',RECHECK_HOURS)


class _Seen(logging.Handler):
    def __init__(self):
        super().__init__();self.hit=False
    def emit(self,record):
        try:
            if WORD in record.getMessage():self.hit=True
        except Exception:pass


def wrap(original):
    def run(adapter,*args,**kwargs):
        root=getattr(getattr(adapter,'project',None),'root',None)
        if root is not None and absent(root):
            LOG.info('문파 없음 · 문파 일정 건너뜀 · 다음 확인은 하루 뒤');return True
        seen=_Seen();loggers=(LOG,logging.getLogger())
        for one in loggers:one.addHandler(seen)
        try:result=original(adapter,*args,**kwargs)
        finally:
            for one in loggers:one.removeHandler(seen)
        if seen.hit and root is not None:
            mark(root);return True
        return result
    run._owner_clan_absent=True;run.__wrapped__=original
    return run


def install(gui=None):
    import sys
    try:import project_adapter.clan_boss_request as native
    except ImportError:return
    original=native.run_clan_boss_request
    if getattr(original,'_owner_clan_absent',False):return
    new=wrap(original)
    for name,module in tuple(sys.modules.items()):
        if module is None or not name.startswith(('project_adapter','owner_')):continue
        for key,value in tuple(vars(module).items()):
            if value is original:setattr(module,key,new)
    from project_adapter._entry import Adapter
    method=getattr(Adapter,'run_clan_boss_request',None)
    if callable(method) and not getattr(method,'_owner_clan_absent',False):
        Adapter.run_clan_boss_request=wrap(method)
