"""One explicitly scoped manual observation, not an automatic claim receipt."""
import hashlib,json
from pathlib import Path
from owner_hunt_rules_candidate import configured_identity
from owner_energy_box_runtime_candidate import Journal,Hold
SCOPE='configured-v1:b90482f60c6d7efa11a3847b98f3b927d105ad3a8903ed2b6aed52dbafe26eab'
CHARACTER='256b0f6111f96bcaaf78501c'
RECEIPT='scoped-v1:e3e3adc1e220d59f2aa0c8ef924ae44d0354dbabc729d02c21a9709b8180cfe3'

def migrate(root,*,observed_character):
 root=Path(root)
 if observed_character!=CHARACTER or configured_identity(root)!=SCOPE:raise Hold('수동 관측 캐릭터·서버 불일치')
 expected='scoped-v1:'+hashlib.sha256((SCOPE+'|'+CHARACTER).encode('utf-8')).hexdigest()
 if expected!=RECEIPT:raise Hold('캐릭터 기록 범위 불일치')
 try:progress=json.loads((root/'settings'/'owner-progression.json').read_text(encoding='utf-8-sig'))
 except (OSError,ValueError) as exc:raise Hold('기존 캐릭터 관측 기록 없음') from exc
 if progress.get('schema')!='owner-progression-v2' or CHARACTER not in progress.get('characters',{}):raise Hold('기존 캐릭터 관측 기록 확인 필요')
 return Journal(root,RECEIPT).note_manual_event(event_id='20261102-manual-life-one',name='생명',quantity=1,
    source='2026-11-02 약 02:52 수동 수령 화면 및 별도 상자 50→49 관측; 자동 수령 증거 아님')
