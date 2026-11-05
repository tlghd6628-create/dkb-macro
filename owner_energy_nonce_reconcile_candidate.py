"""Nonce-bound, read-only reconciliation of an observed dream-one claim."""
from pathlib import Path
import hashlib,json,math,time
from io import BytesIO
import numpy as np
from PIL import Image
from owner_energy_box_runtime_candidate import Hold,proof
from owner_energy_box_detail_candidate import left_shown
from owner_energy_reward_candidate import READERS,matches as reward_matches
from owner_ui_foreground import inventory_header

def reconcile(root,journal,current,*,character,scope,guard,refresh_current=None):
 if guard() is not True:raise Hold('기운 수령 캐릭터 확인 필요')
 data=journal.read();pending=data.get('pending')
 if not isinstance(pending,dict) or pending.get('phase')!='sent':raise Hold('수령 대기 기록 확인 필요')
 name=pending.get('name');operation=pending.get('operation_id');before=pending.get('boxes_before');at=pending.get('at')
 quantity=pending.get('quantity')
 if (name not in READERS or type(quantity) is not int or not isinstance(operation,str) or len(operation)!=32
     or any(ch not in '0123456789abcdef' for ch in operation) or type(before) is not int or not 1<=quantity<=before
     or type(at) not in (int,float) or not math.isfinite(at)):
  raise Hold('검증된 기운 수령 요청 확인 필요')
 if not proof(current) or current.get('boxes')!=before-quantity:raise Hold('현재 상자 잔량 두 화면 확인 필요')
 directory=Path(root)/'logs'/'energy-claim-evidence'
 try:folders=sorted((p for p in directory.iterdir() if p.is_dir()),key=lambda p:p.name)
 except OSError as exc:raise Hold('수령 자료 폴더 확인 필요') from exc
 if len(folders)>512:raise Hold('수령 자료가 많아 안전 확인 필요')
 matches=[]
 for folder in folders:
  if len(folder.name)!=32 or any(c not in '0123456789abcdef' for c in folder.name):continue
  try:manifest=json.loads((folder/'capture-manifest.json').read_text(encoding='utf8'))
  except (OSError,ValueError):continue
  if manifest.get('operation_id')==operation:matches.append((folder,manifest))
 if len(matches)!=1:raise Hold('수령 요청과 자료 연결 확인 필요')
 folder,manifest=matches[0]
 if (manifest.get('version')!=2 or manifest.get('target')!=name or manifest.get('quantity',1)!=quantity or manifest.get('errors')!=[]
     or manifest.get('identity')!={'receipt_key':journal.identity,'character':character,'scope':scope}):raise Hold('수령 자료 캐릭터 범위 불일치')
 entries=manifest.get('frames')
 if not isinstance(entries,list) or not 4<=len(entries)<=32:raise Hold('수령 프레임 수 확인 필요')
 ids=[];last_wall=at;last_mono=-1.;frames=[]
 for index,row in enumerate(entries):
  if not isinstance(row,dict) or row.get('file')!=f'after-{index:02d}.png' or row.get('saved') is not True:raise Hold('수령 프레임 누락')
  fid=row.get('frame_id');wall=row.get('captured_at');mono=row.get('captured_monotonic')
  if (not isinstance(fid,str) or not fid or fid in ids or type(wall) not in (int,float) or type(mono) not in (int,float)
      or not math.isfinite(wall) or not math.isfinite(mono) or not at<=wall<=at+10 or wall<last_wall or mono<=last_mono):raise Hold('수령 프레임 순서 확인 필요')
  ids.append(fid);last_wall=wall;last_mono=mono
  try:
   raw=(folder/row['file']).read_bytes()
   with Image.open(BytesIO(raw)) as image:frame=np.asarray(image.convert('RGB'))
  except (OSError,ValueError) as exc:raise Hold('수령 원본 읽기 실패') from exc
  # A frame taken while the dialog fades cannot name the character; only named frames count below.
  if inventory_header(frame,character) is None:continue
  frames.append((row,frame,hashlib.sha256(raw).hexdigest()))
 before_ids=pending.get('before_frame_ids')
 if not isinstance(before_ids,list) or len(before_ids)!=2 or set(ids)&set(before_ids) or set(ids)&set(current['frame_ids']):raise Hold('다른 시점의 화면 확인 필요')
 rewards=[i for i,(_,f,_) in enumerate(frames) if reward_matches(f,name,quantity)]
 if len(rewards)<2:raise Hold('선택한 기운 수령 수량 원본 확인 필요')
 first,second=rewards[0],rewards[1]
 details=[i for i,(_,f,_) in enumerate(frames) if i>second and left_shown(f,before-quantity)]
 if len(details)<2:raise Hold('수령 후 상자 잔량 두 화면 확인 필요')
 picked=[frames[i] for i in (first,second,details[0],details[1])]
 if callable(refresh_current):current=refresh_current()
 if (guard() is not True or not proof(current) or current.get('boxes')!=before-quantity
     or set(ids)&set(current['frame_ids'])):raise Hold('현재 캐릭터 또는 화면 갱신 필요')
 again=journal.read()
 if again.get('pending')!=pending:raise Hold('수령 기록 변경')
 if pending.get('protocol')=='energy-batch-v3':
  from owner_energy_batch_runner_candidate import commit_result
  commit_result(again,pending)
 else:again['confirmed'][name]+=quantity
 again['receipts'].append({'name':name,'quantity':quantity,'operation_id':operation,'proof':'nonce_reward_and_decrement',
    'boxes_before':before,'boxes_after':before-quantity,
    'frame_ids':[r['frame_id'] for r,_,_ in picked],'sha256':[h for _,_,h in picked],'evidence_dir':folder.name,'at':time.time()})
 again['pending']=None;journal.save(again)
 return 'confirmed'
