"""Entity primitives used by the demo game."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

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
    """Player entity hydrated from a JSON definition."""

    def __init__(self, x: float, y: float, tile_size: int, tpl_path: str | Path):
        tpl_path = Path(tpl_path)
        with open(tpl_path, "r", encoding="utf-8") as fp:
            definition = json.load(fp)

        sprite_template = _load_template(tpl_path.parent / definition.get("sprite_template", "player_chibi.json"))
        surf = render_template_to_surface(sprite_template)
        super().__init__(x, y, surf, True)

        stats = definition.get("stats", {})
        self.max_health = int(stats.get("health", 100))
        self.health = self.max_health
        self.max_mana = int(stats.get("mana", 120))
        self.mana = self.max_mana
        speed_tiles = float(stats.get("speed_tiles_per_second", 3.5))
        self.move_speed = speed_tiles * tile_size

        self.inventory = definition.get("inventory", {"slots": 10, "items": []})
        self._spell_ids: List[str] = list(definition.get("spells", []))
        self.spells: List[Spell] = []

    def load_spells(self, templates_dir: Path) -> None:
        """Populate the player's spellbook from YAML definitions."""

        spells_path = templates_dir / "spells" / "spells.yaml"
        if not spells_path.exists():
            self.spells = []
            return

        with open(spells_path, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}

        definitions = {entry["id"]: entry for entry in data.get("spells", []) if "id" in entry}
        spellbook: List[Spell] = []
        for spell_id in self._spell_ids:
            entry = definitions.get(spell_id)
            if not entry:
                continue
            spellbook.append(Spell(
                id=entry["id"],
                mana_cost=int(entry.get("mana_cost", 0)),
                speed=float(entry.get("speed", 0.0)),
                radius=float(entry.get("radius", 0.0)),
                damage=int(entry.get("damage", 0)),
                sprite_layers=list(entry.get("sprite_layers", [])),
                sound=str(entry.get("sound", "")),
                description=str(entry.get("description", "")),
            ))
        self.spells = spellbook


@dataclass(slots=True)
class Spell:
    id: str
    mana_cost: int
    speed: float
    radius: float
    damage: int
    sprite_layers: List[str]
    sound: str
    description: str


class NPC(Entity):
    def __init__(
        self,
        x: float,
        y: float,
        tpl_path: str | Path,
        prompt: str = "Offer a wizardly insight.",
        personality: str = "neutral",
        school: str = "arcane",
        dialogue: Dict[str, object] | None = None,
    ):
        tpl = _load_template(tpl_path)
        surf = render_template_to_surface(tpl)
        super().__init__(x, y, surf, True)
        self.dialogue_prompt = prompt
        self.personality = personality
        self.school = school
        self.dialogue_tree: Dict[str, object] = dialogue or {}
        self._fallback_lines: List[str] = self._collect_lines(self.dialogue_tree)

    @staticmethod
    def _collect_lines(dialogue: Dict[str, object]) -> List[str]:
        lines: List[str] = []
        greeting = dialogue.get("greeting") if dialogue else None
        if isinstance(greeting, list):
            lines.extend(str(item) for item in greeting if item)
        elif isinstance(greeting, str):
            lines.append(greeting)

        if dialogue:
            branch = dialogue.get("branch")
            if isinstance(branch, dict):
                lines.extend(str(val) for val in branch.values() if val)
            elif isinstance(branch, list):
                lines.extend(str(item) for item in branch if item)
            elif isinstance(branch, str):
                lines.append(branch)

            for key in ("combat_trigger", "reward_hint"):
                value = dialogue.get(key)
                if isinstance(value, list):
                    lines.extend(str(item) for item in value if item)
                elif isinstance(value, dict):
                    lines.extend(str(item) for item in value.values() if item)
                elif isinstance(value, str) and value:
                    lines.append(value)

        return lines or [
            "We duel with insight long before the first spark of mana.",
            "Even a whisper of focus can bend the weave of battle.",
        ]

    @property
    def fallback_lines(self) -> List[str]:
        return self._fallback_lines
