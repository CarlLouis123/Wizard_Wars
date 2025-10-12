"""Entity primitives used by the demo game."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pygame as pg

from .proc_templates import render_template_to_surface


def _load_template(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


@dataclass(slots=True)
class Entity:
    x: float
    y: float
    sprite: pg.Surface
    solid: bool = True

    def rect(self) -> pg.Rect:
        rect = self.sprite.get_rect()
        rect.center = (int(self.x), int(self.y))
        return rect


class Player(Entity):
    def __init__(self, x: float, y: float, tile_size: int, tpl_path: str | Path):
        tpl = _load_template(tpl_path)
        surf = render_template_to_surface(tpl)
        super().__init__(x, y, surf, True)
        self.speed = 150


class NPC(Entity):
    def __init__(
        self,
        x: float,
        y: float,
        tile_size: int,
        tpl_path: str | Path,
        prompt: str = "Offer a wizardly insight.",
    ):
        tpl = _load_template(tpl_path)
        surf = render_template_to_surface(tpl)
        super().__init__(x, y, surf, True)
        self.dialogue_prompt = prompt
