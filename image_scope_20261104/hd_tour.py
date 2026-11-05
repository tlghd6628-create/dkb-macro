"""Walk the screens that need no spending and collect new pictures on each. Program closed; game on the field.
Only opens menus and tabs and leaves them. Refuses nothing by itself, so keep this list to navigation."""
from pathlib import Path
import subprocess,sys,time
D=Path(__file__).parent
PY=sys.executable
def step(*a):return subprocess.run([PY,'live_step.py',*a],cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace').stdout.strip()[-60:]
def pair(name):
    out=subprocess.run([PY,'hd_pair.py',name],cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace')
    print((out.stdout or out.stderr).splitlines()[0][:90] if (out.stdout or out.stderr) else name,flush=True)
BACK=('click','21','19','_b','2')
TOUR=[
 ('inventory',[('key','49','_a')],[('key','49','_b')]),
 ('inv_goods',[('key','49','_a'),('click','792','50','_a','1.2')],[('key','49','_b')]),
 ('menu',[('click','875','20','_a','1.5')],[('click','875','20','_b','1.5')]),
 ('growth_enhance',[('key','55','_a')],[BACK]),
 ('growth_break',[('key','55','_a'),('click','43','111','_a','1.2')],[BACK]),
 ('growth_awaken',[('key','55','_a'),('click','43','145','_a','1.2')],[BACK]),
 ('growth_reroll',[('key','55','_a'),('click','43','179','_a','1.2')],[BACK]),
 ('growth_blessing',[('key','55','_a'),('click','124','49','_a','1.5')],[BACK]),
 ('growth_skill',[('key','55','_a'),('click','198','49','_a','1.5')],[BACK]),
 ('skills',[('key','4B','_a')],[BACK]),
 ('map',[('key','4D','_a')],[BACK]),
 ('missions',[('key','4A','_a')],[BACK]),
 ('blessing',[('key','4F','_a')],[BACK]),
 ('info',[('key','50','_a')],[BACK]),
 ('guide',[('key','74','_a')],[BACK]),
 ('event',[('key','75','_a')],[BACK]),
 ('market',[('key','76','_a')],[BACK]),
 ('mail',[('key','78','_a')],[BACK]),
 ('shop',[('key','49','_a'),('click','688','62','_a','2.5')],[BACK]),
 ('shop_popup',[('key','49','_a'),('click','688','62','_a','2.5'),('click','110','171','_a','1.2')],[('click','408','302','_b','1'),BACK]),
]
only=set(sys.argv[1:])
for name,go,leave in TOUR:
    if only and name not in only:continue
    for a in go:step(*a)
    pair(name)
    for a in leave:step(*a)
    time.sleep(1)
step('shot','_end')
print('done',flush=True)
