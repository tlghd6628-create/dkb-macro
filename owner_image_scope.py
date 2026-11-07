"""Recover moved or re-rendered UI inside the existing detector.

The native fixed ROI always runs first. Only after it misses, the same original
image is compared softly, so changed text rendering does not need a new capture.
Nothing here sends input: native click, guard and revalidation paths receive the
same hit shape they always did, and re-read it through this code on a fresh frame.
"""
from functools import lru_cache,wraps
from pathlib import Path
import json,logging,threading,time
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()
SIGMA=.6;GAP=.1;RAW_FLOOR=.8;SOFT_FROM=.8
NEAR=(8,8);WIDE=(120,30);MOVED=3;OVERLAP=.4
ASSETS=Path(__file__).parent/'assets/movement'

# A resource or ticket is spent by these, so they stay on the exact native match.
COMMIT=('강화버튼','개방버튼','돌파실행','각성실행','실행','구매','소환10','상자열기','결정','분해','소모','즉시','매칭',
        '입장','쿠폰','일괄획득','모두등록','완성','수락','신청','등록','MAX','_수련','사용','치료')

def _titled(anchor,*members,zone=None):return {'anchors':(anchor,),'need':1,'members':members,'zone':zone}
# Each window is identified first; only its own buttons may move, and only inside it.
WINDOWS={
 'move_method':{'asset':('move-method-title',(340,125,220,50)),'members':('버튼_축지술_가운데',),'zone':(340,255,220,75),'same_spot':True},
 'world_map':{'anchors':('버튼_지도_일반','버튼_지도_즐겨찾기','버튼_지도_저장위치'),'need':2,
              'members':('버튼_지도_축지술','버튼_보스_축지술'),'zone':(600,425,297,54),'same_spot':True},
 'hud_top':{'anchors':('버튼_우편','버튼_인벤토리','버튼_전체매뉴','버튼_길라잡이2','버튼_이벤트2'),'need':2,
            'members':('버튼_길라잡이','버튼_길라잡이2','버튼_이벤트','버튼_이벤트2','버튼_거래소','버튼_우편','버튼_인벤토리','버튼_전체매뉴'),'zone':(600,0,297,36)},
 'growth':{'anchors':('체크_성장','체크_전체매뉴_성장'),'need':1,'members':('버튼_성장_장비탭','버튼_성장_가호탭','버튼_성장_도술탭','버튼_성장_강화','버튼_성장_장비_돌파','버튼_성장_장비_돌파2','버튼_성장_장비_각성','버튼_성장_장비_각성2'),'zone':None},
 'mission':_titled('체크_임무','버튼_임무_일일탭','버튼_임무_주간탭','버튼_임무_전래동화탭'),
 'boss':_titled('체크_보스토벌','버튼_보스_필드보스탭','버튼_보스_레이드탭','버튼_보스_세계지도이동'),
 'dungeon':_titled('체크_비경','버튼_비경_전래동화탭'),
 'clan':{**_titled('체크_문파','버튼_문파_전투','버튼_문파_전투2','버튼_문파_닫기','버튼_문파_활동보상'),'title':'문파'},
 # The hamburger menu has no title. Its own entries prove it, on a frame with real pixels.
 'full_menu':{'anchors':('버튼_전체매뉴_성장','버튼_전체매뉴_임무'),'need':2,'members':(),'zone':None,
              'words':(('성장','도술','가호','친구','세계지도','제작','임무','업적'),3,(610,37,287,400))},
 'mail':_titled('체크_우편함','버튼_우편탭_모두받기'),
 'exchange':_titled('체크_거래소','버튼_거래소_판매탭'),
 'treasure':_titled('체크_보물찾기','버튼_보물찾기_보상모두받기'),
 'seal':_titled('체크_단봉인해제','버튼_단봉인해제_나가기'),
 'aura':_titled('체크_전체매뉴_기운발현','버튼_기운발현_생명','버튼_기운발현_여명','버튼_기운발현_몽환','버튼_기운발현_홍염'),
 'blessing':_titled('체크_전체매뉴_가호','버튼_가호_소환탭','버튼_가호_소환_나가기'),
 'settings':_titled('체크_전체매뉴_설정','버튼_전체매뉴_설정_계정'),
 'spirit':_titled('체크_영기수련','버튼_X_영기수련','버튼_X_영기수련2'),
 'notice':_titled('체크_알림','버튼_알림_확인'),
 'long_absence':_titled('체크_장시간미접속','버튼_장시간미접속_확인'),
 'boss_timeout':_titled('체크_보스_시간초과','버튼_보스_시간초과확인'),
 'guide':_titled('체크_길라잡이','버튼_길라잡이_보상받기'),
 'event':_titled('체크_이벤트','버튼_X_이벤트창'),
 # The patch made this window taller: title 12px up, buttons 12px down.
 'raid_admit':{'asset':('raid-admit-title',(415,120,70,40)),'members':()},
}
MEMBER={name:key for key,window in WINDOWS.items() for name in window['members']}

def committed(name):return any(word in name for word in COMMIT)

# List rows repeat the same image at a neighbouring spot, so a nearby match is another row.
LIST_WORDS=('자동진행','진행중','버튼_가호_1','버튼_가호_2','버튼_가호_3','버튼_가호_4','버튼_가호_5')
def listed(name):return any(word in name for word in LIST_WORDS)
def _near_ok(profile,name,e):
    """Small images and state checks match too loosely (saved-frame control:
    a tiny arrow in 610 frames, a different worn item in 312) to soften in place."""
    # Short titles also stay exact: softened, 설정 reads as 성장 on the real screen.
    return name.startswith('버튼_') and e['w']*e['h']>=150 and not listed(name) and _alone(profile,name)

@lru_cache(maxsize=4)
def _geometry(profile):
    from project_adapter import protected_assets
    target=json.loads(protected_assets.read_text(Path(profile)/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
    store=json.loads(protected_assets.read_text(Path(profile)/target['roi'],encoding='utf-8-sig'))
    return {n:(e['x'],e['y'],e['w'],e['h']) for n,e in store.items() if isinstance(e,dict) and e.get('type')=='template'}

@lru_cache(maxsize=512)
def _alone(profile,name):
    """False when another image shares this spot: it may be a state variant, so
    a softer comparison at that spot could turn one state into the other."""
    boxes=_geometry(profile);box=boxes.get(name)
    if box is None:return False
    x,y,w,h=box
    for other,(u,v,p,q) in boxes.items():
        if other==name:continue
        ix,iy=min(x+w,u+p)-max(x,u),min(y+h,v+q)-max(y,v)
        if ix>0 and iy>0 and ix*iy>=OVERLAP*min(w*h,p*q):return False
    return True

def _clip(x,y,w,h):
    l,t=max(0,x),max(0,y);return l,t,min(897,x+w)-l,min(479,y+h)-t

def peaks(hay,needle,box,*,count=2):
    """Best separated scores of raw uint8 images under equal soft blur."""
    import cv2,numpy as np
    x,y,w,h=box;hh,ww=needle.shape[:2]
    if w<ww or h<hh:return []
    pad=2;l,t,r,b=max(0,x-pad),max(0,y-pad),min(hay.shape[1],x+w+pad),min(hay.shape[0],y+h+pad)
    soft=cv2.GaussianBlur(hay[t:b,l:r],(0,0),SIGMA)[y-t:y-t+h,x-l:x-l+w]
    scores=cv2.matchTemplate(soft,cv2.GaussianBlur(needle,(0,0),SIGMA),cv2.TM_CCOEFF_NORMED)
    scores=np.where(np.isfinite(scores),scores,-1);found=[]
    for _ in range(count):
        _,score,_,at=cv2.minMaxLoc(scores);found.append((float(score),at[0]+x,at[1]+y))
        scores=scores.copy();scores[max(0,at[1]-hh//2):at[1]+hh//2+1,max(0,at[0]-ww//2):at[0]+ww//2+1]=-1
    return found

def unique_peak(hay,needle,box,threshold):
    found=peaks(hay,needle,box)
    if not found or found[0][0]<threshold:return None
    if len(found)>1 and found[0][0]-found[1][0]<GAP:return None
    return found[0]

@lru_cache(maxsize=16)
def asset(name):
    from PIL import Image
    import numpy as np
    return np.asarray(Image.open(ASSETS/(name+'.png')).convert('RGB'))

@lru_cache(maxsize=1)
def learned():
    """Which images are on screen together with each button, measured from saved frames."""
    try:return json.loads((Path(__file__).parent/'assets/image-scope/window_map.json').read_text(encoding='utf-8'))['rows']
    except (OSError,ValueError,KeyError):return {}

@lru_cache(maxsize=2)
def _anchors(profile):
    from roi_runtime import RoiDetector
    names=sorted({n for w in WINDOWS.values() for n in w.get('anchors',())}|{n for r in learned().values() for n in r['anchors']})
    return RoiDetector(Path(profile),names)

def _witnessed(profile,anchors,need,frame):
    import cv2
    detector=_anchors(profile);seen=0
    if getattr(LOCAL,'frame',None) is not frame:LOCAL.frame=frame;LOCAL.windows={}
    known=LOCAL.windows;hay=frame[:,:,::-1]
    for name in anchors:
        # The raw score identifies a window; a softened short title can name the wrong one.
        key='image:'+name
        if key not in known:
            e=detector.entries[name]
            l,t,cw,ch=_clip(e['x']-NEAR[0],e['y']-NEAR[1],e['w']+2*NEAR[0],e['h']+2*NEAR[1])
            known[key]=float(cv2.matchTemplate(hay[t:t+ch,l:l+cw].copy(),detector.templates[name],cv2.TM_CCOEFF_NORMED).max())>=.93
        if known[key]:seen+=1
        if seen>=need:return True
    return False

def _title_says(profile,words,frame):
    """Does the title read these words? None on a frame with no real pixels, so the picture answers as before."""
    if getattr(frame,'hi',None) is None:return None
    try:
        import owner_text
        return owner_text.shows_title(frame,words,Path(profile).parents[1])
    except Exception as exc:
        LOG.debug('제목 읽기 생략 · %s',type(exc).__name__);return None

def _entries_say(profile,spec,frame):
    """Are enough of a menu's own entries readable? None with no real pixels or no read, so the picture answers."""
    if getattr(frame,'hi',None) is None:return None
    words,need,zone=spec
    rows=_zone_words(profile,zone,frame)
    if rows is None:return None
    return len({r['text'] for r in rows if r['score']>=WORD_SCORE}&set(words))>=need

def window_open(profile,key,frame):
    if getattr(LOCAL,'frame',None) is not frame:LOCAL.frame=frame;LOCAL.windows={}
    known=LOCAL.windows
    if key not in known:
        spec=WINDOWS[key]
        seen=None
        if key=='move_method' and getattr(frame,'hi',None) is not None:
            from owner_movement import method_open
            seen=method_open(frame)
        if seen is None and 'title' in spec:seen=_title_says(profile,spec['title'],frame)
        if seen is None and 'words' in spec:seen=_entries_say(profile,spec['words'],frame)
        if seen is not None:known[key]=seen
        elif 'asset' in spec:
            name,box=spec['asset'];known[key]=unique_peak(frame,asset(name),box,.92) is not None
        else:
            known[key]=_witnessed(profile,spec['anchors'],spec['need'],frame)
    return known[key]

def learned_open(profile,name,frame):
    row=learned().get(name)
    if row is None:return False
    if getattr(LOCAL,'frame',None) is not frame:LOCAL.frame=frame;LOCAL.windows={}
    key='learned:'+name
    if key not in LOCAL.windows:LOCAL.windows[key]=_witnessed(profile,row['anchors'],row['need'],frame)
    return LOCAL.windows[key]

def _hit(name,e,peak,tier):
    x,y=peak[1],peak[2];w,h=e['w'],e['h']
    key=(name,x-e['x'],y-e['y'],tier);seen=getattr(_hit,'seen',None)
    if seen is None:seen=_hit.seen=set()
    if key not in seen and len(seen)<512:
        seen.add(key);LOG.info('이미지 보정 · %s · 이동 %+d,%+d · 일치 %.3f · %s',name,x-e['x'],y-e['y'],peak[0],tier)
    return (x+w//2,y+h//2,(x,y,x+w,y+h))

def _raw_ok(hay,needle,peak):
    import cv2
    hh,ww=needle.shape[:2];patch=hay[peak[2]:peak[2]+hh,peak[1]:peak[1]+ww]
    return patch.shape==needle.shape and float(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)[0,0])>=RAW_FLOOR

# Exactly one of these shows in one slot, so they can be compared with each other.
STATE_SLOTS=(tuple('체크_레이드_%d단계'%n for n in range(1,6)),)
SLOT_OF={name:slot for slot in STATE_SLOTS for name in slot}

@lru_cache(maxsize=2)
def _slot_reader(profile):
    from roi_runtime import RoiDetector
    return RoiDetector(Path(profile),list(SLOT_OF))

def slot_winner(profile,name,frame):
    """The clear best of a state slot, when re-rendered text drops all of them under the usual score.
    Only the leading digit differs between stages, so only it is compared (real screens: best .83+, gap .10+)."""
    if not window_open(profile,'boss',frame):return None
    reader=_slot_reader(profile);hay=frame[:,:,::-1];scored=[]
    for other in SLOT_OF[name]:
        e=reader.entries[other];found=peaks(hay,reader.templates[other][:,:9],_clip(e['x']-4,e['y']-3,17,e['h']+6),count=1)
        scored.append((found[0] if found else (-1,0,0),other))
    scored.sort(key=lambda row:-row[0][0])
    (best,winner),(second,_)=scored[0],scored[1]
    return best if winner==name and best[0]>=.8 and best[0]-second[0]>=.09 else None

# The game redrew these, so the original image cannot match. Only tried inside the window.
REDRAWN={'버튼_레이드_다음단계':('raid-next','boss',(850,70,47,50)),
         # Reworded: 기본시간 -> 기본 시간, 추가시간 -> 현재 추가된 시간. Same size, so the time reader lines up.
         '체크_비경_기본시간':('dungeon-base-time','dungeon',(712,96,90,28)),
         '체크_비경_추가시간':('dungeon-added-time','dungeon',(712,118,90,28)),
         # The patch turned the four icons into a text list further up and to the right.
         '버튼_기운발현_생명':('energy-life','aura',(20,40,90,28)),
         '버튼_기운발현_여명':('energy-dawn','aura',(20,78,90,28)),
         '버튼_기운발현_몽환':('energy-dream','aura',(20,116,90,28)),
         '버튼_기운발현_홍염':('energy-flame','aura',(20,154,90,28)),
         # These spend a ticket, so each needs its own window's title on the same frame.
         '체크_레이드_매칭입장':('../movement/raid-admit-title','raid_admit',(415,120,70,40)),
         '버튼_레이드_매칭입장확인':('raid-admit-confirm','raid_admit',(480,315,60,30)),
         '버튼_레이드_일괄소모':('raid-admit-max','raid_admit',(515,258,40,34)),
         '버튼_레이드_일괄소모2':('raid-admit-max','raid_admit',(515,258,40,34)),
         # Redrawn in the patch (.82 on a real raid), so the raid looked unentered and AUTO was
         # never pressed. Its translucent mark moves with the background, so the guide label stands
         # in. Only the raid flow asks this name. It is itself the proof of being inside.
         '체크_레이드진입':('raid-entered',None,(755,58,90,36))}

@lru_cache(maxsize=8)
def _redrawn_image(name):
    from PIL import Image
    import numpy as np
    return np.asarray(Image.open(Path(__file__).parent/'assets/image-scope'/(name+'.png')).convert('RGB'))

# Last resort for navigation only: the printed word, read inside the button's own proved
# window. Measured on saved frames (image_scope_20261104/RESULT.md): these read exactly and
# nowhere else. Small tabs misread (소함, 전래등화, 가호 .62) and are not listed. Neither is a
# button whose missing image means something, like a greyed claim or a selected tab.
WORDS={'버튼_임무_일일탭':('일일','mission',None),'버튼_임무_주간탭':('주간','mission',None),
       '버튼_임무_전래동화탭':('전래동화','mission',None),
       '버튼_보스_레이드탭':('레이드','boss',None),'버튼_보스_세계지도이동':('세계지도이동','boss',None),
       '버튼_기운발현_생명':('생명의기운','aura',(0,30,220,340)),'버튼_기운발현_여명':('여명의기운','aura',(0,30,220,340)),
       '버튼_기운발현_홍염':('홍염의기운','aura',(0,30,220,340)),
       '버튼_비경_전래동화탭':('전래동화','dungeon',None),'버튼_가호_소환탭':('소환','blessing',None),
       # 1366x768 clan battle screen, read off saved real frames: the tab list on the left, the chosen one's big title,
       # and 전투 in the row of tabs. Places are 897x479 terms. Nothing here applies or spends.
       '버튼_문파_전투':('전투','clan',(640,30,257,40)),'버튼_문파_전투2':('전투','clan',(640,30,257,40)),
       '버튼_문파_요신토벌령':('요신토벌령','clan',(0,65,110,135)),'버튼_문파_결계지방어':('결계지방어','clan',(0,65,110,135)),
       '버튼_문파_미혹의정원':('미혹의정원','clan',(0,65,110,135)),'버튼_문파_신기쟁탈전':('신기쟁탈전','clan',(0,65,110,135)),
       '체크_문파_요신토벌령':('요신토벌령','clan',(150,70,140,50)),'체크_문파_결계지방어':('결계지방어','clan',(150,70,140,50)),
       '체크_문파_미혹의정원':('미혹의정원','clan',(150,70,140,50)),'체크_문파_신기쟁탈전':('신기쟁탈전','clan',(150,70,140,50)),
       # The entry in the hamburger menu. Exactly 문파, so 문파 전투 further down does not answer for it.
       '버튼_전체매뉴_문파':('문파','full_menu',(610,37,287,400))}
# Fixed misreads seen on real frames, read as the word they are (the idea of MaaFramework's
# OCR "replace"; its code is not used). Only for a word already expected inside its window.
MISREADS={'전래등화':'전래동화','소함':'소환'}
WORD_SCORE=.8;WORD_EVERY=.4;WORD_CEILING=.95

def _read_words(profile,box,frame):
    from tools.ocr_support import get_paddle_engine
    from owner_progression import resized
    import numpy as np,re
    rows=[]
    for page in get_paddle_engine(Path(profile).parents[1],language='korean').predict(resized(frame,box)):
        polys=page.get('rec_polys',())
        for i,(text,score) in enumerate(zip(page.get('rec_texts',()),page.get('rec_scores',()))):
            if i>=len(polys):continue
            poly=np.asarray(polys[i]);lo,hi=poly.min(axis=0)/4-8,poly.max(axis=0)/4-8
            rows.append({'text':re.sub(r'\s+','',str(text)),'score':float(score),
                         'box':(round(box[0]+lo[0]),round(box[1]+lo[1]),round(box[0]+hi[0]),round(box[1]+hi[1]))})
    return rows

def _zone_words(profile,box,frame):
    """Reads are .28s, so a polling caller reuses them while the zone's pixels stay the same."""
    import hashlib
    x,y,w,h=box;digest=hashlib.blake2b(frame[y:y+h,x:x+w].tobytes(),digest_size=16).digest()
    cache=getattr(LOCAL,'words',None)
    if cache is None:cache=LOCAL.words={}
    prior=cache.get(box)
    if prior and prior[0]==digest:return prior[1]
    if prior and time.monotonic()-prior[2]<WORD_EVERY:return None
    try:rows=_read_words(profile,box,frame)
    except Exception as exc:
        LOG.debug('글자 찾기 생략 · %s',type(exc).__name__);return None
    if len(cache)>=16:cache.clear()
    cache[box]=(digest,rows,time.monotonic());return rows

def _joined(rows,word):
    """A word the reader split at its space (결계지 · 방어), side by side on one line. Letters only: stray strokes come back as ㅣ."""
    import re
    parts=[(re.sub('[^가-힣]','',r['text']),r) for r in rows or () if r['score']>=WORD_SCORE]
    found=[]
    for left,a in parts:
        for right,b in parts:
            if a is b or not left or left+right!=word:continue
            p,q=a['box'],b['box']
            if abs(p[1]+p[3]-q[1]-q[3])<=8 and -8<=q[0]-p[2]<=12:
                found.append({'text':word,'score':min(a['score'],b['score']),'box':(p[0],min(p[1],q[1]),q[2],max(p[3],q[3]))})
    return found

def word_hit(detector,name,frame,threshold,candidate_filter):
    spec=WORDS.get(name)
    if spec is None or committed(name) or threshold>WORD_CEILING:return None
    word,key,zone=spec;e=detector.entries.get(name)
    if e is None or not window_open(detector.profile,key,frame):return None
    box=zone or _clip(e['x']-WIDE[0],e['y']-WIDE[1],e['w']+2*WIDE[0],e['h']+2*WIDE[1])
    rows=_zone_words(detector.profile,box,frame)
    found=[r for r in rows or () if MISREADS.get(r['text'],r['text'])==word and r['score']>=WORD_SCORE] or _joined(rows,word)
    if len(found)!=1:return None
    l,t,r,b=found[0]['box']
    if not (box[0]<=l<r<=box[0]+box[2] and box[1]<=t<b<=box[1]+box[3]):return None
    # The native code compares its picture inside the bounds it gets, so they are never smaller than the picture.
    # A bare word's box raised an OpenCV size error out of the clan boss job (19:42).
    x,y=(l+r)//2,(t+b)//2;w,h=max(r-l,e['w']),max(b-t,e['h'])
    made=(x,y,(max(0,x-w//2),max(0,y-h//2),min(897,x-w//2+w),min(479,y-h//2+h)))
    if candidate_filter is not None and not candidate_filter(frame,made):return None
    note(detector.profile,name,'word')
    seen=getattr(word_hit,'seen',None)
    if seen is None:seen=word_hit.seen=set()
    if (name,made[:2]) not in seen and len(seen)<256:
        seen.add((name,made[:2]));LOG.info('이미지 보정 · %s · 글자 %s로 찾음 · 위치 %d,%d · 일치 %.3f',name,word,made[0],made[1],found[0]['score'])
    return made

# What changed since the last patch, kept per day so nobody has to go looking.
KINDS={'moved':'위치 보정','word':'글자 보정','drift':'못 찾음'};HEALTH_DAYS=14
def _health_path():
    """Beside the installed program only: a test or probe run from elsewhere writes nothing."""
    return Path(__file__).resolve().parents[1]/'vendor/DKB_Auto/logs/image-health.json'
def note(profile,name,kind):
    """Writes only when a button or kind is new that day, so polling never touches the disk."""
    today=time.strftime('%Y-%m-%d');seen=getattr(note,'seen',None)
    if seen is None:seen=note.seen=set()
    if (today,name,kind) in seen:return
    seen.add((today,name,kind));path=_health_path()
    if not path.parent.exists():return
    try:
        data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(data,dict):data={}
        data.setdefault(today,{}).setdefault(kind,[])
        if name not in data[today][kind]:data[today][kind].append(name)
        for old in sorted(data)[:-HEALTH_DAYS]:del data[old]
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
    except (OSError,ValueError) as exc:LOG.debug('이미지 변화 기록 생략 · %s',type(exc).__name__)

def health_summary(path,days=3):
    """One line for the log at launch. Silent when nothing needed correcting."""
    try:data=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    if not isinstance(data,dict):return None
    names={kind:set() for kind in KINDS}
    for day in sorted(data)[-days:]:
        for kind,rows in data[day].items() if isinstance(data[day],dict) else ():
            if kind in names and isinstance(rows,list):names[kind].update(rows)
    if not any(names.values()):return None
    line='이미지 변화 기록 · 최근 %d일 · '%days+' · '.join('%s %d개'%(KINDS[k],len(names[k])) for k in KINDS)
    if names['drift']:line+=' · 못 찾은 항목: '+', '.join(sorted(names['drift'])[:8])
    return line

# Translucent over the moving world, so the plain score wanders around .90 and the native
# path waited 8 seconds and fell back to the menu. Its white moon does not change. Two renders
# seen on 1127 of 1649 real frames, each at one exact spot; menus and combat score under .7.
GLYPHS={'버튼_절전모드바로진입':(('sleep-glyph-a','sleep-glyph-b'),(690,431,34,36),.8)}

def glyph_hit(name,frame,candidate_filter):
    images,(x,y,w,h),floor=GLYPHS[name]
    hay=frame[y:y+h,x:x+w].min(axis=2)>=175;top=(0.,0,0,0,0)
    for image in images:
        ref=_redrawn_image(image)[:,:,0]>127;rh,rw=ref.shape
        for j in range(hay.shape[0]-rh+1):
            for i in range(hay.shape[1]-rw+1):
                part=hay[j:j+rh,i:i+rw];union=(part|ref).sum()
                score=(part&ref).sum()/union if union else 0.
                if score>top[0]:top=(float(score),x+i,y+j,rw,rh)
    if top[0]<floor:return None
    score,left,upper,rw,rh=top
    made=(left+rw//2,upper+rh//2,(left,upper,left+rw,upper+rh))
    return made if candidate_filter is None or candidate_filter(frame,made) else None

def summon_already_shown(detector,name,frame):
    """With every effect skipped the results appear at once and 즉시확인 never does.

    Native stops there and leaves the game on this screen (real run 11-05 01:32). A press
    on the empty margin lets it go on to its own exit button. It spends nothing.
    """
    if name!='버튼_가호_즉시확인' or '버튼_가호_소환_나가기' not in detector.templates:return None
    if not detector.find('버튼_가호_소환_나가기',frame,threshold=.9):return None
    return (850,440,(845,435,855,445))

# At 1366x768 these are found by their words and nothing else: a softer look at their pictures could take a neighbour.
REAL_WORDS={'체크_사망상태':'death_mark','버튼_축지술_가운데':'teleport_word','버튼_귀환':'home_word','버튼_보스_축지술':'map_teleport','버튼_지도_축지술':'map_teleport','버튼_지도_물약상인':'map_merchant','버튼_지도_물약상인2':'map_merchant','버튼_전체매뉴_설정_쿠폰등록':'coupon_menu'}

def real_word_hit(detector,name,frame,candidate_filter):
    import owner_movement,owner_real_marks
    reader=REAL_WORDS[name]
    made=getattr(owner_movement,reader,None) or getattr(owner_real_marks,reader)
    made=made(frame)
    if made is None or (candidate_filter is not None and not candidate_filter(frame,made)):return None
    note(detector.profile,name,'word')
    seen=getattr(real_word_hit,'seen',None)
    if seen is None:seen=real_word_hit.seen=set()
    if (name,made[:2]) not in seen and len(seen)<256:
        seen.add((name,made[:2]));LOG.info('이미지 보정 · %s · 글자로 찾음 · 위치 %d,%d',name,made[0],made[1])
    return made

def recover(detector,name,frame,region,threshold,candidate_filter):
    e=detector.entries.get(name);needle=detector.templates.get(name)
    if e is None or needle is None or e.get('type')!='template':return None
    if name in REAL_WORDS and not region and getattr(frame,'hi',None) is not None:
        return real_word_hit(detector,name,frame,candidate_filter)
    shown=summon_already_shown(detector,name,frame)
    if shown:return shown
    if name in GLYPHS and getattr(frame,'shape',None)==(479,897,3):return glyph_hit(name,frame,candidate_filter)
    # A redrawn image replaces the original, so the original's mask has no say in it.
    if name not in REDRAWN and name in detector.masks:return None
    if name in REDRAWN:
        image,key,box=REDRAWN[name]
        if key is not None and not window_open(detector.profile,key,frame):return None
        alt=_redrawn_image(image);peak=unique_peak(frame,alt,box,max(threshold,.92))
        if peak is None:return word_hit(detector,name,frame,threshold,candidate_filter)
        h,w=alt.shape[:2];made=(peak[1]+w//2,peak[2]+h//2,(peak[1],peak[2],peak[1]+w,peak[2]+h))
        return made if candidate_filter is None or candidate_filter(frame,made) else None
    if name in SLOT_OF and not region and threshold<=.95:
        peak=slot_winner(detector.profile,name,frame)
        if peak:
            made=_hit(name,e,peak,'상태 비교')
            return made if candidate_filter is None or candidate_filter(frame,made) else None
        return None
    if name!='버튼_축지술_가운데' and committed(name):return None
    # Words before a softer look at the picture: 버튼_문파_전투 matched .905 at 70 pixels off and pressed nothing (19:42).
    if name in WORDS and not region and getattr(frame,'hi',None) is not None:
        hit=word_hit(detector,name,frame,threshold,candidate_filter)
        if hit is not None:return hit
    profile=detector.profile;need=max(threshold,.9);hay=frame[:,:,::-1];hit=None
    def accept(peak,tier):
        if peak is None or not _raw_ok(hay,needle,peak):return None
        made=_hit(name,e,peak,tier)
        return made if candidate_filter is None or candidate_filter(frame,made) else None
    if region:
        r=detector.entries.get(region)
        if not r or r.get('type')!='rect':return None
        return accept(unique_peak(hay,needle,(r['x'],r['y'],r['w'],r['h']),need),'지정 범위')
    x,y,w,h=e['x'],e['y'],e['w'],e['h'];key=MEMBER.get(name);spec=WINDOWS.get(key)
    if _near_ok(profile,name,e) or (spec and spec.get('same_spot')):
        hit=accept(unique_peak(hay,needle,_clip(x-NEAR[0],y-NEAR[1],w+2*NEAR[0],h+2*NEAR[1]),need),'제자리')
    if hit is None and spec and window_open(profile,key,frame):
        box=spec.get('zone') or _clip(x-WIDE[0],y-WIDE[1],w+2*WIDE[0],h+2*WIDE[1])
        peak=unique_peak(hay,needle,box,need)
        if peak and (spec.get('same_spot') or abs(peak[1]-x)>=MOVED or abs(peak[2]-y)>=MOVED):hit=accept(peak,'창 '+key)
    elif hit is None and spec is None and not listed(name) and learned_open(profile,name,frame):
        peak=unique_peak(hay,needle,_clip(x-WIDE[0],y-WIDE[1],w+2*WIDE[0],h+2*WIDE[1]),need)
        if peak and (abs(peak[1]-x)>=MOVED or abs(peak[2]-y)>=MOVED):hit=accept(peak,'창 자동')
    if hit is not None:
        note(profile,name,'moved');return hit
    return word_hit(detector,name,frame,threshold,candidate_filter)

def drift_scan(detector,name,frame,now=time.monotonic):
    """A requested image timed out: note where it now is. Evidence only, no input."""
    last=getattr(drift_scan,'last',None)
    if last is None:last=drift_scan.last={}
    if name not in detector.templates or now()-last.get(name,-1e9)<600:return None
    last[name]=now();e=detector.entries[name];hay=frame[:,:,::-1]
    found=peaks(hay,detector.templates[name],(0,0,897,479))
    if not found or found[0][0]<.85 or (len(found)>1 and found[0][0]-found[1][0]<GAP):return None
    note(detector.profile,name,'drift')
    row={'at':time.strftime('%Y-%m-%dT%H:%M:%S'),'name':name,'roi':[e['x'],e['y']],'found':[found[0][1],found[0][2]],'score':round(found[0][0],3)}
    LOG.info('이미지 위치 변경 의심 · %s · 기존 %d,%d · 현재 %d,%d · 일치 %.3f',name,e['x'],e['y'],found[0][1],found[0][2],found[0][0])
    try:
        path=Path(detector.profile).parents[1]/'logs/image-drift.jsonl'
        if not path.exists() or path.stat().st_size<262144:
            with path.open('a',encoding='utf-8') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n')
    except OSError:pass
    return row

# The zoom bar moved in the patch, and the native treasure route re-checks the button itself before
# clicking, so a recovered hit is refused. It has to see the current image at the current place.
MOVED_IMAGES={'버튼_보물찾기_지도축소':('map-zoom-out',354,450)}

def install(gui=None):
    from roi_runtime import RoiDetector
    from project_adapter.sleep_mode import SleepModeActions
    if not getattr(RoiDetector.__init__,'_owner_moved_images',False):
        construct=RoiDetector.__init__
        @wraps(construct)
        def made(detector,*args,**kwargs):
            construct(detector,*args,**kwargs)
            for name,(image,x,y) in MOVED_IMAGES.items():
                if name in detector.templates and name in detector.entries:
                    detector.templates[name]=_redrawn_image(image)[:,:,::-1].copy()
                    detector.entries[name]=dict(detector.entries[name],x=x,y=y)
        made._owner_moved_images=True;RoiDetector.__init__=made
    if not getattr(install,'reported',False):
        install.reported=True
        line=health_summary(_health_path())
        if line:LOG.info(line)
    if not getattr(RoiDetector.find,'_owner_image_scope',False):
        ordinary=RoiDetector.find
        @wraps(ordinary)
        def find(detector,name,frame,region=None,threshold=.9,*,candidate_filter=None):
            import owner_growth_words as words
            if words.answers(name,frame):
                hit=words.find_word(detector,name,frame)
                if hit is not None and (candidate_filter is None or candidate_filter(frame,hit)):return hit
                if name in words.WORDS_ONLY:return None
            hit=ordinary(detector,name,frame,region,threshold,candidate_filter=candidate_filter)
            if hit is not None or threshold<SOFT_FROM:return hit
            LOCAL.last_frame=frame
            return recover(detector,name,frame,region,threshold,candidate_filter)
        find._owner_image_scope=True;RoiDetector.find=find
    from project_adapter.main_quest import StateROIs
    if not getattr(StateROIs.match_roi,'_owner_image_scope',False):
        # The native map travel click and the quest runner read through this
        # second path, which never reaches RoiDetector.find. Only buttons whose
        # own window can be proved may move here: this path also decides quest state.
        match_roi=StateROIs.match_roi
        @wraps(match_roi)
        def scoped(slots,name,frame,spec,*,threshold_override=None):
            result=match_roi(slots,name,frame,spec,threshold_override=threshold_override)
            if result.get('hit') or threshold_override is not None or name not in MEMBER:return result
            threshold=result.get('threshold') or 0
            if threshold<SOFT_FROM or set(spec)-{'threshold'}:return result
            hit=recover(slots.detector,name,frame,None,threshold,None)
            return result if hit is None else dict(result,hit=hit,score=max(result.get('score') or 0,threshold))
        scoped._owner_image_scope=True;StateROIs.match_roi=scoped
    if not getattr(SleepModeActions.detect,'_owner_image_scope',False):
        detect=SleepModeActions.detect
        @wraps(detect)
        def timed(actions,name,*a,**k):
            hit=detect(actions,name,*a,**k);frame=getattr(LOCAL,'last_frame',None)
            if hit is None and frame is not None:
                try:drift_scan(actions.detector,name,frame)
                except Exception as exc:LOG.debug('이미지 위치 기록 생략 · %s',type(exc).__name__)
            return hit
        timed._owner_image_scope=True;SleepModeActions.detect=timed
