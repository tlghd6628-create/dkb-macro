"""A quest's 감정표현 step at 1366x768, by the screen's own words.

pc1 11-06 13:40, [5장] 반가운 재회 ('지정 위치에서 채팅-감정표현 중 '웃음' 사용하기'): clicking the quest's title in the
tracker walks the character to its spot; the chat opens from its preview at the bottom left, the face button opens the
감정 표현 panel, and the 웃음 card there moved the quest on at once (a dialogue with 몽련 began). The old path looked for
897x479 pictures of the chat and the target spot and never started.

Each input is one click on a word or a place proved on the same frame; the per-character one-minute rate and its three
attempts are the existing ones.
"""
import logging,re,time
import numpy as np
import owner_hd as hd
import owner_text as text

LOG=logging.getLogger('project_gui.DKB')
EMOTES=('웃음','부끄','삐짐','놀람','메롱','윙크','화남','졸기','황당','뽐내기','슬픔','인사','박수','하트','감사','최고')
TRACKER=(1095,75,215,225)          # real: the quest tracker at the top right
CHAT_PREVIEW=(160,705)             # real: the chat lines at the bottom left, which open the chat
CHAT_INPUT=(90,722,255,26);CHAT_HEAD=(15,12,90,32);CHAT_CLOSE=(372,28)
FACE_BUTTON=(316,688)              # real: the face under the chat lines, which opens the 감정 표현 panel
PANEL_TITLE=(420,485,220,30);PANEL_CARDS=(400,515,285,245);PANEL_CLOSE=(672,500)
CARD_ABOVE_WORD=33                 # the card's face stands this far above its word
SETTLE=(400,120,600,420)           # real: the middle of the field, still once the walk is over


def words(frame,box,minimum=.6):
    return [dict(row,word=text.clean(row['text'])) for row in text.read(None,frame,box,scale=2,minimum=minimum)]


def requirement(frame,title):
    """(emote, title row) when the tracker shows this quest asking for a 감정표현 under its title, else None."""
    rows=sorted(words(frame,TRACKER,.5),key=lambda r:r['ry'])
    tag=re.match(r'\[[^\]]+\]',title or '')
    for i,row in enumerate(rows):
        if '감정표현' not in row['word']:continue
        found=[name for name in EMOTES if name in row['word']]
        heads=[r for r in rows[:i] if '[' in r['word'] or '장]' in r['word']]
        if len(found)==1 and heads and (not tag or text.clean(tag[0]) in heads[-1]['word']):return found[0],heads[-1]
    return None


def tracker_title(frame,mode,title=None):
    """The tracker's row of the running quest: with its title known, only the row that reads as that title; else a
    [N장] title for the main quest, or the first other [..] title."""
    rows=sorted(words(frame,TRACKER,.5),key=lambda r:r['ry'])
    titled=[r for r in rows if '[' in r['word'] and ']' in r['word']]
    if title:
        from difflib import SequenceMatcher
        want=text.clean(title).lstrip('!①')
        near=[r for r in titled if SequenceMatcher(None,r['word'].lstrip('!①'),want).ratio()>=.8]
        return near[0] if len(near)==1 else None
    main=[r for r in titled if re.search(r'\d+장\]',r['word'])]
    if mode=='main_quest':return main[0] if main else None
    others=[r for r in titled if r not in main]
    return others[0] if others else None


def settle(ui,seconds=25.):
    """Wait until the field stops moving after a walk (two still looks in a row), at most seconds."""
    end=time.monotonic()+seconds;last=None;still=0
    while time.monotonic()<end:
        ui.context.wait(.8);ui.context.checkpoint()
        x,y,w,h=SETTLE;now=np.asarray(ui.frame().hi)[y:y+h:4,x:x+w:4].astype(np.int16)
        if last is not None and float(np.abs(now-last).mean())<4:
            still+=1
            if still>=2:return True
        else:still=0
        last=now
    return False


def chat_open(frame):
    return any('채팅을입력' in r['word'] for r in words(frame,CHAT_INPUT,.5)) or any(r['word']=='전체' for r in words(frame,CHAT_HEAD))


def panel_open(frame):
    return any('감정' in r['word'] and '표현' in r['word'] for r in words(frame,PANEL_TITLE))


def click(ui,place,wait=1.):
    ui.context.checkpoint();x,y,box=hd.real_hit(*place)
    ui.service.click_hit((x,y,box)) if getattr(ui,'service',None) else ui.click(x,y,lambda f:True)
    ui.context.wait(wait)


def close_all(ui):
    from owner_quest_emote_candidate import empty_chat
    frame=ui.frame()
    if panel_open(frame):click(ui,PANEL_CLOSE,.6);frame=ui.frame()
    if chat_open(frame):
        if not empty_chat(frame):LOG.warning('감정표현 후 채팅 입력칸이 비어 있지 않음 · 닫지 않음');return False
        click(ui,CHAT_CLOSE,.8)
    return not chat_open(ui.frame())


def run(ui,book,key):
    """True when the emote was pressed; False when this quest is not asking for one now, or it must wait."""
    frame=ui.frame()
    if getattr(frame,'hi',None) is None:return False
    row=book.item.get('quests',{}).get(key) or {}
    need=requirement(frame,row.get('title'))
    if not need:return False
    target,head=need
    from owner_emote_cooldown import Rate
    from owner_progression import state
    from owner_hunt_rules_candidate import configured_identity
    character=state(ui.adapter).character;scope=configured_identity(ui.adapter.project.root)
    rate=Rate(ui.adapter.project.root,scope,character)
    if rate.remaining()>0:return False
    # Walk to the quest's spot by its own title; already there, the character just stays.
    click(ui,(round(head['rx']),round(head['ry'])),1.)
    settle(ui)
    if not chat_open(ui.frame()):click(ui,CHAT_PREVIEW,1.)
    if not chat_open(ui.frame()):
        LOG.info('감정 임무 · 채팅창 안 열림 · %s',target);return False
    if not panel_open(ui.frame()):click(ui,FACE_BUTTON,1.)
    frame=ui.frame()
    if not panel_open(frame):
        LOG.info('감정 임무 · 감정 표현 창 안 열림 · %s',target);close_all(ui);return False
    cards=[r for r in words(frame,PANEL_CARDS) if r['word']==target]
    if len(cards)!=1:
        LOG.info('감정 임무 · %s 카드 못 찾음 · 보이는 카드 %s',target,[r['word'] for r in words(frame,PANEL_CARDS)]);close_all(ui);return False
    rate.reserve(key,target)
    click(ui,(round(cards[0]['rx']),round(cards[0]['ry'])-CARD_ABOVE_WORD),2.)
    after=ui.frame();left=requirement(after,row.get('title'))
    LOG.info('감정 임무 · %s 누름 · %s',target,'요구 사라짐' if not left else '요구 그대로')
    if chat_open(after) or panel_open(after):close_all(ui)
    return True
