"""DKB candidate policy: pure decisions, no game input or persistence."""
from dataclasses import dataclass

@dataclass(frozen=True)
class GearTarget:
    enhance: int = 50
    breakthrough: int = 3
    awakening: int = 1

GEAR_TARGETS={'일반':GearTarget(), '희귀':GearTarget(), '영웅':GearTarget(breakthrough=2)}
# Skill reinforcement is independent of equipment growth. User selected 49
# for 파멸 after reviewing current advice, and 19 for the other two styles.
SKILL_REINFORCEMENT_TARGETS={
    '절명':0, '연타':0, '강타':19, '척살':0, '저격':0, '주술':0,
    '파멸':49, '강인':19, '기동':0, '기만':0, '헌신':0, '제압':0,
}
PRIORITY=('무기','팔찌','반지')
SKILL_BOX_ORDER=('생명의 흐름','방패 밀기','공간 결계')
# User order: ultimate 대폭발 occurs in the third position; general skill order
# remains 방패 밀기, 생명의 흐름, 공간 결계, 연쇄 번개, 검기 폭발, 번개 폭풍, 요기 폭발, 하늘의 심판.
AOE_SKILLS=('방패 밀기','생명의 흐름','공간 결계','연쇄 번개','검기 폭발','번개 폭풍','요기 폭발','하늘의 심판')
ULTIMATE='대폭발'
ULTIMATE_USE_INDEX=2  # zero-based: use after the first two skills
# Equip order is distinct from use order: the first five include three 파멸 skills.
AOE_EQUIP=('방패 밀기','생명의 흐름','연쇄 번개','번개 폭풍','요기 폭발','공간 결계','검기 폭발','하늘의 심판')

def should_replace(current_grade,new_grade):
    return current_grade=='일반' and new_grade=='희귀'

def skill_box_next(learned,level):
    if level is None or level<30:return None
    # None represents unknown: stop instead of consuming a choice box.
    for skill in SKILL_BOX_ORDER:
        if learned.get(skill) is None:return None
        if learned[skill] is False:return skill
    return None

def choose_hunt_rule(power,rules):
    if type(power) is not int or power<0:return None
    accepted=[]
    for rule in rules:
        threshold,slot=rule.get('power'),rule.get('slot')
        if type(threshold) is not int or threshold<0 or type(slot) is not int or not 1<=slot<=4:
            raise ValueError('사냥터 전투력 또는 저장 위치 번호 오류')
        if threshold<=power:accepted.append(rule)
    if len({r['power'] for r in rules})!=len(rules):raise ValueError('중복된 사냥터 기준 전투력')
    return max(accepted,key=lambda r:r['power']) if accepted else None

def hunt_destination(available_quests,power,rules=()):
    if available_quests is None or power is None:return None
    if available_quests:return 'quests'
    return choose_hunt_rule(power,rules) or '둘러보기 추천'

def hunt_death_policy(confirmed_deaths,active_rule):
    if type(confirmed_deaths) is not int or confirmed_deaths<0:raise ValueError('사망 기록 오류')
    if confirmed_deaths<2:return '재시도'
    return '둘러보기 추천' if active_rule else '추천 사냥터 재확인'
