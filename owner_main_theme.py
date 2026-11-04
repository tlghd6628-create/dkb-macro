"""Colours of the main window only. Positions, callbacks and saved files stay.

The window keeps showing the run state: the host still paints these colours from
gui.config on every state change. Nothing here is written back to the profile.
"""
from tkinter import ttk
from compact_styles import button_palette
from owner_settings_theme import ACCENT,ACCENT_HOVER,ACCENT_SOFT,BORDER,HOVER,MUTED,SURFACE,TEXT,FONT

STATE_COLORS={
 'running':{'background':'#F1FAF4','accent':'#16A34A','foreground':'#166534'},
 'paused':{'background':'#FFFBEB','accent':'#D97706','foreground':'#92400E'},
 'stopped':{'background':'#F5F6F8','accent':'#CBD0D8','foreground':'#3B4252'},
}
BUTTON_COLORS={
 'start':{'background':ACCENT,'active':ACCENT_HOVER,'pressed':ACCENT_HOVER,'foreground':'#FFFFFF'},
 'pause':{'background':'#FEF3C7','active':'#FDE68A','pressed':'#FCD34D','foreground':'#92400E'},
 'stop':{'background':'#FFE4E6','active':'#FECDD3','pressed':'#FDA4AF','foreground':'#BE123C'},
 'details':{'background':ACCENT_SOFT,'active':'#E0E3FF','pressed':'#C7CCFF','foreground':ACCENT},
}

def paint_controls(gui):
 style=ttk.Style(gui.root)
 gui.config['state_colors']=STATE_COLORS;gui.config['button_colors']=BUTTON_COLORS
 for name,colors in BUTTON_COLORS.items():
  button_palette(style,name.title()+'.RunControl.TButton',colors['background'],colors['active'],colors['foreground'],colors['pressed'])
 style.configure('RunControl.TButton',font=(FONT,10,'bold'),padding=(6,4))
 button_palette(style,'TButton',SURFACE,HOVER,TEXT)
 style.configure('TButton',font=(FONT,9),padding=(8,4))
 button_palette(style,'LogSend.TButton',SURFACE,HOVER,TEXT)
 style.configure('LogSend.TButton',font=(FONT,9),padding=(6,4))
 button_palette(style,'HUDPlace.TButton',ACCENT_SOFT,'#E0E3FF',ACCENT)
 style.configure('IdentitySave.TButton',font=(FONT,9,'bold'),padding=(4,3))
 style.configure('UpdateLink.TButton',foreground=ACCENT,font=(FONT,9,'bold'))
 style.map('UpdateLink.TButton',foreground=[('disabled','#A0A6AD'),('active',ACCENT_HOVER)])
 for name in ('TEntry','TCombobox','TSpinbox'):
  style.configure(name,fieldbackground=SURFACE,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,arrowcolor=MUTED,padding=3)
  style.map(name,bordercolor=[('focus',ACCENT)],lightcolor=[('focus',ACCENT)],darkcolor=[('focus',ACCENT)])
 for name in ('Vertical.TScrollbar','Horizontal.TScrollbar'):
  style.configure(name,background='#CDD1D8',troughcolor=SURFACE,bordercolor=SURFACE,lightcolor='#CDD1D8',darkcolor='#CDD1D8',arrowcolor=MUTED)
  style.map(name,background=[('active','#A9AEB8')],lightcolor=[('active','#A9AEB8')],darkcolor=[('active','#A9AEB8')])

def paint_log(gui):
 # The visible log may be the layout's copy of the original widget.
 originals=getattr(getattr(gui,'visual_view',None),'originals',{})
 for log in {gui.log,originals.get('log',gui.log)}:
  log.configure(relief='flat',borderwidth=0,highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER,
                background=SURFACE,foreground=TEXT,padx=8,pady=6,spacing1=1,spacing3=1,font=(FONT,9))

def install(gui):
 if getattr(gui,'_owner_main_theme',False):return
 paint_controls(gui);paint_log(gui)
 ordinary=gui.sync_compact_state
 def sync():
  before=gui._painted_state
  result=ordinary()
  if gui._painted_state!=before:
   # The host keeps this for check boxes; the mode radios need the same.
   pale=STATE_COLORS[gui._painted_state]['background']
   style=ttk.Style(gui.root)
   style.map('TRadiobutton',background=[('active',pale),('disabled',pale)])
   style.configure('HUD.TCheckbutton',background=pale)
   style.map('HUD.TCheckbutton',background=[('active',pale),('disabled',pale)])
  return result
 gui.sync_compact_state=sync
 gui._owner_main_theme=True
 gui._painted_state=None
 sync()
