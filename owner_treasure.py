"""Only known routes with sufficient combat power; unknown routes stay queued.

On a real frame the native entry's screen, tabs and rows are answered by their words: its pictures and pixel checks
miss the open tab, the selected row and the castle's done badge at 1366x768, and then it never gets past choosing a point.
"""
from difflib import SequenceMatcher
from functools import wraps
import logging,time
import numpy as np
import owner_hd as hd
import owner_text as text
from owner_progression import state
LOG=logging.getLogger('project_gui.DKB')
# The native entry itself only has maps for this region (ENABLED_REGIONS); the
# other two return "해당 지방 준비 중" before any input. Nothing here changes that.
REGION_SETTING='auto_challenge.treasure_hunt.region'
# Native point 2 (영험한 청산, 5 maps, 21 chests), 3 (안개 기슭 지하, 4) and 4
# (산신의 영역 지하, 4) all take the same walk: the native card check still
# requires the green (sufficient) power digits before it clicks 진입.
POWER_ROUTES=('포인트_보물찾기_타바로2','포인트_보물찾기_타바로3','포인트_보물찾기_타바로4')
TITLE='보물찾기'
# Real pixels. Words are looked for inside these, and nothing is pressed by its place alone.
MENU=(930,60,436,640);SIDE=(10,62,135,330);FOOT=(1100,700,266,60);FIRST_CARD=(150,110,245,50)
# The menu's label sits under its icon, and the icon is the point known to open the screen.
LABEL_UNDER_ICON=25
TABS={'타바로지방':'버튼_보물찾기_타바로지방','가모리지방':'버튼_보물찾기_가모리지방','수아리지방':'버튼_보물찾기_수아리지방'}
ROWS={'체크_보물찾기_타바로1':'타바로성','체크_보물찾기_타바로2':'영험한청산','체크_보물찾기_타바로3':'안개기슭지하','체크_보물찾기_타바로4':'산신의영역지하',
      '체크_보물찾기_가모리1':'귀명촌','체크_보물찾기_가모리2':'숨겨진해골동굴','체크_보물찾기_가모리3':'주술결계동굴'}
ROW_ABOVE={'타바로성':'타바로지방'}
CASTLE_DONE='체크_보물찾기_타바로1_완료'
FIRST_CARD_WORDS={'버튼_보물찾기_타바로_바로가기':'바로가기','체크_보물찾기_타바로_현위치':'현위치'}
# The card you stand on has 현위치 where the others have 바로가기. Unseen, it was pressed for a move window that never
# comes, and the visit ended on 이동 버튼 확인 시간 초과 with nothing found (other PC, 19:35).
CURRENT_ICONS=('체크_보물찾기_현위치아이콘','체크_보물찾기_현위치아이콘2');CARD_ROW=(150,110,1216,50)
GREEN_SPREAD=40;GREEN_PIXELS=20
LIT_RATIO=1.5;CHOSEN_RATIO=1.15
_running=[0]


def allowed_points(power,recent_death=False):
    points=['포인트_보물찾기_타바로1']  # Town route: no combat-power requirement.
    # The full second route reaches an 85,050 requirement. 50% headroom is a
    # conservative local policy, not a guarantee that every build survives.
    if isinstance(power,int) and power>=127575 and not recent_death:points.extend(POWER_ROUTES)
    return points


def _like(seen,wanted):
    seen=text.clean(seen)
    return wanted in seen or SequenceMatcher(None,seen,wanted).ratio()>=.7


def _hit(row,frame,above=0):
    x,y=hd.logical_of(row['rx'],row['ry']-above,frame.layout)
    x0,y0,x1,y1=text.logical_bounds({**row,'x':x,'y':y},frame)
    return x,y,(x0,y0,x1,y1)


def _is_real(frame):
    return getattr(frame,'hi',None) is not None and getattr(frame,'shape',None)==(479,897,3)


def _on_screen(frame):
    return bool(text.shows_title(frame,TITLE))


def _side(frame):
    return text.read(None,frame,SIDE)


def tab_rows(rows):
    """{word: row} for the region tabs that read."""
    return {word:row for word in TABS for row in rows if text.clean(row['text'])==word}


def lit_tab(real,tabs):
    """The open tab: white against the grey of the others. None with fewer than two to compare, or no clear winner."""
    if len(tabs)<2:return None
    light={}
    for word,row in tabs.items():
        x0,y0,x1,y1=row['bounds'];light[word]=float(np.median(np.asarray(real)[y0:y1,x0:x1]))
    best=max(light,key=light.get)
    others=[v for w,v in light.items() if w!=best]
    return best if light[best]>=max(others)*LIT_RATIO else None


def point_row(rows,name):
    """The list row for this point. A done badge covers the castle's middle letter, so it is told by its ending and by
    being the first row under its tab."""
    wanted=ROWS.get(name)
    if wanted is None:return None
    tab=ROW_ABOVE.get(wanted)
    if tab:
        above=tab_rows(rows).get(tab)
        if above is None:return None
        return next((r for r in rows if r['ry']>above['ry'] and (text.clean(r['text']).endswith('로성') or _like(r['text'],wanted))),None)
    return next((r for r in rows if _like(r['text'],wanted)),None)


def _ink(real,row):
    x0,y0,x1,y1=row['bounds'];part=np.asarray(real)[y0:y1,x0:x1].min(axis=2)
    return float(np.percentile(part,95)) if part.size else 0.


def chosen_row(real,rows,name):
    """Is this point's row the lit one? Its words are white and the rows around it are grey, whatever the level of each."""
    mine=point_row(rows,name)
    if mine is None:return False
    # The rows of one list sit between its tab and the next.
    words=[r for r in rows if r is not mine and text.clean(r['text']) not in TABS and abs(r['rx']-mine['rx'])<=40 and len(text.clean(r['text']))>=3]
    if not words:return False
    return _ink(real,mine)>=max(_ink(real,r) for r in words)*CHOSEN_RATIO


def has_done_badge(real,row):
    """The castle's green check over its letters. Rows without it measure 0 green pixels, the badge about 40."""
    x0,y0,x1,y1=row['bounds']
    part=np.asarray(real)[max(0,y0-6):y1+6,max(0,x0-6):x1+6].astype(np.int16)
    return int((part[:,:,1]-np.maximum(part[:,:,0],part[:,:,2])>GREEN_SPREAD).sum())>=GREEN_PIXELS


def current_card(frame,region):
    """현위치 on a card, inside the part of the row the caller asks about. Region is (x, y, w, h) in logical terms."""
    hits=[_hit(row,frame) for row in text.find(text.read(None,frame,CARD_ROW),'현위치')]
    if isinstance(region,(tuple,list)) and len(region)==4:
        x,y,w,h=region;hits=[hit for hit in hits if x<=hit[0]<x+w and y<=hit[1]<y+h]
    return hits[0] if hits else None


def word_answer(name,frame,region=None):
    """(answered, hit). Not answered means the picture still decides this one."""
    if name in CURRENT_ICONS and _on_screen(frame):return True,current_card(frame,region)
    if name=='버튼_보물찾기':
        row=next((r for r in text.read(None,frame,MENU) if _like(r['text'],TITLE)),None)
        return (True,_hit(row,frame,LABEL_UNDER_ICON)) if row else (False,None)
    if name=='체크_보물찾기':
        row=next((r for r in text.read(None,frame,text.TITLE) if _like(r['text'],TITLE)),None)
        return (True,_hit(row,frame)) if row else (False,None)
    if not _on_screen(frame):return False,None
    if name=='버튼_보물찾기_보상모두받기':
        rows=text.find(text.read(None,frame,FOOT),'보상모두받기')
        return True,_hit(rows[0],frame) if rows else None
    if name in FIRST_CARD_WORDS:
        rows=text.find(text.read(None,frame,FIRST_CARD),FIRST_CARD_WORDS[name])
        return True,_hit(rows[0],frame) if rows else None
    if name in ROWS:
        row=point_row(_side(frame),name)
        return (True,_hit(row,frame)) if row else (False,None)
    for word,closed in TABS.items():
        if name not in (closed,closed+'열림'):continue
        tabs=tab_rows(_side(frame));row=tabs.get(word)
        if row is None:return False,None
        lit=lit_tab(frame.hi,tabs)
        if lit is None:return False,None
        return True,_hit(row,frame) if (lit==word)==(name!=closed) else None
    return False,None


def _on_real(ordinary,answer):
    """Words on a real frame with this row on it, the original check on anything else."""
    @wraps(ordinary)
    def check(detector,frame,name,*rest):
        if _is_real(frame) and (name in ROWS or name==CASTLE_DONE) and _on_screen(frame):
            return answer(frame,name)
        return ordinary(detector,frame,name,*rest)
    check._owner_treasure_words=True
    return check


def castle_done(frame,name):
    if name!=CASTLE_DONE:return None
    rows=_side(frame);row=point_row(rows,'체크_보물찾기_타바로1')
    return _hit(row,frame) if row is not None and has_done_badge(frame.hi,row) else None


def point_chosen(frame,name):
    return chosen_row(frame.hi,_side(frame),name)


def install_words():
    """Safe to call again. The find only answers while the native entry runs, so no other screen pays for reading."""
    from roi_runtime import RoiDetector
    from project_adapter import treasure_entry as native
    if getattr(RoiDetector.find,'_owner_treasure_words',False):return
    ordinary=RoiDetector.find
    @wraps(ordinary)
    def find(detector,name,frame,region=None,threshold=.9,*,candidate_filter=None):
        if _running[0] and _is_real(frame):
            answered,hit=word_answer(name,frame,region)
            if answered:return hit if hit is None or candidate_filter is None or candidate_filter(frame,hit) else None
        return ordinary(detector,name,frame,region,threshold,candidate_filter=candidate_filter)
    find._owner_treasure_words=True;RoiDetector.find=find
    native.completion_marker_hit=_on_real(native.completion_marker_hit,castle_done)
    native.selected_point_active=_on_real(native.selected_point_active,point_chosen)
    native.selected_point_confirmed=_on_real(native.selected_point_confirmed,point_chosen)


def install(gui):
    from project_adapter._entry import Adapter
    from project_adapter import treasure_entry
    if getattr(Adapter.run_treasure_region_entry,'_owner_treasure_gate',False):return
    install_words()
    ordinary=Adapter.run_treasure_region_entry
    @wraps(ordinary)
    def run(adapter,context,inputs):
        context.checkpoint();progress=state(adapter)
        power=progress.power if time.monotonic()-progress.observed<=300 else None
        allowed=allowed_points(power,time.monotonic()-progress.last_death<600)
        original=treasure_entry.REGIONS['타바로지방']
        selected=[p for p in original[2] if p in allowed]
        region=adapter.values.get(REGION_SETTING) if isinstance(getattr(adapter,'values',None),dict) else None
        LOG.info('보물찾기 안전 조건 · 지방=%s · 전투력=%s · 허용 경로=%s · 미확인 고위험 경로 보류',region,power,','.join(selected))
        if power is None:LOG.info('보물찾기 전투력 미확인 · 5분 내 판독 없음 · 타바로1만 허용')
        treasure_entry.REGIONS['타바로지방']=(original[0],original[1],selected)
        _running[0]+=1
        try:return ordinary(adapter,context,inputs)
        finally:
            _running[0]-=1;treasure_entry.REGIONS['타바로지방']=original
    run._owner_treasure_gate=True;Adapter.run_treasure_region_entry=run;gui._owner_treasure_gate=True
