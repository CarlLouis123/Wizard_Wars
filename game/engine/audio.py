"""Lightweight audio management for ambience, footsteps, and weather."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, Optional

import pygame as pg


class AudioManager:
    """Encapsulates sound playback while gracefully handling missing assets."""

    def __init__(self, content_dir: Path) -> None:
        self.content_dir = content_dir
        self._enabled = self._init_mixer()
        self._ambient_channel: Optional[pg.mixer.Channel] = None
        self._effect_channel: Optional[pg.mixer.Channel] = None
        self._loops: Dict[str, pg.mixer.Sound] = {}
        self._effects: Dict[str, list[pg.mixer.Sound]] = {}
        self._current_ambient: Optional[str] = None
        self._footstep_timer = 0.0

        if self._enabled:
            self._ambient_channel = pg.mixer.Channel(0)
            self._effect_channel = pg.mixer.Channel(1)
            self._load_defaults()

    # ------------------------------------------------------------------ helpers
    def _init_mixer(self) -> bool:
        try:
            if not pg.mixer.get_init():
                pg.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            return True
        except Exception:
            return False

    def _load_defaults(self) -> None:
        self._register_loop("ambient_clear", "ambient_clear.ogg", volume=0.35)
        self._register_loop("ambient_rain", "ambient_rain.ogg", volume=0.45)
        self._register_loop("ambient_wind", "ambient_wind.ogg", volume=0.4)
        self._register_loop("ambient_fog", "ambient_fog.ogg", volume=0.3)

        self._register_effect("footstep_soft", ["footstep_grass1.wav", "footstep_grass2.wav"])
        self._register_effect("footstep_hard", ["footstep_stone1.wav", "footstep_stone2.wav"])
        self._register_effect("environmental", ["owl_hoot.wav", "wind_gust.wav", "drip.wav"])

    def _resolve(self, relative: str) -> Optional[Path]:
        path = self.content_dir / relative
        if path.exists():
            return path
        return None

    def _register_loop(self, key: str, filename: str, volume: float = 1.0) -> None:
        resolved = self._resolve(filename)
        if not resolved:
            return
        try:
            sound = pg.mixer.Sound(resolved.as_posix())
        except Exception:
            return
        sound.set_volume(max(0.0, min(1.0, volume)))
        self._loops[key] = sound

    def _register_effect(self, key: str, filenames: list[str]) -> None:
        resolved: list[pg.mixer.Sound] = []
        for filename in filenames:
            path = self._resolve(filename)
            if not path:
                continue
            try:
                resolved.append(pg.mixer.Sound(path.as_posix()))
            except Exception:
                continue
        if resolved:
            self._effects[key] = resolved

    # ------------------------------------------------------------------- control
    def update(self, dt: float, is_moving: bool, surface: str, weather: str) -> None:
        if not self._enabled:
            return

        self._update_ambient(weather)
        self._footstep_timer = max(0.0, self._footstep_timer - dt)
        if is_moving and self._footstep_timer <= 0.0:
            self.play_footstep(surface)
            self._footstep_timer = 0.42 if surface == "soft" else 0.32

        if random.random() < dt * 0.05:
            self._play_random_environmental()

    def _update_ambient(self, weather: str) -> None:
        mapping = {
            "rain": "ambient_rain",
            "fog": "ambient_fog",
            "wind": "ambient_wind",
        }
        key = mapping.get(weather, "ambient_clear")
        if key == self._current_ambient:
            return
        sound = self._loops.get(key)
        if sound is None or self._ambient_channel is None:
            return
        self._ambient_channel.play(sound, loops=-1, fade_ms=750)
        self._current_ambient = key

    def play_footstep(self, surface: str) -> None:
        key = "footstep_soft" if surface == "soft" else "footstep_hard"
        self._play_effect(key, volume=0.6 if surface == "soft" else 0.5)

    def _play_random_environmental(self) -> None:
        self._play_effect("environmental", volume=0.45)

    def _play_effect(self, key: str, volume: float = 1.0) -> None:
        if not self._enabled or self._effect_channel is None:
            return
        sounds = self._effects.get(key)
        if not sounds:
            return
        sound = random.choice(sounds)
        sound.set_volume(max(0.0, min(1.0, volume)))
        self._effect_channel.play(sound)

    def shutdown(self) -> None:
        if not self._enabled:
            return
        try:
            pg.mixer.fadeout(500)
        except Exception:
            pass
