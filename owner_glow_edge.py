"""A glow box clipped by the frame edge is not a sparkle (짱군네 11-07 13:05, and the 'event reward mask error' of 11-06).

glow_border.GlowBorder.flickers crops each frame at the candidate box; near the bottom or right edge the crop is
shorter than the mask (23 rows against 34), the boolean index fails, and the whole 이벤트 run stops on IndexError. A
clipped box cannot be judged, so it counts as not flickering, as a static frame does.
"""


def guard(flickers):
    def checked(self,frames,box):
        x,y,r,b=box;h,w=self.mask.shape[:2]
        if any(f[y:b,x:r].shape[:2]!=(h,w) for f in frames):return False
        return flickers(self,frames,box)
    checked._owner_edge=True
    return checked


def install(gui=None):
    try:from glow_border import GlowBorder
    except ImportError:return
    if not getattr(GlowBorder.flickers,'_owner_edge',False):GlowBorder.flickers=guard(GlowBorder.flickers)
