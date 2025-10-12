\
import pygame as pg, sys, math, random, os
from engine.tilemap import TileMap, T_TREE
from engine.entities import Player, NPC
import settings as S
HERE=os.path.dirname(__file__); TPL_DIR=os.path.join(HERE,"content","templates")
def main():
    pg.init(); pg.display.set_caption("PokeLike - Template Driven"); screen=pg.display.set_mode((S.WINDOW_W,S.WINDOW_H)); clock=pg.time.Clock(); font=pg.font.SysFont(None,20)
    random.seed(S.SEED); tilemap=TileMap(S.WORLD_W,S.WORLD_H,S.TILE_SIZE,S.SEED,TPL_DIR)
    player=Player(S.WINDOW_W//2,S.WINDOW_H//2,S.TILE_SIZE, os.path.join(TPL_DIR,"player_chibi.json"))
    npcs=[]
    for _ in range(8):
        while True:
            tx=random.randint(0,S.WORLD_W-1); ty=random.randint(0,S.WORLD_H-1)
            if tilemap.walkable(tx,ty):
                nx=tx*S.TILE_SIZE+S.TILE_SIZE//2; ny=ty*S.TILE_SIZE+S.TILE_SIZE//2; npcs.append(NPC(nx,ny,S.TILE_SIZE, os.path.join(TPL_DIR,"npc_chibi.json"))); break
    from engine.dialogue import DialogueEngine
    dlg=DialogueEngine(use_gemini=S.USE_GEMINI, model_name=S.MODEL_NAME); dialogue_text=""
    def world_to_tile(x,y): return int(x//S.TILE_SIZE), int(y//S.TILE_SIZE)
    def collides(nx,ny): tx,ty=world_to_tile(nx,ny); return not tilemap.walkable(tx,ty)
    running=True; cam_x=player.x-S.WINDOW_W/2; cam_y=player.y-S.WINDOW_H/2
    while running:
        dt=clock.tick(S.FPS)/1000.0
        for e in pg.event.get():
            if e.type==pg.QUIT: running=False
            elif e.type==pg.KEYDOWN:
                if e.key==pg.K_ESCAPE: running=False
                elif e.key==pg.K_g: dlg.use_gemini=not dlg.use_gemini
                elif e.key==pg.K_e:
                    talking=None; best=56
                    for n in npcs:
                        d=math.hypot(n.x-player.x, n.y-player.y)
                        if d<best: best=d; talking=n
                    if talking: dialogue_text=dlg.npc_line(talking.dialogue_prompt)
        keys=pg.key.get_pressed(); dx=dy=0.0; spd=S.PLAYER_SPEED
        if keys[pg.K_LEFT] or keys[pg.K_a]: dx-=spd
        if keys[pg.K_RIGHT] or keys[pg.K_d]: dx+=spd
        if keys[pg.K_UP] or keys[pg.K_w]: dy-=spd
        if keys[pg.K_DOWN] or keys[pg.K_s]: dy+=spd
        nx=player.x+dx*dt; ny=player.y+dy*dt
        if not collides(nx,player.y): player.x=nx
        if not collides(player.x,ny): player.y=ny
        cam_x=player.x-S.WINDOW_W/2; cam_y=player.y-S.WINDOW_H/2
        screen.fill((0,0,0)); ts=S.TILE_SIZE
        stx=max(0,int(cam_x//ts)-2); sty=max(0,int(cam_y//ts)-2); etx=min(tilemap.w,int((cam_x+S.WINDOW_W)//ts)+3); ety=min(tilemap.h,int((cam_y+S.WINDOW_H)//ts)+3)
        for ty in range(sty,ety):
            for tx in range(stx,etx):
                t=tilemap.base[ty][tx]; surf=tilemap.get_tile_surface(t,(tx*73856093)^(ty*19349663)); screen.blit(surf,(tx*ts-cam_x, ty*ts-cam_y))
        for ty in range(sty,ety):
            for tx in range(stx,etx):
                d=tilemap.deco[ty][tx]
                if d:
                    surf=tilemap.get_deco_surface(d,(tx*83492791)^(ty*29765729))
                    if surf:
                        rect=surf.get_rect(); rect.center=(tx*ts-cam_x+ts//2, ty*ts-cam_y+ts//2); screen.blit(surf,rect)
        for n in npcs:
            rect=n.sprite.get_rect(center=(n.x-cam_x, n.y-cam_y)); screen.blit(n.sprite,rect)
        rect=player.sprite.get_rect(center=(player.x-cam_x, player.y-cam_y)); screen.blit(player.sprite,rect)
        ui=[f"FPS: {clock.get_fps():.0f}", f"G (Gemini): {'ON' if dlg.use_gemini else 'OFF'}", "Move: WASD/Arrows | Talk: E | Toggle: G | Esc: Quit"]
        for i,line in enumerate(ui): screen.blit(font.render(line,True,(255,255,255)), (8,8+i*18))
        if dialogue_text:
            box_h=88; pg.draw.rect(screen,(0,0,0),(0,S.WINDOW_H-box_h,S.WINDOW_W,box_h)); pg.draw.rect(screen,(255,255,255),(0,S.WINDOW_H-box_h,S.WINDOW_W,box_h),2)
            words=dialogue_text.split(); lines=[]; cur=""
            for w in words:
                test=(cur+" "+w).strip()
                if font.size(test)[0]>S.WINDOW_W-20: lines.append(cur); cur=w
                else: cur=test
            if cur: lines.append(cur)
            for i,line in enumerate(lines[:3]): screen.blit(font.render(line,True,(255,255,255)), (10,S.WINDOW_H-box_h+10+i*22))
        pg.display.flip()
    pg.quit(); sys.exit()
if __name__=="__main__": main()
