"""Durable individual quest decisions, independent of game input."""
from pathlib import Path
import copy,hashlib,json,math,re,time
from difflib import SequenceMatcher
from owner_timetable import save

def normalize(title):return re.sub(r'[\s·.,]+','',str(title))
def hangul(title):return re.sub('[^\uac00-\ud7a3]','',re.sub(r'^\s*\[[^\]]+\]','',str(title)))
def same_step(a,b):
    """Same title in another reading: chapter tag and step digits must agree."""
    a,b=str(a),str(b)
    if re.findall(r'\[[^\]]+\]',normalize(a))!=re.findall(r'\[[^\]]+\]',normalize(b)) or re.findall(r'\d+',a)!=re.findall(r'\d+',b):return False
    return SequenceMatcher(None,normalize(a),normalize(b)).ratio()>=.88
def quest_key(mode,title,objective=''):return mode+':'+hashlib.sha256((normalize(title)+'|'+normalize(objective)).encode()).hexdigest()[:24]

class QuestBook:
    def __init__(self,root,character,clock=time.time):
        if not character:raise ValueError('현재 캐릭터 확인 필요')
        self.path=Path(root)/'settings/owner-mission-journal.json';self.clock=clock
        if self.path.exists():
            self.data=json.loads(self.path.read_text(encoding='utf-8-sig'))
            if self.data.get('version')!=1 or not isinstance(self.data.get('characters'),dict):raise ValueError('임무 기록 형식 확인 필요')
        else:self.data={'version':1,'characters':{}}
        self.item=self.data['characters'].setdefault(character,{'quests':{},'active':None,'work':'main_quest'})
        self.item.setdefault('batch',{'number':0,'keys':[],'phase':'fill'})
    def commit(self):save(self.path,self.data)
    def observe(self,mode,title,**proof):
        original_key=quest_key(mode,title,proof.get('objective',''));key=original_key
        for _ in range(8):
            alias=self.item['quests'].get(key,{}).get('identity_alias_of')
            if not alias or alias not in self.item['quests'] or alias==key:break
            key=alias
        if key not in self.item['quests'] or self.item.get('active') not in (None,key):
            # Independently re-read row+objective can contain a minor glyph
            # variation. Preserve a uniquely matching prior identity/deaths;
            # chapter/step digits must match, and ambiguous matches stay new.
            from difflib import SequenceMatcher
            category=re.findall(r'\[[^\]]+\]',normalize(title));digits=re.findall(r'\d+',title);matches=[]
            for prior,entry in self.item['quests'].items():
                if entry.get('identity_alias_of'):continue
                if entry['mode']!=mode or re.findall(r'\[[^\]]+\]',normalize(entry['title']))!=category or re.findall(r'\d+',entry['title'])!=digits:continue
                names=SequenceMatcher(None,normalize(title),normalize(entry['title'])).ratio()
                a,b=proof.get('objective',''),entry.get('objective','')
                objectives=SequenceMatcher(None,normalize(a),normalize(b)).ratio() if a and b else 0
                if names>=.88 and objectives>=.80:matches.append(prior)
            active=self.item.get('active')
            if active in matches:key=active
            elif len(matches)==1:key=matches[0]
        if key!=original_key and original_key in self.item['quests']:
            previous=self.item['quests'][original_key];current=self.item['quests'][key]
            previous['identity_alias_of']=key
            current['deaths']=max(current.get('deaths',0),previous.get('deaths',0))
            if previous.get('block') and not current.get('block'):current['block']=copy.deepcopy(previous['block'])
        row=self.item['quests'].setdefault(key,{'mode':mode,'title':title,'deaths':0})
        row['title']=title
        row.update(last_seen=self.clock(),**proof)
        if proof.get('completed') is True:
            row.pop('block',None)
            if self.item.get('active')==key:self.item['active']=None
        self.commit();return key
    def activate(self,key):
        row=self.item['quests'][key]
        if row.get('completed'):raise ValueError('완료 임무 실행 금지')
        self.item.update(active=key,work=row['mode']);row['started_at']=self.clock();self.commit()
    def blocked(self,key,power,completed=()):
        row=self.item['quests'][key];block=row.get('block')
        if not block:return False
        reason=block['reason']
        if reason=='death':return power is None or block.get('baseline') is None or power<math.ceil(block['baseline']*1.15)
        if reason=='power':return power is None or not block.get('required') or power<block['required']
        if reason=='prerequisite':return block.get('prerequisite') not in completed
        # An unclassified condition is retried only when a new catalog sweep
        # independently proves this exact quest is actionable.
        return True
    def defer(self,key,reason,**details):
        if reason not in ('death','power','prerequisite','condition'):raise ValueError(reason)
        self.item['quests'][key]['block']={'reason':reason,'at':self.clock(),**details}
        if self.item.get('active')==key:self.item['active']=None
        self.commit()
    def batch_needs_fill(self,power):
        active=self.item.get('active')
        if active and self.eligible(active,power):return False
        batch=self.item['batch']
        if batch.get('phase') in ('fill','filling'):return True
        if not batch.get('keys') and not self.item.get('quests'):return True
        return False
    def start_batch(self):
        batch=self.item['batch']
        if batch.get('phase')=='filling':return
        self.item['batch']={'number':batch.get('number',0)+1,'keys':[],'phase':'filling','at':self.clock()};self.commit()
    def batch_add(self,key):
        batch=self.item['batch']
        if key not in batch['keys'] and len(batch['keys'])<20:batch['keys'].append(key);self.commit()
    def seal_batch(self):self.item['batch']['phase']='drain';self.commit()
    def refill_finished_batch(self,power):
        batch=self.item['batch']
        if batch.get('phase')!='drain' or not batch.get('keys'):return False
        if any(self.eligible(key,power) for key in batch['keys']):return False
        batch['phase']='fill';batch['finished_at']=self.clock();self.commit();return True
    def death(self,key,power):
        row=self.item['quests'][key];row['deaths']=row.get('deaths',0)+1
        if row['deaths']>=2:self.defer(key,'death',baseline=power)
        else:self.commit()
        return row['deaths']>=2
    def eligible(self,key,power,completed=()):
        row=self.item['quests'][key]
        return not row.get('legacy_step') and not row.get('identity_alias_of') and not row.get('completed') and row.get('suitable') is True and row.get('actionable') is True and not self.blocked(key,power,completed)
    def choose(self,keys,requested,power):
        complete={normalize(r['title']) for r in self.item['quests'].values() if r.get('completed')}
        active=self.item.get('active')
        # Recovery of another quest's prerequisite/power gate cannot preempt
        # the currently running individual quest, including across restart.
        if active in keys and self.eligible(active,power,complete):return active
        modes=('main_quest','sub_quest') if requested=='main_quest' else ('sub_quest',)
        for mode in modes:
            for key in keys:
                if mode=='sub_quest' and self.item['batch'].get('phase')=='drain' and key not in self.item['batch']['keys']:
                    block=self.item['quests'][key].get('block',{})
                    empty_accepted=not self.item['batch']['keys'] and self.item['quests'][key].get('accepted') is True
                    if not empty_accepted and not (block and not self.blocked(key,power,complete)) and not self.item['quests'][key].get('condition_recovered'):continue
                if self.item['quests'][key]['mode']==mode and self.eligible(key,power,complete):
                    row=self.item['quests'][key]
                    if row.get('block',{}).get('reason')=='death':row['deaths']=0
                    row.pop('block',None);self.commit();return key
        return None
    def chapter_reached(self,chapter):
        """The main story is on this chapter, so a hold naming an earlier one is out of date. Only a chapter name
        settles it: the saved title can misread ('전인' for '전언') and then never matched a finished quest, which
        held the very side story chapter 4 was waiting on. The row is read afresh before it runs."""
        changed=False
        for row in self.item['quests'].values():
            block=row.get('block') or {}
            if block.get('functional_hold') or block.get('reason') not in ('prerequisite','condition'):continue
            named=[int(n) for n in re.findall(r'\[\s*(\d+)\s*장\s*\]',str(block.get('prerequisite') or '')+' '+str(block.get('detail') or ''))]
            if named and max(named)<chapter:
                row.pop('block');row['condition_recovered']=True;changed=True
        if changed:self.commit()
        return changed
    def prerequisite_proved(self,key):
        # Called only after reading the selected quest detail without the
        # prior prerequisite condition, not because a timer elapsed.
        row=self.item['quests'][key];opened=False
        if row.get('block',{}).get('reason') in ('prerequisite','condition'):row.pop('block',None);opened=True
        # The objective is part of a step's key, so a main step whose wait ended comes back under a new key
        # and the old row stays held. The new row must still count as reopened, or it waits behind the story.
        if row.get('mode')=='main_quest':
            for other,entry in self.item['quests'].items():
                block=entry.get('block',{})
                if other==key or entry.get('mode')!='main_quest' or entry.get('completed') or block.get('functional_hold'):continue
                if block.get('reason') in ('prerequisite','condition') and same_step(row.get('title'),entry.get('title')):
                    entry.pop('block');opened=True
        if opened:row['condition_recovered']=True;self.commit()
    def story_finished(self,name):
        """Has the side story a main step names been seen finished? Its row can read 방랑! 도사, so close names count."""
        want=hangul(name)
        if len(want)<4:return False
        return any(r.get('mode')=='sub_quest' and r.get('completed') and SequenceMatcher(None,want,hangul(r.get('title'))).ratio()>=.86 for r in self.item['quests'].values())

def movement_distance(rows):
    values=set()
    for row in rows:
        if row.get('score',0)<.96:continue
        m=re.fullmatch(r'\s*([0-9]{1,5}(?:\.[0-9]+)?)\s*(m|미터)\s*',row['text'],re.I)
        if m:values.add(float(m[1]))
    return next(iter(values)) if len(values)==1 else None
