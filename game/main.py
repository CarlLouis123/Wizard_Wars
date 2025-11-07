"""Entry point for the production-grade Wizard Wars first-person prototype."""

from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import pygame as pg
import yaml

from engine.audio import AudioManager
from engine.dialogue import DialogueEngine
from engine.entities import (
    Collectible,
    Inventory,
    NPC,
    PatrollingEnemy,
    PlayerStats,
    Wildlife,
)
from engine.proc_templates import render_template_to_surface
from engine.player import MovementInput, PlayerController
from engine.render import RaycastRenderer
from engine.terrain import TerrainSystem
from engine.world import TileDefinition, WorldMap
from engine.weather import WeatherSystem
import settings as S


MAP_LAYOUT = (
    "111111111111111",
    "1A0000000000001",
    "100011110000001",
    "103011210000001",
    "100010010000001",
    "100010010000001",
    "100000000000001",
    "100000040000001",
    "100000000000001",
    "122222222222221",
    "1B0000000000001",
    "111111111111111",
)

TILESET = {
    "0": TileDefinition((60, 60, 70), solid=False),
    "1": TileDefinition((210, 210, 220), solid=True),
    "2": TileDefinition((140, 180, 255), solid=True),
    "3": TileDefinition((220, 120, 150), solid=True),
    "4": TileDefinition((200, 160, 80), solid=True),
    "A": TileDefinition((60, 120, 220), solid=True),
    "B": TileDefinition((180, 90, 220), solid=True),
}


@dataclass
class GameConfig:
    resolution: tuple[int, int]
    fps_limit: int
    move_speed: float
    mouse_sensitivity: float


class GameApp:
    """High-level application wrapper providing lifecycle management."""

    def __init__(self, config: GameConfig) -> None:
        pg.init()
        pg.font.init()
        pg.display.set_caption("Wizard Wars :: Prototype 3D Engine")
        self.screen = pg.display.set_mode(config.resolution, pg.RESIZABLE)
        self.clock = pg.time.Clock()

        self.config = config
        self.world = WorldMap(MAP_LAYOUT, TILESET, light_position=(7.5, 3.5), light_intensity=2.8)
        self.terrain = TerrainSystem(seed=2718)
        self.player = PlayerController(
            position=(2.5, 2.5),
            yaw=0.0,
            move_speed=config.move_speed,
            mouse_sensitivity=config.mouse_sensitivity,
        )
        self.renderer = RaycastRenderer(self.world, *config.resolution, terrain=self.terrain)
        self._movement = MovementInput()
        self._mouse_captured = False
        self._toggle_mouse_lock(True)

        self.font = pg.font.SysFont("arial", 18)
        self.dialogue_font = pg.font.SysFont("georgia", 20)
        self.player_stats = PlayerStats(max_health=120.0, max_mana=80.0)
        self.inventory = Inventory(slots=10)
        self.dialogue_engine = DialogueEngine(use_gemini=getattr(S, "USE_GEMINI_DIALOGUE", False))

        self.templates_dir = Path(__file__).resolve().parent / "content" / "templates"
        self.npcs = self._spawn_npcs()
        self.dialogue_engine.prewarm(npc.dialogue_prompt for npc in self.npcs)
        self.wildlife = self._spawn_wildlife()
        self.enemies = self._spawn_enemies()
        self.collectibles = self._spawn_collectibles()

        audio_dir = Path(__file__).resolve().parent / "content" / "audio"
        self.audio = AudioManager(audio_dir)
        self.weather = WeatherSystem(config.resolution)
        self.save_path = Path(__file__).resolve().parent / "savegame.json"

        self._map_cache: Dict[int, pg.Surface] = {}
        self._minimap_scale = 8
        self._worldmap_scale = 22
        self._show_world_map = False

        self._dialogue_text = ""
        self._dialogue_timer = 0.0
        self._pickup_message = ""
        self._pickup_timer = 0.0
        self._attack_cooldown = 0.0
        self._pending_attack = False
        self._player_attack_damage = 22.0
        self._attack_range = 1.6

    # ----------------------------------------------------------------- lifecycle
    def run(self) -> None:
        try:
            while True:
                dt = self.clock.tick(self.config.fps_limit) / 1000.0
                if not self._process_events():
                    break
                self._update(dt)
                self._draw()
                pg.display.flip()
                fps = self.clock.get_fps()
                pg.display.set_caption(f"Wizard Wars :: FPS {fps:5.1f}")
        finally:
            self.audio.shutdown()

    # ------------------------------------------------------------------- internals
    def _process_events(self) -> bool:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return False
            if event.type == pg.VIDEORESIZE:
                self.screen = pg.display.set_mode(event.size, pg.RESIZABLE)
                self.renderer.resize(*event.size)
                self.weather.resize(*event.size)
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                if self._mouse_captured:
                    self._toggle_mouse_lock(False)
                else:
                    return False
            if event.type == pg.KEYDOWN and event.key == pg.K_m:
                self._show_world_map = not self._show_world_map
            if event.type == pg.KEYDOWN and event.key == pg.K_F5:
                self._save_game()
            if event.type == pg.KEYDOWN and event.key == pg.K_F9:
                self._load_game()
            if event.type == pg.KEYDOWN and event.key == pg.K_e:
                self._interact()
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and self._mouse_captured:
                self._pending_attack = True
            if event.type == pg.MOUSEMOTION and self._mouse_captured:
                dx, dy = event.rel
                self.player.handle_mouse(dx, dy)
        return True

    def _toggle_mouse_lock(self, enable: bool) -> None:
        self._mouse_captured = enable
        pg.mouse.set_visible(not enable)
        pg.event.set_grab(enable)
        pg.mouse.get_rel()

    def _update(self, dt: float) -> None:
        keys = pg.key.get_pressed()
        self._movement.forward = float(keys[pg.K_w]) - float(keys[pg.K_s])
        self._movement.right = float(keys[pg.K_d]) - float(keys[pg.K_a])
        self.player.update(dt, self._movement, self.world)
        self.renderer.update_time(dt)
        self.weather.update(dt)
        self._apply_weather_to_renderer()

        is_moving = self.player.velocity.length_squared() > 0.01
        surface_type = self._player_surface_type()
        self.audio.update(dt, is_moving, surface_type, self.weather.current_state)
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        self._update_npcs(dt)
        self._update_wildlife(dt)
        self._update_enemies(dt)
        self._update_collectibles()
        self._update_dialogue(dt)
        self._pending_attack = False

    def _apply_weather_to_renderer(self) -> None:
        base_distance = 24.0
        base_ambient = self.renderer.ambient_light
        state = self.weather.current_state
        intensity = self.weather.intensity

        if state == "fog":
            self.renderer.view_distance = max(10.0, base_distance * (1.0 - 0.5 * intensity))
            self.renderer.ambient_light = min(0.7, base_ambient + 0.1 * intensity)
        elif state == "rain":
            self.renderer.view_distance = max(14.0, base_distance * (1.0 - 0.25 * intensity))
            self.renderer.ambient_light = max(0.08, base_ambient - 0.05 * intensity)
        elif state == "wind":
            self.renderer.view_distance = base_distance * (1.0 + 0.05 * intensity)
            self.renderer.ambient_light = base_ambient
        else:
            self.renderer.view_distance = base_distance
            self.renderer.ambient_light = base_ambient

    def _player_surface_type(self) -> str:
        tile = self.world.tile(int(self.player.position.x), int(self.player.position.y))
        return "hard" if tile.solid else "soft"

    def _draw(self) -> None:
        sprites = tuple(self.npcs + self.wildlife + self.enemies + self.collectibles)
        self.renderer.render(self.screen, self.player, sprites)
        self.weather.draw(self.screen)
        self._draw_hud()

    # ------------------------------------------------------------------ spawners
    def _spawn_npcs(self) -> List[NPC]:
        npc_config_path = self.templates_dir / "npc_wizard.yaml"
        if not npc_config_path.exists():
            return []
        with open(npc_config_path, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}

        archetypes = {
            entry.get("id"): entry
            for entry in data.get("npc_archetypes", [])
            if isinstance(entry, dict) and entry.get("id")
        }

        spawn_rings = [ring for ring in data.get("spawn_rings", []) if isinstance(ring, dict)]
        center = pg.math.Vector2(self.world.width / 2 + 0.5, self.world.height / 2 + 0.5)
        npcs: List[NPC] = []
        for ring in spawn_rings:
            radius = float(ring.get("radius_tiles", 6.0))
            count = max(1, int(ring.get("count", 1)))
            archetype_ids = [aid for aid in ring.get("archetypes", []) if aid in archetypes]
            if not archetype_ids:
                continue
            for i in range(count):
                archetype = archetypes.get(random.choice(archetype_ids))
                if not archetype:
                    continue
                angle = (math.tau / count) * i + random.uniform(-0.1, 0.1)
                position = center + pg.math.Vector2(math.cos(angle), math.sin(angle)) * radius
                position = self._find_open_position(position, search_radius=1.8)
                sprite_template = archetype.get("sprite_template", "npc_chibi.json")
                prompt = archetype.get("prompt", "Offer a wizardly insight.")
                npc = NPC(
                    position.x,
                    position.y,
                    self.templates_dir / sprite_template,
                    prompt=prompt,
                    personality=str(archetype.get("personality", "neutral")),
                    school=str(archetype.get("school", "arcane")),
                    dialogue=archetype.get("dialogue"),
                )
                npcs.append(npc)
        return npcs

    def _spawn_wildlife(self) -> List[Wildlife]:
        colors = [
            (168, 214, 120),
            (220, 205, 150),
            (140, 192, 255),
            (200, 166, 220),
        ]
        wildlife: List[Wildlife] = []
        for _ in range(6):
            position = self._find_open_position(search_radius=10.0)
            wildlife.append(Wildlife(position.x, position.y, random.choice(colors)))
        return wildlife

    def _spawn_enemies(self) -> List[PatrollingEnemy]:
        frames = self._load_sprite_frames("wizard_ember.json")
        fallback_frames = frames or [self._make_colored_blob((220, 120, 150))]
        enemies: List[PatrollingEnemy] = []
        patrol_centers = [
            pg.math.Vector2(6.5, 6.5),
            pg.math.Vector2(9.5, 3.5),
            pg.math.Vector2(3.5, 9.5),
        ]
        for center in patrol_centers:
            center = self._find_open_position(center, search_radius=1.5)
            points = [
                center + pg.math.Vector2(math.cos(math.tau * t / 4), math.sin(math.tau * t / 4)) * 1.8
                for t in range(4)
            ]
            enemy = PatrollingEnemy(
                center.x,
                center.y,
                frames if frames else fallback_frames,
                patrol_points=[(p.x, p.y) for p in points],
                speed=1.5,
                health=60.0,
                attack_damage=12.0,
                aggro_range=6.5,
                attack_range=1.4,
                attack_cooldown=1.8,
            )
            enemies.append(enemy)
        return enemies

    def _spawn_collectibles(self) -> List[Collectible]:
        items = [
            {
                "id": "healing_herb",
                "name": "Healing Herb",
                "description": "Restores a touch of vitality.",
                "effect": {"type": "heal", "amount": 18},
                "color": (120, 200, 140),
            },
            {
                "id": "crystal_vial",
                "name": "Crystal Vial",
                "description": "Shimmers with latent mana.",
                "effect": {"type": "mana", "amount": 20},
                "color": (120, 180, 255),
            },
            {
                "id": "ember_shard",
                "name": "Ember Shard",
                "description": "A spark captured from a pyromancer's flare.",
                "effect": {"type": "heal", "amount": 10},
                "color": (255, 120, 80),
            },
        ]
        collectibles: List[Collectible] = []
        for item in items:
            position = self._find_open_position(search_radius=8.0)
            collectibles.append(
                Collectible(
                    position.x,
                    position.y,
                    item["id"],
                    item["name"],
                    item["description"],
                    item["effect"],
                    item["color"],
                )
            )
        return collectibles

    def _find_open_position(
        self,
        center: pg.math.Vector2 | None = None,
        search_radius: float = 4.0,
        attempts: int = 12,
    ) -> pg.math.Vector2:
        if center is None:
            center = pg.math.Vector2(self.world.width / 2 + 0.5, self.world.height / 2 + 0.5)
        for _ in range(attempts):
            angle = random.uniform(0, math.tau)
            distance = random.uniform(0.8, search_radius)
            candidate = center + pg.math.Vector2(math.cos(angle), math.sin(angle)) * distance
            if not self.world.is_wall(candidate.x, candidate.y):
                return candidate
        return center

    # ------------------------------------------------------------------- updates
    def _update_npcs(self, dt: float) -> None:
        for npc in self.npcs:
            npc.update(dt)

    def _update_wildlife(self, dt: float) -> None:
        for critter in self.wildlife:
            critter.update(dt, self.world)

    def _update_enemies(self, dt: float) -> None:
        player_pos = (self.player.position.x, self.player.position.y)
        damage_taken = 0.0
        for enemy in list(self.enemies):
            did_attack = enemy.update(dt, self.world, player_pos)
            if did_attack:
                damage_taken += enemy.attack_damage
            if enemy.health <= 0:
                self.enemies.remove(enemy)
        if damage_taken > 0:
            self.player_stats.take_damage(damage_taken)
        if self._pending_attack and self._attack_cooldown <= 0.0:
            self._perform_player_attack()

    def _perform_player_attack(self) -> None:
        player_vec = pg.math.Vector2(self.player.position)
        target = None
        target_distance = float("inf")
        for enemy in self.enemies:
            distance = player_vec.distance_to(pg.math.Vector2(enemy.x, enemy.y))
            if distance <= self._attack_range and distance < target_distance:
                target = enemy
                target_distance = distance
        if target is None:
            return
        target.health -= self._player_attack_damage
        self._attack_cooldown = 0.6
        self._pickup_message = f"Struck {target_distance:0.1f}m foe for {self._player_attack_damage:.0f}!"
        self._pickup_timer = 1.0

    def _update_collectibles(self) -> None:
        player_vec = pg.math.Vector2(self.player.position)
        for collectible in list(self.collectibles):
            if player_vec.distance_to(pg.math.Vector2(collectible.x, collectible.y)) <= 1.1:
                if self.inventory.add_item(collectible.display_name):
                    collectible.apply_effect(self.player_stats)
                    self._pickup_message = f"Picked up {collectible.display_name}!"
                    self.collectibles.remove(collectible)
                    self._pickup_timer = 2.4
                else:
                    self._pickup_message = "Inventory full!"
                    self._pickup_timer = 2.0

    def _update_dialogue(self, dt: float) -> None:
        if self._dialogue_timer > 0.0:
            self._dialogue_timer -= dt
            if self._dialogue_timer <= 0.0:
                self._dialogue_text = ""
        if self._pickup_timer > 0.0:
            self._pickup_timer -= dt
            if self._pickup_timer <= 0.0:
                self._pickup_message = ""

    # ---------------------------------------------------------------- interactions
    def _interact(self) -> None:
        player_vec = pg.math.Vector2(self.player.position)
        nearest = None
        nearest_distance = float("inf")
        for npc in self.npcs:
            distance = player_vec.distance_to(pg.math.Vector2(npc.x, npc.y))
            if distance <= npc.interaction_radius and distance < nearest_distance:
                nearest = npc
                nearest_distance = distance
        if nearest is None:
            return
        line = self.dialogue_engine.npc_line(nearest.dialogue_prompt, nearest.fallback_lines)
        self._dialogue_text = f"{nearest.personality.title()} mage: {line}"
        self._dialogue_timer = 7.0

    # ---------------------------------------------------------------------- hud
    def _draw_hud(self) -> None:
        health_ratio = 0.0
        if self.player_stats.max_health > 0:
            health_ratio = self.player_stats.health / self.player_stats.max_health
        bar_rect = pg.Rect(20, 20, 220, 18)
        pg.draw.rect(self.screen, (30, 32, 40), bar_rect.inflate(4, 4), border_radius=6)
        inner = bar_rect.copy()
        inner.width = max(0, int(bar_rect.width * health_ratio))
        pg.draw.rect(self.screen, (200, 60, 70), inner, border_radius=5)
        health_text = self.font.render(
            f"HP {int(self.player_stats.health)}/{int(self.player_stats.max_health)}",
            True,
            (235, 235, 235),
        )
        self.screen.blit(health_text, (bar_rect.x, bar_rect.y - 20))

        inv_string = ", ".join(self.inventory.items) if self.inventory.items else "Empty"
        inv_text = self.font.render(
            f"Inventory ({len(self.inventory.items)}/{self.inventory.slots}): {inv_string}",
            True,
            (220, 215, 190),
        )
        self.screen.blit(inv_text, (20, 54))

        if self._pickup_message:
            pickup = self.font.render(self._pickup_message, True, (250, 240, 180))
            self.screen.blit(pickup, (20, 78))

        if self._dialogue_text:
            self._draw_dialogue_box(self._dialogue_text)

        if self.player_stats.health <= 0:
            banner = self.dialogue_font.render("You have fallen! Press ESC to exit.", True, (255, 120, 120))
            rect = banner.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
            self.screen.blit(banner, rect)

        self._draw_weather_indicator()
        self._draw_minimap()
        if self._show_world_map:
            self._draw_world_map()

    def _draw_dialogue_box(self, text: str) -> None:
        max_width = self.screen.get_width() - 80
        lines = self._wrap_text(text, max_width, self.dialogue_font)
        if not lines:
            return
        line_height = self.dialogue_font.get_linesize()
        box_height = line_height * len(lines) + 20
        box_rect = pg.Rect(40, self.screen.get_height() - box_height - 40, max_width, box_height)
        overlay = pg.Surface(box_rect.size, pg.SRCALPHA)
        overlay.fill((10, 12, 24, 200))
        pg.draw.rect(overlay, (120, 150, 255, 220), overlay.get_rect(), width=2, border_radius=12)
        self.screen.blit(overlay, box_rect)
        y = box_rect.top + 10
        for line in lines:
            rendered = self.dialogue_font.render(line, True, (230, 232, 250))
            self.screen.blit(rendered, (box_rect.left + 12, y))
            y += line_height

    def _draw_minimap(self) -> None:
        surface = self._get_map_surface(self._minimap_scale).copy()
        scale = self._minimap_scale
        px = self.player.position.x * scale
        py = self.player.position.y * scale
        yaw = self.player.yaw
        arrow = [
            (px + math.cos(yaw) * 10, py + math.sin(yaw) * 10),
            (px + math.cos(yaw + 2.6) * 6, py + math.sin(yaw + 2.6) * 6),
            (px + math.cos(yaw - 2.6) * 6, py + math.sin(yaw - 2.6) * 6),
        ]
        pg.draw.polygon(surface, (255, 230, 150), arrow)
        pg.draw.circle(surface, (30, 30, 32), (int(px), int(py)), 3)

        frame = pg.Surface((surface.get_width() + 12, surface.get_height() + 12), pg.SRCALPHA)
        frame.fill((12, 14, 24, 210))
        frame.blit(surface, (6, 6))
        pg.draw.rect(frame, (120, 140, 190, 220), frame.get_rect(), width=2, border_radius=10)
        rect = frame.get_rect()
        rect.topright = (self.screen.get_width() - 20, 20)
        self.screen.blit(frame, rect)

    def _draw_world_map(self) -> None:
        overlay = pg.Surface(self.screen.get_size(), pg.SRCALPHA)
        overlay.fill((6, 8, 16, 200))
        self.screen.blit(overlay, (0, 0))

        map_surface = self._get_map_surface(self._worldmap_scale).copy()
        scale = self._worldmap_scale
        px = self.player.position.x * scale
        py = self.player.position.y * scale
        yaw = self.player.yaw
        arrow = [
            (px + math.cos(yaw) * 16, py + math.sin(yaw) * 16),
            (px + math.cos(yaw + 2.5) * 10, py + math.sin(yaw + 2.5) * 10),
            (px + math.cos(yaw - 2.5) * 10, py + math.sin(yaw - 2.5) * 10),
        ]
        pg.draw.polygon(map_surface, (255, 230, 160), arrow)
        pg.draw.circle(map_surface, (30, 30, 32), (int(px), int(py)), 4)

        panel = pg.Surface((map_surface.get_width() + 60, map_surface.get_height() + 60), pg.SRCALPHA)
        panel.fill((18, 20, 32, 235))
        panel.blit(map_surface, (30, 30))
        panel_rect = panel.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
        pg.draw.rect(panel, (120, 150, 220, 230), panel.get_rect(), width=2, border_radius=18)
        self.screen.blit(panel, panel_rect)

        caption = self.dialogue_font.render("World Map", True, (235, 240, 255))
        caption_rect = caption.get_rect(midtop=(panel_rect.centerx, panel_rect.top + 16))
        self.screen.blit(caption, caption_rect)

        hint = self.font.render("Press M to close", True, (220, 220, 220))
        hint_rect = hint.get_rect(midtop=(panel_rect.centerx, panel_rect.bottom + 12))
        self.screen.blit(hint, hint_rect)

    def _get_map_surface(self, scale: int) -> pg.Surface:
        cached = self._map_cache.get(scale)
        if cached is not None:
            return cached

        width = self.world.width * scale
        height = self.world.height * scale
        surface = pg.Surface((width, height), pg.SRCALPHA)
        for y in range(self.world.height):
            for x in range(self.world.width):
                tile = self.world.tile(x, y)
                color = tile.color if tile.solid else (70, 90, 60)
                rect = pg.Rect(x * scale, y * scale, scale, scale)
                pg.draw.rect(surface, color, rect)
        self._map_cache[scale] = surface
        return surface

    def _draw_weather_indicator(self) -> None:
        label = f"Weather: {self.weather.current_state.title()}"
        status = self.font.render(label, True, (220, 225, 240))
        rect = status.get_rect()
        rect.bottomleft = (20, self.screen.get_height() - 20)
        backdrop = pg.Surface((rect.width + 16, rect.height + 12), pg.SRCALPHA)
        backdrop.fill((10, 12, 18, 200))
        backdrop.blit(status, (8, 6))
        pg.draw.rect(backdrop, (90, 110, 160, 220), backdrop.get_rect(), width=1, border_radius=8)
        panel_rect = backdrop.get_rect(bottomleft=(20, self.screen.get_height() - 20))
        self.screen.blit(backdrop, panel_rect)

    def _save_game(self) -> None:
        data = {
            "player": {
                "position": [self.player.position.x, self.player.position.y],
                "yaw": self.player.yaw,
            },
            "stats": {
                "health": self.player_stats.health,
                "mana": self.player_stats.mana,
            },
            "inventory": list(self.inventory.items),
            "weather": {
                "state": self.weather.current_state,
                "intensity": self.weather.intensity,
                "timer": self.weather.transition_timer,
                "next_transition": self.weather.next_transition,
            },
            "time_of_day": self.renderer.time_of_day,
        }
        try:
            with open(self.save_path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)
        except OSError as exc:
            self._pickup_message = f"Save failed: {exc.strerror or exc}"[:60]
            self._pickup_timer = 2.5
            return
        self._pickup_message = "Game saved."
        self._pickup_timer = 2.0

    def _load_game(self) -> None:
        if not self.save_path.exists():
            self._pickup_message = "No save data found."
            self._pickup_timer = 2.5
            return
        try:
            with open(self.save_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, json.JSONDecodeError) as exc:
            self._pickup_message = f"Load failed: {exc}"[:60]
            self._pickup_timer = 2.5
            return

        player_data = data.get("player", {})
        position = player_data.get("position")
        if isinstance(position, list) and len(position) == 2:
            self.player.position.update(float(position[0]), float(position[1]))
        yaw = player_data.get("yaw")
        if isinstance(yaw, (int, float)):
            self.player.yaw = float(yaw)
            self.player._refresh_vectors()

        stats = data.get("stats", {})
        health = stats.get("health")
        mana = stats.get("mana")
        if isinstance(health, (int, float)):
            self.player_stats.health = max(0.0, min(self.player_stats.max_health, float(health)))
        if isinstance(mana, (int, float)):
            self.player_stats.mana = max(0.0, min(self.player_stats.max_mana, float(mana)))

        inventory = data.get("inventory")
        if isinstance(inventory, list):
            self.inventory.items = [str(item) for item in inventory][: self.inventory.slots]

        weather = data.get("weather", {})
        state = weather.get("state")
        if isinstance(state, str):
            self.weather.current_state = state
        for key in ("intensity", "timer", "next_transition"):
            value = weather.get(key)
            if isinstance(value, (int, float)):
                setattr(self.weather, key if key != "timer" else "transition_timer", float(value))
        self.weather._particles.clear()

        time_of_day = data.get("time_of_day")
        if isinstance(time_of_day, (int, float)):
            self.renderer.time_of_day = float(time_of_day) % 1.0

        self._apply_weather_to_renderer()
        self._pickup_message = "Save loaded."
        self._pickup_timer = 2.5

    @staticmethod
    def _wrap_text(text: str, max_width: int, font: pg.font.Font) -> List[str]:
        words = text.split()
        if not words:
            return []
        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    # ---------------------------------------------------------------- utilities
    def _load_sprite_frames(self, template_name: str) -> List[pg.Surface]:
        template_path = self.templates_dir / template_name
        if not template_path.exists():
            return []
        with open(template_path, "r", encoding="utf-8") as fp:
            template = json.load(fp)
        surface = render_template_to_surface(template)
        return NPC._build_idle_frames(surface)

    @staticmethod
    def _make_colored_blob(color: tuple[int, int, int]) -> pg.Surface:
        surface = pg.Surface((32, 32), pg.SRCALPHA)
        pg.draw.circle(surface, color, (16, 16), 14)
        pg.draw.circle(surface, (255, 255, 255, 120), (12, 12), 5)
        return surface


def build_config() -> GameConfig:
    resolution = (getattr(S, "WINDOW_W", 960), getattr(S, "WINDOW_H", 540))
    fps_limit = getattr(S, "FPS", 60)
    base_speed_tiles = getattr(S, "PLAYER_BASE_SPEED_TILES", 3.5)
    move_speed = base_speed_tiles * 0.9
    mouse_sensitivity = 0.0022
    return GameConfig(resolution, fps_limit, move_speed, mouse_sensitivity)


def main(argv: Iterable[str] | None = None) -> int:
    config = build_config()
    app = GameApp(config)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
