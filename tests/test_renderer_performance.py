"""Performance regression checks that guard the renderer's frame time."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Iterator

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame as pg
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = REPO_ROOT / "game"
if str(GAME_ROOT) not in sys.path:
    sys.path.insert(0, str(GAME_ROOT))

from engine.player import PlayerController
from engine.render import RaycastRenderer
from engine.terrain import TerrainSystem
from engine.world import TileDefinition, WorldMap


# The compact map roughly matches the one used by ``game.main`` but keeps the
# renderer focused on the most important surfaces for the FPS measurement.
MAP_LAYOUT: tuple[str, ...] = (
    "111111111111111",
    "1A0000000000001",
    "100011110000001",
    "103011210000001",
    "100010010000001",
    "100010010000001",
    "100000000000001",
    "100000040000001",
    "100000000000001",
    "122222222222221",
    "1B0000000000001",
    "111111111111111",
)

TILESET: dict[str, TileDefinition] = {
    "0": TileDefinition((60, 60, 70), solid=False),
    "1": TileDefinition((210, 210, 220), solid=True),
    "2": TileDefinition((140, 180, 255), solid=True),
    "3": TileDefinition((220, 120, 150), solid=True),
    "4": TileDefinition((200, 160, 80), solid=True),
    "A": TileDefinition((60, 120, 220), solid=True),
    "B": TileDefinition((180, 90, 220), solid=True),
}


@pytest.fixture(scope="module")
def pygame_headless() -> Iterator[None]:
    """Initialise pygame in headless mode for the duration of the module."""

    pg.init()
    try:
        yield
    finally:
        pg.quit()


def _build_renderer(width: int, height: int) -> tuple[RaycastRenderer, pg.Surface, PlayerController]:
    """Construct a renderer/surface/player trio for repeated frame rendering."""

    world = WorldMap(MAP_LAYOUT, TILESET, light_position=(7.5, 3.5), light_intensity=2.8)
    terrain = TerrainSystem(seed=2718)
    renderer = RaycastRenderer(world, width, height, terrain)
    renderer._gpu_enabled = False  # force CPU path for deterministic timing
    surface = pg.Surface((width, height))
    player = PlayerController(position=(2.5, 2.5))
    return renderer, surface, player


def _measure_fps(renderer: RaycastRenderer, surface: pg.Surface, player: PlayerController, frames: int) -> float:
    """Render ``frames`` frames and return the achieved frames per second."""

    start = time.perf_counter()
    for _ in range(frames):
        # Apply a tiny yaw perturbation so that consecutive frames are not identical.
        player.handle_mouse(0.002, 0.0)
        renderer.render(surface, player)
    elapsed = time.perf_counter() - start
    return frames / max(elapsed, 1e-9)


def test_raycast_renderer_maintains_playable_fps(pygame_headless: None) -> None:
    """The CPU renderer should comfortably exceed a 35 FPS baseline."""

    width, height = 80, 60
    renderer, surface, player = _build_renderer(width, height)

    # Render enough frames to iron out one-off fluctuations and cache warm-up.
    measured_fps = _measure_fps(renderer, surface, player, frames=240)

    assert measured_fps >= 35.0, f"Expected >=35 FPS, observed {measured_fps:.1f}"
