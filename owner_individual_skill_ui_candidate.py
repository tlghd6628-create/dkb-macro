"""Individual skill goals editor; no game reads or input."""
import copy
import tkinter as tk
from tkinter import ttk


class IndividualSkillEditor:
    def __init__(self, parent, saved, catalog, current_value=None):
        self.parent = parent
        self.saved = copy.deepcopy(saved)
        self.catalog = dict(catalog)
        self.current_value = current_value if callable(current_value) else lambda name:'—'
        # Preserve names from older settings even if a public catalog changes.
        for name in self.saved:
            self.catalog.setdefault(name, '기타')
        self.current = None
        self.items = {}
        self.locked = False
        top = ttk.Frame(parent); top.pack(fill='x')
        ttk.Label(top,text='계열').pack(side='left')
        self.style = tk.StringVar(parent,value='전체')
        choices = ['전체'] + sorted(set(self.catalog.values()))
        selector = ttk.Combobox(top,textvariable=self.style,values=choices,state='readonly',width=12)
        selector.pack(side='left',padx=6)
        selector.bind('<<ComboboxSelected>>',self.change_filter)
        ttk.Label(top,text='도술').pack(side='left',padx=(8,0))
        self.query=tk.StringVar(parent,value='')
        search=ttk.Entry(top,textvariable=self.query,width=16);search.pack(side='left',padx=6)
        search.bind('<Return>',self.change_filter)
        ttk.Button(top,text='찾기',command=self.change_filter).pack(side='left')
        table = ttk.Frame(parent); table.pack(fill='both',expand=True,pady=6)
        columns=('style','name','enabled','current_awaken','goal_awaken')
        self.tree=ttk.Treeview(table,columns=columns,show='headings',height=9,selectmode='browse')
        for key,label,width in (('style','계열',55),('name','도술',135),('enabled','사용',45),('current_awaken','각성 현재',75),
                                ('goal_awaken','각성 목표',75)):
            self.tree.heading(key,text=label);self.tree.column(key,width=width,anchor='center',stretch=(key=='name'))
        bar=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set);self.tree.pack(side='left',fill='both',expand=True);bar.pack(side='right',fill='y')
        self.tree.bind('<<TreeviewSelect>>',self.select)
        edit=ttk.Frame(parent);edit.pack(fill='x')
        self.enabled=tk.BooleanVar(parent,value=False)
        self.awaken=tk.StringVar(parent,value='')
        ttk.Checkbutton(edit,text='사용',variable=self.enabled).pack(side='left')
        ttk.Label(edit,text='각성 목표').pack(side='left',padx=(8,2))
        ttk.Entry(edit,textvariable=self.awaken,width=5).pack(side='left')
        self.refresh()

    @staticmethod
    def number(value):
        text=value.strip()
        if not text:return None
        if not text.isascii() or not text.isdecimal() or int(text)>9999:
            raise ValueError('목표는 빈칸 또는 0~9999의 정수로 입력해 주세요.')
        return int(text)

    def commit(self):
        if self.current is None:return
        row=copy.deepcopy(self.saved.get(self.current,{}))
        row.update(enabled=bool(self.enabled.get()),awaken=self.number(self.awaken.get()))
        # Historical per-skill breakthrough values are preserved verbatim,
        # never copied into the style goal or interpreted as an action.
        if not row['enabled'] and row['awaken'] is None and not (set(row)-{'enabled','awaken'}):
            self.saved.pop(self.current,None)
        else:self.saved[self.current]=row
        iid=self.items.get(self.current)
        if iid and self.tree.exists(iid):self.tree.item(iid,values=self.values(self.current))

    def values(self,name):
        row=self.saved.get(name,{})
        def display(value):return '—' if value is None else str(value)
        return (self.catalog[name],name,'✓' if row.get('enabled') else '—',self.current_value(name),display(row.get('awaken')))

    def refresh_current(self):
        for name,iid in self.items.items():
            if self.tree.exists(iid):self.tree.item(iid,values=self.values(name))

    def refresh(self):
        self.locked=True
        try:
            self.tree.delete(*self.tree.get_children());self.items={}
            names=sorted(self.catalog,key=lambda n:(self.catalog[n],n))
            for name in names:
                if self.style.get()!='전체' and self.catalog[name]!=self.style.get():continue
                if self.query.get().strip().casefold() not in name.casefold():continue
                iid=self.tree.insert('', 'end',values=self.values(name));self.items[name]=iid
            self.current=None;self.enabled.set(False);self.awaken.set('')
        finally:self.locked=False

    def change_filter(self,_event=None):
        from tkinter import messagebox
        try:self.commit()
        except ValueError as error:
            messagebox.showerror('도술 목표',str(error),parent=self.parent)
            # Keep current row visible until its value has been corrected.
            self.style.set('전체');return
        self.refresh()

    def select(self,_event=None):
        if self.locked:return
        selected=self.tree.selection()
        if not selected:return
        name=self.tree.item(selected[0],'values')[1]
        if name==self.current:return
        try:self.commit()
        except ValueError as error:
            from tkinter import messagebox
            messagebox.showerror('도술 목표',str(error),parent=self.parent)
            if self.current in self.items:
                self.locked=True
                try:self.tree.selection_set(self.items[self.current])
                finally:self.locked=False
            return
        self.current=name;row=self.saved.get(name,{})
        self.enabled.set(row.get('enabled',False))
        self.awaken.set('' if row.get('awaken') is None else str(row['awaken']))

    def export(self):
        self.commit()
        return copy.deepcopy(self.saved)
