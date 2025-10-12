\
import pygame as pg, json, os, random
from .proc_templates import render_template_to_surface
T_GRASS=1; T_SAND=2; T_WATER=3; T_TREE=4
def _load_template(path):
    with open(path,"r",encoding="utf-8") as f: return json.load(f)
class TileMap:
    def __init__(self,w_tiles,h_tiles,tile_size,seed,templates_dir):
        self.w=w_tiles; self.h=h_tiles; self.ts=tile_size; self.seed=seed
        self.base=[[T_GRASS for _ in range(w_tiles)] for _ in range(h_tiles)]
        self.deco=[[0 for _ in range(w_tiles)] for _ in range(h_tiles)]
        self._cache={}; self.templates_dir=templates_dir
        self._tpl_grass=_load_template(os.path.join(templates_dir,"grass.json"))
        self._tpl_sand=_load_template(os.path.join(templates_dir,"sand.json"))
        self._tpl_water=_load_template(os.path.join(templates_dir,"water.json"))
        self._tpl_tree=_load_template(os.path.join(templates_dir,"tree.json"))
        self.generate()
    def generate(self):
        random.seed(self.seed)
        for y in range(self.h):
            for x in range(self.w):
                r=random.random()
                if r<0.10: self.base[y][x]=T_WATER
                elif r<0.25: self.base[y][x]=T_SAND
                else: self.base[y][x]=T_GRASS
                if self.base[y][x]==T_GRASS and random.random()<0.06: self.deco[y][x]=T_TREE
    def walkable(self,tx,ty):
        if not (0<=tx<self.w and 0<=ty<self.h): return False
        return self.base[ty][tx]!=T_WATER
    def _render(self,tpl,variant_key):
        tpl=dict(tpl); tpl["seed"]=int(variant_key)&0xFFFFFFFF; return render_template_to_surface(tpl)
    def get_tile_surface(self,tile_id,variant_key):
        key=(tile_id,variant_key)
        if key in self._cache: return self._cache[key]
        if tile_id==T_GRASS: s=self._render(self._tpl_grass,variant_key)
        elif tile_id==T_SAND: s=self._render(self._tpl_sand,variant_key)
        elif tile_id==T_WATER: s=self._render(self._tpl_water,variant_key)
        else: s=pg.Surface((self.ts,self.ts), pg.SRCALPHA)
        self._cache[key]=s; return s
    def get_deco_surface(self,deco_id,variant_key):
        if deco_id==T_TREE: return self._render(self._tpl_tree,variant_key)
        return None
