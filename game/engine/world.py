"""World representation and collision utilities for the Wizard Wars FPS demo."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

import pygame as pg

Vector2 = pg.math.Vector2


@dataclass(frozen=True)
class TileDefinition:
    """Static description of a single map tile."""

    color: tuple[int, int, int]
    solid: bool = True


class WorldMap:
    """Grid-based world representation with collision helpers."""

    def __init__(
        self,
        layout: Sequence[str],
        tile_definitions: dict[str, TileDefinition],
        light_position: Iterable[float] = (4.5, 4.5),
        light_intensity: float = 2.4,
    ) -> None:
        if not layout:
            raise ValueError("World layout must contain at least one row")
        row_lengths = {len(row) for row in layout}
        if len(row_lengths) != 1:
            raise ValueError("World layout rows must be of equal length")

        self.width = row_lengths.pop()
        self.height = len(layout)
        self._grid = [list(row) for row in layout]
        self._tiles = tile_definitions
        self.light_position = Vector2(*light_position)
        self.light_intensity = float(light_intensity)

    # --------------------------------------------------------------------- tiles
    def tile_id(self, tile_x: int, tile_y: int) -> str:
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return "1"  # treat out-of-bounds as walls
        return self._grid[tile_y][tile_x]

    def tile(self, tile_x: int, tile_y: int) -> TileDefinition:
        tile_id = self.tile_id(tile_x, tile_y)
        return self._tiles.get(tile_id, TileDefinition((200, 200, 200), solid=True))

    def is_wall(self, x: float | int, y: float | int) -> bool:
        tile_x = int(math.floor(x))
        tile_y = int(math.floor(y))
        tile = self.tile(tile_x, tile_y)
        return tile.solid

    # ------------------------------------------------------------------ collision
    def collides(self, position: Vector2, radius: float) -> bool:
        samples = (
            (position.x - radius, position.y - radius),
            (position.x - radius, position.y + radius),
            (position.x + radius, position.y - radius),
            (position.x + radius, position.y + radius),
        )
        return any(self.is_wall(x, y) for x, y in samples)

    def clip_movement(self, origin: Vector2, proposed: Vector2, radius: float) -> Vector2:
        """Resolve wall collisions for the player's circular collider."""

        resolved = Vector2(proposed)

        # Resolve X axis
        test_pos = Vector2(resolved.x, origin.y)
        if self.collides(test_pos, radius):
            resolved.x = origin.x
        # Resolve Y axis with updated X
        test_pos.update(resolved.x, resolved.y)
        if self.collides(test_pos, radius):
            resolved.y = origin.y
        return resolved

    # --------------------------------------------------------------- line-of-sight
    def has_line_of_sight(self, start: Vector2, end: Vector2, step: float = 0.1) -> bool:
        """Coarse visibility test between two points inside the map."""

        direction = Vector2(end) - start
        distance = direction.length()
        if distance < 1e-5:
            return True
        direction.scale_to_length(step)
        samples = int(distance / step)
        probe = Vector2(start)
        for _ in range(samples):
            probe += direction
            if self.is_wall(probe.x, probe.y):
                return False
        return True
