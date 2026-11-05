"""One floor for everything that costs coins: the shop's 남길 엽전, for growth, entry fees and the rest as well.

The user's rule (11-05). A button that spends is simply not there while the coins are at the floor, so every path,
native or ours, stops the way it already stops for a button it cannot see. A balance that cannot be read spends nothing.
"""
import logging,re,time
import numpy as np

LOG=logging.getLogger('project_gui.DKB')
AREA=(608,16,76,24)  # real pixels of the coin amount in the top bar: 4.27M ends at 676, and cut short it read as nothing
SCALE=6              # measured on 72 saved screens: at 6 times it reads right or not at all, at 3 it took 1 for 7
SHOWN=re.compile(r'\d{1,3}(?:\.\d{1,2})?[KMB]')
REMEMBER=300.;SAID_EVERY=60.;FRESH=1.
_last=[None,0.];_said={};_recent=[None,0.,None]


def reserve(root=None):
    from owner_shop_settings_candidate import ShopSettingsStore,DEFAULT_COIN_RESERVE
    from owner_hunt_rules_candidate import configured_identity
    import owner_text
    try:
        value=ShopSettingsStore(root or owner_text._ROOT[0],configured_identity(root or owner_text._ROOT[0])).read_document()['coin_reserve']
    except (OSError,ValueError,TypeError,KeyError):return DEFAULT_COIN_RESERVE
    return DEFAULT_COIN_RESERVE if value is None else value


def lower_bound(text):
    """The least this display can mean, or None. Only the compact form: a plain 1,221 in that place is another currency."""
    from owner_shop_reader_candidate import displayed_balance_interval
    value=str(text).strip()
    if not SHOWN.fullmatch(value):return None
    # This font's 1 reads as 7 (140.18K as 740.78K on saved screens), so a 7 counts as a 1. That can only hold back.
    found=displayed_balance_interval(value.replace('7','1'))
    return found['lower'] if found else None


def read_balance(frame):
    """The coins on this frame, or the last read if this screen shows none and that is recent. None when unknown."""
    real=getattr(frame,'hi',None)
    if real is None:return None
    import owner_text
    x,y,w,h=AREA
    rows=owner_text.read_area(None,np.asarray(real)[y:y+h,x:x+w],scale=SCALE,minimum=.7)
    # Only spaces come out: the point in 85.18K is the amount.
    values=[v for v in (lower_bound(re.sub(r'\s','',r['text'])) for r in rows) if v is not None]
    if len(values)==1:
        _last[0],_last[1]=values[0],time.monotonic()
        return values[0]
    return _last[0] if _last[0] is not None and time.monotonic()-_last[1]<=REMEMBER else None


def leaves_enough(balance,floor,cost=0):
    return balance is not None and balance-cost>=floor


def can_spend(frame,what='',cost=0,root=None):
    """May this be paid for now? True on a frame with no real pixels, where this rule has nothing to read."""
    if getattr(frame,'hi',None) is None:return True
    now=time.monotonic()
    if not cost and _recent[0] is not None and now-_recent[1]<=FRESH:
        balance,floor=_recent[2]
    else:
        balance,floor=read_balance(frame),reserve(root)
        _recent[0],_recent[1],_recent[2]=True,now,(balance,floor)
    allowed=leaves_enough(balance,floor,cost)
    if not allowed and now-_said.get(what,-1e9)>=SAID_EVERY:
        _said[what]=now
        LOG.info('엽전 기준 · %s 보류 · 잔액 %s · 비용 %s · 남길 엽전 %d',what or '소비','미확인' if balance is None else balance,cost,floor)
    return allowed
