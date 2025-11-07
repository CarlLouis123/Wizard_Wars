"""Weather simulation and rendering helpers."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple

import pygame as pg


@dataclass
class WeatherParticle:
    position: pg.math.Vector2
    velocity: pg.math.Vector2
    length: float
    color: Tuple[int, int, int, int]


class WeatherSystem:
    """Generates rain, fog, and wind overlays for the renderer."""

    def __init__(self, size: Tuple[int, int]) -> None:
        self.size = size
        self.current_state = "clear"
        self.transition_timer = 0.0
        self.next_transition = random.uniform(35.0, 65.0)
        self.intensity = 0.0
        self._particles: List[WeatherParticle] = []
        self._surface = pg.Surface(size, pg.SRCALPHA)
        self._wind_offset = 0.0
        self._fog_density = 0.0

    # ---------------------------------------------------------------- lifecycle
    def resize(self, width: int, height: int) -> None:
        self.size = (max(1, width), max(1, height))
        self._surface = pg.Surface(self.size, pg.SRCALPHA)
        self._particles.clear()

    def update(self, dt: float) -> None:
        self.transition_timer += dt
        if self.transition_timer >= self.next_transition:
            self.transition_timer = 0.0
            self.next_transition = random.uniform(35.0, 65.0)
            self.current_state = random.choice(["clear", "rain", "fog", "wind"])

        target_intensity = {
            "clear": 0.0,
            "rain": 1.0,
            "fog": 0.8,
            "wind": 0.6,
        }.get(self.current_state, 0.0)
        self.intensity += (target_intensity - self.intensity) * min(1.0, dt * 1.5)

        if self.current_state == "rain":
            self._update_rain(dt)
            self._fog_density += (0.3 - self._fog_density) * min(1.0, dt * 0.6)
        elif self.current_state == "fog":
            self._fog_density += (0.6 - self._fog_density) * min(1.0, dt * 0.5)
            self._particles.clear()
        else:
            self._fog_density += (0.1 - self._fog_density) * min(1.0, dt * 0.4)
            self._update_wind(dt if self.current_state == "wind" else 0.0)

    # ------------------------------------------------------------------- drawing
    def draw(self, target: pg.Surface) -> None:
        if self.intensity <= 0.01:
            return

        self._surface.fill((0, 0, 0, 0))
        if self.current_state == "rain":
            self._draw_rain(self._surface)
        elif self.current_state == "wind":
            self._draw_wind(self._surface)

        if self._fog_density > 0.05:
            fog_alpha = int(max(0, min(180, 255 * self._fog_density * self.intensity)))
            fog_overlay = pg.Surface(self.size, pg.SRCALPHA)
            fog_overlay.fill((140, 150, 160, fog_alpha))
            self._surface.blit(fog_overlay, (0, 0))

        blend_flag = getattr(pg, "BLEND_ALPHA_SDL2", pg.BLEND_PREMULTIPLIED)
        target.blit(self._surface, (0, 0), special_flags=blend_flag)

    # ------------------------------------------------------------------ helpers
    def _update_rain(self, dt: float) -> None:
        spawn_rate = int(450 * self.intensity)
        width, height = self.size
        for _ in range(spawn_rate):
            x = random.uniform(0, width)
            y = random.uniform(-height * 0.2, 0)
            velocity = pg.math.Vector2(random.uniform(-40, -20), random.uniform(420, 620))
            length = random.uniform(6, 12)
            color = (180, 200, 255, 140)
            self._particles.append(WeatherParticle(pg.math.Vector2(x, y), velocity, length, color))

        alive: List[WeatherParticle] = []
        for particle in self._particles:
            particle.position += particle.velocity * dt
            if particle.position.y - particle.length > height:
                continue
            alive.append(particle)
        self._particles = alive[-1200:]

    def _update_wind(self, dt: float) -> None:
        if dt <= 0.0:
            return
        self._wind_offset += dt * 40.0
        self._wind_offset %= self.size[0] + 120

    def _draw_rain(self, surface: pg.Surface) -> None:
        for particle in self._particles:
            start = (particle.position.x, particle.position.y)
            end = (particle.position.x + particle.velocity.x * 0.04, particle.position.y + particle.length)
            pg.draw.line(surface, particle.color, start, end, 1)

    def _draw_wind(self, surface: pg.Surface) -> None:
        width, height = self.size
        spacing = 90
        gust_color = (200, 220, 235, int(120 * self.intensity))
        for i in range(-1, width // spacing + 3):
            x = (i * spacing + self._wind_offset) % (width + spacing) - spacing
            y = height * 0.2 + (i % 3) * 60
            rect = pg.Rect(int(x), int(y), 80, 2)
            pg.draw.rect(surface, gust_color, rect)
