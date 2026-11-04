"""Story threshold observations: only accept a single independently read number."""
import re

def read_recommended(rows):
    found=set()
    for row in rows:
        if row.get('score',0)<.96:continue
        text=row.get('text','').strip().replace(',','')
        if re.fullmatch(r'[0-9]{4,7}',text):
            number=int(text)
            if 1000<=number<=10000000:found.add(number)
    return next(iter(found)) if len(found)==1 else None

def newly_reachable(entries,previous,current):
    if not isinstance(previous,int) or not isinstance(current,int) or current<=previous:return []
    return [k for k,row in entries.items() if row.get('power_proven') is True and type(row.get('required')) is int and previous<row['required']<=current and row.get('completed') is not True]

def needs_recheck(entries,previous,current,catalog_complete):
    if type(previous) is not int or type(current) is not int or current<=previous:return False
    if not catalog_complete:return True
    for row in entries.values():
        if row.get('completed') is True or row.get('identity_alias_of') or row.get('legacy_step'):continue
        if row.get('power_proven') is not True or type(row.get('required')) is not int:return True
        if previous<row['required']<=current:return True
    return False
