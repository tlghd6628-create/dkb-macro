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


class ShopSettings:
    def __init__(self, parent, root, character, *, embedded=False):
        self.store = ShopSettingsStore(root, character)
        document,self.open_revision = self.store.snapshot()
        self.rows = document['items']
        self.embedded=embedded
        self.window = ttk.Frame(parent) if embedded else tk.Toplevel(parent)
        if embedded:self.window.pack(fill='both',expand=True)
        else:
            self.window.title('잡화상점 구매 설정');self.window.geometry('640x520')
        top = ttk.Frame(self.window, padding=10)
        top.pack(fill='both', expand=True)
        self.enabled=tk.BooleanVar(self.window,value=document.get('enabled',True))
        ttk.Checkbutton(top,text='설정 상품 구매 사용',variable=self.enabled).pack(anchor='w',pady=(0,8))
        reserve_bar = ttk.Frame(top)
        reserve_bar.pack(fill='x', pady=(0, 5))
        ttk.Label(reserve_bar, text='남길 엽전').pack(side='left')
        self.reserve = tk.StringVar(value='' if document['coin_reserve'] is None else str(document['coin_reserve']))
        ttk.Entry(reserve_bar, textvariable=self.reserve, width=14).pack(side='left', padx=5)
        ttk.Label(reserve_bar, text='미설정 시 구매 보류').pack(side='left')
        self.tabs = ttk.Notebook(top)
        self.tabs.pack(fill='both', expand=True)
        self.trees = {}
        for shop, label in SHOP_NAMES.items():
            tab = ttk.Frame(self.tabs, padding=5)
            self.tabs.add(tab, text=label)
            tree = ttk.Treeview(tab, columns=('name', 'enabled', 'current', 'target','support'), show='headings', selectmode='browse')
            for col, title, width in [('name', '품목', 220), ('enabled', '사용', 55),
                                      ('current', '현재', 65), ('target', '목표', 65),('support','판독 상태',120)]:
                tree.heading(col, text=title)
                tree.column(col, width=width, stretch=col=='name')
            bar = ttk.Scrollbar(tab, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=bar.set)
            bar.pack(side='right', fill='y'); tree.pack(fill='both', expand=True)
            tree.bind('<ButtonRelease-1>', lambda event, s=shop: self.toggle_enabled(event, s))
            tree.bind('<Double-1>', lambda event, s=shop: self.edit_selected(s))
            self.trees[shop] = tree
        buttons = ttk.Frame(top); buttons.pack(fill='x', pady=8)
        ttk.Button(buttons, text='품목 추가', command=self.add).pack(side='left')
        ttk.Button(buttons, text='선택 수정', command=lambda: self.edit_selected(self.shop())).pack(side='left', padx=4)
        ttk.Button(buttons, text='선택 삭제', command=self.delete).pack(side='left')
        ttk.Button(buttons, text='저장 후 닫기', command=self.save).pack(side='right')
        self.refresh()

    def toggle_enabled(self, event, shop):
        tree = self.trees[shop]
        if tree.identify_region(event.x, event.y) != 'cell' or tree.identify_column(event.x) != '#2':
            return
        row_id = tree.identify_row(event.y)
        if row_id:
            row = self.rows[int(row_id)]
            row['enabled'] = not row['enabled']
            tree.set(row_id, 'enabled', '☑' if row['enabled'] else '☐')

    def shop(self):
        return list(SHOP_NAMES)[self.tabs.index('current')]

    def refresh(self):
        from owner_shop_reader_candidate import OBSERVED_NAMES
        for tree in self.trees.values():
            tree.delete(*tree.get_children())
        for index, row in enumerate(self.rows):
            status=('구매창 미검증' if row['name']=='1단 체력 회복 물약' else
                    ('후보·실전 미검증' if row['name'] in OBSERVED_NAMES else 'OCR·실전 미검증'))
            self.trees[row['shop']].insert('', 'end', iid=str(index), values=(row['name'],
                '☑' if row['enabled'] else '☐', '—', '최대' if row['mode'] == 'max' else row['quantity'],status))

    def add(self):
        self.edit(None, self.shop())

    def edit_selected(self, shop):
        selection = self.trees[shop].selection()
        if selection:
            self.edit(int(selection[0]), shop)

    def edit(self, index, shop):
        row = dict(self.rows[index]) if index is not None else dict(shop=shop, name='', enabled=False,
            mode='quantity', quantity=1, verification='사용자 추가·게임 확인 필요', source='사용자 입력')
        dialog = tk.Toplevel(self.window); dialog.title('상점 품목 설정'); dialog.transient(self.window)
        body = ttk.Frame(dialog, padding=12); body.pack(fill='both', expand=True)
        name = tk.StringVar(value=row['name']); enabled = tk.BooleanVar(value=row['enabled'])
        mode = tk.StringVar(value=row['mode']); quantity = tk.StringVar(value=str(row['quantity']))
        ttk.Label(body, text=SHOP_NAMES[shop]).grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(body, text='품목 이름').grid(row=1, column=0, sticky='w')
        ttk.Entry(body, textvariable=name, width=35).grid(row=1, column=1, sticky='ew', pady=4)
        ttk.Checkbutton(body, text='구매 사용', variable=enabled).grid(row=2, column=1, sticky='w')
        ttk.Radiobutton(body, text='수량', variable=mode, value='quantity').grid(row=3, column=0, sticky='w')
        ttk.Entry(body, textvariable=quantity, width=10).grid(row=3, column=1, sticky='w')
        ttk.Radiobutton(body, text='최대', variable=mode, value='max').grid(row=4, column=0, sticky='w')
        def apply():
            try:
                changed = dict(row, name=name.get().strip(), enabled=enabled.get(), mode=mode.get(), quantity=int(quantity.get()))
                if changed['name'] != row['name']:
                    changed.update(source='사용자 입력', verification='사용자 수정·게임 확인 필요')
                candidate = list(self.rows)
                if index is None: candidate.append(changed)
                else: candidate[index] = changed
                validate(candidate)
            except ValueError as error:
                messagebox.showerror('품목 확인', str(error), parent=dialog); return
            self.rows = candidate; self.refresh(); dialog.destroy()
        ttk.Button(body, text='적용', command=apply).grid(row=6, column=1, sticky='e')

    def delete(self):
        selected = self.trees[self.shop()].selection()
        if selected:
            del self.rows[int(selected[0])]; self.refresh()

    def save(self):
        try:
            value = self.reserve.get().strip().replace(',', '')
            self.store.write(self.rows, int(value) if value else None,expected_revision=self.open_revision,enabled=self.enabled.get())
        except (ValueError, OSError) as error:
            messagebox.showerror('상점 설정 저장 실패', str(error), parent=self.window); return
        self.open_revision=self.store.revision()
        if not self.embedded:self.window.destroy()
        return True


def open_settings(parent, root, character, *, embedded=False):
    """Hook from details button; character must be a verified stable identity."""
    return ShopSettings(parent, root, character,embedded=embedded)
