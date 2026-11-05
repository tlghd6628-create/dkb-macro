"""The game's own settings the macro relies on, read by their words and set when they differ.

Camera shake and effects cover what the program has to see, and both PCs must draw the same screen. Each row is found
by its label and each option by its word, so a patch that moves or adds rows changes nothing here. Asked once per
program start, on the field. A failure is logged and never stops the work.
"""
import json,logging,re,time
from difflib import SequenceMatcher
from pathlib import Path
import numpy as np
import owner_text as text

LOG=logging.getLogger('project_gui.DKB')
RESOLUTION='1366x768'
# Only the environment tab's graphics page: what changes how the screen is drawn.
WANTED={
    ('환경','그래픽'):(
        ('UI 크기 설정','보통'),('화면 모드','창 모드'),('카메라 흔들림','사용 안 함'),('최대 프레임 설정','60fps'),
        ('이펙트 표시','끄기'),('구름 효과','끄기'),('도술 이펙트 제한','높음'),('저사양 모드','사용 안 함'),
        ('그림자 표시','켜기'),('물 반사 효과','켜기'),('3D 객체 아웃라인 효과','켜기'),('렌더 스케일','높음'),
        ('후처리 효과','사용'),('SSAO','사용'),('DOF','사용'),
    ),
    # The game asleep hides everything the program reads, so it never goes there by itself.
    ('기능','편의'):(('절전모드 진입','사용 안 함'),),
}
RESOLUTION_WORD=re.compile(r'\d{3,4}\s*[xX×]\s*\d{3,4}')
LABEL_END=580   # real x: labels are left of this, options right of it
ROW_SLACK=14
PANEL=(180,100,1140,668);TABS=(0,62,1366,38);SIDE=(20,110,140,110);MENU_BOTTOM=(930,640,436,128)
WHEEL_AT=(484,281);WHEEL_STEP=8;MOST_PAGES=8


def _has_word(value):
    """At least two letters: leaves out the icons beside labels (88, ※, ?) and slider numbers (100%, +)."""
    return len(re.findall(r'[가-힣A-Za-z]',value))>=2


MINUTES=re.compile(r'\d+\s*분')

def _is_option(value):
    """A word, a resolution, or a time such as 5분, which is one letter and still a choice."""
    return _has_word(value) or bool(RESOLUTION_WORD.search(value)) or bool(MINUTES.fullmatch(text.clean(value)))


def similarity(a,b):
    a,b=text.clean(a),text.clean(b)
    return 1. if a==b else SequenceMatcher(None,a,b).ratio()


def panel_rows(rows):
    """Rows of the settings panel: label, its height and its option words. A label and its options share a height."""
    labels=[r for r in rows if r['rx']<LABEL_END and r['bounds'][0]>=190 and _has_word(r['text'])]
    options=[r for r in rows if r['bounds'][0]>=LABEL_END and _is_option(r['text'])]
    out=[]
    for label in labels:
        here=[o for o in options if abs(o['ry']-label['ry'])<=ROW_SLACK]
        if here:out.append(dict(label=label['text'],y=label['ry'],row=label,options=sorted(here,key=lambda o:o['rx'])))
    return out


def _pill_brightness(real,word):
    """How light the background beside this word is: the chosen option sits on a lighter pill."""
    x0,y0,x1,y1=word['bounds'];middle=(y0+y1)//2
    top,bottom=max(0,middle-6),min(real.shape[0],middle+7)
    parts=[p.reshape(-1,3) for p in (real[top:bottom,max(0,x0-18):max(0,x0-5)],real[top:bottom,x1+5:x1+18]) if p.size]
    return float(np.median(np.concatenate(parts),axis=0).mean()) if parts else 0.0


def chosen(real,row):
    """The option word that is on, or None when the difference between them is not clear."""
    words=[o for o in row['options'] if _has_word(o['text']) or MINUTES.fullmatch(text.clean(o['text']))]
    if len(words)<2:return None
    row=dict(row,options=words)
    values=sorted(((_pill_brightness(real,o),i) for i,o in enumerate(row['options'])),reverse=True)
    return row['options'][values[0][1]] if values[0][0]-values[1][0]>=12 else None


def _digits(value):
    """The number in a word, with the letter o the reader takes for a zero (6ofps) put right."""
    return re.sub(r'\D','',re.sub(r'(?<=\d)[oO]|[oO](?=\d)','0',str(value)))


def option_for(row,word):
    """The option meaning this word, or None when it cannot be told. A wrong press is worse than none: 좌측 and 우측
    differ by one letter, so a close spelling is only trusted when no other option is about as close."""
    wanted=text.clean(word);options=row['options']
    exact=[o for o in options if text.clean(o['text'])==wanted]
    if len(exact)==1:return exact[0]
    if _digits(word):
        same=[o for o in options if _digits(o['text'])==_digits(word)]
        return same[0] if len(same)==1 else None
    holding=[o for o in options if wanted in text.clean(o['text'])]
    if wanted!='사용' and len(holding)==1:return holding[0]
    scored=sorted(((similarity(o['text'],word),i) for i,o in enumerate(options)),reverse=True)
    if not scored or scored[0][0]<.7 or (len(scored)>1 and scored[0][0]-scored[1][0]<.05):return None
    return options[scored[0][1]]


def row_for(rows,label):
    best=max(rows,key=lambda r:similarity(r['label'],label),default=None)
    return best if best is not None and similarity(best['label'],label)>=.72 else None


def read_panel(root,frame):
    return panel_rows(text.read(root,frame,PANEL,bright=True))


def compare(rows,real,wanted):
    """Of these wanted (label, option): which are right, which to press, which rows are not on screen or not clear."""
    right=[];press=[];unclear=[];absent=[]
    for label,word in wanted:
        row=row_for(rows,label)
        if row is None:absent.append((label,word));continue
        on=chosen(real,row);target=option_for(row,word)
        if target is None or on is None:unclear.append((label,word));continue
        if on is target:right.append(label)
        else:press.append((label,word,target))
    return right,press,unclear,absent


def _first(rows,words):
    found=text.find(rows,words)
    return found[0] if found else None


class _Session:
    def __init__(self,adapter,context,inputs):
        from owner_mission_ui import MissionUI
        self.ui=MissionUI(adapter,context,inputs);self.root=adapter.project.root;self.context=context;self.changed=[];self.failed=[]
    def frame(self):
        frame=self.ui.frame()
        if getattr(frame,'hi',None) is None:raise RuntimeError('실제 화면 없음')
        return frame
    def press(self,row):
        self.ui.click(row['x'],row['y'],lambda f:True);self.context.wait(.7)
    def tab_on(self,frame):
        return bool(text.find(text.read(self.root,frame,TABS,bright=True),'환경'))
    def open(self):
        self.ui.click(875,20,lambda f:True);self.context.wait(1.2)
        word=_first(text.read(self.root,self.frame(),MENU_BOTTOM),'설정')
        if word is None:raise RuntimeError('전체 메뉴의 설정 미확인')
        self.press(word);self.context.wait(1.2)
        if not self.tab_on(self.frame()):raise RuntimeError('설정 창 미확인')
    def close(self):
        self.ui.click(22,19,lambda f:True);self.context.wait(1.5)
        if self.tab_on(self.frame()):
            self.ui.click(22,19,lambda f:True);self.context.wait(1.5)
    def go(self,tab,side):
        word=_first(text.read(self.root,self.frame(),TABS,bright=True),tab)
        if word is None:raise RuntimeError('설정 탭 미확인 · '+tab)
        self.press(word)
        if side:
            word=_first(text.read(self.root,self.frame(),SIDE,bright=True),side)
            if word is None:raise RuntimeError('설정 왼쪽 탭 미확인 · '+side)
            self.press(word)
        self.ui.wheel(1,WHEEL_STEP*4,at=WHEEL_AT,scene=lambda f:True,verify_cursor=True);self.context.wait(.9)
    def resolution(self):
        frame=self.frame();rows=read_panel(self.root,frame);row=row_for(rows,'해상도')
        if row is None or not row['options']:
            self.failed.append('해상도');return
        if _digits(row['options'][0]['text'])==_digits(RESOLUTION):return
        self.press(row['options'][0])
        for word in text.read(self.root,self.frame(),PANEL,bright=True):
            if _digits(word['text'])==_digits(RESOLUTION):
                self.press(word);self.context.wait(2);self.changed.append('해상도');return
        self.failed.append('해상도')
    def apply_page(self,wanted):
        """Set this page's rows and read it again. Returns the rows not on this page."""
        for _ in range(3):
            frame=self.frame();real=np.asarray(frame.hi);rows=read_panel(self.root,frame)
            _,press,unclear,absent=compare(rows,real,wanted)
            if not press:
                return rows,absent,unclear
            for label,word,target in press:
                self.press(target);self.changed.append('%s=%s'%(label,word))
        frame=self.frame();rows=read_panel(self.root,frame)
        _,press,unclear,absent=compare(rows,np.asarray(frame.hi),wanted)
        return rows,absent,unclear+[(label,word) for label,word,_ in press]
    def page_through(self,wanted):
        left=list(wanted);unclear=[];before=None
        for _ in range(MOST_PAGES):
            rows,absent,doubts=self.apply_page(left)
            unclear+=doubts;left=absent
            if not left:break
            seen=[r['label'] for r in rows]
            if seen==before:break   # the bottom of the page
            before=seen
            self.ui.wheel(-1,WHEEL_STEP,at=WHEEL_AT,scene=lambda f:True,verify_cursor=True);self.context.wait(.9)
        self.failed+=[label for label,_ in left]+[label for label,_ in unclear]


def ensure(adapter,context,inputs):
    """Open the game's settings, set what differs, and leave. Returns (changed, not confirmed)."""
    session=_Session(adapter,context,inputs)
    session.open()
    try:
        for (tab,side),wanted in WANTED.items():
            session.go(tab,side)
            if tab=='환경':session.resolution()
            session.page_through(wanted)
    finally:session.close()
    return session.changed,session.failed


def _record(root):
    return Path(root)/'settings/owner-game-settings.json'


def _wanted_rows():
    """What was checked: a row added to WANTED is asked at the next start, not only tomorrow."""
    return sorted(label for rows in WANTED.values() for label,_ in rows)


def checked_today(root,today=None):
    try:
        seen=json.loads(_record(root).read_text(encoding='utf-8'))
        return seen.get('date')==(today or time.strftime('%Y-%m-%d')) and seen.get('rows')==_wanted_rows()
    except (OSError,ValueError,AttributeError):return False


def ensure_once(adapter,context,inputs):
    """Once a day, at the first start on the field. It must never stop the work after it.
    Only a check with nothing left unconfirmed counts, so anything else is asked again at the next start."""
    root=adapter.project.root
    if checked_today(root):return
    try:
        changed,failed=ensure(adapter,context,inputs)
    except (RuntimeError,ValueError,OSError) as exc:
        LOG.warning('게임 설정 확인 중단 · %s',str(exc)[:120]);return
    LOG.info('게임 설정 확인 · 변경 %d개%s',len(changed),' · '+', '.join(changed) if changed else '')
    if failed:LOG.warning('게임 설정 미확인 · %s',', '.join(failed));return
    try:_record(root).write_text(json.dumps({'date':time.strftime('%Y-%m-%d'),'rows':_wanted_rows()},ensure_ascii=False),encoding='utf-8')
    except OSError as exc:LOG.warning('게임 설정 확인 기록 저장 보류 · %s',exc)
