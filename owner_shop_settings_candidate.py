"""Private shop settings editor. Settings only: never sends a game input or purchase.

The 21-name seed is a community catalogue, not proof of the current game UI.
Remote availability and limits must be checked independently in-game.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

SOURCE = 'https://kkaebi.gg/shop'
SHOP_NAMES = {'town': '일반 잡화상점', 'remote': '원격 잡화상점'}
DEFAULT_COIN_RESERVE = 100000
NAMES = ([f'{n}단 체력 회복 물약' for n in range(1, 5)] +
         ['영웅 장비 강화 비법서', '영웅 가호의 정수', '전설 장비 강화 비법서',
          '전설 가호의 정수'] +
         [f'{name} 도술 강화 요령서' for name in
          ('절명', '연타', '강타', '척살', '저격', '주술', '파멸', '강인',
           '기동', '기만', '헌신', '제압')] + ['천요석'])


def initial_rows():
    return [{'shop': shop, 'name': name, 'enabled': False, 'mode': 'quantity',
             'quantity': 1, 'verification': ('커뮤니티 목록·게임 확인 필요' if shop == 'town'
                         else '원격 판매 여부 미확인'), 'source': SOURCE}
            for shop in SHOP_NAMES for name in NAMES]


def validate(rows):
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError('품목 목록이 올바르지 않습니다.')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('shop') not in SHOP_NAMES:
            raise ValueError('상점을 확인해 주세요.')
        name = row.get('name')
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError('품목 이름을 입력해 주세요.')
        key = (row['shop'], name.strip().casefold())
        if key in seen:
            raise ValueError('같은 상점에 이름이 중복된 품목이 있습니다.')
        seen.add(key)
        if type(row.get('enabled')) is not bool or row.get('mode') not in ('quantity', 'max'):
            raise ValueError('구매 설정을 확인해 주세요.')
        if type(row.get('quantity')) is not int or not 1 <= row['quantity'] <= 999999:
            raise ValueError('수량은 1~999999 사이의 정수여야 합니다.')
        for key in ('source', 'verification'):
            if not isinstance(row.get(key), str) or len(row[key]) > 500:
                raise ValueError('출처 또는 확인 상태가 올바르지 않습니다.')
    return rows


class ShopSettingsStore:
    def __init__(self, root, character):
        if not isinstance(character, str) or not character.strip():
            raise ValueError('캐릭터가 확인된 후 설정할 수 있습니다.')
        ident = hashlib.sha256(character.strip().encode('utf-8')).hexdigest()[:24]
        self.path = Path(root) / 'settings' / ('owner-shop-settings-' + ident + '.json')

    def read(self):
        return self.read_document()['items']

    def read_document(self):
        return self.snapshot()[0]

    def snapshot(self):
        if not self.path.exists():
            return {'version': 1, 'items': initial_rows(), 'coin_reserve': DEFAULT_COIN_RESERVE}, 'missing'
        raw=self.path.read_bytes()
        obj = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(obj, dict) or obj.get('version') != 1:
            raise ValueError('알 수 없는 상점 설정 형식입니다.')
        validate(obj.get('items'))
        reserve = obj.get('coin_reserve')
        if reserve is not None and (type(reserve) is not int or not 0 <= reserve <= 10**12):
            raise ValueError('남길 엽전은 0 이상 정수여야 합니다.')
        obj['coin_reserve']=reserve
        if type(obj.get('enabled',True)) is not bool:raise ValueError('상점 사용 설정 확인 필요')
        return obj,hashlib.sha256(raw).hexdigest()

    def revision(self):
        try:return hashlib.sha256(self.path.read_bytes()).hexdigest()
        except FileNotFoundError:return 'missing'

    def merge_observed(self, shop, names):
        """Add screen-observed suggestions disabled; never alter selections."""
        if shop not in SHOP_NAMES or not isinstance(names,list) or len(names)>100:
            raise ValueError('상점 판독 목록을 확인해 주세요.')
        document,revision=self.snapshot();rows=document['items'];seen={(r['shop'],''.join(r['name'].split()).casefold()) for r in rows};added=[]
        for name in names:
            if not isinstance(name,str):continue
            name=name.strip()
            if not name or len(name)>100 or any(ord(c)<32 for c in name):continue
            key=(shop,''.join(name.split()).casefold())
            if key in seen:continue
            if len(rows)>=500:break
            rows.append({'shop':shop,'name':name,'enabled':False,'mode':'quantity','quantity':1,
                         'verification':'화면 판독 후보 · 실제 판매·이름 재확인 필요','source':'게임 화면 판독'})
            seen.add(key);added.append(name)
        if added:self.write(rows,document['coin_reserve'],expected_revision=revision)
        return added

    def write(self, rows, coin_reserve=None, *, expected_revision=None, enabled=None):
        validate(rows)
        if coin_reserve is not None and (type(coin_reserve) is not int or not 0 <= coin_reserve <= 10**12):
            raise ValueError('남길 엽전은 0 이상 정수여야 합니다.')
        document,revision=self.snapshot()
        if expected_revision is not None and revision!=expected_revision:
            raise ValueError('다른 창에서 변경된 설정입니다. 다시 열어 확인해 주세요.')
        document.update(version=1,items=rows,coin_reserve=coin_reserve)
        if enabled is not None:
            if type(enabled) is not bool:raise ValueError('상점 사용 설정 확인 필요')
            document['enabled']=enabled
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.owner-shop-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            if expected_revision is not None and self.revision()!=expected_revision:
                raise ValueError('다른 창에서 변경된 설정입니다. 다시 열어 확인해 주세요.')
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


TARGET_CHOICES=tuple(range(1,51))+('최대',)
SCREEN_GUESS='게임 화면 판독'

def target_text(row):
    return '최대' if row['mode']=='max' else str(row['quantity'])

def one_list(items):
    """One row per item, in saved order. Which shop buys it depends on the membership at run time.

    Potions have their own setting, and a misread name the shop screen once added is not an item.
    """
    rows={}
    for row in items:
        name=row['name']
        if '물약' in name or (row.get('source')==SCREEN_GUESS and not row['enabled']):
            continue
        held=rows.get(name)
        if held is None:
            rows[name]=dict(row)
        elif row['enabled'] and not held['enabled']:
            rows[name].update(row)
    return list(rows.values())

def both_shops(rows):
    return [dict(row,shop=shop) for shop in SHOP_NAMES for row in rows]


class ShopSettings:
    SWITCH = '설정 상품 구매 사용'
    # The 단각 교환 table (owner_seal_shop) is this same table over its own file.
    def make_store(self, root, character): return ShopSettingsStore(root, character)
    def rows_of(self, document): return one_list(document['items'])
    def saved_rows(self, rows): return both_shops(rows)
    def check(self, rows): return validate(self.saved_rows(rows))
    def new_row(self):
        return dict(shop='remote', name='', enabled=False, mode='quantity', quantity=1,
                    verification='사용자 추가·게임 확인 필요', source='사용자 입력')

    def __init__(self, parent, root, character, *, embedded=False):
        self.store = self.make_store(root, character)
        document,self.open_revision = self.store.snapshot()
        self.rows = self.rows_of(document)
        self.embedded=embedded
        self.window = ttk.Frame(parent) if embedded else tk.Toplevel(parent)
        if embedded:self.window.pack(fill='both',expand=True)
        else:
            self.window.title('잡화상점 구매 설정');self.window.geometry('640x520')
        top = ttk.Frame(self.window, padding=10)
        top.pack(fill='both', expand=True)
        self.enabled=tk.BooleanVar(self.window,value=document.get('enabled',True))
        self.enabled_row=ttk.Frame(top);self.enabled_row.pack(fill='x',pady=(0,8))
        ttk.Checkbutton(self.enabled_row,text=self.SWITCH,variable=self.enabled).pack(side='left')
        table = ttk.Frame(top)
        table.pack(fill='both', expand=True)
        tree = ttk.Treeview(table, columns=('order', 'name', 'enabled', 'target'), show='headings', selectmode='browse')
        for col, title, width, stretch in (('order', '순위', 50, False), ('name', '품목', 300, True), ('enabled', '사용', 60, False), ('target', '목표', 90, False)):
            tree.heading(col, text=title)
            tree.column(col, width=width, stretch=stretch)
        bar = ttk.Scrollbar(table, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y'); tree.pack(fill='both', expand=True)
        tree.bind('<ButtonRelease-1>', self.cell_clicked)
        tree.bind('<Double-1>', self.rename_clicked)
        self.tree = tree
        buttons = ttk.Frame(top); buttons.pack(fill='x', pady=8)
        ttk.Button(buttons, text='품목 추가', command=self.add).pack(side='left')
        ttk.Button(buttons, text='선택 삭제', command=self.delete).pack(side='left', padx=4)
        ttk.Button(buttons, text='▲ 위로', command=lambda: self.move(-1)).pack(side='left', padx=(12, 4))
        ttk.Button(buttons, text='▼ 아래로', command=lambda: self.move(1)).pack(side='left')
        ttk.Button(buttons, text='저장 후 닫기', command=self.save).pack(side='right')
        self.refresh()

    def add_test(self,request):
        result=tk.StringVar(self.enabled_row)
        ttk.Button(self.enabled_row,text='TEST',width=6,command=lambda:request(result)).pack(side='left',padx=(8,12))
        ttk.Label(self.enabled_row,textvariable=result).pack(side='left')

    def cell_clicked(self, event):
        tree = self.tree
        row_id = tree.identify_row(event.y)
        if tree.identify_region(event.x, event.y) != 'cell' or not row_id:
            return
        column = tree.identify_column(event.x)
        if column == '#3':
            row = self.rows[int(row_id)]
            row['enabled'] = not row['enabled']
            tree.set(row_id, 'enabled', '☑' if row['enabled'] else '☐')
        elif column == '#4':
            self.edit_target(row_id)

    def rename_clicked(self, event):
        tree = self.tree
        row_id = tree.identify_row(event.y)
        if row_id and tree.identify_region(event.x, event.y) == 'cell' and tree.identify_column(event.x) == '#2':
            self.edit(int(row_id))

    def edit_target(self, row_id):
        """The target cell edits in place: arrows, typing, Enter or clicking away."""
        tree = self.tree
        box = tree.bbox(row_id, 'target')
        if not box:
            return
        row = self.rows[int(row_id)]
        field = ttk.Spinbox(tree, values=TARGET_CHOICES, justify='center')
        field.set(target_text(row))
        field.place(x=box[0], y=box[1], width=box[2], height=box[3])
        field.focus_set(); field.selection_range(0, 'end')
        done = []
        def finish(keep):
            if done:
                return
            done.append(True); text = field.get(); field.destroy()
            if keep:
                self.set_target(int(row_id), text)
        field.bind('<Return>', lambda _: finish(True))
        field.bind('<FocusOut>', lambda _: finish(True))
        field.bind('<Escape>', lambda _: finish(False))

    def set_target(self, index, text):
        """Anything that is not a whole number of at least 1 leaves the row as it was."""
        text = text.strip(); row = self.rows[index]
        if text == '최대':
            row['mode'] = 'max'
        elif text.isdigit() and int(text) >= 1:
            row.update(mode='quantity', quantity=int(text))
        self.tree.set(str(index), 'target', target_text(row))

    def move(self, step):
        """Higher rows buy first, which decides what the coins go to when they run short."""
        selected = self.tree.selection()
        if not selected:
            return
        index = int(selected[0]); other = index + step
        if not 0 <= other < len(self.rows):
            return
        self.rows[index], self.rows[other] = self.rows[other], self.rows[index]
        self.refresh()
        self.tree.selection_set(str(other)); self.tree.see(str(other))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(self.rows):
            self.tree.insert('', 'end', iid=str(index), values=(index + 1, row['name'],
                '☑' if row['enabled'] else '☐', target_text(row)))

    def add(self):
        self.edit(None)

    def edit(self, index):
        row = dict(self.rows[index]) if index is not None else self.new_row()
        dialog = tk.Toplevel(self.window); dialog.title('상점 품목 설정'); dialog.transient(self.window)
        body = ttk.Frame(dialog, padding=12); body.pack(fill='both', expand=True)
        name = tk.StringVar(value=row['name'])
        ttk.Label(body, text='품목 이름').grid(row=0, column=0, sticky='w')
        ttk.Entry(body, textvariable=name, width=35).grid(row=0, column=1, sticky='ew', pady=4)
        def apply():
            try:
                changed = dict(row, name=name.get().strip())
                if changed['name'] != row['name'] and 'source' in row:
                    changed.update(source='사용자 입력', verification='사용자 수정·게임 확인 필요')
                candidate = list(self.rows)
                if index is None: candidate.append(changed)
                else: candidate[index] = changed
                self.check(candidate)
            except ValueError as error:
                messagebox.showerror('품목 확인', str(error), parent=dialog); return
            self.rows = candidate; self.refresh(); dialog.destroy()
        ttk.Button(body, text='적용', command=apply).grid(row=1, column=1, sticky='e')

    def delete(self):
        selected = self.tree.selection()
        if selected:
            del self.rows[int(selected[0])]; self.refresh()

    def save(self):
        try:
            self.store.write(self.saved_rows(self.rows), DEFAULT_COIN_RESERVE,expected_revision=self.open_revision,enabled=self.enabled.get())
        except (ValueError, OSError) as error:
            messagebox.showerror('상점 설정 저장 실패', str(error), parent=self.window); return
        self.open_revision=self.store.revision()
        if not self.embedded:self.window.destroy()
        return True


def open_settings(parent, root, character, *, embedded=False):
    """Hook from details button; character must be a verified stable identity."""
    return ShopSettings(parent, root, character,embedded=embedded)
