"""1 or 7 by the glyph's own shape, for the game's pixel font at 1366x768.

The root of every 1-read-as-7 (각성 1→7, 41>>47, 장식1→7, 강화 1→7, 11-05..06): this font's 1 is a full-width bar on top and a
straight stem down its right side, a 7 with no slant. The OCR engine was trained on ordinary fonts and keeps calling it 7,
or nothing at all when the 1 stands alone in a small crop. The pixels settle it: below the bar a 1's stem keeps one column,
a 7's stroke walks left. A glyph that is neither shape is left to the engine.
"""
import re
import numpy as np

WHITE=170;GREY=50;MIN_HEIGHT=8


def glyphs(area):
    """White-ink glyphs, left to right: (x, y, w, h, mask)."""
    import cv2
    a=np.asarray(area).astype(np.int16)
    if a.ndim!=3 or a.shape[0]<MIN_HEIGHT or a.shape[1]<2:return []
    mask=((a.min(2)>WHITE)&(a.max(2)-a.min(2)<GREY)).astype(np.uint8)
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask,connectivity=8)
    found=[(int(x),int(y),int(w),int(h),labels[y:y+h,x:x+w]==i) for i,(x,y,w,h,_) in enumerate(stats) if i and h>=MIN_HEIGHT]
    return sorted(found,key=lambda g:g[0])


def one_or_seven(mask):
    """'1', '7' or None for one glyph's mask."""
    h,w=mask.shape
    if h<MIN_HEIGHT or w<2 or w>h:return None
    top=mask[:max(2,round(h*.2))]
    if not all(row.sum()>=max(2,round(w*.8)) for row in top):return None
    centres=[]
    for row in mask[round(h*.4):]:
        xs=np.flatnonzero(row)
        if not len(xs):return None
        if xs[-1]-xs[0]+1!=len(xs) or len(xs)>max(3,round(w*.5)):return None   # one thin run, or it is another digit
        centres.append(xs.mean())
    if len(centres)<3:return None
    if max(centres)-min(centres)<=1 and centres[-1]>=(w-1)*.5:return '1'
    drift=centres[0]-centres[-1]
    if drift>=2 and all(b<=a+.5 for a,b in zip(centres,centres[1:])):return '7'
    return None


NUMERIC=re.compile(r'^[\d+\-−%/,.()>»→←\s]*\d[\d+\-−%/,.()>»→←\s]*$')


def settle(text,area):
    """The engine's text with each 1 or 7 decided by its glyph, when the glyphs line up one to one with the digits."""
    if not isinstance(text,str) or not NUMERIC.match(text) or not re.search('[17]',text):return text
    found=glyphs(area)
    if not found:return text
    tallest=max(g[3] for g in found)
    tall=[g for g in found if g[3]>=tallest*.75]
    digits=[i for i,c in enumerate(text) if c.isdigit()]
    if len(tall)!=len(digits):return text
    chars=list(text)
    for index,glyph in zip(digits,tall):
        if chars[index] in '17':
            shape=one_or_seven(glyph[4])
            if shape:chars[index]=shape
    return ''.join(chars)


def lone_one(area):
    """True when the area's only tall glyph is a 1: the engine often reads a lone 1 as nothing, T or ]."""
    found=glyphs(area)
    if not found:return False
    tallest=max(g[3] for g in found)
    tall=[g for g in found if g[3]>=tallest*.75]
    return len(tall)==1 and one_or_seven(tall[0][4])=='1'
