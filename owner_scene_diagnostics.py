"""Bounded reuse of retained game frames in explicit diagnostic transmission."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib,io,json,re,sqlite3


def append_scenes(root,archive,pictures,details,sanitize):
    folder=Path(root)/'logs/scene-corpus';index=folder/'index.sqlite3'
    if not index.is_file():return {'screens':0,'reason':'no retained scene index'}
    if folder.is_symlink() or index.is_symlink():return {'screens':0,'reason':'unsafe scene index'}
    count=0;skipped=0;total=0
    try:
        # Read only; do not enumerate/compress the complete capture archive.
        with sqlite3.connect(index.resolve().as_uri()+'?mode=ro',uri=True,timeout=.3) as db:
            rows=db.execute('SELECT relative_dir FROM scenes ORDER BY observed_at DESC LIMIT 30').fetchall()
        used={p['incident_id'] for p in pictures}|{p['incident_id'] for p in details}
        for (relative,) in rows:
            try:
                if not re.fullmatch(r'\d{8}[/\\]\d{8}T\d{6}-[a-f0-9]{8}',relative):
                    skipped+=1;continue
                path=folder/Path(relative.replace('\\','/'))
                if path.parent.is_symlink() or path.is_symlink() or folder.resolve() not in path.resolve().parents:
                    skipped+=1;continue
                photo=path/'screen.png';meta=path/'observation.json'
                if (not photo.is_file() or photo.is_symlink() or not meta.is_file() or meta.is_symlink()
                    or photo.stat().st_size>4*1024**2 or meta.stat().st_size>1024**2):
                    skipped+=1;continue
                value=json.loads(meta.read_text(encoding='utf8'))
                if value.get('game_only') is not True:
                    skipped+=1;continue
                from PIL import Image
                with Image.open(photo) as image:
                    if image.size!=(897,479):
                        skipped+=1;continue
                    buffer=io.BytesIO();image.convert('RGB').save(buffer,format='JPEG',quality=78)
                jpeg=buffer.getvalue()
                if len(jpeg)>512*1024 or total+len(jpeg)>15*1024**2:
                    skipped+=1;continue
                # Existing collector protocol requires this identifier shape.
                # Metadata explicitly distinguishes observations from failures.
                observed=datetime.strptime(path.name[:15],'%Y%m%dT%H%M%S').replace(tzinfo=timezone(timedelta(hours=9)))
                ident=observed.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+hashlib.sha256(('scene:'+relative).encode()).hexdigest()[:8]
                if ident in used:continue
                value=sanitize({'evidence_kind':'retained_scene','scene_relative_dir':relative,'observation':value})
                text=json.dumps(value,ensure_ascii=False,indent=2)
                image_entry='images/'+ident+'.jpg';detail_entry='incidents/'+ident+'.json'
                archive.writestr(image_entry,jpeg);archive.writestr(detail_entry,text)
                pictures.append({'entry':image_entry,'sha256':hashlib.sha256(jpeg).hexdigest(),
                                 'incident_id':ident,'evidence_kind':'retained_scene'})
                details.append({'entry':detail_entry,'incident_id':ident,
                                'parts':max(1,(len(text.encode('utf8'))+1199)//1200)})
                used.add(ident);count+=1;total+=len(jpeg)
            except (ValueError,OSError,TypeError):skipped+=1
        return {'screens':count,'skipped':skipped,'bytes':total,'limit':30}
    except (sqlite3.Error,OSError,ValueError):
        return {'screens':count,'skipped':skipped,'reason':'scene index unavailable'}
