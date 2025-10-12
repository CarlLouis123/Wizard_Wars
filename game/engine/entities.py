\
import pygame as pg, json
from dataclasses import dataclass
from .proc_templates import render_template_to_surface
def _load_template(path):
    with open(path,"r",encoding="utf-8") as f: return json.load(f)
@dataclass
class Entity:
    x: float; y: float; sprite: pg.Surface; solid: bool=True
    def rect(self):
        r=self.sprite.get_rect(); r.center=(int(self.x),int(self.y)); return r
class Player(Entity):
    def __init__(self,x,y,tile_size,tpl_path):
        tpl=_load_template(tpl_path); surf=render_template_to_surface(tpl); super().__init__(x,y,surf,True); self.speed=150
class NPC(Entity):
    def __init__(self,x,y,tile_size,tpl_path,prompt="Share a short tip."):
        tpl=_load_template(tpl_path); surf=render_template_to_surface(tpl); super().__init__(x,y,surf,True); self.dialogue_prompt=prompt
