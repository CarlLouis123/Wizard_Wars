"""Entity primitives and lightweight actor logic used by the demo game."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import yaml

import pygame as pg

from .proc_templates import render_template_to_surface

Vector2 = pg.math.Vector2


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


class AnimatedEntity(Entity):
    """Entity with a simple frame-based animation loop."""

    def __init__(
        self,
        x: float,
        y: float,
        frames: Sequence[pg.Surface],
        frame_duration: float = 0.4,
        solid: bool = True,
    ) -> None:
        if not frames:
            raise ValueError("AnimatedEntity requires at least one frame")
        first_frame = frames[0].convert_alpha()
        super().__init__(x, y, first_frame, solid)
        self._frames = [frame.convert_alpha() for frame in frames]
        self._frame_duration = max(0.05, float(frame_duration))
        self._frame_index = 0
        self._frame_timer = random.random() * self._frame_duration

    def update_animation(self, dt: float) -> None:
        if len(self._frames) <= 1:
            return
        self._frame_timer += dt
        while self._frame_timer >= self._frame_duration:
            self._frame_timer -= self._frame_duration
            self._frame_index = (self._frame_index + 1) % len(self._frames)
            self.sprite = self._frames[self._frame_index]


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

        turn_speed = float(stats.get("turn_speed_deg_per_second", 140.0))
        initial_angle = float(stats.get("initial_angle_deg", 90.0))
        self.turn_speed = math.radians(turn_speed)
        self.angle = math.radians(initial_angle)
        self.fov = math.radians(float(stats.get("fov_degrees", 80.0)))
        self.eye_height = float(stats.get("eye_height_pixels", tile_size * 0.75))
        self.step_height = float(stats.get("step_height_pixels", tile_size * 0.25))

        self.inventory = definition.get("inventory", {"slots": 10, "items": []})
        self._spell_ids: List[str] = list(definition.get("spells", []))
        self.spells: List[Spell] = []

    # ------------------------------------------------------------------ vectors
    def forward_vector(self) -> Tuple[float, float]:
        """Return a normalized vector representing the facing direction."""

        return math.cos(self.angle), math.sin(self.angle)

    def right_vector(self) -> Tuple[float, float]:
        """Return a normalized vector pointing to the player's right."""

        fx, fy = self.forward_vector()
        return -fy, fx

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


class NPC(AnimatedEntity):
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
        frames = self._build_idle_frames(surf)
        super().__init__(x, y, frames, frame_duration=0.55, solid=True)
        self.dialogue_prompt = prompt
        self.personality = personality
        self.school = school
        self.dialogue_tree: Dict[str, object] = dialogue or {}
        self._fallback_lines: List[str] = self._collect_lines(self.dialogue_tree)
        self.interaction_radius = 1.8

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

    @staticmethod
    def _build_idle_frames(base: pg.Surface) -> List[pg.Surface]:
        """Create subtle idle animation frames by tinting the base sprite."""

        frames: List[pg.Surface] = []
        tint_cycles = ((12, 18, 28), (0, 0, 0), (-18, -12, -6))
        for r, g, b in tint_cycles:
            frame = pg.Surface(base.get_size(), pg.SRCALPHA)
            frame.blit(base, (0, 0))
            if r or g or b:
                tint = pg.Surface(base.get_size(), pg.SRCALPHA)
                tint.fill((max(0, r), max(0, g), max(0, b), 0))
                if r < 0 or g < 0 or b < 0:
                    tint.fill((abs(r), abs(g), abs(b), 0))
                    frame.blit(tint, (0, 0), special_flags=pg.BLEND_RGBA_SUB)
                else:
                    frame.blit(tint, (0, 0), special_flags=pg.BLEND_RGBA_ADD)
            frames.append(frame)
        return frames or [base]

    def update(self, dt: float) -> None:
        self.update_animation(dt)

    @property
    def fallback_lines(self) -> List[str]:
        return self._fallback_lines


class Wildlife(AnimatedEntity):
    """Ambient critters that wander around open tiles."""

    def __init__(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        frames = self._make_frames(color)
        super().__init__(x, y, frames, frame_duration=0.35, solid=False)
        self.direction = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if self.direction.length_squared() < 1e-5:
            self.direction.update(1.0, 0.0)
        else:
            self.direction = self.direction.normalize()
        self.speed = random.uniform(0.4, 0.8)
        self._wander_timer = random.uniform(2.0, 5.0)

    @staticmethod
    def _make_frames(color: tuple[int, int, int]) -> List[pg.Surface]:
        frames: List[pg.Surface] = []
        size = 28
        for scale in (1.0, 0.92, 1.05):
            frame = pg.Surface((size, size), pg.SRCALPHA)
            radius = int(size * 0.35 * scale)
            pg.draw.circle(frame, color, (size // 2, size // 2), radius)
            eye_color = (255, 255, 255)
            pg.draw.circle(frame, eye_color, (size // 2 - 4, size // 2 - 2), 3)
            pg.draw.circle(frame, eye_color, (size // 2 + 4, size // 2 - 2), 3)
            frames.append(frame)
        return frames

    def update(self, dt: float, world: "WorldMap") -> None:  # type: ignore[name-defined]
        self.update_animation(dt)
        self._wander_timer -= dt
        if self._wander_timer <= 0.0:
            self._wander_timer = random.uniform(2.0, 4.5)
            self.direction = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
            if self.direction.length_squared() < 1e-5:
                self.direction.update(1.0, 0.0)
            else:
                self.direction = self.direction.normalize()

        step = self.direction * self.speed * dt
        new_pos = Vector2(self.x, self.y) + step
        if not world.is_wall(new_pos.x, new_pos.y):
            self.x, self.y = new_pos.x, new_pos.y
        else:
            self.direction *= -1


class PatrollingEnemy(AnimatedEntity):
    """Enemy that patrols between waypoints and spars with the player."""

    def __init__(
        self,
        x: float,
        y: float,
        frames: Sequence[pg.Surface],
        patrol_points: Sequence[Tuple[float, float]],
        speed: float = 1.6,
        health: float = 35.0,
        attack_damage: float = 10.0,
        aggro_range: float = 6.0,
        attack_range: float = 1.2,
        attack_cooldown: float = 1.4,
    ) -> None:
        super().__init__(x, y, frames, frame_duration=0.3, solid=True)
        self._patrol_points = [Vector2(point) for point in patrol_points] or [Vector2(x, y)]
        self._patrol_index = 0
        self.speed = speed
        self.health = health
        self.attack_damage = attack_damage
        self.aggro_range = aggro_range
        self.attack_range = attack_range
        self._attack_cooldown = attack_cooldown
        self._cooldown_timer = random.uniform(0.0, attack_cooldown)
        self._state = "patrol"

    def update(
        self,
        dt: float,
        world: "WorldMap",  # type: ignore[name-defined]
        player_position: Tuple[float, float],
    ) -> bool:
        self.update_animation(dt)
        pos = Vector2(self.x, self.y)
        player_vec = Vector2(player_position)
        to_player = player_vec - pos
        distance_to_player = to_player.length()

        if distance_to_player < self.aggro_range:
            self._state = "chase"
        elif distance_to_player > self.aggro_range * 1.6:
            self._state = "patrol"

        target = player_vec if self._state == "chase" else self._current_patrol_target()
        if target:
            step = self._steer_towards(pos, target, dt, world)
            self.x, self.y = step.x, step.y

        self._cooldown_timer -= dt
        if distance_to_player <= self.attack_range and self._cooldown_timer <= 0.0:
            self._cooldown_timer = self._attack_cooldown
            return True
        return False

    def _current_patrol_target(self) -> Vector2:
        if not self._patrol_points:
            return Vector2(self.x, self.y)
        target = self._patrol_points[self._patrol_index]
        if Vector2(self.x, self.y).distance_to(target) < 0.2:
            self._patrol_index = (self._patrol_index + 1) % len(self._patrol_points)
            target = self._patrol_points[self._patrol_index]
        return target

    def _steer_towards(
        self,
        pos: Vector2,
        target: Vector2,
        dt: float,
        world: "WorldMap",  # type: ignore[name-defined]
    ) -> Vector2:
        if dt <= 0.0:
            return pos
        direction = (target - pos)
        if direction.length_squared() < 1e-6:
            return pos
        direction = direction.normalize()
        proposed = pos + direction * self.speed * dt
        if world.is_wall(proposed.x, proposed.y):
            # simple avoidance: try strafe
            side = Vector2(-direction.y, direction.x)
            proposed_side = pos + side * self.speed * dt * 0.7
            if not world.is_wall(proposed_side.x, proposed_side.y):
                proposed = proposed_side
            else:
                proposed = pos
        return proposed


class Collectible(Entity):
    """Collectible items that can be stored in the player's inventory."""

    def __init__(
        self,
        x: float,
        y: float,
        item_id: str,
        display_name: str,
        description: str,
        effect: Dict[str, object],
        color: tuple[int, int, int],
    ) -> None:
        sprite = self._build_sprite(color)
        super().__init__(x, y, sprite, False)
        self.item_id = item_id
        self.display_name = display_name
        self.description = description
        self.effect = effect

    @staticmethod
    def _build_sprite(color: tuple[int, int, int]) -> pg.Surface:
        surf = pg.Surface((24, 24), pg.SRCALPHA)
        pg.draw.circle(surf, color, (12, 12), 10)
        pg.draw.circle(surf, (255, 255, 255, 120), (8, 8), 4)
        return surf

    def apply_effect(self, player_stats: "PlayerStats") -> None:  # type: ignore[name-defined]
        effect_type = str(self.effect.get("type", ""))
        if effect_type == "heal":
            amount = float(self.effect.get("amount", 0))
            player_stats.restore_health(amount)
        elif effect_type == "mana":
            amount = float(self.effect.get("amount", 0))
            player_stats.restore_mana(amount)


class PlayerStats:
    """Simple container tracking the player's combat state."""

    def __init__(self, max_health: float = 100.0, max_mana: float = 60.0) -> None:
        self.max_health = max_health
        self.health = max_health
        self.max_mana = max_mana
        self.mana = max_mana

    def take_damage(self, amount: float) -> None:
        self.health = max(0.0, self.health - amount)

    def restore_health(self, amount: float) -> None:
        if amount <= 0:
            return
        self.health = min(self.max_health, self.health + amount)

    def restore_mana(self, amount: float) -> None:
        if amount <= 0:
            return
        self.mana = min(self.max_mana, self.mana + amount)


class Inventory:
    """Basic finite inventory to showcase loot collection."""

    def __init__(self, slots: int = 8):
        self.slots = slots
        self.items: List[str] = []

    def add_item(self, item_name: str) -> bool:
        if len(self.items) >= self.slots:
            return False
        self.items.append(item_name)
        return True

    def remove_item(self, item_name: str) -> bool:
        if item_name not in self.items:
            return False
        self.items.remove(item_name)
        return True

