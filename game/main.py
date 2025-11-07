"""Entry point for the production-grade Wizard Wars first-person prototype."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Iterable

import pygame as pg

from engine.player import MovementInput, PlayerController
from engine.render import RaycastRenderer
from engine.world import TileDefinition, WorldMap
import settings as S


MAP_LAYOUT = (
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

TILESET = {
    "0": TileDefinition((60, 60, 70), solid=False),
    "1": TileDefinition((210, 210, 220), solid=True),
    "2": TileDefinition((140, 180, 255), solid=True),
    "3": TileDefinition((220, 120, 150), solid=True),
    "4": TileDefinition((200, 160, 80), solid=True),
    "A": TileDefinition((60, 120, 220), solid=True),
    "B": TileDefinition((180, 90, 220), solid=True),
}


@dataclass
class GameConfig:
    resolution: tuple[int, int]
    fps_limit: int
    move_speed: float
    mouse_sensitivity: float


class GameApp:
    """High-level application wrapper providing lifecycle management."""

    def __init__(self, config: GameConfig) -> None:
        pg.init()
        pg.display.set_caption("Wizard Wars :: Prototype 3D Engine")
        self.screen = pg.display.set_mode(config.resolution, pg.RESIZABLE)
        self.clock = pg.time.Clock()

        self.config = config
        self.world = WorldMap(MAP_LAYOUT, TILESET, light_position=(7.5, 3.5), light_intensity=2.8)
        self.player = PlayerController(
            position=(2.5, 2.5),
            yaw=0.0,
            move_speed=config.move_speed,
            mouse_sensitivity=config.mouse_sensitivity,
        )
        self.renderer = RaycastRenderer(self.world, *config.resolution)
        self._movement = MovementInput()
        self._mouse_captured = False
        self._toggle_mouse_lock(True)

    # ----------------------------------------------------------------- lifecycle
    def run(self) -> None:
        while True:
            dt = self.clock.tick(self.config.fps_limit) / 1000.0
            if not self._process_events():
                break
            self._update(dt)
            self._draw()
            pg.display.flip()
            fps = self.clock.get_fps()
            pg.display.set_caption(f"Wizard Wars :: FPS {fps:5.1f}")

    # ------------------------------------------------------------------- internals
    def _process_events(self) -> bool:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return False
            if event.type == pg.VIDEORESIZE:
                self.screen = pg.display.set_mode(event.size, pg.RESIZABLE)
                self.renderer.resize(*event.size)
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                if self._mouse_captured:
                    self._toggle_mouse_lock(False)
                else:
                    return False
            if event.type == pg.MOUSEMOTION and self._mouse_captured:
                dx, dy = event.rel
                self.player.handle_mouse(dx, dy)
        return True

    def _toggle_mouse_lock(self, enable: bool) -> None:
        self._mouse_captured = enable
        pg.mouse.set_visible(not enable)
        pg.event.set_grab(enable)
        pg.mouse.get_rel()

    def _update(self, dt: float) -> None:
        keys = pg.key.get_pressed()
        self._movement.forward = float(keys[pg.K_w]) - float(keys[pg.K_s])
        self._movement.right = float(keys[pg.K_d]) - float(keys[pg.K_a])
        self.player.update(dt, self._movement, self.world)

    def _draw(self) -> None:
        self.renderer.render(self.screen, self.player)


def build_config() -> GameConfig:
    resolution = (getattr(S, "WINDOW_W", 960), getattr(S, "WINDOW_H", 540))
    fps_limit = getattr(S, "FPS", 60)
    base_speed_tiles = getattr(S, "PLAYER_BASE_SPEED_TILES", 3.5)
    move_speed = base_speed_tiles * 0.9
    mouse_sensitivity = 0.0022
    return GameConfig(resolution, fps_limit, move_speed, mouse_sensitivity)


def main(argv: Iterable[str] | None = None) -> int:
    config = build_config()
    app = GameApp(config)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
