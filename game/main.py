"""Entry point for the neon-drenched first-person Wizard Wars experience."""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
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


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


@dataclass
class Star:
    x: float
    y: float
    depth: float
    size: int
    speed: float
    phase: float
    color: tuple[int, int, int]


class VisualFX:
    """Collection of ambient and post-processing effects for the neon arena."""

    def __init__(self, width: int, height: int, seed: int = 0xFADF00D) -> None:
        self.width = width
        self.height = height
        self.horizon = height // 2
        self.timer = 0.0
        self._rng = random.Random(seed)
        self.stars = self._build_starfield(220)
        self.scanlines = self._build_scanlines()
        self.vignette = self._build_vignette()
        self.grain_surface = pg.Surface((width, height), pg.SRCALPHA).convert_alpha()
        self._grain_points: list[tuple[int, int, int]] = []
        self._grain_timer = 0.0
        self.motes = self._build_motes(32)

    def update(self, dt: float) -> None:
        self.timer += dt
        self._grain_timer += dt
        if self._grain_timer >= 0.05:
            self._grain_timer = 0.0
            self._grain_points = [
                (
                    self._rng.randrange(self.width),
                    self._rng.randrange(self.height),
                    self._rng.randint(14, 42),
                )
                for _ in range(96)
            ]

    def _build_starfield(self, count: int) -> list[Star]:
        palette = [
            (255, 228, 128),
            (122, 255, 238),
            (255, 120, 228),
            (168, 210, 255),
        ]
        stars: list[Star] = []
        for _ in range(count):
            depth = self._rng.uniform(0.2, 1.0)
            x = self._rng.uniform(0, self.width)
            y = self._rng.uniform(0, max(8, self.horizon - 16))
            size = 1 if depth > 0.6 else 2
            speed = self._rng.uniform(0.5, 1.4)
            phase = self._rng.uniform(0, math.tau)
            color = palette[self._rng.randrange(len(palette))]
            stars.append(Star(x, y, depth, size, speed, phase, color))
        return stars

    def _build_scanlines(self) -> pg.Surface:
        surface = pg.Surface((self.width, self.height), pg.SRCALPHA)
        for y in range(0, self.height, 2):
            alpha = 26 + (y % 6)
            pg.draw.line(surface, (8, 0, 24, alpha), (0, y), (self.width, y))
        return surface.convert_alpha()

    def _build_vignette(self) -> pg.Surface:
        surface = pg.Surface((self.width, self.height), pg.SRCALPHA)
        centre = (self.width // 2, self.height // 2)
        max_radius = int(math.hypot(self.width, self.height) // 2)
        steps = max(16, max_radius // 12)
        for i in range(steps, 0, -1):
            radius = int(max_radius * (i / steps))
            alpha = int(220 * (1 - (i / steps)) ** 1.6)
            color = (6, 0, 26, alpha)
            pg.draw.circle(surface, color, centre, radius)
        return surface.convert_alpha()

    def _build_motes(self, count: int) -> list[dict[str, float]]:
        motes: list[dict[str, float]] = []
        for _ in range(count):
            motes.append(
                {
                    "angle": self._rng.uniform(0, math.tau),
                    "radius": self._rng.uniform(60, min(self.width, self.height) // 2),
                    "speed": self._rng.uniform(0.4, 1.0),
                    "height": self._rng.uniform(0.35, 0.95),
                }
            )
        return motes

    def draw_environment(self, surface: pg.Surface) -> None:
        width = self.width
        height = self.height
        horizon = self.horizon
        t = self.timer

        sky_mix = _clamp(0.5 + 0.5 * math.sin(t * 0.15))
        sky_top = _lerp_color(SKY_TOP, (24, 6, 72), sky_mix)
        sky_bottom = _lerp_color(SKY_BOTTOM, (188, 50, 255), _clamp(0.45 + 0.45 * math.cos(t * 0.21)))
        floor_mix = _clamp(0.5 + 0.5 * math.cos(t * 0.25 + 1.4))
        floor_top = _lerp_color(FLOOR_TOP, (32, 0, 54), floor_mix)
        floor_bottom = _lerp_color(FLOOR_BOTTOM, (12, 64, 96), _clamp(0.55 + 0.45 * math.sin(t * 0.32)))

        for y in range(horizon):
            ty = y / max(horizon - 1, 1)
            color = _lerp_color(sky_top, sky_bottom, ty)
            pg.draw.line(surface, color, (0, y), (width, y))
        for y in range(horizon, height):
            ty = (y - horizon) / max(height - horizon - 1, 1)
            color = _lerp_color(floor_top, floor_bottom, ty)
            pg.draw.line(surface, color, (0, y), (width, y))

        self._draw_aurora(surface)
        self._draw_starfield(surface)
        self.draw_floor_grid(surface)

    def _draw_starfield(self, surface: pg.Surface) -> None:
        width = self.width
        horizon = self.horizon
        t = self.timer
        for star in self.stars:
            wave = math.sin(t * star.speed + star.phase)
            parallax = 1.0 - star.depth * 0.5
            x = (star.x + wave * 18.0 * (1.0 - star.depth)) % width
            y = star.y + math.cos(t * 0.35 + star.phase) * 6.0 * (1.0 - star.depth)
            if y < 0:
                y += horizon
            brightness = 0.6 + 0.4 * math.sin(t * star.speed * 1.2 + star.phase * 1.5)
            color = tuple(min(255, int(component * brightness)) for component in star.color)
            pg.draw.circle(surface, color, (int(x), int(y)), star.size)

    def _draw_aurora(self, surface: pg.Surface) -> None:
        width = self.width
        horizon = self.horizon
        t = self.timer
        bands = [
            ((96, 255, 255), 0.32, 26, 0.8),
            ((255, 120, 240), 0.38, 18, 1.05),
            ((160, 255, 190), 0.44, 14, 1.25),
        ]
        for color, base_ratio, amplitude, speed in bands:
            overlay = pg.Surface((width, horizon), pg.SRCALPHA)
            points: list[tuple[float, float]] = []
            for x in range(-40, width + 40, 24):
                wave = math.sin(t * 0.7 * speed + x * 0.016 + speed)
                y = base_ratio * horizon + wave * amplitude
                points.append((x, y))
            if len(points) >= 3:
                pg.draw.aalines(overlay, color, False, points, 2)
            overlay.set_alpha(70)
            surface.blit(overlay, (0, 0), special_flags=pg.BLEND_ADD)

    def draw_floor_grid(self, surface: pg.Surface) -> None:
        overlay = pg.Surface((self.width, self.height), pg.SRCALPHA)
        horizon = self.horizon
        depth = self.height - horizon
        t = self.timer
        lines = 22
        for i in range(1, lines + 1):
            ratio = i / lines
            y = horizon + int((ratio**1.8) * depth)
            energy = _clamp(0.4 + 0.6 * math.sin(t * 2.6 + ratio * 18.0))
            color = (
                int(60 + 120 * energy),
                int(120 + 100 * energy),
                255,
                80,
            )
            pg.draw.line(overlay, color, (0, y), (self.width, y), 1)

        columns = 12
        for col in range(-columns, columns + 1):
            offset = col / columns
            base_x = self.width / 2 + offset * self.width * 0.55
            top_x = self.width / 2 + offset * self.width * 0.15
            color = (40, 200, 255, 60)
            pg.draw.line(
                overlay,
                color,
                (int(base_x), self.height),
                (int(top_x), horizon + 12),
                1,
            )

        sweep_y = horizon + int(((math.sin(t * 0.85) + 1.0) * 0.5) * depth)
        pg.draw.rect(
            overlay,
            (40, 140, 255, 70),
            pg.Rect(0, sweep_y - 18, self.width, 36),
        )
        surface.blit(overlay, (0, 0), special_flags=pg.BLEND_ADD)

    def draw_astral_motes(self, surface: pg.Surface, focus: tuple[int, int] | None) -> None:
        overlay = pg.Surface((self.width, self.height), pg.SRCALPHA)
        if focus:
            centre_x, centre_y = focus
        else:
            centre_x, centre_y = self.width / 2, self.height / 2 + self.height * 0.1

        for mote in self.motes:
            angle = mote["angle"] + self.timer * mote["speed"]
            radius = mote["radius"] * (1.0 + 0.08 * math.sin(self.timer * 1.4 + mote["angle"]))
            x = centre_x + math.cos(angle) * radius
            y = centre_y + math.sin(angle) * radius * 0.35
            y += (self.height - self.horizon) * (mote["height"] - 0.5) * 0.6
            brightness = 0.45 + 0.55 * math.sin(self.timer * 2.0 + mote["angle"] * 2.3)
            color = (
                int(120 + 100 * brightness),
                int(200 + 40 * brightness),
                255,
                int(120 + 80 * brightness),
            )
            pg.draw.circle(overlay, color, (int(x), int(y)), 3)

        surface.blit(overlay, (0, 0), special_flags=pg.BLEND_ADD)

    def apply_scene_glow(self, surface: pg.Surface) -> None:
        w = max(1, self.width // 2)
        h = max(1, self.height // 2)
        glow = pg.transform.smoothscale(surface, (w, h))
        glow = pg.transform.smoothscale(glow, (self.width, self.height))
        glow.set_alpha(120)
        surface.blit(glow, (0, 0), special_flags=pg.BLEND_ADD)

    def draw_screen_overlay(self, screen: pg.Surface) -> None:
        self.grain_surface.fill((0, 0, 0, 0))
        for x, y, alpha in self._grain_points:
            self.grain_surface.set_at((x, y), (255, 255, 255, alpha))
        screen.blit(self.scanlines, (0, 0))
        screen.blit(self.vignette, (0, 0))
        screen.blit(self.grain_surface, (0, 0), special_flags=pg.BLEND_ADD)

    def draw_target_brackets(self, surface: pg.Surface, rect: pg.Rect) -> None:
        overlay = pg.Surface(rect.inflate(32, 32).size, pg.SRCALPHA)
        overlay_rect = overlay.get_rect()
        pulse = 6 + 4 * math.sin(self.timer * 4.2)
        color = (0, 255, 255, 190)
        span = 24
        thickness = 2
        corners = [
            ((overlay_rect.left + pulse, overlay_rect.top + pulse), (overlay_rect.left + pulse + span, overlay_rect.top + pulse)),
            ((overlay_rect.right - pulse, overlay_rect.top + pulse), (overlay_rect.right - pulse, overlay_rect.top + pulse + span)),
            ((overlay_rect.right - pulse, overlay_rect.bottom - pulse), (overlay_rect.right - pulse - span, overlay_rect.bottom - pulse)),
            ((overlay_rect.left + pulse, overlay_rect.bottom - pulse), (overlay_rect.left + pulse, overlay_rect.bottom - pulse - span)),
        ]
        for start, end in corners:
            pg.draw.line(overlay, color, start, end, thickness)
        overlay.set_alpha(200)
        surface.blit(overlay, rect.inflate(32, 32).topleft, special_flags=pg.BLEND_ADD)

    def draw_crosshair(self, surface: pg.Surface) -> None:
        overlay = pg.Surface((120, 120), pg.SRCALPHA)
        centre = overlay.get_rect().center
        pulse = 12 + 4 * math.sin(self.timer * 4.0)
        spin = self.timer * 2.2
        for i in range(4):
            angle = spin + i * (math.tau / 4)
            orbit = 20 + 6 * math.sin(self.timer * 3.2 + i)
            x = centre[0] + math.cos(angle) * orbit
            y = centre[1] + math.sin(angle) * orbit
            pg.draw.circle(overlay, (0, 255, 255, 180), (int(x), int(y)), 6, 2)

        cross_color = (255, 80, 220, 220)
        length = 26
        pg.draw.line(
            overlay,
            cross_color,
            (centre[0] - length, centre[1]),
            (centre[0] - pulse, centre[1]),
            2,
        )
        pg.draw.line(
            overlay,
            cross_color,
            (centre[0] + pulse, centre[1]),
            (centre[0] + length, centre[1]),
            2,
        )
        pg.draw.line(
            overlay,
            cross_color,
            (centre[0], centre[1] - length),
            (centre[0], centre[1] - pulse),
            2,
        )
        pg.draw.line(
            overlay,
            cross_color,
            (centre[0], centre[1] + pulse),
            (centre[0], centre[1] + length),
            2,
        )

        rune_radius = 34 + 6 * math.sin(self.timer * 2.8)
        for i in range(6):
            angle = spin * 1.6 + i * math.tau / 6
            x = centre[0] + math.cos(angle) * rune_radius
            y = centre[1] + math.sin(angle) * rune_radius
            pg.draw.circle(overlay, (80, 255, 255, 90), (int(x), int(y)), 3)

        surface.blit(overlay, overlay.get_rect(center=(self.width // 2, self.height // 2)))


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
    fx: VisualFX,
) -> list[float]:
    width, height = screen.get_size()
    proj_dist = (width / 2) / math.tan(player.fov / 2)
    half_height = height // 2
    depth_buffer: list[float] = [MAX_VIEW_DISTANCE] * width

    fx.draw_environment(screen)

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
        shimmer = 0.85 + 0.15 * math.sin(column * 0.12 + ticks * 3.2)
        intensity = min(1.0, distance_fade * 1.55 * pulse * shimmer)
        shade = tuple(min(255, int(component * intensity)) for component in base_color)

        pg.draw.line(screen, shade, (column, top), (column, bottom))

        if bottom < height:
            mist = tuple(min(255, int(component * 0.18)) for component in base_color)
            pg.draw.line(screen, mist, (column, bottom), (column, height))

        highlight_strength = max(0.0, 1.0 - corrected / 420.0)
        if highlight_strength > 0:
            glow_color = tuple(
                min(255, int(component * (0.25 + highlight_strength * 0.5)))
                for component in base_color
            )
            pg.draw.line(
                screen,
                glow_color,
                (column, max(0, top - 1)),
                (column, min(height - 1, top + 1)),
            )

    return depth_buffer


def _render_sprites(
    screen: pg.Surface,
    player: Player,
    npcs: Iterable[NPC],
    depth_buffer: Sequence[float],
    highlight: NPC | None,
    fx: VisualFX,
) -> pg.Rect | None:
    width, height = screen.get_size()
    proj_dist = (width / 2) / math.tan(player.fov / 2)
    centre_x = width / 2
    bob = math.sin(pg.time.get_ticks() / 420.0) * player.step_height * 0.15

    sorted_npcs = sorted(npcs, key=lambda npc: math.hypot(npc.x - player.x, npc.y - player.y), reverse=True)
    target_rect: pg.Rect | None = None
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

        if highlight is npc:
            target_rect = pg.Rect(screen_x, screen_y, size, size)
            fx.draw_target_brackets(screen, pg.Rect(screen_x, screen_y, size, size))

    return target_rect


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

    box_h = 148
    overlay = pg.Surface((S.WINDOW_W, box_h), pg.SRCALPHA)
    for y in range(box_h):
        ratio = y / max(box_h - 1, 1)
        color = _lerp_color((16, 0, 48), (48, 0, 68), ratio)
        overlay.fill((*color, 220), pg.Rect(0, y, S.WINDOW_W, 1))

    pulse = 0.5 + 0.5 * math.sin(pg.time.get_ticks() / 280.0)
    border_rgb = _lerp_color((40, 180, 255), (255, 120, 255), pulse)
    pg.draw.rect(overlay, (*border_rgb, 220), overlay.get_rect(), 2, border_radius=18)
    pg.draw.rect(overlay, (0, 0, 0, 160), overlay.get_rect(), 4, border_radius=22)

    accent = pg.Surface((S.WINDOW_W, 16), pg.SRCALPHA)
    accent.fill((0, 255, 255, 40))
    overlay.blit(accent, (0, 0))

    lines = _wrap_text(font, text, S.WINDOW_W - 96)
    bubble_rect = pg.Rect(30, 32, S.WINDOW_W - 60, min(26 * len(lines[:5]) + 20, box_h - 60))
    pg.draw.rect(overlay, (10, 30, 50, 120), bubble_rect, 0, border_radius=12)
    pg.draw.rect(overlay, (0, 255, 255, 90), bubble_rect, 2, border_radius=12)

    glow_font = font
    for i, line in enumerate(lines[:5]):
        y = 40 + i * 24
        glow = glow_font.render(line, True, (30, 160, 255))
        overlay.blit(glow, (40, y + 1))
        text_surface = glow_font.render(line, True, (236, 240, 255))
        overlay.blit(text_surface, (40, y))

    if not hasattr(_draw_dialogue, "_glyph_font"):
        _draw_dialogue._glyph_font = pg.font.SysFont("Share Tech Mono", 16)
    glyph_font: pg.font.Font = _draw_dialogue._glyph_font
    glyphs = ["<>", "//", "**", "||", "::"]
    for i, x in enumerate(range(24, S.WINDOW_W - 24, 72)):
        glyph = glyphs[i % len(glyphs)]
        wave = math.sin(pg.time.get_ticks() / 220.0 + i)
        color = _lerp_color((120, 255, 255), (255, 150, 255), (wave + 1) * 0.5)
        glyph_surface = glyph_font.render(glyph, True, color)
        overlay.blit(glyph_surface, (x, 8 + wave * 4))

    screen.blit(overlay, (0, S.WINDOW_H - box_h))


def _draw_ui(
    screen: pg.Surface,
    font: pg.font.Font,
    dlg,
    clock: pg.time.Clock,
    player: Player,
    biome,
    highlight: NPC | None,
    fx: VisualFX,
) -> None:
    hud_height = 112
    hud = pg.Surface((S.WINDOW_W, hud_height), pg.SRCALPHA)
    for y in range(hud_height):
        ratio = y / max(hud_height - 1, 1)
        color = _lerp_color((12, 0, 36), (48, 0, 66), ratio)
        hud.fill((*color, 200), pg.Rect(0, y, S.WINDOW_W, 1))

    pg.draw.rect(hud, (255, 0, 200, 160), hud.get_rect(), 2, border_radius=14)

    hp_ratio = _clamp(player.health / max(1, player.max_health))
    mana_ratio = _clamp(player.mana / max(1, player.max_mana))

    def _draw_bar(rect: pg.Rect, ratio: float, start_color: tuple[int, int, int], end_color: tuple[int, int, int]) -> None:
        pg.draw.rect(hud, (24, 0, 48, 210), rect.inflate(8, 8), border_radius=10)
        fill_width = max(0, int(rect.width * ratio))
        if fill_width <= 0:
            return
        for x in range(fill_width):
            t = x / max(fill_width - 1, 1)
            color = _lerp_color(start_color, end_color, t)
            hud.fill((*color, 230), pg.Rect(rect.x + x, rect.y, 1, rect.height))
        pg.draw.rect(hud, (255, 255, 255, 90), rect, 1, border_radius=8)

    hp_rect = pg.Rect(24, 16, S.WINDOW_W // 3, 16)
    mana_rect = pg.Rect(24, 44, S.WINDOW_W // 3, 16)
    _draw_bar(hp_rect, hp_ratio, (255, 90, 170), (140, 42, 255))
    _draw_bar(mana_rect, mana_ratio, (80, 220, 255), (140, 120, 255))

    hp_label = font.render(f"Vitality {player.health}/{player.max_health}", True, (232, 236, 255))
    mana_label = font.render(f"Mana {player.mana}/{player.max_mana}", True, (214, 230, 255))
    hud.blit(hp_label, (hp_rect.right + 12, hp_rect.y - 2))
    hud.blit(mana_label, (mana_rect.right + 12, mana_rect.y - 2))

    spells = ", ".join(spell.id for spell in player.spells) if player.spells else "None"
    biome_line = f"Biome: {biome.label}" if biome else "Biome: Unknown"
    focused = f"Focus: {'Gemini' if dlg.use_gemini else 'Archive'}"
    target_name = getattr(highlight, "archetype_id", "--").replace("_", " ").title()

    info_lines: Sequence[str] = (
        f"Spells: {spells}",
        biome_line,
        focused,
        f"FPS: {clock.get_fps():.0f} | WASD move | Arrows turn | E commune | G toggle focus",
    )
    for i, line in enumerate(info_lines):
        text_surface = font.render(line, True, (214, 220, 255))
        hud.blit(text_surface, (24, 70 + i * 14))

    if not hasattr(_draw_ui, "_title_font"):
        _draw_ui._title_font = pg.font.SysFont("Orbitron", 28, bold=True)
    title_font: pg.font.Font = _draw_ui._title_font
    title = title_font.render("Wizard Wars // Neon Astral", True, (255, 120, 255))
    hud.blit(title, (S.WINDOW_W - title.get_width() - 24, 14))

    target_panel = pg.Surface((280, 70), pg.SRCALPHA)
    target_panel.fill((12, 0, 36, 160))
    pg.draw.rect(target_panel, (0, 255, 255, 160), target_panel.get_rect(), 2, border_radius=12)
    target_title = font.render("Target Link", True, (196, 240, 255))
    target_panel.blit(target_title, (16, 10))
    if highlight:
        pulse = 0.6 + 0.4 * math.sin(pg.time.get_ticks() / 240.0)
        name_color = _lerp_color((120, 255, 255), (255, 160, 255), pulse)
        name_surface = font.render(target_name, True, name_color)
    else:
        name_surface = font.render("--", True, (160, 160, 180))
    target_panel.blit(name_surface, (16, 34))
    hud.blit(target_panel, (S.WINDOW_W - target_panel.get_width() - 24, 54))

    screen.blit(hud, (0, 0))

    fx.draw_crosshair(screen)


def main() -> None:
    pg.init()
    pg.display.set_caption("WizardWars: Neon Sigils")
    screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
    clock = pg.time.Clock()
    font = pg.font.SysFont("Share Tech Mono", 20)
    scene_surface = pg.Surface((S.WINDOW_W, S.WINDOW_H), pg.SRCALPHA).convert_alpha()
    fx = VisualFX(S.WINDOW_W, S.WINDOW_H)

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
        fx.update(dt)

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

        scene_surface.fill((0, 0, 0))
        depth_buffer = _render_scene(scene_surface, tilemap, player, wall_palette, fx)
        target_rect = _render_sprites(scene_surface, player, npcs, depth_buffer, highlight, fx)
        focus_point = target_rect.center if target_rect else None
        fx.draw_astral_motes(scene_surface, focus_point)
        fx.apply_scene_glow(scene_surface)

        screen.blit(scene_surface, (0, 0))

        biome = tilemap.biome_at_world(player.x, player.y)
        _draw_ui(screen, font, dlg, clock, player, biome, highlight, fx)
        _draw_dialogue(screen, font, dialogue_text)
        fx.draw_screen_overlay(screen)

        pg.display.flip()

    pg.quit()
    sys.exit()


if __name__ == "__main__":
    main()
