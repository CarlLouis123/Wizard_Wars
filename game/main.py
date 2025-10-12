"""Entry point for the template-driven PokeLike demo."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Iterable, Sequence

import pygame as pg

from engine.entities import NPC, Player
from engine.tilemap import TileMap
import settings as S


HERE = Path(__file__).resolve().parent
TPL_DIR = HERE / "content" / "templates"


def _world_to_tile(x: float, y: float) -> tuple[int, int]:
    return int(x // S.TILE_SIZE), int(y // S.TILE_SIZE)


def _collides(tilemap: TileMap, nx: float, ny: float, current_y: float, current_x: float) -> tuple[bool, bool]:
    tx, ty = _world_to_tile(nx, current_y)
    col_x = not tilemap.walkable(tx, ty)
    tx, ty = _world_to_tile(current_x, ny)
    col_y = not tilemap.walkable(tx, ty)
    return col_x, col_y


def _spawn_npcs(tilemap: TileMap, count: int, tpl_path: Path) -> list[NPC]:
    npcs: list[NPC] = []
    for _ in range(count):
        while True:
            tx = random.randint(0, tilemap.w - 1)
            ty = random.randint(0, tilemap.h - 1)
            if tilemap.walkable(tx, ty):
                nx = tx * S.TILE_SIZE + S.TILE_SIZE // 2
                ny = ty * S.TILE_SIZE + S.TILE_SIZE // 2
                npcs.append(NPC(nx, ny, S.TILE_SIZE, str(tpl_path)))
                break
    return npcs


def _nearest_npc(player: Player, npcs: Iterable[NPC], max_distance: float = 56.0) -> NPC | None:
    talking: NPC | None = None
    best = max_distance
    for npc in npcs:
        dist = math.hypot(npc.x - player.x, npc.y - player.y)
        if dist < best:
            best = dist
            talking = npc
    return talking


def _draw_ui(screen: pg.Surface, font: pg.font.Font, dlg, clock: pg.time.Clock) -> None:
    ui_lines: Sequence[str] = (
        f"FPS: {clock.get_fps():.0f}",
        f"G (Gemini): {'ON' if dlg.use_gemini else 'OFF'}",
        "Move: WASD/Arrows | Talk: E | Toggle: G | Esc: Quit",
    )
    for i, line in enumerate(ui_lines):
        screen.blit(font.render(line, True, (255, 255, 255)), (8, 8 + i * 18))


def _draw_dialogue(screen: pg.Surface, font: pg.font.Font, text: str) -> None:
    if not text:
        return

    box_h = 88
    pg.draw.rect(screen, (0, 0, 0), (0, S.WINDOW_H - box_h, S.WINDOW_W, box_h))
    pg.draw.rect(screen, (255, 255, 255), (0, S.WINDOW_H - box_h, S.WINDOW_W, box_h), 2)

    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] > S.WINDOW_W - 20:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    for i, line in enumerate(lines[:3]):
        screen.blit(font.render(line, True, (255, 255, 255)), (10, S.WINDOW_H - box_h + 10 + i * 22))


def main() -> None:
    pg.init()
    pg.display.set_caption("PokeLike - Template Driven")
    screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
    clock = pg.time.Clock()
    font = pg.font.SysFont(None, 20)

    random.seed(S.SEED)
    tilemap = TileMap(S.WORLD_W, S.WORLD_H, S.TILE_SIZE, S.SEED, str(TPL_DIR))
    player = Player(S.WINDOW_W // 2, S.WINDOW_H // 2, S.TILE_SIZE, str(TPL_DIR / "player_chibi.json"))
    npcs = _spawn_npcs(tilemap, 8, TPL_DIR / "npc_chibi.json")

    from engine.dialogue import DialogueEngine

    dlg = DialogueEngine(use_gemini=S.USE_GEMINI, model_name=S.MODEL_NAME)
    dialogue_text = ""

    running = True
    cam_x = player.x - S.WINDOW_W / 2
    cam_y = player.y - S.WINDOW_H / 2

    while running:
        dt = clock.tick(S.FPS) / 1000.0

        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    running = False
                elif event.key == pg.K_g:
                    dlg.use_gemini = not dlg.use_gemini
                elif event.key == pg.K_e:
                    npc = _nearest_npc(player, npcs)
                    if npc:
                        dialogue_text = dlg.npc_line(npc.dialogue_prompt)

        keys = pg.key.get_pressed()
        dx = dy = 0.0
        speed = S.PLAYER_SPEED
        if keys[pg.K_LEFT] or keys[pg.K_a]:
            dx -= speed
        if keys[pg.K_RIGHT] or keys[pg.K_d]:
            dx += speed
        if keys[pg.K_UP] or keys[pg.K_w]:
            dy -= speed
        if keys[pg.K_DOWN] or keys[pg.K_s]:
            dy += speed

        nx = player.x + dx * dt
        ny = player.y + dy * dt
        col_x, col_y = _collides(tilemap, nx, ny, player.y, player.x)
        if not col_x:
            player.x = nx
        if not col_y:
            player.y = ny

        cam_x = player.x - S.WINDOW_W / 2
        cam_y = player.y - S.WINDOW_H / 2

        screen.fill((0, 0, 0))
        ts = S.TILE_SIZE
        stx = max(0, int(cam_x // ts) - 2)
        sty = max(0, int(cam_y // ts) - 2)
        etx = min(tilemap.w, int((cam_x + S.WINDOW_W) // ts) + 3)
        ety = min(tilemap.h, int((cam_y + S.WINDOW_H) // ts) + 3)

        for ty in range(sty, ety):
            for tx in range(stx, etx):
                tile_id = tilemap.base[ty][tx]
                surf = tilemap.get_tile_surface(tile_id, (tx * 73856093) ^ (ty * 19349663))
                screen.blit(surf, (tx * ts - cam_x, ty * ts - cam_y))

        for ty in range(sty, ety):
            for tx in range(stx, etx):
                deco_id = tilemap.deco[ty][tx]
                if deco_id:
                    surf = tilemap.get_deco_surface(deco_id, (tx * 83492791) ^ (ty * 29765729))
                    if surf:
                        rect = surf.get_rect()
                        rect.center = (tx * ts - cam_x + ts // 2, ty * ts - cam_y + ts // 2)
                        screen.blit(surf, rect)

        for npc in npcs:
            rect = npc.sprite.get_rect(center=(npc.x - cam_x, npc.y - cam_y))
            screen.blit(npc.sprite, rect)

        rect = player.sprite.get_rect(center=(player.x - cam_x, player.y - cam_y))
        screen.blit(player.sprite, rect)

        _draw_ui(screen, font, dlg, clock)
        _draw_dialogue(screen, font, dialogue_text)

        pg.display.flip()

    pg.quit()
    sys.exit()


if __name__ == "__main__":
    main()
