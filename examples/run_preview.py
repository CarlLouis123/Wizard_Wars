\
import sys, json, os, pygame as pg, yaml
from game.engine.proc_templates import render_template_to_surface
from game.engine.proc_templates.spec import validate_template
def load_any(path):
    with open(path,"r",encoding="utf-8") as f:
        txt=f.read()
    return yaml.safe_load(txt) if path.lower().endswith((".yml",".yaml")) else json.loads(txt)
def main():
    if len(sys.argv)<2: print("Usage: python examples/run_preview.py game/content/templates/grass.json"); raise SystemExit(1)
    tpl_path=sys.argv[1]; tpl=load_any(tpl_path); validate_template(tpl); pg.init()
    surf=render_template_to_surface(tpl); w,h=surf.get_size(); screen=pg.display.set_mode((max(256,w),max(256,h))); clock=pg.time.Clock(); run=True
    while run:
        for e in pg.event.get():
            if e.type==pg.QUIT or (e.type==pg.KEYDOWN and e.key==pg.K_ESCAPE): run=False
        screen.fill((32,32,40)); rect=surf.get_rect(center=(screen.get_width()//2, screen.get_height()//2)); screen.blit(surf,rect); pg.display.set_caption(os.path.basename(tpl_path)); pg.display.flip(); clock.tick(60)
    pg.quit()
if __name__=="__main__": main()
