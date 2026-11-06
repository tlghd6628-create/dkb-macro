"""Confirmed starter preparation survives Stop/Start and application restart."""
from pathlib import Path
import json,logging,time
from owner_timetable import save
LOG=logging.getLogger('project_gui.DKB');CRITICAL=('무기','반지','팔찌')

class Preparation:
 def __init__(self,root,character):
  if not character:raise ValueError('현재 캐릭터 확인 필요')
  self.path=Path(root)/'settings/owner-startup-receipts.json'
  self.data=json.loads(self.path.read_text(encoding='utf-8-sig')) if self.path.exists() else {'version':1,'characters':{}}
  if self.data.get('version')!=1 or not isinstance(self.data.get('characters'),dict):raise ValueError('초기 준비 기록 형식 확인 필요')
  self.item=self.data['characters'].setdefault(character,{'worn':{},'coupons':{}})
 def commit(self):save(self.path,self.data)
 def worn(self,parts):
  for name,value in parts.items():
   if value is True:self.item['worn'][name]={'confirmed':True,'at':time.time(),'proof':'two_inventory_frames_equipped_badge'}
   elif value is False:self.item['worn'].pop(name,None)
  self.commit()
 def starter_ready(self):return all(self.item['worn'].get(name,{}).get('confirmed') is True for name in CRITICAL)
 def coupon_receipts(self,rows):
  for code,row in rows.items():
   if row.get('completed') is True:self.item['coupons'][code]={'completed':True,'status':row.get('status'),'at':row.get('at'),'proof':'existing_native_coupon_receipt'}
  self.commit()

def coupon_scope(root,identity):
 """The native coupon record is keyed by the PC number only, so a new character on this PC took the old one's codes
 as done (user 11-06: 짱군네 after 홍짱군). The record is swapped per server·character: the old one is kept aside and
 the new one starts from its own copy, or empty."""
 import hashlib,shutil
 root=Path(root);settings=root/'settings';main=settings/'coupon_results.json';marker=settings/'owner-coupon-owner.json'
 who='%s|%s'%(identity.get('server_name') or '',identity.get('character_name') or '')
 if who=='|':return
 def kept(owner):return settings/('owner-coupon-'+hashlib.sha256(owner.encode('utf-8')).hexdigest()[:24]+'.json')
 try:owner=json.loads(marker.read_text(encoding='utf-8')).get('owner')
 except (OSError,ValueError,AttributeError):owner=None
 if owner==who:return
 if owner and main.exists():shutil.copy2(main,kept(owner))
 if kept(who).exists():shutil.copy2(kept(who),main)
 elif owner and main.exists():main.unlink()
 marker.write_text(json.dumps({'owner':who},ensure_ascii=False),encoding='utf-8')
 LOG.info('쿠폰 기록 캐릭터 전환 · %s → %s',owner or '미기록',who)

def terminal_coupons(root,identity):
 """Use the exact existing native identity scope; never another account."""
 coupon_scope(root,identity)
 root=Path(root);config=json.loads((root/'profiles/DKB/config/coupons.json').read_text(encoding='utf-8-sig'))
 codes={row['code'] for row in config.get('coupons',[]) if row.get('enabled',True) and row.get('code')}
 path=root/'settings/coupon_results.json';record=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
 alias=identity.get('pc_alias') or '0000';matches=[]
 for key,rows in record.get('characters',{}).items():
  try:scope=json.loads(key)
  except (ValueError,TypeError):continue
  if scope=={'pc_alias':alias}:matches.append(rows)
 rows=matches[0] if len(matches)==1 else {}
 complete={code:rows[code] for code in codes if rows.get(code,{}).get('completed') is True}
 return codes-set(complete),complete

def initial_coupons(adapter,context,inputs):
 """Return whether a new coupon batch ran and its mail needs checking."""
 from owner_progression import state
 from owner_coupons import identity_values
 from project_adapter.coupon_registration import run_coupon_registration
 progress=state(adapter);identity=identity_values()
 try:pending,complete=terminal_coupons(adapter.project.root,identity)
 except (OSError,ValueError,TypeError,KeyError):pending=None;complete={}
 if progress.character and complete:
  try:Preparation(adapter.project.root,progress.character).coupon_receipts(complete)
  except (OSError,ValueError):LOG.warning('쿠폰 준비 기록 저장 보류 · 기존 쿠폰 이력 유지')
 if pending==set():
  LOG.info('초기 쿠폰 준비 완료 기록 · %d개 · 등록 화면·초기 우편 재확인 생략',len(complete));return False
 context.checkpoint();run_coupon_registration(adapter,context,inputs)
 if progress.character:
  try:
   _,complete=terminal_coupons(adapter.project.root,identity)
   Preparation(adapter.project.root,progress.character).coupon_receipts(complete)
  except (OSError,ValueError,TypeError,KeyError):LOG.warning('쿠폰 준비 기록 저장 보류 · 기존 쿠폰 이력 유지')
 return True
