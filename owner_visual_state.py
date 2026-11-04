"""Read label identity separately from enabled/disabled state and consumption.

Brightness is not a label identity. Only callers with independent foreground
landmarks may use this shape proof to classify a screen. It never proves an
enabled button, quantity, cost, selected item or successful action.
"""
import numpy as np

def same_label(frame, reference, box, *, correlation=.97):
    if not isinstance(frame,np.ndarray) or frame.dtype!=np.uint8 or frame.ndim!=3:return False
    if not isinstance(reference,np.ndarray) or reference.dtype!=np.uint8:return False
    x,y,w,h=box
    if min(x,y)<0 or w<8 or h<5:return False
    patch=frame[y:y+h,x:x+w]
    if patch.shape!=reference.shape or patch.ndim!=3 or patch.shape[2]!=3:return False
    a=reference.min(axis=2).astype('float64').ravel()
    b=patch.min(axis=2).astype('float64').ravel()
    if min(a.std(),b.std())<5:return False
    contrast=np.percentile(b,95)-np.percentile(b,5)
    if contrast<20:return False
    centered_a=a-a.mean();centered_b=b-b.mean()
    score=float(np.dot(centered_a,centered_b)/(np.linalg.norm(centered_a)*np.linalg.norm(centered_b)))
    if not np.isfinite(score) or score<correlation:return False
    gain=float(np.dot(centered_a,centered_b)/np.dot(centered_a,centered_a))
    residual=b-(a*gain+(b.mean()-gain*a.mean()))
    # Require the complete text geometry, including its negative space.
    return bool(gain>0 and np.percentile(np.abs(residual),99)/contrast<=.16)
