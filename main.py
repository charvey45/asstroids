import math
import random
from dataclasses import dataclass, field

import pygame


WIDTH = 960
HEIGHT = 720
FPS = 60
BACKGROUND = (6, 10, 18)
FOREGROUND = (232, 240, 255)
ACCENT = (255, 191, 105)
WARNING = (255, 107, 107)

SHIP_TURN_SPEED = 220
SHIP_ACCELERATION = 320
SHIP_FRICTION = 0.992
SHIP_RADIUS = 16
BULLET_SPEED = 520
BULLET_LIFETIME = 1.1
BULLET_COOLDOWN = 0.2
RESPAWN_INVULN = 2.0
ASTEROID_SPEED = {
    3: (35, 70),
    2: (55, 95),
    1: (80, 125),
}
ASTEROID_RADIUS = {
    3: 52,
    2: 30,
    1: 18,
}
SCORE_VALUES = {
    3: 20,
    2: 50,
    1: 100,
}


@dataclass
class Bullet:
    position: pygame.Vector2
    velocity: pygame.Vector2
    ttl: float = BULLET_LIFETIME


@dataclass
class Asteroid:
    position: pygame.Vector2
    velocity: pygame.Vector2
    size: int
    angle: float
    spin: float
    points: list[pygame.Vector2] = field(default_factory=list)

    @property
    def radius(self) -> float:
        return ASTEROID_RADIUS[self.size]


@dataclass
class Ship:
    position: pygame.Vector2
    velocity: pygame.Vector2
    angle: float = -90
    lives: int = 3
    cooldown: float = 0.0
    invulnerability: float = RESPAWN_INVULN


def wrap_position(position: pygame.Vector2) -> None:
    position.x %= WIDTH
    position.y %= HEIGHT


def heading_vector(angle: float) -> pygame.Vector2:
    radians = math.radians(angle)
    return pygame.Vector2(math.cos(radians), math.sin(radians))


def random_asteroid_shape(radius: float) -> list[pygame.Vector2]:
    points: list[pygame.Vector2] = []
    corners = random.randint(9, 13)
    for index in range(corners):
        angle = index * (360 / corners)
        distance = radius * random.uniform(0.72, 1.08)
        points.append(heading_vector(angle) * distance)
    return points


def spawn_asteroid(size: int, avoid: pygame.Vector2 | None = None) -> Asteroid:
    while True:
        position = pygame.Vector2(
            random.uniform(0, WIDTH),
            random.uniform(0, HEIGHT),
        )
        if avoid is None or position.distance_to(avoid) > 180:
            break

    speed_low, speed_high = ASTEROID_SPEED[size]
    velocity = heading_vector(random.uniform(0, 360)) * random.uniform(speed_low, speed_high)
    return Asteroid(
        position=position,
        velocity=velocity,
        size=size,
        angle=random.uniform(0, 360),
        spin=random.uniform(-35, 35),
        points=random_asteroid_shape(ASTEROID_RADIUS[size]),
    )


def asteroid_screen_points(asteroid: Asteroid) -> list[tuple[float, float]]:
    transformed = []
    for point in asteroid.points:
        rotated = point.rotate(asteroid.angle)
        transformed.append((asteroid.position.x + rotated.x, asteroid.position.y + rotated.y))
    return transformed


def ship_points(ship: Ship) -> list[tuple[float, float]]:
    nose = heading_vector(ship.angle) * 20
    rear_left = heading_vector(ship.angle + 140) * 16
    rear_right = heading_vector(ship.angle - 140) * 16
    center = ship.position
    return [
        (center.x + nose.x, center.y + nose.y),
        (center.x + rear_left.x, center.y + rear_left.y),
        (center.x + rear_right.x, center.y + rear_right.y),
    ]


def draw_wrapped_circle(surface: pygame.Surface, color: tuple[int, int, int], position: pygame.Vector2, radius: int) -> None:
    for dx in (-WIDTH, 0, WIDTH):
        for dy in (-HEIGHT, 0, HEIGHT):
            pygame.draw.circle(
                surface,
                color,
                (position.x + dx, position.y + dy),
                radius,
            )


def draw_wrapped_polygon(surface: pygame.Surface, color: tuple[int, int, int], points: list[tuple[float, float]], anchor: pygame.Vector2) -> None:
    for dx in (-WIDTH, 0, WIDTH):
        for dy in (-HEIGHT, 0, HEIGHT):
            shifted = [(x + dx, y + dy) for x, y in points]
            shifted_anchor = pygame.Vector2(anchor.x + dx, anchor.y + dy)
            if -80 <= shifted_anchor.x <= WIDTH + 80 and -80 <= shifted_anchor.y <= HEIGHT + 80:
                pygame.draw.polygon(surface, color, shifted, width=2)


def distance_with_wrap(a: pygame.Vector2, b: pygame.Vector2) -> float:
    dx = min(abs(a.x - b.x), WIDTH - abs(a.x - b.x))
    dy = min(abs(a.y - b.y), HEIGHT - abs(a.y - b.y))
    return math.hypot(dx, dy)


def create_level(level: int, ship_position: pygame.Vector2) -> list[Asteroid]:
    count = min(4 + level, 10)
    return [spawn_asteroid(3, avoid=ship_position) for _ in range(count)]


def reset_ship() -> Ship:
    return Ship(
        position=pygame.Vector2(WIDTH / 2, HEIGHT / 2),
        velocity=pygame.Vector2(),
    )


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Astroids")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    hud_font = pygame.font.SysFont("consolas", 24)
    title_font = pygame.font.SysFont("consolas", 36, bold=True)

    ship = reset_ship()
    bullets: list[Bullet] = []
    level = 1
    score = 0
    asteroids = create_level(level, ship.position)
    running = True
    game_over = False

    while running:
        dt = clock.tick(FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and game_over and event.key == pygame.K_r:
                ship = reset_ship()
                bullets.clear()
                level = 1
                score = 0
                asteroids = create_level(level, ship.position)
                game_over = False

        keys = pygame.key.get_pressed()

        if not game_over:
            if keys[pygame.K_LEFT]:
                ship.angle -= SHIP_TURN_SPEED * dt
            if keys[pygame.K_RIGHT]:
                ship.angle += SHIP_TURN_SPEED * dt
            if keys[pygame.K_UP]:
                ship.velocity += heading_vector(ship.angle) * SHIP_ACCELERATION * dt

            ship.velocity *= SHIP_FRICTION
            ship.position += ship.velocity * dt
            wrap_position(ship.position)
            ship.cooldown = max(0.0, ship.cooldown - dt)
            ship.invulnerability = max(0.0, ship.invulnerability - dt)

            if keys[pygame.K_SPACE] and ship.cooldown == 0.0:
                direction = heading_vector(ship.angle)
                bullets.append(
                    Bullet(
                        position=ship.position + direction * 20,
                        velocity=ship.velocity + direction * BULLET_SPEED,
                    )
                )
                ship.cooldown = BULLET_COOLDOWN

            for bullet in bullets[:]:
                bullet.position += bullet.velocity * dt
                wrap_position(bullet.position)
                bullet.ttl -= dt
                if bullet.ttl <= 0:
                    bullets.remove(bullet)

            for asteroid in asteroids:
                asteroid.position += asteroid.velocity * dt
                asteroid.angle += asteroid.spin * dt
                wrap_position(asteroid.position)

            spawned: list[Asteroid] = []
            for bullet in bullets[:]:
                hit = next(
                    (
                        asteroid
                        for asteroid in asteroids
                        if distance_with_wrap(bullet.position, asteroid.position) < asteroid.radius
                    ),
                    None,
                )
                if hit is None:
                    continue

                bullets.remove(bullet)
                asteroids.remove(hit)
                score += SCORE_VALUES[hit.size]

                if hit.size > 1:
                    for direction in (-30, 30):
                        velocity = hit.velocity.rotate(direction)
                        if velocity.length() == 0:
                            velocity = heading_vector(random.uniform(0, 360))
                        velocity.scale_to_length(random.uniform(*ASTEROID_SPEED[hit.size - 1]))
                        spawned.append(
                            Asteroid(
                                position=hit.position.copy(),
                                velocity=velocity,
                                size=hit.size - 1,
                                angle=random.uniform(0, 360),
                                spin=random.uniform(-55, 55),
                                points=random_asteroid_shape(ASTEROID_RADIUS[hit.size - 1]),
                            )
                        )

            asteroids.extend(spawned)

            if ship.invulnerability == 0.0:
                for asteroid in asteroids:
                    if distance_with_wrap(ship.position, asteroid.position) < asteroid.radius + SHIP_RADIUS - 3:
                        ship.lives -= 1
                        if ship.lives <= 0:
                            game_over = True
                        else:
                            preserved_lives = ship.lives
                            ship = reset_ship()
                            ship.lives = preserved_lives
                        bullets.clear()
                        break

            if not asteroids and not game_over:
                level += 1
                asteroids = create_level(level, ship.position)

        screen.fill(BACKGROUND)

        for asteroid in asteroids:
            draw_wrapped_polygon(screen, FOREGROUND, asteroid_screen_points(asteroid), asteroid.position)

        for bullet in bullets:
            draw_wrapped_circle(screen, ACCENT, bullet.position, 3)

        if not game_over:
            flicker = ship.invulnerability > 0 and int(pygame.time.get_ticks() / 120) % 2 == 0
            if not flicker:
                draw_wrapped_polygon(screen, FOREGROUND, ship_points(ship), ship.position)

            if keys[pygame.K_UP]:
                flame = [
                    (
                        ship.position.x + heading_vector(ship.angle + 175).x * 10,
                        ship.position.y + heading_vector(ship.angle + 175).y * 10,
                    ),
                    (
                        ship.position.x + heading_vector(ship.angle + 180).x * random.uniform(18, 26),
                        ship.position.y + heading_vector(ship.angle + 180).y * random.uniform(18, 26),
                    ),
                    (
                        ship.position.x + heading_vector(ship.angle - 175).x * 10,
                        ship.position.y + heading_vector(ship.angle - 175).y * 10,
                    ),
                ]
                pygame.draw.polygon(screen, ACCENT, flame, width=2)

        score_text = hud_font.render(f"Score {score:05d}", True, FOREGROUND)
        lives_text = hud_font.render(f"Lives {ship.lives}", True, FOREGROUND)
        level_text = hud_font.render(f"Level {level}", True, FOREGROUND)
        help_text = hud_font.render("Arrows move, Space fires, Esc quits", True, (170, 181, 205))

        screen.blit(score_text, (24, 20))
        screen.blit(lives_text, (24, 50))
        screen.blit(level_text, (24, 80))
        screen.blit(help_text, (24, HEIGHT - 42))

        if game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((2, 4, 8, 170))
            screen.blit(overlay, (0, 0))

            title = title_font.render("Game Over", True, WARNING)
            retry = hud_font.render("Press R to restart", True, FOREGROUND)
            final_score = hud_font.render(f"Final score: {score}", True, FOREGROUND)

            screen.blit(title, title.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 40)))
            screen.blit(final_score, final_score.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 4)))
            screen.blit(retry, retry.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 44)))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
