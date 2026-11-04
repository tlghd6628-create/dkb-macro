"""Pure blessing selection policy; actual game actions are not connected."""
PATTERNS=('봉황','나비','도깨비','연꽃','토끼')
GRADES=('일반','희귀','영웅','전설')

def validate_order(order):
    if not isinstance(order,list) or len(order)>len(PATTERNS):raise ValueError('문양 순위 오류')
    if any(name not in PATTERNS for name in order) or len(set(order))!=len(order):
        raise ValueError('문양 순위가 중복되었거나 올바르지 않습니다')
    return order

def collect_rank_fields(values):
    if not isinstance(values,list) or len(values)!=5:raise ValueError('문양 순위 항목 오류')
    result=[];gap=False
    for value in values:
        if not value:gap=True
        elif gap:raise ValueError('문양 순위는 1순위부터 채워 주세요')
        else:result.append(value)
    return validate_order(result)

def compare(current,candidate,order):
    """Compare two fresh, already-verified candidates for the same slot.

    No rank is inferred for an unlisted pattern. The caller must verify live
    identity and that the candidate is actually equippable before using this.
    """
    validate_order(order)
    for row in (current,candidate):
        if not isinstance(row,dict) or row.get('verified') is not True:return 'hold'
        if row.get('grade') not in GRADES or row.get('pattern') not in PATTERNS:return 'hold'
        if type(row.get('slot')) is not int or row['slot'] not in range(1,6):return 'hold'
    if current['slot']!=candidate['slot']:return 'hold'
    a,b=GRADES.index(current['grade']),GRADES.index(candidate['grade'])
    if b>a:return 'replace'
    if b<a or current['pattern']==candidate['pattern']:return 'keep'
    if current['pattern'] not in order or candidate['pattern'] not in order:return 'hold'
    return 'replace' if order.index(candidate['pattern'])<order.index(current['pattern']) else 'keep'
