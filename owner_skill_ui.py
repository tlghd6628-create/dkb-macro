"""Bounded visual skill workflow, using the existing target/transaction guards."""
from pathlib import Path
from functools import lru_cache
from collections import OrderedDict
import hashlib,json,logging,re,threading,time
from owner_skill_goal import Pending,STORY,GATES,FINAL,catalog,requested_plan
LOG=logging.getLogger('project_gui.DKB')
ASSETS=Path(__file__).parent/'assets/skill-goal'
SLOTS=((492,420),(530,420),(568,420),(607,420),(645,420),(512,378),(550,378),(588,378))

class ExactRowsCache:
    """Per-UI bounded cache of OCR classifications, never input decisions."""
    def __init__(self,max_entries=64,max_bytes=8*1024*1024):
        self.max_entries=max_entries;self.max_bytes=max_bytes;self.data=OrderedDict();self.bytes=0
    def key(self,frame,box,language,engine):
        x,y,w,h=box;crop=frame[y:y+h,x:x+w]
        # Bytes (not just a hash) make equality exact, including selected row
        # decorations. Absolute box is needed because result coordinates vary.
        return (language,id(engine),tuple(box),crop.shape,crop.dtype.str,crop.tobytes())
    def get(self,key):
        value=self.data.get(key)
        if value is None:return None
        self.data.move_to_end(key)
        return [dict(row) for row in value]
    def put(self,key,rows):
        size=len(key[-1])+sum(len(row.get('text','').encode('utf-8'))+128 for row in rows)
        if size>self.max_bytes:return
        if key in self.data:
            old=self.data.pop(key);self.bytes-=len(key[-1])+sum(len(row.get('text','').encode('utf-8'))+128 for row in old)
        self.data[key]=tuple(dict(row) for row in rows);self.bytes+=size
        while len(self.data)>self.max_entries or self.bytes>self.max_bytes:
            oldkey,old=self.data.popitem(last=False)
            self.bytes-=len(oldkey[-1])+sum(len(row.get('text','').encode('utf-8'))+128 for row in old)

def clean(value):
    value=re.sub(r'[\s\[\],.:·]+','',str(value))
    # This one glyph confusion is reproduced in the saved exact quest title;
    # card image + suffix digit are independently required before selection.
    return value.replace('자격등명','자격증명')

@lru_cache(maxsize=50)
def asset(name):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(ASSETS/(name+'.png')).convert('RGB'))

def match(frame,name,box,threshold=.96):
    import cv2,numpy as np
    if getattr(frame,'shape',None)!=(479,897,3):return None
    x,y,w,h=box;needle=asset(name);image=frame[y:y+h,x:x+w]
    if min(image.shape[:2])==0 or image.shape[0]<needle.shape[0] or image.shape[1]<needle.shape[1]:return None
    scores=cv2.matchTemplate(image,needle,cv2.TM_CCOEFF_NORMED)
    scores=np.where(np.isfinite(scores),scores,-1)
    _,score,_,point=cv2.minMaxLoc(scores)
    if score<threshold:return None
    l,t=x+point[0],y+point[1];hh,ww=needle.shape[:2]
    return (l+ww//2,t+hh//2,(l,t,l+ww,t+hh))

def bright_title(frame,name,box):
    import numpy as np
    hit=match(frame,name,box)
    if not hit:return False
    l,t,r,b=hit[2];expected=asset(name);mask=expected.min(axis=2)>170
    # Normalized correlation alone also matches a dimmed menu behind a
    # modal. Require the original foreground title's bright glyphs as well.
    return bool(mask.sum()>=8 and float((frame[t:b,l:r].min(axis=2)[mask]>150).mean())>=.80)
def skill_screen(frame):return bright_title(frame,'skill-title',(36,7,54,26))
def quest_screen(frame):return bright_title(frame,'quest-title',(36,7,54,26))
def map_screen(frame):return bright_title(frame,'map-title',(51,7,68,26))
def learn_confirm_for(frame,sid):
    """The dialog contains one icon, no readable skill name in saved frame."""
    try:
        if match(frame,'learn-confirm',(378,148,150,28),.96) is None:return False
        if sid!=39:return identify_icon(frame,(412,205,70,75))==sid
        import cv2,numpy as np
        patch=frame[205:280,412:482];src=crossbow_confirm_icon();scores=[]
        for width in (30,32,34):
            im=cv2.resize(src,(width,width),interpolation=cv2.INTER_AREA);m=width//5;im=im[m:-m,m:-m]
            v=cv2.matchTemplate(patch,im,cv2.TM_CCOEFF_NORMED)
            scores.append(float(np.where(np.isfinite(v),v,-1).max()))
        best=max(scores);competitors=[]
        for other in map(int,catalog()['skills']):
            if other==39:continue
            for width in (30,32,34):
                v=cv2.matchTemplate(patch,icon(other,width),cv2.TM_CCOEFF_NORMED)
                competitors.append(float(np.where(np.isfinite(v),v,-1).max()))
        return best>=.90 and bool(competitors) and best-max(competitors)>=.07
    except (OSError,KeyError,ValueError,Pending):return False

def parse_ratio(rows):
    values=set()
    for row in rows:
        if row['score']<.98:continue
        m=re.search(r'([0-9,]+)\s*/\s*([0-9,]+)',row['text'])
        if m:
            current,required=(int(s.replace(',','')) for s in m.groups())
            if required in GATES and 0<=current<=10000000:values.add((current,required))
    return next(iter(values)) if len(values)==1 else None

def selected_quest_box(frame):
    import numpy as np
    if getattr(frame,'shape',None)!=(479,897,3):return None
    mask=(frame[110:438,654:660].min(axis=2)>160).any(axis=1)
    edges=np.diff(np.r_[False,mask,False].astype(np.int8));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
    runs=[(int(a)+110,int(b)+110) for a,b in zip(starts,ends) if 16<=b-a<=55]
    if len(runs)!=1:return None
    a,b=runs[0];return (40,max(108,a-2),615,min(60,b-a+4))

PAIR_SLACK=.1
def paired_rows_match(first,second,minimum=.86):
    # Quantizing y to round(y/4) rejects identical text at a bucket boundary.
    # Keep exact text agreement with small direct geometric tolerances.
    # The same word scoring .91 then .89 is still the same word: the slack is only
    # for agreeing with the other frame. Each reader still requires its own score.
    def covered(rows,others):
        remaining=[r for r in others if r['score']>=minimum-PAIR_SLACK]
        for row in rows:
            if row['score']<minimum:continue
            matches=[i for i,other in enumerate(remaining) if clean(row['text'])==clean(other['text']) and abs(row['y']-other['y'])<=3 and abs(row['x']-other['x'])<=5]
            if not matches:return False
            remaining.pop(min(matches,key=lambda i:abs(row['y']-remaining[i]['y'])+abs(row['x']-remaining[i]['x'])))
        return True
    return covered(first,second) and covered(second,first)

@lru_cache(maxsize=160)
def icon(skill_id,width):
    import cv2,numpy as np
    from PIL import Image
    entry=catalog()['skills'][str(skill_id)]
    path=Path(__file__).parent/entry['icon']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['icon_sha256']:raise Pending('도술 이미지 검증 불일치')
    im=np.asarray(Image.open(path).convert('RGB'))
    im=cv2.resize(im,(width,width),interpolation=cv2.INTER_AREA);margin=width//5
    return im[margin:-margin,margin:-margin]

@lru_cache(maxsize=1)
def chain59_game_icon():
    """Additional candidate image; original public 59 image remains intact."""
    import numpy as np
    from PIL import Image
    path=Path(__file__).parent/'skill_assets_candidate'/'chain_lightning_59_live_a.png'
    if hashlib.sha256(path.read_bytes()).hexdigest()!='73fa1edfc258b0eedba777af696acb706f8a7a042029abab2725bea5c50a3f2a':
        raise Pending('연쇄 번개 게임 이미지 검증 불일치')
    with Image.open(path) as source: image=np.asarray(source.convert('RGB'))
    if image.shape!=(21,21,3):raise Pending('연쇄 번개 게임 이미지 크기 불일치')
    return image

@lru_cache(maxsize=1)
def crossbow_confirm_icon():
    """Specific actual confirmation icon, distinct from its list thumbnail."""
    import numpy as np
    from PIL import Image
    path=Path(__file__).parent/'skill_assets_candidate/icons/39-confirm.png'
    if hashlib.sha256(path.read_bytes()).hexdigest()!='aac6bb50a968af899546ba1cd891c2c8fced26443da8bb06a6778c33ef1dd284':
        raise Pending('쇠뇌 사격 확인 이미지 검증 불일치')
    with Image.open(path) as source:image=np.asarray(source.convert('RGB'))
    if image.shape!=(34,34,3):raise Pending('쇠뇌 사격 확인 이미지 크기 불일치')
    return image

def identify_icon(frame,box,ids=None):
    import cv2,numpy as np
    x,y,w,h=box;patch=frame[y:y+h,x:x+w]
    if getattr(frame,'shape',None)!=(479,897,3) or patch.size==0:return None
    scores=[]
    for sid in (ids if ids is not None else map(int,catalog()['skills'])):
        best=-1.
        for width in (30,32,34):
            image=icon(sid,width)
            if image.shape[0]>h or image.shape[1]>w:continue
            values=cv2.matchTemplate(patch,image,cv2.TM_CCOEFF_NORMED)
            value=float(np.where(np.isfinite(values),values,-1).max())
            best=max(best,value)
        if sid==59:
            image=chain59_game_icon()
            if image.shape[0]<=h and image.shape[1]<=w:
                values=cv2.matchTemplate(patch,image,cv2.TM_CCOEFF_NORMED)
                best=max(best,float(np.where(np.isfinite(values),values,-1).max()))
        scores.append((best,sid))
    scores.sort(reverse=True)
    return scores[0][1] if scores and scores[0][0]>=.90 and (len(scores)==1 or scores[0][0]-scores[1][0]>=.07) else None

def visible_crossbow_y(frame):
    """A list item can hide its name while showing the known skill icon."""
    import cv2,numpy as np
    if getattr(frame,'shape',None)!=(479,897,3):return None
    patch=frame[79:444,695:735];points=[]
    for width in (30,32,34):
        needle=icon(39,width);scores=cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)
        ys,xs=np.where(np.isfinite(scores)&(scores>=.90))
        for y,x in zip(ys,xs):points.append((float(scores[y,x]),79+int(y)+needle.shape[0]//2))
    clusters=[]
    for score,y in sorted(points,reverse=True):
        if any(abs(y-c[1])<=12 for c in clusters):continue
        if 20<=y<459 and identify_icon(frame,(695,y-20,40,40))==39:clusters.append((score,y))
    return clusters[0][1] if len(clusters)==1 else None

def item_name(text,known):
    value=re.sub(r'^\[[^\]]+\]','',text).replace('도술 조각','').replace('도술조각','')
    names=[name for name in known if clean(name)==clean(value)]
    return names[0] if len(names)==1 else None

class NoLearnRow(Pending):
    """No 배우기 row names this skill: it still lacks fragments, or it is already learned."""

class SkillUI:
    def __init__(self,adapter,context,inputs):
        from project_adapter.town_services import TownServices
        from owner_startup_stage import DUNGEON,EXIT,MENU
        from owner_special_contexts import NAMES
        from project_adapter.secret_exploration import AUTO_NAMES
        from project_adapter import market_inventory,guide_rewards,favorite_hunt
        names=list(dict.fromkeys([DUNGEON,EXIT,MENU,'체크_사망상태','버튼_나가기','버튼_X','버튼_메인퀘_도술모두배우기',*NAMES,*AUTO_NAMES,
            *market_inventory.INVENTORY_USE_NAMES,*guide_rewards.NAMES,*favorite_hunt.NAMES]))
        self.service=TownServices(adapter,context,inputs,names)
        self.adapter,self.context,self.inputs=adapter,context,inputs
        self.opened=None;self.changed=False;self.read_worker=None;self.touched=False
        self.public=catalog()
    def _check_identity(self):
        check=getattr(self,'_owner_identity_guard',None)
        if check is not None and (not callable(check) or check() is not True):
            raise Pending('현재 캐릭터·도술 설정 재확인 필요')
    def frame(self):
        self.context.checkpoint();self.service.check();frame=self.service.capture()
        if getattr(frame,'shape',None)!=(479,897,3):raise Pending('도술 작업 해상도 변경 · 화면 재확인 필요')
        return frame
    def wait(self,predicate,seconds=5):
        end=time.monotonic()+seconds
        while True:
            frame=self.frame()
            if predicate(frame):return frame
            if time.monotonic()>=end:raise Pending('도술 화면 전환 확인 시간 초과')
            self.context.wait(.12)
    def click(self,x,y,proof,*,radius=5):
        # Re-read immediately at the input boundary; OCR never authorizes a
        # click after its source menu disappeared or target identity changed.
        frame=self.frame()
        if not proof(frame):raise Pending('도술 입력 직전 화면 변경')
        self._check_identity()
        self.service.click_hit((x,y,(x-radius,y-radius,x+radius+1,y+radius+1)))
        self.touched=True
        self.context.wait(.25)
    def key(self,vk):self.context.checkpoint();self._check_identity();self.service.key(vk);self.touched=True;self.context.wait(.25)
    def drag(self,start,end,proof,*,hold=0):
        if not proof(self.frame()):raise Pending('도술 목록 이동 직전 화면 변경')
        self._check_identity()
        with self.inputs.transaction():
            self.inputs.move(*start);self.context.wait(.05)
            pressed=False
            try:
                self._check_identity()
                pressed=True;self.inputs.down('mouse','left');self.context.wait(.08)
                for n in range(1,17):
                    self.context.checkpoint();self._check_identity()
                    self.inputs.move(round(start[0]+(end[0]-start[0])*n/16),round(start[1]+(end[1]-start[1])*n/16))
                    self.context.wait(.025)
                # Letting go while still moving flings a list further than the drag.
                if hold:self.context.wait(hold)
            finally:
                if pressed:self.inputs.up('mouse','left')
        self.context.wait(.2)
        self.touched=True
    def rows(self,box,*,language='korean',pair=True,pair_minimum=.86,text_mode='raw',_again=0):
        """OCR worker has no input; stale/late responses are discarded."""
        import numpy as np
        from tools.ocr_support import get_paddle_engine
        from owner_progression import resized
        if text_mode not in ('raw','gray'):raise ValueError('unknown OCR text mode')
        if self.read_worker and self.read_worker.is_alive():raise Pending('이전 도술 판독 종료 대기')
        engine=get_paddle_engine(self.adapter.project.root,language=language)
        if getattr(self,'_owner_rows_context',None) is not self.context:
            self._owner_rows_cache=ExactRowsCache();self._owner_rows_context=self.context
            self._owner_rows_engines={}
        engines=self._owner_rows_engines
        if language in engines and engines[language] is not engine:
            self._owner_rows_cache=ExactRowsCache()
        engines[language]=engine
        cache=self._owner_rows_cache
        self._owner_last_rows_pair=None;self._owner_last_rows_raw=None
        answers=[];done=threading.Event();ticks=[time.monotonic()];frames=[self.frame().copy()]
        if pair:
            self.context.wait(.12);ticks.append(time.monotonic());frames.append(self.frame().copy())
        started=time.monotonic()
        def read_only():
            try:
                for frame in frames:
                    key=cache.key(frame,box,language if text_mode=='raw' else language+':gray',engine)
                    cached=cache.get(key)
                    if cached is not None:
                        answers.append(cached);continue
                    found=[]
                    source=resized(frame,box)
                    if text_mode=='gray':
                        import cv2
                        source=cv2.cvtColor(cv2.cvtColor(source,cv2.COLOR_RGB2GRAY),cv2.COLOR_GRAY2RGB)
                    for page in engine.predict(source):
                        for index,(text,score) in enumerate(zip(page.get('rec_texts',()),page.get('rec_scores',()))):
                            polys=page.get('rec_polys',())
                            if len(polys)<=index:continue
                            poly=np.asarray(polys[index]);cx,cy=poly.mean(axis=0)/4-8
                            lo=poly.min(axis=0)/4-8;hi=poly.max(axis=0)/4-8
                            found.append({'text':str(text),'score':float(score),'x':round(box[0]+cx),'y':round(box[1]+cy),
                                'bounds':(max(0,round(box[0]+lo[0])-2),max(0,round(box[1]+lo[1])-2),min(897,round(box[0]+hi[0])+3),min(479,round(box[1]+hi[1])+3))})
                    cache.put(key,found);answers.append(found)
            except Exception as exc:answers.append(exc)
            finally:done.set()
        self.read_worker=threading.Thread(target=read_only,name='dkb-skill-read-only',daemon=True);self.read_worker.start()
        while not done.is_set() and time.monotonic()-started<3:
            self.context.wait(.05);self.context.checkpoint()
        if not done.is_set() or time.monotonic()-started>3 or len(answers)!=len(frames) or any(isinstance(x,Exception) for x in answers):raise Pending('도술 판독 신선도/응답 확인 필요')
        if pair:
            a,b=answers
            if not paired_rows_match(a,b,pair_minimum):
                self._owner_last_pair_mismatch={'first':a,'second':b}
                # Pulsing dots and a list still gliding spoil one pair. The agreement needed is the same.
                if _again<4:
                    self.context.wait(.4)
                    return self.rows(box,language=language,pair=pair,pair_minimum=pair_minimum,text_mode=text_mode,_again=_again+1)
                LOG.info('도술 두 화면 판독 불일치 · 영역=%s · %s / %s',box,[(r['text'],round(r['score'],2)) for r in a][:8],[(r['text'],round(r['score'],2)) for r in b][:8])
                raise Pending('도술 두 화면 판독 불일치')
            self._owner_last_rows_pair=(frames,ticks,answers)
        self.last_text_frame=frames[-1];self.last_text_tick=ticks[-1]
        return answers[-1]
    def prepare_batch_engines(self,languages=('korean','number')):
        """Warm model inference before a source frame is captured (no input)."""
        from tools.ocr_support import get_paddle_engine
        from owner_progression import resized
        from PIL import Image,ImageDraw
        import numpy as np
        if self.read_worker and self.read_worker.is_alive():raise Pending('이전 도술 판독 종료 대기')
        engines={lang:get_paddle_engine(self.adapter.project.root,language=lang) for lang in languages}
        warmed=getattr(self,'_owner_batch_warmed',{})
        todo=[(lang,engine) for lang,engine in engines.items() if warmed.get(lang) is not engine]
        if not todo:return engines
        dummy=Image.new('RGB',(220,80),'white');ImageDraw.Draw(dummy).text((8,16),'10/1 123 ABC',fill='black')
        crop=np.asarray(dummy);done=threading.Event();errors=[];start=time.monotonic()
        def warm():
            try:
                for _,engine in todo:list(engine.predict(resized(crop,(0,0,220,80))))
            except Exception as exc:errors.append(exc)
            finally:done.set()
        self.read_worker=threading.Thread(target=warm,name='dkb-skill-ocr-warmup',daemon=True);self.read_worker.start()
        while not done.is_set() and time.monotonic()-start<45:
            self.context.wait(.05);self.context.checkpoint()
        if not done.is_set() or errors:raise Pending('도술 판독기 준비 확인 필요')
        self._owner_batch_warmed=dict(engines)
        return engines
    def rows_batch(self,specs):
        """Classify several ROIs from the same fresh frame pair, read-only.

        Cached values are OCR results only. The caller must revalidate every
        critical pixel on new frames before any action; this method does not
        authorize input. Load engines before capture so cold startup does not
        age the source images before recognition begins.
        """
        import numpy as np
        from owner_progression import resized
        if self.read_worker and self.read_worker.is_alive():raise Pending('이전 도술 판독 종료 대기')
        if not specs:raise ValueError('판독 영역 없음')
        specs=[(item[0],item[1],item[2],item[3] if len(item)>=4 else 'original',item[4] if len(item)>=5 else None,item[5] if len(item)>=6 else None) for item in specs]
        if any(mode not in ('original','clahe','binary','original_or_clahe') or (mode=='original_or_clahe' and (language!='number' or agreement is None)) or (predicate is not None and not callable(predicate)) or (agreement is not None and not callable(agreement)) for _,language,_,mode,predicate,agreement in specs):raise ValueError('판독 방식 오류')
        engines=self.prepare_batch_engines(tuple(dict.fromkeys(lang for _,lang,_,_,_,_ in specs)))
        if getattr(self,'_owner_rows_context',None) is not self.context:
            self._owner_rows_cache=ExactRowsCache();self._owner_rows_context=self.context;self._owner_rows_engines={}
        for lang,engine in engines.items():
            if lang in self._owner_rows_engines and self._owner_rows_engines[lang] is not engine:
                self._owner_rows_cache=ExactRowsCache()
            self._owner_rows_engines[lang]=engine
        cache=self._owner_rows_cache;self._owner_last_rows_pair=None;self._owner_last_rows_raw=None
        ticks=[time.monotonic()];frames=[self.frame().copy()]
        self.context.wait(.12);ticks.append(time.monotonic());frames.append(self.frame().copy())
        done=threading.Event();answers=[];raw_answers=[];started=time.monotonic()
        def read_only():
            try:
                for box,language,minimum,mode,predicate,agreement in specs:
                    engine=engines[language];agrees=False
                    # A short material's red count is lost in grey ("3/5" read as "/5").
                    # The brightest channel keeps it at .99 without touching white digits.
                    variants=('original','clahe','peak') if mode=='original_or_clahe' else (mode,)
                    for variant in variants:
                        pair=[];raw_pair=[]
                        for frame in frames:
                            key=cache.key(frame,box,language+'\x00'+variant,engine);found=cache.get(key)
                            if found is None:
                                found=[];image=resized(frame,box)
                                if variant=='clahe':
                                    import cv2
                                    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                                    image=cv2.cvtColor(cv2.createCLAHE(2,(8,8)).apply(gray),cv2.COLOR_GRAY2RGB)
                                elif variant=='binary':
                                    import cv2
                                    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                                    image=cv2.cvtColor(cv2.threshold(gray,120,255,cv2.THRESH_BINARY)[1],cv2.COLOR_GRAY2RGB)
                                elif variant=='peak':
                                    import cv2
                                    image=cv2.cvtColor(image.max(axis=2),cv2.COLOR_GRAY2RGB)
                                for page in engine.predict(image):
                                    for i,(text,score) in enumerate(zip(page.get('rec_texts',()),page.get('rec_scores',()))):
                                        polys=page.get('rec_polys',())
                                        if len(polys)<=i:continue
                                        poly=np.asarray(polys[i]);cx,cy=poly.mean(axis=0)/4-8
                                        lo=poly.min(axis=0)/4-8;hi=poly.max(axis=0)/4-8
                                        found.append({'text':str(text),'score':float(score),'x':round(box[0]+cx),'y':round(box[1]+cy),
                                            'bounds':(max(0,round(box[0]+lo[0])-2),max(0,round(box[1]+lo[1])-2),min(897,round(box[0]+hi[0])+3),min(479,round(box[1]+hi[1])+3))})
                                cache.put(key,found)
                            raw_pair.append([dict(row) for row in found])
                            pair.append([row for row in found if predicate(row)] if predicate else found)
                        # Optional numeric alternate uses the SAME two source
                        # frames. Its verifier retains strong per-frame values
                        # across variants and rejects any contradiction.
                        agrees=(agreement(pair[0],pair[1]) is True if agreement is not None else paired_rows_match(pair[0],pair[1],minimum))
                        if agrees:break
                    if not agrees:raise Pending('도술 두 화면 판독 불일치: '+str(box))
                    answers.append(pair);raw_answers.append(raw_pair)
            except Exception as exc:answers.append(exc)
            finally:done.set()
        self.read_worker=threading.Thread(target=read_only,name='dkb-skill-batch-read-only',daemon=True);self.read_worker.start()
        while not done.is_set() and time.monotonic()-started<12:
            self.context.wait(.05);self.context.checkpoint()
        if answers and isinstance(answers[-1],Pending):raise answers[-1]
        if not done.is_set() or len(answers)!=len(specs) or any(isinstance(x,Exception) for x in answers):
            raise Pending('도술 일괄 판독 응답 확인 필요')
        self._owner_last_rows_pair=(frames,ticks,[p[1] for p in answers])
        # Observational metadata only. A consumer may publish other visible
        # style values after its own per-row agreement/fresh-pixel checks;
        # unrelated noisy rows still cannot invalidate the selected action.
        self._owner_last_rows_raw=(frames,ticks,raw_answers)
        self.last_text_frame=frames[-1];self.last_text_tick=ticks[-1]
        return [p[1] for p in answers]
    def word(self,text,box,minimum=.90,*,exact=False):
        rows=self.rows(box)
        candidates=[r for r in rows if r['score']>=minimum and (clean(r['text'])==clean(text) if exact else clean(text) in clean(r['text']))]
        if len(candidates)!=1:
            LOG.debug('도술 판독 대조 보류 · 기대=%s · 후보=%s',text,[(r['text'][:60],round(r['score'],3)) for r in rows])
            raise Pending('도술 표시 확인 필요: '+text)
        return candidates[0]
    def click_word(self,text,box,proof,minimum=.90):
        import cv2,numpy as np
        row=self.word(text,box,minimum);l,t,r,b=row['bounds'];source=self.last_text_frame[t:b,l:r].copy();tick=self.last_text_tick
        def fresh(frame):
            patch=frame[t:b,l:r]
            if time.monotonic()-tick>3 or patch.shape!=source.shape or not proof(frame):return False
            value=float(cv2.matchTemplate(patch,source,cv2.TM_CCOEFF_NORMED)[0,0])
            return np.isfinite(value) and value>=.97
        self.click(row['x'],row['y'],fresh);return row
    def normal(self):
        from owner_startup_stage import scene
        first=scene(self.service.detector,self.frame());self.context.wait(.15)
        return first==scene(self.service.detector,self.frame())=='field'
    def open_skills(self):
        if not skill_screen(self.frame()):
            if not self.normal():raise Pending('도술 창 열기 전 일반 필드 확인 필요')
            self.key(0x4b)
        self.wait(skill_screen);self.opened='skill'
    def close_known(self):
        # In-flight OCR keeps only its old local cache; it cannot repopulate a
        # closed/reused UI's next cache after this reference is discarded.
        self._owner_rows_cache=None;self._owner_rows_context=None;self._owner_rows_engines={}
        self._owner_last_rows_raw=None;self._owner_last_rows_pair=None
        self._owner_style_bindings={};self._owner_style_bindings_context=None
        self._owner_growth_deadline=None
        if getattr(self.context,'stop',None) is not None and self.context.stop.is_set():return
        frame=self.frame()
        if self.opened=='shop' and match(frame,'shop-quantity',(408,150,84,28),.96):
            self.click(411,302,lambda f:match(f,'shop-quantity',(408,150,84,28),.96) is not None)
            frame=self.frame()
        if self.opened=='skill' and match(frame,'learn-confirm',(378,148,150,28),.96):
            self.click(411,315,lambda f:match(f,'learn-confirm',(378,148,150,28),.96) is not None)
            frame=self.frame()
        if self.opened=='skill' and match(frame,'order-title',(410,40,80,27),.96):
            self.click(425,441,lambda f:match(f,'order-title',(410,40,80,27),.96) is not None)
            frame=self.frame()
        if self.opened=='skill' and match(frame,'preset-copy-notice',(365,228,170,33),.96):
            self.click(450,282,lambda f:match(f,'preset-copy-notice',(365,228,170,33),.96) is not None)
            frame=self.frame()
        if self.opened=='quest' and match(frame,'quest-search-close',(866,11,20,22),.96) and float((frame[44:64,20:790].min(axis=2)>140).mean())>.7:
            self.click(876,21,lambda f:match(f,'quest-search-close',(866,11,20,22),.96) is not None)
            frame=self.wait(quest_screen)
        if self.opened=='skill' and skill_screen(frame):self.key(0x4b)
        elif self.opened=='quest' and quest_screen(frame):self.key(0x4a)
        elif self.opened=='shop':
            self.word('도술 상점',(30,1,200,30));self.click(21,19,lambda f:not skill_screen(f) and not quest_screen(f))
        elif self.opened=='map' and map_screen(frame):self.click(21,19,map_screen)
        self.opened=None
        if self.touched:
            # Closing a menu may pass through a loading/blur transition. Do
            # not issue more input until the original field proof returns.
            self.wait(lambda f:self.normal_frame(f),seconds=20)
    def search(self,text):
        # This is an ordinary game's search field, never an auth dialog.
        self.click(770,54,quest_screen)
        self.wait(lambda f:float((f[44:64,20:790].min(axis=2)>140).mean())>.7)
        self.click(120,54,lambda f:float((f[44:64,20:790].min(axis=2)>140).mean())>.7)
        self.clear_text();self.text(text);self.key(0x0d)
    def text(self,text):
        """Normal foreground Unicode keyboard entry inside the shared lock.

        Does not read/write game memory and never changes the clipboard.
        """
        if not isinstance(text,str) or len(text)>40:raise Pending('검색어 길이 확인 필요')
        self._check_identity()
        import ctypes,win32gui
        from ctypes import wintypes as W
        class KEY(ctypes.Structure):_fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
        class MOUSE(ctypes.Structure):_fields_=[('x',W.LONG),('y',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
        class UNION(ctypes.Union):_fields_=[('ki',KEY),('mi',MOUSE)]
        class INPUT(ctypes.Structure):_fields_=[('type',W.DWORD),('value',UNION)]
        send=ctypes.windll.user32.SendInput;send.argtypes=[W.UINT,ctypes.POINTER(INPUT),ctypes.c_int];send.restype=W.UINT
        with self.inputs.transaction():
            self.inputs._guard_target()
            hwnd=self.adapter.window.hwnd
            if win32gui.GetForegroundWindow()!=hwnd:raise Pending('검색 문자 입력 전 게임 포커스 확인 필요')
            for character in text:
                self.context.checkpoint();self._check_identity();self.inputs._guard_target()
                if win32gui.GetForegroundWindow()!=hwnd:raise Pending('검색 문자 입력 중 게임 포커스 변경')
                pair=(INPUT*2)(INPUT(1,UNION(ki=KEY(0,ord(character),4,0,0))),INPUT(1,UNION(ki=KEY(0,ord(character),6,0,0))))
                if send(2,pair,ctypes.sizeof(INPUT))!=2:raise Pending('검색 문자 입력 미완료')
                self.context.wait(.02)
    def open_story(self):
        if not quest_screen(self.frame()):
            if not self.normal():raise Pending('서사 선택 전 일반 필드 확인 필요')
            self.key(0x4a)
        self.wait(quest_screen);self.opened='quest';self.click(146,54,quest_screen)
    def select_story(self,step):
        self.search('도술 구매')
        # Six fixed search cards were observed: power1, learn1,2 / 3,4,5.
        points={1:(120,91),2:(698,91),3:(120,133),4:(408,133),5:(698,133)}
        point=points[step]
        cardbox={1:(48,72,183,32),2:(640,72,168,32),3:(48,116,183,32),4:(336,116,184,32),5:(640,116,168,32)}[step]
        self.wait(lambda f:match(f,'story-search-'+str(step),cardbox,.96) is not None)
        self.click(*point,lambda f:match(f,'story-search-'+str(step),cardbox,.96) is not None)
        self.wait(quest_screen)
        if step==5 and match(self.frame(),'story-title5',(685,77,174,27),.97):return
        self.word(STORY+str(step),(681,78,190,22),minimum=.86)
    def story(self,ledger,progress):
        self.open_story()
        for step in range(max(1,ledger.item.get('story_step',0)+1),6):
            if step==2 and not ledger.item.get('tutorial_completed'):self.tutorial_objective(ledger)
            self.select_story(step)
            if step==1:
                # Before skill qualification1, the named first-step dialog is
                # an actual prerequisite. Do not click a grey acceptance row.
                try:prereq=self.word('도술의 달인',(674,244,200,102),minimum=.90)
                except Pending:prereq=None
                if prereq:
                    self.search('도술의 달인')
                    self.click_word('도술의 달인',(25,68,230,50),lambda f:float((f[44:64,20:790].min(axis=2)>140).mean())>.7,minimum=.88)
                    self.wait(quest_screen);self.word('도술의 달인',(675,76,200,35),minimum=.90)
                    self.run_selected_story();raise Pending('도술의 달인 선행 서사 진행 후 재확인')
            # Search selects the exact quest and scrolls it into view. The
            # native list's explicit circle-check means completed, not Auto.
            box=selected_quest_box(self.frame())
            if box is None:raise Pending('선택한 도술 서사 행의 흰 테두리 확인 필요')
            rows=self.rows(box)
            selected=[r for r in rows if r['score']>=.86 and clean(STORY+str(step)) in clean(r['text'])]
            # Two different objectives are both numbered1. Only the white
            # outlined selected row can authorize its completion receipt.
            frame=self.frame()
            selected=[r for r in selected if int((frame[max(0,r['y']-15):r['y']+16,655:659].min(axis=2)>145).sum())>=16]
            if len(selected)==1:
                row=selected[0];box=(624,max(114,row['y']-13),25,26)
                first=match(self.frame(),'completed',box,.96);self.context.wait(.12)
                if first and match(self.frame(),'completed',box,.96):
                    ledger.story_receipt(step,{'title':STORY+str(step),'verified':True,'source':'two_fresh_exact_quest_row_completed_marks'})
                    continue
            ratio=parse_ratio(self.rows((796,262,72,17),language='number'))
            if ratio:
                current,required=ratio
                if required!=GATES[step-1]:raise Pending('선택 도술 서사와 전투력 조건 불일치')
                if current<required:
                    ledger.hold(f'도술 서사 {step} · 전투력 {current:,}/{required:,} · 기존 육성 계속',required_power=required,last_power=current)
                    return
            required=GATES[step-1]
            if ratio is None and progress.power is not None and time.monotonic()-progress.observed<=180 and progress.power<required:
                ledger.hold(f'도술 서사 {step} · 전투력 {progress.power:,}/{required:,} · 기존 육성 계속',required_power=required,last_power=progress.power)
                return
            if ratio is None and (progress.power is None or time.monotonic()-progress.observed>180 or progress.power<required):raise Pending('도술 서사 전투력 조건 판독 필요')
            # Only the verified selected quest's accept/auto button. Native
            # runner handles dialog/tutorial/death. No arbitrary confirmation.
            self.run_selected_story()
            self.open_story();self.select_story(step)
            raise Pending('도술 서사 진행 후 완료 표시 재검증 대기 · 다음 안전 시점 재확인')
    def confirm_final_story(self,ledger):
        """Read the exact final leaf through Missions; never accept or run it.

        Group-based quest execution does not visit the old selected-leaf
        receipt writer. Reconcile at a real quest boundary, including after a
        restart, rather than treating quest disappearance or power as clear.
        """
        if ledger.item.get('story_step')==5:return True
        self.open_story();self.select_story(5)
        def completed_final(frame):
            if not quest_screen(frame) or not match(frame,'story-title5',(685,77,174,27),.97):return False
            box=selected_quest_box(frame)
            if box is None:return False
            y=round(box[1]+box[3]/2)
            return bool(match(frame,'completed',(624,max(114,y-14),28,28),.96))
        first=completed_final(self.frame());self.context.wait(.12)
        if not first or not completed_final(self.frame()):return False
        ledger.story_receipt(5,{'title':STORY+'5','verified':True,
                              'source':'two_fresh_exact_final_mission_header_selected_leaf_completed_marks'})
        return True
    def run_selected_story(self):
        accepted=False
        try:self.click_word('임무 수락',(675,432,200,40),quest_screen);accepted=True
        except Pending:self.click_word('자동 진행',(750,432,130,40),quest_screen)
        if accepted and quest_screen(self.frame()):self.click_word('자동 진행',(750,432,130,40),quest_screen)
        self.wait(lambda f:not quest_screen(f),seconds=12);self.opened=None
        self.adapter._owner_skill_return_mode=self.adapter.mode
        before=getattr(self.adapter,'_owner_temporary_work',None);self.adapter._owner_temporary_work='skill_story'
        try:
            from project_adapter.main_quest import BoundedMainQuestRunner,StateROIs,dependencies
            profile,deps=dependencies(self.adapter,self.context,self.inputs)
            runner=BoundedMainQuestRunner(StateROIs(profile,mode='sub_quest'),**deps)
            end=time.monotonic()+180
            while time.monotonic()<end:
                self.context.checkpoint();result=runner.step()
                if result=='DEATH_RECOVERED':raise Pending('도술 해금 서사 사망 확인 · 원래 육성으로 복귀')
                if self.normal() and time.monotonic()>end-160:break
                self.context.wait(.1)
        finally:self.adapter._owner_temporary_work=before
    def tutorial_objective(self,ledger):
        self.open_story();self.search('도술 구매')
        proof=lambda f:match(f,'story-search-tutorial1',(336,72,184,32),.96) is not None
        self.wait(proof);self.click(408,91,proof);self.wait(quest_screen)
        self.word(STORY+'1',(676,76,199,36),minimum=.86)
        box=selected_quest_box(self.frame())
        if box is None:raise Pending('선택한 학습 서사 행 확인 필요')
        rows=self.rows(box);frame=self.frame()
        selected=[r for r in rows if r['score']>=.86 and clean(STORY+'1') in clean(r['text']) and int((frame[max(0,r['y']-15):r['y']+16,655:659].min(axis=2)>145).sum())>=16]
        if len(selected)==1:
            row=selected[0];box=(624,max(114,row['y']-13),25,26)
            first=match(frame,'completed',box,.96);self.context.wait(.12)
            if first and match(self.frame(),'completed',box,.96):
                ledger.item['tutorial_completed']=True;ledger.event('tutorial_objective_completed');return
        # The exact observed tutorial card names a learning objective. Only
        # its single known 100-fragment coin purchase is allowed before5.
        self.word('도술',(676,245,198,48),minimum=.90)
        ledger.item['tutorial_required']='쇠뇌 사격';ledger.event('tutorial_purchase_required')
        self.close_known();owned=self.scan_owned();self.close_known()
        sid=self.public['all_skill_names']['쇠뇌 사격']['id']
        if sid not in owned:
            previous=ledger.item.get('purchases',{}).get(str(sid),{})
            if previous.get('status')=='intent':raise Pending('서사 필수 도술 이전 구매 결과 확인 필요')
            if previous.get('status')!='confirmed':
                self.enter_shop('저격');rows=self.shop_rows('저격')
                found=[r for r in rows if r['id']==sid]
                if len(found)!=1:raise Pending('서사 필수 쇠뇌 사격 품목 확인 필요')
                if not self.buy_one(ledger,found[0],tutorial=True):raise Pending('서사 필수 쇠뇌 사격 구매 가능 여부 확인 필요')
                self.close_known()
            self.learn_one(sid,ledger,tutorial=True)
        self.close_known();self.open_story()
        raise Pending('서사 필수 도술 확인 완료 · 임무 완료 표시 재확인')
    def skill_rows(self):
        # A flicked list keeps gliding, and the two reads disagree until it stops. Nothing is pressed here.
        # Only skill names have to agree: stray text over the moving art held this whole list before.
        known={clean(name):name for name in self.public['all_skill_names']}
        for attempt in range(8):
            self.rows_batch([((729,79,80,365),'korean',.88,'original',None,lambda a,b:True)])
            first,second=self._owner_last_rows_raw[2][0]
            def named(rows):return [dict(r,name=known[clean(r['text'])]) for r in rows if clean(r['text']) in known]
            a,b=named(first),named(second)
            def has(row,others,floor):return any(o['name']==row['name'] and o['score']>=floor and abs(o['y']-row['y'])<=3 and abs(o['x']-row['x'])<=5 for o in others)
            floor=.88-PAIR_SLACK
            if all(has(r,b,floor) for r in a if r['score']>=.88) and all(has(r,a,floor) for r in b if r['score']>=.88):break
            if attempt==7:raise Pending('도술 두 화면 판독 불일치')
            self.context.wait(.5)
        ids=self.public['all_skill_names']
        return [dict(r,id=ids[r['name']]['id']) for r in b if r['score']>=.88]
    def all_filter(self,owned_only):
        # The top All category scrolls with the style bar; locate its text.
        try:self.click_word('전체',(850,30,45,450),skill_screen,minimum=.90)
        except Pending:
            for _ in range(5):self.drag((868,100),(868,435),skill_screen)
            self.click_word('전체',(850,30,45,450),skill_screen,minimum=.90)
        checked=match(self.frame(),'skill-checked-all',(687,57,18,18),.96) is not None
        if checked==owned_only:self.click(696,66,skill_screen)
    def scan_owned(self):
        self.open_skills();self.all_filter(True)
        for _ in range(3):self.drag((762,118),(762,424),skill_screen)
        found=set();previous=None
        for _ in range(24):
            page=self.skill_rows()
            if not page:raise Pending('보유 도술 목록 판독 실패 · 중복 구매 보류')
            signature=tuple((r['id'],r['y']) for r in page)
            found.update(r['id'] for r in page)
            if signature==previous:return found
            previous=signature;self.drag((762,425),(762,117),skill_screen)
        raise Pending('보유 도술 목록 끝 확인 실패')
    def find_skill(self,sid):
        self.all_filter(False)
        for _ in range(3):self.drag((762,118),(762,424),skill_screen)
        previous=None
        for _ in range(24):
            rows=self.skill_rows();hit=next((r for r in rows if r['id']==sid),None)
            if hit:
                if sid==59:
                    self._click_chain59_paired(hit)
                    return hit
                # Public icon is independently paired with exact skill name;
                # dim locked entries do not meet the colored icon proof.
                if identify_icon(self.frame(),(695,hit['y']-20,40,40))!=sid:raise Pending('선택 도술 아이콘/이름 대조 실패: '+hit['name'])
                self.click(754,hit['y'],skill_screen);return hit
            if sid==39:
                # The real unlearned row can show only a greyed name; its
                # verified icon plus two frames may select the row, but the
                # paired exact full title must still be read after selection.
                pair=getattr(self,'_owner_last_rows_pair',None)
                if pair:
                    frames,ticks,_=pair;now=time.monotonic()
                    if (len(frames)==2 and len(ticks)==2 and frames[0] is not frames[1]
                        and not __import__('numpy').shares_memory(frames[0],frames[1])
                        and all(0<=now-t<=3 for t in ticks)
                        and all(skill_screen(frame) for frame in frames)):
                        a,b=(visible_crossbow_y(frame) for frame in frames)
                        if a is not None and b is not None and abs(a-b)<=3:
                            def same_icon(frame):
                                if not skill_screen(frame):return False
                                found=visible_crossbow_y(frame)
                                return found is not None and abs(found-b)<=3
                            self.click(754,b,same_icon)
                            self.word('쇠뇌 사격',(46,70,155,25),minimum=.94,exact=True)
                            return {'id':39,'name':'쇠뇌 사격','y':b}
            signature=tuple((r['id'],r['y']) for r in rows)
            if not rows or signature==previous:break
            previous=signature;self.drag((762,425),(762,117),skill_screen)
        raise Pending('도술 목록에서 찾지 못함: '+self.public['skills'][str(sid)]['name'])
    def _click_chain59_paired(self,hit):
        """Use paired exact OCR+all-catalog image proof and recheck on click."""
        import cv2,numpy as np
        pair=getattr(self,'_owner_last_rows_pair',None)
        if not pair:raise Pending('연쇄 번개 두 화면 확인 필요')
        frames,ticks,answers=pair;now=time.monotonic()
        if len(frames)!=2 or len(ticks)!=2 or frames[0] is frames[1] or np.shares_memory(frames[0],frames[1]):
            raise Pending('연쇄 번개 서로 다른 화면 확인 필요')
        if any(t>now or now-t>3 for t in ticks):raise Pending('연쇄 번개 화면 판독 지연')
        found=[]
        for frame,items in zip(frames,answers):
            hits=[r for r in items if r['score']>=.88 and clean(r['text'])==clean('연쇄 번개')]
            if len(hits)!=1 or abs(hits[0]['y']-hit['y'])>3 or not skill_screen(frame):
                raise Pending('연쇄 번개 이름 두 화면 대조 실패')
            box=(695,hits[0]['y']-20,40,40)
            if identify_icon(frame,box)!=59:raise Pending('연쇄 번개 아이콘 두 화면 대조 실패')
            found.append(hits[0])
        if abs(found[0]['x']-found[1]['x'])>5 or abs(found[0]['y']-found[1]['y'])>3:
            raise Pending('연쇄 번개 목록 위치 변경')
        row=found[-1];l,t,r,b=row['bounds']
        if not (0<=l<r<=897 and 0<=t<b<=479):raise Pending('연쇄 번개 이름 영역 불명')
        source=frames[-1][t:b,l:r].copy();tick=ticks[-1];y=row['y']
        def fresh(frame):
            patch=frame[t:b,l:r]
            if time.monotonic()-tick>3 or patch.shape!=source.shape or not skill_screen(frame):return False
            value=float(cv2.matchTemplate(patch,source,cv2.TM_CCOEFF_NORMED)[0,0])
            return np.isfinite(value) and value>=.97 and identify_icon(frame,(695,y-20,40,40))==59
        self.click(754,y,fresh)
    def learn_available(self):
        # Legacy bulk button can learn an unapproved 강인 skill along with the
        # desired ones. Exact individual skill learning is not yet verified.
        raise Pending('선택한 도술만 배우기 확인 필요 · 전체 학습 보류')
    def learn_one(self,sid,ledger,*,tutorial=False,coupon=False):
        """Learn exactly one authorized skill; unknown visual proof is held.

        Saved screenshots show an individual '배우기' button and a one-icon
        dialog, but their click-to-receipt chain still requires live testing.
        """
        import cv2,numpy as np
        entry=self.public.get('skills',{}).get(str(sid))
        if coupon and not entry:
            # A skill picked for the fragment box may have no public image; its title still names it.
            found=[n for n,v in self.public.get('all_skill_names',{}).items() if v.get('id')==sid]
            if found:entry={'name':found[0],'style':self.public['all_skill_names'][found[0]].get('style')}
        if not entry:raise Pending('개별 도술 이미지가 없어 학습 보류')
        style=entry.get('style');name=entry.get('name')
        allowed=(style in ('파멸','강타') or sid in (84,68,89))
        if tutorial:
            allowed=(ledger.item.get('story_step')==1 and ledger.item.get('tutorial_required')=='쇠뇌 사격' and name=='쇠뇌 사격')
        elif coupon:
            from owner_progression import state
            from owner_hunt_rules_candidate import configured_identity
            from owner_starter_choice_candidate import chosen_skills
            progress=state(self.adapter)
            age=time.monotonic()-progress.observed
            picked=[row[0] for row in chosen_skills(self.adapter.project.root,configured_identity(self.adapter.project.root))]
            allowed=(sid in picked and progress.character==getattr(ledger,'character',None)
                     and type(progress.level) is int and progress.level>=30
                     and 0<=age<=180)
        elif ledger.item.get('story_step')!=5:allowed=False
        if not allowed:raise Pending('승인하지 않은 도술 개별 학습 보류')
        if coupon:return self._learn_target(sid,name,ledger)
        owned=self.scan_owned()
        if not isinstance(owned,set):raise Pending('도술 학습 전 보유 확인 필요')
        if sid in owned:
            old=ledger.item.get('learning_intents',{}).get(str(sid))
            if old and old.get('status')=='intent':
                old.update(status='confirmed',proof='fresh_paired_owned_scan')
                ledger.event('individual_learning_reconciled',skill=sid)
            return True
        if ledger.item.get('learning_intents',{}).get(str(sid),{}).get('status')=='intent':
            raise Pending('이전 도술 학습 결과 확인 필요: '+name)
        self.open_skills();row=self.find_skill(sid)
        selected=self.word(name,(46,70,155,25),minimum=.94,exact=True)
        l,t,r,b=selected['bounds'];title=self.last_text_frame[t:b,l:r].copy();tick=self.last_text_tick
        if not (0<=l<r<=897 and 0<=t<b<=479) or not title.size or float(title.std())<10:
            raise Pending('선택 도술 이름 영역 확인 필요')
        def selected_proof(frame):
            patch=frame[t:b,l:r]
            if time.monotonic()-tick>3 or patch.shape!=title.shape or not skill_screen(frame):return False
            value=float(cv2.matchTemplate(patch,title,cv2.TM_CCOEFF_NORMED)[0,0])
            return bool(np.isfinite(value) and value>=.97 and identify_icon(frame,(695,row['y']-20,40,40))==sid)
        self.click_word('배우기',(798,row['y']-15,35,30),selected_proof,minimum=.94)
        first_at=time.monotonic();first=self.frame();self.context.wait(.12)
        second_at=time.monotonic();second=self.frame();now=time.monotonic()
        if (first is second or np.shares_memory(first,second) or now-first_at>3 or now-second_at>3
            or not learn_confirm_for(first,sid) or not learn_confirm_for(second,sid)):
            raise Pending('선택 도술과 개별 학습 확인창 불일치')
        intents=ledger.item.setdefault('learning_intents',{})
        intents[str(sid)]={'status':'intent','skill':name,'at':time.time()}
        ledger.event('individual_learning_intent',skill=sid,name=name)
        self.click_word('확인',(430,290,112,55),lambda f:learn_confirm_for(f,sid),minimum=.94)
        rows=self.rows((280,70,340,240))
        if (not any(r['score']>=.94 and clean('새로운 도술') in clean(r['text']) for r in rows)
            or not any(r['score']>=.94 and clean(r['text'])==clean(name) for r in rows)):
            raise Pending('획득 도술 이름 확인 필요: '+name)
        names=[r for r in rows if r['score']>=.94 and clean(r['text'])==clean(name)]
        if len(names)!=1:raise Pending('획득 도술 이름 중복')
        l,t,r,b=names[0]['bounds'];source=self.last_text_frame[t:b,l:r].copy();receipt_tick=self.last_text_tick
        if not (0<=l<r<=897 and 0<=t<b<=479) or not source.size or float(source.std())<10:
            raise Pending('획득 도술 이름 영역 확인 필요')
        def same_receipt(frame):
            patch=frame[t:b,l:r]
            if time.monotonic()-receipt_tick>3 or patch.shape!=source.shape:return False
            value=float(cv2.matchTemplate(patch,source,cv2.TM_CCOEFF_NORMED)[0,0])
            return np.isfinite(value) and value>=.97
        self.click_word('새로운 도술',(280,70,340,240),same_receipt,minimum=.94)
        self.wait(skill_screen,seconds=8)
        after=self.scan_owned()
        if not isinstance(after,set) or sid not in after:raise Pending('개별 도술 학습 후 보유 확인 필요: '+name)
        intents[str(sid)].update(status='confirmed',proof='name_and_fresh_paired_owned_scan')
        ledger.event('individual_learning_verified',skill=sid,name=name)
        return True
    def learn_rows(self):
        """Rows offering 배우기, at the top of the all-skills list."""
        self.open_skills();self.all_filter(False)
        for _ in range(3):self.drag((762,118),(762,424),skill_screen)
        self.context.wait(.8)
        return [r for r in self.rows((798,79,45,365),pair_minimum=.9) if r['score']>=.94 and clean(r['text'])==clean('배우기')]
    def title_is(self,sid,name):
        """Selected skill's big title. A split or weak reading also needs its own icon beside it."""
        rows=self.rows((46,70,155,25));text=clean(''.join(r['text'] for r in sorted(rows,key=lambda r:r['x'])))
        if text!=clean(name) or not rows:return False
        worst=min(r['score'] for r in rows)
        return worst>=.94 or (worst>=.85 and identify_icon(self.frame(),(8,66,46,46))==sid)
    def _learn_target(self,sid,name,ledger):
        """List names are too small to read reliably, so each 배우기 row is opened and named by its title."""
        intents=ledger.item.setdefault('learning_intents',{})
        pending=intents.get(str(sid),{}).get('status')=='intent'
        hit=None
        for row in self.learn_rows():
            self.click(754,row['y'],skill_screen);self.context.wait(.6)
            if self.title_is(sid,name):hit=row;break
        if hit is None:
            if pending:
                # The fragments are gone and nothing offers this skill, so the sent learn took effect.
                intents[str(sid)].update(status='confirmed',proof='no_learn_row_after_intent')
                ledger.event('individual_learning_reconciled',skill=sid);return True
            raise NoLearnRow(name)
        if pending:raise Pending('이전 도술 학습 결과 확인 필요: '+name)
        before=len(self.learn_rows())
        self.click(754,hit['y'],skill_screen);self.context.wait(.6)
        if not self.title_is(sid,name):raise Pending('선택 도술 이름 확인 필요: '+name)
        self.click_word('배우기',(798,hit['y']-15,35,30),skill_screen,minimum=.94)
        # Without a public image the selected title above is the proof, and the dialog only has to be this dialog.
        if str(sid) in self.public.get('skills',{}):confirm=lambda f:learn_confirm_for(f,sid)
        else:confirm=lambda f:match(f,'learn-confirm',(378,148,150,28),.96) is not None
        self.context.wait(.5);first=self.frame();self.context.wait(.12);second=self.frame()
        if not confirm(first) or not confirm(second):
            raise Pending('선택 도술과 개별 학습 확인창 불일치')
        intents[str(sid)]={'status':'intent','skill':name,'at':time.time()}
        ledger.event('individual_learning_intent',skill=sid,name=name)
        self.click_word('확인',(430,290,112,55),confirm,minimum=.94)
        self.context.wait(1.)
        # Only dismisses a screen that closes on any press; the learn is proved by the row going away.
        # Its effects keep moving, so two frames rarely agree here and one reading has to do.
        for attempt in range(8):
            if any(r['score']>=.80 and clean('새로운 도술') in clean(r['text']) for r in self.rows((280,70,340,240),pair=False)):
                self.click(448,190,lambda f:True);break
            if attempt==7:raise Pending('획득 도술 화면 확인 필요: '+name)
            self.context.wait(.4)
        self.wait(skill_screen,seconds=8);self.context.wait(.8)
        if len(self.learn_rows())>=before:raise Pending('개별 도술 학습 후 배우기 행 감소 확인 필요: '+name)
        intents[str(sid)].update(status='confirmed',proof='learn_dialog_icon_and_learn_row_gone')
        ledger.event('individual_learning_verified',skill=sid,name=name)
        LOG.info('도술 학습 확인 · %s',name)
        return True
    def enter_shop(self,style):
        if style not in ('파멸','저격','연타','강타'):raise Pending('엽전 상인 분류 확인 필요')
        self.close_known()
        if not self.normal():raise Pending('도술 상인 이동 전 일반 필드 확인 필요')
        self.adapter.run_town_return(self.context,self.inputs)
        from owner_town_return import town_pair
        if not self.normal() or not town_pair(self.adapter,self.context,self.inputs):raise Pending('도술 상인 이동 전 마을 복귀 확인 필요')
        self.click(51,51,lambda f:self.normal_frame(f))
        self.wait(map_screen);self.opened='map'
        self.click(22,49,map_screen)
        self.wait(lambda f:map_screen(f) and float((f[42:60,47:165].min(axis=2)>140).mean())>.7)
        self.click(90,50,map_screen);self.clear_text();self.text('도술');self.key(0x0d)
        self.click_word(style,(44,65,140,145),map_screen,minimum=.90)
        self.word(style+' 도술 상점',(737,31,150,33),minimum=.90)
        self.click_word('걸어가기',(720,420,110,50),map_screen,minimum=.90)
        self.opened=None
        end=time.monotonic()+45
        while time.monotonic()<end:
            self.context.checkpoint()
            try:
                self.word(style+' 도술 상점',(30,1,210,30),minimum=.90);self.opened='shop';return
            except Pending:pass
            # Interact only with a read, unique NPC label, not a fixed spot
            # after an unverified movement timeout.
            try:
                npc=self.word(style+' 도술',(250,30,360,240),minimum=.90)
                self.click(npc['x'],npc['y']+18,lambda f:self.normal_frame(f))
            except Pending:pass
            self.context.wait(.5)
        raise Pending(style+' 도술 상인 도착·상점 표시 미확인')
    def clear_text(self):
        self._check_identity()
        with self.inputs.transaction():
            ctrl=False;letter=False
            try:
                ctrl=True;self.inputs.down('key',0x11);self._check_identity();letter=True;self.inputs.down('key',0x41)
                self.context.wait(.05)
            finally:
                if letter:self.inputs.up('key',0x41)
                if ctrl:self.inputs.up('key',0x11)
        self.key(0x08)
    def normal_frame(self,frame):
        from owner_startup_stage import scene
        return scene(self.service.detector,frame)=='field'
    def shop_rows(self,style):
        rows=self.rows((44,61,153,350));known=self.public['all_skill_names'];out=[]
        for r in rows:
            name=item_name(r['text'],known)
            if name and r['score']>=.86 and known[name]['style']==style:out.append(dict(r,name=name,id=known[name]['id']))
        return out
    def buy_one(self,ledger,row,*,tutorial=False):
        # Availability and currency glyphs are copied from an actual 0/1,
        # 100-fragment coin item, separately checked against the quote dialog.
        frame=self.frame();y=row['y']
        availability=match(frame,'shop-available',(43,y+11,83,23),.96)
        coin=match(frame,'shop-coin',(43,y+2,30,20),.96)
        fragments=match(frame,'shop-fragments100',(22,y+11,25,24),.96)
        if not availability or not coin or not fragments:return False
        key=str(row['id']);old=ledger.item['purchases'].get(key,{})
        if old.get('status') in ('intent','confirmed'):return False
        self.click(110,y,lambda f:match(f,'shop-available',(43,y+11,83,23),.96) is not None)
        self.wait(lambda f:match(f,'shop-quantity',(408,150,84,28),.96) is not None)
        # The second independent read must identify the same item exactly.
        rows=self.rows((405,190,122,38));known=self.public['all_skill_names']
        names=[entry for entry in rows if entry.get('score',0)>=.88 and item_name(entry.get('text',''),known)==row['name']]
        if len(names)!=1:raise Pending('도술 구매 품목 이름 정확히 재확인 필요')
        import cv2,numpy as np
        l,t,r,b=names[0]['bounds'];source=self.last_text_frame[t:b,l:r].copy();tick=self.last_text_tick
        if not (0<=l<r<=897 and 0<=t<b<=479) or not source.size or float(source.std())<10:
            raise Pending('도술 구매 품목 표시 확인 필요')
        def quote_current(frame):
            patch=frame[t:b,l:r];age=time.monotonic()-tick
            if not 0<=age<=3 or patch.shape!=source.shape:return False
            value=float(cv2.matchTemplate(patch,source,cv2.TM_CCOEFF_NORMED)[0,0])
            return (np.isfinite(value) and value>=.97
                    and match(frame,'shop-quantity',(408,150,84,28),.96) is not None
                    and match(frame,'quote-10000',(461,198,51,24),.97) is not None
                    and match(frame,'quote-one',(432,239,21,20),.97) is not None)
        if not quote_current(self.frame()):raise Pending('도술 품목·가격·수량 재확인 필요')
        quote={'currency':'엽전','price':10000,'bundles':1,'fragments':100,'item':row['name']}
        # Save before the first purchase-committing action. An interrupted
        # intent never blindly retries; next launch requires quota/ownership.
        if not ledger.begin_purchase(key,quote,tutorial=tutorial):return False
        self.click(490,302,quote_current)
        total=self.word('10,000',(439,380,70,35),minimum=.96,exact=True)
        l,t,r,b=total['bounds'];total_source=self.last_text_frame[t:b,l:r].copy();total_tick=self.last_text_tick
        if not (0<=l<r<=897 and 0<=t<b<=479) or not total_source.size or float(total_source.std())<10:
            raise Pending('도술 구매 합계 표시 확인 필요')
        def cart_current(frame):
            patch=frame[t:b,l:r];age=time.monotonic()-total_tick
            if not 0<=age<=3 or patch.shape!=total_source.shape:return False
            score=float(cv2.matchTemplate(patch,total_source,cv2.TM_CCOEFF_NORMED)[0,0])
            return (np.isfinite(score) and score>=.97
                    and match(frame,'shop-title',(30,1,210,30),.96) is not None
                    and match(frame,'shop-quantity',(408,150,84,28),.96) is None)
        self.click_word('구매',(730,430,65,40),cart_current,minimum=.92)
        self.word('아이템 구매를 완료',(230,80,440,250),minimum=.92)
        ledger.purchase_receipt(key,{'item':row['name'],'verified':True,'source':'fresh_exact_purchase_complete_toast'})
        return True
    def purchase_and_learn(self,ledger):
        return self.purchase_required_and_learn(ledger)
    def purchase_required_and_learn(self,ledger):
        """Story 5 only; process verified coin-shop skills in approved styles.

        강인 merchant traversal and full shop coverage are deliberately held
        until actual screen/path evidence exists. Never buy unrelated
        저격/연타 items or consume selection boxes here.
        """
        if ledger.item.get('story_step')!=5:
            raise Pending('최종 도술 서사 완료 확인 전')
        from owner_aoe_preset_candidate import SLOTS
        # 궁극기는 슬롯 배치에 따라 활성화되며 순서 설정에서 검증한다.
        required=set(SLOTS)
        if any(str(sid) not in self.public.get('skills',{}) for sid in required):
            raise Pending('요청 도술 목록 확인 필요')
        expected={68:'강인',84:'헌신',59:'파멸',55:'파멸',63:'파멸',89:'기만',25:'강타',64:'파멸',65:'파멸'}
        if any(self.public['skills'][str(sid)].get('style')!=style for sid,style in expected.items()):
            raise Pending('요청 도술·계열 확인 필요')
        owned=self.scan_owned()
        if not isinstance(owned,set):raise Pending('현재 보유 도술 확인 필요')
        from owner_learned_skills_candidate import remember_verified_owned
        try:remember_verified_owned(ledger,owned)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            raise Pending('선택상자 도술 학습 기록 저장 보류') from exc
        self.close_known();spent=0;seen=set();purchased=set();pending_learning=set()
        for style in ('파멸','강타'):
            self.enter_shop(style);previous=None
            for _ in range(12):
                self.context.checkpoint()
                page=self.shop_rows(style)
                if not page:raise Pending(style+' 상점 품목 판독 필요')
                signature=tuple((r['id'],r['y']) for r in page)
                if previous==signature:break
                previous=signature
                for shoprow in page:
                    sid=shoprow['id']
                    if sid in seen or sid in owned:continue
                    seen.add(sid)
                    previous_purchase=ledger.item.get('purchases',{}).get(str(sid),{})
                    if previous_purchase.get('status')=='intent':
                        raise Pending('이전 도술 구매 결과 확인 필요: '+shoprow['name'])
                    if previous_purchase.get('status')=='confirmed':
                        pending_learning.add(sid);continue
                    if spent>=1000000:raise Pending('도술 1회 엽전 지출 한도 100만 도달')
                    if self.buy_one(ledger,shoprow):
                        spent+=10000;purchased.add(sid)
                    else:raise Pending(style+' 상점 품목 구매 가능 여부·기존 구매 기록 확인 필요: '+shoprow['name'])
                self.drag((117,382),(117,87),lambda f:not skill_screen(f) and not quest_screen(f))
            else:raise Pending(style+' 상점 목록 끝 확인 필요')
            self.close_known()
        unavailable=[]
        for sid in sorted((purchased|pending_learning)-owned):
            self.context.checkpoint()
            if str(sid) not in self.public['skills']:
                unavailable.append(sid);continue
            self.learn_one(sid,ledger)
        after=self.scan_owned()
        if not isinstance(after,set):raise Pending('도술 학습 후 목록 확인 필요')
        try:remember_verified_owned(ledger,after)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            raise Pending('선택상자 도술 학습 기록 저장 보류') from exc
        missing=required-after
        ledger.item['owned_skills']=sorted(after)
        ledger.event('learning_verified',owned=len(after),missing=sorted(missing))
        unresolved=[]
        if (purchased|pending_learning)-after or unavailable:unresolved.append('파멸·강타 개별 도술 학습 화면 확인 필요')
        if missing:unresolved.append('요청 광역 도술 학습 미완료: '+', '.join(self.public['skills'][str(i)]['name'] for i in sorted(missing)))
        # A repeated page signature is not proof that OCR covered every shop
        # item, and the third shop is not verified. Do not mark the whole user
        # request complete merely because the nine preset skills are learned.
        unresolved.append('파멸·강타 전체 판매 목록 확인 필요')
        result={'status':'partial','owned_skills':sorted(after),
                'aoe_ready':not missing,'unresolved':unresolved}
        ledger.item['requested_learning']=result
        ledger.event('requested_learning_partial',**result)
        return result
    def select_preset(self,number):
        if number not in (1,2):raise Pending('프리셋 번호 확인 필요')
        # The patch made this menu five rows, the last one locked: its lock marks the open menu.
        menu=lambda f:match(f,'preset-open',(630,338,40,30),.96) is not None
        self.open_skills()
        if not menu(self.frame()):self.click(579,459,skill_screen)
        self.wait(menu)
        self.click(590,436 if number==1 else 416,menu)
        # First use of an empty preset copies the old deck once. It is an
        # informational game dialog, not purchase/unlock confirmation.
        if match(self.frame(),'preset-copy-notice',(365,228,170,33),.96):
            self.click(450,282,lambda f:match(f,'preset-copy-notice',(365,228,170,33),.96) is not None)
        self.wait(skill_screen)
        # The bar is still sliding after a switch, and two early frames disagree. Nothing is pressed here.
        for attempt in range(4):
            self.context.wait(.4)
            # OCR cannot read the bar's lone digit since the patch. The name beside it reads
            # .94: the user's own name, or the game's default on a new character.
            try:rows=self.rows((560,450,60,18))
            except Pending:
                if attempt==3:raise
                continue
            names={1:('광역','프리셋1'),2:('단일','프리셋2')}[number]
            if any(clean(r['text']) in names for r in rows if r['score']>=.80):return
        raise Pending('현재 프리셋 이름 대조 실패')
    def unlocked(self):
        import cv2,numpy as np
        frame=self.frame();unlocked=set(range(5))
        for i in (5,6,7):
            x,y=SLOTS[i]
            if match(frame,'slot-lock',(x-9,y-10,20,21),.96):continue
            # Existing colored skill icon establishes an open slot. Empty or
            # otherwise unknown extra slots remain held, never purchased.
            hsv=cv2.cvtColor(frame[y-15:y+16,x-15:x+16],cv2.COLOR_RGB2HSV)
            if int(((hsv[:,:,1]>65)&(hsv[:,:,2]>80)).sum())>=160:unlocked.add(i)
        return unlocked
    def current_slots(self,unlocked):
        frame=self.frame();result=[None]*8
        for i in unlocked:
            x,y=SLOTS[i];result[i]=identify_icon(frame,(x-19,y-19,38,38))
            # Circular game hotbar icons crop/zoom the art differently from
            # the public square icon. Never relax that classifier's threshold:
            # select the exact slot and read the larger left-hand skill title.
            if result[i] is None:
                self.click(x,y,skill_screen)
                rows=self.rows((46,70,155,25))
                names={n['id'] for name,n in self.public['all_skill_names'].items() for r in rows if r['score']>=.94 and clean(r['text'])==clean(name)}
                if len(names)==1:result[i]=next(iter(names))
        return result
    def equip(self,sid,index):
        x,y=SLOTS[index]
        if self.current_slots({index})[index]==sid:return
        row=self.find_skill(sid);row_box=(798,row['y']-15,35,30)
        row_proof=lambda f:skill_screen(f) and identify_icon(f,(695,row['y']-20,40,40))==sid
        actions=[clean(r['text']) for r in self.rows(row_box) if r.get('score',0)>=.94 and clean(r.get('text','')) in ('해제','장착')]
        if len(actions)!=1:raise Pending('선택한 도술의 장착 상태 확인 필요')
        if actions[0]=='해제':self.click_word('해제',row_box,row_proof,minimum=.94)
        self.click(x,y,skill_screen);row=self.find_skill(sid)
        self.click_word('장착',(798,row['y']-15,35,30),
                        lambda f:skill_screen(f) and identify_icon(f,(695,row['y']-20,40,40))==sid,minimum=.94)
        self.wait(skill_screen)
        self.context.wait(.12)
        if self.current_slots({index})[index]!=sid:raise Pending('장착 도술 사후 확인 실패')
    def order_row(self):
        frame=self.frame();items=[]
        # Header icons are fixed 50px apart; 5~8 skills plus ultimate.
        for i in range(9):
            x=252+i*50
            if x>665:break
            sid=identify_icon(frame,(x-19,82,38,41))
            if sid is not None:items.append(sid)
        return items
    def set_order(self,desired):
        self.click(176,459,skill_screen)
        self.word('사용 순서 설정',(360,39,180,25),minimum=.94)
        proof=lambda f:match(f,'order-title',(410,40,80,27),.96) is not None
        current=self.order_row()
        if set(current)!=set(desired):raise Pending('시전 순서 도술 목록 불일치')
        for i,sid in enumerate(desired):
            current=self.order_row()
            if current[i]==sid:continue
            j=current.index(sid)
            self.drag((252+j*50,103),(252+i*50,103),proof)
            if self.order_row()[:i+1]!=desired[:i+1]:raise Pending('도술 시전 순서 이동 확인 실패')
        self.click(509,441,proof);self.wait(skill_screen)
        # Reopen and verify saved order, rather than trusting the save click.
        self.click(176,459,skill_screen)
        self.word('사용 순서 설정',(360,39,180,25),minimum=.94)
        if self.order_row()!=desired:raise Pending('저장된 시전 순서 재확인 실패')
        self.click(425,441,proof);self.wait(skill_screen)
    def configure_both(self,ledger):
        raise Pending('이전 광역·단일 동시 설정은 사용하지 않습니다 · 광역 1번 경로 필요')
