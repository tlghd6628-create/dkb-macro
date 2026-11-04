"""Only missing equipment can authorize searching its starter box."""
from functools import lru_cache,wraps
from pathlib import Path
import logging,time
LOG=logging.getLogger('project_gui.DKB')
SLOTS={'무기':(17,211,26,27),'반지':(160,241,23,22),'팔찌':(160,211,23,22),
 '목걸이':(159,149,26,26),'귀걸이':(158,180,25,25),
 '갑옷':(17,183,24,25),'다리':(126,210,26,27),'신발':(126,239,26,26),
 '장갑':(126,179,26,27),'투구':(17,152,25,26),'허리띠':(127,149,25,25)}
WEAPON='버튼_인벤토리_희귀무기상자';ARMOR='버튼_인벤토리_희귀방어구상자';ACCESSORY='버튼_희귀_장신구상자'
ARMOR_PARTS=('갑옷','다리','신발','장갑','투구','허리띠')

@lru_cache(maxsize=2)
def _weapon_grade_detector(profile):
    from roi_runtime import RoiDetector
    detector=RoiDetector(Path(profile),['체크_인벤토리_갑옷'])
    # Reuse the native upper-tile colour classifier at the authored weapon
    # location. This private detector never changes the native armour crops.
    detector.entries['체크_인벤토리_갑옷'].update(dict(zip(('x','y','w','h'),SLOTS['무기'])))
    return detector

def paired_rare_weapon(profile,first,second):
    from owner_progression import inventory_parts
    from project_adapter import market_inventory as native
    if inventory_parts(first)!=(True,True) or inventory_parts(second)!=(True,True):return None
    detector=_weapon_grade_detector(str(profile))
    values=[native.inspect_equipment_grades(detector,frame,parts=('갑옷',)).get('갑옷',{}).get('grade') for frame in (first,second)]
    if values==['희귀 이상','희귀 이상']:return True
    if values==['일반','일반']:return False
    return None

@lru_cache(maxsize=1)
def badge():
    from PIL import Image
    import numpy as np
    return [np.asarray(Image.open(path).convert('RGB')) for path in sorted((Path(__file__).parent/'assets').glob('equipped_badge_*.png'))]

def inspect(frame):
    """True=worn E mark, False=proved blank badge corner, None=uncertain."""
    from owner_progression import inventory_parts
    import cv2,numpy as np
    if inventory_parts(frame)!=(True,True):return dict.fromkeys(SLOTS)
    answer={};needles=badge()
    if not needles:return dict.fromkeys(SLOTS)
    for part,(x,y,w,h) in SLOTS.items():
        patch=frame[y-3:y+12,x+w-11:x+w+5]
        score=max(float(cv2.minMaxLoc(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED))[1]) for needle in needles)
        if score>=.94:answer[part]=True
        # Real level-1 blanks measure score .46-.53, std 8-16, mean 32-42; worn slots score .99, std 50+.
        elif score<.60 and float(np.max(patch.std(axis=(0,1))))<20 and float(patch.mean())<100:answer[part]=False
        else:answer[part]=None
    return answer

def agree(first,second):
    a,b=inspect(first),inspect(second)
    return {part:a[part] if a[part] is b[part] else None for part in SLOTS}

def plan(worn,level=None,rare_weapon=None):
    items=[]
    # The coupon rare fan is a level-30 task; unknown level never opens it.
    if (worn.get('무기') is False or (worn.get('무기') is True and rare_weapon is False)) and type(level) is int and level>=30:items.append(WEAPON)
    armor=[p for p in ARMOR_PARTS if worn.get(p) is False]
    accessories=[p for p in ('팔찌','반지','목걸이','귀걸이') if worn.get(p) is False]
    if armor:items.append(ARMOR)
    if accessories:items.append(ACCESSORY)
    return items,armor,accessories

def close_inventory(service):
    from owner_progression import inventory_parts
    service.check()
    if inventory_parts(service.capture())==(True,True):
        service.key(0x49);service.context.wait(.15)
    left,right=inventory_parts(service.capture())
    if left:service.click_hit((184,17,(178,10,191,24)));service.context.wait(.1)
    if right:service.click_hit((883,54,(877,48,890,61)));service.context.wait(.1)

def energy_after_inventory(adapter,context,inputs,skip_before):
    """Reuse only a genuinely admitted, completed native inventory opportunity."""
    if getattr(adapter,'_owner_inventory_skip_generation',0)!=skip_before:
        LOG.info('기운 선택상자 보류 · 인벤토리 일정이 건너뛰어짐')
        return 'inventory_skipped'
    context.checkpoint()
    from owner_schedule_priority import hold_reason
    reason=hold_reason(adapter)
    if reason:
        LOG.info('기운 선택상자 보류 · %s',reason)
        return 'priority_hold'
    from owner_energy_next_integration_candidate import attempt
    return attempt(adapter,context,inputs)

def install(gui):
    from project_adapter import market_inventory as inv
    from project_adapter.town_services import TownServices
    if getattr(inv.run_inventory_use,'_owner_missing_gear',False):return
    ordinary=inv.run_inventory_use
    @wraps(ordinary)
    def use(adapter,context,inputs):
        if adapter.values.get('auto_rewards.inventory_use.enabled') is not True:return False
        from owner_progression import state
        context.checkpoint();now=time.monotonic()
        interval=300 if state(adapter).level==50 else 45
        cached=getattr(adapter,'_owner_worn_equipment',None)
        level=state(adapter).level
        # The E badge proves only that something is worn, not its grade.
        # At level 30+ this must not become a durable proof of a rare fan.
        if cached and cached['context'] is context and now-cached['time']<interval and all(v is True for v in cached['parts'].values()) and type(level) is int and (level<30 or cached.get('rare_weapon') is True):
            LOG.info('초반 장비 장착 완료 · 상자 탐색·개봉 생략');return True
        if not getattr(adapter,'_owner_preparing_gears',False) and now-getattr(adapter,'_owner_inventory_completed',-1e30)<interval:return True
        service=TownServices(adapter,context,inputs,inv.INVENTORY_USE_NAMES)
        if inv.open_inventory(service) is False:raise RuntimeError('상자 처리 전 장착 상태를 확인하지 못했습니다.')
        first=service.capture();context.wait(.15);service.check();second=service.capture()
        worn=agree(first,second)
        rare_weapon=paired_rare_weapon(Path(adapter.project.root)/'profiles/DKB',first,second) if worn.get('무기') is True else None
        items,armor,accessories=plan(worn,level,rare_weapon)
        adapter._owner_worn_equipment={'context':context,'time':time.monotonic(),'parts':worn,'rare_weapon':rare_weapon}
        LOG.info('상자 사전 점검 · 장착=%s · 빈 칸=%s · 판독 보류=%s',
          ','.join(p for p,v in worn.items() if v is True) or '없음',
          ','.join(p for p,v in worn.items() if v is False) or '없음',
          ','.join(p for p,v in worn.items() if v is None) or '없음')
        if type(level) is int and level>=30 and worn.get('무기') is True and rare_weapon is None:
            LOG.info('30레벨 희귀 부채 확인 보류 · 착용 표시는 등급을 증명하지 않음')
        if rare_weapon is True:
            LOG.info('희귀 이상 무기 장착 확인 · 부채 상자 추가 개봉 생략')
            from owner_startup_receipts import Preparation
            progress=state(adapter)
            if progress.character:
                preparation=Preparation(adapter.project.root,progress.character)
                preparation.item['rare_weapon_worn']={'confirmed':True,'at':time.time(),'proof':'paired_native_grade_on_authored_weapon_crop','scope':'rare_or_higher_weapon_not_fan_name'}
                preparation.commit()
        if not items:
            close_inventory(service);adapter._owner_inventory_completed=time.monotonic()
            if type(level) is int and level>=30 and worn.get('무기') is not False and rare_weapon is None:
                LOG.info('무기 등급 미확인 · 부채 상자 처리 완료 여부를 판단하지 않음')
            else:LOG.info('필요한 장비 상자 없음 · 상자 탐색·개봉 생략')
            return True
        previous=(inv.INVENTORY_USE_ITEMS,inv.RARE_ARMOR_PRIORITY,inv.RARE_ACCESSORY_PRIORITY)
        inv.INVENTORY_USE_ITEMS=items;inv.RARE_ARMOR_PRIORITY=armor;inv.RARE_ACCESSORY_PRIORITY=accessories
        try:return ordinary(adapter,context,inputs)
        finally:inv.INVENTORY_USE_ITEMS,inv.RARE_ARMOR_PRIORITY,inv.RARE_ACCESSORY_PRIORITY=previous
    @wraps(use)
    def with_energy(adapter,context,inputs):
        skip_before=getattr(adapter,'_owner_inventory_skip_generation',0)
        result=use(adapter,context,inputs)
        if result is False:return result
        from owner_energy_box_runtime_candidate import Hold
        try:
            outcome=energy_after_inventory(adapter,context,inputs,skip_before)
            if outcome not in ('disabled','character_unknown'):
                LOG.info('기운 선택상자 · %s',outcome)
        except Hold as exc:
            LOG.info('기운 선택상자 확인 보류 · %s',str(exc))
        return result
    with_energy._owner_missing_gear=True;inv.run_inventory_use=with_energy;gui._owner_equipment_boxes=True
