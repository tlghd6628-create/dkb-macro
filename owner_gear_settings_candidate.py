"""장비 목표 설정 후보. 게임 조작 및 강화/분해 로직은 포함하지 않는다."""
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from owner_growth_policy_candidate import GEAR_TARGETS, SKILL_REINFORCEMENT_TARGETS
from owner_blessing_priority_candidate import PATTERNS, validate_order, collect_rank_fields

GRADES = ('일반', '희귀', '영웅')
LEGACY_SKILLS = {'파멸', '강타', '강인'}
BLESSINGS = ('1번', '2번', '3번', '4번', '5번')
ENERGIES = ('생명', '여명', '몽환', '홍염')
DEFAULT = {'version': 1, 'recheck_minutes': 20, 'grades': {
    grade: {'enabled': False, 'enhance': target.enhance,
            'breakthrough': target.breakthrough, 'awaken': target.awakening}
    for grade, target in GEAR_TARGETS.items()
}, 'skills': {name: {'enabled': False, 'enhance': target, 'breakthrough': 0}
               for name, target in SKILL_REINFORCEMENT_TARGETS.items()},
    'individual': {}, 'album': {'mode': '조각 등록만'},
    'blessings': {name: {'enabled': False, 'enhance': 49, 'breakthrough': 0} for name in BLESSINGS},
    'energies': {name: {'enabled': False, 'stage': None} for name in ENERGIES},
    'blessing_equip': {'enabled': True, 'priorities': [], 'higher': False},
    # Higher grade first, by step (owner_upgrade_equip). Each kind has its own time in the timetable.
    'gear_equip': {'higher': False},
    # 가호 소환 (owner_blessing_summon): 10회 while ten tickets or more, 1회 for the rest.
    'blessing_summon': {'one': False, 'ten': False}}
# 높은 등급 우선 장착 is one switch now; the per-step ticks it replaced still read as it (owner_upgrade_equip.LEGACY).
EQUIP_STEPS = (('higher', '높은 등급 우선 장착'),)
EQUIP_LEGACY = ('normal_to_rare', 'rare_to_hero')
# A TEST result goes on its own line under its controls, as wide as they are and clipped there. Beside the button a
# longer text moved 기능 사용 and TEST, and a click meant for the checkbox started a second TEST (pc2 11-06); a box of
# fixed size beside them widened the page's columns instead.
def controls_line(parent, **grid):
    """(outer, line): grid the outer frame, pack the controls into line, and put the result under them."""
    outer = ttk.Frame(parent); outer.grid(**grid)
    line = ttk.Frame(outer); line.pack(side='top', anchor='w')
    return outer, line


def result_label(parent, variable):
    box = ttk.Frame(parent, width=1, height=18)
    box.pack_propagate(False)
    ttk.Label(box, textvariable=variable, anchor='w').pack(fill='both', expand=True)
    box.pack(side='top', fill='x')
    return box


def skill_catalog():
    """Reuse the existing public catalog; identifiers are not game addresses."""
    path = Path(__file__).with_name('skill_catalog.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    entries = data.get('all_skill_names')
    if not isinstance(entries, dict) or not entries:
        raise ValueError('도술 목록을 확인해 주세요.')
    result = {}
    for name, row in entries.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(row, dict) or row.get('style') not in SKILL_REINFORCEMENT_TARGETS:
            raise ValueError('도술 목록 형식을 확인해 주세요.')
        result[name] = row['style']
    return result


def validate(document):
    if not isinstance(document, dict) or document.get('version') != 1:
        raise ValueError('지원하지 않는 장비 설정 형식입니다.')
    interval=document.get('recheck_minutes',20)
    if type(interval) is not int or not 1<=interval<=1440:
        raise ValueError('재확인 주기는 1~1440분의 정수여야 합니다.')
    grades = document.get('grades')
    if not isinstance(grades, dict) or set(grades) != set(GRADES):
        raise ValueError('일반·희귀·영웅 설정이 모두 필요합니다.')
    for grade in GRADES:
        row = grades[grade]
        if not isinstance(row, dict) or type(row.get('enabled')) is not bool:
            raise ValueError(grade + ' 활성화 상태를 확인해 주세요.')
        for key, limit, label in (('enhance', 9999, '강화'), ('breakthrough', 9999, '돌파'), ('awaken', 9999, '각성')):
            value = row.get(key)
            if type(value) is not int or not 0 <= value <= limit:
                raise ValueError(f'{grade} {label}은 0~{limit}의 정수여야 합니다.')
    # Old settings predate this section. Preserve those documents and supply
    # defaults when read; never silently accept a partial or malformed section.
    if 'skills' in document:
        skills = document['skills']
        if not isinstance(skills, dict) or set(skills) not in (set(SKILL_REINFORCEMENT_TARGETS), LEGACY_SKILLS):
            raise ValueError('도술 강화 계열 설정을 확인해 주세요.')
        for name, row in skills.items():
            if not isinstance(row, dict) or type(row.get('enabled')) is not bool:
                raise ValueError(name + ' 활성화 상태를 확인해 주세요.')
            value = row.get('enhance')
            if type(value) is not int or not 0 <= value <= 9999:
                raise ValueError(name + ' 강화 목표는 0~9999의 정수여야 합니다.')
            value=row.get('breakthrough',0)
            if type(value) is not int or not 0<=value<=9999:
                raise ValueError(name+' 돌파 목표는 0~9999의 정수여야 합니다.')
    if 'individual' in document:
        rows = document['individual']
        if not isinstance(rows, dict) or len(rows) > 1000:
            raise ValueError('개별 도술 설정을 확인해 주세요.')
        for name, row in rows.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 100 or not isinstance(row, dict):
                raise ValueError('개별 도술 이름을 확인해 주세요.')
            if type(row.get('enabled')) is not bool:
                raise ValueError(name + ' 사용 여부를 확인해 주세요.')
            for key in ('awaken', 'breakthrough'):
                value = row.get(key)
                if value is not None and (type(value) is not int or not 0 <= value <= 9999):
                    raise ValueError(name + ' 목표는 빈칸 또는 0~9999의 정수여야 합니다.')
            if row['enabled'] and all(row.get(key) is None for key in ('awaken','breakthrough')):
                raise ValueError(name + ' 사용 시 각성 또는 돌파 목표를 입력해 주세요.')
    if 'album' in document:
        album = document['album']
        if not isinstance(album, dict) or album.get('mode') not in ('조각 등록만', '완성'):
            raise ValueError('화첩 처리 방식을 확인해 주세요.')
    if 'blessing_equip' in document:
        equip=document['blessing_equip']
        if not isinstance(equip,dict) or type(equip.get('enabled')) is not bool:
            raise ValueError('가호 장착 설정을 확인해 주세요.')
        validate_order(equip.get('priorities'))
    for section in ('blessing_equip','gear_equip'):
        if section in document:
            if not isinstance(document[section],dict) or any(type(document[section].get(key,False)) is not bool for key in ('higher',)+EQUIP_LEGACY):
                raise ValueError('높은 등급 우선 장착 설정을 확인해 주세요.')
    if 'blessing_summon' in document:
        summon=document['blessing_summon']
        if not isinstance(summon,dict) or any(type(summon.get(key,False)) is not bool for key in ('one','ten')):
            raise ValueError('가호 소환 설정을 확인해 주세요.')
    for section, names, fields in (('blessings', BLESSINGS, ('enhance','breakthrough')),
                                   ('energies', ENERGIES, ('stage',))):
        if section not in document:continue
        rows=document[section]
        if not isinstance(rows,dict) or set(rows)!=set(names):
            raise ValueError('성장 목표 목록을 확인해 주세요.')
        for name,row in rows.items():
            if not isinstance(row,dict) or type(row.get('enabled')) is not bool:
                raise ValueError(name+' 사용 여부를 확인해 주세요.')
            for field in fields:
                value=row.get(field)
                if value is not None and (type(value) is not int or not 0<=value<=9999):
                    raise ValueError(name+' 목표는 빈칸 또는 0~9999 정수여야 합니다.')
                if row['enabled'] and value is None:
                    raise ValueError(name+' 사용 시 목표를 입력해 주세요.')
    return document


class Store:
    def __init__(self, root, character):
        if not isinstance(character, str) or not character.strip():
            raise ValueError('서버와 캐릭터가 확인되어야 합니다.')
        ident = hashlib.sha256(character.strip().encode('utf-8')).hexdigest()[:24]
        self.path = Path(root) / 'settings' / ('owner-gear-settings-' + ident + '.json')

    def snapshot(self):
        try:raw=self.path.read_bytes()
        except FileNotFoundError:return copy.deepcopy(DEFAULT),'missing'
        revision=hashlib.sha256(raw).hexdigest()
        document = validate(json.loads(raw.decode('utf-8-sig')))
        document.setdefault('recheck_minutes',20)
        if 'skills' not in document:
            document['skills'] = copy.deepcopy(DEFAULT['skills'])
        elif set(document['skills']) == LEGACY_SKILLS:
            migrated = copy.deepcopy(DEFAULT['skills'])
            migrated.update(document['skills'])
            document['skills'] = migrated
        for row in document['skills'].values():row.setdefault('breakthrough',0)
        document.setdefault('individual', {})
        document.setdefault('album', copy.deepcopy(DEFAULT['album']))
        document.setdefault('blessings',copy.deepcopy(DEFAULT['blessings']))
        document.setdefault('energies',copy.deepcopy(DEFAULT['energies']))
        document.setdefault('blessing_equip',copy.deepcopy(DEFAULT['blessing_equip']))
        document.setdefault('gear_equip',copy.deepcopy(DEFAULT['gear_equip']))
        for section in ('blessing_equip','gear_equip'):
            row=document[section]
            row.setdefault('higher',any(row.get(key) is True for key in EQUIP_LEGACY))
        document.setdefault('blessing_summon',copy.deepcopy(DEFAULT['blessing_summon']))
        return document,revision

    def read(self):
        return self.snapshot()[0]

    def revision(self):
        try:return hashlib.sha256(self.path.read_bytes()).hexdigest()
        except FileNotFoundError:return 'missing'

    def write(self, value, *, expected_revision=None):
        validate(value)
        if expected_revision is not None and self.revision()!=expected_revision:
            raise ValueError('다른 창에서 설정이 변경되었습니다. 설정창을 닫고 다시 열어 확인해 주세요.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.gear-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
                f.flush(); os.fsync(f.fileno())
            if expected_revision is not None and self.revision()!=expected_revision:
                raise ValueError('다른 창에서 설정이 변경되었습니다. 설정창을 닫고 다시 열어 확인해 주세요.')
            os.replace(name, self.path)
        finally:
            if os.path.exists(name): os.unlink(name)


class GearSettings:
    def __init__(self, parent, root, character, *, switches=None, embedded=False):
        self.store = Store(root, character)
        self.switches=switches
        self.feature_vars={}
        self.value,self.open_revision = self.store.snapshot()
        self.embedded=embedded
        self.window = ttk.Frame(parent) if embedded else tk.Toplevel(parent)
        if embedded:self.window.pack(fill='both',expand=True)
        else:self.window.title('성장 설정')
        self.current_values=[]
        outer = ttk.Frame(self.window, padding=12); outer.pack(fill='both', expand=True)
        self.current_hint=tk.StringVar(self.window,value='현재: 최근 확인값')
        ttk.Label(outer,textvariable=self.current_hint).pack(anchor='e',pady=(0,4))
        tabs = ttk.Notebook(outer); tabs.pack(fill='both', expand=True);self.tabs=tabs
        box = ttk.Frame(tabs, padding=8); tabs.add(box, text='장비')
        self.feature_switch(box,'equipment',column=4,columnspan=4)
        self.recheck_minutes=tk.StringVar(self.window,value=str(self.value['recheck_minutes']))
        ttk.Label(box,text='재확인 주기(분)').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,8))
        ttk.Spinbox(box,textvariable=self.recheck_minutes,from_=1,to=1440,width=6).grid(row=0,column=2,sticky='w',pady=(0,8))
        for column, label in enumerate(('등급', '사용', '강화 목표', '돌파 목표', '각성 목표')):
            ttk.Label(box, text=label).grid(row=1, column=column, padx=6, sticky='w')
        self.vars = {}
        for index, grade in enumerate(GRADES, start=2):
            row = self.value['grades'][grade]
            v = {'enabled': tk.BooleanVar(self.window, value=row['enabled'])}
            for key in ('enhance', 'breakthrough', 'awaken'):
                v[key] = tk.StringVar(self.window, value=str(row[key]))
            self.vars[grade] = v
            ttk.Label(box, text=grade).grid(row=index, column=0, sticky='w', pady=5)
            ttk.Checkbutton(box, variable=v['enabled']).grid(row=index, column=1)
            for target_column,key in ((2,'enhance'),(3,'breakthrough'),(4,'awaken')):
                ttk.Entry(box,textvariable=v[key],width=6).grid(row=index,column=target_column,padx=4)
        self.gear_steps=self.equip_line(box,'gear',self.value['gear_equip'],row=5,columnspan=8)
        self.worn_heading(box,'착용 장비 · 최근 확인값',row=6,columnspan=8)
        equipped=ttk.Treeview(box,columns=('slot','grade','enhance','breakthrough','awaken'),show='headings',height=5)
        for key,text in zip(equipped['columns'],('부위','등급','강화','돌파','각성')):
            equipped.heading(key,text=text);equipped.column(key,width=78,anchor='center',stretch=True)
        equipped.grid(row=7,column=0,columnspan=8,sticky='nsew')
        scroll=ttk.Scrollbar(box,orient='vertical',command=equipped.yview);equipped.configure(yscrollcommand=scroll.set)
        scroll.grid(row=7,column=8,sticky='ns')
        self._equipped_display=None
        skills = ttk.Frame(tabs, padding=8); tabs.add(skills, text='도술')
        self.feature_switch(skills,'skills')
        skill_tabs=ttk.Notebook(skills);skill_tabs.grid(row=1,column=0,columnspan=8,sticky='nsew')
        skills=ttk.Frame(skill_tabs,padding=4);skill_tabs.add(skills,text='계열 강화·돌파')
        for column,label in enumerate(('계열','사용','강화 현재','목표','돌파 현재','목표')):
            ttk.Label(skills,text=label).grid(row=1,column=column,padx=5,sticky='w')
        self.skill_vars = {}
        for index, name in enumerate(SKILL_REINFORCEMENT_TARGETS):
            row = self.value['skills'][name]
            v = {'enabled': tk.BooleanVar(self.window,value=row['enabled']),
                 'enhance': tk.StringVar(self.window,value=str(row['enhance'])),
                 'breakthrough':tk.StringVar(self.window,value=str(row.get('breakthrough',0)))}
            self.skill_vars[name] = v
            grid_row=2+index
            ttk.Label(skills,text=name).grid(row=grid_row,column=0,sticky='w',pady=3)
            ttk.Checkbutton(skills,variable=v['enabled']).grid(row=grid_row,column=1)
            for current_col,target_col,field in ((2,3,'enhance'),(4,5,'breakthrough')):
                current=tk.StringVar(self.window,value='—')
                ttk.Label(skills,textvariable=current).grid(row=grid_row,column=current_col)
                self.current_values.append(('skills',name,field,current))
                ttk.Entry(skills,textvariable=v[field],width=6).grid(row=grid_row,column=target_col,padx=5)
        from owner_individual_skill_ui_candidate import IndividualSkillEditor
        from owner_growth_current import current_value
        individual = ttk.Frame(skill_tabs, padding=8); skill_tabs.add(individual,text='개별 각성')
        self.individual = IndividualSkillEditor(individual,self.value['individual'],skill_catalog(),
            current_value=lambda name:current_value(root,character,'individual',name,'awaken'))
        blessings=ttk.Frame(tabs,padding=8);tabs.add(blessings,text='가호')
        self.feature_switch(blessings,'blessings')
        # A blessing has no breakthrough in the game. Its second goal is awakening, saved under the old field's name.
        for col,label in enumerate(('장착 칸','사용','강화 목표','각성 목표')):
            ttk.Label(blessings,text=label).grid(row=1,column=col,padx=5,sticky='w')
        self.blessing_vars={}
        for index,name in enumerate(BLESSINGS,start=2):
            row=self.value['blessings'][name]
            var={'enabled':tk.BooleanVar(self.window,value=row['enabled'])}
            for field in ('enhance','breakthrough'):
                var[field]=tk.StringVar(self.window,value='' if row[field] is None else str(row[field]))
            self.blessing_vars[name]=var
            ttk.Label(blessings,text=name).grid(row=index,column=0,sticky='w',pady=5)
            ttk.Checkbutton(blessings,variable=var['enabled']).grid(row=index,column=1)
            for target_col,field in ((2,'enhance'),(3,'breakthrough')):
                ttk.Entry(blessings,textvariable=var[field],width=6).grid(row=index,column=target_col,padx=4)
        ttk.Separator(blessings,orient='horizontal').grid(row=7,column=0,columnspan=6,sticky='ew',pady=8)
        equip=self.value['blessing_equip']
        self.blessing_equip=tk.BooleanVar(self.window,value=equip['enabled'])
        self.blessing_steps=self.equip_line(blessings,'blessing',equip,row=8,columnspan=6)
        ttk.Label(blessings,text='같은 등급 문양 순위').grid(row=9,column=0,columnspan=6,sticky='w',pady=(8,3))
        self.blessing_rank=[]
        ranks=ttk.Frame(blessings);ranks.grid(row=10,column=0,columnspan=6,sticky='w')
        for index in range(5):
            v=tk.StringVar(self.window,value=equip['priorities'][index] if index<len(equip['priorities']) else '')
            self.blessing_rank.append(v)
            ttk.Label(ranks,text=str(index+1)).grid(row=0,column=index,padx=3)
            ttk.Combobox(ranks,textvariable=v,values=('',)+PATTERNS,state='readonly',width=7).grid(row=1,column=index,padx=3)
        # Row 11 is the settings console's 가호 일괄 획득 box (owner_settings_console), which hid this line there (pc2 11-06);
        # it sits under the worn table on the right, where the page has room.
        summon_box,summon=controls_line(blessings,row=8,column=6,rowspan=2,sticky='nw',padx=(24,0),pady=(9,3))
        ttk.Label(summon,text='가호 소환').pack(side='left')
        self.summon_vars={key:tk.BooleanVar(self.window,value=self.value['blessing_summon'].get(key) is True) for key in ('one','ten')}
        for key,label in (('one','1회'),('ten','10회')):
            ttk.Checkbutton(summon,text=label,variable=self.summon_vars[key]).pack(side='left',padx=(10,0))
        summon_result=tk.StringVar(self.window,value='')
        ttk.Button(summon,text='TEST',width=6,command=lambda:self.summon_test(summon_result)).pack(side='left',padx=(10,8))
        result_label(summon_box,summon_result)
        # Beside the targets: below the reward box the page runs out of height.
        self.worn_heading(blessings,'착용 가호 · 최근 확인값',row=0,column=6,columnspan=1,padx=(24,0))
        worn_blessings=ttk.Treeview(blessings,columns=('slot','kind','grade','enhance','awaken'),show='headings',height=5)
        for key,text,width in zip(worn_blessings['columns'],('칸','종류','등급','강화','각성'),(44,62,52,46,46)):
            worn_blessings.heading(key,text=text);worn_blessings.column(key,width=width,anchor='center',stretch=False)
        worn_blessings.grid(row=1,column=6,rowspan=6,sticky='nw',padx=(24,0))
        self._blessing_display=None
        energies=ttk.Frame(tabs,padding=8);tabs.add(energies,text='기운')
        self.feature_switch(energies,'energies')
        for col,label in enumerate(('기운','사용','현재','목표 단계')):
            ttk.Label(energies,text=label).grid(row=1,column=col,padx=5,sticky='w')
        self.energy_vars={}
        for index,name in enumerate(ENERGIES,start=2):
            row=self.value['energies'][name]
            var={'enabled':tk.BooleanVar(self.window,value=row['enabled']),
                 'stage':tk.StringVar(self.window,value='' if row['stage'] is None else str(row['stage']))}
            self.energy_vars[name]=var
            ttk.Label(energies,text=name).grid(row=index,column=0,sticky='w',pady=5)
            ttk.Checkbutton(energies,variable=var['enabled']).grid(row=index,column=1)
            current=tk.StringVar(self.window,value='—')
            ttk.Label(energies,textvariable=current).grid(row=index,column=2)
            self.current_values.append(('energies',name,'stage',current))
            ttk.Entry(energies,textvariable=var['stage'],width=7).grid(row=index,column=3,padx=5)
        album = ttk.Frame(tabs,padding=8);tabs.add(album,text='화첩')
        self.feature_switch(album,'album')
        self.album_mode=tk.StringVar(self.window,value=self.value['album']['mode'])
        ttk.Label(album,text='처리 방식').grid(row=1,column=0,sticky='w',pady=7)
        ttk.Combobox(album,textvariable=self.album_mode,values=('조각 등록만','완성'),state='readonly',width=16).grid(row=1,column=1,padx=8)
        ttk.Label(album,text='완성: 요혼석 사용').grid(row=2,column=0,columnspan=2,sticky='w')
        ttk.Button(outer, text='성장 설정 저장' if embedded else '저장 후 닫기', command=self.save).pack(anchor='e',pady=(8,0))
        def refresh_current():
            if not self.window.winfo_exists():return
            from owner_growth_current import last_observed_at
            from owner_growth_current import equipped_rows
            display=equipped_rows(root,character)
            if display!=self._equipped_display:
                equipped.delete(*equipped.get_children())
                for row in display:equipped.insert('', 'end',values=row)
                self._equipped_display=display
            from owner_growth_current import blessing_rows
            shown=blessing_rows(root,character)
            if shown!=self._blessing_display:
                worn_blessings.delete(*worn_blessings.get_children())
                for row in shown:worn_blessings.insert('', 'end',values=row)
                self._blessing_display=shown
            from owner_growth_current import current_value
            for section,name,field,var in self.current_values:var.set(current_value(root,character,section,name,field))
            self.individual.refresh_current()
            stamp=last_observed_at(root,character)
            if stamp:
                import datetime
                self.current_hint.set('최근 확인 '+datetime.datetime.fromtimestamp(stamp).strftime('%m/%d %H:%M:%S'))
            self.window.after(1000,refresh_current)
        refresh_current()

    def feature_switch(self,parent,section,**layout):
        if self.switches is None:return
        value=tk.BooleanVar(self.window,value=self.switches.initial[section])
        self.feature_vars[section]=value
        outer,line=controls_line(parent,row=0,sticky='w',pady=(0,8),**dict({'column':0,'columnspan':6},**layout))
        check=ttk.Checkbutton(line,text='기능 사용',variable=value);check.pack(side='left')
        if not self.switches.editable[section]:check.configure(state='disabled')
        result=tk.StringVar(self.window,value='')
        test=ttk.Button(line,text='TEST',width=6,command=lambda:self.test_request(section,result))
        test.pack(side='left',padx=(10,8))
        result_label(outer,result)

    def test_request(self,section,result):
        """Set by the settings console; alone in a separate window it has no worker to run on."""
        result.set('세부설정 창에서 실행해 주세요')

    def worn_heading(self,parent,title,*,row,columnspan,column=0,padx=0):
        outer,line=controls_line(parent,row=row,column=column,columnspan=columnspan,sticky='w',pady=(9,3),padx=padx)
        ttk.Label(line,text=title).pack(side='left')
        result=tk.StringVar(self.window,value='')
        ttk.Button(line,text='TEST',width=6,command=lambda:self.worn_test(result)).pack(side='left',padx=(10,8))
        result_label(outer,result)

    def worn_test(self,result):
        """Set by the settings console, like test_request."""
        result.set('세부설정 창에서 실행해 주세요')

    def equip_line(self,parent,kind,section,*,row,columnspan):
        """높은 등급 우선 장착: one tick, and its TEST. The time is in the timetable."""
        outer,line=controls_line(parent,row=row,column=0,columnspan=columnspan,sticky='w',pady=(9,3))
        steps={}
        for key,text in EQUIP_STEPS:
            steps[key]=tk.BooleanVar(self.window,value=section.get(key) is True)
            ttk.Checkbutton(line,text=text,variable=steps[key]).pack(side='left')
        result=tk.StringVar(self.window,value='')
        ttk.Button(line,text='TEST',width=6,command=lambda:self.equip_test(kind,result)).pack(side='left',padx=(10,8))
        result_label(outer,result)
        return steps

    def equip_test(self,kind,result):
        """Set by the settings console, like test_request."""
        result.set('세부설정 창에서 실행해 주세요')

    def summon_test(self,result):
        """Set by the settings console, like test_request."""
        result.set('세부설정 창에서 실행해 주세요')

    def save(self):
        try:
            value=copy.deepcopy(self.value)
            raw=self.recheck_minutes.get().strip()
            if not raw.isascii() or not raw.isdecimal():raise ValueError('재확인 주기는 정수로 입력해 주세요.')
            value['recheck_minutes']=int(raw)
            value['individual']=self.individual.export()
            value['album']['mode']=self.album_mode.get()
            steps={key:var.get() for key,var in self.blessing_steps.items()}
            # The old single switch (the original priority equip, at the old size) follows it; the old step ticks go.
            for key in EQUIP_LEGACY:value['blessing_equip'].pop(key,None);value['gear_equip'].pop(key,None)
            value['blessing_equip'].update(enabled=any(steps.values()),**steps,
                                           priorities=collect_rank_fields([v.get() for v in self.blessing_rank]))
            value['gear_equip'].update({key:var.get() for key,var in self.gear_steps.items()})
            value['blessing_summon'].update({key:var.get() for key,var in self.summon_vars.items()})
            for grade, v in self.vars.items():
                row = value['grades'][grade]
                row['enabled']=v['enabled'].get()
                for key in ('enhance', 'breakthrough', 'awaken'):
                    raw = v[key].get().strip()
                    if not raw.isdecimal() or not raw.isascii():
                        raise ValueError(grade + ' 수치는 0 이상의 정수로 입력해 주세요.')
                    row[key] = int(raw)
                value['grades'][grade] = row
            for name, v in self.skill_vars.items():
                row=value['skills'][name];row['enabled']=v['enabled'].get()
                for field in ('enhance','breakthrough'):
                    raw=v[field].get().strip()
                    if not raw.isdecimal() or not raw.isascii():
                        raise ValueError(name+' 목표는 0 이상의 정수로 입력해 주세요.')
                    row[field]=int(raw)
            for section, variables, fields in (('blessings',self.blessing_vars,('enhance','breakthrough')),
                                               ('energies',self.energy_vars,('stage',))):
                for name, v in variables.items():
                    row=value[section][name]
                    row['enabled']=v['enabled'].get()
                    for field in fields:
                        raw=v[field].get().strip()
                        if raw and (not raw.isdecimal() or not raw.isascii()):
                            raise ValueError(name+' 목표는 빈칸 또는 0 이상의 정수여야 합니다.')
                        row[field]=int(raw) if raw else None
                    value[section][name]=row
            validate(value)
            def write_goals():
                self.store.write(value,expected_revision=self.open_revision)
                self.open_revision=self.store.revision();self.value=copy.deepcopy(value)
            if self.switches is None:write_goals()
            else:
                wanted={section:var.get() for section,var in self.feature_vars.items()}
                self.switches.save(wanted,write_goals)
        except (ValueError, OSError) as error:
            messagebox.showerror('장비 목표 설정', str(error), parent=self.window); return
        if not self.embedded:self.window.destroy()
        return True


def open_settings(parent, root, character, *, gui=None, embedded=False):
    # These are configuration intentions, not game/character receipts. Keep
    # the existing user's enable choices visible even before the first run.
    from owner_gear_migration_candidate import initialize_missing
    try:
        native=json.loads((Path(root)/'settings/auto-settings.json').read_text(encoding='utf-8-sig'))
        initialize_missing(root,character,native.get('values'))
    except (OSError,ValueError,TypeError):pass
    switches=None
    if gui is not None:
        from owner_settings_layout import GrowthSwitches
        switches=GrowthSwitches(gui,character)
    return GearSettings(parent, root, character,switches=switches,embedded=embedded)
