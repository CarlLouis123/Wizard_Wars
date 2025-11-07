"""Player controller logic for the first-person renderer."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame as pg

from .world import WorldMap

Vector2 = pg.math.Vector2


@dataclass
class MovementInput:
    forward: float = 0.0
    right: float = 0.0


class PlayerController:
    """Handle player movement, camera orientation and physics."""

    def __init__(
        self,
        position: tuple[float, float] = (2.5, 2.5),
        yaw: float = 0.0,
        move_speed: float = 4.0,
        acceleration: float = 18.0,
        friction: float = 10.0,
        radius: float = 0.28,
        fov_degrees: float = 75.0,
        mouse_sensitivity: float = 0.0022,
    ) -> None:
        self.position = Vector2(position)
        self.velocity = Vector2()
        self.yaw = yaw
        self.pitch = 0.0
        self.move_speed = move_speed
        self.acceleration = acceleration
        self.friction = friction
        self.radius = radius
        self.fov = math.radians(fov_degrees)
        self.mouse_sensitivity = mouse_sensitivity

        self.direction = Vector2(math.cos(self.yaw), math.sin(self.yaw))
        self.right = Vector2(-self.direction.y, self.direction.x)
        self.camera_plane = self.right * math.tan(self.fov / 2)

    # ---------------------------------------------------------------- orientation
    def handle_mouse(self, dx: float, dy: float) -> None:
        self.yaw += dx * self.mouse_sensitivity
        self.pitch -= dy * self.mouse_sensitivity
        self.pitch = max(-0.45, min(0.45, self.pitch))
        self._refresh_vectors()

    def _refresh_vectors(self) -> None:
        self.direction.update(math.cos(self.yaw), math.sin(self.yaw))
        self.right.update(-self.direction.y, self.direction.x)
        self.camera_plane = self.right * math.tan(self.fov / 2)

    # ------------------------------------------------------------------ movement
    def update(self, dt: float, user_input: MovementInput, world: WorldMap) -> None:
        if dt <= 0.0:
            return

        desired = self.direction * user_input.forward + self.right * user_input.right
        if desired.length_squared() > 0.0:
            desired = desired.normalize() * self.move_speed
        else:
            desired = Vector2()

        # Accelerate toward desired velocity and apply friction for smoothing
        velocity_delta = desired - self.velocity
        accel_step = self.acceleration * dt
        if velocity_delta.length_squared() > accel_step * accel_step:
            velocity_delta.scale_to_length(accel_step)
        self.velocity += velocity_delta

        # Apply drag to naturally slow down when no input is provided
        drag = min(1.0, self.friction * dt)
        self.velocity -= self.velocity * drag * 0.2

        proposed = self.position + self.velocity * dt
        clipped = world.clip_movement(self.position, proposed, self.radius)
        if not math.isclose(clipped.x, proposed.x, abs_tol=1e-4):
            self.velocity.x = 0.0
        if not math.isclose(clipped.y, proposed.y, abs_tol=1e-4):
            self.velocity.y = 0.0
        self.position = clipped

    # ------------------------------------------------------------------- helpers
    @property
    def camera_height_offset(self) -> float:
        """Vertical offset for head tilt (used as simple view bob)."""

        return self.pitch
