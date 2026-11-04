"""Signed owner-only updates. Pure verification; no network or game input."""
from pathlib import Path,PurePosixPath
import base64,hashlib,hmac,json,re,zipfile

MAX_ZIP=32*1024*1024
MAX_EXPANDED=96*1024*1024
class UpdateError(ValueError):pass
def digest(raw):return hashlib.sha256(raw).hexdigest()
def load(raw):
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise UpdateError('duplicate JSON key')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=unique)
def atomic(path,data):
    import os,uuid
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()
def save(path,value):atomic(path,json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())
def allowed(name):
    if not isinstance(name,str) or '\\' in name or ':' in name or name.startswith('/') or len(name)>230:return False
    parts=PurePosixPath(name).parts
    if len(parts)<2 or parts[0]!='owner' or any(p in ('','.','..') for p in parts):return False
    if any(p.lower() in ('settings','logs','upstream_source','__pycache__','.cache','launcher') for p in parts):return False
    tail=parts[-1]
    if tail=='owner_update_trust.json':return False
    if len(parts)==2:
        return ((tail.startswith('owner_') and tail.endswith('.py')) or tail in ('start.py','apply_profile.py','skill_catalog.json','legacy_album_projection.py','owner_release.json'))
    return parts[1] in ('assets','skill_assets_candidate','owner_gear_assets_candidate','owner_energy_assets_candidate','owner_blessing_assets_candidate') and Path(tail).suffix.lower() in ('.json','.png','.jpg','.jpeg','.webp','.ico')
def target(root,name):
    if not allowed(name):raise UpdateError('unsupported update path')
    root=Path(root).resolve();p=(root/name).resolve()
    if not p.is_relative_to(root/'owner'):raise UpdateError('update path leaves owner tree')
    return p
def verify_signed(raw,trust,minimum=0):
    if len(raw)>1024*1024:raise UpdateError('manifest too large')
    envelope=load(raw)
    try:
        payload=base64.b64decode(envelope['payload'],validate=True);signature=base64.b64decode(envelope['signature'],validate=True)
        modulus=base64.b64decode(trust['modulus'],validate=True);exponent=base64.b64decode(trust['exponent'],validate=True)
    except (KeyError,TypeError,ValueError) as e:raise UpdateError('invalid signature encoding') from e
    n=int.from_bytes(modulus,'big');e=int.from_bytes(exponent,'big');size=(n.bit_length()+7)//8
    if n.bit_length()<2048 or e!=65537 or len(signature)!=size or int.from_bytes(signature,'big')>=n:raise UpdateError('invalid signing key')
    actual=pow(int.from_bytes(signature,'big'),e,n).to_bytes(size,'big')
    suffix=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256(payload).digest()
    expected=b'\0\1'+b'\xff'*(size-len(suffix)-3)+b'\0'+suffix
    if not hmac.compare_digest(actual,expected):raise UpdateError('release signature mismatch')
    doc=load(payload)
    if doc.get('protocol')!=1 or doc.get('product')!='DKB-owner' or doc.get('channel')!='stable':raise UpdateError('wrong update product')
    seq=doc.get('sequence')
    if type(seq) is not int or not minimum<seq<=2147483647:raise UpdateError('old release sequence')
    if type(doc.get('bytes')) is not int or not 0<doc['bytes']<=MAX_ZIP:raise UpdateError('invalid update size')
    if not re.fullmatch('[0-9a-f]{64}',str(doc.get('sha256',''))):raise UpdateError('invalid update hash')
    if doc.get('bundle')!='/updates/bundles/'+doc['sha256']+'.zip':raise UpdateError('invalid update URL')
    rows=doc.get('files')
    if not isinstance(rows,list) or not 1<=len(rows)<=4000:raise UpdateError('invalid update file list')
    seen=set();total=0
    for row in rows:
        name=row.get('path');size=row.get('bytes')
        if not allowed(name) or name.casefold() in seen:raise UpdateError('duplicate or unsupported update file')
        if not re.fullmatch('[0-9a-f]{64}',str(row.get('sha256',''))):raise UpdateError('invalid file hash')
        if type(size) is not int or not 0<=size<=MAX_EXPANDED:raise UpdateError('invalid expanded size')
        total+=size;seen.add(name.casefold())
    if total>MAX_EXPANDED:raise UpdateError('expanded update too large')
    return doc
def verify_zip(path,doc):
    path=Path(path)
    if path.stat().st_size!=doc['bytes'] or digest(path.read_bytes())!=doc['sha256']:raise UpdateError('download hash mismatch')
    expected={r['path']:r for r in doc['files']}
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(expected) or set(names)!=set(expected):raise UpdateError('unexpected ZIP entries')
        for entry in z.infolist():
            row=expected[entry.filename]
            if entry.file_size!=row['bytes'] or (entry.external_attr>>16)&0o170000==0o120000:raise UpdateError('unsupported ZIP entry')
            if digest(z.read(entry))!=row['sha256']:raise UpdateError('update file hash mismatch')
    return True
