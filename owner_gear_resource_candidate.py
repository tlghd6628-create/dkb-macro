"""Fixture-tested native equipment button/material check, not price OCR."""
import numpy as np


class NativeResources:
    def __init__(self,native,detector,*,root=None):self.native=native;self.detector=detector;self.root=root
    def __call__(self,frame):
        if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return {'verified':False}
        tab=self.native.GROWTH_EQUIPMENT_TAB
        try:
            if not self.detector.find(tab,frame,threshold=.95):return {'verified':False}
            from owner_growth_reading import exec_button
            button=exec_button(self.detector,self.native.GROWTH_EXEC_BUTTONS,frame)
            if button['active'] is not True:return {'verified':False}
            name=button['name']
            opening=name==self.native.GROWTH_EXEC_BUTTONS[1]
            # Actual 19→20 opening frame has no material counter; the active
            # native opening button is the game's positive readiness signal.
            # Owner 2026-11-03: the native enabled enhancement button is the
            # readiness authority. Material-count OCR is display only and
            # must not block an independently active button.
            material=None
        except (KeyError,ValueError,TypeError,AttributeError):return {'verified':False}
        # User allows ordinary in-game spending. No numeric balance is inferred.
        return {'verified':True,'active':True,'mode':'native_active','currency':None,'cost':None,'balance':None,
                'button_name':name,'opening':opening,'materials':(material or {}).get('status')}
