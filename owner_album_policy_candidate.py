"""Decide a single album action from paired UI evidence; no input is sent.

Evidence must describe the selected action's cost, not a currency counter in
the surrounding HUD. A missing icon cannot be treated as a zero-cost proof.
"""

def decision(mode, first, second):
    if mode not in ('조각 등록만','완성'):raise ValueError('화첩 처리 방식 오류')
    if not isinstance(first,dict) or not isinstance(second,dict):return 'hold'
    if first.get('verified') is not True or second.get('verified') is not True:return 'hold'
    if any(first.get(k)!=second.get(k) for k in ('character','entry','completion_visible')):return 'hold'
    if not isinstance(first.get('character'),str) or not first['character']:return 'hold'
    if not isinstance(first.get('entry'),str) or not first['entry']:return 'hold'
    if type(first.get('completion_visible')) is not bool:return 'hold'
    # A confirmed completion button is enough to stop; a cost need not be
    # readable for a decision that will not issue any input.
    if mode=='조각 등록만' and first['completion_visible']:return 'skip'
    if any(first.get(k)!=second.get(k) for k in ('action','currency','amount')):return 'hold'
    action=first.get('action');currency=first.get('currency');amount=first.get('amount')
    if action not in ('조각 등록','완성'):return 'hold'
    if currency not in ('없음','요혼석','엽전','기타'):return 'hold'
    if type(amount) is not int or amount<0:return 'hold'
    if currency=='없음' and amount!=0:return 'hold'
    if currency=='기타':return 'hold'
    # Register only never executes the distinct final-completion action, even
    # if a particular completion appears free.
    if mode=='조각 등록만' and action=='완성':return 'skip'
    if mode=='조각 등록만' and currency=='요혼석' and amount>0:return 'skip'
    return 'allow'
