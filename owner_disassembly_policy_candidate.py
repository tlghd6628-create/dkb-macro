"""Policy only: identify and protect equipped item duplicates before dismantling."""
import re

def normal(value):
 if not isinstance(value,str):return None
 name=re.sub(r'\s+','',value)
 return name if len(name)>=2 else None

def dismantle_decision(item,equipped,*,equipped_scan_complete):
 # Both records require item name AND slot confirmed by two fresh screens.
 if not equipped_scan_complete or item.get('verified') is not True:return 'hold'
 name=normal(item.get('name'));slot=item.get('slot')
 if name is None or not isinstance(slot,str) or not slot:return 'hold'
 for row in equipped:
  if row.get('verified') is not True or normal(row.get('name')) is None or not row.get('slot'):return 'hold'
  if row['slot']==slot and normal(row['name'])==name:return 'protect'
 # The native dismantler has no proven per-item exclusion hook, and current
 # captures do not establish all equipped identities or an unchanged selected
 # dismantle set.  A non-match must never authorize an irreversible action.
 return 'hold'
