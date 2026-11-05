"""Conservative visual identity candidate; thresholds are fixture-derived only."""
import hashlib
import cv2
import numpy as np


CENTRE_ICON=(578,155,32,30)  # real pixels, inside the panel's frame

class IconIdentity:
    def __init__(self,native,detector):
        self.native=native;self.detector=detector;self.pre=None;self.index=None;self.token=None;self.post_seen=False

    def _same_on_real(self,real,old,index):
        """The panel's icon against every tile before selection, at full size: the chosen tile leads by a wide margin.
        Measured own .91 and the next .53 (hat, 11-05)."""
        from owner_hd import real_box
        x,y,w,h=CENTRE_ICON;needle=real[y:y+h,x:x+w];scores=[]
        for row in self.pre_rows:
            s=row['slot'];cx,cy,cw,ch=real_box((s['cell_x'],s['cell_y'],s['cell_w'],s['cell_h']),rule='right')
            cell=old[cy:cy+ch,cx:cx+cw]
            if cell.shape[0]<h or cell.shape[1]<w:return False
            value=float(cv2.matchTemplate(cell,needle,cv2.TM_CCOEFF_NORMED).max())
            if not np.isfinite(value):return False
            scores.append((value,row['index']))
        own=next((v for v,i in scores if i==index),None);others=[v for v,i in scores if i!=index]
        return own is not None and bool(others) and own>=.75 and own-max(others)>=.25

    def __call__(self,frame,index,selected):
        if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
        rows=self.native.inspect_growth_equipment(self.detector,frame)
        target=next((r for r in rows if r.get('index')==index),None)
        if target is None:return None
        if not selected:
            if self.post_seen or self.index!=index:self.pre=None;self.token=None;self.post_seen=False
            if self.native._growth_selected_slot(frame,rows)==index:return None
            if target.get('equipped') is not True or target.get('equipped_state')!='장착':return None
            if target.get('grade') not in ('흰','파랑','보라'):return None
            s=target['slot'];x=s['cell_x']+8;y=s['cell_y']+8;core=frame[y:y+18,x:x+18]
            if core.shape!=(18,18,3):return None
            token='icon:'+hashlib.sha256(core.tobytes()).hexdigest()
            if self.pre is not None:
                before=self.pre[y:y+18,x:x+18]
                delta=float(np.abs(before.astype(np.float32)-core.astype(np.float32)).mean())
                similarity=float(cv2.matchTemplate(before,core,cv2.TM_CCOEFF_NORMED)[0,0])
                if delta>2.0 or not np.isfinite(similarity) or similarity<.99:return None
                token=self.token
            if self.pre is None:
                self.pre=frame.copy();self.index=index;self.token=token
                self.pre_rows=rows;self.previous_selected=self.native._growth_selected_slot(frame,rows)
            return token
        if self.pre is None or self.index!=index:return None
        self.post_seen=True
        if self.native._growth_selected_slot(frame,rows)!=index:return None
        if {r.get('index') for r in rows}!={r.get('index') for r in self.pre_rows}:return None
        # Detect other inventory-cell changes that could mean a reordered grid.
        for row in self.pre_rows:
            if row['index'] in (index,self.previous_selected):continue
            s=row['slot'];x=s['cell_x']+8;y=s['cell_y']+8
            a=self.pre[y:y+18,x:x+18];b=frame[y:y+18,x:x+18]
            if a.shape!=(18,18,3) or b.shape!=(18,18,3):return None
            if float(np.abs(a.astype(np.float32)-b.astype(np.float32)).mean())>2.0:return None
        real=getattr(frame,'hi',None);old=getattr(self.pre,'hi',None)
        if real is not None and old is not None:return self.token if self._same_on_real(np.asarray(real),np.asarray(old),index) else None
        # Compare the unmarked icon centre against every visible grid candidate;
        # border, E badge, and enhancement digits are outside these crops.
        # The selected icon is rendered on two observed pixel alignments.
        # Current live boots use a19px inner crop one pixel to the right;
        # forcing the old20px crop mixed its border into the same icon (.693).
        # Both variants retain the original .80 identity and .30 uniqueness
        # thresholds, full RGB comparison, all visible competitors and stable
        # grid/selected-slot checks above. No item image or numeric value is
        # hardcoded, and duplicate icons still cannot authorize an action.
        details=(frame[97:117,383:403],frame[97:116,384:403])
        for detail in details:
            if detail.shape not in ((20,20,3),(19,19,3)):continue
            scores=[]
            needle=cv2.resize(detail,(18,18),interpolation=cv2.INTER_AREA)
            for row in self.pre_rows:
                s=row['slot'];x=s['cell_x']+8;y=s['cell_y']+8
                cell=self.pre[y:y+18,x:x+18]
                if cell.shape!=(18,18,3):return None
                value=float(cv2.matchTemplate(cell,needle,cv2.TM_CCOEFF_NORMED)[0,0])
                if not np.isfinite(value):return None
                scores.append((value,row['index']))
            own=next((v for v,i in scores if i==index),None)
            competitors=[v for v,i in scores if i!=index]
            if own is not None and competitors and own>=.80 and own-max(competitors)>=.30:return self.token
            # Dark shoes read .799 against their own tile and .278 against the next (11-05), and ended every visit.
            # A lead that wide names the item as well as the higher score does.
            if own is not None and competitors and own>=.75 and own-max(competitors)>=.45:return self.token
        return None
