"""Higher grade first, at 1366x768: a spare of a higher grade than the worn one takes its place, for the steps the user ticked
(일반 → 희귀, 희귀 → 영웅). Gear and blessings each have their own switch and their own time in the timetable.

The grade decides, not the stats: an unenhanced 영웅 can show less 전투력 than a worn +50 희귀, and the game's green arrow
and the 전투력 rise are then missing (user, 11-06).
Gear: a tile coloured above 일반 (blue 희귀, purple 영웅) in the bag's equipment list is opened; the comparison window
names both grades. Blessings: every spare of a slot (all but its first tile, the worn one) is opened.

Each tile is clicked once and its window closed with X before the next: a second click on a selected tile equips it.
Nothing is spent. Equipping is pressed only with both grades read and the step ticked.
"""
import logging,re,time
import numpy as np
import owner_hd as hd
import owner_text as text
import owner_worn_stats as worn
import owner_blessing_bound as bound

LOG=logging.getLogger('project_gui.DKB')
ORDER=('일반','희귀','영웅','전설')
# One switch (user, 11-06, after a 전설 appeared): any higher grade goes on. The old per-step ticks still turn it on.
CHOICES=('higher',)
LEGACY=('normal_to_rare','rare_to_hero')
GEAR_KEY='owner_equip.gear.enabled';BLESSING_KEY='owner_equip.blessing.enabled'
# Real pixels, 1366x768 (pc1 11-06 photographs).
BAG_FILTER=(1335,215)                                   # the bag's equipment list (25 on pc1)
BAG_X=(1097,1157,1217,1277);BAG_Y=tuple(177+60*row for row in range(10))
LEFT_GRADE=(445,200,110,45);RIGHT_GRADE=(695,200,110,45)  # worn on the left, the clicked spare on the right
LEFT_TITLE=(435,155,215,32)                               # the worn one's name (토끼 가호 장식5) on the left
RIGHT_BUTTONS=(690,560,230,46);RIGHT_PART=(830,200,95,40)  # 귀걸이 at (884,219)
POWER_ROW=(695,338,225,20)                                # 전투력 6,334 1,965▲ on the spare's window
TOAST=(560,572,240,36)                                    # 전투력 +1955▲ after an equip
TILE_SPREAD=20
MAX_ACQUIRE=4                                             # blessings made on one slot tab per run
# The bag's sorted view (▼ON) puts 무기 · 방어구 · 장신구 headings between rows, so the fixed grid lands on headings and
# gaps: pc2's TEST never reached its rare fan and three tiles 'did not open' (11-06). The view goes to OFF for the work
# and back after.
GROUPING=(1300,112,66,34);GROUPING_HIT=(1337,129)                                            # an empty place is flat; an item's tile varies by 40 or more


def allowed(worn_grade,new_grade,choice):
    """True when the switch is on and new_grade is above worn_grade."""
    if choice.get('higher') is not True or worn_grade not in ORDER or new_grade not in ORDER:return False
    return ORDER.index(new_grade)>ORDER.index(worn_grade)


def blessing_better(left,right,left_kind,right_kind,choice,priorities):
    """A blessing goes on when its grade is higher, or the grade is the same and its pattern stands higher in the user's
    같은 등급 문양 순위 (나비 first: every slot should end up 나비, user 11-06). A lower grade never."""
    if choice.get('higher') is not True or left not in ORDER or right not in ORDER:return False
    if ORDER.index(right)!=ORDER.index(left):return ORDER.index(right)>ORDER.index(left)
    rank=lambda kind:len(priorities)-list(priorities).index(kind) if kind in priorities else 0
    return right_kind is not None and rank(right_kind)>rank(left_kind)


def grade(real,box):
    x,y,w,h=box
    found={text.clean(row['text']) for row in text.read_area(None,real[y:y+h,x:x+w],scale=2,minimum=.6)}&set(ORDER)
    return found.pop() if len(found)==1 else None


def above_common(real,place):
    """A tile coloured above 일반: its corners blue (희귀) or purple (영웅). pc1 11-06: 희귀 corners ran (47,64,78) to
    (51,102,139), even (50,58,68) low in the list; 일반 (81,76,69) and (61,57,52); an empty place (52,47,45).
    Only a filter on what to open: the window's grade word decides."""
    x,y=place;tile=real[y-24:y+24,x-24:x+24].astype(np.float32)
    if tile.std()<TILE_SPREAD:return False
    corners=[real[y+dy:y+dy+5,x+dx:x+dx+5].reshape(-1,3).mean(0) for dx,dy in ((-24,-24),(19,-24),(-24,19),(19,19))]
    r,g,b=np.median(np.array(corners,np.float32),0)
    return bool(b>=r+10 or (r>g+10 and b>g+10))


def candidates(real):
    return [(x,y) for y in BAG_Y for x in BAG_X if above_common(real,(x,y))]


def signature(real,place):
    """A tile's look, the same wherever the list puts it: the middle (the icon), coarse, and its grade colour. The list
    darkens downward, and the whole tile's look changed with its row, so a re-sorted bag opened every item again (pc1 05:00)."""
    x,y=place;middle=real[y-10:y+10,x-10:x+10].astype(np.float32)
    return (above_common(real,place),)+tuple((middle.reshape(4,5,4,5,3).mean(axis=(1,3))//40).astype(int).ravel())


def seen_before(adapter,kind,fingerprint):
    """The list looks as it did when the last full check found nothing to swap."""
    return (getattr(adapter,'_owner_equip_unchanged',None) or {}).get(kind)==fingerprint


def remember(adapter,kind,fingerprint):
    store=getattr(adapter,'_owner_equip_unchanged',None)
    if store is None:store={};adapter._owner_equip_unchanged=store
    if fingerprint is None:store.pop(kind,None)
    else:store[kind]=fingerprint


def open_compare(service,context,place):
    """Click a tile once; the window kind, or None when nothing opened."""
    bound.wait_closed(service,context)
    context.checkpoint();service.check()
    service.click_hit(hd.real_hit(*place))
    for look in range(worn.OPEN_LOOKS):
        context.wait(.2);context.checkpoint();service.check()
        frame=service.capture();kind=bound.window_kind(frame)
        if kind:context.wait(.4);return kind
        # A blessing not made yet opens 가호를 획득하시겠습니까? instead; no need to wait the rest out.
        if look%3==2 and bound.acquire_popup(frame) is not None:return None
    return None


def press_equip(service,context):
    real=np.asarray(service.capture().hi);x,y,w,h=RIGHT_BUTTONS
    button=[row for row in text.read_area(None,real[y:y+h,x:x+w],left=x,top=y,scale=2,minimum=.6) if text.clean(row['text'])=='장착']
    if len(button)!=1:return False
    context.checkpoint();service.check()
    service.click_hit(hd.real_hit(round(button[0]['rx']),round(button[0]['ry'])))
    return True


def compare(service,context,choice):
    """Read the open comparison. (worn grade, spare grade, title, None to equip or why not)."""
    real=np.asarray(service.capture().hi)
    left,right=grade(real,LEFT_GRADE),grade(real,RIGHT_GRADE)
    title=bound.window_title(service.capture(),'compare')
    return left,right,title,(None if allowed(left,right,choice) else '등급 조건 아님')


def spare_power(service):
    """The spare's own 전투력 on its window (6,334 in 전투력 6,334 1,965▲), or None."""
    real=np.asarray(service.capture().hi);x,y,w,h=POWER_ROW
    words=[str(row['text']).strip() for row in text.read_area(None,real[y:y+h,x:x+w],left=x,top=y,scale=2,minimum=.6)]
    numbers=[int(word.replace(',','')) for word in words if re.fullmatch(r'\d{1,3}(?:,\d{3})+|\d{1,6}',word)]
    return numbers[0] if numbers and any('전투력' in text.clean(word) for word in words) else None


def best(found,key):
    """The best candidate per slot, by key."""
    chosen={}
    for row in found:
        if row['slot'] not in chosen or key(row)>key(chosen[row['slot']]):chosen[row['slot']]=row
    return list(chosen.values())


def equip_chosen(service,context,row):
    """Open the chosen tile again, check it is the same spare, and press 장착. The window's own words decide."""
    kind=open_compare(service,context,row['place'])
    if kind!='compare':
        if kind:bound.close_window(service,context,kind)
        return '비교창 아님'
    left,right,title,_=compare(service,context,{key:True for key in CHOICES})
    # The name's digit and marks read differently between looks (나비가호장식 / 나비가호장식], 11:22): letters only.
    same=lambda t:re.sub(r'[\d\]\[|lI()]','',t or '')
    if (left,right,same(title))!=(row['worn'],row['spare'],same(row['title'])):
        bound.close_window(service,context,'compare');return '다시 연 창이 다름 · %s %s'%(title,right)
    if not press_equip(service,context):
        bound.close_window(service,context,'compare');return '장착 버튼 미확인'
    return None


def scan_gear(service,context,choice):
    """Every candidate tile once, closed again: the allowed spares with their slot and 전투력, and how many went unread."""
    context.checkpoint();service.check();real=np.asarray(service.capture().hi)
    found=[];unread=0;seen=set()
    for place in candidates(real):
        mark=signature(real,place)
        if mark in seen:continue  # a second copy of one item answers the same
        seen.add(mark)
        kind=open_compare(service,context,place)
        if kind!='compare':
            # A worn item opens its own window alone: nothing to compare.
            if kind:bound.close_window(service,context,kind)
            else:LOG.info('장비 높은 등급 장착 · 상세창 안 열림');unread+=1
            continue
        left,right,title,reason=compare(service,context,choice)
        if reason:
            unread+=left is None or right is None
            LOG.info('장비 높은 등급 장착 안 함 · %s · 착용 %s · %s %s',reason,left or '미확인',title or '제목 미확인',right or '미확인')
        else:
            row=dict(place=place,slot=part_slot(read_part(service),title),worn=left,spare=right,title=title,power=spare_power(service))
            LOG.info('장비 높은 등급 후보 · %s · %s → %s · %s · 전투력 %s',row['slot'] or '부위 미확인',left,right,title,row['power'] or '미확인')
            if row['slot']:found.append(row)
            else:unread+=1
        bound.close_window(service,context,'compare')
    return found,unread


def grouping(service):
    """True when the bag's sorted view is on, False when off, None when its word does not read."""
    real=np.asarray(service.capture().hi);x,y,w,h=GROUPING
    found=''.join(text.clean(row['text']).upper() for row in text.read_area(None,real[y:y+h,x:x+w],scale=3,minimum=.5))
    if 'OFF' in found:return False
    if 'ON' in found:return True
    return None


def plain_grid(service,context):
    """Turn the sorted view off. True when it was on (so it goes back on after), False when already off, None unread."""
    state=grouping(service)
    if state is not True:return state if state is False else None
    service.click_hit(hd.real_hit(*GROUPING_HIT));context.wait(1.2)
    return True if grouping(service) is False else None


def restore_grouping(service,context,changed):
    if changed is True and grouping(service) is False:
        service.click_hit(hd.real_hit(*GROUPING_HIT));context.wait(.8)


def gear(adapter,service,context,choice):
    """Swap worn gear for the best spare of an allowed higher grade, part by part: the highest grade, then the most 전투력.
    Every candidate is read before any press, so a +0 spare never wins over a better one further down the bag."""
    from owner_progression import open_inventory_by_key,inventory_parts
    swaps=[];unread=0
    if open_inventory_by_key(service) is False or inventory_parts(service.capture())[1] is not True:
        LOG.info('장비 높은 등급 장착 생략 · 가방 안 열림');return swaps
    service.click_hit(hd.real_hit(*BAG_FILTER));context.wait(1.2)
    changed=plain_grid(service,context)
    if changed is None:
        LOG.info('장비 높은 등급 장착 생략 · 가방 정렬 보기 상태 미확인');return swaps
    try:return gear_grid(adapter,service,context,choice,swaps)
    finally:restore_grouping(service,context,changed)


def gear_grid(adapter,service,context,choice,swaps):
    unread=0
    real=np.asarray(service.capture().hi)
    if all(real[y-24:y+24,x-24:x+24].std()>=TILE_SPREAD for x in BAG_X for y in BAG_Y[-1:]):
        LOG.info('장비 높은 등급 장착 · 장비 목록이 한 화면을 넘을 수 있음 · 보이는 칸만 확인')
    fingerprint=tuple(signature(real,(x,y)) for y in BAG_Y for x in BAG_X if real[y-24:y+24,x-24:x+24].std()>=TILE_SPREAD)
    if seen_before(adapter,'gear',(fingerprint,tuple(sorted(choice.items())))):
        LOG.info('장비 높은 등급 장착 · 가방 장비 지난 확인과 같음 · 칸 열지 않음');return swaps
    LOG.info('장비 높은 등급 장착 · 후보 칸 %d개',len(candidates(real)))
    done=set()
    for _ in range(len(worn.PART_WORDS)+2):
        found,missed=scan_gear(service,context,choice);unread+=missed
        chosen=[row for row in best(found,lambda r:(ORDER.index(r['spare']),r['power'] or -1)) if row['slot'] not in done]
        if not chosen:break
        row=chosen[0];done.add(row['slot'])
        why=equip_chosen(service,context,row)
        if why:
            LOG.info('장비 높은 등급 장착 안 함 · %s · %s',why,row['title']);unread+=1;continue
        risen=watch_power(service,context)
        if bound.window_kind(service.capture()):bound.close_window(service,context,bound.window_kind(service.capture()))
        LOG.info('장비 높은 등급 장착 %s · %s · %s → %s · %s · %s',
                 '완료' if risen else '결과 미확인',row['slot'],row['worn'],row['spare'],row['title'],risen or '전투력 표시 없음')
        swaps.append((row['slot'],row['title'],row['worn'],row['spare'],bool(risen)))
        mark_stale(adapter,row['slot'])
    # Only a full check with every window read may let the next one skip an unchanged bag.
    remember(adapter,'gear',None if swaps or unread else (fingerprint,tuple(sorted(choice.items()))))
    return swaps


def watch_power(service,context,seconds=3.0):
    """The 전투력 +N▲ notice after an equip, read as it is."""
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        context.wait(.25);context.checkpoint();service.check()
        real=np.asarray(service.capture().hi);x,y,w,h=TOAST
        words=[text.clean(row['text']) for row in text.read_area(None,real[y:y+h,x:x+w],scale=2,minimum=.5)]
        if not any('전투력' in word for word in words):continue
        # The number from the cleaned digits: as it stands, +3,771 read +371 (pc2 06:59).
        digits=[re.sub(r'[^\d]','',str(row['text'])) for row in text.read_digits(None,real[y:y+h,x+110:x+w])]
        digits=[value for value in digits if value]
        if len(digits)==1:return '전투력 +'+digits[0]
        rise=[word for word in words if word.startswith('+')]
        if rise:return '전투력 '+rise[0]
    return None


def part_slot(words,title):
    """The worn slot a spare goes to: its part word (귀걸이, 각반 …), else the title's; a weapon's word is none of these."""
    for slot,word in worn.PART_WORDS.items():
        if word in words or word in (title or ''):return slot
    return '무기' if words else None


def read_part(service):
    real=np.asarray(service.capture().hi);x,y,w,h=RIGHT_PART
    return [text.clean(row['text']) for row in text.read_area(None,real[y:y+h,x:x+w],scale=2,minimum=.6)]


def mark_stale(adapter,slot):
    """The worn table's row for this part is old now; the growth read right after refreshes it."""
    try:
        from owner_growth_current import invalidate_item
        from owner_hunt_rules_candidate import configured_identity
        if slot:invalidate_item(adapter.project.root,configured_identity(adapter.project.root),'worn-slot:'+slot)
    except Exception as exc:LOG.info('착용 표 갱신 보류 · %s',type(exc).__name__)


def bound_title(service,box):
    real=np.asarray(service.capture().hi);x,y,w,h=box
    return ''.join(text.clean(row['text']) for row in text.read_area(None,real[y:y+h,x:x+w],minimum=.5))


def tile_plus(service,place):
    """The +43 on a blessing tile, or 0 when none reads."""
    real=np.asarray(service.capture().hi);x,y=place
    # +43 read as +4 in one crop (pc1 05:41). On pc1's blessing list this crop read +43, 30, +20, +14 and 10, all right;
    # the others are tried after it.
    for top,bottom,left,right in ((4,26,-2,30),(2,28,-6,28),(6,26,0,28)):
        words=[text.clean(row['text']) for row in text.read_area(None,real[y+top:y+bottom,x+left:x+right],language='number',scale=3,minimum=.6)]
        numbers=[int(found) for word in words for found in re.findall(r'\d{1,3}',word)]
        if len(numbers)==1:return numbers[0]
    return 0


def blessings(adapter,service,context,choice,priorities=()):
    """For each slot 1~5 every spare is read first; the best allowed one is equipped: the highest grade, then the user's
    문양 순위, then the highest +. So a +43 도깨비 is never passed over for a +0 spare of the same grade."""
    swaps=[];unread=0
    if not worn.open_blessing_screen(service,context):
        LOG.info('가호 높은 등급 장착 생략 · 가호 화면 안 열림');return swaps
    service.click_hit(hd.real_hit(*bound.ALL_TAB));context.wait(1.2)
    real=np.asarray(service.capture().hi);count=bound.tile_count(service.capture())
    fingerprint=(tuple(signature(real,place) for place in bound.places(count)),tuple(sorted(choice.items())))
    if seen_before(adapter,'blessing',fingerprint):
        LOG.info('가호 높은 등급 장착 · 가호 목록 지난 확인과 같음 · 칸 열지 않음');return swaps
    rank=lambda kind:-(list(priorities).index(kind)) if kind in priorities else -len(priorities)-1
    for slot in (1,2,3,4,5):
        acquired=0
        for _ in range(3+MAX_ACQUIRE):
            context.checkpoint();service.check()
            service.click_hit(hd.real_hit(worn.REAL_FILTER_X,worn.REAL_FILTER_Y[slot]));context.wait(1.2)
            count=bound.tile_count(service.capture())
            if count>=len(bound.TILE_X)*len(bound.TILE_Y):
                LOG.info('가호%d 높은 등급 장착 생략 · 목록이 한 화면을 넘을 수 있음',slot);break
            found=[];made=False
            for place in bound.places(count)[1:]:
                plus=tile_plus(service,place)
                kind=open_compare(service,context,place)
                if kind!='compare':
                    if kind:bound.close_window(service,context,kind)
                    elif bound.acquire_popup(service.capture()) is not None:
                        # Not made yet. With no tradeable piece it is made here (user 11-06) and the slot read again,
                        # since the list moves; else it is left with 취소.
                        tradeable=bound.acquire_popup(service.capture())
                        if tradeable==0 and acquired<MAX_ACQUIRE and bound.press_acquire(service,context):
                            acquired+=1;made=True;LOG.info('가호%d 획득 · 거래 가능 조각 0개',slot);context.wait(1.2)
                            if bound.window_kind(service.capture()):bound.close_window(service,context,bound.window_kind(service.capture()))
                            break
                        bound.close_acquire(service,context)
                        LOG.info('가호%d 획득 안 함 · 거래 가능 조각 %s',slot,tradeable if tradeable is not None and tradeable>=0 else '미확인')
                    else:unread+=1
                    continue
                left,right,title,_=compare(service,context,choice)
                worn_title=bound_title(service,LEFT_TITLE)
                left_kind,right_kind=worn.blessing_kind(worn_title or ''),worn.blessing_kind(title or '')
                if not blessing_better(left,right,left_kind,right_kind,choice,priorities):
                    unread+=left is None or right is None
                    LOG.info('가호%d 장착 안 함 · 착용 %s %s · 예비 %s %s',slot,left_kind or '미확인',left or '미확인',right_kind or title or '미확인',right or '미확인')
                else:
                    found.append(dict(place=place,slot='가호%d'%slot,worn=left,spare=right,title=title,kind=right_kind,plus=plus))
                    LOG.info('가호%d 장착 후보 · %s %s → %s %s · +%d',slot,left_kind,left,right_kind,right,plus)
                bound.close_window(service,context,'compare')
            if made:continue
            if not found:break
            row=max(found,key=lambda r:(ORDER.index(r['spare']),rank(r['kind']),r['plus']))
            before=np.asarray(service.capture().hi)[128:176,1068:1116].astype(int)
            why=equip_chosen(service,context,row)
            if why:
                LOG.info('가호%d 높은 등급 장착 안 함 · %s · %s',slot,why,row['title']);unread+=1;break
            context.wait(1.2)
            if bound.window_kind(service.capture()):bound.close_window(service,context,bound.window_kind(service.capture()))
            after=np.asarray(service.capture().hi)[128:176,1068:1116].astype(int)
            changed=float(np.abs(after-before).mean())>12
            LOG.info('가호%d 높은 등급 장착 %s · %s → %s · %s · +%d',slot,'완료' if changed else '결과 미확인',row['worn'],row['spare'],row['title'],row['plus'])
            swaps.append((row['slot'],row['title'],row['worn'],row['spare'],changed))
            # The best was chosen from every spare, so this slot needs no second look (user: too many repeats).
            break
    remember(adapter,'blessing',None if swaps or unread else fingerprint)
    return swaps


def run(adapter,context,inputs,kind,choice=None):
    """kind 'gear' or 'blessing'. A short result for the log and TEST. Only at 1366x768."""
    from project_adapter.town_services import TownServices
    from project_adapter import market_inventory
    service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES);service.context=context
    if getattr(service.capture(),'hi',None) is None:return '보류 · 1366x768 화면이 아님'
    if choice is None:choice=settings(adapter.project.root,kind)
    if choice.get('higher') is not True:return '보류 · 높은 등급 우선 장착 꺼짐'
    label='장비' if kind=='gear' else '가호'
    LOG.info('%s 높은 등급 장착 시작',label)
    from owner_progression import inventory_parts
    initially_open=inventory_parts(service.capture())==(True,True)
    try:
        if kind=='blessing':
            # 일괄 획득 first, so blessings made from pieces are owned before any swap (user, 11-06).
            bound.claim(adapter,context,inputs,leave=False)   # the swaps go on from the same screen
        swaps=gear(adapter,service,context,choice) if kind=='gear' else blessings(adapter,service,context,choice,priorities(adapter.project.root))
    finally:
        context.checkpoint();service.check()
        kind_open=bound.window_kind(service.capture())
        if kind_open:bound.close_window(service,context,kind_open)
        worn.leave_blessing_screen(service,context)
        if not initially_open:worn.close_bag(service,context)
    done=[row for row in swaps if row[-1]]
    grown=[row[0] for row in swaps if row[0]]
    if grown:
        # The new item grows at once, to the saved goals of its grade (user, 11-06).
        from owner_worn_growth import grow
        grow(adapter,context,inputs,list(dict.fromkeys(grown)))
    return '%s 교체 %d개'%(label,len(done))+(' · 결과 미확인 %d개'%(len(swaps)-len(done)) if len(swaps)!=len(done) else '') if swaps else '교체할 %s 없음'%label


def settings(root,kind):
    """The ticked steps for gear or blessings from the character's growth settings."""
    from owner_gear_settings_candidate import Store
    from owner_hunt_rules_candidate import configured_identity
    try:document=Store(root,configured_identity(root)).read()
    except (OSError,ValueError,TypeError):return {}
    section=document.get('gear_equip' if kind=='gear' else 'blessing_equip',{})
    return {'higher':section.get('higher') is True or any(section.get(key) is True for key in LEGACY)}


def priorities(root):
    """The user's 같은 등급 문양 순위 (도깨비, 토끼 …), best first."""
    from owner_gear_settings_candidate import Store
    from owner_hunt_rules_candidate import configured_identity
    try:return tuple(Store(root,configured_identity(root)).read()['blessing_equip'].get('priorities') or ())
    except (OSError,ValueError,TypeError,KeyError):return ()


def enabled(root,kind):
    return any(settings(root,kind).values())
