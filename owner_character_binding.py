"""Bind the configured server/character to the live name-glyph hash.

Goals, intents and the timetable are keyed by the configured profile; the live
game only yields a hash of the name glyphs. Without this binding, logging in
as another character would silently use the configured character's records.

The glyphs move with the level digits' width, so each profile keeps one hash per
level. A first reading at a new level is accepted only as a forward crossing whose
first name glyph agrees with the bound one. Removing the file rebinds on the next
reading.
"""
from pathlib import Path
import json,logging,os,tempfile,threading

LOG=logging.getLogger('project_gui.DKB')
_LOCK=threading.RLock()
BOUND='bound';MATCHED='matched';CROSSED='crossed';MISMATCH='mismatch';UNAVAILABLE='unavailable'
HEAD_MATCH=.915


def _path(root):return Path(root)/'settings/owner-character-binding.json'


def _read(path):
    try:document=json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:return {'version':1,'profiles':{}}
    if not isinstance(document,dict) or document.get('version')!=1 or not isinstance(document.get('profiles'),dict):
        raise ValueError('캐릭터 연결 기록 형식 오류')
    return document


def _write(path,document):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.character-binding-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(document,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def name_head(frame):
    """First name glyph, found as the first ink run wider than a level digit. None if unreadable.

    Real frames at levels 1, 3, 7, 8, 9, 12, 17 scored .956 or more against each other, and a different
    character at level 50 scored .869 at most. Names sharing a first glyph cannot be told apart here.
    """
    import numpy as np
    columns=(frame[9:25,50:112].min(axis=2)>150).any(axis=0).tolist()+[False]
    start=None
    for i,ink in enumerate(columns):
        if ink and start is None:start=i
        if not ink and start is not None:
            if i-start>=7:
                x=50+start;patch=frame[8:26,x-1:x+9].min(axis=2).astype('uint8')
                return patch.tolist() if patch.shape==(18,10) else None
            start=None
    return None


def same_head(stored,head):
    import cv2,numpy as np
    try:
        a=np.asarray(stored,dtype='uint8');b=np.asarray(head,dtype='uint8')
        return a.shape==b.shape==(18,10) and float(cv2.matchTemplate(a,b[1:-1,1:-1],cv2.TM_CCOEFF_NORMED).max())>=HEAD_MATCH
    except (TypeError,ValueError,cv2.error):return False


def resolve(root,profile,glyph_hash,level,head=None):
    """Return (stable character key, status). Only MISMATCH blocks growth."""
    if not isinstance(profile,str) or not profile or not isinstance(glyph_hash,str) or type(level) is not int:
        return glyph_hash,UNAVAILABLE
    # The fixed name crop shifts with the level digits' width, so each level gets its own hash.
    band='lv%d'%level
    path=_path(root)
    with _LOCK:
        try:document=_read(path)
        except (OSError,ValueError) as exc:
            # An unreadable record cannot prove a mismatch; keep it for review.
            LOG.warning('캐릭터 연결 기록 확인 필요 · %s',exc);return glyph_hash,UNAVAILABLE
        row=document['profiles'].get(profile)
        if not isinstance(row,dict):
            document['profiles'][profile]={'character':glyph_hash,band:glyph_hash,'level':level};status=BOUND
            if head:document['profiles'][profile]['head']=head
        elif row.get(band)==glyph_hash or row.get('high' if level>=10 else 'low')==glyph_hash:
            # 'high' and 'low' are records from before per-level hashes.
            if row.get('level')==level and (row.get('head') or not head):return row['character'],MATCHED
            row['level']=level;status=MATCHED
            if head and not row.get('head'):row['head']=head
        elif band not in row and type(row.get('level')) is int and row['level']<level:
            # A new level is the same character only if the first name glyph agrees. A record or a
            # frame with no glyph cannot prove a different character, so it keeps the forward rule.
            if row.get('head') and head and not same_head(row['head'],head):return glyph_hash,MISMATCH
            row[band]=glyph_hash;row['level']=level;status=CROSSED
            if head and not row.get('head'):row['head']=head
        else:return glyph_hash,MISMATCH
        try:_write(path,document)
        except OSError as exc:LOG.warning('캐릭터 연결 기록 저장 보류 · %s',exc)
        return document['profiles'][profile]['character'],status


def observe(adapter,glyph_hash,level,head=None):
    """Stable key for this reading, and whether timed work must hold."""
    from owner_hunt_rules_candidate import configured_identity
    root=adapter.project.root
    try:profile=configured_identity(root)
    except (OSError,ValueError,TypeError):return glyph_hash
    character,status=resolve(root,profile,glyph_hash,level,head)
    was=getattr(adapter,'_owner_character_mismatch',False) is True
    # An unreadable record proves nothing, so it cannot release a proven hold.
    adapter._owner_character_mismatch=status==MISMATCH or (was and status==UNAVAILABLE)
    if status==MISMATCH and not was:
        LOG.warning('설정 캐릭터와 현재 게임 캐릭터 불일치 · 성장·소비·시간표 작업 보류 · 서버·캐릭터 설정을 확인해 주세요')
    elif was and status not in (MISMATCH,UNAVAILABLE):LOG.info('캐릭터 일치 재확인 · 보류 해제')
    return character


def mismatch(adapter):return getattr(adapter,'_owner_character_mismatch',False) is True
