"""Growth screens read by their words on the real 1366x768 frame: what the selected item is, its level, what the next
step costs, and which button does it. Nothing here sends input; callers press only what two frames agreed on.

Parsers take rows from owner_text and are plain functions. A word that is not exactly the expected word, a score under
the floor, or a number that does not fit answers None, and None presses nothing: 생명 and 여명 differ by one letter.
"""
import logging,re,time
import numpy as np
import owner_text as text

LOG=logging.getLogger('project_gui.DKB')
WORD_FLOOR=.9;NUMBER_FLOOR=.8;NAV_FLOOR=.8
LIT=160            # mean brightness beside a button's word. Measured: gold 210, dimmed 103
LIT_SATURATION=45  # the teal training button, by colour
# Real pixels of the blessing panel (centre anchored).
BLESSING_TITLE=(430,100,330,36);BLESSING_COUNT=(430,632,330,26);BLESSING_PILL=(560,700,235,42)
# Either side of the arrow in 35 >> 36: read apart, so the two never come back as 3536.
BLESSING_LEVEL=(490,202,96,34);BLESSING_NEXT=(604,202,96,34)
NAMES=('봉황','나비','도깨비','연꽃','토끼');TITLE_FLOOR=.75
# The font splits a title and can read the slot digit twice; the rest may be a letter off (가혹). The digit may not.
TITLE=re.compile(r'(.{1,4}?)가[호혹후]장[식시]([1-5])\2?(?:\(귀속\))?')
COUNT=re.compile(r'(\d[\d,]*)/(\d[\d,]*)')
# Real pixels of the energy screen (right anchored, the tabs left anchored).
ENERGY_TITLE=(960,118,360,74);ENERGY_DIAMONDS=(1300,70,60,470);ENERGY_COUNT=(1040,660,210,32);ENERGY_PILL=(1020,700,250,50);ENERGY_TABS=(0,60,280,240)
ENERGY_WORDS={'기운발현':'active','기운돌파':'breakthrough'}
ENERGY_NAME=re.compile(r'(생명|여명|몽환|홍염)의기운발현([1-9][0-9]?)단계')
# Real pixels of the spirit training detail (centre anchored) and its main screen.
SPIRIT_DIALOG=(600,138,170,30);SPIRIT_COUNTS=(490,498,380,30);SPIRIT_BUTTONS=(490,560,410,50);SPIRIT_IDLE=(540,680,290,44)
PAIR_GAP=.12
_last={}


def _sorted(rows):
    return sorted(rows,key=lambda r:(r.get('rx',0)))


def _joined(rows,floor):
    """All rows as one word, or None when any of them is unclear: half a title is not a title."""
    rows=[r for r in rows if text.clean(r['text'])]
    if not rows or any(r['score']<floor for r in rows):return None
    return ''.join(text.clean(r['text']) for r in _sorted(rows))


def _number(value):
    digits=str(value).replace(',','')
    return int(digits) if digits.isdigit() else None


def _closest_name(head):
    """The one real name this reads as. The five share no letters, so one letter off still names one of them;
    anything that sits between two, or near none, names nothing."""
    from difflib import SequenceMatcher
    scored=sorted(((SequenceMatcher(None,head,name).ratio(),name) for name in NAMES),reverse=True)
    if scored[0][0]>=.5 and scored[0][0]-scored[1][0]>=.3:return scored[0][1]
    return None


def blessing_title(rows):
    """{'name','slot','identity'} from 토끼 가호 장식1, or None. The slot digit decides the target, so it is read exactly."""
    word=_joined(rows,TITLE_FLOOR)
    found=TITLE.fullmatch(word) if word else None
    if found:
        name=found[1] if found[1] in NAMES else _closest_name(found[1].rstrip('1Il|'))
        if name:return {'name':name,'slot':int(found[2]),'identity':'blessing-words:%s%s'%(name,found[2])}
    return None


def _one_number(rows):
    """The number on one side of the arrow, or None. Two numbers, or a low score, is not one number."""
    good=[r for r in rows if re.search(r'\d',str(r['text']))]
    if len(good)!=1 or good[0]['score']<NUMBER_FLOOR:return None
    found=re.findall(r'\d+',str(good[0]['text']))
    return int(found[0]) if len(found)==1 and len(found[0])<=3 else None


def level_pair(left,right):
    """(level, next) from the two sides of 35 >> 36. They must be one apart, which a number caught redrawing (37 read
    as 3) is not. One side alone has no next step: known when it has two digits, and never pressable."""
    a,b=_one_number(left),_one_number(right)
    if a is not None and b is not None:return (a,b) if b==a+1 else None
    if a is not None and a>=10 and not any(re.search(r'\d',str(r['text'])) for r in right):return a,None
    return None


def counts(rows):
    """[(owned, needed)] from 80/5, or [] when none is clear."""
    found=[]
    for row in rows:
        if row['score']<NUMBER_FLOOR:continue
        for owned,needed in COUNT.findall(text.clean(row['text'])):
            a,b=_number(owned),_number(needed)
            if a is not None and b:found.append((a,b))
    return found


def enough(pairs):
    """True, False, or None when nothing was read."""
    return None if not pairs else all(owned>=needed for owned,needed in pairs)


def only_word(rows,words,floor=WORD_FLOOR):
    """The one row that is exactly one of these words, or None. Two of them, or a close spelling, is no answer."""
    found=[r for r in rows if text.clean(r['text']) in words]
    if len(found)!=1 or found[0]['score']<floor:return None
    return found[0]


def pill_price(rows):
    """The cost printed beside the button's word: one plain number, or None."""
    found=[str(r['text']).strip() for r in rows if re.search(r'\d',str(r['text'])) and r['score']>=NUMBER_FLOOR]
    # The comma stays in: 5,00 is half a 5,000.
    if len(found)!=1 or not re.fullmatch(r'\d{1,3}(?:,\d{3})*',found[0]):return None
    return _number(found[0])


def lit(real,row):
    """A lit button is gold around its word, a dimmed one is dark. Looks at the button beside the word, not the word."""
    x0,y0,x1,y1=row['bounds'];real=np.asarray(real)
    part=real[max(0,y0-2):y1+3,x1+6:x1+34]
    return part.size>0 and float(np.median(part.reshape(-1,3),axis=0).mean())>=LIT


def lit_colour(real,row):
    """The training button is teal rather than gold. A dimmed one has no colour."""
    x0,y0,x1,y1=row['bounds'];real=np.asarray(real)
    part=real[max(0,y0-2):y1+3,x1+6:x1+34]
    if not part.size:return False
    pixels=part.reshape(-1,3).astype(np.float32)
    return float(np.median(pixels.max(axis=1)-pixels.min(axis=1)))>=LIT_SATURATION


def hit_of(row):
    """A click on the word's middle. The small box stays where owner_hd remembers this word's anchor."""
    x,y=row['x'],row['y']
    return (x,y,(x-6,y-5,x+7,y+6))


def _any_size(root,frame,box,parse,label):
    """The world behind a title moves, and one size of the picture can spoil a word the other reads: a real title stayed
    unread on three tries while the same frame enlarged read it (22:25). The same floor and the same exact digit at each size."""
    rows=[]
    for scale in (3,2):
        rows=text.read(root,frame,box,scale=scale)
        found=parse(rows)
        if found is not None:return found
    said=[(r['text'],round(r['score'],2)) for r in rows]
    if _last.get(label)!=said:
        _last[label]=said;LOG.info('가호 %s 글자 원문 · %s',label,said)
    return None


def read_blessing(root,frame):
    """(panel, None) or (None, reason), from one real frame. The panel holds no pixels, so two can be compared."""
    title=_any_size(root,frame,BLESSING_TITLE,blessing_title,'제목')
    if title is None:return None,'가호 제목 글자 미확인'
    pair=level_pair(text.read(root,frame,BLESSING_LEVEL,scale=3),text.read(root,frame,BLESSING_NEXT,scale=3))
    if pair is None:pair=level_pair(text.read(root,frame,BLESSING_LEVEL,scale=2),text.read(root,frame,BLESSING_NEXT,scale=2))
    if pair is None:return None,'가호 강화 수치 글자 미확인'
    pill=text.read(root,frame,BLESSING_PILL,scale=3)
    word=only_word(pill,('강화','개방'))
    panel=dict(title,level=pair[0],next=pair[1],enough=enough(counts(text.read(root,frame,BLESSING_COUNT,scale=3))),
               word=text.clean(word['text']) if word else None,cost=pill_price(pill),lit=bool(word and lit(frame.hi,word)),hit=hit_of(word) if word else None)
    return panel,None


def parse_energy(rows):
    """{'name','stage','level'} from 생명의 기운 발현 2단계 and 레벨 9. Exactly one of each."""
    words=''.join(text.clean(r['text']) for r in rows if r['score']>=WORD_FLOOR and text.clean(r['text']))
    titles=ENERGY_NAME.findall(words);levels=re.findall(r'레벨([0-9]{1,3})',words)
    if len(titles)!=1 or len(levels)!=1:return None
    return {'name':titles[0][0],'stage':int(titles[0][1]),'level':int(levels[0])}


def gold_at(real,row):
    x,y=row['rx'],row['ry'];import cv2
    part=np.asarray(real)[max(0,y-14):y+15,max(0,x-14):x+15]
    if not part.size:return False
    hsv=cv2.cvtColor(part,cv2.COLOR_RGB2HSV)
    return int(((hsv[:,:,0]>5)&(hsv[:,:,0]<30)&(hsv[:,:,1]>80)&(hsv[:,:,2]>100)).sum())>=150


def selected_stage(rows,gold):
    """The stage whose diamond is lit. It must be the highest shown, and the only lit one."""
    digits=[(int(r['text']),r) for r in rows if str(r['text']).strip().isdigit() and r['score']>=NUMBER_FLOOR and 1<=int(r['text'])<=20]
    if not digits or len({n for n,_ in digits})!=len(digits):return None
    lit_rows=[n for n,r in digits if gold(r)]
    return lit_rows[0] if lit_rows==[max(n for n,_ in digits)] else None


def read_energy_title(root,frame):
    info=parse_energy(text.read(root,frame,ENERGY_TITLE,scale=2))
    if info is None:return None
    rows=text.read(root,frame,ENERGY_DIAMONDS,scale=3)
    if selected_stage(rows,lambda r:gold_at(frame.hi,r))!=info['stage']:return None
    return info


def read_energy_action(root,frame):
    """{'kind','hit','lit','enough'} for the button under the panel. kind None when it is not one clear word."""
    word=only_word(text.read(root,frame,ENERGY_PILL,scale=3),ENERGY_WORDS)
    pairs=counts(text.read(root,frame,ENERGY_COUNT,scale=3))
    return {'kind':ENERGY_WORDS[text.clean(word['text'])] if word else None,'hit':hit_of(word) if word else None,
            'lit':bool(word and lit(frame.hi,word)),'enough':enough(pairs)}


def energy_tab(root,frame,name):
    """The tab 여명의 기운 on the real frame. Exact words only, since the tabs differ by one letter."""
    row=only_word(text.read(root,frame,ENERGY_TABS,scale=3),(name+'의기운',),NAV_FLOOR)
    return hit_of(row) if row else None


# ---- pictures the native routines ask for, answered by words on a real frame

def _titled(frame,word):
    """The title zone holds an icon and a mark beside the words, which can read as letters."""
    return any(word in text.clean(t) for t in text.title(frame) or ())


def _at(detector,name):
    e=detector.entries[name];x,y,w,h=e['x'],e['y'],e['w'],e['h']
    return (x+w//2,y+h//2,(x,y,x+w,y+h))


def spirit_check(detector,name,frame):
    return _at(detector,name) if _titled(frame,'영기수련') else None


def spirit_idle(detector,name,frame):
    rows=text.read(None,frame,SPIRIT_IDLE,scale=3)
    return _at(detector,name) if _titled(frame,'영기수련') and only_word(rows,('진행중인수련이없습니다',),NAV_FLOOR) else None


def spirit_detail(root,frame):
    """What the training detail shows, or None when any part of it is unclear."""
    if not only_word(text.read(root,frame,SPIRIT_DIALOG,scale=3),('영기수련',)):return None
    buttons=text.read(root,frame,SPIRIT_BUTTONS,scale=3)
    train=only_word(buttons,('수련',));instant=only_word(buttons,('즉시완료',),NAV_FLOOR)
    pairs=counts(text.read(root,frame,SPIRIT_COUNTS,scale=3))
    if not train or not instant or abs(train['ry']-instant['ry'])>16 or train['rx']>=instant['rx'] or not pairs:return None
    return {'counts':tuple(pairs),'ready':enough(pairs) is True and lit_colour(frame.hi,train),'hit':hit_of(train)}


def _second_frame(frame):
    """One more look at the screen, for a check that decides a spend and is asked only once. Sends nothing."""
    import owner_hd
    time.sleep(PAIR_GAP)
    last=owner_hd._last_capture
    if last is None:return None
    return owner_hd._capture(*last[:3])


def spirit_train(detector,name,frame,second=_second_frame):
    """버튼_영기수련_수련 spends on a press, so it needs the dialog, both buttons and every count, on two frames."""
    first=spirit_detail(None,frame)
    if not first or first['ready'] is not True:return None
    other=second(frame)
    if other is None or getattr(other,'hi',None) is None:return None
    again=spirit_detail(None,other)
    if not again or again['ready'] is not True or again['counts']!=first['counts']:return None
    LOG.info('영기 수련 글자 확인 · 수련 버튼 · 재료 %s',' · '.join('%d/%d'%pair for pair in again['counts']))
    return again['hit']


FINDERS={'체크_영기수련':spirit_check,'체크_영기수련_미진행':spirit_idle,'버튼_영기수련_수련':spirit_train}
# Decided by words alone on a real frame: a picture must not answer for these where it has no new cut.
WORDS_ONLY=('버튼_영기수련_수련',)


def steady(name,hit):
    """Reads of one word can differ by a pixel, and a native check reads a change of place as a different target."""
    before=_last.get(name)
    if before and hit and abs(before[0]-hit[0])<=4 and abs(before[1]-hit[1])<=4:return before
    _last[name]=hit
    return hit


def answers(name,frame):
    return name in FINDERS and getattr(frame,'hi',None) is not None and getattr(frame,'shape',None)==(479,897,3)


def find_word(detector,name,frame):
    """The hit for a picture this module answers for, or None."""
    try:hit=FINDERS[name](detector,name,frame)
    except Exception as exc:
        LOG.debug('글자 찾기 생략 · %s · %s',name,type(exc).__name__);return None
    return steady(name,hit) if hit else None
