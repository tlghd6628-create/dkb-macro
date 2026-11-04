"""Compare fixed text under independently measured modal dimming.

This changes only a comparison, never a capture, numeric OCR or input proof.
The caller must separately prove the exact supported overlay and character.
"""
import hashlib,numpy as np

def inventory_header(frame,character):
    """Match the canonical name at either existing level-dependent location."""
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
    from owner_progression import inventory_parts
    if inventory_parts(frame)!=(True,True):return None
    matches=[]
    for x in (62,68):
        name=frame[9:25,x:x+33];ink=name.min(axis=2)>150
        if ink.sum()>=8 and hashlib.sha256(ink.tobytes()).hexdigest()[:24]==character:matches.append((x,name))
    return matches[0] if len(matches)==1 else None

def same_dimmed_text(reference,current,anchor_reference,anchor_current):
    patches=(reference,current,anchor_reference,anchor_current)
    if any(not isinstance(p,np.ndarray) or p.dtype!=np.uint8 or p.ndim!=3 or p.shape[2]!=3 for p in patches):return False
    if reference.shape!=current.shape or anchor_reference.shape!=anchor_current.shape:return False
    if reference.size<24 or anchor_reference.size<24:return False
    a=anchor_reference.min(axis=2).astype(np.float64).ravel()
    b=anchor_current.min(axis=2).astype(np.float64).ravel()
    if a.std()<25:return False
    gain,bias=np.linalg.lstsq(np.column_stack((a,np.ones(a.size))),b,rcond=None)[0]
    if not .45<=gain<=1.20 or abs(bias)>10 or np.abs(b-a*gain-bias).max()>2:return False
    expected=reference.min(axis=2).astype(np.float64)
    actual=(current.min(axis=2).astype(np.float64)-bias)/gain
    ink=expected>150
    return bool(ink.sum()>=8 and np.abs(actual-expected).max()<=3 and np.array_equal(actual>150,ink))
