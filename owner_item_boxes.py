"""One switch per box under 아이템 사용 (user 11-06). All on by default; the master switch still decides first.

Boxes are opened from level 30: the rare fan and accessory boxes to put on what is missing (팔찌·반지 first), the
skill choice box for 생명의 흐름 · 방패 밀기 · 공간 결계, the skill manual box and the energy choice box.
"""
import copy

MASTER='auto_rewards.inventory_use.enabled'
BOXES=(('weapon','희귀 무기 상자'),('accessory','희귀 장신구 상자'),('skill_choice','도술 선택상자'),
       ('manual','도술 요령서 상자'),('energy','기운 선택상자'))


def key(code):return 'auto_rewards.inventory_use.boxes.'+code


def enabled(values,code):
    """A box is used when the master is on and its own switch is not off."""
    return values.get(MASTER) is True and values.get(key(code),True) is not False


def add_fields(schema):
    groups=[g for t in schema['tabs'] for g in t['groups']]
    entries={f['id']:(g,f) for g in groups for f in g['fields']}
    if MASTER not in entries:return schema
    group,master=entries[MASTER]
    at=group['fields'].index(master)+1
    for code,label in BOXES:
        if key(code) in entries:continue
        field=copy.deepcopy(master)
        field.update(id=key(code),label=label,default=True,existing_default=True,settings_only=True)
        field.pop('enabled_if',None)
        group['fields'].insert(at,field);at+=1
    return schema
