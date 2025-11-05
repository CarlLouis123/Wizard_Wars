"""Entry point for the neon-drenched first-person Wizard Wars experience."""

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

NEON_WALL_COLORS: Sequence[tuple[int, int, int]] = (
    (234, 77, 255),
    (76, 217, 255),
    (255, 107, 153),
    (146, 255, 144),
    (255, 215, 99),
    (171, 117, 255),
    (92, 255, 212),
)
SKY_TOP = (11, 2, 28)
SKY_BOTTOM = (45, 15, 92)
FLOOR_TOP = (15, 3, 38)
FLOOR_BOTTOM = (8, 39, 62)

MAX_VIEW_DISTANCE = 2200.0
RAY_STEP = 2.0


def _load_npc_catalog(path: Path) -> tuple[dict[str, dict], list[dict]]:
    with open(path, "r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    archetypes = {entry["id"]: entry for entry in data.get("npc_archetypes", []) if entry.get("id")}
    rings = [ring for ring in data.get("spawn_rings", []) if ring]
    return archetypes, rings


NPC_ARCHETYPES, NPC_SPAWN_RINGS = _load_npc_catalog(TPL_DIR / "npc_wizard.yaml")


def _world_to_tile(x: float, y: float) -> tuple[int, int]:
    return int(x // S.TILE_SIZE), int(y // S.TILE_SIZE)


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


def _find_spawn(tilemap: TileMap) -> tuple[float, float]:
    centre_tx = tilemap.w // 2
    centre_ty = tilemap.h // 2
    if tilemap.walkable(centre_tx, centre_ty):
        return (
            centre_tx * S.TILE_SIZE + S.TILE_SIZE // 2,
            centre_ty * S.TILE_SIZE + S.TILE_SIZE // 2,
        )

    max_radius = max(tilemap.w, tilemap.h)
    for radius in range(1, max_radius):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                tx = centre_tx + dx
                ty = centre_ty + dy
                if not (0 <= tx < tilemap.w and 0 <= ty < tilemap.h):
                    continue
                if tilemap.walkable(tx, ty):
                    return (
                        tx * S.TILE_SIZE + S.TILE_SIZE // 2,
                        ty * S.TILE_SIZE + S.TILE_SIZE // 2,
                    )

    return (
        centre_tx * S.TILE_SIZE + S.TILE_SIZE // 2,
        centre_ty * S.TILE_SIZE + S.TILE_SIZE // 2,
    )


def _angle_delta(angle: float, reference: float) -> float:
    delta = angle - reference
    return math.atan2(math.sin(delta), math.cos(delta))


def _nearest_visible_npc(
    player: Player,
    npcs: Iterable[NPC],
    max_distance: float = 196.0,
    angle_window: float | None = None,
) -> NPC | None:
    if angle_window is None:
        angle_window = player.fov / 3.0

    talking: NPC | None = None
    best = max_distance
    for npc in npcs:
        dist = math.hypot(npc.x - player.x, npc.y - player.y)
        if dist >= best:
            continue
        delta = _angle_delta(math.atan2(npc.y - player.y, npc.x - player.x), player.angle)
        if abs(delta) > angle_window:
            continue
        best = dist
        talking = npc
    return talking


def _build_wall_palette(tilemap: TileMap) -> dict[str, tuple[int, int, int]]:
    palette: dict[str, tuple[int, int, int]] = {}
    neon = list(NEON_WALL_COLORS)
    if not neon:
        neon = [(200, 150, 255)]
    index = 0
    for tile_id, tile in tilemap.ground_tiles.items():
        if tile.walkable:
            continue
        palette[tile_id] = neon[index % len(neon)]
        index += 1
    palette.setdefault("__void__", (190, 130, 255))
    return palette


def _is_walkable(tilemap: TileMap, x: float, y: float, padding: float) -> bool:
    offsets = (
        (0.0, 0.0),
        (padding, 0.0),
        (-padding, 0.0),
        (0.0, padding),
        (0.0, -padding),
    )
    for ox, oy in offsets:
        tx, ty = _world_to_tile(x + ox, y + oy)
        if not tilemap.walkable(tx, ty):
            return False
    return True


def _move_player(tilemap: TileMap, player: Player, dx: float, dy: float) -> None:
    padding = S.TILE_SIZE * 0.25
    if dx:
        nx = player.x + dx
        if _is_walkable(tilemap, nx, player.y, padding):
            player.x = nx
    if dy:
        ny = player.y + dy
        if _is_walkable(tilemap, player.x, ny, padding):
            player.y = ny


def _lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_gradient(screen: pg.Surface) -> None:
    width, height = screen.get_size()
    horizon = height // 2
    for y in range(horizon):
        t = y / max(horizon - 1, 1)
        color = _lerp_color(SKY_TOP, SKY_BOTTOM, t)
        pg.draw.line(screen, color, (0, y), (width, y))
    for y in range(horizon, height):
        t = (y - horizon) / max(height - horizon - 1, 1)
        color = _lerp_color(FLOOR_TOP, FLOOR_BOTTOM, t)
        pg.draw.line(screen, color, (0, y), (width, y))


def _cast_ray(tilemap: TileMap, origin_x: float, origin_y: float, angle: float) -> tuple[float, str]:
    sin_a = math.sin(angle)
    cos_a = math.cos(angle)
    distance = 0.0
    while distance < MAX_VIEW_DISTANCE:
        distance += RAY_STEP
        sample_x = origin_x + cos_a * distance
        sample_y = origin_y + sin_a * distance
        tx, ty = _world_to_tile(sample_x, sample_y)
        if not (0 <= tx < tilemap.w and 0 <= ty < tilemap.h):
            return MAX_VIEW_DISTANCE, "__void__"
        if not tilemap.walkable(tx, ty):
            tile_id = tilemap.base[ty][tx]
            return distance, tile_id or "__void__"
    return MAX_VIEW_DISTANCE, "__void__"


def _render_scene(
    screen: pg.Surface,
    tilemap: TileMap,
    player: Player,
    wall_palette: dict[str, tuple[int, int, int]],
) -> list[float]:
    width, height = screen.get_size()
    proj_dist = (width / 2) / math.tan(player.fov / 2)
    half_height = height // 2
    depth_buffer: list[float] = [MAX_VIEW_DISTANCE] * width

    _draw_gradient(screen)

    ticks = pg.time.get_ticks() / 600.0
    for column in range(width):
        offset = column / width - 0.5
        ray_angle = player.angle + offset * player.fov
        raw_distance, tile_id = _cast_ray(tilemap, player.x, player.y, ray_angle)
        corrected = raw_distance * math.cos(ray_angle - player.angle)
        if corrected <= 0.001:
            corrected = 0.001
        depth_buffer[column] = corrected

        wall_height = int((S.TILE_SIZE * proj_dist) / corrected)
        top = max(0, half_height - wall_height // 2)
        bottom = min(height, half_height + wall_height // 2)

        base_color = wall_palette.get(tile_id, wall_palette["__void__"])
        distance_fade = max(0.2, 1.0 - (corrected / MAX_VIEW_DISTANCE))
        pulse = 0.55 + 0.45 * math.sin(ticks + offset * math.tau)
        intensity = min(1.0, distance_fade * 1.35 * pulse)
        shade = tuple(min(255, int(component * intensity)) for component in base_color)
        pg.draw.line(screen, shade, (column, top), (column, bottom))

    return depth_buffer


def _render_sprites(
    screen: pg.Surface,
    player: Player,
    npcs: Iterable[NPC],
    depth_buffer: Sequence[float],
    highlight: NPC | None,
) -> None:
    width, height = screen.get_size()
    proj_dist = (width / 2) / math.tan(player.fov / 2)
    centre_x = width / 2
    bob = math.sin(pg.time.get_ticks() / 420.0) * player.step_height * 0.15

    sorted_npcs = sorted(npcs, key=lambda npc: math.hypot(npc.x - player.x, npc.y - player.y), reverse=True)
    for npc in sorted_npcs:
        dx = npc.x - player.x
        dy = npc.y - player.y
        distance = math.hypot(dx, dy)
        if distance < 1.0:
            continue

        angle_to = _angle_delta(math.atan2(dy, dx), player.angle)
        if abs(angle_to) > player.fov / 2 + 0.35:
            continue

        size = int((S.TILE_SIZE * proj_dist) / max(distance, 1.0))
        if size <= 4:
            continue

        screen_x = int(centre_x + math.tan(angle_to) * proj_dist - size / 2)
        if screen_x + size <= 0 or screen_x >= width:
            continue

        depth_sample_x = min(width - 1, max(0, screen_x + size // 2))
        if distance > depth_buffer[depth_sample_x] * 1.1:
            continue

        sprite = pg.transform.smoothscale(npc.sprite, (size, size))
        sprite = sprite.convert_alpha()
        if highlight is npc:
            glow = pg.Surface((size, size), pg.SRCALPHA)
            pg.draw.circle(glow, (0, 255, 255, 140), (size // 2, size // 2), size // 2)
            sprite.blit(glow, (0, 0), special_flags=pg.BLEND_ADD)

        screen_y = height // 2 - size // 2 - int(bob)
        screen.blit(sprite, (screen_x, screen_y))


def _wrap_text(font: pg.font.Font, text: str, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        test = current + " " + word
        if font.size(test)[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = test
    lines.append(current)
    return lines


def _draw_dialogue(screen: pg.Surface, font: pg.font.Font, text: str) -> None:
    if not text:
        return

    box_h = 128
    overlay = pg.Surface((S.WINDOW_W, box_h), pg.SRCALPHA)
    overlay.fill((12, 0, 36, 210))
    pg.draw.rect(overlay, (0, 255, 255, 180), overlay.get_rect(), 2)

    lines = _wrap_text(font, text, S.WINDOW_W - 48)
    glow_font = font
    for i, line in enumerate(lines[:5]):
        text_surface = glow_font.render(line, True, (222, 238, 255))
        overlay.blit(text_surface, (24, 20 + i * 22))

    screen.blit(overlay, (0, S.WINDOW_H - box_h))


def _draw_ui(
    screen: pg.Surface,
    font: pg.font.Font,
    dlg,
    clock: pg.time.Clock,
    player: Player,
    biome,
    highlight: NPC | None,
) -> None:
    hud_height = 84
    hud = pg.Surface((S.WINDOW_W, hud_height), pg.SRCALPHA)
    hud.fill((10, 0, 30, 180))
    pg.draw.rect(hud, (255, 0, 200, 160), hud.get_rect(), 2)

    spells = ", ".join(spell.id for spell in player.spells) if player.spells else "None"
    biome_line = f"Biome: {biome.label}" if biome else "Biome: Unknown"
    focused = f"Focus: {'Gemini' if dlg.use_gemini else 'Archive'}"
    target_line = (
        f"Link ready: {getattr(highlight, 'archetype_id', 'unknown').title()}"
        if highlight
        else "Link ready: --"
    )
    info_lines: Sequence[str] = (
        f"HP {player.health}/{player.max_health} | Mana {player.mana}/{player.max_mana}",
        f"Spells: {spells}",
        biome_line,
        target_line,
        focused,
        f"FPS: {clock.get_fps():.0f} | WASD move | Arrows turn | E commune | G toggle focus",
    )
    for i, line in enumerate(info_lines):
        text_surface = font.render(line, True, (214, 220, 255))
        hud.blit(text_surface, (16, 12 + i * 14))

    screen.blit(hud, (0, 0))

    centre = (S.WINDOW_W // 2, S.WINDOW_H // 2)
    pg.draw.circle(screen, (255, 0, 200), centre, 4, 2)
    pg.draw.circle(screen, (0, 255, 255), centre, 10, 1)


def main() -> None:
    pg.init()
    pg.display.set_caption("WizardWars: Neon Sigils")
    screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
    clock = pg.time.Clock()
    font = pg.font.SysFont("Share Tech Mono", 20)

    random.seed(S.SEED)
    tilemap = TileMap(S.WORLD_W, S.WORLD_H, S.TILE_SIZE, S.SEED, str(TPL_DIR))
    spawn_x, spawn_y = _find_spawn(tilemap)
    player = Player(
        spawn_x,
        spawn_y,
        S.TILE_SIZE,
        str(TPL_DIR / "player_wizard.json"),
    )
    player.angle = math.tau / 4
    player.load_spells(TPL_DIR)
    npcs = _spawn_npcs(tilemap)
    wall_palette = _build_wall_palette(tilemap)

    from engine.dialogue import DialogueEngine

    dlg = DialogueEngine(use_gemini=S.USE_GEMINI, model_name=S.MODEL_NAME)
    dlg.prewarm(npc.dialogue_prompt for npc in npcs)
    dialogue_text = ""
    active_npc: NPC | None = None

    running = True
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
                    target = _nearest_visible_npc(player, npcs)
                    if target:
                        active_npc = target
                        dialogue_text = dlg.npc_line(target.dialogue_prompt, target.fallback_lines)

        keys = pg.key.get_pressed()
        if keys[pg.K_LEFT]:
            player.angle -= player.turn_speed * dt
        if keys[pg.K_RIGHT]:
            player.angle += player.turn_speed * dt
        player.angle %= math.tau

        forward = 0.0
        if keys[pg.K_w] or keys[pg.K_UP]:
            forward += 1.0
        if keys[pg.K_s] or keys[pg.K_DOWN]:
            forward -= 1.0

        strafe = 0.0
        if keys[pg.K_d]:
            strafe += 1.0
        if keys[pg.K_a]:
            strafe -= 1.0

        direction_length = math.hypot(forward, strafe)
        if direction_length > 0.0:
            forward /= direction_length
            strafe /= direction_length

        boost = 1.0 + (0.5 if keys[pg.K_LSHIFT] or keys[pg.K_RSHIFT] else 0.0)
        speed = player.move_speed * dt * boost
        fx, fy = player.forward_vector()
        rx, ry = player.right_vector()
        dx = (fx * forward + rx * strafe) * speed
        dy = (fy * forward + ry * strafe) * speed
        _move_player(tilemap, player, dx, dy)

        highlight = _nearest_visible_npc(player, npcs)
        if active_npc:
            if math.hypot(active_npc.x - player.x, active_npc.y - player.y) > 220:
                active_npc = None
                dialogue_text = ""
            else:
                highlight = active_npc

        depth_buffer = _render_scene(screen, tilemap, player, wall_palette)
        _render_sprites(screen, player, npcs, depth_buffer, highlight)

        biome = tilemap.biome_at_world(player.x, player.y)
        _draw_ui(screen, font, dlg, clock, player, biome, highlight)
        _draw_dialogue(screen, font, dialogue_text)

        pg.display.flip()

    pg.quit()
    sys.exit()


if __name__ == "__main__":
    main()
