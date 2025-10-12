"""Entry point for the template-driven Wizard Wars sandbox."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Iterable, Sequence

import pygame as pg
import yaml

from engine.entities import NPC, Player
from engine.tilemap import TileMap
import settings as S


HERE = Path(__file__).resolve().parent
TPL_DIR = HERE / "content" / "templates"


def _load_npc_catalog(path: Path) -> tuple[dict[str, dict], list[dict]]:
    with open(path, "r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    archetypes = {entry["id"]: entry for entry in data.get("npc_archetypes", []) if entry.get("id")}
    rings = [ring for ring in data.get("spawn_rings", []) if ring]
    return archetypes, rings


NPC_ARCHETYPES, NPC_SPAWN_RINGS = _load_npc_catalog(TPL_DIR / "npc_wizard.yaml")


def _world_to_tile(x: float, y: float) -> tuple[int, int]:
    return int(x // S.TILE_SIZE), int(y // S.TILE_SIZE)


def _collides(tilemap: TileMap, nx: float, ny: float, current_y: float, current_x: float) -> tuple[bool, bool]:
    tx, ty = _world_to_tile(nx, current_y)
    col_x = not tilemap.walkable(tx, ty)
    tx, ty = _world_to_tile(current_x, ny)
    col_y = not tilemap.walkable(tx, ty)
    return col_x, col_y


def _spawn_npcs(tilemap: TileMap) -> list[NPC]:
    if not NPC_ARCHETYPES:
        return []

    centre_x = tilemap.w / 2.0
    centre_y = tilemap.h / 2.0
    npcs: list[NPC] = []
    rng = random.Random(tilemap.seed ^ 0xC1A0F00D)

    for ring in NPC_SPAWN_RINGS:
        radius = float(ring.get("radius_tiles", 6))
        count = int(ring.get("count", 0))
        archetypes = [NPC_ARCHETYPES[a] for a in ring.get("archetypes", []) if a in NPC_ARCHETYPES]
        if not archetypes or count <= 0:
            continue

        for i in range(count):
            spec = archetypes[i % len(archetypes)]
            angle = rng.random() * math.tau
            for _ in range(32):
                tx = int(centre_x + math.cos(angle) * radius + rng.uniform(-1, 1))
                ty = int(centre_y + math.sin(angle) * radius + rng.uniform(-1, 1))
                angle += math.tau / (count + 1)
                if not tilemap.walkable(tx, ty):
                    continue
                wx = tx * S.TILE_SIZE + S.TILE_SIZE // 2
                wy = ty * S.TILE_SIZE + S.TILE_SIZE // 2
                tpl = TPL_DIR / spec.get("sprite_template", "wizard_moon.json")
                npc = NPC(
                    wx,
                    wy,
                    str(tpl),
                    prompt=str(spec.get("prompt", "Offer a wizardly insight.")),
                    personality=str(spec.get("personality", "neutral")),
                    school=str(spec.get("school", "arcane")),
                    dialogue=spec.get("dialogue", {}),
                )
                npc.archetype_id = spec.get("id", "unknown")
                npc.spawn_radius = radius
                biome = tilemap.biome_at(tx, ty)
                npc.spawn_biome = biome.id
                npcs.append(npc)
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


def _draw_ui(
    screen: pg.Surface,
    font: pg.font.Font,
    dlg,
    clock: pg.time.Clock,
    player: Player,
    biome,
) -> None:
    title_color = (228, 220, 255)
    info_color = (180, 170, 210)
    title = font.render("Wizard Wars", True, title_color)
    screen.blit(title, (8, 8))

    spells = ", ".join(spell.id for spell in player.spells) if player.spells else "None"
    status = f"HP {player.health}/{player.max_health} | Mana {player.mana}/{player.max_mana}"
    biome_line = f"Biome: {biome.label}" if biome else "Biome: Unknown"
    features = biome.description if biome else ""
    ui_lines: Sequence[str] = (
        status,
        f"Spells: {spells}",
        biome_line,
        features,
        f"Focus: {'Gemini' if dlg.use_gemini else 'Archive'}",
        "WASD/Arrows move | E commune | G toggle guidance",
        f"Calm FPS: {clock.get_fps():.0f}",
    )
    for i, line in enumerate(ui_lines):
        screen.blit(font.render(line, True, info_color), (8, 30 + i * 18))


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
    pg.display.set_caption("WizardWars")
    screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
    clock = pg.time.Clock()
    font = pg.font.SysFont(None, 20)

    random.seed(S.SEED)
    tilemap = TileMap(S.WORLD_W, S.WORLD_H, S.TILE_SIZE, S.SEED, str(TPL_DIR))
    player = Player(
        S.WINDOW_W // 2,
        S.WINDOW_H // 2,
        S.TILE_SIZE,
        str(TPL_DIR / "player_wizard.json"),
    )
    player.load_spells(TPL_DIR)
    npcs = _spawn_npcs(tilemap)

    from engine.dialogue import DialogueEngine

    dlg = DialogueEngine(use_gemini=S.USE_GEMINI, model_name=S.MODEL_NAME)
    dlg.prewarm(npc.dialogue_prompt for npc in npcs)
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
                    if dlg.use_gemini:
                        dlg.prewarm(npc.dialogue_prompt for npc in npcs)
                elif event.key == pg.K_e:
                    npc = _nearest_npc(player, npcs)
                    if npc:
                        dialogue_text = dlg.npc_line(npc.dialogue_prompt, npc.fallback_lines)

        keys = pg.key.get_pressed()
        dx = dy = 0.0
        speed = player.move_speed
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
                drawable = tilemap.get_deco_drawable(deco_id, (tx * 83492791) ^ (ty * 29765729))
                if drawable:
                    surf, offset = drawable
                    rect = surf.get_rect()
                    rect.center = (tx * ts - cam_x + ts // 2, ty * ts - cam_y + ts // 2)
                    rect.move_ip(offset)
                    screen.blit(surf, rect)

        for npc in npcs:
            rect = npc.sprite.get_rect(center=(npc.x - cam_x, npc.y - cam_y))
            screen.blit(npc.sprite, rect)

        rect = player.sprite.get_rect(center=(player.x - cam_x, player.y - cam_y))
        screen.blit(player.sprite, rect)

        biome = tilemap.biome_at_world(player.x, player.y)
        _draw_ui(screen, font, dlg, clock, player, biome)
        _draw_dialogue(screen, font, dialogue_text)

        pg.display.flip()

    pg.quit()
    sys.exit()


if __name__ == "__main__":
    main()
