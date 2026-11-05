"""Existing native gear detection + selection + numeric reader, conservative.

An integration must provide observed same-item identity and resource readers;
they do not yet exist. None/uncertainty blocks before native selection/input.
This module is not installed or started automatically.
"""
import base64,json,time
from dataclasses import replace
from pathlib import Path
import numpy as np
from collections import deque
from owner_gear_decision_candidate import Observation


class Hold(RuntimeError):pass


class Observer:
    def __init__(self,service,context,character,native,identity_reader,resources_reader,*,clock=time.monotonic,observation_sink=None):
        if not character:raise Hold('캐릭터 확인 필요')
        if resources_reader is None:
            from owner_gear_resource_candidate import NativeResources
            resources_reader=NativeResources(native,service.detector,root=service.adapter.project.root)
        if not callable(resources_reader):raise Hold('재료·버튼 판독기 필요')
        if identity_reader is None:
            from owner_gear_identity_candidate import IconIdentity
            identity_reader=IconIdentity(native,service.detector)
        if not callable(identity_reader):raise Hold('장비 동일성 판독기 필요')
        self.service,self.context,self.character,self.native=service,context,character,native
        self.identity_reader,self.resources_reader,self.clock=identity_reader,resources_reader,clock
        self.observation_sink=observation_sink
        self.sequence=0;self.ticket=None;self.logical_identity=None;self.minimum_level=None;self.last_reason='미확인';self.last_levels=[]
        self._last_numeric_proof=None;self.last_timings={}
        self.use_raw_input_numbers=False
        self.last_frames=deque(maxlen=2)
        path=Path(service.adapter.project.root)/'profiles/DKB/ocr_regions.json'
        self.config=json.loads(path.read_text(encoding='utf-8'))['regions']['OCR_성장_장비레벨']

    def capture(self):
        self.context.checkpoint();self.service.check();frame=self.service.capture();stamp=self.clock();self.sequence+=1
        if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:raise Hold('화면 크기 확인 필요')
        self.last_frames.append(frame.copy())
        return self.sequence,stamp,frame

    def items(self,frame):return self.native.inspect_growth_equipment(self.service.detector,frame)

    def _both_engines(self,frame):
        """A lone digit sits near the reader's .85 (3 read .83). Either engine may name it at the
        same .85 on a crop of the digit alone, if they do not differ. Callers still need two frames."""
        import re
        from tools.ocr_support import get_paddle_engine
        from owner_progression import resized
        box=self._number_box(frame)
        if box is None:return None
        root=self.service.adapter.project.root;values=set();minimum=self.config.get('threshold',.85)
        for language in ('number','korean'):
            for page in get_paddle_engine(root,language=language).predict(resized(frame,(box[0]+51,box[1]+3,26,20))):
                for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
                    if score>=minimum and re.fullmatch(r'\d{1,2}',str(text).strip()):values.add(int(text))
        return values.pop() if len(values)==1 else None

    def _number_box(self,frame):
        hit=self.service.detector.find(self.config['template_roi'],frame,region=self.config['search_roi'],threshold=self.config.get('threshold',.85))
        if not hit:return None
        x=hit[2][2]+self.config['rel_x'];y=hit[2][3]+self.config['rel_y'];w=self.config['w'];h=self.config['h']
        if any(type(v) is not int for v in (x,y,w,h)) or not 0<=x<x+w<=897 or not 0<=y<y+h<=479:return None
        return x,y,w,h

    @staticmethod
    def _same_number_pixels(source,current,box):
        import cv2
        if box is None:return False
        x,y,w,h=box;a=source[y:y+h,x:x+w];b=current[y:y+h,x:x+w]
        if a.shape!=(h,w,3) or b.shape!=a.shape or not a.size:return False
        # Ignore the animated scenery behind the transparent panel. Every
        # white/gold foreground pixel in the *whole* current→next numeric ROI
        # must be identical in position; a changed digit cannot reuse its OCR.
        def ink(im):
            hsv=cv2.cvtColor(im,cv2.COLOR_RGB2HSV)
            mask=(im.min(axis=2)>150)|((hsv[:,:,0]>=12)&(hsv[:,:,0]<=40)&(hsv[:,:,1]>100)&(hsv[:,:,2]>150))
            # The native number ROI also clips a flashing frame rim above
            # the digits. Actual rim components are 1..3px high, digits 8px.
            # Keep whole text-height components, then require EXACT masks
            # and the original RGB tolerance. Blank/tiny remnants cannot
            # certify a number. No OCR value is invented or refreshed here.
            count,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
            keep=np.zeros(count,dtype=bool)
            for i in range(1,count):keep[i]=stats[i,cv2.CC_STAT_HEIGHT]>=max(5,h//5)
            return keep[labels]
        left,right=ink(a),ink(b)
        if int(left.sum())<3 or int(left.sum())>=left.size-3 or not np.array_equal(left,right):return False
        return float(np.abs(a[left].astype(np.float32)-b[right].astype(np.float32)).mean())<=5

    def _revalidate_slow_pair(self,observations,frames,resources,require_resource):
        """Produce NEW observations only after two new captures match OCR.

        This does not enlarge the1.5sec action lifetime or relabel an old
        screenshot with the current time. Slow OCR is computation; its result
        is reusable only while the complete recognized number ROI is unchanged.
        """
        if len(observations)!=2 or len(frames)!=2:return None
        boxes=[self._number_box(frame) for frame in frames]
        if boxes[0] is None or boxes[0]!=boxes[1]:return None
        box=boxes[0]
        if not self._same_number_pixels(frames[0],frames[1],box):return None
        fresh=[];fresh_frames=[]
        for before in observations:
            seq,at,frame=self.capture();rows=self.items(frame)
            if (self.native._growth_selected_slot(frame,rows)!=self.ticket['index']
                or self.identity_reader(frame,self.ticket['index'],True)!=self.ticket['identity']
                or self._number_box(frame)!=box or not self._same_number_pixels(frames[-1],frame,box)):
                self.last_reason='판독 후 장비·숫자 영역 변경';return None
            if require_resource:
                current=self.resources_reader(frame);prior=resources[-1]
                keys=('verified','cost','balance','currency','active','mode','button_name','opening')
                if not isinstance(current,dict) or not isinstance(prior,dict) or any(current.get(k)!=prior.get(k) for k in keys):
                    self.last_reason='판독 후 재료·실행 버튼 변경';return None
            fresh.append(replace(before,sequence=seq,captured_at=at));fresh_frames.append(frame)
            self.context.wait(.08)
        a,b=fresh
        if not 0<b.captured_at-a.captured_at<=1.5 or not 0<=self.clock()-a.captured_at<=1.5:
            self.last_reason='새 화면 재검증 시간 초과';return None
        self.ticket['captured_at']=b.captured_at
        return fresh,fresh_frames

    def prepare_and_select(self,index,*,selection_check=None):
        if type(index) is not int or index<1:raise Hold('장비 칸 확인 필요')
        first=self.capture();self.context.wait(.12);second=self.capture()
        if not 0<second[1]-first[1]<=1.5:raise Hold('선택 전 화면 지연')
        evidence=[]
        for capture in (first,second):
            rows=self.items(capture[2]);selected=self.native._growth_selected_slot(capture[2],rows)
            if selected==index:raise Hold('선택 전 장비 등급 확인 필요')
            row=next((r for r in rows if r.get('index')==index),None)
            if not row or row.get('equipped') is not True or row.get('equipped_state')!='장착':raise Hold('장착 장비 확인 필요')
            grade={'흰':'일반','파랑':'희귀','보라':'영웅'}.get(row.get('grade'))
            identity=self.identity_reader(capture[2],index,False)
            if grade is None or not isinstance(identity,str) or not identity.strip():raise Hold('선택 전 등급·동일 장비 확인 필요')
            slot=row.get('slot') or {};x,y,w,h=(slot.get(k) for k in ('cell_x','cell_y','cell_w','cell_h'))
            if not all(type(v) is int and v>0 for v in (x,y,w,h)):raise Hold('장비 위치 확인 필요')
            evidence.append((grade,identity,(x,y,w,h),row))
        if evidence[0][:3]!=evidence[1][:3]:raise Hold('선택 전 장비 화면 불일치')
        if self.clock()-second[1]>1.5:raise Hold('선택 전 장비 화면 지연')
        self.context.checkpoint();self.service.check()
        if callable(selection_check) and selection_check() is not True:raise Hold('캐릭터 또는 설정 변경')
        # Existing native routine is used only for selection, never growth.
        self.native.select_growth_equipment(self.service,evidence[1][3])
        self.context.checkpoint();self.service.check()
        # The tile flashes after a click and reads as unselected until the flash ends.
        def graded(listed):return sum(r.get('grade') in ('흰','파랑','보라') for r in listed)
        shown=graded(self.items(second[2]))
        for _ in range(20):
            frame=self.capture()[2];listed=self.items(frame);chosen=self.native._growth_selected_slot(frame,listed)
            if chosen==index:break
            # The awaken list narrows to the chosen item and its duplicates, so the index moves and the wait above ran out
            # every time: 4 s per item with nothing to wait for (18:21).
            if chosen is not None and graded(listed)<shown:break
            self.context.wait(.2);self.context.checkpoint()
        self.ticket={'index':index,'grade':evidence[1][0],'identity':evidence[1][1],'row':evidence[1][3],
                     'captured_at':second[1]}
        return self.ticket

    def read_pair(self,require_resource=True):
        self.last_levels=[];self.last_reason='미확인';self._last_numeric_proof=None
        if self.ticket is None:self.last_reason='장비 미선택';return {'screen_proof':False}
        if self.clock()-self.ticket['captured_at']>10:self.last_reason='선택 확인 시간 초과';return {'screen_proof':False}
        observations=[];resources=[];frames=[];detail_ms=[];resource_ms=[];started=self.clock()
        for _ in range(2):
            seq,at,frame=self.capture();rows=self.items(frame)
            if self.native._growth_selected_slot(frame,rows)!=self.ticket['index']:
                self.last_reason='선택 칸 불일치';return {'screen_proof':False}
            if self.identity_reader(frame,self.ticket['index'],True)!=self.ticket['identity']:
                self.last_reason='장비 아이콘 불일치';return {'screen_proof':False}
            options={'item':self.ticket['row']}
            if type(self.minimum_level) is int and self.minimum_level>=0:options['minimum_level']=self.minimum_level
            stage_start=self.clock()
            if self.use_raw_input_numbers:
                # After a numeric disagreement, restart with two NEW raw ROI
                # reads using the existing MDT reader. No earlier value, max,
                # minimum or pending-result observation authorizes this input.
                from tools.ocr_support import read_growth_number_mdt
                box=self._number_box(frame)
                if box is None:self.last_reason='강화 숫자 위치 미확인';return {'screen_proof':False}
                x,y,w,h=box
                result=read_growth_number_mdt(Path(self.service.adapter.project.root),frame[y:y+h,x:x+w].copy(),
                    context=self.context,threshold=self.config.get('threshold',.85))
                value=result.get('value') if isinstance(result,dict) else None
                confidence=result.get('confidence') if isinstance(result,dict) else None
                if type(value) is not int:
                    value=self._both_engines(frame);confidence=1. if type(value) is int else None
                if (type(value) is not int or not 0<=value<=50 or type(confidence) not in (int,float)
                    or confidence<self.config.get('threshold',.85)):
                    self.last_reason='강화 원본 숫자 미확인';return {'screen_proof':False}
                detail={'enhancement':value}
            else:detail=self.native.read_growth_equipment_detail(self.service,frame,self.config,**options)
            detail_ms.append(round((self.clock()-stage_start)*1000,1))
            level=detail.get('enhancement') if isinstance(detail,dict) else None
            if type(level) is not int:level=self._both_engines(frame)
            if type(level) is not int or level<0:self.last_reason='강화 수치 판독 실패';return {'screen_proof':False}
            if type(self.minimum_level) is int and level<self.minimum_level:
                self.last_reason='이전 확인 수치보다 낮음';return {'screen_proof':False}
            self.last_levels.append(level)
            stage_start=self.clock();resource=self.resources_reader(frame);resource_ms.append(round((self.clock()-stage_start)*1000,1))
            verified_resource=isinstance(resource,dict) and resource.get('verified') is True
            opening=verified_resource and resource.get('opening') is True
            available=((level%10==9 if opening else True) and
                       resource.get('active') is True) if verified_resource else None
            observations.append(Observation(seq,at,self.character,self.logical_identity or self.ticket['identity'],
                'growth-slot:'+str(self.ticket['index']),self.ticket['grade'],level,None,None,available,None,None))
            resources.append(resource);frames.append(frame)
            self.context.wait(.12)
        a,b=observations
        if a.enhancement!=b.enhancement:self.last_reason='강화 수치 불일치';return {'screen_proof':False}
        self.last_timings={'detail_ms':detail_ms,'resource_ms':resource_ms,'initial_pair_ms':round((self.clock()-started)*1000,1)}
        if self.clock()-a.captured_at>1.5 or not 0<b.captured_at-a.captured_at<=1.5:
            refreshed=self._revalidate_slow_pair(observations,frames,resources,require_resource)
            if refreshed is None:
                if self.last_reason=='미확인':self.last_reason='두 화면 판독 시간 초과 · 새 숫자 영역 확인 실패'
                return {'screen_proof':False}
            observations,frames=refreshed;a,b=observations
            self.last_timings['refreshed_after_ocr']=True
        self.ticket['captured_at']=b.captured_at
        if callable(self.observation_sink):
            try:
                from datetime import datetime,timezone
                display_icon=None
                pre=getattr(self.identity_reader,'pre',None)
                old=next((r for r in getattr(self.identity_reader,'pre_rows',()) if r.get('index')==self.ticket['index']),None)
                if isinstance(pre,np.ndarray) and old:
                    s=old['slot'];ix,iy=s['cell_x']+8,s['cell_y']+8;core=pre[iy:iy+18,ix:ix+18]
                    if core.shape==(18,18,3):display_icon=base64.b64encode(core.tobytes()).decode('ascii')
                self.observation_sink({'character':self.character,'item_identity':a.item,
                    'grid_index':self.ticket['index'],'grade':a.grade,'enhancement':a.enhancement,
                    'breakthrough':a.breakthrough,'awakening':a.awakening,
                    'observed_at':datetime.now(timezone.utc).isoformat(),
                    'source':'paired_growth_screen','verified_fields':['grade','enhancement'],'item_icon':display_icon})
            except Exception:
                # Diagnostic storage/display cannot authorize or halt input.
                pass
        if not require_resource:
            self.last_reason='결과 수치 확인'
            return {'screen_proof':True,'first':a,'second':b}
        if any(not isinstance(r,dict) or r.get('verified') is not True for r in resources):
            self.last_reason='재료 또는 실행 버튼 미확인';return {'screen_proof':False}
        if any(resources[0].get(k)!=resources[1].get(k) for k in ('cost','balance','currency','active','mode','button_name','opening')):
            self.last_reason='재료 또는 버튼 불일치';return {'screen_proof':False}
        r=resources[0]
        box=self._number_box(frames[-1])
        if box is None:self.last_reason='최종 숫자 영역 미확인';return {'screen_proof':False}
        self._last_numeric_proof=(frames[-1].copy(),box,b.captured_at,a.enhancement,dict(r))
        self.last_reason='두 화면 확인'
        icon=None
        previous=getattr(self.identity_reader,'pre',None);previous_rows=getattr(self.identity_reader,'pre_rows',())
        row=next((entry for entry in previous_rows if entry.get('index')==self.ticket['index']),None)
        if isinstance(previous,np.ndarray) and row:
            slot=row['slot'];x,y=slot['cell_x']+8,slot['cell_y']+8;crop=previous[y:y+18,x:x+18]
            if crop.shape==(18,18,3):icon=base64.b64encode(crop.tobytes()).decode('ascii')
        return {'screen_proof':True,'first':a,'second':b,'cost_pair_verified':r.get('mode')!='native_active',
                'active_pair_verified':r.get('mode')=='native_active','resource_mode':r.get('mode'),
                'currency':r.get('currency'),'cost':r.get('cost'),'balance':r.get('balance'),
                'button_name':r.get('button_name'),'opening':r.get('opening'),'item_icon':icon}

    def read_result_pair(self):
        """Fresh result-only proof via the native final raw-crop OCR reader.

        This value cannot authorize a new resource input: read_pair and
        verify_final remain the separate input-side decision path.
        """
        from tools.ocr_support import read_growth_number_mdt
        self.last_levels=[];self.last_reason='결과 판독 미확인'
        if self.ticket is None:return {'screen_proof':False}
        if self.clock()-self.ticket['captured_at']>10:
            self.last_reason='선택 확인 시간 초과';return {'screen_proof':False}
        observations=[];frames=[]
        for _ in range(2):
            seq,at,frame=self.capture();rows=self.items(frame)
            if self.native._growth_selected_slot(frame,rows)!=self.ticket['index']:
                self.last_reason='결과 선택 칸 불일치';return {'screen_proof':False}
            if self.identity_reader(frame,self.ticket['index'],True)!=self.ticket['identity']:
                self.last_reason='결과 장비 아이콘 불일치';return {'screen_proof':False}
            hit=self.service.detector.find(self.config['template_roi'],frame,region=self.config['search_roi'],threshold=self.config.get('threshold',.85))
            if not hit:self.last_reason='결과 숫자 위치 미확인';return {'screen_proof':False}
            box=hit[2];x=box[2]+self.config['rel_x'];y=box[3]+self.config['rel_y'];w=self.config['w'];h=self.config['h']
            if any(type(v) is not int for v in (x,y,w,h)) or x<0 or y<0 or w<=0 or h<=0 or x+w>897 or y+h>479:
                self.last_reason='결과 숫자 영역 미확인';return {'screen_proof':False}
            result=read_growth_number_mdt(Path(self.service.adapter.project.root),frame[y:y+h,x:x+w].copy(),
                                          context=self.context,threshold=self.config.get('threshold',.85))
            level=result.get('value') if isinstance(result,dict) else None
            confidence=result.get('confidence') if isinstance(result,dict) else None
            if type(level) is not int:
                # This box finds nothing on one digit (0 to 9), so the first enhance of an item never
                # confirmed. The input-side reader sees those, and still needs two agreeing frames.
                detail=self.native.read_growth_equipment_detail(self.service,frame,self.config,item=self.ticket['row'])
                level=detail.get('enhancement') if isinstance(detail,dict) else None
                if type(level) is not int:level=self._both_engines(frame)
                confidence=1. if type(level) is int else None
            if (type(level) is not int or not 0<=level<=50 or type(confidence) not in (int,float)
                or confidence<self.config.get('threshold',.85)):
                self.last_reason='결과 숫자 판독 실패';return {'screen_proof':False}
            if type(self.minimum_level) is int and level<self.minimum_level:
                self.last_reason='이전 확인 수치보다 낮음';return {'screen_proof':False}
            self.last_levels.append(level)
            observations.append(Observation(seq,at,self.character,self.logical_identity or self.ticket['identity'],
                'growth-slot:'+str(self.ticket['index']),self.ticket['grade'],level,None,None,None,None,None))
            frames.append(frame)
            self.context.wait(.12)
        a,b=observations
        if a.enhancement!=b.enhancement:
            self.last_reason='결과 수치 불일치 또는 시간 초과';return {'screen_proof':False}
        if not 0<b.captured_at-a.captured_at<=1.5 or not 0<=self.clock()-a.captured_at<=1.5:
            refreshed=self._revalidate_slow_pair(observations,frames,(),False)
            if refreshed is None:
                self.last_reason='결과 수치 불일치 또는 시간 초과';return {'screen_proof':False}
            observations,frames=refreshed;a,b=observations
        self.ticket['captured_at']=b.captured_at
        self.last_reason='MDT 결과 전용 두 화면 확인'
        return {'screen_proof':True,'first':a,'second':b,'source':'native_mdt_result_only'}

    def verify_final(self,frame,latest,kind):
        def reject(reason):self.last_reason='입력 직전 · '+reason;return False
        if kind!='enhance' or self.ticket is None or not isinstance(latest,dict):return reject('선택 기록 미확인')
        start=self.clock();self.context.checkpoint();self.service.check()
        if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return reject('화면 크기 미확인')
        self.last_frames.append(frame.copy())
        rows=self.items(frame)
        if self.native._growth_selected_slot(frame,rows)!=self.ticket['index']:return reject('선택 칸 변경')
        if self.identity_reader(frame,self.ticket['index'],True)!=self.ticket['identity']:return reject('장비 아이콘 변경')
        proof=self._last_numeric_proof;prior=latest.get('second');resource=self.resources_reader(frame)
        if not isinstance(prior,Observation) or not isinstance(resource,dict) or not proof:return reject('숫자·버튼 근거 미확인')
        source,box,stamp,level,saved_resource=proof
        if not 0<=self.clock()-stamp<=1.5:return reject('숫자 근거 시간 초과')
        if self._number_box(frame)!=box:return reject('숫자 위치 변경')
        if not self._same_number_pixels(source,frame,box):return reject('숫자 영역 변경')
        if level!=prior.enhancement:return reject('현재 수치 불일치')
        if self.clock()-start>1.5:return reject('최종 검사 시간 초과')
        opening=resource.get('opening') is True
        material_ok=prior.enhancement%10==9 if opening else resource.get('verified') is True
        valid=(material_ok and
                resource.get('verified') is True and resource.get('active') is True and
                resource.get('mode')==latest.get('resource_mode') and
                resource.get('button_name')==latest.get('button_name') and resource.get('opening')==latest.get('opening') and
                resource.get('currency')==latest.get('currency') and resource.get('cost')==latest.get('cost') and
                resource.get('balance')==latest.get('balance'))
        if not valid:return reject('실행 버튼 상태 변경')
        self.last_reason='입력 직전 같은 장비·현재 수치·활성 버튼 확인';return True
