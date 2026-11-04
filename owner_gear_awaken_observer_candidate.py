"""One-action awakening observer for a previously verified equipped item.

The caller must navigate to the item's awakening detail using the same input
worker. This module does not navigate/select and never presses a button.
Only the observed 0→1 line is currently supported; an unknown result stays
pending and cannot authorize a second attempt.
"""
import base64,hashlib,time
from pathlib import Path
import cv2
import numpy as np
from owner_gear_decision_candidate import Observation
from owner_gear_awaken_reader_candidate import read_zero_to_one

# 1+ awakening post-result has not yet been verified from an actual screen.
# Prevent a real input from creating an unreconcilable durable intent.
AWAKEN_RESULT_READER_VERIFIED=False

def find_awaken_list_item(source,frame,detector):
    """Locate the previously equipped icon in the awakening list, without input.

    Returns None unless the same icon has a clear lead over all visible cells.
    This does not establish which tab is selected; caller must verify that too.
    """
    ticket=source.ticket;reader=source.identity_reader
    pre=getattr(reader,'pre',None);rows=getattr(reader,'pre_rows',None)
    if not isinstance(ticket,dict) or not isinstance(pre,np.ndarray) or not isinstance(rows,list):return None
    original=next((row for row in rows if row.get('index')==ticket.get('index')),None)
    if original is None:return None
    slot=original.get('slot') or {};x=slot.get('cell_x',-100)+8;y=slot.get('cell_y',-100)+8
    target=pre[y:y+18,x:x+18]
    if target.shape!=(18,18,3) or not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return None
    try:current=source.native.inspect_growth_equipment(detector,frame)
    except Exception:return None
    scores=[]
    for row in current:
        s=row.get('slot') or {};x=s.get('cell_x',-100)+8;y=s.get('cell_y',-100)+8
        candidate=frame[y:y+18,x:x+18]
        if candidate.shape!=(18,18,3):return None
        score=float(cv2.matchTemplate(candidate,target,cv2.TM_CCOEFF_NORMED)[0,0])
        if not np.isfinite(score):return None
        scores.append((score,row))
    if len(scores)<2:return None
    scores.sort(key=lambda pair:pair[0],reverse=True)
    if scores[0][0]<.90 or scores[0][0]-scores[1][0]<.25:return None
    return scores[0][1]

def _gear_awakening_tab_selected(frame):
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return False
    # The three left tab backgrounds are independent of their label text.
    def mean(y):return float(frame[y:y+20,14:73].mean())
    awaken,breakthrough,enhance=mean(135),mean(101),mean(67)
    return awaken>=180 and awaken-breakthrough>=50 and awaken-enhance>=50

def native_extra_readers_factory(service,context,identity,targets,kind):
    """Navigate once and select the same observed gear; never execute growth.

    Breakthrough stages have no verified reader and return None. When a
    separately validated post-result reader exists the four callbacks are
    pre-read, final verification, detector cleanup, and post-read.
    """
    if kind!='awaken' or not AWAKEN_RESULT_READER_VERIFIED:return None
    # Stage counting must be proved separately; the observed `각성→각성+`
    # line alone cannot be treated as a numerical 0→1 transition.
    result_reader=getattr(service.adapter,'_owner_gear_awaken_result_reader',None)
    if not callable(result_reader):return None
    source=getattr(service.adapter,'_owner_growth_observer',None)
    if source is None or source.context is not context or source.service is not service or source.character!=identity:return None
    ticket=source.ticket
    if not isinstance(ticket,dict) or targets.get(ticket.get('grade'),{}).get('awaken',0)<1:return None
    context.checkpoint();service.check();before=service.capture()
    if source.identity_reader(before,ticket['index'],True)!=ticket['identity']:return None
    from roi_runtime import RoiDetector
    from project_adapter import market_inventory as native, growth_equipment_extra as extra
    original=service.detector
    names=set(native.GROWTH_ENHANCE_NAMES)|{extra.AWAKE_TAB,extra.AWAKE_BUTTON}
    service.detector=RoiDetector(Path(service.adapter.project.root)/'profiles/DKB',list(names))
    def cleanup():service.detector=original
    try:
        context.checkpoint();service.check();service.button(extra.AWAKE_TAB,wait_before_click=.1,required=True)
        context.wait(.15);context.checkpoint();service.check();a=service.capture()
        context.wait(.12);context.checkpoint();service.check();b=service.capture()
        if not _gear_awakening_tab_selected(a) or not _gear_awakening_tab_selected(b):cleanup();return None
        row_a=find_awaken_list_item(source,a,service.detector);row_b=find_awaken_list_item(source,b,service.detector)
        if not row_a or not row_b or row_a.get('index')!=row_b.get('index') or row_a.get('slot')!=row_b.get('slot'):
            cleanup();return None
        slot=row_b['slot'];x,y=native._click_xy(slot)
        left,top,w,h=(slot.get(k) for k in ('cell_x','cell_y','cell_w','cell_h'))
        if not all(type(v) is int for v in (x,y,left,top,w,h)) or not (left<=x<left+w and top<=y<top+h):
            cleanup();return None
        context.checkpoint();service.check();service.click_hit((x,y,(left,top,left+w,top+h)))
        context.wait(.25)
        observer=AwakeningObserver(source,result_reader=result_reader)
        return observer.read_pair,observer.verify_final,cleanup,observer.read_result_pair
    except BaseException:
        cleanup();raise

class AwakeningObserver:
    def __init__(self,source,*,clock=time.monotonic,result_reader=None):
        self.source=source;self.service=source.service;self.context=source.context
        self.native=source.native;self.clock=clock
        self.result_reader=result_reader
        self.ticket=source.ticket
        reader=source.identity_reader
        self.pre=getattr(reader,'pre',None);self.rows=getattr(reader,'pre_rows',None)
        if not isinstance(self.ticket,dict) or not isinstance(self.pre,np.ndarray) or not isinstance(self.rows,list):
            raise ValueError('선택 전 장착 장비 증거가 필요합니다')

    def _same_item(self,frame):
        """Compare center icon against every preselection candidate."""
        if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return False
        # Two pixel alignments of the selected icon, as IconIdentity reads them. Thresholds
        # are unchanged: the real awaken screen read .779 on one crop and .870 on the other.
        for detail in (frame[97:117,383:403],frame[97:116,384:403]):
            center=cv2.resize(detail,(18,18),interpolation=cv2.INTER_AREA)
            scores=[]
            for row in self.rows:
                s=row.get('slot') or {};x=s.get('cell_x',-100)+8;y=s.get('cell_y',-100)+8
                candidate=self.pre[y:y+18,x:x+18]
                if candidate.shape!=(18,18,3):return False
                score=float(cv2.matchTemplate(candidate,center,cv2.TM_CCOEFF_NORMED)[0,0])
                if not np.isfinite(score):return False
                scores.append((row.get('index'),score))
            own=next((v for i,v in scores if i==self.ticket['index']),None)
            other=[v for i,v in scores if i!=self.ticket['index']]
            # A white-grade icon draws differently in the centre: .65 to .70 on real screens,
            # still .43 clear of every other item. The lead is what tells items apart.
            floor=.60 if self.ticket.get('grade')=='일반' else .80
            if own is not None and other and own>=floor and own-max(other)>=.30:return True
        return False

    def _read(self,frame):
        if read_zero_to_one(frame) is None or not self._same_item(frame):return None
        from project_adapter import growth_equipment_extra as extra
        material=self.native.inspect_growth_materials(self.service.detector,frame)
        # Only a known active native button + positively sufficient materials
        # may authorize a click; shortage/unknown never authorize it.
        hit=self.service.detector.find(extra.AWAKE_BUTTON,frame,threshold=.95)
        active=False
        if hit:
            x1,y1,x2,y2=hit[2];patch=frame[y1:y2,x1:x2]
            reference=self.service.detector.templates.get(extra.AWAKE_BUTTON)
            if patch.size and reference is not None and reference.size and reference.mean()>0:
                ratio=float(patch.mean()/reference.mean())
                active=.90<=ratio<=1.30
        return {'available':bool(active and material.get('status')=='재료 충분')}

    def read_pair(self):
        observations=[]
        for _ in range(2):
            self.context.checkpoint();self.service.check();frame=self.service.capture();now=self.clock()
            state=self._read(frame)
            if state is None:return {'screen_proof':False}
            self.source.sequence+=1
            observations.append(Observation(self.source.sequence,now,self.source.character,self.ticket['identity'],
                'growth-slot:'+str(self.ticket['index']),self.ticket['grade'],None,None,0,None,None,state['available']))
            self.context.wait(.12)
        a,b=observations
        if not 0<b.captured_at-a.captured_at<=1.5 or self.clock()-a.captured_at>1.5:return {'screen_proof':False}
        if a.awaken_available!=b.awaken_available:return {'screen_proof':False}
        row=next((entry for entry in self.rows if entry.get('index')==self.ticket['index']),None)
        icon=None
        if row:
            slot=row['slot'];x,y=slot['cell_x']+8,slot['cell_y']+8;crop=self.pre[y:y+18,x:x+18]
            if crop.shape==(18,18,3) and 'icon:'+hashlib.sha256(crop.tobytes()).hexdigest()==self.ticket['identity']:
                icon=base64.b64encode(crop.tobytes()).decode('ascii')
        return {'screen_proof':True,'first':a,'second':b,'resource_mode':'native_active',
                'action_mode':'awaken','active_pair_verified':a.awaken_available is True,'item_icon':icon}

    def read_result_pair(self):
        """Proof-only post-reader; the caller must supply a validated stage reader."""
        if not callable(self.result_reader):return {'screen_proof':False}
        observations=[]
        for _ in range(2):
            self.context.checkpoint();self.service.check();frame=self.service.capture();now=self.clock()
            if not _gear_awakening_tab_selected(frame) or not self._same_item(frame):return {'screen_proof':False}
            result=self.result_reader(frame)
            stage=result.get('current') if isinstance(result,dict) else None
            if type(stage) is not int or stage<0:return {'screen_proof':False}
            self.source.sequence+=1
            observations.append(Observation(self.source.sequence,now,self.source.character,self.ticket['identity'],
                'growth-slot:'+str(self.ticket['index']),self.ticket['grade'],None,None,stage,None,None,None))
            self.context.wait(.12)
        a,b=observations
        if a.awakening!=b.awakening or not 0<b.captured_at-a.captured_at<=1.5 or self.clock()-a.captured_at>1.5:
            return {'screen_proof':False}
        return {'screen_proof':True,'first':a,'second':b}

    def verify_final(self,frame,latest,kind):
        if kind!='awaken' or not isinstance(latest,dict):return False
        self.context.checkpoint();self.service.check()
        state=self._read(frame)
        return state is not None and state['available'] is True
