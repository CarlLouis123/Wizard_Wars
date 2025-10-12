"""Procedural tile map used by the demo."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, Tuple

import pygame as pg

from .proc_templates import render_template_to_surface

T_GRASS = 1
T_SAND = 2
T_WATER = 3
T_TREE = 4


def _load_template(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


class TileMap:
    def __init__(self, w_tiles: int, h_tiles: int, tile_size: int, seed: int, templates_dir: str | Path):
        self.w = w_tiles
        self.h = h_tiles
        self.ts = tile_size
        self.seed = seed

        self.base = [[T_GRASS for _ in range(w_tiles)] for _ in range(h_tiles)]
        self.deco = [[0 for _ in range(w_tiles)] for _ in range(h_tiles)]
        self._cache: Dict[Tuple[int, int], pg.Surface] = {}

        templates_dir = Path(templates_dir)
        self.templates_dir = templates_dir
        self._tpl_grass = _load_template(templates_dir / "grass.json")
        self._tpl_sand = _load_template(templates_dir / "sand.json")
        self._tpl_water = _load_template(templates_dir / "water.json")
        self._tpl_tree = _load_template(templates_dir / "tree.json")

        self.generate()

    def generate(self) -> None:
        random.seed(self.seed)
        for y in range(self.h):
            for x in range(self.w):
                roll = random.random()
                if roll < 0.08:
                    self.base[y][x] = T_WATER
                elif roll < 0.20:
                    self.base[y][x] = T_SAND
                else:
                    self.base[y][x] = T_GRASS

                if self.base[y][x] == T_GRASS and random.random() < 0.05:
                    self.deco[y][x] = T_TREE

    def walkable(self, tx: int, ty: int) -> bool:
        if not (0 <= tx < self.w and 0 <= ty < self.h):
            return False
        return self.base[ty][tx] != T_WATER

    def _render(self, tpl: dict, variant_key: int) -> pg.Surface:
        tpl = dict(tpl)
        tpl["seed"] = int(variant_key) & 0xFFFFFFFF
        return render_template_to_surface(tpl)

    def get_tile_surface(self, tile_id: int, variant_key: int) -> pg.Surface:
        key = (tile_id, variant_key)
        if key in self._cache:
            return self._cache[key]

        if tile_id == T_GRASS:
            surface = self._render(self._tpl_grass, variant_key)
        elif tile_id == T_SAND:
            surface = self._render(self._tpl_sand, variant_key)
        elif tile_id == T_WATER:
            surface = self._render(self._tpl_water, variant_key)
        else:
            surface = pg.Surface((self.ts, self.ts), pg.SRCALPHA)

        self._cache[key] = surface
        return surface

    def get_deco_surface(self, deco_id: int, variant_key: int) -> pg.Surface | None:
        if deco_id == T_TREE:
            return self._render(self._tpl_tree, variant_key)
        return None
