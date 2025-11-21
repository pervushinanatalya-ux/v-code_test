"""Pygame front-end for the ball mixing sandbox powered by logic.py."""

from __future__ import annotations

import colorsys
import math
import random
from typing import Tuple

import pygame

from logic import Ball, Color, DeleteZone, GameLogic

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
WINDOW_SIZE: Tuple[int, int] = (1100, 720)
BACKGROUND_COLOR = (250, 250, 250)
PLAYFIELD_COLOR = (255, 255, 255)
INVENTORY_COLOR = (240, 244, 248)
HUD_TEXT_COLOR = (35, 35, 40)
FPS = 60
INITIAL_BALLS = 35
BALL_RADIUS_RANGE = (12.0, 24.0)
BALL_SPEED_RANGE = (50.0, 150.0)
MOUSE_INFLUENCE_RADIUS = 80
SPIT_SPEED_MULTIPLIER = 8.0
INVENTORY_STRIP_HEIGHT = 130.0
DELETE_ZONE_SIZE = (150, 90)
DELETE_ZONE_COLOR = (255, 210, 210)
DELETE_ZONE_BORDER = (206, 106, 106)


def _random_color() -> Color:
    hue = random.random()
    saturation = random.uniform(0.65, 1.0)
    value = random.uniform(0.7, 1.0)
    return colorsys.hsv_to_rgb(hue, saturation, value)


def _random_velocity() -> Tuple[float, float]:
    angle = random.uniform(0.0, math.tau)
    speed = random.uniform(*BALL_SPEED_RANGE)
    return math.cos(angle) * speed, math.sin(angle) * speed


def _spawn_initial_balls(game: GameLogic, play_area_height: float) -> None:
    for _ in range(INITIAL_BALLS):
        position = (
            random.uniform(0.0, game.width),
            random.uniform(0.0, play_area_height),
        )
        velocity = _random_velocity()
        radius = random.uniform(*BALL_RADIUS_RANGE)
        game.spawn_ball(position, velocity, radius, _random_color())


def _color_to_rgb(color: Color) -> Tuple[int, int, int]:
    return tuple(int(max(0.0, min(1.0, c)) * 255) for c in color)


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Color Vacuum Playground")
    screen = pygame.display.set_mode(WINDOW_SIZE)
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Segoe UI", 17)

    play_area_height = WINDOW_SIZE[1] - INVENTORY_STRIP_HEIGHT
    delete_zone = DeleteZone(
        WINDOW_SIZE[0] - DELETE_ZONE_SIZE[0] - 24,
        play_area_height - DELETE_ZONE_SIZE[1] - 24,
        WINDOW_SIZE[0] - 24,
        play_area_height - 24,
    )

    game = GameLogic(
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        delete_zone=delete_zone,
        inventory_strip_height=INVENTORY_STRIP_HEIGHT,
        inventory_slot_size=56.0,
        inventory_padding=20.0,
        refill_on_remove=True,
    )

    _spawn_initial_balls(game, play_area_height)

    running = True
    last_mouse_position = pygame.mouse.get_pos()

    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                _spit_ball(game, pygame.mouse.get_pos(), last_mouse_position, dt)

        mouse_pos = pygame.mouse.get_pos()
        mouse_buttons = pygame.mouse.get_pressed(num_buttons=3)
        if mouse_buttons[0]:
            game.suck_ball(mouse_pos, MOUSE_INFLUENCE_RADIUS)

        game.update(dt)

        _draw_scene(screen, font, game, delete_zone, mouse_pos, play_area_height)
        pygame.display.flip()

        last_mouse_position = mouse_pos

    pygame.quit()


def _spit_ball(
    game: GameLogic,
    mouse_pos: Tuple[int, int],
    last_mouse_pos: Tuple[int, int],
    dt: float,
) -> None:
    if dt <= 0:
        dt = 1.0 / FPS

    vx = (mouse_pos[0] - last_mouse_pos[0]) / dt / SPIT_SPEED_MULTIPLIER
    vy = (mouse_pos[1] - last_mouse_pos[1]) / dt / SPIT_SPEED_MULTIPLIER
    game.spit_ball(mouse_pos, (vx, vy))


def _draw_scene(
    screen: pygame.Surface,
    font: pygame.font.Font,
    game: GameLogic,
    delete_zone: DeleteZone,
    mouse_pos: Tuple[int, int],
    play_area_height: float,
) -> None:
    screen.fill(BACKGROUND_COLOR)

    # Play area
    play_rect = pygame.Rect(0, 0, game.width, play_area_height)
    pygame.draw.rect(screen, PLAYFIELD_COLOR, play_rect)

    # Delete zone
    delete_rect = pygame.Rect(
        delete_zone.min_x,
        delete_zone.min_y,
        delete_zone.max_x - delete_zone.min_x,
        delete_zone.max_y - delete_zone.min_y,
    )
    pygame.draw.rect(screen, DELETE_ZONE_COLOR, delete_rect, border_radius=10)
    pygame.draw.rect(screen, DELETE_ZONE_BORDER, delete_rect, width=3, border_radius=10)

    # Inventory strip
    inventory_rect = pygame.Rect(0, play_area_height, game.width, game.height - play_area_height)
    pygame.draw.rect(screen, INVENTORY_COLOR, inventory_rect)

    active_balls = game.balls()

    # Balls on playfield
    for ball in active_balls:
        pygame.draw.circle(
            screen,
            _color_to_rgb(ball.color),
            (int(ball.position.x), int(ball.position.y)),
            int(ball.radius),
        )

    # Inventory balls (use same drawing for clarity)
    for ball in game.inventory:
        pygame.draw.circle(
            screen,
            _color_to_rgb(ball.color),
            (int(ball.position.x), int(ball.position.y)),
            int(ball.radius),
        )

    # Mouse influence radius
    pygame.draw.circle(
        screen,
        (180, 190, 220),
        mouse_pos,
        MOUSE_INFLUENCE_RADIUS,
        width=1,
    )

    _draw_hud(screen, font, active_balls, len(game.inventory), delete_zone, play_area_height)


def _draw_hud(
    screen: pygame.Surface,
    font: pygame.font.Font,
    active_balls: Tuple[Ball, ...],
    inventory_count: int,
    delete_zone: DeleteZone,
    play_area_height: float,
) -> None:
    lines = [
        "Left click / hold — vacuum balls",
        "Right click — spit last stored ball",
        "Esc or Q — exit",
        f"Active balls: {len(active_balls)}",
        f"Inventory: {inventory_count}",
    ]

    for idx, text in enumerate(lines):
        surface = font.render(text, True, HUD_TEXT_COLOR)
        screen.blit(surface, (16, 16 + idx * 20))

    label = font.render("Delete zone", True, DELETE_ZONE_BORDER)
    screen.blit(label, (delete_zone.min_x + 8, delete_zone.min_y + 8))

    inv_label = font.render("Inventory strip", True, HUD_TEXT_COLOR)
    screen.blit(inv_label, (16, play_area_height + 10))


if __name__ == "__main__":
    main()
