"""World boss needs the character free to reach it; normal hunting stays fixed in place.

The user's rule. Boss and raid: fixed-in-place off, range slider at its right end (30m).
Hunting: fixed-in-place on, slider at its left end (5m).
A failure here is logged and never stops the boss or the hunt. What must be restored
is written down first, so a stop or crash during the boss is repaired at the next
safe moment instead of leaving hunting unfixed.
"""
from functools import lru_cache
from pathlib import Path
import json,logging,os,tempfile,time

LOG=logging.getLogger('project_gui.DKB')
ASSETS=Path(__file__).parent/'assets/hunt-range'
SELECTED=90;UNSELECTED=75
FILE='settings/owner-boss-range.json'
class RangeError(RuntimeError):pass

@lru_cache(maxsize=8)
def asset(name):
    from PIL import Image
    import numpy as np
    return np.asarray(Image.open(ASSETS/(name+'.png')).convert('RGB'))

def _peak(frame,name,box,score=.9):
    from owner_image_scope import unique_peak
    return unique_peak(frame,asset(name),box,score)

PANEL=(960,60,400,640)  # real pixels: the panel's words, on the right of the screen
FIXED_LABEL='자동전투중이동고정';RANGE_LABEL='자율수행범위'

def _real(frame):return getattr(frame,'hi',None)

def _close_to(text,wanted):
    from difflib import SequenceMatcher
    from owner_text import clean
    return SequenceMatcher(None,clean(text),wanted).ratio()>=.7

def real_panel(frame):
    """The panel's rows by their words. Each switch's two options, and the slider's value line. Parts not showing are missing."""
    from owner_text import read,clean
    rows=read(None,frame,PANEL,scale=2,bright=True);out={}
    def options(label_y,low,high):
        here=[r for r in rows if low<=r['ry']-label_y<=high and clean(r['text']) in ('사용','사용안함','사용안할') and r['bounds'][0]>=1000]
        off=[r for r in here if clean(r['text'])!='사용'];on=[r for r in here if clean(r['text'])=='사용']
        return (off[0],on[0]) if len(off)==1 and len(on)==1 else None
    for row in rows:
        if _close_to(row['text'],FIXED_LABEL):
            pair=options(row['ry'],25,55)
            if pair:out['fixed']=pair
        elif _close_to(row['text'],RANGE_LABEL):
            pair=options(row['ry'],-14,14)
            if pair:out['range']=pair
            value=[r for r in rows if 30<=r['ry']-row['ry']<=65 and clean(r['text']).endswith('m')]
            if value:out['value']=value[0]
    return out

def panel_open(frame):
    if _real(frame) is not None:
        import numpy as np
        from owner_text import read_area,clean
        return any('수행설정' in clean(r['text']) or '조작설정' in clean(r['text']) for r in read_area(None,np.asarray(frame.hi)[70:100,960:1330],left=960,top=70))
    return _peak(frame,'panel-title',(640,40,90,28)) is not None
def cog(frame):return _peak(frame,'cog',(720,425,100,45))

def _pill(frame,left,right,y):
    def bright(x):return float(frame[y-5:y+5,x-13:x+13].mean())
    a,b=bright(left),bright(right)
    if b>SELECTED and a<UNSELECTED:return True
    if a>SELECTED and b<UNSELECTED:return False
    return None

def locate(frame):
    """Rows move with the panel's scroll, so each is found from its own label."""
    if _real(frame) is not None:
        rows=real_panel(frame)
        if 'fixed' not in rows or 'range' not in rows:return None
        return {key:(rows[key][0]['x'],rows[key][1]['x'],rows[key][1]['y']) for key in ('fixed','range')}
    fixed=_peak(frame,'fixed-label',(655,60,120,360));spread=_peak(frame,'range-label',(655,60,120,360))
    if fixed is None or spread is None:return None
    return {'fixed':(710,822,fixed[2]+31),'range':(800,851,spread[2]+8)}

def read(frame):
    if _real(frame) is not None:
        import numpy as np
        from owner_game_settings import chosen
        rows=real_panel(frame)
        if 'fixed' not in rows or 'range' not in rows:return None
        found={}
        for key in ('fixed','range'):
            on=chosen(np.asarray(frame.hi),dict(options=list(rows[key])))
            if on is None:return None
            found[key]=on is rows[key][1]
        return found
    rows=locate(frame)
    if rows is None:return None
    found={key:_pill(frame,*row) for key,row in rows.items()}
    return None if None in found.values() else found

SLIDER_LEFT=722;SLIDER_RIGHT=860;SLIDER_DOWN=36
REAL_SLIDER=(1050,1295)  # real x of the slider's track
VALUES={'low':'five-m','high':'thirty-m'}
def slider_y(frame):
    if _real(frame) is not None:
        value=real_panel(frame).get('value')
        return value['y'] if value else None
    rows=locate(frame)
    return None if rows is None else rows['range'][2]-8+SLIDER_DOWN
def handle(frame):
    """The white knob is the brightest column on the slider's own row."""
    if _real(frame) is not None:
        import numpy as np
        from owner_hd import logical_of
        value=real_panel(frame).get('value')
        if not value:return None
        band=np.asarray(frame.hi)[value['ry']-8:value['ry']+9,REAL_SLIDER[0]:REAL_SLIDER[1]]
        return logical_of(REAL_SLIDER[0]+int(band.mean(axis=(0,2)).argmax()),value['ry'],frame.layout)[0]
    y=slider_y(frame)
    if y is None:return None
    return int(frame[y-6:y+6,SLIDER_LEFT:SLIDER_RIGHT].mean(axis=(0,2)).argmax())+SLIDER_LEFT
def shows(frame,value):
    if _real(frame) is not None:
        from owner_text import clean
        seen=real_panel(frame).get('value')
        return bool(seen) and clean(seen['text'])==('5m' if value=='low' else '30m')
    y=slider_y(frame)
    return y is not None and _peak(frame,VALUES[value],(660,y-16,50,32),.9) is not None

def _state_path(root):return Path(root)/FILE
def pending(root):
    try:data=json.loads(_state_path(root).read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    if isinstance(data,dict) and type(data.get('fixed')) is bool and type(data.get('range')) is bool:return data
    return None
def _write(root,data):
    path=_state_path(root);fd,tmp=tempfile.mkstemp(prefix='.boss-range-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(data,out);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def _clear(root):
    try:_state_path(root).unlink()
    except FileNotFoundError:pass

def _until(ui,test,seconds=4):
    end=time.monotonic()+seconds
    while True:
        ui.context.checkpoint();frame=ui.frame();value=test(frame)
        if value:return value
        if time.monotonic()>=end:return None
        ui.context.wait(.2)

def _open(ui):
    frame=ui.frame()
    if panel_open(frame):return
    peak=cog(frame)
    if peak is None:raise RangeError('자동 전투 설정 톱니바퀴 미확인')
    h,w=asset('cog').shape[:2]
    ui.click(peak[1]+w//2,peak[2]+h//2,lambda f:cog(f) is not None)
    if not _until(ui,panel_open):raise RangeError('자동 전투 설정 창 미확인')

def _rows(ui):
    for _ in range(3):
        found=read(ui.frame())
        if found:return found
        ui.wheel(-1,12,at=(760,260),scene=panel_open,verify_cursor=True);ui.context.wait(.4)
    raise RangeError('이동 고정·수행 범위 행 미확인')

def _close(ui):
    frame=ui.frame()
    if not panel_open(frame):return
    peak=_peak(frame,'confirm',(700,425,130,50))
    if peak is not None:
        h,w=asset('confirm').shape[:2];ui.click(peak[1]+w//2,peak[2]+h//2,panel_open)
    else:ui.click(883,53,panel_open)
    if not _until(ui,lambda f:not panel_open(f)):raise RangeError('자동 전투 설정 창 닫힘 미확인')

def _slide(ui,value):
    frame=ui.frame()
    if shows(frame,value):return
    y,x=slider_y(frame),handle(frame)
    if y is None or x is None:raise RangeError('수행 범위 슬라이더 미확인')
    if _real(frame) is not None:
        from owner_hd import logical_of
        target=logical_of(REAL_SLIDER[1]+6 if value=='high' else REAL_SLIDER[0]-6,round(y*1.6),frame.layout)[0]
    else:target=SLIDER_RIGHT if value=='high' else SLIDER_LEFT-20
    ui.drag((x,y),(target,y),panel_open)
    if not _until(ui,lambda f:shows(f,value),2):raise RangeError('수행 범위 '+('최대' if value=='high' else '5m')+' 확인 실패')

def apply(ui,fixed,slider,*,before_change=None):
    """Set the fixed switch and the slider end. Returns what the switches were. Each is read back."""
    _open(ui)
    try:
        was=_rows(ui)
        if before_change is not None:before_change(was)
        for key,value in (('fixed',fixed),('range',True)):
            if read(ui.frame())[key]==value:continue
            left,right,y=locate(ui.frame())[key]
            ui.click(right if value else left,y,panel_open)
            if not _until(ui,lambda f:(read(f) or {}).get(key)==value,2):raise RangeError(key+' 전환 확인 실패')
        _slide(ui,slider)
    finally:_close(ui)
    return was

def _ui(adapter,context,inputs):
    from owner_mission_ui import MissionUI
    return MissionUI(adapter,context,inputs)

def loosen(adapter,context,inputs):
    """Before the boss. An earlier unrestored record keeps the original values."""
    root=adapter.project.root;saved=pending(root)
    try:
        adapter.exit_sleep_mode(context,inputs);context.checkpoint()
        def remember(was):
            if saved is None:_write(root,{'fixed':was['fixed'],'range':was['range']})
        apply(_ui(adapter,context,inputs),False,'high',before_change=remember)
        LOG.info('이동 전투 설정 · 이동 고정 끔 · 수행 범위 최대')
        return True
    except (RangeError,RuntimeError,ValueError,OSError) as exc:
        LOG.warning('보스 전 자동 전투 설정 실패 · 기존 설정으로 진행 · %s',str(exc)[:120]);return False

def restore(adapter,context,inputs):
    """After the boss, or at the next safe moment. Stays recorded until it succeeds."""
    root=adapter.project.root;saved=pending(root)
    if saved is None:return False
    try:
        adapter.exit_sleep_mode(context,inputs);context.checkpoint()
        if not panel_open(ui_frame:=(ui:=_ui(adapter,context,inputs)).frame()) and cog(ui_frame) is None:
            LOG.info('자동 전투 설정 복원 대기 · 기본 화면 아님');return False
        # The user's rule: hunting is always fixed in place at 5m, whatever it was before.
        apply(ui,True,'low')
        _clear(root)
        LOG.info('자동 전투 설정 복원 · 이동 고정 사용 · 수행 범위 5m')
        return True
    except (RangeError,RuntimeError,ValueError,OSError) as exc:
        LOG.warning('자동 전투 설정 복원 보류 · 다음 기회에 재시도 · %s',str(exc)[:120]);return False
