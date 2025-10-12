\
import pygame as pg, math, random
from typing import Dict, Any
from .spec import validate_template, TemplateError, _subst
from .palette import named_palette, lerp_color
PTSurface = pg.Surface
def _resolve_color(c, palette):
    if isinstance(c,(list,tuple)) and len(c)==3: return (int(c[0]),int(c[1]),int(c[2]))
    if isinstance(c,str):
        if c.startswith("#") and len(c)==7: return (int(c[1:3],16),int(c[3:5],16),int(c[5:7],16))
        try: return named_palette(c)
        except: 
            if isinstance(palette,dict) and c in palette:
                v = palette[c]; 
                if isinstance(v,(list,tuple)) and len(v)==3: return (int(v[0]),int(v[1]),int(v[2]))
    raise TemplateError(f"Unknown color spec: {c}")
def _value(v,vars_dict): return _subst(v, vars_dict)
def _value_noise(w,h,scale,rng):
    surf = pg.Surface((w,h), pg.SRCALPHA); grid={}
    def gv(ix,iy):
        k=(ix,iy); 
        if k not in grid: grid[k]=rng.random()
        return grid[k]
    for y in range(h):
        for x in range(w):
            gx=x/scale; gy=y/scale; x0=int(gx); y0=int(gy)
            tx=gx-x0; ty=gy-y0
            v00=gv(x0,y0); v10=gv(x0+1,y0); v01=gv(x0,y0+1); v11=gv(x0+1,y0+1)
            s=lambda t:t*t*(3-2*t); sx=s(tx); sy=s(ty)
            a=v00*(1-sx)+v10*sx; b=v01*(1-sx)+v11*sx; v=a*(1-sy)+b*sy
            g=int(v*255); surf.set_at((x,y),(g,g,g,255))
    return surf
def _apply_alpha(dst, src, alpha):
    if alpha is None: alpha=1.0
    if alpha<=0: return
    if alpha>=1.0: dst.blit(src,(0,0)); return
    s=src.copy(); s.set_alpha(int(alpha*255)); dst.blit(s,(0,0))
def op_fill(canvas, p, pal, rng, vars): canvas.fill(_resolve_color(_value(p.get("color","WHITE"),vars), pal))
def op_noise(canvas, p, pal, rng, vars):
    scale=int(_value(p.get("scale",24),vars)); alpha=float(_value(p.get("alpha",0.5),vars))
    noise=_value_noise(canvas.get_width(), canvas.get_height(), max(2,scale), rng)
    c1=p.get("color1"); c2=p.get("color2")
    if c1 and c2:
        c1=_resolve_color(_value(c1,vars),pal); c2=_resolve_color(_value(c2,vars),pal)
        colored=pg.Surface(canvas.get_size(), pg.SRCALPHA)
        for y in range(canvas.get_height()):
            for x in range(canvas.get_width()):
                g=noise.get_at((x,y))[0]/255.0; colored.set_at((x,y), (*lerp_color(c1,c2,g),255))
        _apply_alpha(canvas,colored,alpha)
    else: _apply_alpha(canvas,noise,alpha)
def op_stripes(canvas, p, pal, rng, vars):
    ori=_value(p.get("orientation","h"),vars); gap=int(_value(p.get("gap",8),vars)); w=int(_value(p.get("width",2),vars))
    color=_resolve_color(_value(p.get("color","BLACK"),vars),pal)
    if ori=="h":
        for y in range(0,canvas.get_height(),gap): pg.draw.rect(canvas,color,(0,y,canvas.get_width(),w))
    else:
        for x in range(0,canvas.get_width(),gap): pg.draw.rect(canvas,color,(x,0,w,canvas.get_height()))
def op_dots(canvas,p,pal,rng,vars):
    count=int(_value(p.get("count",50),vars)); rad=int(_value(p.get("radius",3),vars)); color=_resolve_color(_value(p.get("color","BLACK"),vars),pal)
    for _ in range(count):
        x=rng.randint(0,canvas.get_width()-1); y=rng.randint(0,canvas.get_height()-1); pg.draw.circle(canvas,color,(x,y),rad)
def op_blobs(canvas,p,pal,rng,vars):
    count=int(_value(p.get("count",10),vars)); radius=int(_value(p.get("radius",12),vars)); color=_resolve_color(_value(p.get("color","BLACK"),vars),pal); jitter=float(_value(p.get("jitter",0.3),vars))
    for _ in range(count):
        cx=rng.randint(0,canvas.get_width()-1); cy=rng.randint(0,canvas.get_height()-1); r=max(2,int(radius*(0.7+rng.random()*0.6))); pg.draw.circle(canvas,color,(cx,cy),r)
        for _i in range(max(12,r*2)):
            ang=rng.random()*math.tau; rr=r+int(rng.random()*r*jitter); x=int(cx+math.cos(ang)*rr); y=int(cy+math.sin(ang)*rr)
            if 0<=x<canvas.get_width() and 0<=y<canvas.get_height(): canvas.set_at((x,y),color)
def op_outline_rect(canvas,p,pal,rng,vars):
    x=int(_value(p.get("x",1),vars)); y=int(_value(p.get("y",1),vars)); w=int(_value(p.get("w",canvas.get_width()-2),vars)); h=int(_value(p.get("h",canvas.get_height()-2),vars)); color=_resolve_color(_value(p.get("color","BLACK"),vars),pal); thick=int(_value(p.get("thickness",2),vars))
    pg.draw.rect(canvas,color,(x,y,w,h),thick)
def op_gradient_linear(canvas,p,pal,rng,vars):
    c1=_resolve_color(_value(p.get("color1","WHITE"),vars),pal); c2=_resolve_color(_value(p.get("color2","BLACK"),vars),pal); axis=_value(p.get("axis","y"),vars)
    W,H=canvas.get_size()
    for i in range(H if axis=="y" else W):
        t=i/((H-1) if axis=="y" else (W-1))
        col=(int(c1[0]+(c2[0]-c1[0])*t),int(c1[1]+(c2[1]-c1[1])*t),int(c1[2]+(c2[2]-c1[2])*t))
        if axis=="y": pg.draw.line(canvas,col,(0,i),(W-1,i))
        else: pg.draw.line(canvas,col,(i,0),(i,H-1))
def op_sprite_chibi(canvas,p,pal,rng,vars):
    shirt=_resolve_color(_value(p.get("shirt","ROOF_BLUE"),vars),pal); pants=_resolve_color(_value(p.get("pants","BLACK"),vars),pal); skin=_resolve_color(_value(p.get("skin",[238,207,161]),vars),pal); hat=bool(_value(p.get("hat",False),vars))
    W,H=canvas.get_size(); rr=lambda v:int(v)
    pg.draw.rect(canvas,shirt,(rr(W*0.25),rr(H*0.40),rr(W*0.5),rr(H*0.38)))
    pg.draw.circle(canvas,skin,(rr(W*0.5),rr(H*0.25)),rr(min(W,H)*0.18))
    pg.draw.circle(canvas,(30,30,30),(rr(W*0.45),rr(H*0.24)),2); pg.draw.circle(canvas,(30,30,30),(rr(W*0.55),rr(H*0.24)),2)
    pg.draw.rect(canvas,pants,(rr(W*0.28),rr(H*0.72),rr(W*0.15),rr(H*0.22))); pg.draw.rect(canvas,pants,(rr(W*0.57),rr(H*0.72),rr(W*0.15),rr(H*0.22)))
    if hat: pg.draw.rect(canvas,shirt,(rr(W*0.3),rr(H*0.18),rr(W*0.4),3)); pg.draw.circle(canvas,shirt,(rr(W*0.5),rr(H*0.16)),rr(min(W,H)*0.10))
def op_building_simple(canvas,p,pal,rng,vars):
    walls=_resolve_color(_value(p.get("walls","SAND"),vars),pal); roof=_resolve_color(_value(p.get("roof","ROOF_RED"),vars),pal); trim=_resolve_color(_value(p.get("trim","BLACK"),vars),pal); W,H=canvas.get_size()
    import pygame as pg
    pg.draw.rect(canvas,walls,(int(W*0.08),int(H*0.30),int(W*0.84),int(H*0.62)))
    pg.draw.polygon(canvas,roof,[(int(W*0.05),int(H*0.30)),(int(W*0.95),int(H*0.30)),(int(W*0.75),int(H*0.15)),(int(W*0.25),int(H*0.15))])
    pg.draw.rect(canvas,trim,(int(W*0.46),int(H*0.56),int(W*0.08),int(H*0.36)))
    pg.draw.rect(canvas,trim,(int(W*0.22),int(H*0.45),int(W*0.14),int(H*0.12)),2); pg.draw.rect(canvas,trim,(int(W*0.64),int(H*0.45),int(W*0.14),int(H*0.12)),2)
OPS={"fill":op_fill,"noise":op_noise,"stripes":op_stripes,"dots":op_dots,"blobs":op_blobs,"outline_rect":op_outline_rect,"gradient_linear":op_gradient_linear,"sprite_chibi":op_sprite_chibi,"building_simple":op_building_simple}
def render_template_to_surface(tpl: Dict[str,Any]) -> pg.Surface:
    tpl=validate_template(tpl); pg.init(); W,H=tpl["size"]; surf=pg.Surface((W,H), pg.SRCALPHA); import random
    rng=random.Random(int(tpl.get("seed",0) or 0)); palette={}; pal=tpl.get("palette",[])
    for i,col in enumerate(pal): palette[f"P{i}"] = col
    vars=tpl.get("vars",{})
    for layer in tpl["layers"]:
        op=layer.get("op"); fn=OPS.get(op)
        if not fn: raise TemplateError(f"Unknown op: {op}")
        alpha=layer.get("alpha",None); temp=pg.Surface((W,H), pg.SRCALPHA); fn(temp,layer,palette,rng,vars)
        if alpha is None: surf.blit(temp,(0,0))
        else:
            a=float(_subst(alpha,vars))
            if a<=0: continue
            if a>=1: surf.blit(temp,(0,0))
            else: temp.set_alpha(int(a*255)); surf.blit(temp,(0,0))
    return surf
def render_template(tpl: Dict[str,Any], out_path: str):
    surf=render_template_to_surface(tpl); pg.image.save(surf,out_path); return out_path
