"""Software raycaster used to render the world from a first-person perspective."""

from __future__ import annotations

import pygame as pg

from .player import PlayerController
from .world import TileDefinition, WorldMap

Vector2 = pg.math.Vector2


class RaycastRenderer:
    """Simple first-person raycasting renderer with diffuse lighting and shadows."""

    def __init__(self, world: WorldMap, width: int, height: int) -> None:
        self.world = world
        self.resize(width, height)
        self.view_distance = 24.0
        self.ambient_light = 0.22

    # -------------------------------------------------------------------- sizing
    def resize(self, width: int, height: int) -> None:
        self.width = max(1, width)
        self.height = max(1, height)
        self.half_height = self.height // 2

    # ------------------------------------------------------------------- drawing
    def render(self, surface: pg.Surface, player: PlayerController) -> None:
        self._draw_background(surface, player)
        direction = player.direction
        plane = player.camera_plane
        pos = player.position

        for column in range(self.width):
            camera_x = 2 * column / self.width - 1
            ray_dir_x = direction.x + plane.x * camera_x
            ray_dir_y = direction.y + plane.y * camera_x
            ray_dir = Vector2(ray_dir_x, ray_dir_y)

            wall_hit = self._cast_ray(pos, ray_dir)
            if wall_hit is None:
                continue

            distance, tile_x, tile_y, side, step_x, step_y = wall_hit
            if distance <= 0.0:
                continue

            line_height = int(self.height / distance)
            pitch_offset = int(player.camera_height_offset * self.height)
            draw_start = -line_height // 2 + self.half_height + pitch_offset
            draw_end = line_height // 2 + self.half_height + pitch_offset
            draw_start_clamped = max(0, min(self.height - 1, draw_start))
            draw_end_clamped = max(0, min(self.height - 1, draw_end))

            tile = self.world.tile(tile_x, tile_y)
            color = self._shade_color(tile, pos, ray_dir, distance, side, step_x, step_y)
            if draw_end_clamped >= draw_start_clamped:
                pg.draw.line(surface, color, (column, draw_start_clamped), (column, draw_end_clamped))

    # ------------------------------------------------------------------ internals
    def _cast_ray(self, origin: Vector2, direction: Vector2):
        map_x = int(origin.x)
        map_y = int(origin.y)

        delta_dist_x = abs(1 / direction.x) if direction.x != 0 else float("inf")
        delta_dist_y = abs(1 / direction.y) if direction.y != 0 else float("inf")

        if direction.x < 0:
            step_x = -1
            side_dist_x = (origin.x - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - origin.x) * delta_dist_x

        if direction.y < 0:
            step_y = -1
            side_dist_y = (origin.y - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - origin.y) * delta_dist_y

        hit = False
        side = 0
        max_steps = 512
        for _ in range(max_steps):
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            if self.world.tile(map_x, map_y).solid:
                hit = True
                break
        if not hit:
            return None

        if side == 0:
            distance = (map_x - origin.x + (1 - step_x) / 2) / (direction.x or 1e-6)
        else:
            distance = (map_y - origin.y + (1 - step_y) / 2) / (direction.y or 1e-6)
        distance = max(distance, 1e-4)
        return distance, map_x, map_y, side, step_x, step_y

    def _shade_color(
        self,
        tile: TileDefinition,
        origin: Vector2,
        ray_dir: Vector2,
        distance: float,
        side: int,
        step_x: int,
        step_y: int,
    ) -> tuple[int, int, int]:
        base_color = tile.color
        hit_point = origin + ray_dir * distance

        if side == 0:
            normal = Vector2(-step_x, 0)
        else:
            normal = Vector2(0, -step_y)

        light_factor = self._compute_lighting(hit_point, normal, distance)
        shaded = tuple(max(0, min(255, int(component * light_factor))) for component in base_color)
        return shaded

    def _compute_lighting(self, hit_point: Vector2, normal: Vector2, distance: float) -> float:
        ambient = self.ambient_light
        light_pos = self.world.light_position
        to_light = light_pos - hit_point
        light_distance = to_light.length()
        if light_distance < 1e-5:
            return 1.0
        light_dir = to_light.normalize()

        if self.world.has_line_of_sight(hit_point + normal * 0.02, light_pos):
            diffuse = max(0.0, normal.dot(light_dir))
            attenuation = 1.0 / (1.0 + 0.14 * light_distance + 0.07 * light_distance * light_distance)
            light_term = diffuse * attenuation * self.world.light_intensity
        else:
            light_term = 0.08

        fog = max(0.2, 1.0 - min(distance / self.view_distance, 1.0) ** 1.2)
        brightness = ambient + light_term
        return max(0.05, min(1.0, brightness * fog))

    def _draw_background(self, surface: pg.Surface, player: PlayerController) -> None:
        pitch = player.camera_height_offset
        horizon = int(self.half_height + pitch * self.height)
        horizon = max(0, min(self.height, horizon))

        self._draw_gradient(surface, pg.Rect(0, 0, self.width, horizon), (32, 43, 96), (5, 7, 18))
        self._draw_gradient(
            surface,
            pg.Rect(0, horizon, self.width, self.height - horizon),
            (18, 20, 26),
            (6, 6, 8),
        )

    def _draw_gradient(
        self,
        surface: pg.Surface,
        rect: pg.Rect,
        top_color: tuple[int, int, int],
        bottom_color: tuple[int, int, int],
    ) -> None:
        if rect.height <= 0:
            return
        for y in range(rect.height):
            t = y / max(rect.height - 1, 1)
            color = (
                int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
                int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
                int(top_color[2] + (bottom_color[2] - top_color[2]) * t),
            )
            pg.draw.line(surface, color, (rect.left, rect.top + y), (rect.right, rect.top + y))
