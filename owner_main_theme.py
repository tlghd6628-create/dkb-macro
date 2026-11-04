"""Colours of the main window only. Positions, callbacks and saved files stay.

The window keeps showing the run state: the host still paints these colours from
gui.config on every state change. Nothing here is written back to the profile.
"""
from tkinter import ttk
from compact_styles import button_palette
from owner_settings_theme import ACCENT,ACCENT_HOVER,ACCENT_SOFT,BORDER,HOVER,MUTED,SURFACE,TEXT

STATE_COLORS={
 'running':{'background':'#EFFBF4','accent':'#16A34A','foreground':'#166534'},
 'paused':{'background':'#FFFBEB','accent':'#D97706','foreground':'#92400E'},
 'stopped':{'background':SURFACE,'accent':'#CBD0D8','foreground':MUTED},
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
 button_palette(style,'TButton',SURFACE,HOVER,TEXT)
 button_palette(style,'LogSend.TButton',SURFACE,HOVER,TEXT)
 button_palette(style,'HUDPlace.TButton',ACCENT_SOFT,'#E0E3FF',ACCENT)
 style.configure('UpdateLink.TButton',foreground=ACCENT)
 style.map('UpdateLink.TButton',foreground=[('disabled','#A0A6AD'),('active',ACCENT_HOVER)])
 for name in ('TEntry','TCombobox','TSpinbox'):
  style.configure(name,fieldbackground=SURFACE,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,arrowcolor=MUTED)
  style.map(name,bordercolor=[('focus',ACCENT)],lightcolor=[('focus',ACCENT)],darkcolor=[('focus',ACCENT)])
 for name in ('Vertical.TScrollbar','Horizontal.TScrollbar'):
  style.configure(name,background='#CDD1D8',troughcolor=SURFACE,bordercolor=SURFACE,lightcolor='#CDD1D8',darkcolor='#CDD1D8',arrowcolor=MUTED)
  style.map(name,background=[('active','#A9AEB8')],lightcolor=[('active','#A9AEB8')],darkcolor=[('active','#A9AEB8')])

def paint_log(gui):
 # The visible log may be the layout's copy of the original widget.
 originals=getattr(getattr(gui,'visual_view',None),'originals',{})
 for log in {gui.log,originals.get('log',gui.log)}:
  log.configure(relief='flat',borderwidth=0,highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER,
                background=SURFACE,foreground=TEXT,padx=7,pady=5)

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
   ttk.Style(gui.root).map('TRadiobutton',background=[('active',pale),('disabled',pale)])
  return result
 gui.sync_compact_state=sync
 gui._owner_main_theme=True
 gui._painted_state=None
 sync()
