"""Read-only verified reconciliation of the single captured 49→48 trial."""
from pathlib import Path
import hashlib,json,math,time
import numpy as np
from PIL import Image
from owner_energy_box_detail_candidate import evidence_detail
from owner_energy_reward_candidate import dawn_one
from owner_energy_box_runtime_candidate import Hold,proof

LEGACY_DIR='c8ef897182164064bb56f235e1d90dc2'
LEGACY_CHARACTER='256b0f6111f96bcaaf78501c'
LEGACY_RECEIPT='scoped-v1:e3e3adc1e220d59f2aa0c8ef924ae44d0354dbabc729d02c21a9709b8180cfe3'
LEGACY_AT=1793564837.0005507
LEGACY_BEFORE=['b2338e0312244e14859f5b59ecc9d188','3ba4daff99c74bf7813c36ac9395670d']
LEGACY_SHA256=('135c3538debf3fbbabda442f52378bba608f5bce82133204703ee26ff3342deb',
 '24190aa9994efc7612d5ceb74470823268134387254a699d53afc6e59d215dc7',
 '7dbda4b53912c818d2858da0a965362ebb5191b42eeab1f78a2d556a576ac88b',
 '1f5b4a940d180ca18cfea9a69ccd4a798b7721035a72b837c28ef8d9cd11cf39')

def _character(frame):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return None
 return hashlib.sha256((np.min(frame[9:25,68:101],axis=2)>150).tobytes()).hexdigest()[:24]

def read_legacy(root,journal,current,*,character,guard):
 """Verify exact original manifest plus fresh current two-frame detail.

 This is deliberately restricted to the one original pre-nonce event. The
 evidence images are never accepted as fresh action authority.
 """
 if guard() is not True or character!=LEGACY_CHARACTER or journal.identity!=LEGACY_RECEIPT:raise Hold('수령 당시 캐릭터 일치 확인 필요')
 if not proof(current) or current.get('boxes')!=48:raise Hold('현재 기운상자 48개 두 화면 확인 필요')
 state=journal.read();pending=state.get('pending')
 if not isinstance(pending,dict):raise Hold('기운 수령 대기 기록 없음')
 if (pending.get('phase')!='sent' or pending.get('name')!='여명' or pending.get('quantity')!=1 or pending.get('boxes_before')!=49
     or pending.get('before_frame_ids')!=LEGACY_BEFORE or type(pending.get('at')) not in (int,float) or abs(pending['at']-LEGACY_AT)>.001
     or pending.get('operation_id') is not None):raise Hold('기존 여명 수령 요청 불일치')
 folder=Path(root)/'logs'/'energy-claim-evidence'/LEGACY_DIR
 manifest=json.loads((folder/'capture-manifest.json').read_text(encoding='utf8'))
 if manifest.get('version')!=1 or manifest.get('target')!='여명' or manifest.get('errors')!=[]:raise Hold('수령 기록 목록 확인 필요')
 entries=manifest.get('frames')
 if not isinstance(entries,list):raise Hold('수령 프레임 목록 확인 필요')
 byname={e.get('file'):e for e in entries if isinstance(e,dict)}
 names=('after-00.png','after-06.png','after-07.png','after-18.png')
 if len(byname)!=len(entries) or any(n not in byname for n in names):raise Hold('수령 화면 누락')
 rows=[byname[n] for n in names];ids=[e.get('frame_id') for e in rows]
 times=[e.get('captured_at') for e in rows];mono=[e.get('captured_monotonic') for e in rows]
 if (any(e.get('saved') is not True for e in rows) or any(not isinstance(v,str) or not v for v in ids) or len(set(ids))!=4
     or set(ids)&set(pending['before_frame_ids']) or set(ids)&set(current['frame_ids'])
     or any(type(v) not in (int,float) or not math.isfinite(v) for v in times+mono)
     or not pending['at']<=times[0]<times[1]<times[2]<times[3]<=pending['at']+10
     or not mono[0]<mono[1]<mono[2]<mono[3]):raise Hold('수령 시각 또는 별도 프레임 확인 필요')
 images=[];hashes=[]
 for name in names:
  raw=(folder/name).read_bytes();hashes.append(hashlib.sha256(raw).hexdigest())
  from io import BytesIO
  with Image.open(BytesIO(raw)) as image:images.append(np.asarray(image.convert('RGB')))
 if tuple(hashes)!=LEGACY_SHA256:raise Hold('원본 수령 화면 무결성 불일치')
 if any(_character(frame)!=character for frame in images):raise Hold('수령 화면 캐릭터 일치 실패')
 if evidence_detail(images[0])!=48 or evidence_detail(images[3])!=48 or not dawn_one(images[1]) or not dawn_one(images[2]):
  raise Hold('여명 1개 획득과 상자 48개 차감 확인 필요')
 if guard() is not True or not proof(current):raise Hold('현재 캐릭터 또는 화면 갱신 필요')
 again=journal.read()
 if again.get('pending')!=pending:raise Hold('기운 수령 기록 변경')
 again['confirmed']['여명']+=1
 again['receipts'].append({'name':'여명','quantity':1,'proof':'legacy_49_to_48_and_dawn_one',
                           'frame_ids':ids,'sha256':hashes,'evidence_dir':LEGACY_DIR,'at':time.time()})
 again['pending']=None;journal.save(again)
 return 'confirmed'
