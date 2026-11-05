"""Set the shop rows for a live check. Run with the program closed. `shop_plan.py 1` or `shop_plan.py max`."""
import glob,json,os,sys
ROOT=os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계'
WANTED=('천요석','강타 도술 강화 요령서','강인 도술 강화 요령서','파멸 도술 강화 요령서','영웅 장비 강화 비법서','전설 장비 강화 비법서')
path=glob.glob(os.path.join(ROOT,'vendor','DKB_Auto','settings','owner-shop-settings-*.json'))[0]
document=json.load(open(path,encoding='utf-8'))
limit=sys.argv[1]
rank=lambda row:WANTED.index(row['name']) if row['name'] in WANTED else len(WANTED)
rows=[r for r in document['items'] if '물약' not in r['name'] and r.get('source')!='게임 화면 판독']
rows.sort(key=rank)
for row in rows:
    row['enabled']=row['name'] in WANTED
    if row['enabled']:
        row['mode']='max' if limit=='max' else 'quantity'
        if limit!='max':row['quantity']=int(limit)
document['items']=rows;document['enabled']=True
if document.get('coin_reserve') is None:document['coin_reserve']=100000
json.dump(document,open(path,'w',encoding='utf-8',newline='\n'),ensure_ascii=False,indent=2)
print(len(rows),[(r['name'],r['mode'],r['quantity']) for r in rows if r['enabled'] and r['shop']=='remote'])
