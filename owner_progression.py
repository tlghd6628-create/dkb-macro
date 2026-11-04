"""Image-proved character level, milestone receipts and confirmed death routing."""
from functools import wraps,lru_cache
from pathlib import Path
import hashlib,json,logging,re,threading,time
from owner_quest_memory import QuestMemory
MILESTONES=(20,30,40,45)
GROWTH='auto_growth.equipment.enabled'
LOG=logging.getLogger('project_gui.DKB')

@lru_cache(maxsize=2)
def inventory_anchor(name):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(Path(__file__).parent/'assets'/name).convert('RGB'))

def inventory_parts(frame):
    import cv2
    if frame.shape!=(479,897,3):return False,False
    result=[]
    for name,(x,y,w,h) in (('inventory-level-label.png',(34,11,19,12)),('inventory-right-label.png',(721,45,30,23))):
        needle=inventory_anchor(name)
        result.append(float(cv2.matchTemplate(frame[y:y+h,x:x+w],needle,cv2.TM_CCOEFF_NORMED)[0,0])>=.94)
    return tuple(result)

def open_inventory_by_key(service):
    frame=service.capture();left,right=inventory_parts(frame)
    if left and right:return True
    # Normalize a proved partial inventory, never arbitrary dialogs.
    if left and not right:service.click_hit((184,17,(178,10,191,24)));service.context.wait(.2)
    if right and not left:service.click_hit((883,54,(877,48,890,61)));service.context.wait(.2)
    # 01:28 real run: one key press in combat did nothing. Press again only while neither
    # panel shows: the key toggles, so a slow panel must not be closed by a second press.
    for attempt in range(2):
        service.check()
        if attempt and any(inventory_parts(service.capture())):break
        service.key(0x49)
        end=time.monotonic()+3
        while time.monotonic()<end:
            service.check()
            if inventory_parts(service.capture())==(True,True):
                LOG.info('정보창 열림 · 좌우 패널 확인',extra={'gui_message':'정보창 열림 · 좌우 패널 확인'})
                return True
            service.context.wait(.1)
    raise RuntimeError('인벤토리 단축키 입력 후 좌우 패널을 확인하지 못했습니다.')


def open_inventory_entry(service,ordinary,*args,**kwargs):
    """Reuse the established I-key path when the ordinary icon is absent."""
    frame=service.capture()
    button=service.detector.find('버튼_인벤토리',frame) if '버튼_인벤토리' in service.detector.entries else None
    # An explicit request for this same icon is not evidence that it exists.
    # Preserve genuinely different native entry buttons and their arguments.
    explicit=kwargs.get('click_button')
    if button is not None or explicit not in (None,'버튼_인벤토리'):
        return ordinary(service,*args,**kwargs)
    return open_inventory_by_key(service)


def texts(pages):
    return [(str(t),float(s)) for page in pages for t,s in zip(page.get('rec_texts',()),page.get('rec_scores',()))]


def parse_level(number_pages,header_pages):
    digits={int(t.strip()) for t,s in texts(number_pages) if s>=.985 and re.fullmatch(r'\d{1,2}',t.strip()) and 1<=int(t.strip())<=50}
    labels={int(m[1]) for t,s in texts(header_pages) if s>=.88 for m in [re.search(r'레벨\s*(\d{1,2})(?!\d)',t)] if m and 1<=int(m[1])<=50}
    return next(iter(digits)) if len(digits)==1 and digits==labels else None


def read_level(number,korean,frame):
    """A one-digit level leaves the name's first glyph in the two-digit box, so '1' reads as '18'."""
    header=korean.predict(resized(frame,(32,7,76,20)))
    wide=number.predict(resized(frame,(53,9,12,15)))
    level=parse_level(wide,header)
    if level is not None:return level
    # Level 17 read .95 as a number and .85 in the header, both right and both under their gates.
    # Two independent readers agreeing on one value is proof enough, and two frames must still agree.
    numbers={int(t.strip()) for t,s in texts(wide) if s>=.90 and re.fullmatch(r'\d{1,2}',t.strip()) and 1<=int(t.strip())<=50}
    named={int(m[1]) for t,s in texts(header) if s>=.80 for m in [re.search(r'레벨\s*(\d{1,2})(?!\d)',t)] if m and 1<=int(m[1])<=50}
    if len(numbers)==1 and numbers==named:return next(iter(numbers))
    # A strong two-digit reading contradicts the header: keep holding, never narrow past it.
    if any(s>=.985 and re.fullmatch(r'\d{2}',t.strip()) for t,s in texts(wide)):return None
    labels={int(m[1]) for t,s in texts(header) if s>=.88 for m in [re.search(r'레벨\s*(\d{1,2})(?!\d)',t)] if m}
    if len(labels)!=1 or next(iter(labels))>=10:return None
    # The header only proves there is one digit: it read a real 3 as 8 at .97.
    # The caller still requires two frames to agree.
    for box in ((52,9,9,15),(53,9,8,15)):
        digits={int(t.strip()) for t,s in texts(number.predict(resized(frame,box))) if s>=.985 and re.fullmatch(r'[1-9]',t.strip())}
        if len(digits)==1:return next(iter(digits))
    return None


def parse_power(pages,minimum=.98):
    values=set()
    for text,score in texts(pages):
        match=re.fullmatch(r'[:\s×X]*([0-9]{1,3}(?:[,.][0-9]{3})+|[0-9]+)',text.strip())
        if score>=minimum and match:
            value=int(re.sub(r'\D','',match[1]))
            if 100<=value<=10_000_000:values.add(value)
    return next(iter(values)) if len(values)==1 else None


def power_image(frame):
    """Separate the orange inventory digits without lowering OCR confidence."""
    import cv2,numpy as np
    part=frame[47:64,35:85]
    r,g,b=(part[:,:,i].astype('float32') for i in range(3))
    mask=(r>130)&(g>65)&(r>g*1.12)&(g>b*1.5)
    image=np.repeat(np.where(mask,0,255).astype('uint8')[:,:,None],3,axis=2)
    image=cv2.copyMakeBorder(image,8,8,8,8,cv2.BORDER_CONSTANT,value=(255,255,255))
    return cv2.resize(image,None,fx=4,fy=4,interpolation=cv2.INTER_NEAREST)


def read_inventory_power(engine,frame):
    original=engine.predict(resized(frame,(40,47,42,17)))
    value=parse_power(original)
    if value is not None:return value
    # Six-digit orange text can have lower OCR confidence despite unchanged
    # glyphs. Require both inventory anchors and agreement at two resampling
    # sizes; observe_inventory independently repeats this on a fresh frame.
    if inventory_parts(frame)==(True,True):
        import cv2
        patch=frame[47:64,40:82]
        patch=cv2.copyMakeBorder(patch,8,8,8,8,cv2.BORDER_CONSTANT,value=(40,40,40))
        # A second interpolation helps tiny glyphs while keeping the 0.98
        # confidence gate; a lower-confidence original must agree exactly.
        linear=engine.predict(cv2.resize(patch,None,fx=3,fy=3,interpolation=cv2.INTER_LINEAR))
        strong,original_agreement=parse_power(linear),parse_power(original,.90)
        if strong is not None and strong==original_agreement:return strong
        alternate=engine.predict(cv2.resize(patch,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC))
        a,b=parse_power(original,.90),parse_power(alternate,.92)
        if a is not None and a==b:return a
    value=parse_power(engine.predict(power_image(frame)))
    return value if value is not None else read_short_power(engine,frame)


def power_digits_box(frame):
    """Crop after the orange x icon: a short value leaves its tail in the fixed box."""
    import numpy as np
    part=frame[47:64,35:85]
    r,g,b=(part[:,:,i].astype('float32') for i in range(3))
    columns=((r>130)&(g>65)&(r>g*1.12)&(g>b*1.5)).any(axis=0)
    ink=np.flatnonzero(columns)
    if not len(ink):return None
    gaps=np.flatnonzero(np.diff(ink)>1)
    if not len(gaps):return None
    start=35+int(ink[gaps[0]+1])-1
    return (start,47,85-start,17)


def read_short_power(engine,frame):
    """Four- and five-digit power at a low level. Two resamplings must agree exactly."""
    import cv2
    box=power_digits_box(frame) if inventory_parts(frame)==(True,True) else None
    if box is None:return None
    x,y,w,h=box
    patch=cv2.copyMakeBorder(frame[y:y+h,x:x+w],8,8,8,8,cv2.BORDER_CONSTANT,value=(40,40,40))
    a=parse_power(engine.predict(cv2.resize(patch,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)),.92)
    b=parse_power(engine.predict(cv2.resize(patch,None,fx=3,fy=3,interpolation=cv2.INTER_LINEAR)),.92)
    return a if a is not None and a==b else None


class Progress(QuestMemory):
    def __init__(self,root):
        self.path=Path(root)/'settings/owner-progression.json';self.last_query=-1e30
        self.character=None;self.level=None;self.power=None;self.observed=0.;self.records={}
        self.deaths={'main_quest':0,'sub_quest':0};self.last_mode=None;self.last_outcome=None
        self.route='main';self.functional_retries=0
        self.last_death=-1e30
        self.work_mode=None;self.quest_labels={}
        self.records=self.load_records()
    def accept(self,level,power,character):
        if not 1<=level<=50:return False
        unidentified_work=self.work_mode if self.character is None else None
        if self.character is not None and self.character!=character:
            self.deaths={'main_quest':0,'sub_quest':0};self.route='main';self.functional_retries=0
            self.quest_labels={}
        self.character=character;self.level=level;self.power=power;self.observed=time.monotonic()
        self.records.setdefault(character,{'attempted_milestones':[]})
        self.restore_character()
        if unidentified_work in ('main_quest','sub_quest','auto_mode'):self.begin_work(unidentified_work)
        return True
    def due(self):
        if self.level is None or self.character is None:return None
        done=self.records[self.character]['attempted_milestones']
        crossed=[m for m in MILESTONES if m<=self.level and m not in done]
        return max(crossed) if crossed else None
    def attempted(self,milestone):
        if self.character is None or milestone not in MILESTONES:return
        # Catching up at an existing level is one pass, not four back-to-back.
        self.records[self.character]['attempted_milestones']=sorted(set(self.records[self.character]['attempted_milestones'])|{m for m in MILESTONES if m<=milestone})
        self.save()
    def outcome(self,mode,result):
        self.last_mode=mode;self.last_outcome=result
        if result=='DEATH_RECOVERED':
            self.last_death=time.monotonic()
            self.deaths[mode]=self.deaths.get(mode,0)+1
            self.remember_death(mode)
            LOG.info('육성 사망 집계 · 모드=%s · 확인된 사망=%d회 · 레벨=%s',mode,self.deaths[mode],self.level)


def state(adapter):
    result=getattr(adapter,'_owner_progression',None)
    if result is None:result=Progress(adapter.project.root);adapter._owner_progression=result
    return result


def resized(frame,box):
    import cv2
    x,y,w,h=box;roi=frame[y:y+h,x:x+w].copy()
    roi=cv2.copyMakeBorder(roi,8,8,8,8,cv2.BORDER_CONSTANT,value=(40,40,40))
    return cv2.resize(roi,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)


def observe_inventory(service,*,force=False):
    """Read two fresh, already-open inventory frames. Never open another UI."""
    progress=state(service.adapter);now=time.monotonic()
    if not force and now-progress.last_query<45:return False
    progress.last_query=now
    from tools.ocr_support import get_paddle_engine
    number=get_paddle_engine(service.adapter.project.root,language='number')
    korean=get_paddle_engine(service.adapter.project.root,language='korean')
    # Warm models before capturing the evidence frames. Initial model loading
    # must not turn an otherwise valid frame into an old actionable reading.
    job=getattr(service.adapter,'_owner_level_model_job',None)
    if job is None:
        import numpy as np
        job={'ready':threading.Event(),'error':None};service.adapter._owner_level_model_job=job
        def warm():
            try:
                blank=np.full((64,120,3),255,dtype='uint8')
                number.predict(blank);korean.predict(blank)
            except Exception as exc:job['error']=type(exc).__name__
            finally:job['ready'].set()
        threading.Thread(target=warm,name='dkb-level-model-warmup',daemon=True).start()
    end=time.monotonic()+25
    while not job['ready'].is_set() and time.monotonic()<end:
        service.context.wait(.05);service.check()
    if not job['ready'].is_set() or job['error']:
        LOG.info('육성 레벨 판독 보류 · 숫자·한글 모델 준비 미완료');return False
    frames=[]
    for _ in range(2):
        service.check();frames.append(service.capture());service.context.wait(.12)
    if any(frame.shape!=(479,897,3) for frame in frames):return False
    reply=[];done=threading.Event();started=time.monotonic()
    def read():
        try:
            values=[]
            for frame in frames:
                values.append((read_level(number,korean,frame),read_inventory_power(number,frame)))
            reply.append(values)
        except Exception as exc:reply.append(exc)
        finally:done.set()
    old=getattr(service.adapter,'_owner_level_worker',None)
    if old is not None and old.is_alive():return False
    worker=threading.Thread(target=read,name='dkb-level-reader',daemon=True);service.adapter._owner_level_worker=worker;worker.start()
    while not done.is_set() and time.monotonic()-started<8:
        service.context.wait(.05);service.check()
    if not done.is_set() or time.monotonic()-started>3 or not reply or isinstance(reply[0],Exception):
        LOG.info('육성 레벨 판독 보류 · 신선도·응답 조건 미충족');return False
    first,second=reply[0]
    if first!=second or first[0] is None:
        LOG.info('육성 레벨 판독 보류 · 두 화면 판독 불일치');return False
    level,power=first
    # Name glyphs move by one digit width at level 10. Hash only that label.
    import numpy as np
    x=68 if level>=10 else 62
    patch=frames[-1][9:25,x:x+33]
    if not np.array_equal(np.min(patch,axis=2)>150,np.min(frames[0][9:25,x:x+33],axis=2)>150):
        LOG.info('육성 캐릭터 판독 보류 · 두 화면 이름 영역 불일치');return False
    character=hashlib.sha256((np.min(patch,axis=2)>150).tobytes()).hexdigest()[:24]
    from owner_character_binding import observe as bind_character,name_head
    character=bind_character(service.adapter,character,level,name_head(frames[-1]))
    progress.accept(level,power,character)
    from owner_equipment_boxes import agree
    from owner_startup_receipts import Preparation
    try:Preparation(service.adapter.project.root,character).worn(agree(frames[0],frames[1]))
    except (OSError,ValueError):LOG.warning('초기 장비 준비 기록 저장 보류 · 다음 시작에 재확인')
    LOG.info('육성 상태 확인 · 레벨=%d · 전투력=%s · 강화 예정 구간=%s',level,power,progress.due(),extra={'gui_message':f'캐릭터 정보 확인 · 레벨 {level} · 전투력 {power if power is not None else "미확인"}'})
    return True


def install(gui):
    if getattr(gui,'_owner_progression_installed',False):return
    from project_adapter import market_inventory
    if not getattr(market_inventory.open_inventory,'_owner_progression',False):
        ordinary=market_inventory.open_inventory
        @wraps(ordinary)
        def opened(service,*args,**kwargs):
            result=open_inventory_entry(service,ordinary,*args,**kwargs)
            if result is not False:observe_inventory(service)
            return result
        opened._owner_progression=True;market_inventory.open_inventory=opened
    gui._owner_progression_installed=True
