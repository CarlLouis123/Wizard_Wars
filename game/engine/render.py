"""Software raycaster used to render the world from a first-person perspective."""

from __future__ import annotations

import math
from typing import Iterable

import pygame as pg

from .player import PlayerController
from .terrain import TerrainSystem
from .world import TileDefinition, WorldMap

Vector2 = pg.math.Vector2


class RaycastRenderer:
    """Simple first-person raycasting renderer with diffuse lighting and shadows."""

    def __init__(self, world: WorldMap, width: int, height: int, terrain: TerrainSystem) -> None:
        self.world = world
        self.terrain = terrain
        self.resize(width, height)
        self.view_distance = 24.0
        self.time_of_day = 0.35
        self.day_length = 120.0
        self._sun_strength = 0.5
        self.ambient_light = 0.22

    # -------------------------------------------------------------------- sizing
    def resize(self, width: int, height: int) -> None:
        self.width = max(1, width)
        self.height = max(1, height)
        self.half_height = self.height // 2

    # ------------------------------------------------------------------- drawing
    def render(
        self,
        surface: pg.Surface,
        player: PlayerController,
        sprites: Iterable[object] | None = None,
    ) -> None:
        horizon = self._draw_background(surface, player)
        self._draw_floor(surface, player, horizon)
        direction = player.direction
        plane = player.camera_plane
        pos = player.position

        z_buffer = [float("inf")] * self.width
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

            z_buffer[column] = distance

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

        if sprites:
            self._draw_sprites(surface, player, sprites, z_buffer)

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

    def update_time(self, dt: float) -> None:
        if self.day_length <= 0:
            return
        self.time_of_day = (self.time_of_day + dt / self.day_length) % 1.0
        cycle = math.sin(self.time_of_day * math.tau)
        daylight = max(0.0, cycle)
        night = max(0.0, -cycle)
        self._sun_strength = 0.35 + daylight * 0.65
        self.ambient_light = 0.12 + daylight * 0.38 + night * 0.08
        self.world.light_intensity = 1.6 + daylight * 1.4 + night * 0.4

    def _draw_background(self, surface: pg.Surface, player: PlayerController) -> int:
        pitch = player.camera_height_offset
        horizon = int(self.half_height + pitch * self.height)
        horizon = max(0, min(self.height, horizon))

        sky_top, sky_bottom = self._sky_colors()
        self._draw_gradient(surface, pg.Rect(0, 0, self.width, horizon), sky_top, sky_bottom)
        self._draw_mountains(surface, player, horizon)
        self._draw_gradient(
            surface,
            pg.Rect(0, horizon, self.width, self.height - horizon),
            (18, 20, 26),
            (6, 6, 8),
        )
        return horizon

    def _draw_mountains(self, surface: pg.Surface, player: PlayerController, horizon: int) -> None:
        if horizon <= 0:
            return
        direction = player.direction
        plane = player.camera_plane
        pos = player.position
        for column in range(self.width):
            camera_x = 2 * column / self.width - 1
            ray_dir = direction + plane * camera_x
            ray_dir.normalize_ip()
            far_point = pos + ray_dir * self.terrain.mountain_distance
            height_value = self.terrain.mountain_height(far_point.x, far_point.y)
            column_height = int((0.45 + max(0.0, height_value)) * self.height * 0.22)
            start_y = max(0, horizon - column_height)
            color = self.terrain.mountain_color(height_value, self._sun_strength)
            if start_y < horizon:
                pg.draw.line(surface, color, (column, start_y), (column, horizon))

    def _draw_floor(self, surface: pg.Surface, player: PlayerController, horizon: int) -> None:
        if horizon >= self.height:
            return
        direction = player.direction
        plane = player.camera_plane
        pos = player.position

        ray_dir_left = direction - plane
        ray_dir_right = direction + plane

        pos_z = (self.height / 2.0) + player.camera_height_offset * self.height
        if pos_z <= 0.0:
            pos_z = 1.0

        surface.lock()
        try:
            pixels = pg.PixelArray(surface)
            map_rgb = surface.map_rgb
            for screen_y in range(max(horizon, 0), self.height):
                denom = screen_y - horizon + 0.5
                if abs(denom) < 1e-5:
                    continue
                row_distance = pos_z / denom
                floor_step = (ray_dir_right - ray_dir_left) * (row_distance / self.width)
                floor_pos = pos + ray_dir_left * row_distance
                for screen_x in range(self.width):
                    sample = self.terrain.sample(
                        floor_pos.x, floor_pos.y, row_distance, self._sun_strength
                    )
                    pixels[screen_x, screen_y] = map_rgb(sample.color)
                    floor_pos += floor_step
            del pixels
        finally:
            surface.unlock()

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

    def _sky_colors(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        day = max(0.0, min(1.0, self._sun_strength - 0.2))
        top_day = (68, 120, 210)
        bottom_day = (160, 205, 255)
        top_night = (8, 10, 25)
        bottom_night = (18, 22, 40)
        top_color = _lerp_tuple(top_night, top_day, day)
        bottom_color = _lerp_tuple(bottom_night, bottom_day, day)
        return top_color, bottom_color

    def _draw_sprites(
        self,
        surface: pg.Surface,
        player: PlayerController,
        sprites: Iterable[object],
        z_buffer: list[float],
    ) -> None:
        plane = player.camera_plane
        direction = player.direction
        pos = player.position
        determinant = plane.x * direction.y - direction.x * plane.y
        if abs(determinant) < 1e-6:
            determinant = 1e-6
        inv_det = 1.0 / determinant
        pitch_offset = int(player.camera_height_offset * self.height)

        # Sort sprites by distance descending for painter's algorithm fallback.
        sortable = []
        for sprite in sprites:
            if not hasattr(sprite, "x") or not hasattr(sprite, "sprite"):
                continue
            dx = float(sprite.x) - pos.x
            dy = float(sprite.y) - pos.y
            distance_sq = dx * dx + dy * dy
            sortable.append((distance_sq, sprite))
        sortable.sort(key=lambda entry: entry[0], reverse=True)

        for _, sprite in sortable:
            sprite_surface = sprite.sprite
            sprite_x = float(sprite.x) - pos.x
            sprite_y = float(sprite.y) - pos.y

            transform_x = inv_det * (direction.y * sprite_x - direction.x * sprite_y)
            transform_y = inv_det * (-plane.y * sprite_x + plane.x * sprite_y)
            if transform_y <= 0:
                continue

            sprite_screen_x = int((self.width / 2) * (1 + transform_x / transform_y))
            sprite_height = abs(int(self.height / transform_y))
            sprite_width = sprite_height
            draw_start_y = -sprite_height // 2 + self.half_height + pitch_offset
            draw_end_y = sprite_height // 2 + self.half_height + pitch_offset
            draw_start_x = sprite_screen_x - sprite_width // 2
            draw_end_x = sprite_screen_x + sprite_width // 2

            if draw_end_x < 0 or draw_start_x >= self.width:
                continue

            if 0 <= sprite_screen_x < self.width:
                if transform_y >= z_buffer[sprite_screen_x] + 0.2:
                    continue

            scaled_sprite = pg.transform.smoothscale(sprite_surface, (sprite_width, sprite_height))
            dest_rect = scaled_sprite.get_rect()
            dest_rect.centerx = sprite_screen_x
            dest_rect.bottom = draw_end_y
            surface.blit(scaled_sprite, dest_rect)


def _lerp_tuple(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )
