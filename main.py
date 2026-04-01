import json
import math
import random
from array import array
from dataclasses import dataclass, field
from pathlib import Path

import pygame


WIDTH = 960
HEIGHT = 720
FPS = 60
BACKGROUND = (6, 10, 18)
FOREGROUND = (232, 240, 255)
ACCENT = (255, 191, 105)
WARNING = (255, 107, 107)
MUTED = (170, 181, 205)
SAVE_PATH = Path(__file__).with_name(".asteroids-save.json")

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
PARTICLE_DRAG = 0.96
DEFAULT_VOLUME = 0.10
VOLUME_STEP = 0.05
MIN_VOLUME = 0.0
MAX_VOLUME = 1.0


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


@dataclass
class Particle:
    position: pygame.Vector2
    velocity: pygame.Vector2
    ttl: float
    max_ttl: float
    color: tuple[int, int, int]
    radius: float


@dataclass
class SoundBank:
    shoot: pygame.mixer.Sound | None
    hit: pygame.mixer.Sound | None
    ship_hit: pygame.mixer.Sound | None


@dataclass
class SoundSettings:
    enabled: bool = True
    volume: float = DEFAULT_VOLUME


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


def build_tone(
    frequency: float,
    duration: float,
    *,
    volume: float,
    waveform: str = "sine",
    sweep: float = 0.0,
    noise_mix: float = 0.0,
) -> pygame.mixer.Sound | None:
    mixer_settings = pygame.mixer.get_init()
    if mixer_settings is None:
        return None

    sample_rate, _, channels = mixer_settings
    sample_count = max(1, int(duration * sample_rate))
    samples = array("h")
    phase = 0.0

    for sample_index in range(sample_count):
        progress = sample_index / sample_count
        current_frequency = max(40.0, frequency + sweep * progress)
        phase += (2 * math.pi * current_frequency) / sample_rate

        if waveform == "square":
            tone = 1.0 if math.sin(phase) >= 0.0 else -1.0
        elif waveform == "triangle":
            tone = (2.0 / math.pi) * math.asin(math.sin(phase))
        elif waveform == "noise":
            tone = random.uniform(-1.0, 1.0)
        else:
            tone = math.sin(phase)

        if noise_mix:
            tone = (tone * (1.0 - noise_mix)) + (random.uniform(-1.0, 1.0) * noise_mix)

        envelope = (1.0 - progress) ** 1.8
        value = max(-1.0, min(1.0, tone * volume * envelope))
        sample = int(value * 32767)
        samples.append(sample)

    if channels == 2:
        stereo_samples = array("h")
        for sample in samples:
            stereo_samples.append(sample)
            stereo_samples.append(sample)
        return pygame.mixer.Sound(buffer=stereo_samples.tobytes())

    return pygame.mixer.Sound(buffer=samples.tobytes())


def build_sound_bank() -> SoundBank:
    return SoundBank(
        shoot=build_tone(720, 0.09, volume=0.18, waveform="square", sweep=-240),
        hit=build_tone(160, 0.2, volume=0.28, waveform="triangle", sweep=-70, noise_mix=0.2),
        ship_hit=build_tone(110, 0.45, volume=0.32, waveform="noise", sweep=-60, noise_mix=0.55),
    )


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def apply_sound_settings(sound_bank: SoundBank, settings: SoundSettings) -> None:
    effective_volume = settings.volume if settings.enabled else 0.0
    for sound in (sound_bank.shoot, sound_bank.hit, sound_bank.ship_hit):
        if sound is not None:
            sound.set_volume(effective_volume)


def play_sound(sound: pygame.mixer.Sound | None) -> None:
    if sound is not None:
        sound.play()


def adjust_volume(sound_bank: SoundBank, settings: SoundSettings, delta: float) -> None:
    settings.volume = clamp(settings.volume + delta, MIN_VOLUME, MAX_VOLUME)
    apply_sound_settings(sound_bank, settings)


def toggle_sound(sound_bank: SoundBank, settings: SoundSettings) -> None:
    settings.enabled = not settings.enabled
    apply_sound_settings(sound_bank, settings)


def sound_status_text(settings: SoundSettings) -> str:
    if not settings.enabled:
        return f"Sound Off ({round(settings.volume * 100):d}%)"
    return f"Sound On ({round(settings.volume * 100):d}%)"


def emit_particles(
    position: pygame.Vector2,
    count: int,
    color: tuple[int, int, int],
    *,
    speed_range: tuple[float, float],
    ttl_range: tuple[float, float],
    radius_range: tuple[float, float],
) -> list[Particle]:
    particles: list[Particle] = []
    for _ in range(count):
        lifetime = random.uniform(*ttl_range)
        particles.append(
            Particle(
                position=position.copy(),
                velocity=heading_vector(random.uniform(0, 360)) * random.uniform(*speed_range),
                ttl=lifetime,
                max_ttl=lifetime,
                color=color,
                radius=random.uniform(*radius_range),
            )
        )
    return particles


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


def create_session() -> tuple[Ship, list[Bullet], list[Particle], int, int, list[Asteroid]]:
    ship = reset_ship()
    level = 1
    score = 0
    asteroids = create_level(level, ship.position)
    return ship, [], [], level, score, asteroids


def read_save_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if isinstance(payload, dict):
        return payload
    return {}


def load_save_data() -> dict[str, object]:
    return read_save_payload(SAVE_PATH)


def load_best_score(payload: dict[str, object]) -> int:
    best_score = payload.get("best_score", 0)
    if isinstance(best_score, int) and best_score >= 0:
        return best_score
    return 0


def load_sound_settings(payload: dict[str, object]) -> SoundSettings:
    sound_payload = payload.get("sound", {})
    if not isinstance(sound_payload, dict):
        return SoundSettings()

    enabled = sound_payload.get("enabled", True)
    volume = sound_payload.get("volume", DEFAULT_VOLUME)

    if not isinstance(enabled, bool):
        enabled = True
    if not isinstance(volume, (int, float)):
        volume = DEFAULT_VOLUME

    return SoundSettings(
        enabled=enabled,
        volume=clamp(float(volume), MIN_VOLUME, MAX_VOLUME),
    )


def save_progress(best_score: int, sound_settings: SoundSettings) -> None:
    payload = {
        "best_score": max(0, int(best_score)),
        "sound": {
            "enabled": sound_settings.enabled,
            "volume": round(clamp(sound_settings.volume, MIN_VOLUME, MAX_VOLUME), 2),
        },
    }
    saved = False
    try:
        SAVE_PATH.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def update_particles(particles: list[Particle], dt: float) -> None:
    for particle in particles[:]:
        particle.position += particle.velocity * dt
        particle.velocity *= PARTICLE_DRAG
        wrap_position(particle.position)
        particle.ttl -= dt
        if particle.ttl <= 0:
            particles.remove(particle)


def draw_particles(surface: pygame.Surface, particles: list[Particle]) -> None:
    for particle in particles:
        life_ratio = particle.ttl / particle.max_ttl
        radius = max(1, int(particle.radius * (0.4 + life_ratio)))
        color = tuple(int(channel * (0.25 + 0.75 * life_ratio)) for channel in particle.color)
        draw_wrapped_circle(surface, color, particle.position, radius)


def update_asteroids(asteroids: list[Asteroid], dt: float) -> None:
    for asteroid in asteroids:
        asteroid.position += asteroid.velocity * dt
        asteroid.angle += asteroid.spin * dt
        wrap_position(asteroid.position)


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.display.set_caption("Asteroids")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    hud_font = pygame.font.SysFont("consolas", 24)
    title_font = pygame.font.SysFont("consolas", 36, bold=True)
    hero_font = pygame.font.SysFont("consolas", 72, bold=True)
    save_data = load_save_data()
    sound_bank = build_sound_bank()
    sound_settings = load_sound_settings(save_data)
    apply_sound_settings(sound_bank, sound_settings)

    ship, bullets, particles, level, score, asteroids = create_session()
    attract_asteroids = [spawn_asteroid(random.choice((2, 2, 3, 3))) for _ in range(6)]
    best_score = load_best_score(save_data)
    running = True
    state = "title"
    new_high_score = False

    while running:
        dt = clock.tick(FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and state == "title" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                ship, bullets, particles, level, score, asteroids = create_session()
                state = "playing"
                new_high_score = False
            elif event.type == pygame.KEYDOWN and state == "game_over" and event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                ship, bullets, particles, level, score, asteroids = create_session()
                state = "playing"
                new_high_score = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                toggle_sound(sound_bank, sound_settings)
                save_progress(best_score, sound_settings)
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                adjust_volume(sound_bank, sound_settings, -VOLUME_STEP)
                save_progress(best_score, sound_settings)
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                adjust_volume(sound_bank, sound_settings, VOLUME_STEP)
                save_progress(best_score, sound_settings)

        keys = pygame.key.get_pressed()

        if state == "title":
            update_asteroids(attract_asteroids, dt)
        elif state == "playing":
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
                play_sound(sound_bank.shoot)

            for bullet in bullets[:]:
                bullet.position += bullet.velocity * dt
                wrap_position(bullet.position)
                bullet.ttl -= dt
                if bullet.ttl <= 0:
                    bullets.remove(bullet)

            update_asteroids(asteroids, dt)

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
                particles.extend(
                    emit_particles(
                        hit.position,
                        6 + (hit.size * 3),
                        ACCENT,
                        speed_range=(45, 170),
                        ttl_range=(0.24, 0.55),
                        radius_range=(1.5, 3.4),
                    )
                )
                particles.extend(
                    emit_particles(
                        hit.position,
                        5 + (hit.size * 2),
                        FOREGROUND,
                        speed_range=(35, 120),
                        ttl_range=(0.18, 0.45),
                        radius_range=(1.2, 2.8),
                    )
                )
                play_sound(sound_bank.hit)

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
                        particles.extend(
                            emit_particles(
                                ship.position,
                                18,
                                WARNING,
                                speed_range=(65, 220),
                                ttl_range=(0.35, 0.9),
                                radius_range=(2.0, 4.2),
                            )
                        )
                        particles.extend(
                            emit_particles(
                                ship.position,
                                10,
                                ACCENT,
                                speed_range=(40, 160),
                                ttl_range=(0.25, 0.7),
                                radius_range=(1.5, 3.5),
                            )
                        )
                        play_sound(sound_bank.ship_hit)
                        ship.lives -= 1
                        if ship.lives <= 0:
                            state = "game_over"
                            if score > best_score:
                                best_score = score
                                save_progress(best_score, sound_settings)
                                new_high_score = True
                            else:
                                new_high_score = False
                        else:
                            preserved_lives = ship.lives
                            ship = reset_ship()
                            ship.lives = preserved_lives
                        bullets.clear()
                        break

            if not asteroids and state == "playing":
                level += 1
                asteroids = create_level(level, ship.position)
        elif state == "game_over":
            update_asteroids(asteroids, dt)

        update_particles(particles, dt)
        screen.fill(BACKGROUND)

        visible_asteroids = attract_asteroids if state == "title" else asteroids

        for asteroid in visible_asteroids:
            draw_wrapped_polygon(screen, FOREGROUND, asteroid_screen_points(asteroid), asteroid.position)

        if state != "title":
            for bullet in bullets:
                draw_wrapped_circle(screen, ACCENT, bullet.position, 3)

            draw_particles(screen, particles)

        if state == "playing":
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

        if state != "title":
            score_text = hud_font.render(f"Score {score:05d}", True, FOREGROUND)
            best_text = hud_font.render(f"Best {best_score:05d}", True, FOREGROUND)
            lives_text = hud_font.render(f"Lives {ship.lives}", True, FOREGROUND)
            level_text = hud_font.render(f"Level {level}", True, FOREGROUND)
            sound_text = hud_font.render(sound_status_text(sound_settings), True, MUTED)
            help_text = hud_font.render("Arrows move, Space fires, Esc quits", True, MUTED)
            sound_help_text = hud_font.render("M toggles sound, -/+ adjusts volume", True, MUTED)

            screen.blit(score_text, (24, 20))
            screen.blit(best_text, (24, 50))
            screen.blit(lives_text, (24, 80))
            screen.blit(level_text, (24, 110))
            screen.blit(sound_text, (24, 140))
            screen.blit(sound_help_text, (24, HEIGHT - 72))
            screen.blit(help_text, (24, HEIGHT - 42))

        if state == "title":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((2, 4, 8, 150))
            screen.blit(overlay, (0, 0))

            title = hero_font.render("ASTEROIDS", True, FOREGROUND)
            subtitle = hud_font.render("A tiny arcade field with local score tracking", True, ACCENT)
            prompt = hud_font.render("Press Enter or Space to start", True, FOREGROUND)
            best = title_font.render(f"Best Score {best_score:05d}", True, FOREGROUND)
            controls = hud_font.render("Left / Right rotate   Up thrust   Space fire   Esc quit", True, MUTED)
            sound_controls = hud_font.render("M toggles sound   - / + volume", True, MUTED)
            sound_status = hud_font.render(sound_status_text(sound_settings), True, FOREGROUND)

            screen.blit(title, title.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 120)))
            screen.blit(subtitle, subtitle.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 56)))
            screen.blit(best, best.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 12)))
            screen.blit(prompt, prompt.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 72)))
            screen.blit(sound_status, sound_status.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 112)))
            screen.blit(sound_controls, sound_controls.get_rect(center=(WIDTH / 2, HEIGHT - 102)))
            screen.blit(controls, controls.get_rect(center=(WIDTH / 2, HEIGHT - 72)))

        if state == "game_over":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((2, 4, 8, 170))
            screen.blit(overlay, (0, 0))

            title = title_font.render("Game Over", True, WARNING)
            retry = hud_font.render("Press Enter, Space, or R to restart", True, FOREGROUND)
            final_score = hud_font.render(f"Final score: {score}", True, FOREGROUND)
            best = hud_font.render(f"Best score: {best_score}", True, FOREGROUND)
            banner = hud_font.render("New high score!" if new_high_score else "Try to beat your best run", True, ACCENT)

            screen.blit(title, title.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 40)))
            screen.blit(final_score, final_score.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 2)))
            screen.blit(best, best.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 36)))
            screen.blit(banner, banner.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 70)))
            screen.blit(retry, retry.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 108)))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
