"""Bind the configured server/character to the live name-glyph hash.

Goals, intents and the timetable are keyed by the configured profile; the live
game only yields a hash of the name glyphs. Without this binding, logging in
as another character would silently use the configured character's records.

The glyphs move with the level digit's width, so each profile keeps one hash per
one-digit level and one for levels of 10 or more. A first reading in a new band
is accepted only as a forward level crossing from a one-digit level. Removing
the file rebinds on the next reading.
"""
from pathlib import Path
import json,logging,os,tempfile,threading

LOG=logging.getLogger('project_gui.DKB')
_LOCK=threading.RLock()
BOUND='bound';MATCHED='matched';CROSSED='crossed';MISMATCH='mismatch';UNAVAILABLE='unavailable'


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


def resolve(root,profile,glyph_hash,level):
    """Return (stable character key, status). Only MISMATCH blocks growth."""
    if not isinstance(profile,str) or not profile or not isinstance(glyph_hash,str) or type(level) is not int:
        return glyph_hash,UNAVAILABLE
    # The fixed name crop shifts with the level digit's width, so each one-digit level gets its own hash.
    band='high' if level>=10 else 'low%d'%level
    path=_path(root)
    with _LOCK:
        try:document=_read(path)
        except (OSError,ValueError) as exc:
            # An unreadable record cannot prove a mismatch; keep it for review.
            LOG.warning('캐릭터 연결 기록 확인 필요 · %s',exc);return glyph_hash,UNAVAILABLE
        row=document['profiles'].get(profile)
        if not isinstance(row,dict):
            document['profiles'][profile]={'character':glyph_hash,band:glyph_hash,'level':level};status=BOUND
        elif row.get(band)==glyph_hash:
            if row.get('level')==level:return row['character'],MATCHED
            row['level']=level;status=MATCHED
        elif band not in row and type(row.get('level')) is int and row['level']<level and row['level']<10:
            row[band]=glyph_hash;row['level']=level;status=CROSSED
        else:return glyph_hash,MISMATCH
        try:_write(path,document)
        except OSError as exc:LOG.warning('캐릭터 연결 기록 저장 보류 · %s',exc)
        return document['profiles'][profile]['character'],status


def observe(adapter,glyph_hash,level):
    """Stable key for this reading, and whether timed work must hold."""
    from owner_hunt_rules_candidate import configured_identity
    root=adapter.project.root
    try:profile=configured_identity(root)
    except (OSError,ValueError,TypeError):return glyph_hash
    character,status=resolve(root,profile,glyph_hash,level)
    was=getattr(adapter,'_owner_character_mismatch',False) is True
    # An unreadable record proves nothing, so it cannot release a proven hold.
    adapter._owner_character_mismatch=status==MISMATCH or (was and status==UNAVAILABLE)
    if status==MISMATCH and not was:
        LOG.warning('설정 캐릭터와 현재 게임 캐릭터 불일치 · 성장·소비·시간표 작업 보류 · 서버·캐릭터 설정을 확인해 주세요')
    elif was and status not in (MISMATCH,UNAVAILABLE):LOG.info('캐릭터 일치 재확인 · 보류 해제')
    return character


def mismatch(adapter):return getattr(adapter,'_owner_character_mismatch',False) is True
