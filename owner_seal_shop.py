"""단 봉인해제 and its 단각 교환 shop at 1366x768, by the screen's own words (user 11-06).

Once a game day, an hour before the 05:00 reset: every 단 is unsealed (each pass at most 100, 연출 건너뛰기 ticked
first), then the checked 단각 교환 rows are bought in their order, each up to its target for the period its row
shows (도사 일일/주간 한정). Seen on pc1 11-06 18:59: 6 영기단 gave 24 단각 with five items; the shop list holds 26
rows and its quantity window has a ▶| button for the most the limit and the 단각 allow.

The native seal_release pass was built on 897 pictures; it is replaced here, and outside this job it only waits.
"""
import copy,hashlib,json,logging,os,re,tempfile,time
from pathlib import Path

LOG=logging.getLogger('project_gui.DKB')
KEY='auto_rewards.seal_release.enabled'
JOB_TIME='04:00'

# name, 단각 price, period, limit — pc1 11-06 18:59 screen, in the screen's order.
CATALOG=(('요혼석',10,'일일',100),('신기 가루',10,'일일',100),('엽전',10,'일일',100),
 ('생명의 정수',10,'주간',10),('여명의 정수',10,'주간',10),('몽환의 정수',10,'주간',10),('홍염의 정수',10,'주간',10),
 ('희귀 장비 강화 비법서',10,'일일',50),('영웅 장비 강화 비법서',20,'일일',20),('전설 장비 강화 비법서',100,'일일',10),
 ('희귀 가호의 정수',10,'일일',50),('영웅 가호의 정수',20,'일일',20),('전설 가호의 정수',100,'일일',10),
 *[(name+' 도술 강화 요령서',100,'일일',10) for name in ('절명','연타','강타','척살','저격','주술','파멸','강인','기동','기만','헌신','제압')],
 ('가호 주머니',50,'주간',10))
DANS=('정기단','영기단','천지단','조화단','태초단')

# Real 1366 places.
MENU=(1330,32);MENU_SEAL=(1258,150);EXIT=(1330,32)
TITLE=(85,12,160,38)
TAB_UNSEAL=(20,68,145,34);TAB_SHOP=(162,68,145,34)
SKIP_BOX=(24,723,22,22);SKIP_WORD=(48,720,100,28)
ORB_ROW=(300,598,770,44);ORB_Y=548
AMOUNT=(610,646,150,28);BUTTON_COUNT=(570,689,90,28);UNSEAL_BUTTON=(640,688,140,32);RESULT=(590,700,190,46)
BALANCE=(595,14,60,30)
LIST=(15,112,290,636);LIST_X=160;LIST_DRAG=(660,180)
POPUP_TITLE=(590,255,190,32);POPUP_COUNT=(630,384,80,28);POPUP_MAX=(777,397);POPUP_PLUS=(747,397)
POPUP_OK=(690,466,120,34);POPUP_CANCEL=(570,466,120,34)
MAX_PASSES=12;LIST_PAGES=5


def compact(text):return ''.join(str(text).split())


# ---------- settings ----------

def initial_rows():
    return [{'name':name,'enabled':False,'mode':'max','quantity':1} for name,*_ in CATALOG]


def validate(rows):
    if not isinstance(rows,list) or len(rows)>100:raise ValueError('단각 교환 목록이 올바르지 않습니다.')
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('name'),str) or not row['name'].strip():raise ValueError('품목 이름을 확인해 주세요.')
        key=compact(row['name']).casefold()
        if key in seen:raise ValueError('이름이 중복된 품목이 있습니다.')
        seen.add(key)
        if type(row.get('enabled')) is not bool or row.get('mode') not in ('quantity','max'):raise ValueError('교환 설정을 확인해 주세요.')
        if type(row.get('quantity')) is not int or not 1<=row['quantity']<=999:raise ValueError('수량은 1~999 사이 정수여야 합니다.')
    return rows


class SealShopStore:
    """One file per character, the same way the 잡화상점 rows are kept."""
    def __init__(self,root,character):
        if not isinstance(character,str) or not character.strip():raise ValueError('캐릭터가 확인된 후 설정할 수 있습니다.')
        ident=hashlib.sha256(character.strip().encode('utf-8')).hexdigest()[:24]
        self.path=Path(root)/'settings'/('owner-seal-shop-'+ident+'.json')

    def snapshot(self):
        if not self.path.exists():return {'version':1,'enabled':True,'items':initial_rows()},'missing'
        raw=self.path.read_bytes();obj=json.loads(raw.decode('utf-8-sig'))
        if not isinstance(obj,dict) or obj.get('version')!=1:raise ValueError('알 수 없는 단각 교환 설정 형식입니다.')
        validate(obj.get('items'))
        if type(obj.get('enabled',True)) is not bool:raise ValueError('단각 교환 사용 설정 확인 필요')
        names={compact(r['name']) for r in obj['items']}
        # A row the catalogue gained later shows unchecked at the end.
        obj['items']+=[row for row in initial_rows() if compact(row['name']) not in names]
        return obj,hashlib.sha256(raw).hexdigest()

    def read_document(self):return self.snapshot()[0]

    def revision(self):
        try:return hashlib.sha256(self.path.read_bytes()).hexdigest()
        except FileNotFoundError:return 'missing'

    def write(self,rows,coin_reserve=None,*,expected_revision=None,enabled=None):
        validate(rows)
        document,revision=self.snapshot()
        if expected_revision is not None and revision!=expected_revision:raise ValueError('다른 창에서 변경된 설정입니다. 다시 열어 확인해 주세요.')
        document.update(version=1,items=[{k:row[k] for k in ('name','enabled','mode','quantity')} for row in rows])
        if enabled is not None:document['enabled']=bool(enabled)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.owner-seal-',suffix='.tmp',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as stream:
                json.dump(document,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)


def open_settings(parent,root,character,*,embedded=False):
    from owner_shop_settings_candidate import ShopSettings
    class SealShopSettings(ShopSettings):
        SWITCH='단각 교환 사용'
        def make_store(self,root,character):return SealShopStore(root,character)
        def rows_of(self,document):return [dict(row) for row in document['items']]
        def saved_rows(self,rows):return rows
        def check(self,rows):return validate(rows)
        def new_row(self):return dict(name='',enabled=False,mode='max',quantity=1)
    return SealShopSettings(parent,root,character,embedded=embedded)


def configured(root):
    from owner_hunt_rules_candidate import configured_identity
    document=SealShopStore(root,configured_identity(root)).read_document()
    return document.get('enabled',True),[row for row in document['items'] if row['enabled']]


# ---------- screen reading ----------

def words(frame,box,minimum=.55):
    import owner_text as text
    return [dict(row,word=text.clean(row['text'])) for row in text.read(None,frame,box,scale=2,minimum=minimum)]


def on_screen(frame):
    return getattr(frame,'hi',None) is not None and any('봉인해제' in r['word'] for r in words(frame,TITLE))


def number(word):
    digits=re.sub(r'[^\d]','',word.replace('O','0').replace('o','0'))
    return int(digits) if digits else None


def dan_counts(frame):
    """{name: count} under the five orbs; a count is the number row right below its name."""
    rows=words(frame,ORB_ROW,.5);found={}
    for name in DANS:
        heads=[r for r in rows if name in r['word']]
        if len(heads)!=1:continue
        head=heads[0]
        below=[r for r in rows if r is not head and 8<r['ry']-head['ry']<34 and abs(r['rx']-head['rx'])<45 and number(r['word']) is not None]
        if len(below)==1:found[name]=(number(below[0]['word']),round(head['rx']))
    return found


def balance(frame):
    rows=sorted([r for r in words(frame,BALANCE,.5) if re.fullmatch(r'[\d,]+',r['word'])],key=lambda r:r['rx'])
    return number(rows[0]['word']) if rows else None


LIMIT=re.compile(r'(일일|주간)한정:?\(?(\d+)/(\d+)\)?')


def shop_rows(frame):
    """Visible list rows: {compact name: dict(ry, price, used, limit, period)} with every part read."""
    rows=words(frame,LIST,.5);known={compact(name):name for name,*_ in CATALOG};found={}
    for head in rows:
        name=compact(head['word'])
        if name not in known:continue
        price=[r for r in rows if 8<r['ry']-head['ry']<34 and re.fullmatch(r'\d{1,4}',r['word'])]
        limit=[m for r in rows if 26<r['ry']-head['ry']<56 for m in [LIMIT.search(r['word'])] if m]
        if len(price)==1 and len(limit)==1:
            m=limit[0]
            found[name]=dict(ry=round(head['ry']),price=int(price[0]['word']),period=m.group(1),used=int(m.group(2)),limit=int(m.group(3)))
    return found


def skip_ticked(frame):
    """The tick inside the 연출 건너뛰기 box is light grey (56 of 144 inner pixels above 150, pc1 18:59); an empty
    box is dark inside (none above 120, 19:14)."""
    import numpy as np
    x,y,w,h=SKIP_BOX;patch=np.asarray(frame.hi)[y+5:y+h-5,x+5:x+w-5].astype(int)
    return int(((patch.min(axis=2)>150)).sum())>=20


def wanted(row,seen,coins):
    """How many to buy now: the target less what the period's count shows, within the limit and the coins."""
    room=seen['limit']-seen['used']
    if row['mode']=='quantity':room=min(room,row['quantity']-seen['used'])
    return max(0,min(room,coins//seen['price'] if seen['price'] else 0))


# ---------- the run ----------

class Run:
    def __init__(self,adapter,context,inputs):
        from owner_mission_ui import MissionUI
        import owner_hd as hd
        self.hd=hd;self.ui=MissionUI(adapter,context,inputs);self.context=context;self.adapter=adapter

    def frame(self):return self.ui.frame()

    def tap(self,x,y,wait=1.):
        self.context.checkpoint();self.ui.service.click_hit(self.hd.real_hit(x,y));self.context.wait(wait)

    def until(self,test,seconds=8.):
        end=time.monotonic()+seconds
        while True:
            frame=self.frame()
            if test(frame):return frame
            if time.monotonic()>=end:return None
            self.context.wait(.4)

    def word_at(self,frame,box,want):
        rows=[r for r in words(frame,box) if want in r['word']]
        return rows[0] if len(rows)==1 else None

    def open(self):
        if on_screen(self.frame()):return True
        from owner_worn_stats import skip_scene,close_bag
        skip_scene(self.ui.service,self.context);close_bag(self.ui.service,self.context)
        self.tap(*MENU,1.5);self.tap(*MENU_SEAL,1.)
        return self.until(on_screen,10) is not None

    def leave(self):
        for _ in range(3):
            frame=self.frame()
            if not on_screen(frame):return True
            for box in (RESULT,POPUP_CANCEL):
                row=self.word_at(frame,box,'나가기' if box is RESULT else '취소')
                if row:self.tap(round(row['rx']),round(row['ry']),1.);break
            else:self.tap(*EXIT,1.5)
        return not on_screen(self.frame())

    def tab(self,box,word):
        frame=self.frame();row=self.word_at(frame,box,word)
        if row is None:raise RuntimeError(word+' 탭 미확인')
        self.tap(round(row['rx']),round(row['ry']),1.2)

    def tick_skip(self):
        frame=self.frame()
        if not any('연출' in r['word'] for r in words(frame,SKIP_WORD)):raise RuntimeError('연출 건너뛰기 미확인')
        if skip_ticked(frame):return True
        x,y,w,h=SKIP_BOX;self.tap(x+w//2,y+h//2,.6)
        if skip_ticked(self.frame()):LOG.info('단 봉인해제 · 연출 건너뛰기 체크');return True
        raise RuntimeError('연출 건너뛰기 체크 확인 실패')

    def unseal(self):
        """Every 단 down to 0. Returns {name: number unsealed}."""
        self.tab(TAB_UNSEAL,'봉인해제');self.tick_skip()
        done={}
        for name in DANS:
            for _ in range(MAX_PASSES):
                counts=self.counts(name)
                if name not in counts:
                    # A lone red 0 is the read OCR misses most (19:20); not unsealing is the safe side.
                    LOG.info('단 봉인해제 · %s 수량 판독 안 됨 · 건너뜀',name);break
                count,x=counts[name]
                if count<=0:break
                self.tap(x,ORB_Y,1.)
                # The game fills the amount itself (all held, at most 100); that figure is the pass, since an 8
                # under the orb read as 7 here (19:27) and all of it goes anyway.
                # A lone digit can go unread in one place (영기단 5, 19:43): the button repeats the amount, and the
                # count under the orb is the last word.
                frame=self.frame();amount=None
                for box in (AMOUNT,BUTTON_COUNT):
                    read=[number(r['word']) for r in words(frame,box,.4) if number(r['word'])]
                    if len(read)==1 and 1<=read[0]<=100:amount=read[0];break
                if amount is None and count<100:amount=count
                if amount is None:raise RuntimeError('%s 수량 판독 실패'%name)
                count=amount
                button=self.word_at(frame,UNSEAL_BUTTON,'봉인해제')
                if button is None:raise RuntimeError('봉인 해제 버튼 미확인')
                self.tap(round(button['rx']),round(button['ry']),1.5)
                for word in ('즉시확인','나가기'):
                    frame=self.until(lambda f:self.word_at(f,RESULT,word) is not None,10)
                    if frame is None:raise RuntimeError('봉인 해제 결과 '+word+' 미확인')
                    row=self.word_at(frame,RESULT,word);self.tap(round(row['rx']),round(row['ry']),1.5)
                if self.until(lambda f:self.word_at(f,UNSEAL_BUTTON,'봉인해제') is not None,8) is None:raise RuntimeError('봉인 해제 화면 복귀 미확인')
                done[name]=done.get(name,0)+count
                LOG.info('단 봉인해제 · %s %d개',name,count)
                if count<100:break  # the pass took all there was
            else:raise RuntimeError(name+' 봉인 해제 반복 한도')
        return done

    def counts(self,name,tries=3):
        for _ in range(tries):
            found=dan_counts(self.frame())
            if name in found:return found
            self.context.wait(.4)
        return found

    def drag_list(self,up):
        top,bottom=LIST_DRAG;a,b=(bottom,top) if up else (top,bottom)
        start=self.hd.logical_of(LIST_X,a);end=self.hd.logical_of(LIST_X,b)
        self.ui.drag((round(start[0]),round(start[1])),(round(end[0]),round(end[1])),on_screen);self.context.wait(.8)

    def find(self,name):
        """The row of name, scrolling down from the top of the list."""
        for _ in range(2):self.drag_list(False)
        for _ in range(LIST_PAGES):
            seen=shop_rows(self.frame())
            if compact(name) in seen:return seen[compact(name)]
            self.drag_list(True)
        return None

    def buy(self,row,seen,coins):
        want=wanted(row,seen,coins)
        if want<=0:return 0
        self.tap(LIST_X,seen['ry'],1.)
        frame=self.until(lambda f:any('수량입력' in r['word'] for r in words(f,POPUP_TITLE)),5)
        if frame is None:raise RuntimeError(row['name']+' 수량 입력창 미확인')
        most=min(seen['limit']-seen['used'],coins//seen['price'])
        if want==most:self.tap(*POPUP_MAX,.6)
        else:
            for _ in range(want-1):self.tap(*POPUP_PLUS,.25)
        shown=[number(r['word']) for r in words(self.frame(),POPUP_COUNT) if number(r['word'])]
        if shown!=[want]:
            self.tap(*self.centre(POPUP_CANCEL),.8);raise RuntimeError('%s 수량 %s · 기대 %d'%(row['name'],shown,want))
        ok=self.word_at(self.frame(),POPUP_OK,'확인')
        if ok is None:raise RuntimeError('수량 입력 확인 버튼 미확인')
        self.tap(round(ok['rx']),round(ok['ry']),1.5)
        return want

    @staticmethod
    def centre(box):x,y,w,h=box;return (x+w//2,y+h//2)

    def exchange(self,rows):
        """Buys rows in order; returns a list of (name, count)."""
        self.tab(TAB_SHOP,'단각교환');self.context.wait(.6)
        bought=[]
        for row in rows:
            coins=balance(self.frame())
            if coins is None:raise RuntimeError('단각 판독 실패')
            seen=self.find(row['name'])
            if seen is None:LOG.info('단각 교환 · %s 목록에서 못 찾음',row['name']);continue
            count=self.buy(row,seen,coins)
            if not count:continue
            after=self.find(row['name'])
            if after is None or after['used']!=seen['used']+count:raise RuntimeError('%s 구매 수량 확인 실패'%row['name'])
            LOG.info('단각 교환 · %s %d개 · %s %d/%d',row['name'],count,after['period'],after['used'],after['limit'])
            bought.append((row['name'],count))
        return bought


def run(adapter,context,inputs):
    """The whole pass. Returns a short result text; anything unproven raises and leaves the screen."""
    root=adapter.project.root
    shop_on,rows=configured(root)
    work=Run(adapter,context,inputs)
    adapter.exit_sleep_mode(context,inputs)
    if not work.open():raise RuntimeError('단 봉인해제 화면 미확인')
    try:
        done=work.unseal()
        bought=work.exchange(rows) if shop_on and rows else []
    finally:work.leave()
    text='봉인 해제 '+(', '.join('%s %d'%item for item in done.items()) or '없음')
    text+=' · 교환 '+(', '.join('%s %d'%item for item in bought) or '없음')
    LOG.info('단 봉인해제 완료 · %s',text)
    return text


def install(gui=None):
    """The native 897 pass is not used: outside the 04:00 job it only notes the wait."""
    import sys
    try:import project_adapter.seal_release as native
    except ImportError:return
    original=native.run_seal_release
    if getattr(original,'_owner_seal',False):return
    def waiting(*args,**kwargs):
        LOG.info('단 봉인해제 · %s 일정에서 실행',JOB_TIME);return True
    waiting._owner_seal=True
    for name,module in tuple(sys.modules.items()):
        if module is None or not name.startswith(('project_adapter','owner_')):continue
        for key,value in tuple(vars(module).items()):
            if value is original:setattr(module,key,waiting)
    from project_adapter._entry import Adapter
    if callable(getattr(Adapter,'run_seal_release',None)):
        Adapter.run_seal_release=lambda adapter,*a,**k:waiting()
