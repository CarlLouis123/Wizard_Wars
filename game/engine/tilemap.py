"""Procedural tile map driven by template definitions."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pygame as pg
import yaml

from .proc_templates import render_template_to_surface


@dataclass(frozen=True)
class GroundTile:
    id: str
    template: Path
    walkable: bool


@dataclass(frozen=True)
class DecoTile:
    id: str
    template: Path
    offset: Tuple[int, int] = (0, 0)


@dataclass(slots=True)
class BiomeDefinition:
    id: str
    label: str
    description: str
    radius_tiles: float
    palette: Dict[str, object]
    music: str
    weather: Dict[str, object]
    enemies: List[str]
    base_tiles: List[Tuple[str, float]]
    deco_tiles: List[Tuple[str, float]]


def _load_template(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


class TileMap:
    """Generate a tilemap by sampling biome definitions."""

    def __init__(self, w_tiles: int, h_tiles: int, tile_size: int, seed: int, templates_dir: str | Path):
        self.w = w_tiles
        self.h = h_tiles
        self.ts = tile_size
        self.seed = seed

        self.base: List[List[str]] = [["" for _ in range(w_tiles)] for _ in range(h_tiles)]
        self.deco: List[List[str]] = [["" for _ in range(w_tiles)] for _ in range(h_tiles)]
        self.biome_map: List[List[str]] = [["" for _ in range(w_tiles)] for _ in range(h_tiles)]

        self.templates_dir = Path(templates_dir)
        self._template_cache: Dict[Path, dict] = {}
        self._surface_cache: Dict[Tuple[Path, int], pg.Surface] = {}

        self.ground_tiles: Dict[str, GroundTile] = {}
        self.deco_tiles: Dict[str, DecoTile] = {}
        self._biomes: List[BiomeDefinition] = []
        self._biome_index: Dict[str, BiomeDefinition] = {}

        self._load_tile_catalog()
        self._load_biomes()
        self.generate()

    # ------------------------------------------------------------------ loaders
    def _load_tile_catalog(self) -> None:
        catalog_path = self.templates_dir / "world" / "tiles.yaml"
        with open(catalog_path, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}

        for entry in data.get("ground_tiles", []):
            tile_id = entry.get("id")
            if not tile_id:
                continue
            template = self.templates_dir / entry.get("template", "")
            self.ground_tiles[tile_id] = GroundTile(
                id=tile_id,
                template=template,
                walkable=bool(entry.get("walkable", True)),
            )

        for entry in data.get("decor_tiles", []):
            tile_id = entry.get("id")
            if not tile_id:
                continue
            template = self.templates_dir / entry.get("template", "")
            offset = entry.get("offset", [0, 0])
            if not (isinstance(offset, Iterable) and len(offset) == 2):  # type: ignore[arg-type]
                offset = [0, 0]
            self.deco_tiles[tile_id] = DecoTile(
                id=tile_id,
                template=template,
                offset=(int(offset[0]), int(offset[1])),
            )

    def _load_biomes(self) -> None:
        biomes_path = self.templates_dir / "world" / "biomes.yaml"
        with open(biomes_path, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}

        self._biomes.clear()
        self._biome_index.clear()
        for entry in data.get("biomes", []):
            biome = BiomeDefinition(
                id=entry.get("id", "unknown"),
                label=entry.get("label", "Unknown"),
                description=entry.get("description", ""),
                radius_tiles=float(entry.get("radius_tiles", 999)),
                palette=dict(entry.get("palette", {})),
                music=str(entry.get("music", "")),
                weather=dict(entry.get("weather", {})),
                enemies=list(entry.get("enemies", [])),
                base_tiles=[(opt.get("tile"), float(opt.get("weight", 0.0))) for opt in entry.get("base_tiles", [])],
                deco_tiles=[(opt.get("tile"), float(opt.get("weight", 0.0))) for opt in entry.get("deco_tiles", [])],
            )
            self._biomes.append(biome)
            self._biome_index[biome.id] = biome

        # Ensure outermost biome has an infinite radius to cover the map.
        if self._biomes:
            self._biomes[-1].radius_tiles = float("inf")

    # ---------------------------------------------------------------- generation
    def generate(self) -> None:
        centre_x = self.w / 2.0
        centre_y = self.h / 2.0

        for y in range(self.h):
            for x in range(self.w):
                dist = math.hypot(x - centre_x, y - centre_y)
                biome = self._biome_for_distance(dist)
                rng_seed = self.seed ^ (x * 73856093) ^ (y * 19349663)
                rng = random.Random(rng_seed)

                tile_id = self._choose_tile(biome.base_tiles, rng) or ""
                self.base[y][x] = tile_id
                self.biome_map[y][x] = biome.id

                deco_id = ""
                ground = self.ground_tiles.get(tile_id)
                if ground and ground.walkable:
                    deco_id = self._choose_deco(biome.deco_tiles, rng)
                self.deco[y][x] = deco_id

    def _biome_for_distance(self, distance: float) -> BiomeDefinition:
        for biome in self._biomes:
            if distance <= biome.radius_tiles:
                return biome
        return self._biomes[-1]

    @staticmethod
    def _choose_tile(options: List[Tuple[str, float]], rng: random.Random) -> Optional[str]:
        filtered = [(tile, weight) for tile, weight in options if tile and weight > 0]
        if not filtered:
            return None
        total = sum(weight for _, weight in filtered)
        roll = rng.random() * total
        upto = 0.0
        for tile, weight in filtered:
            upto += weight
            if roll <= upto:
                return tile
        return filtered[-1][0]

    @staticmethod
    def _choose_deco(options: List[Tuple[str, float]], rng: random.Random) -> str:
        for tile, weight in options:
            if not tile or weight <= 0:
                continue
            if rng.random() < weight:
                return tile
        return ""

    # ---------------------------------------------------------------- queries
    def walkable(self, tx: int, ty: int) -> bool:
        if not (0 <= tx < self.w and 0 <= ty < self.h):
            return False
        tile_id = self.base[ty][tx]
        ground = self.ground_tiles.get(tile_id)
        return bool(ground and ground.walkable)

    def biome_at(self, tx: int, ty: int) -> BiomeDefinition:
        if not (0 <= tx < self.w and 0 <= ty < self.h):
            return self._biomes[-1]
        biome_id = self.biome_map[ty][tx]
        return self._biome_index.get(biome_id, self._biomes[-1])

    def biome_at_world(self, wx: float, wy: float) -> BiomeDefinition:
        tx = int(wx // self.ts)
        ty = int(wy // self.ts)
        return self.biome_at(tx, ty)

    # ---------------------------------------------------------------- surfaces
    def _render(self, template_path: Path, variant_key: int) -> pg.Surface:
        tpl = self._template_cache.get(template_path)
        if tpl is None:
            tpl = _load_template(template_path)
            self._template_cache[template_path] = tpl
        tpl = dict(tpl)
        tpl["seed"] = int(variant_key) & 0xFFFFFFFF
        return render_template_to_surface(tpl)

    def get_tile_surface(self, tile_id: str, variant_key: int) -> pg.Surface:
        ground = self.ground_tiles.get(tile_id)
        if not ground:
            return pg.Surface((self.ts, self.ts), pg.SRCALPHA)

        key = (ground.template, variant_key)
        if key not in self._surface_cache:
            self._surface_cache[key] = self._render(ground.template, variant_key)
        return self._surface_cache[key]

    def get_deco_drawable(self, deco_id: str, variant_key: int) -> Optional[Tuple[pg.Surface, Tuple[int, int]]]:
        deco = self.deco_tiles.get(deco_id)
        if not deco:
            return None
        key = (deco.template, variant_key)
        if key not in self._surface_cache:
            self._surface_cache[key] = self._render(deco.template, variant_key)
        return self._surface_cache[key], deco.offset
