"""The boss's purple pillars and dark purple floor join the native danger mask (pc2 11-06, tower boss 자서귀).

pc2 died four times at 0:50 to three bright purple pillars followed by a full-screen purple cross; the native
dodge logged no '긴급 회피'. Treating the pillars as danger and stepping away cleared it at 0:58. The thresholds are
pc2's, in OpenCV HSV (hue 0-180):
- pillars: h 125-155, s >= 60, v >= 225
- dark purple floor: h 118-150, s >= 120, v 35-140
They are added to BossFloorAnalyzer.danger_mask, so every boss fight that uses the native floor dodge sees them.
"""
import logging,time
LOG=logging.getLogger('project_gui.DKB')
PILLAR=((125,60,225),(155,255,255));FLOOR=((118,120,35),(150,255,140))
BEAM_AREA=(300,150,1066,650);BEAM_SHARE=.012   # pc2: pillars over 1.2% of the centre, real 1366 px
FEET=(628,365,738,440)                          # pc2: the character stays at the centre (683,395)
MIN_SHARE=.002   # below this the purple is scattered pixels (skill sparks, flowers), not a hazard


def purple(rgb,hsv=None):
    import cv2,numpy as np
    if hsv is None:hsv=cv2.cvtColor(np.ascontiguousarray(rgb),cv2.COLOR_RGB2HSV)
    pillar=cv2.inRange(hsv,np.array(PILLAR[0]),np.array(PILLAR[1]))>0
    floor=cv2.inRange(hsv,np.array(FLOOR[0]),np.array(FLOOR[1]))>0
    return pillar,floor


def merged(mask,extra):
    import numpy as np
    if mask is None:return extra
    if getattr(mask,'shape',None)!=extra.shape:return mask
    if mask.dtype==bool:return mask|extra
    out=mask.copy();out[extra]=255 if out.max(initial=0)>1 else 1;return out


def install(gui=None):
    try:from project_adapter.boss_floor import BossFloorAnalyzer
    except ImportError:return
    original=BossFloorAnalyzer.danger_mask
    if getattr(original,'_owner_purple',False):return
    def danger_mask(self,rgb,*,hsv=None):
        mask=original(self,rgb,hsv=hsv)
        try:
            import numpy as np
            pillar,floor=purple(rgb,hsv)
            h,w=floor.shape;x0,y0,x1,y1=(round(a*b) for a,b in zip(BEAM_AREA,(w/1366,h/768,w/1366,h/768)))
            beam=float(pillar[y0:y1,x0:x1].mean())
            # The dark purple floor read 2.5% of the 21:00 field boss's own ground all along, and the
            # character stopped attacking; only the pillars count until the floor is told apart.
            extra=np.zeros_like(floor)
            if beam>=BEAM_SHARE:
                # pc2: the pillars come before a full-screen cross; dodge on them wherever they stand.
                fx0,fy0,fx1,fy1=(round(a*b) for a,b in zip(FEET,(w/1366,h/768,w/1366,h/768)))
                extra|=pillar;extra[fy0:fy1,fx0:fx1]=True
            share=float(extra.mean())
            if beam<BEAM_SHARE:return mask
            now=time.monotonic()
            if now-getattr(self,'_owner_purple_noted',-1e9)>=5:
                self._owner_purple_noted=now
                LOG.info('보스 보라 기둥·장판 위험 추가 · 기둥 %.1f%% · 장판 %.1f%%',beam*100,floor.mean()*100)
            return merged(mask,extra)
        except Exception as exc:
            LOG.info('보스 보라 판정 보류 · %s',type(exc).__name__);return mask
    danger_mask._owner_purple=True
    BossFloorAnalyzer.danger_mask=danger_mask
