"""Preset letter B swaps skills only: 장비·가호·의복 1, 도술 2 (user 11-06).

A new character's letter B holds 장비2·가호2·도술2·의복2, so switching to it for a boss takes every worn item off.
The H menu's cog opens 프리셋 설정; the letter picked there is applied at once, and each section's buttons pick
that letter's preset. A picked button has a fully white bottom edge (pc1 20:21: 1.00 against 0.38 at most).
Done once per character, then remembered; letter A is put back before the panel closes.
"""
import hashlib,json,logging
from pathlib import Path

LOG=logging.getLogger('project_gui.DKB')
COG=(1110,435);TITLE=(1120,68,190,34);CLOSE=(1343,85);WHEEL=(1213,500)
LETTER_Y=142;LETTER_X={'A':1118,'B':1165,'C':1213,'D':1261,'E':1309}
PANEL=(1075,160,285,550);BUTTON_X={1:1147,2:1280};BUTTON_BELOW=42;BUTTON_HALF=(65,30)
SECTIONS=('장비프리셋','가호프리셋','도술프리셋','의복프리셋')


def wanted(letter):
    """B: everything as A except the skills, which use preset 2."""
    return {'장비프리셋':1,'가호프리셋':1,'도술프리셋':2,'의복프리셋':1} if letter=='B' else None


def _flag(root,character):
    ident=hashlib.sha256(str(character).strip().encode('utf-8')).hexdigest()[:24]
    return Path(root)/'settings'/('owner-preset-compose-'+ident+'.json')


def done(root,character,letter):
    try:return json.loads(_flag(root,character).read_text(encoding='utf-8')).get(letter) is True
    except (OSError,ValueError):return False


def remember(root,character,letter):
    path=_flag(root,character)
    try:value=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):value={}
    value[letter]=True;path.write_text(json.dumps(value),encoding='utf-8')


def words(frame,box):
    import owner_text as text
    return [dict(row,word=text.clean(row['text'])) for row in text.read(None,frame,box,scale=2,minimum=.55)]


def picked(real,x,y):
    """The button at (x, y) shows the picked frame: one fully white row near its bottom edge."""
    import numpy as np
    half_w,half_h=BUTTON_HALF;patch=np.asarray(real)[y-half_h:y+half_h,x-half_w+12:x+half_w-12].astype(int)
    return any(float((row.min(axis=1)>170).mean())>=.8 for row in patch)


def headers(frame):
    """{section: real y} for the section titles shown in the panel."""
    found={}
    for row in words(frame,PANEL):
        for name in SECTIONS:
            if name in row['word'] and name not in found:found[name]=round(row['ry'])
    return found


class Compose:
    def __init__(self,ui):
        import owner_hd as hd
        self.ui,self.service,self.context,self.hd=ui,ui.service,ui.context,hd

    def tap(self,x,y,wait=.8):
        self.context.checkpoint();self.service.click_hit(self.hd.real_hit(x,y));self.context.wait(wait)

    def real(self):return self.ui.frame()

    def panel_open(self,frame):return any('프리셋설정' in r['word'] for r in words(frame,TITLE))

    def open(self):
        from owner_quick_preset import KEY_H,_wait_open
        if self.panel_open(self.real()):return True
        self.service.key(KEY_H)
        if _wait_open(self.service) is None:return False
        self.tap(*COG,1.2)
        return self.panel_open(self.real())

    def scroll(self,down):
        x,y=self.hd.logical_of(*WHEEL)
        self.ui.wheel(-1 if down else 1,4,at=(round(x),round(y)),scene=self.panel_open);self.context.wait(.6)

    def set_section(self,name,number):
        for _ in range(3):
            frame=self.real();top=headers(frame)
            if name in top and top[name]+BUTTON_BELOW+BUTTON_HALF[1]<PANEL[1]+PANEL[3]:break
            self.scroll(True)
        else:raise RuntimeError(name+' 줄 미확인')
        x,y=BUTTON_X[number],top[name]+BUTTON_BELOW
        if not picked(frame.hi,x,y):self.tap(x,y,.8)
        if not picked(self.real().hi,x,y):raise RuntimeError('%s %d번 선택 확인 실패'%(name,number))

    def run(self,letter):
        plan=wanted(letter)
        if plan is None:return False
        if not self.open():raise RuntimeError('프리셋 설정 창 미확인')
        try:
            self.tap(LETTER_X[letter],LETTER_Y,1.2)
            for name in SECTIONS:self.set_section(name,plan[name])
            self.scroll(False)
            self.tap(LETTER_X['A'],LETTER_Y,1.2)
        finally:self.tap(*CLOSE,.8)
        return True


def ensure(adapter,context,inputs,letter):
    """Before switching to letter for the first time on this character. A failure is logged; the switch goes on."""
    if wanted(letter) is None:return False
    from owner_hunt_rules_candidate import configured_identity
    root=adapter.project.root;character=configured_identity(root)
    if done(root,character,letter):return True
    from owner_mission_ui import MissionUI
    try:
        Compose(MissionUI(adapter,context,inputs)).run(letter)
    except Exception as exc:
        from biol_base.session import Cancelled
        if isinstance(exc,Cancelled):raise
        LOG.warning('프리셋 %s 구성 보류 · %s',letter,str(exc)[:120]);return False
    remember(root,character,letter)
    LOG.info('프리셋 %s 구성 · 장비·가호·의복 1번 · 도술 2번',letter)
    return True
