"""Growth of worn items and blessings by way of the bag, at 1366x768.

A worn tile on the info panel is clicked, its details say what it is, and its own 성장 button opens the growth screen with
that item selected. Nothing picks from the growth screen's list, so a spare can never be taken for a worn item.

The durable input record and its guard are the ordinary ones. What the details window reads is the truth: a record left
from an earlier press settles against it when the same item is read again, and the value decides what happens next.
"""
from owner_settle import settle
import logging,re,time
from pathlib import Path
import numpy as np
import owner_text as text
import owner_worn_stats as worn
from owner_gear_decision_candidate import Observation
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_settings_candidate import Store
from owner_gear_step_guard_candidate import Guard
from owner_growth_reading import breakthrough_allowed,goal_state
from owner_growth_words import (BLESSING_COUNT,BLESSING_LEVEL,BLESSING_NEXT,BLESSING_PILL,BLESSING_TITLE,clean_pair,counts,enough,left_pair,level_pair,lit,lone_one_pair,next_pair,only_word,pill_price)
from owner_hd import real_hit
from owner_short_notice import shown as coins_short

LOG=logging.getLogger('project_gui.DKB')
SIDE_TABS=(0,100,170,240)      # real pixels of 강화 돌파 각성
GROWTH_BUTTON=(570,560,120,46) # real pixels of the details window's 성장
LIST_COUNT=(1066,78,105,24);SECOND_TILE=(1150,146)  # the growth list: how many it shows, and the tile after the selected one
RESULT_CLOSE=(400,640,560,100);RESULT_SECONDS=20
HOLD_WORDS=(500,585,370,160);HOLD_BUTTON=(683,682);HOLD_SECONDS=6  # real: 길게 터치하여 돌파 at y 606, its button 682, 버튼을 눌러 주세요! 724 (pc1 11-06 13:30)
SKIP_BOXES=((1180,8,186,90),(1180,660,186,108))  # real: its 넘기기, which the user says does the 돌파 (top right on pc1 13:02)
BACK=(35,30)                   # real place of the growth screen's back arrow
ACTION_PILL=(470,700,325,42)   # real pixels of the 돌파 or 각성 button and its price
VISIT_SECONDS=300;ITEM_SECONDS=VISIT_SECONDS;  # one stay per item: leaving every 90 s to reread its details was the in-and-out (user 11-06)
RESULT_READS=8;ROUNDS=8;LEVEL_STEP=3
FRESH_SECONDS=8
ENHANCE,BREAK,AWAKEN='enhance','breakthrough','awaken';READ='read'
LABEL={ENHANCE:'강화',BREAK:'돌파',AWAKEN:'각성'}


class CoinsShort(Exception):
    """The game said there are no coins for this. The turn ends; nothing was spent."""


def real_place(row):
    """A click on the word just read, exactly where it was read."""
    return real_hit(row['rx'],row['ry'])


def title_words(root,frame):
    return ''.join(text.clean(row['text']) for row in text.read(root,frame,BLESSING_TITLE,scale=2,minimum=.5))


def have_enough(root,frame):
    """True, False, or None when unread. The 0 of 0/1 can read as a letter at one size and clearly at the other (팔찌, 11-06)."""
    for scale in (3,2):
        pairs=counts(text.read(root,frame,BLESSING_COUNT,scale=scale))
        if pairs:return enough(pairs)
    return None


def list_count(frame):
    """How many tiles the growth list says it holds, or None. A lone digit reads best with room around it, at a larger size."""
    x,y,w,h=LIST_COUNT
    for box,scale in (((x,y,w,h),3),((x,y-3,w,h+6),4),((x,y,w,h),2)):
        shown=[text.clean(r['text']) for r in text.read(None,frame,box,scale=scale,minimum=.5)]
        shown=[word for word in shown if word.isdigit()]
        if len(shown)==1:return int(shown[0])
    return None


def font_pair(left,right):
    """40 >> 41 read as 40 >> 47: the font's 1 reads 7. The two sides are one apart, so that settles it when exactly one way of
    swapping 7 for 1 makes them so. Anything else stays unread."""
    from itertools import product
    def number(rows):
        # The + beside the next level lowers its score, so this floor is lower than the plain reader's. The sides must still fit.
        good=[r for r in rows if re.search(r'\d',str(r['text'])) and r['score']>=.5]
        found=re.findall(r'\d+',str(good[0]['text'])) if len(good)==1 else ()
        return int(found[0]) if len(found)==1 and len(found[0])<=3 else None
    a,b=number(left),number(right)
    if a is None or b is None:return None
    def ways(number):
        digits=str(number);spots=[i for i,d in enumerate(digits) if d=='7']
        return {int(''.join('1' if i in spots and pick[spots.index(i)] else d for i,d in enumerate(digits))) for pick in product((False,True),repeat=len(spots))}
    found=[(x,y) for x in ways(a) for y in ways(b) if y==x+1]
    return found[0] if len(found)==1 else None


def read_panel(root,frame):
    """The selected item's level and next step on the 강화 tab, from one real frame, or None."""
    if not title_words(root,frame):return None
    pair=clean_pair(frame,root)
    if pair is None:
        # Only when the cleaned digits did not read: two OCR calls fewer on every look (user 11-06: 강화 too slow).
        left,right=text.read(root,frame,BLESSING_LEVEL,scale=3),text.read(root,frame,BLESSING_NEXT,scale=3)
        pair=level_pair(left,right) or font_pair(left,right)
    if pair is None:
        left,right=text.read(root,frame,BLESSING_LEVEL,scale=2),text.read(root,frame,BLESSING_NEXT,scale=2)
        pair=level_pair(left,right) or font_pair(left,right)
    if pair is None:pair=lone_one_pair(frame,text.read(root,frame,BLESSING_NEXT,scale=3))
    if pair is None:pair=next_pair(text.read(root,frame,BLESSING_LEVEL,scale=3),text.read(root,frame,BLESSING_NEXT,scale=3))
    if pair is None:pair=left_pair(frame,root)
    if pair is None:return None
    pill=text.read(root,frame,BLESSING_PILL,scale=3);word=only_word(pill,('강화','개방'))
    have=have_enough(root,frame)
    opening=bool(word) and text.clean(word['text'])=='개방'
    # A step that opens the next tier can show no counter, but a count that is short stays short.
    material=have is not False if opening else have is True
    cost=pill_price(pill)
    active=bool(word and lit(frame.hi,word) and type(cost) is int and cost>0 and pair[1]==pair[0]+1 and material)
    return {'level':pair[0],'next':pair[1],'word':text.clean(word['text']) if word else None,'cost':cost,'enough':have,'active':active,
            'opening':opening,'hit':real_place(word) if word else None}


def read_action(root,frame,word):
    """The 돌파 or 각성 button and its count, or None when the panel holds no item."""
    if not title_words(root,frame):return None
    # Without 자동 선택 beside it the pill stands further left, its price with it.
    pill=text.read(root,frame,ACTION_PILL,scale=3);row=only_word(pill,(word,),.8)
    if row is None:return None
    cost=pill_price(pill);have=have_enough(root,frame)
    return {'word':word,'cost':cost,'enough':have,'active':bool(lit(frame.hi,row) and have is True and type(cost) is int and cost>0),'hit':real_place(row)}


class Item:
    """One worn tile: where it is, what it answers to in the settings, what its details last said."""
    def __init__(self,slot,blessing):
        self.slot=slot;self.blessing=blessing;self.values=None;self.grade=None;self.title='';self.done=set();self.changed=False
    @property
    def key(self):return self.slot[-1]+'번' if self.blessing else self.grade
    @property
    def record(self):return 'worn:'+self.slot


class EnhanceObserver:
    """The guard's two looks at the 강화 tab of the item the bag opened."""
    def __init__(self,service,context,identity,item,clock=time.monotonic):
        self.service=service;self.context=context;self.identity=identity;self.item=item;self.clock=clock
        self.sequence=0;self.panel=None;self.root=Path(service.adapter.project.root);self.last_diff=None;self.looked_at=None
    def read_pair(self):
        looks=[];stamps=[]
        for _ in range(2):
            self.context.checkpoint();self.service.check();frame=self.service.capture()
            panel=read_panel(self.root,frame)
            if panel is None:
                self.last_diff='판독 없음';return {'screen_proof':False}
            looks.append(panel);stamps.append(self.clock());self.context.wait(.12)
        same=lambda panel:{k:v for k,v in panel.items() if k!='hit'}
        if same(looks[0])!=same(looks[1]):
            # Which part flickered, for the log when the guard holds.
            self.last_diff={k:(looks[0].get(k),looks[1].get(k)) for k in same(looks[0]) if looks[0].get(k)!=looks[1].get(k)}
            return {'screen_proof':False}
        self.panel=looks[1];obs=[];self.looked_at=stamps[:]
        for stamp,panel in zip(stamps,looks):
            self.sequence+=1
            obs.append(Observation(self.sequence,stamp,self.identity,'worn-slot:'+self.item.slot,self.item.record,self.item.key,panel['level'],None,None,panel['active'],None,None))
        return {'screen_proof':True,'first':obs[0],'second':obs[1],'resource_mode':'native_active','active_pair_verified':looks[1]['active'],
                'button_name':looks[1]['word'],'opening':looks[1]['opening'],'item_icon':None}


class Route:
    def __init__(self,adapter,context,inputs,service,identity,profile,character,document):
        self.adapter=adapter;self.context=context;self.inputs=inputs;self.service=service;self.identity=identity
        self.profile=profile;self.character=character;self.document=document;self.root=Path(adapter.project.root)
        path=Store(self.root,identity).path
        self.intents=IntentStore(path.with_name(path.stem+'-intent.json'))
        self.deadline=time.monotonic()+VISIT_SECONDS
    # ---- moving between the bag and the growth screen
    def check(self):self.context.checkpoint();self.service.check()
    def frame(self):self.check();return self.service.capture()
    def in_growth(self):return text.shows_title(self.frame(),'성장') is True
    def open_bag(self):
        from owner_progression import inventory_parts,open_inventory_by_key
        if inventory_parts(self.frame())[0] is True:return True
        open_inventory_by_key(self.service)
        # A click on a tile just after the panel opens is lost.
        self.context.wait(1.5)
        return inventory_parts(self.frame())[0] is True
    def leave_growth(self):
        for _ in range(3):
            if not self.in_growth():return True
            self.service.click_hit(real_hit(*BACK));settle(self.service,self.context,1.2)
        return not self.in_growth()
    def into_growth(self,item):
        """From the open details window, by its own button."""
        for _ in range(5):
            row=only_word(text.read(None,self.frame(),GROWTH_BUTTON,scale=2),('성장',),.7)
            if row:break
            self.context.wait(.2)
        else:
            LOG.info('착용 %s 성장 버튼 못 찾음',item.slot);return False
        self.service.click_hit(real_place(row))
        for _ in range(15):
            self.context.wait(.3)
            if self.in_growth():
                self.context.wait(.8);return True
        LOG.info('착용 %s 성장 화면 안 열림',item.slot);return False
    # ---- what the details say
    def goal(self,item):
        if not item.blessing:return self.document['grades'].get(item.key)
        # Saved under the old field's name: a blessing has awakening, not breakthrough.
        row=self.document['blessings'].get(item.key)
        return dict(row,awaken=row.get('breakthrough')) if isinstance(row,dict) else row
    def need(self,item):
        """The next thing this item is short of, by its own details. None when it has its goals or none of it can run."""
        goal=self.goal(item)
        if not isinstance(goal,dict) or goal.get('enabled') is not True:return None
        kinds=(ENHANCE,AWAKEN) if item.blessing else (ENHANCE,BREAK,AWAKEN) if breakthrough_allowed() else (ENHANCE,AWAKEN)
        for kind in kinds:
            if kind in item.done or resting(self.adapter,item.slot,kind):continue
            value=item.values.get(kind)
            if type(value) is int and type(goal.get(kind)) is int and value<goal[kind]:return kind
        return None
    def settle(self,item):
        """A press left waiting is settled by the details just read: the value rose, or it did not and the press did nothing."""
        pending=self.intents.pending()
        if not pending or pending['before'].slot!=item.record:return
        kind=pending['kind'];field={ENHANCE:'enhancement',BREAK:'breakthrough',AWAKEN:'awakening'}[kind]
        before=getattr(pending['before'],field);now=item.values.get(kind)
        if type(now) is not int:return
        if type(before) is int and now>before:self.intents.complete('observed_progress')
        else:
            self.intents.complete('observed_failure' if kind==BREAK else 'no_effect')
            LOG.info('착용 %s %s 수치 그대로 · %s',item.slot,LABEL[kind],'돌파 실패' if kind==BREAK else '입력 효과 없음')
    def read(self,item):
        """Read the item's details down to its numbers, which also puts them in the program's table, and close."""
        self.leave_growth()
        # A blessing is read on the blessing screen, which the reader opens.
        if not item.blessing and not self.open_bag():
            LOG.info('착용 %s 건너뜀 · 인벤토리 안 열림',item.slot);return False
        # The window just closed fades out, and a click into the fade is lost.
        worn.settle_after_popup(self.service,self.context)
        def decide(values,grade,title):
            item.values=values;item.grade=grade;item.title=title
            self.settle(item)
            return False
        return worn.inspect_real(self.service,self.context,self.inputs,self.profile,self.character,item.slot,decide=decide) is True
    def enter(self,item):
        """Its details, then straight to its 성장 button: no need to scroll down to the numbers for that."""
        self.leave_growth()
        if not item.blessing and not self.open_bag():
            LOG.info('착용 %s 건너뜀 · 인벤토리 안 열림',item.slot);return False
        worn.settle_after_popup(self.service,self.context)
        if not worn.open_tile(self.service,self.context,item.slot):return False
        heading=worn.tile_heading(self.service,self.context,item.slot)
        if heading is not None:
            if item.grade is None:item.grade=heading[1]
            if self.into_growth(item):return True
        worn.close_details(self.service,self.context)
        return False
    # ---- on the growth screen
    def side_tab(self,kind):
        row=only_word(text.read(None,self.frame(),SIDE_TABS,scale=2),(LABEL[kind],),.7)
        if row is None:return False
        self.service.click_hit(real_place(row));settle(self.service,self.context,1.5);return True
    def press_enhance(self,item,cap=None):
        """강화 until the goal, this turn's cap, or something stops it."""
        observer=EnhanceObserver(self.service,self.context,self.identity,item)
        guard=Guard(self.context,self.intents,observer.read_pair,fresh_seconds=FRESH_SECONDS)
        goal=self.goal(item);targets={item.key:goal}
        # A press left without a result: the level on this panel settles it.
        pending=self.intents.pending()
        if pending and pending['before'].slot==item.record:
            panel=read_panel(self.root,self.frame())
            if panel:
                item.values=dict(item.values or {},enhance=panel['level']);self.settle(item)
        end=time.monotonic()+ITEM_SECONDS;rereads=0;started=time.monotonic();first=(item.values or {}).get(ENHANCE)
        try:return self._enhance_loop(item,cap,observer,guard,goal,targets,end,rereads)
        finally:
            last=(observer.panel or {}).get('level')
            if type(last) is int:
                LOG.info('착용 %s 강화 머문 시간 %.0f초 · %s → %d',item.slot,time.monotonic()-started,first,last)
    def _enhance_loop(self,item,cap,observer,guard,goal,targets,end,rereads):
        def one(latest,mark_sent):
            frame=self.frame();panel=read_panel(self.root,frame)
            if not panel or not panel['active'] or panel['level']!=latest['second'].enhancement or panel['word']!=latest['button_name']:raise worn.ReadAgain()
            self.check();mark_sent();self.check();self.service.click_hit(panel['hit'])
        while time.monotonic()<end and time.monotonic()<self.deadline:
            self.check()
            try:status=guard.run_one(ENHANCE,targets,one)
            except worn.ReadAgain:status='hold_boundary_preinput'
            # The press's flash and the level's redraw can last a few seconds; ten looks span about ten.
            if status in ('hold_screen_unverified','hold_observation','hold_boundary_preinput') and rereads<10:
                rereads+=1;self.context.wait(.5);continue
            if status!='pending_confirmation':
                panel=observer.panel or {}
                if status=='hold_policy' and goal_state(goal,panel.get('level',-1))=='below':
                    # What the guard saw, so a lit button with enough material that still held can be told apart (10 >> 11, 10:21).
                    ages=[round(time.monotonic()-at,1) for at in (observer.looked_at or ())]
                    LOG.info('착용 %s 강화 불가 · 재료 부족 또는 버튼 꺼짐 · %s · 판독 %s · 판독 후 %s초',item.slot,panel.get('word'),
                             {k:v for k,v in panel.items() if k!='hit'},ages)
                    if panel.get('enough') is False:item.short=True
                elif status not in ('hold_policy',):
                    seen=read_panel(self.root,self.frame())
                    LOG.info('착용 %s 강화 중단 · %s · 판독 %s · 흔들린 값 %s',item.slot,status,{k:v for k,v in (seen or {}).items() if k!='hit'},observer.last_diff)
                item.done.add(ENHANCE);return
            rereads=0
            result='hold_result_unknown'
            for attempt in range(RESULT_READS):
                self.context.wait(.35)
                self.check()
                result=guard.reconcile(short_notice=lambda:coins_short(self.frame()))
                if result!='hold_result_unknown':break
            if result=='short_of_coins':raise CoinsShort()
            item.changed=True
            if result!='observed_progress':
                # The details decide it on the next read of this item.
                LOG.info('착용 %s 강화 결과 미확인 · 현재값으로 다시 판단',item.slot);return
            level=observer.panel['level'] if observer.panel else None
            if cap is not None and type(level) is int and level>=cap:return
    def press_once(self,item,kind):
        """One 돌파 or 각성, then back to the details for what it did: a stage that rose is success, the same stage is not."""
        if not self.side_tab(kind):
            LOG.info('착용 %s %s 탭 못 찾음',item.slot,LABEL[kind]);item.done.add(kind);return
        action=read_action(self.root,self.frame(),LABEL[kind])
        if action is None:
            LOG.info('착용 %s %s 대상 아님',item.slot,LABEL[kind]);item.done.add(kind);return
        # A blessing awakens on its own pieces; only an item picks a spare.
        if kind==AWAKEN and not item.blessing and action['enough'] is False and self.choose_material(item):
            action=read_action(self.root,self.frame(),LABEL[kind]) or action
        if not action['active']:
            LOG.info('착용 %s %s 불가 · 재료 부족 또는 버튼 꺼짐',item.slot,LABEL[kind]);item.done.add(kind);rest(self.adapter,item.slot,kind);return
        field={BREAK:'breakthrough',AWAKEN:'awakening'}[kind]
        def seen(sequence,stamp):
            return Observation(sequence,stamp,self.identity,'worn-slot:'+item.slot,item.record,item.key,item.values.get(ENHANCE),
                               item.values.get(BREAK) if kind==BREAK else None,item.values.get(AWAKEN) if kind==AWAKEN else None,None,
                               True if kind==BREAK else None,True if kind==AWAKEN else None)
        count=[0]
        def read_pair():
            stamps=[]
            for _ in range(2):
                now=read_action(self.root,self.frame(),LABEL[kind])
                if now is None or not now['active']:return {'screen_proof':False}
                stamps.append(time.monotonic());self.context.wait(.12)
            count[0]+=2
            return {'screen_proof':True,'first':seen(count[0]-1,stamps[0]),'second':seen(count[0],stamps[1]),'resource_mode':'native_active','active_pair_verified':True,
                    'action_mode':kind,'button_name':LABEL[kind],'opening':None,'item_icon':None}
        def one(latest,mark_sent):
            now=read_action(self.root,self.frame(),LABEL[kind])
            if now is None or not now['active']:raise worn.ReadAgain()
            self.check();mark_sent();self.check();self.service.click_hit(now['hit'])
        guard=Guard(self.context,self.intents,read_pair,fresh_seconds=FRESH_SECONDS)
        try:status=guard.run_one(kind,{item.key:self.goal(item)},one)
        except worn.ReadAgain:status='hold_boundary_preinput'
        if status!='pending_confirmation':
            LOG.info('착용 %s %s 안 누름 · %s',item.slot,LABEL[kind],status);item.done.add(kind);return
        LOG.info('착용 %s %s 입력 · 현재 %s',item.slot,LABEL[kind],item.values.get(kind))
        self.after_result(item,kind)
        item.changed=True
    def after_result(self,item,kind):
        """Watch for the short-of-coins message, then close whatever result window the press brought up."""
        end=time.monotonic()+RESULT_SECONDS;quiet=0
        while time.monotonic()<end:
            self.context.wait(.3);frame=self.frame()
            if coins_short(frame):
                self.intents.complete('short_of_coins');raise CoinsShort()
            if kind==BREAK and self.hold_needed(frame):
                # The user's way (11-06): 넘기기. Held down only when no 넘기기 reads.
                skip=next((row for box in SKIP_BOXES for row in text.read(None,frame,box,scale=2,minimum=.6) if '넘기기' in text.clean(row['text'])),None)
                if skip:
                    self.service.click_hit(real_place(skip));LOG.info('착용 %s 돌파 넘기기',item.slot);self.context.wait(1.5)
                else:self.hold_press(item)
                continue
            row=only_word(text.read(None,frame,RESULT_CLOSE,scale=2),('클릭하여닫기',),.7)
            if row:
                self.service.click_hit(real_place(row));settle(self.service,self.context,1);return
            # 각성 stays on its tab; 돌파 plays first, and the screen has no title while it does.
            if text.shows_title(frame,'성장') is True:
                quiet+=1
                if quiet>=(8 if kind==AWAKEN else 12):return
            else:quiet=0
    def hold_needed(self,frame):
        return any('길게' in text.clean(row['text']) or '눌러주세요' in text.clean(row['text'])
                   for row in text.read(None,frame,HOLD_WORDS,scale=2,minimum=.6))
    def hold_press(self,item):
        """The 돌파 button held down until its 길게 터치 prompt goes, at most HOLD_SECONDS. A click did nothing and the job
        waited out its 20 s, and the next job found the screen unknown (pc1 11-06 13:02)."""
        x,y,_=real_hit(*HOLD_BUTTON);started=time.monotonic();pressed=False
        with self.inputs.transaction():
            self.inputs.move(x,y);self.context.wait(.05)
            try:
                self.inputs.down('mouse','left');pressed=True
                while time.monotonic()-started<HOLD_SECONDS:
                    self.context.wait(.4)
                    if not self.hold_needed(self.service.capture()):break
            finally:
                if pressed:self.inputs.up('mouse','left')
        LOG.info('착용 %s 돌파 길게 누름 · %.1f초',item.slot,time.monotonic()-started)
        self.context.wait(1)
    def choose_material(self,item):
        """The list under an item on the 각성 tab holds it and the spares the game accepts: 강화되지 않은 동일한 장비. The next tile is one."""
        shown=list_count(self.frame())
        if shown is None:
            LOG.info('착용 %s 각성 재료 목록 수 미확인',item.slot);return False
        if shown<2:
            LOG.info('착용 %s 각성 재료 없음 · 동일 장비 없음',item.slot);rest(self.adapter,item.slot,AWAKEN);return False
        self.service.click_hit(real_hit(*SECOND_TILE));settle(self.service,self.context,1)
        return True
    # ---- the visit
    def work(self,item,cap=None):
        """This item's turn, already on its growth screen. True when something was pressed, so its details should be read again.
        What cannot run moves on to the item's next need on the same screen, with nothing read twice."""
        kind=item.pending_kind
        while kind:
            before=len(item.done)
            if kind==ENHANCE:self.press_enhance(item,cap)
            else:self.press_once(item,kind)
            if len(item.done)==before:return True
            kind=self.need(item)
        return False
    def visit(self,item,cap=None):
        """Grow what it lacks, then read its details again: that reading is what the program's table shows and what decides
        the next step, at the end of every turn, one ended by no coins included."""
        for _ in range(ROUNDS):
            if time.monotonic()>=self.deadline:return
            kind=self.need(item) if item.values else None
            if not kind or not self.enter(item):return
            item.pending_kind=kind;item.changed=False
            try:pressed=self.work(item,cap)
            except CoinsShort:
                if item.changed:self.read(item)
                raise
            finally:self.leave_growth()
            # Nothing done, nothing new to read: no materials go straight on to the next item.
            if item.changed:self.pressed=True;self.read(item)
            if not pressed or (kind==ENHANCE and cap is not None):return
    def gear(self):
        from owner_equipment_boxes import SLOTS
        # A part that could not be read rests (an empty slot at level 3 was tried twice a pass, 9 parts x 10 s, pc1
        # 22:47-22:50). A tile that did not open gets one more turn only when few did: pressing it twice in a row
        # could take the item off.
        items=[Item(slot,False) for slot in SLOTS if not resting(self.adapter,slot,READ)]
        for turn in range(2):
            pending=[item for item in items if not item.values]
            if turn and len(pending)>3:break
            for item in pending:
                self.check()
                if not self.from_table(item):self.read(item)
        known=[item for item in items if item.values and item.grade]
        missed=[item.slot for item in items if not item.values]
        for slot in missed:rest(self.adapter,slot,READ)
        if missed:LOG.info('착용 장비 현재값 못 읽음 · %d분 쉼 · %s',IDLE_MINUTES,', '.join(missed))
        # Stones are per grade: the lowest goes first and stops a little past the next lowest, so they spread.
        for grade in {item.grade for item in known}:
            group=[item for item in known if item.grade==grade]
            for _ in range(len(group)*20):
                self.check()
                if time.monotonic()>=self.deadline:return
                waiting=sorted((item for item in group if self.need(item)==ENHANCE),key=lambda item:item.values[ENHANCE])
                if not waiting:break
                chosen=waiting[0];others=[item.values[ENHANCE] for item in group if item is not chosen]
                before=chosen.values[ENHANCE]
                self.visit(chosen,min(others)+LEVEL_STEP if others else None)
                # Stones are per grade: one part short of them means the whole grade is (짱군네 11-07 09:03: all eleven
                # parts were visited, 8 s each, every one '재료 부족'). The grade rests until a change wakes it.
                if getattr(chosen,'short',False):
                    for item in group:item.done.add(ENHANCE);rest(self.adapter,item.slot,ENHANCE)
                    LOG.info('착용 %s 등급 강화 재료 부족 · 같은 등급 %d개 쉼',grade,len(group));break
                # A turn that raised nothing must not come round again: the lowest stayed the lowest, and one item was read every 7 s (pc2, 11-06).
                if chosen.values[ENHANCE]<=before:
                    chosen.done.add(ENHANCE)
                    LOG.info('착용 %s 강화 수치 그대로 · 이번 차례 제외',chosen.slot)
            for item in group:
                if self.need(item):self.visit(item)
    def blessings(self):
        # On the blessing screen, slot by slot. One that did not open gets one more turn after the others.
        items=[Item(slot,True) for slot in worn.BLESSING_SLOTS if not resting(self.adapter,slot,READ)]
        for turn in range(2):
            pending=[item for item in items if not item.values]
            if turn and len(pending)>2:break
            for item in pending:
                self.check()
                if time.monotonic()>=self.deadline:return
                if not self.from_table(item) and not self.read(item) and item is items[0] and turn==0:
                    # The blessing screen did not open at all (locked at level 3, pc1 22:51): no slot will.
                    for other in items:rest(self.adapter,other.slot,READ)
                    LOG.info('가호 화면 안 열림 · 가호 성장 %d분 쉼',IDLE_MINUTES);return
        missed=[item.slot for item in items if not item.values]
        for slot in missed:rest(self.adapter,slot,READ)
        if missed:LOG.info('착용 가호 현재값 못 읽음 · %d분 쉼 · %s',IDLE_MINUTES,', '.join(missed))
        for item in items:
            self.check()
            if time.monotonic()>=self.deadline:return
            if item.values and self.need(item):self.visit(item)
    def from_table(self,item):
        """A part read within TABLE_SECONDS is not opened again (user 11-06: read only what changed)."""
        from owner_growth_current import recent_reading
        try:found=recent_reading(self.root,self.profile,item.slot,TABLE_SECONDS)
        except Exception:return False
        if not found or found[0] not in ('일반','희귀','영웅','전설'):return False
        # The values only change by a press here (its screen reads the real level before the next press) or a swap
        # (which drops the reading), so a fresh reading decides without opening the part (짱군네 11-07 09:02: eleven
        # parts reopened, 70 s, before eleven presses that could not run).
        item.grade,item.values=found
        return True
    def to_field(self):
        self.leave_growth();worn.leave_blessing_screen(self.service,self.context)
        worn.close_bag(self.service,self.context)


def growth_switches(root):
    """The saved growth switches (기능 사용) for gear and blessings. A TEST or a timed job sees only its own switch in
    adapter.values, so the saved file decides here."""
    import json
    try:values=json.loads((Path(root)/'settings/auto-settings.json').read_text(encoding='utf-8-sig')).get('values',{})
    except (OSError,ValueError,AttributeError):return {'gear':False,'blessing':False}
    return {'gear':values.get('auto_growth.equipment.enabled') is True,'blessing':values.get('auto_growth.blessing.enabled') is True}


def grow(adapter,context,inputs,slots):
    """Right after a higher-grade swap: the new item grows to its goals by this same route, at once (user, 11-06).
    Only where growth is switched on for its kind and its grade's goals are ticked. Spends as ordinary growth does."""
    from project_adapter.town_services import TownServices
    from project_adapter import market_inventory
    from owner_hunt_rules_candidate import configured_identity
    from owner_progression import state
    root=adapter.project.root;switches=growth_switches(root)
    items=[Item(slot,slot in worn.BLESSING_SLOTS) for slot in slots]
    items=[item for item in items if switches['blessing' if item.blessing else 'gear']]
    if not items:
        LOG.info('교체 장비 바로 성장 생략 · 성장 기능 사용 꺼짐 · %s',', '.join(slots));return False
    service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES)
    if getattr(service.capture(),'hi',None) is None:return False
    identity=configured_identity(root)
    document,revision=Store(root,identity).snapshot()
    if revision=='missing':return False
    route=Route(adapter,context,inputs,service,identity,identity,state(adapter).character,document)
    old=route.intents.pending()
    if old and old.get('phase')=='prepared':route.intents.abort_prepared('이전 입력 전 기록');old=None
    if old and not str(old['before'].slot).startswith('worn:'):route.intents.close_absent('인벤토리 경로로 전환 · 현재값으로 다시 판단')
    try:
        for item in items:
            route.check()
            if not route.read(item) or not item.values:
                LOG.info('교체 장비 바로 성장 · %s 현재값 못 읽음',item.slot);continue
            LOG.info('교체 장비 바로 성장 · %s · %s · 다음 %s',item.slot,item.grade,LABEL.get(route.need(item),'목표 도달 또는 목표 꺼짐'))
            if route.need(item):route.visit(item)
    except CoinsShort:
        LOG.info('성장 재화 부족 · 교체 장비 성장 종료')
    finally:
        context.checkpoint()
        if worn.popup(service.capture()):service.click_hit(real_hit(*worn.REAL_CLOSE));context.wait(.8)
        route.to_field()
    return True


def run(adapter,context,inputs):
    """Worn gear and blessing growth from the field. True when this route handled them; the old list route then stands aside."""
    from project_adapter.town_services import TownServices
    from project_adapter import market_inventory
    from owner_hunt_rules_candidate import configured_identity
    from owner_progression import state
    equipment=adapter.values.get('auto_growth.equipment.enabled') is True
    blessing=adapter.values.get('auto_growth.blessing.enabled') is True
    if not equipment and not blessing:return False
    service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES)
    if getattr(service.capture(),'hi',None) is None:return False
    root=adapter.project.root;identity=configured_identity(root)
    document,revision=Store(root,identity).snapshot()
    if revision=='missing':return False
    adapter._owner_worn_growth_context=context
    if idle_skip(adapter,revision):
        LOG.info('착용 장비·가호 성장 · 지난 확인에서 할 일 없음 · %d분 안 다시 읽지 않음',IDLE_MINUTES);return True
    route=Route(adapter,context,inputs,service,identity,identity,state(adapter).character,document)
    route.pressed=False;coins=False
    old=route.intents.pending()
    if old and old.get('phase')=='prepared':route.intents.abort_prepared('이전 입력 전 기록');old=None
    if old and not str(old['before'].slot).startswith('worn:'):
        # From the list route, which no longer runs here. The details read below decide what is next.
        route.intents.close_absent('인벤토리 경로로 전환 · 현재값으로 다시 판단')
    try:
        if equipment:route.gear()
        if blessing:route.blessings()
    except CoinsShort:
        LOG.info('성장 재화 부족 · 이번 차례 종료');coins=True
    finally:
        context.checkpoint()
        if worn.popup(service.capture()):service.click_hit(real_hit(*worn.REAL_CLOSE));context.wait(.8)
        route.to_field()
    # A pass that pressed nothing (goals met, no materials) or ran out of coins rests IDLE_MINUTES (pc1 15:03 and 15:11:
    # all 14 parts read twice in eight minutes with nothing to do).
    store=Rests(adapter)
    store.data['idle']=[time.time()+IDLE_MINUTES*60,revision] if (coins or not getattr(route,'pressed',False)) else None
    store.save()
    return True


IDLE_MINUTES=180
TABLE_SECONDS=6*3600
AWAKEN_HOURS=24
# Rests are kept on disk per character and end on a change, not on the clock alone (user 11-06: growth must take far
# less time). A pass that changed nothing took 5-6 minutes every 20 minutes and after every restart (pc1 17:58,
# 18:22, 18:44): each part's details were read again and each 각성 was tried again for '동일 장비 없음'.
# wake() ends them: a death, a swap, the bag's red dot, a new character. A 각성 rest ends only when the bag's gear
# changes (wake_awaken from the higher-grade check).


class Rests:
    def __init__(self,adapter):
        import json
        self.adapter=adapter;self.path=getattr(adapter,'_owner_worn_rest_path',None)
        cached=getattr(adapter,'_owner_worn_rests',None)
        if cached is not None:self.data=cached;return
        self.data={'idle':None,'short':{}}
        try:adapter._owner_worn_rests=self.data
        except AttributeError:pass
        try:
            from owner_hunt_rules_candidate import configured_identity
            import hashlib
            ident=hashlib.sha256(str(configured_identity(adapter.project.root)).encode('utf-8')).hexdigest()[:24]
            self.path=Path(adapter.project.root)/'settings'/('owner-worn-rest-'+ident+'.json');adapter._owner_worn_rest_path=self.path
            loaded=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(loaded,dict):self.data.update(loaded)
        except (OSError,ValueError,TypeError,AttributeError):pass
        if not isinstance(self.data.get('short'),dict):self.data['short']={}
    def save(self):
        import json
        if self.path is None:return
        try:self.path.write_text(json.dumps(self.data,ensure_ascii=False),encoding='utf-8')
        except OSError:pass


def rest(adapter,slot,kind):
    """A step that could not run for want of materials or coins waits for a change: IDLE_MINUTES at most, a 각성 with
    no spare of the same item until the bag's gear changes (AWAKEN_HOURS at most)."""
    store=Rests(adapter)
    store.data['short'][slot+'|'+kind]=time.time()+(AWAKEN_HOURS*3600 if kind==AWAKEN else IDLE_MINUTES*60)
    store.save()


def resting(adapter,slot,kind):
    return time.time()<Rests(adapter).data['short'].get(slot+'|'+kind,0)


def idle_skip(adapter,revision):
    """Within the rest after an idle pass, with the same saved goals. A swap or a death clears the rest."""
    idle=Rests(adapter).data.get('idle')
    return bool(idle and time.time()<idle[0] and idle[1]==revision)


def wake(adapter):
    """Something may have changed (a new item, a death, new materials): the next pass reads again. A 각성 rest stays
    unless the bag's gear changed."""
    store=Rests(adapter);store.data['idle']=None
    store.data['short']={k:v for k,v in store.data['short'].items() if k.endswith('|'+AWAKEN)}
    store.save()


def wake_awaken(adapter):
    store=Rests(adapter);store.data['idle']=None;store.data['short']={};store.save()
