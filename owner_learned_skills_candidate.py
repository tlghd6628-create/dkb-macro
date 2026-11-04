"""Verified owned-skill receipts, separated per character and persisted atomically."""
import json, os, tempfile, time
from pathlib import Path

class LearnedSkills:
    def __init__(self,root,character):
        if not isinstance(character,str) or not character.strip():
            raise ValueError('캐릭터 확인 필요')
        self.path=Path(root)/'settings'/'owner-learned-skills.json'
        self.character=character
        if self.path.exists():
            self.data=json.loads(self.path.read_text(encoding='utf-8-sig'))
            if self.data.get('version')!=1 or not isinstance(self.data.get('characters'),dict):raise ValueError('기록 형식 오류')
        else:self.data={'version':1,'characters':{}}
    def observed(self,skill,*,verified):
        if verified is not True or not isinstance(skill,str) or not skill.strip():raise ValueError('학습 확인 필요')
        character=self.data['characters'].setdefault(self.character,{})
        character[skill]={'verified':True,'observed_at':time.time()}
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix='.skill-',suffix='.tmp',dir=str(self.path.parent))
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(self.data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
            os.replace(temp,self.path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
    def known(self,skill):
        return self.data['characters'].get(self.character,{}).get(skill,{}).get('verified') is True

def remember_verified_owned(ledger,owned):
    """Record positive owned-list observations only; absence is never proof.

    `owned` must be the output of the existing live paired-rows owned scan,
    after the caller verifies the current character against the ledger.
    """
    if not isinstance(owned,set) or not isinstance(getattr(ledger,'character',None),str) or not ledger.character.strip():
        raise ValueError('현재 캐릭터와 보유 도술 확인 필요')
    path=Path(ledger.path)
    if path.name!='owner-skill-goal.json' or path.parent.name!='settings':raise ValueError('도술 기록 경로 확인 필요')
    known={84:'생명의 흐름',68:'방패 밀기',89:'공간 결계'}
    store=LearnedSkills(path.parent.parent,getattr(ledger,'receipt_key',ledger.character))
    for sid,name in known.items():
        if sid in owned and not store.known(name):store.observed(name,verified=True)
