\
from typing import Tuple
NAMED = {
    "WHITE": (255,255,255), "BLACK": (0,0,0), "GRAY": (120,120,120), "DARK": (40,40,40),
    "FOREST": (38,120,72), "SAND": (229,201,144), "WATER": (64,133,191),
    "LEAF1": (34,139,94), "LEAF2": (25,120,80), "BARK": (130,90,50),
    "ROOF_RED": (190,60,60), "ROOF_BLUE": (60,110,220), "STONE": (110,110,120),
}
def named_palette(name: str) -> Tuple[int,int,int]:
    up = name.upper()
    if up not in NAMED: raise KeyError(f"Unknown named color: {name}")
    return NAMED[up]
def clamp(x,a=0,b=255): return a if x<a else b if x>b else x
def lerp(a,b,t): return a+(b-a)*t
def lerp_color(c1,c2,t): return (int(lerp(c1[0],c2[0],t)),int(lerp(c1[1],c2[1],t)),int(lerp(c1[2],c2[2],t)))
def srgb(r,g,b): return (int(r),int(g),int(b))
