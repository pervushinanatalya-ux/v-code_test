"""Core game logic for managing and simulating colored balls.

The module is UI-agnostic and focuses solely on state updates and rules:
    * movement across the playfield,
    * vacuuming balls into the inventory with the mouse,
    * spitting balls back onto the field,
    * color mixing whenever balls touch (no physical repulsion),
    * optional delete zone that removes balls crossing it,
    * a capture strip along the bottom for stored balls,
    * automatic refilling so the playfield never runs dry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Tuple
import colorsys
import math
import itertools
import random

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
    stored_velocity: Vec2 = field(default_factory=lambda: Vec2(0.0, 0.0))


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
    """Encapsulates simulation, capture strip layout, and auto-refill logic."""

    def __init__(
        self,
        width: float,
        height: float,
        delete_zone: Optional[DeleteZone] = None,
        *,
        inventory_strip_height: float = 100.0,
        inventory_slot_size: float = 48.0,
        inventory_padding: float = 16.0,
        refill_on_remove: bool = True,
        refill_generator: Optional[
            Callable[
                ["GameLogic"],
                Tuple[Tuple[float, float], Tuple[float, float], float, Color],
            ]
        ] = None,
        rng_seed: Optional[int] = None,
    ) -> None:
        self.width = width
        self.height = height
        self.delete_zone = delete_zone
        self.inventory = Inventory()
        self._balls: List[Ball] = []
        self._id_counter = itertools.count()
        self.inventory_strip_height = max(0.0, inventory_strip_height)
        self.inventory_slot_size = max(1.0, inventory_slot_size)
        self.inventory_padding = max(0.0, inventory_padding)
        self.refill_on_remove = refill_on_remove
        self._refill_generator = refill_generator
        self._rng = random.Random(rng_seed)

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
        ball.stored_velocity = ball.velocity
        self._balls.append(ball)
        return ball

    def update(self, dt: float) -> None:
        """Advance the simulation by `dt` seconds."""
        for ball in list(self._balls):
            self._move_ball(ball, dt)
            if self.delete_zone and self.delete_zone.contains(ball.position):
                self._balls.remove(ball)
                self._spawn_replacement()

        self._apply_color_mixing()

    def suck_ball(self, pointer: Tuple[float, float], influence_radius: float) -> Optional[Ball]:
        """Vacuum the closest ball within `influence_radius` of the pointer."""
        target = self._find_ball(pointer, influence_radius)
        if not target:
            return None

        self._balls.remove(target)
        target.stored_velocity = target.velocity
        self.inventory.add(target)
        self._refresh_inventory_layout()
        self._spawn_replacement()
        return target

    def spit_ball(
        self,
        position: Tuple[float, float],
        velocity: Optional[Tuple[float, float]] = None,
    ) -> Optional[Ball]:
        """Eject the most recently stored ball back onto the playfield."""
        ball = self.inventory.pop_last()
        if not ball:
            return None

        self._refresh_inventory_layout()
        chosen_velocity = (
            Vec2(*velocity)
            if velocity is not None
            else (
                ball.stored_velocity
                if ball.stored_velocity.length() > 0.0
                else self._random_velocity()
            )
        )
        ball.position = Vec2(*position)
        ball.velocity = chosen_velocity
        ball.stored_velocity = chosen_velocity
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
        ball.stored_velocity = ball.velocity

        # Wrap-around edges keep gameplay dense without extra rules.
        ball.position = Vec2(
            ball.position.x % self.width,
            ball.position.y % self._play_area_height(),
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

    def _refresh_inventory_layout(self) -> None:
        if self.inventory_strip_height <= 0:
            return

        for idx, ball in enumerate(self.inventory):
            self._place_ball_in_inventory(ball, idx)

    def _place_ball_in_inventory(self, ball: Ball, slot_index: int) -> None:
        slot_position = self._inventory_slot_position(slot_index)
        ball.position = slot_position
        ball.velocity = Vec2(0.0, 0.0)

    def _inventory_slot_position(self, slot_index: int) -> Vec2:
        safe_width = max(1.0, self.width)
        usable_width = max(1.0, safe_width - 2 * min(self.inventory_padding, safe_width / 2))
        columns = max(1, int(usable_width // self.inventory_slot_size))
        slot_width = usable_width / columns
        gutter_offset = (safe_width - usable_width) / 2

        col = slot_index % columns
        row = slot_index // columns

        x = gutter_offset + slot_width * (col + 0.5)
        slot_height = min(self.inventory_slot_size, max(1.0, self.inventory_strip_height))
        strip_top = max(0.0, self.height - self.inventory_strip_height)
        max_offset = max(0.0, self.inventory_strip_height - slot_height / 2)
        row_offset = slot_height * (row + 0.5)
        y = strip_top + min(row_offset, max_offset if max_offset > 0 else slot_height / 2)
        y = min(self.height - slot_height / 2, y)

        clamped_x = min(safe_width - slot_width / 2, max(slot_width / 2, x))
        return Vec2(clamped_x, y)

    def _spawn_replacement(self) -> None:
        if not self.refill_on_remove:
            return

        spawn_spec = (
            self._refill_generator(self)
            if self._refill_generator
            else self._default_spawn_spec()
        )

        position, velocity, radius, color = spawn_spec
        self.spawn_ball(position, velocity, radius, color)

    def _random_velocity(self, speed_range: Tuple[float, float] = (40.0, 140.0)) -> Vec2:
        angle = self._rng.uniform(0.0, 2 * math.pi)
        speed = self._rng.uniform(*speed_range)
        return Vec2(math.cos(angle) * speed, math.sin(angle) * speed)

    def _default_spawn_spec(
        self,
    ) -> Tuple[Tuple[float, float], Tuple[float, float], float, Color]:
        x = self._rng.uniform(0.0, max(1.0, self.width))
        y = self._rng.uniform(0.0, self._play_area_height())
        radius = self._rng.uniform(12.0, 26.0)
        velocity_vec = self._random_velocity()
        color = self._random_color()
        return ((x, y), (velocity_vec.x, velocity_vec.y), radius, color)

    def _random_color(self) -> Color:
        hue = self._rng.random()
        saturation = self._rng.uniform(0.65, 1.0)
        value = self._rng.uniform(0.7, 1.0)
        return colorsys.hsv_to_rgb(hue, saturation, value)

    def _play_area_height(self) -> float:
        return max(1.0, self.height - self.inventory_strip_height)

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

