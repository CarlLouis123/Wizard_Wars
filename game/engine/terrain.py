"""Procedural terrain synthesis utilities used by the renderer."""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass


def _hash_noise(x: float, y: float, seed: int) -> float:
    """Deterministic pseudo-random noise in the range [0, 1]."""

    value = math.sin(x * 12.9898 + y * 78.233 + seed * 0.192) * 43758.5453
    return value - math.floor(value)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_color(
    c0: tuple[int, int, int], c1: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(_lerp(c0[0], c1[0], t)),
        int(_lerp(c0[1], c1[1], t)),
        int(_lerp(c0[2], c1[2], t)),
    )


@dataclass(slots=True)
class TerrainSample:
    color: tuple[int, int, int]
    height: float


class TerrainSystem:
    """Generates a stylised heightmap, textures, and distant silhouettes."""

    def __init__(self, seed: int = 1337, scale: float = 0.08) -> None:
        self.seed = seed
        self.scale = scale
        self.mountain_distance = 64.0
        # Terrain shading is evaluated thousands of times per frame. The
        # underlying noise functions are comparatively expensive, so we cache
        # quantised lookups to drastically cut down the number of evaluations.
        # An ordered dict keeps the memory footprint bounded while providing a
        # lightweight manual LRU cache.
        self._sample_cache: "OrderedDict[tuple[int, int, int, int], TerrainSample]" = OrderedDict()
        self._cache_limit = 50_000
        self._cache_scale_xy = 4.0  # 0.25 world unit precision
        self._cache_scale_distance = 12.0  # ~0.08 precision
        self._cache_scale_light = 24.0  # ~0.04 precision

    # ----------------------------------------------------------------- sampling
    def sample(self, wx: float, wy: float, distance: float, light: float) -> TerrainSample:
        key = self._quantise_sample(wx, wy, distance, light)
        cached = self._sample_cache.get(key)
        if cached is not None:
            # Refresh position to maintain simple LRU behaviour.
            self._sample_cache.move_to_end(key)
            return cached

        height = self._height(wx, wy)

        river = self._river_mask(wx, wy)
        road = self._road_mask(wx, wy)
        grass_color = self._grass_color(wx, wy, height)

        if river < 0.12:
            tint = river / 0.12
            base_color = _lerp_color((28, 60, 130), (70, 140, 210), tint)
        elif road < 0.08:
            tint = road / 0.08
            base_color = _lerp_color((70, 60, 50), (130, 118, 96), tint)
        else:
            base_color = grass_color

        tree_density = self._tree_density(wx, wy, height)
        if tree_density > 0.0 and river > 0.25:
            base_color = _lerp_color(base_color, (28, 90, 32), tree_density * 0.8)

        shade = 0.6 + 0.4 * ((height + 1.0) * 0.5)
        fog = 1.0 / (1.0 + distance * 0.03)
        shade *= fog * light
        shade = max(0.1, min(1.0, shade))
        shaded_color = tuple(int(component * shade) for component in base_color)
        sample = TerrainSample(shaded_color, height)
        self._store_sample_cache(key, sample)
        return sample

    def _quantise_sample(
        self, wx: float, wy: float, distance: float, light: float
    ) -> tuple[int, int, int, int]:
        qx = int(wx * self._cache_scale_xy)
        qy = int(wy * self._cache_scale_xy)
        qd = int(distance * self._cache_scale_distance)
        ql = int(light * self._cache_scale_light)
        return (qx, qy, qd, ql)

    def _store_sample_cache(
        self, key: tuple[int, int, int, int], sample: TerrainSample
    ) -> None:
        cache = self._sample_cache
        cache[key] = sample
        cache.move_to_end(key)
        if len(cache) > self._cache_limit:
            cache.popitem(last=False)

    def mountain_height(self, wx: float, wy: float) -> float:
        """Approximate skyline elevation for distant mountains."""

        height = self._height(wx, wy)
        ridge = self._ridge(wx, wy)
        return max(-0.6, min(1.3, height * 0.7 + ridge * 0.5))

    def mountain_color(self, height: float, light: float) -> tuple[int, int, int]:
        base = _lerp_color((50, 52, 60), (120, 125, 135), max(0.0, height))
        snow_line = 0.65
        if height > snow_line:
            snow_t = min(1.0, (height - snow_line) / 0.4)
            base = _lerp_color(base, (235, 235, 240), snow_t)
        shade = 0.4 + light * 0.6
        return tuple(int(component * shade) for component in base)

    # ------------------------------------------------------------- internal noise
    def _height(self, wx: float, wy: float) -> float:
        x = wx * self.scale
        y = wy * self.scale
        return self._fbm(x, y)

    def _grass_color(self, wx: float, wy: float, height: float) -> tuple[int, int, int]:
        base = (60, 110, 54)
        highlight = (120, 170, 96)
        hue_noise = _hash_noise(wx * 0.4, wy * 0.4, self.seed)
        mix = max(0.0, min(1.0, (height + 1.0) * 0.4 + hue_noise * 0.3))
        return _lerp_color(base, highlight, mix)

    def _river_mask(self, wx: float, wy: float) -> float:
        meander = math.sin((wx + self.seed) * 0.12) * 4.5
        distance = abs(wy - meander * 0.4 - 6.0)
        distance *= 0.18
        return min(1.0, distance)

    def _road_mask(self, wx: float, wy: float) -> float:
        band_a = abs(math.sin((wx + wy * 0.4) * 0.2 + self.seed * 0.3))
        band_b = abs(math.sin((wy - wx * 0.3) * 0.25 + self.seed * 0.17))
        distance = min(band_a, band_b)
        return min(1.0, distance * 1.6)

    def _tree_density(self, wx: float, wy: float, height: float) -> float:
        if height < -0.2:
            return 0.0
        density = _hash_noise(wx * 0.55, wy * 0.55, self.seed + 9)
        density = max(0.0, density - 0.65) * 2.8
        return max(0.0, min(1.0, density))

    def _ridge(self, wx: float, wy: float) -> float:
        x = wx * self.scale * 0.6
        y = wy * self.scale * 0.6
        noise = math.sin(x * 3.1 + self.seed * 0.4) * math.cos(y * 2.7 + self.seed * 0.2)
        return noise

    def _fbm(self, x: float, y: float, octaves: int = 5) -> float:
        amplitude = 1.0
        frequency = 1.0
        value = 0.0
        total_amplitude = 0.0
        for i in range(octaves):
            noise = _hash_noise(x * frequency, y * frequency, self.seed + i * 37)
            noise = noise * 2.0 - 1.0
            value += noise * amplitude
            total_amplitude += amplitude
            amplitude *= 0.5
            frequency *= 2.05
        return value / max(total_amplitude, 1e-5)

