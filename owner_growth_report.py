"""Read-only character growth projection for Telegram; same cache as PC UI."""
from datetime import datetime,timedelta,timezone
from io import BytesIO
import hashlib,json,math,time
from pathlib import Path

KST=timezone(timedelta(hours=9))
SECTIONS=(('blessings','가호',('enhance','breakthrough'),'강화 / 돌파'),
          ('skills','도술 계열',('enhance','breakthrough'),'강화 / 돌파'),
          ('individual','개별 도술',('awaken',),'각성'),
          ('energies','기운',('stage',),'발현 단계'))

def identity(root):
 from owner_hunt_rules_candidate import configured_identity
 expected=configured_identity(root)
 row=json.loads((Path(root)/'settings/manager_identity.json').read_text(encoding='utf-8-sig'))
 server,name=row['server_name'].strip(),row['character_name'].strip()
 raw=json.dumps([server,name],ensure_ascii=False,separators=(',',':')).encode('utf-8')
 if expected!='configured-v1:'+hashlib.sha256(raw).hexdigest():raise ValueError('캐릭터 설정 변경 · 다시 조회해 주세요.')
 return expected,server+' · '+name

def _stamp(value):
 if type(value) not in (int,float) or not math.isfinite(value) or value<=0:return None
 try:return datetime.fromtimestamp(value,KST).strftime('%m/%d %H:%M')
 except (ValueError,OverflowError,OSError):return None

def project(root,*,clock=time.time):
 """No settings creation, adapter lookup, resource intent or game probing."""
 from owner_growth_current import display_snapshot
 from owner_gear_settings_candidate import Store
 scope,label=identity(root)
 saved=display_snapshot(root,scope);goals=Store(root,scope).read()
 from owner_settings_layout import GROWTH_SWITCHES
 try:
  raw=(Path(root)/'settings/auto-settings.json').read_bytes()
  if len(raw)>1024*1024:raise ValueError('settings too large')
  master=json.loads(raw)['values']
  if not isinstance(master,dict):raise ValueError('invalid settings')
 except (OSError,ValueError,KeyError,TypeError):master={}
 groups=[];last=[]
 for section,title,fields,legend in SECTIONS:
  observed=saved['values'][section];targets=goals.get(section,{})
  if section=='individual':
   names=sorted(set(observed)|{n for n,v in targets.items() if v.get('enabled') is True})
  else:names=list(targets)+sorted(set(observed)-set(targets))
  rows=[]
  for name in names:
   row=observed.get(name,{});values=row.get('values',{});target=targets.get(name,{})
   enabled=target.get('enabled') is True
   current=' / '.join(str(values[f]) if f in values else '미확인' for f in fields)
   goal=(' / '.join(str(target[f]) if type(target.get(f)) is int else '미설정' for f in fields)) if enabled else '꺼짐'
   stamps=[row.get('field_at',{}).get(f,row.get('at_epoch')) for f in fields if f in values]
   stamps=[s for s in stamps if _stamp(s) is not None]
   at=min(stamps) if stamps else None
   last.extend(stamps)
   rows.append({'name':name,'current':current,'target':goal,'checked_at':_stamp(at) or '미확인'})
  enabled=master.get(GROWTH_SWITCHES['skills' if section=='individual' else section])
  if rows:groups.append({'key':section,'title':title,'legend':legend,'rows':rows,
                         'enabled':enabled if type(enabled) is bool else None})
 if identity(root)[0]!=scope:raise ValueError('캐릭터 설정 변경 · 다시 조회해 주세요.')
 return {'identity':scope,'character':label,'generated_at':_stamp(clock()),'groups':groups,
         'last_observed':_stamp(max(last)) if last else None,'display_only':True}

def sheets(snapshot):
 """Compact independent tables; no desktop screenshot or extra OCR."""
 from PIL import Image,ImageDraw,ImageFont
 from owner_schedule_image import FONT,BOLD,wrap
 normal=ImageFont.truetype(str(FONT),24);small=ImageFont.truetype(str(FONT),20)
 titlefont=ImageFont.truetype(str(BOLD),32);bold=ImageFont.truetype(str(BOLD),24)
 probe=ImageDraw.Draw(Image.new('RGB',(1,1)));pages=[]
 for group in snapshot['groups']:
  for start in range(0,len(group['rows']),12):
   batch=group['rows'][start:start+12];prepared=[]
   for row in batch:
    columns=[wrap(probe,row[k],normal,w) for k,w in
             (('name',176),('current',222),('target',166),('checked_at',130))]
    prepared.append((columns,max(58,18+29*max(map(len,columns)))))
   character=wrap(probe,snapshot['character'],normal,720)
   head=126+len(character)*29
   image=Image.new('RGB',(800,head+sum(h for _,h in prepared)+67),'#f1f4f8')
   d=ImageDraw.Draw(image);d.text((26,19),'DKB · '+group['title'],font=titlefont,fill='#18304b')
   for i,line in enumerate(character):d.text((26,61+i*29),line,font=normal,fill='#40556c')
   state='켜짐' if group.get('enabled') is True else '꺼짐' if group.get('enabled') is False else '미확인'
   d.text((26,66+len(character)*29),group['legend']+' · 기능 '+state+' · 최근 확인값',font=small,fill='#697b8c')
   y=head-40;d.rectangle((18,y,782,head),fill='#e3eaf2')
   for x,label in ((26,'항목'),(213,'현재'),(448,'목표'),(628,'확인')):
    d.text((x,y+7),label,font=bold,fill='#334d67')
   y=head
   for i,(columns,height) in enumerate(prepared):
    d.rectangle((18,y,782,y+height),fill='white' if i%2==0 else '#f8fafc')
    for x,lines in zip((26,213,448,628),columns):
     for j,line in enumerate(lines):d.text((x,y+9+j*29),line,font=normal,fill='#344a60')
    y+=height;d.line((18,y,782,y),fill='#dde5ef')
   d.text((26,y+10),'확인: 표시된 수치 중 가장 오래된 시각',font=small,fill='#697b8c')
   d.text((26,y+36),'조회 '+str(snapshot['generated_at']),font=small,fill='#697b8c')
   output=BytesIO();image.save(output,'JPEG',quality=92,subsampling=0)
   pages.append((output.getvalue(),'DKB · '+group['title']+' 현황'))
 return pages

def page_batch(pages,page=1):
 """Bound one request below the bot outbox limit, even with105 skill rows."""
 if type(page) is not int or not 1<=page<=99:raise ValueError('성장현황 페이지 확인 필요')
 count=max(1,(len(pages)+3)//4)
 if page>count:return [(None,'성장현황은 '+str(count)+'페이지까지 있습니다.')]
 result=[(photo,caption+' · '+str(page)+'/'+str(count)) for photo,caption in pages[(page-1)*4:page*4]]
 if page<count:result.append((None,'다음: 성장현황 '+str(page+1)))
 return result
