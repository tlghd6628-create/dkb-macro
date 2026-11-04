"""Presentation of the settings console only: colours, sections and display text.

Nothing here reads or writes a setting. Saved IDs, editors and the save order
stay in their own modules; labels below change what is shown, never the schema.
"""
import tkinter as tk
from tkinter import ttk

SIDEBAR='#F4F5F7';SURFACE='#FFFFFF';BORDER='#E4E6EB';TEXT='#1B1F27';MUTED='#6B7280'
ACCENT='#4F46E5';ACCENT_HOVER='#4338CA';ACCENT_SOFT='#EEF0FF';HOVER='#F4F5F7';DISABLED='#A3A8B2'
FONT='Malgun Gothic'

NAV_GROUPS=(('기본',('기본 설정','보상·정리','사냥터','상점','아이템 사용','문파')),
            ('성장',('장비','도술','가호','기운','화첩')),
            ('스케줄',('요일·시간','비경·보스','수련')),
            ('기타',('진단',)))
# Buttons whose work the one console save already does, in the same order.
INNER_SAVES=('저장','저장 후 닫기','성장 설정 저장')

SECTIONS={
 '기본 설정':(('쿠폰',('main_quest.first_coupon',)),('물약',('common.potion_and_favorite',)),
            ('스킬 프리셋',('common.skill_preset','auto_schedule.field_boss.skill_preset','auto_schedule.boss_raid.skill_preset'))),
 '문파':(('문파 보스',('auto_schedule.clan_boss_request',)),('문파 도움',('auto_rewards.clan_help',)),('문파 협력수련',('auto_growth.clan_cooperative_training',))),
 '보상·정리':(('자동 보상',('auto_rewards',)),('거래소 등록',('auto_register.market',)),('장비 정리',('auto_register.equipment_disassembly',))),
 '아이템 사용':(('아이템 사용',('auto_rewards.inventory_use',)),('단 봉인 해제',('auto_rewards.seal_release',))),
 '가호':(('가호 보상',('auto_rewards.blessing',)),),
 '비경·보스':(('일일·주간',('auto_schedule.daily_quest','auto_schedule.weekly_quest','auto_challenge.ascension_tower','auto_challenge.treasure_hunt')),
            ('월드보스',('auto_schedule.field_boss',)),
            ('전장·레이드',('auto_schedule.falling_battle','auto_schedule.folktale','auto_schedule.artifact_charm','auto_schedule.boss_raid')),
            ('비경탐험',('auto_challenge.secret_exploration',)),
            ('전래동화 비경',('auto_challenge.secret_folktale',))),
 '수련':(('영기수련',('auto_growth.spirit_training',)),
              ('내면의 길',('inner_path',))),
}
# Each preset is one line: its switch, then the choice right beside it.
INLINE_CHOICES=('common.skill_preset.choice','auto_schedule.field_boss.skill_preset.choice','auto_schedule.boss_raid.skill_preset.choice')
LABELS={
 'auto_rewards.inventory_use.enabled':'상자·아이템 사용',
 'auto_growth.spirit_training.interval_minutes':'수련 주기 (분)',
 'auto_growth.clan_cooperative_training.enabled':'문파 협력수련 (2~4시간 랜덤, 일 최대 5회)',
 'common.potion_and_favorite.enabled':'자동 물약구매',
 'common.skill_preset.enabled':'메인·서사퀘 진행',
 'auto_schedule.field_boss.skill_preset.enabled':'월드 보스',
 'auto_schedule.boss_raid.skill_preset.enabled':'레이드',
}

def display_label(item):
 """Shown text only; the schema label and every saved key stay as they are."""
 return LABELS.get(item['id']) or item['label'].strip().lstrip('•').strip().rstrip(':').strip()

def sections(name,items):
 """Every item lands in exactly one section, in schema order; none can vanish."""
 groups=[(title,prefixes,[]) for title,prefixes in SECTIONS.get(name,())]
 rest=[]
 for item in items:
  # The longest prefix wins, so a narrower group can sit beside a wider one.
  best=None
  for group in groups:
   for prefix in group[1]:
    if (item['id']==prefix or item['id'].startswith(prefix+'.') or item['id'].startswith(prefix+'_')) and (best is None or len(prefix)>best[0]):best=(len(prefix),group)
  (best[1][2] if best else rest).append(item)
 result=[(title,rows) for title,_,rows in groups if rows]
 if rest:result.append(('' if not result else '기타',rest))
 return result

def prepare(root):
 style=ttk.Style(root)
 for name,background,foreground in (('Dkb.TFrame',SURFACE,TEXT),('Dkb.TLabel',SURFACE,TEXT),('Dkb.TLabelframe',SURFACE,TEXT),('Dkb.TLabelframe.Label',SURFACE,MUTED),
                                    ('Dkb.TCheckbutton',SURFACE,TEXT),('Dkb.TRadiobutton',SURFACE,TEXT),('Dkb.TSeparator',BORDER,BORDER),
                                    ('DkbSide.TFrame',SIDEBAR,TEXT),('DkbHint.TLabel',SURFACE,MUTED),('DkbNotice.TLabel',SURFACE,ACCENT)):
  style.configure(name,background=background,foreground=foreground,font=(FONT,10))
 style.configure('DkbYes.TLabel',background=SURFACE,foreground='#16A34A',font=(FONT,10,'bold'))
 style.configure('DkbNo.TLabel',background=SURFACE,foreground='#E11D48',font=(FONT,10,'bold'))
 style.configure('DkbSection.TLabel',background=SURFACE,foreground=TEXT,font=(FONT,11,'bold'))
 style.configure('DkbTitle.TLabel',background=SURFACE,foreground=TEXT,font=(FONT,17,'bold'))
 style.configure('DkbBrand.TLabel',background=SIDEBAR,foreground=TEXT,font=(FONT,12,'bold'))
 style.configure('Dkb.TLabelframe',bordercolor=BORDER)
 style.configure('Dkb.TSeparator',bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER)
 for name in ('Dkb.TCheckbutton','Dkb.TRadiobutton'):
  style.configure(name,padding=(0,3))
  style.map(name,background=[('active',SURFACE),('disabled',SURFACE)],foreground=[('disabled',DISABLED),('!disabled',TEXT)])
 for name in ('Dkb.TEntry','Dkb.TCombobox','Dkb.TSpinbox'):
  style.configure(name,fieldbackground=SURFACE,background=SURFACE,foreground=TEXT,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,arrowcolor=MUTED,padding=4,font=(FONT,10))
  style.map(name,fieldbackground=[('readonly',SURFACE),('disabled',SIDEBAR)],background=[('active',SURFACE),('readonly',SURFACE),('disabled',SIDEBAR)],
            foreground=[('disabled',DISABLED)],bordercolor=[('focus',ACCENT)],lightcolor=[('focus',ACCENT)],darkcolor=[('focus',ACCENT)],
            selectbackground=[('readonly',SURFACE)],selectforeground=[('readonly',TEXT)])
 style.configure('Dkb.TButton',background=SURFACE,foreground=TEXT,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,relief='solid',borderwidth=1,padding=(14,6),font=(FONT,10))
 style.map('Dkb.TButton',background=[('disabled',SIDEBAR),('pressed',ACCENT_SOFT),('active',HOVER)],lightcolor=[('pressed',ACCENT_SOFT),('active',HOVER)],darkcolor=[('pressed',ACCENT_SOFT),('active',HOVER)],foreground=[('disabled',DISABLED)])
 style.configure('DkbPrimary.TButton',background=ACCENT,foreground='#FFFFFF',bordercolor=ACCENT,lightcolor=ACCENT,darkcolor=ACCENT,relief='solid',borderwidth=1,padding=(26,8),font=(FONT,10,'bold'))
 style.map('DkbPrimary.TButton',background=[('pressed',ACCENT_HOVER),('active',ACCENT_HOVER)],lightcolor=[('pressed',ACCENT_HOVER),('active',ACCENT_HOVER)],darkcolor=[('pressed',ACCENT_HOVER),('active',ACCENT_HOVER)],bordercolor=[('active',ACCENT_HOVER)],foreground=[('!disabled','#FFFFFF')])
 style.configure('DkbNav.Treeview',background=SIDEBAR,fieldbackground=SIDEBAR,foreground=TEXT,borderwidth=0,relief='flat',rowheight=31,font=(FONT,10))
 style.map('DkbNav.Treeview',background=[('selected',ACCENT_SOFT)],foreground=[('selected',ACCENT)])
 style.layout('DkbNav.Treeview',[('Treeview.treearea',{'sticky':'nswe'})])
 style.configure('Dkb.Treeview',background=SURFACE,fieldbackground=SURFACE,foreground=TEXT,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,rowheight=27,font=(FONT,10))
 style.map('Dkb.Treeview',background=[('selected',ACCENT_SOFT)],foreground=[('selected',ACCENT)])
 style.configure('Dkb.Treeview.Heading',background=SIDEBAR,foreground=MUTED,bordercolor=BORDER,lightcolor=SIDEBAR,darkcolor=SIDEBAR,relief='flat',padding=(6,6),font=(FONT,9,'bold'))
 style.map('Dkb.Treeview.Heading',background=[('active',BORDER)],lightcolor=[('active',BORDER)],darkcolor=[('active',BORDER)])
 for name in ('Dkb.Vertical.TScrollbar','Dkb.Horizontal.TScrollbar'):
  style.configure(name,background='#CDD1D8',troughcolor=SURFACE,bordercolor=SURFACE,lightcolor='#CDD1D8',darkcolor='#CDD1D8',arrowcolor=MUTED,relief='flat')
  style.map(name,background=[('active','#A9AEB8')],lightcolor=[('active','#A9AEB8')],darkcolor=[('active','#A9AEB8')])
 # The page tabs stay hidden; only the visible inner tabs below are drawn.
 style.configure('OwnerDirect.TNotebook',background=SURFACE,bordercolor=SURFACE,lightcolor=SURFACE,darkcolor=SURFACE,borderwidth=0,tabmargins=0)
 style.layout('OwnerDirect.TNotebook.Tab',[])
 style.configure('Dkb.TNotebook',background=SURFACE,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,tabmargins=(0,0,0,0))
 style.configure('Dkb.TNotebook.Tab',background=SURFACE,foreground=MUTED,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,padding=(16,7),font=(FONT,10))
 style.map('Dkb.TNotebook.Tab',background=[('selected',SURFACE),('active',HOVER)],foreground=[('selected',ACCENT)],lightcolor=[('selected',SURFACE)],bordercolor=[('selected',BORDER)])
 return style

CLASSES={'TFrame':'Dkb.TFrame','TLabel':'Dkb.TLabel','TCheckbutton':'Dkb.TCheckbutton','TRadiobutton':'Dkb.TRadiobutton','TButton':'Dkb.TButton',
         'TEntry':'Dkb.TEntry','TCombobox':'Dkb.TCombobox','TSpinbox':'Dkb.TSpinbox','Treeview':'Dkb.Treeview','TNotebook':'Dkb.TNotebook',
         'TLabelframe':'Dkb.TLabelframe','TSeparator':'Dkb.TSeparator'}

def restyle(widget):
 """Give the existing widgets the console's own styles. The main window repaints
 the shared default styles with its run-state colour, so these must not use them."""
 kind=widget.winfo_class()
 name=CLASSES.get(kind)
 if kind=='TScrollbar':name='Dkb.Horizontal.TScrollbar' if str(widget.cget('orient'))=='horizontal' else 'Dkb.Vertical.TScrollbar'
 if name:
  current=str(widget.cget('style'))
  if not current.startswith(('Dkb','OwnerDirect')):widget.configure(style=name)
 elif kind in ('Canvas','Frame','Toplevel') and not getattr(widget,'_dkb_line',False):widget.configure(background=SURFACE)
 for child in widget.winfo_children():restyle(child)

def hide_inner_saves(widget):
 if widget.winfo_class()=='TButton' and str(widget.cget('text')) in INNER_SAVES:
  manager=widget.winfo_manager()
  if manager=='pack':widget.pack_forget()
  elif manager=='grid':widget.grid_remove()
 for child in widget.winfo_children():hide_inner_saves(child)

def tidy(widget):
 """Line every page up under its title and show the worn gear without scrolling.
 Frames inside a visible inner tab keep their padding."""
 kind=widget.winfo_class()
 if kind=='TFrame' and str(widget.cget('padding')):widget.configure(padding=0)
 if kind=='Treeview' and tuple(widget.cget('columns'))[:1]==('slot',):widget.configure(height=9)
 if kind=='TNotebook' and not str(widget.cget('style')).startswith('OwnerDirect'):return
 for child in widget.winfo_children():tidy(child)

def follow(window):
 """Rows and dialogs added later get the same look as they appear."""
 def mapped(event):
  try:
   if event.widget.winfo_exists():restyle(event.widget)
  except (tk.TclError,AttributeError):pass
 window.bind('<Map>',mapped,add='+')
 root=window._root();active=getattr(root,'_dkb_settings_windows',None)
 if active is None:
  active=root._dkb_settings_windows=[]
  def dialog(event):
   path=str(event.widget)
   for owner in list(active):
    if not owner.winfo_exists():active.remove(owner)
    elif path.startswith(str(owner)+'.'):
     try:restyle(event.widget)
     except tk.TclError:pass
     break
  root.bind_class('Toplevel','<Map>',dialog,add='+')
 active.append(window)

def scroll_area(parent):
 """Canvas in the page colour with a scrollbar only while the content overflows."""
 canvas=tk.Canvas(parent,highlightthickness=0,borderwidth=0,background=SURFACE)
 scroll=ttk.Scrollbar(parent,orient='vertical',command=canvas.yview)
 canvas.configure(yscrollcommand=scroll.set);canvas.pack(side='left',fill='both',expand=True)
 body=ttk.Frame(canvas);window=canvas.create_window(0,0,window=body,anchor='nw')
 def fit(event=None):
  canvas.configure(scrollregion=canvas.bbox('all'))
  if body.winfo_reqheight()>canvas.winfo_height()>1:
   if not scroll.winfo_ismapped():scroll.pack(side='right',fill='y')
  elif scroll.winfo_ismapped():scroll.pack_forget()
 body.bind('<Configure>',fit,add='+')
 def resize(event):
  canvas.itemconfigure(window,width=event.width);fit()
 canvas.bind('<Configure>',resize,add='+')
 def wheel(event):
  if body.winfo_reqheight()>canvas.winfo_height():canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
 canvas._dkb_wheel=wheel
 return canvas,body

def bind_wheel(canvas,widget):
 """Value controls keep their own wheel behaviour."""
 if widget.winfo_class() not in ('TCombobox','TSpinbox'):widget.bind('<MouseWheel>',canvas._dkb_wheel,add='+')
 for child in widget.winfo_children():bind_wheel(canvas,child)

def hairline(parent,**size):
 """ttk separators stay dark in this theme whatever colour they are given."""
 line=tk.Frame(parent,background=BORDER,highlightthickness=0,borderwidth=0,**size);line._dkb_line=True
 return line

def section_box(holder,title):
 box=ttk.Frame(holder,style='Dkb.TFrame');box.pack(fill='x',pady=(0,20))
 if title:
  ttk.Label(box,text=title,style='DkbSection.TLabel').pack(anchor='w')
  hairline(box,height=1).pack(fill='x',pady=(5,9))
 return box
