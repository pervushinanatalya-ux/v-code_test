"""Core game logic for managing and simulating colored balls.

The module is UI-agnostic and focuses solely on state updates and rules:
    * movement across the playfield,
    * vacuuming balls into the inventory with the mouse,
    * spitting balls back onto the field,
    * color mixing whenever balls touch (no physical repulsion),
    * optional delete zone that removes balls crossing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple
import colorsys
import math
import itertools

Color = Tuple[float, float, float]  # RGB, normalized [0.0, 1.0]


@dataclass
class Vec2:
    """Simple 2D vector utility."""

    x: float
    y: float

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.y * scalar)

    def length(self) -> float:
        return math.hypot(self.x, self.y)


@dataclass
class Ball:
    """Represents a single ball on the playfield."""

    id: int
    position: Vec2
    velocity: Vec2
    radius: float
    color: Color


@dataclass
class Inventory:
    """Stores balls captured by the mouse vacuum."""

    _balls: List[Ball] = field(default_factory=list)

    def add(self, ball: Ball) -> None:
        self._balls.append(ball)

    def pop_last(self) -> Optional[Ball]:
        return self._balls.pop() if self._balls else None

    def __len__(self) -> int:
        return len(self._balls)

    def __iter__(self) -> Iterable[Ball]:
        return iter(self._balls)


@dataclass
class DeleteZone:
    """Axis-aligned rectangle that deletes balls entering it."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def contains(self, position: Vec2) -> bool:
        return (
            self.min_x <= position.x <= self.max_x
            and self.min_y <= position.y <= self.max_y
        )


class GameLogic:
    """Encapsulates state updates and interactions for the ball playground."""

    def __init__(
        self,
        width: float,
        height: float,
        delete_zone: Optional[DeleteZone] = None,
    ) -> None:
        self.width = width
        self.height = height
        self.delete_zone = delete_zone
        self.inventory = Inventory()
        self._balls: List[Ball] = []
        self._id_counter = itertools.count()

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def spawn_ball(
        self,
        position: Tuple[float, float],
        velocity: Tuple[float, float],
        radius: float,
        color: Color,
    ) -> Ball:
        """Create and register a new ball on the playfield."""
        ball = Ball(
            id=next(self._id_counter),
            position=Vec2(*position),
            velocity=Vec2(*velocity),
            radius=radius,
            color=color,
        )
        self._balls.append(ball)
        return ball

    def update(self, dt: float) -> None:
        """Advance the simulation by `dt` seconds."""
        for ball in list(self._balls):
            self._move_ball(ball, dt)
            if self.delete_zone and self.delete_zone.contains(ball.position):
                self._balls.remove(ball)

        self._apply_color_mixing()

    def suck_ball(self, pointer: Tuple[float, float], influence_radius: float) -> Optional[Ball]:
        """Vacuum the closest ball within `influence_radius` of the pointer."""
        target = self._find_ball(pointer, influence_radius)
        if not target:
            return None

        self._balls.remove(target)
        self.inventory.add(target)
        return target

    def spit_ball(
        self,
        position: Tuple[float, float],
        velocity: Tuple[float, float],
    ) -> Optional[Ball]:
        """Eject the most recently stored ball back onto the playfield."""
        ball = self.inventory.pop_last()
        if not ball:
            return None

        ball.position = Vec2(*position)
        ball.velocity = Vec2(*velocity)
        self._balls.append(ball)
        return ball

    def balls(self) -> Iterable[Ball]:
        """Expose current balls without allowing external mutation."""
        return tuple(self._balls)

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _move_ball(self, ball: Ball, dt: float) -> None:
        ball.position = ball.position + ball.velocity * dt

        # Wrap-around edges keep gameplay dense without extra rules.
        ball.position = Vec2(
            ball.position.x % self.width,
            ball.position.y % self.height,
        )

    def _apply_color_mixing(self) -> None:
        """Combine colors for every touching pair of balls."""
        for idx, ball_a in enumerate(self._balls):
            for ball_b in self._balls[idx + 1 :]:
                if self._are_touching(ball_a, ball_b):
                    mixed = self._mix_colors(ball_a.color, ball_b.color)
                    ball_a.color = mixed
                    ball_b.color = mixed

    @staticmethod
    def _are_touching(ball_a: Ball, ball_b: Ball) -> bool:
        distance = (ball_a.position - ball_b.position).length()
        return distance <= (ball_a.radius + ball_b.radius)

    def _find_ball(
        self,
        pointer: Tuple[float, float],
        influence_radius: float,
    ) -> Optional[Ball]:
        pointer_vec = Vec2(*pointer)
        candidates = [
            (ball, (ball.position - pointer_vec).length() - ball.radius)
            for ball in self._balls
        ]
        candidates = [
            (ball, distance_to_surface)
            for ball, distance_to_surface in candidates
            if distance_to_surface <= influence_radius
        ]

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[1])
        return candidates[0][0]

    @staticmethod
    def _mix_colors(color_a: Color, color_b: Color) -> Color:
        """Blend two RGB colors with saturation boost to avoid dull whites."""
        h1, s1, v1 = colorsys.rgb_to_hsv(*color_a)
        h2, s2, v2 = colorsys.rgb_to_hsv(*color_b)

        # Average hue along the shorter arc to create vivid transitions.
        hue_diff = ((h2 - h1 + 0.5) % 1.0) - 0.5
        mixed_h = (h1 + hue_diff * 0.5) % 1.0

        # Favor higher saturation/value to keep mixes punchy.
        mixed_s = min(1.0, (s1 + s2) / 2 + 0.2 * abs(s1 - s2))
        mixed_v = min(1.0, max(v1, v2) * 0.9 + (v1 + v2) / 2 * 0.1)

        # If the result drifts too close to white, push saturation slightly.
        if mixed_s < 0.15 and mixed_v > 0.85:
            mixed_s = 0.25
            mixed_v = max(0.7, mixed_v - 0.1)

        return colorsys.hsv_to_rgb(mixed_h, mixed_s, mixed_v)


__all__ = [
    "Ball",
    "Color",
    "DeleteZone",
    "GameLogic",
    "Inventory",
    "Vec2",
]

