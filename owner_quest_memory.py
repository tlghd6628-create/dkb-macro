"""Durable, per-character combat blocks; no input or screen assumptions.

15 percent is an operational retry policy, not a published game requirement.
Unknown chapter/power is retained as unknown. Functional failures never block.
"""
import json,math,time
MODES=('main_quest','sub_quest','auto_mode')
QUESTS=MODES[:2]
RETRY_RATIO=1.15


class QuestMemory:
    def load_records(self):
        if not self.path.exists():return {}
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            records=data['characters']
            if not isinstance(records,dict) or any(not isinstance(v,dict) for v in records.values()):raise ValueError('characters')
            return records
        except (OSError,ValueError,KeyError,TypeError) as exc:
            raise RuntimeError('육성 기록을 읽지 못했습니다. 기존 파일을 보존하고 확인이 필요합니다.') from exc

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp')
        try:
            temp.write_text(json.dumps({'schema':'owner-progression-v2','retry_growth_ratio':RETRY_RATIO,
                                       'characters':self.records},ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(self.path)
        except OSError as exc:
            raise RuntimeError('육성 기록 저장 실패 · 재시작 후 중복 도전을 막기 위해 진행을 보류합니다.') from exc

    def record(self):
        if self.character is None:return None
        record=self.records.setdefault(self.character,{'attempted_milestones':[]})
        record.setdefault('quest_blocks',{})
        record.setdefault('work_mode',None)
        return record

    def restore_character(self):
        record=self.record()
        self.deaths={m:int(record['quest_blocks'].get(m,{}).get('deaths',0)) for m in QUESTS}
        self.work_mode=record.get('work_mode')
        self.route=({'main_quest':'main','sub_quest':'sub'}.get(self.work_mode,'main') if self.work_mode!='auto_mode'
                    else ('hunt' if record['quest_blocks'].get('sub_quest',{}).get('blocked') else 'auto'))
        # This is a fresh, two-frame power reading for this character. If the
        # failure had no fresh power, establish a baseline; never assume zero.
        for item in record['quest_blocks'].values():
            if item.get('blocked') and item.get('failed_power') is None and self.power is not None:
                item.update(failed_power=self.power,retry_after_power=math.ceil(self.power*RETRY_RATIO),
                            baseline_source='first_fresh_read_after_failure')
        record.update(last_level=self.level,last_power=self.power,last_observed_at=time.strftime('%Y-%m-%dT%H:%M:%S'))
        self.save()

    def begin_work(self,mode):
        if mode not in MODES:return
        self.work_mode=mode
        self.route=({'main_quest':'main','sub_quest':'sub'}[mode] if mode!='auto_mode'
                    else ('hunt' if self.blocked('sub_quest') else 'auto'))
        record=self.record()
        if record is not None and record.get('work_mode')!=mode:
            record['work_mode']=mode;self.save()

    def set_quest(self,mode,description):
        """Optional two-frame text evidence, never a guessed chapter."""
        if mode in QUESTS:self.quest_labels[mode]=description

    def remember_death(self,mode):
        if mode not in QUESTS:return
        record=self.record()
        if record is None:return
        old=record['quest_blocks'].get(mode,{})
        count=self.deaths.get(mode,0)
        fresh=self.power is not None and time.monotonic()-self.observed<=300
        item=dict(old,deaths=count,last_failure_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
                  cause='DEATH_RECOVERED',quest=self.quest_labels.get(mode),
                  chapter=(self.quest_labels.get(mode) or {}).get('chapter'))
        if count>=2:
            power=self.power if fresh else None
            history=list(old.get('history',[]))[-19:]
            history.append({'power':power,'at':item['last_failure_at'],'cause':'two_confirmed_deaths',
                            'quest':item['quest']})
            item.update(blocked=True,failed_power=power,
                        retry_after_power=math.ceil(power*RETRY_RATIO) if power is not None else None,
                        baseline_source='fresh_inventory' if fresh else 'pending_fresh_inventory',history=history)
        record['quest_blocks'][mode]=item
        self.save()

    def blocked(self,mode):
        record=self.record()
        return bool(record and record['quest_blocks'].get(mode,{}).get('blocked'))

    def eligible(self,mode):
        record=self.record();item=record['quest_blocks'].get(mode,{}) if record else {}
        threshold=item.get('retry_after_power')
        return bool(item.get('blocked') and threshold is not None and self.power is not None
                    and time.monotonic()-self.observed<=120 and self.power>=threshold)

    def choose_mode(self,requested,*,growth_retry=True):
        """Select without granting a retry. A separate durable grant precedes it."""
        if requested not in MODES or self.character is None:return requested
        main=self.blocked('main_quest');sub=self.blocked('sub_quest')
        if requested=='main_quest':
            if not main or (growth_retry and self.eligible('main_quest')):return requested
            return 'sub_quest' if not sub or (growth_retry and self.eligible('sub_quest')) else 'auto_mode'
        if requested=='sub_quest':
            return 'auto_mode' if sub and not (growth_retry and self.eligible('sub_quest')) else requested
        # A manually selected hunt without prior combat blocks stays hunting.
        if growth_retry and main and self.eligible('main_quest'):return 'main_quest'
        if growth_retry and sub and self.eligible('sub_quest'):return 'sub_quest'
        return requested

    def grant_retry(self,mode):
        if not self.eligible(mode):return False
        item=self.record()['quest_blocks'][mode]
        item.update(blocked=False,deaths=0,retry_granted_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
                    retry_power=self.power)
        self.deaths[mode]=0
        self.save()  # Fail closed before starting any new combat attempt.
        return True

    def has_blocks(self):
        return any(any(i.get('blocked') for i in r.get('quest_blocks',{}).values()) for r in self.records.values())
