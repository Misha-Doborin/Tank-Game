import math
import random
import sys
from dataclasses import dataclass

import pygame


SCREEN_WIDTH = 1100
SCREEN_HEIGHT = 750
HUD_HEIGHT = 54
WORLD_WIDTH = 3800
WORLD_HEIGHT = 2800
FPS = 60

BLUE = "blue"
RED = "red"

TEAM_COLORS = {
    BLUE: (53, 140, 245),
    RED: (224, 66, 66),
}

BACKGROUND = (37, 45, 43)
GRID = (48, 58, 55)
OBSTACLE = (83, 88, 82)
OBSTACLE_EDGE = (125, 132, 124)
TEXT = (236, 241, 235)
YELLOW = (245, 204, 84)
STONE = (124, 130, 130)
STONE_DARK = (76, 82, 82)
MONSTER_MAX_HP = 200
MONSTER_START_TIMER = 999999.0
STONE_TRANSITION_TIME = 5.0
MONSTER_REGEN_INTERVAL = 1.5
POWERUP_CHANNEL_TIME = 5.0
STONE_RESIZE_STEP = 18
STONE_MIN_SIZE = 34

DIRS = {
    pygame.K_UP: pygame.Vector2(0, -1),
    pygame.K_DOWN: pygame.Vector2(0, 1),
    pygame.K_LEFT: pygame.Vector2(-1, 0),
    pygame.K_RIGHT: pygame.Vector2(1, 0),
    pygame.K_w: pygame.Vector2(0, -1),
    pygame.K_s: pygame.Vector2(0, 1),
    pygame.K_a: pygame.Vector2(-1, 0),
    pygame.K_d: pygame.Vector2(1, 0),
}

POWERUP_INFO = {
    "ghost": ("Танк-призрак", (126, 216, 255), 10.0),
    "army": ("Великая армия", (117, 232, 136), 12.0),
    "monster": ("Монстр", (203, 92, 255), 12.0),
    "repair": ("Ремонт", (255, 126, 84), 0.0),
    "rapid": ("Быстрая пушка", (255, 229, 99), 10.0),
    "shield": ("Щит", (92, 190, 255), 12.0),
    "turbo": ("Турбо", (255, 151, 204), 10.0),
}


@dataclass
class Bullet:
    pos: pygame.Vector2
    vel: pygame.Vector2
    team: str
    damage: int
    life: float = 2.4
    radius: int = 5
    kind: str = "bullet"
    splash_radius: int = 0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.pos.x - self.radius),
            int(self.pos.y - self.radius),
            self.radius * 2,
            self.radius * 2,
        )


@dataclass
class PowerUp:
    kind: str
    rect: pygame.Rect
    pulse: float = 0.0


@dataclass
class PowerupChannel:
    caster: object
    target: PowerUp
    timer: float = 0.0


@dataclass
class PowerUpParticle:
    pos: pygame.Vector2
    vel: pygame.Vector2
    color: tuple
    life: float
    max_life: float
    radius: float
    drag: float = 0.88


class Tank:
    def __init__(self, team, pos, is_player=False, temporary=False):
        self.team = team
        self.pos = pygame.Vector2(pos)
        self.is_player = is_player
        self.temporary = temporary
        self.direction = pygame.Vector2(0, -1 if team == BLUE else 1)
        self.speed = 145.0
        self.max_hp = 4
        self.hp = self.max_hp
        self.cooldown = random.uniform(0.2, 1.0)
        self.ai_change_timer = 0.0
        self.ai_move = pygame.Vector2()
        self.ai_last_pos = self.pos.copy()
        self.ai_stuck_timer = 0.0
        self.ai_pressure_timer = 0.0
        self.respawn_timer = 0.0
        self.ghost_timer = 0.0
        self.rapid_timer = 0.0
        self.shield_timer = 0.0
        self.turbo_timer = 0.0
        self.turbo_warp_timer = 0.0
        self.mega_speed_timer = 0.0
        self.monster_timer = 0.0
        self.monster_permanent = False
        self.army_timer = 0.0
        self.army_inflate_timer = 0.0
        self.army_burst_done = True
        self.permanent_helper = False
        self.teleport_cooldown = 0.0
        self.rocket_cooldown = 0.0
        self.bile_cooldown = 0.0
        self.life_timer = 28.0 if temporary else 0.0
        self.monster_regen_timer = 0.0
        self.stone_mode = False
        self.stone_transition = 0.0
        self.stone_rect = None

    @property
    def alive(self):
        return self.respawn_timer <= 0.0 and self.hp > 0

    @property
    def size(self):
        return 52 if self.monster_timer > 0 else 38

    @property
    def base_rect(self):
        size = self.size
        return pygame.Rect(
            int(self.pos.x - size / 2),
            int(self.pos.y - size / 2),
            size,
            size,
        )

    @property
    def rect(self):
        if self.stone_mode and self.stone_rect is not None:
            return self.stone_rect.copy()
        return self.base_rect

    @property
    def current_speed(self):
        speed = self.speed
        if self.turbo_warp_timer > 0:
            speed *= 0.78
        if self.mega_speed_timer > 0:
            speed *= 3.35
        if self.monster_timer > 0:
            speed *= 0.82
        if self.stone_mode or self.stone_transition > 0:
            return 0.0
        return speed

    @property
    def shoot_delay(self):
        if self.rapid_timer > 0:
            return 0.28
        return 0.75 if self.is_player else 1.05

    @property
    def bullet_damage(self):
        return 2 if self.monster_timer > 0 else 1

    def update_timers(self, dt):
        was_monster = self.monster_timer > 0
        was_warping = self.turbo_warp_timer > 0
        self.cooldown = max(0.0, self.cooldown - dt)
        self.teleport_cooldown = max(0.0, self.teleport_cooldown - dt)
        self.rocket_cooldown = max(0.0, self.rocket_cooldown - dt)
        self.bile_cooldown = max(0.0, self.bile_cooldown - dt)
        self.ghost_timer = max(0.0, self.ghost_timer - dt)
        self.rapid_timer = max(0.0, self.rapid_timer - dt)
        self.shield_timer = max(0.0, self.shield_timer - dt)
        self.turbo_timer = max(0.0, self.turbo_timer - dt)
        self.turbo_warp_timer = max(0.0, self.turbo_warp_timer - dt)
        self.mega_speed_timer = max(0.0, self.mega_speed_timer - dt)
        if not self.monster_permanent:
            self.monster_timer = max(0.0, self.monster_timer - dt)
        self.army_timer = max(0.0, self.army_timer - dt)
        self.army_inflate_timer = max(0.0, self.army_inflate_timer - dt)
        if was_warping and self.turbo_warp_timer <= 0:
            self.mega_speed_timer = 20.0
        if was_monster and self.monster_timer <= 0:
            self.max_hp = 4
            self.hp = min(self.hp, self.max_hp)
        if self.monster_timer > 0:
            self.monster_regen_timer += dt
            while self.monster_regen_timer >= MONSTER_REGEN_INTERVAL:
                self.monster_regen_timer -= MONSTER_REGEN_INTERVAL
                if self.hp > 0:
                    self.hp = min(self.max_hp, self.hp + 1)
        else:
            self.monster_regen_timer = 0.0

        if self.stone_transition > 0:
            self.stone_transition = max(0.0, self.stone_transition - dt)
            if self.stone_transition <= 0 and not self.stone_mode:
                self.stone_rect = self.base_rect.copy()
                self.stone_mode = True

        if self.temporary and not self.permanent_helper:
            self.life_timer -= dt

    def draw(self, surface, camera, font):
        if not self.alive:
            return

        rect = self.rect.move(-camera.x, -camera.y + HUD_HEIGHT)
        now = pygame.time.get_ticks() / 1000.0
        if self.stone_mode:
            pygame.draw.rect(surface, OBSTACLE, rect, border_radius=5)
            pygame.draw.rect(surface, OBSTACLE_EDGE, rect, 3, border_radius=5)
            for y in range(rect.top + 12, rect.bottom - 6, 18):
                pygame.draw.line(surface, STONE_DARK, (rect.left + 6, y), (rect.right - 6, y - 5), 1)
            pulse = 0.5 + 0.5 * math.sin(now * 5.0)
            pygame.draw.rect(surface, (155, 255, 122), rect.inflate(int(5 + pulse * 5), int(5 + pulse * 5)), 1, border_radius=6)
            return
        if self.army_inflate_timer > 0:
            progress = 1.0 - self.army_inflate_timer / 1.45
            pulse = 0.5 + 0.5 * math.sin(now * 22.0)
            inflate = int(12 + progress * 52 + pulse * 10)
            rect = rect.inflate(inflate, inflate)
        if self.turbo_warp_timer > 0:
            jitter = 5 + int((0.5 + 0.5 * math.sin(now * 19.0)) * 7)
            rect = rect.move(random.randint(-jitter, jitter), random.randint(-jitter, jitter))
        color = TEAM_COLORS[self.team]
        alpha = 135 if self.ghost_timer > 0 else 255

        body = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(body, (*color, alpha), body.get_rect(), border_radius=4)
        pygame.draw.rect(body, (22, 25, 25, alpha), body.get_rect(), 3, border_radius=4)

        track_color = (18, 22, 22, alpha)
        pygame.draw.rect(body, track_color, (1, 4, 7, rect.height - 8), border_radius=3)
        pygame.draw.rect(body, track_color, (rect.width - 8, 4, 7, rect.height - 8), border_radius=3)

        center = pygame.Vector2(rect.width / 2, rect.height / 2)
        barrel_end = center + self.direction * (rect.width * 0.58)
        pygame.draw.line(body, (20, 24, 24, alpha), center, barrel_end, 7)
        pygame.draw.circle(body, (34, 39, 38, alpha), center, max(8, rect.width // 5))

        surface.blit(body, rect)

        if self.stone_mode or self.stone_transition > 0:
            phase = 1.0 if self.stone_mode else 1.0 - (self.stone_transition / STONE_TRANSITION_TIME)
            stone = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(stone, (*STONE, int(60 + 140 * phase)), stone.get_rect(), border_radius=4)
            crack_count = 3 + int(phase * 8)
            for i in range(crack_count):
                y = int((i + 1) * rect.height / (crack_count + 1))
                pygame.draw.line(stone, (*STONE_DARK, int(120 + 90 * phase)), (3, y), (rect.width - 3, max(3, y - 4)), 1)
            surface.blit(stone, rect)

        active_effects = [
            (self.ghost_timer, (126, 216, 255)),
            (self.rapid_timer, (255, 229, 99)),
            (self.turbo_warp_timer + self.mega_speed_timer, (255, 151, 204)),
            (self.monster_timer, (203, 92, 255)),
            (self.army_inflate_timer, (117, 232, 136)),
        ]
        for index, (timer, effect_color) in enumerate(active_effects):
            if timer <= 0:
                continue
            pulse = 0.5 + 0.5 * math.sin(now * (5.5 + index) + index * 1.7)
            inflate = int(12 + index * 5 + pulse * 14)
            aura_rect = rect.inflate(inflate, inflate)
            aura = pygame.Surface(aura_rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(aura, (*effect_color, int(42 + pulse * 48)), aura.get_rect(), 2)
            pygame.draw.ellipse(aura, (*effect_color, int(18 + pulse * 26)), aura.get_rect().inflate(-8, -8), 2)
            surface.blit(aura, aura_rect)

        if self.turbo_warp_timer > 0:
            for i in range(5):
                offset = pygame.Vector2(
                    math.sin(now * 26 + i) * (8 + i),
                    math.cos(now * 21 + i * 1.4) * (6 + i),
                )
                warped = rect.move(offset.x, offset.y)
                pygame.draw.rect(surface, (255, 151, 204), warped, 2, border_radius=5)

        if self.mega_speed_timer > 0:
            back = pygame.Vector2(rect.center) - self.direction * (rect.width * 0.62)
            side = pygame.Vector2(-self.direction.y, self.direction.x)
            for offset in (-12, -4, 4, 12):
                flame_pos = back + side * offset
                length = 24 + int(20 * (0.5 + 0.5 * math.sin(now * 22 + offset)))
                end = flame_pos - self.direction * length
                pygame.draw.line(surface, (255, 240, 135), flame_pos, end, 7)
                pygame.draw.line(surface, (255, 69, 96), flame_pos, end, 3)

        if self.rapid_timer > 0:
            muzzle = pygame.Vector2(rect.center) + self.direction * (rect.width * 0.62)
            side = pygame.Vector2(-self.direction.y, self.direction.x)
            for i in range(3):
                spark = muzzle + side * math.sin(now * 16 + i * 2.1) * 10
                pygame.draw.circle(surface, (255, 236, 130), (int(spark.x), int(spark.y)), 2 + i % 2)

        if self.monster_timer > 0:
            pygame.draw.rect(surface, (223, 118, 255), rect.inflate(8, 8), 3, border_radius=5)
            for i in range(10):
                angle = now * 4.0 + math.tau * i / 10
                p1 = pygame.Vector2(rect.center) + pygame.Vector2(math.cos(angle), math.sin(angle)) * (rect.width * 0.62)
                p2 = pygame.Vector2(rect.center) + pygame.Vector2(math.cos(angle), math.sin(angle)) * (rect.width * 0.82 + math.sin(now * 11 + i) * 8)
                pygame.draw.line(surface, (147, 255, 83), p1, p2, 2)

        if self.shield_timer > 0:
            pulse = 0.5 + 0.5 * math.sin(now * 8.0)
            pygame.draw.ellipse(surface, (108, 206, 255), rect.inflate(16 + int(pulse * 8), 16 + int(pulse * 8)), 2)
            pygame.draw.ellipse(surface, (192, 236, 255), rect.inflate(28 + int(pulse * 12), 28 + int(pulse * 12)), 1)

        hp_w = rect.width
        hp_back = pygame.Rect(rect.left, rect.top - 10, hp_w, 5)
        pygame.draw.rect(surface, (25, 25, 25), hp_back)
        pygame.draw.rect(surface, (91, 225, 111), (hp_back.x, hp_back.y, int(hp_w * self.hp / self.max_hp), 5))

        labels = []
        if self.is_player:
            labels.append(("ИГРОК", TEXT))
        if self.monster_timer > 0:
            if self.stone_mode:
                labels.append(("КАМЕНЬ", STONE))
            elif self.stone_transition > 0:
                labels.append((f"ОКАМЕНЕНИЕ {math.ceil(self.stone_transition)}", STONE))
            else:
                labels.append(("МОНСТР", (203, 92, 255)))
        for index, (text, label_color) in enumerate(labels):
            label = font.render(text, True, label_color)
            surface.blit(label, (rect.centerx - label.get_width() // 2, rect.bottom + 4 + index * 18))


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Бесконечная битва танков")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 20)
        self.big_font = pygame.font.SysFont("arial", 30, bold=True)

        random.seed()
        self.obstacles = self.make_obstacles()
        self.tanks = []
        self.bullets = []
        self.powerups = []
        self.powerup_particles = []
        self.powerup_channel = None
        self.blue_kills = 0
        self.red_kills = 0
        self.powerup_timer = 3.0
        self.message = ""
        self.message_timer = 0.0

        self.spawn_initial_tanks()

    def make_obstacles(self):
        obstacles = []
        reserved = [
            pygame.Rect(120, 120, 520, 430),
            pygame.Rect(WORLD_WIDTH - 640, WORLD_HEIGHT - 560, 520, 430),
        ]

        attempts = 0
        while len(obstacles) < 58 and attempts < 2000:
            attempts += 1
            w = random.randint(95, 260)
            h = random.randint(70, 220)
            x = random.randint(120, WORLD_WIDTH - w - 120)
            y = random.randint(120, WORLD_HEIGHT - h - 120)
            rect = pygame.Rect(x, y, w, h)
            if any(rect.inflate(80, 80).colliderect(other) for other in obstacles + reserved):
                continue
            obstacles.append(rect)
        return obstacles

    def spawn_initial_tanks(self):
        blue_spawns = [(250, 250), (360, 380), (520, 260)]
        red_spawns = [
            (WORLD_WIDTH - 250, WORLD_HEIGHT - 250),
            (WORLD_WIDTH - 380, WORLD_HEIGHT - 410),
            (WORLD_WIDTH - 560, WORLD_HEIGHT - 280),
        ]
        player_tank = Tank(BLUE, blue_spawns[0], is_player=True)
        player_tank.monster_timer = MONSTER_START_TIMER
        player_tank.monster_permanent = True
        player_tank.max_hp = MONSTER_MAX_HP
        player_tank.hp = MONSTER_MAX_HP
        self.tanks.append(player_tank)
        self.spawn_powerup_burst(player_tank.pos, "monster")
        self.flash("Игрок получил Монстра до первой смерти. G — окаменение")
        for pos in blue_spawns[1:]:
            self.tanks.append(Tank(BLUE, pos))
        for pos in red_spawns:
            self.tanks.append(Tank(RED, pos))

    @property
    def player(self):
        return next(t for t in self.tanks if t.is_player)

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self.try_shoot(self.player)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_t:
                self.try_monster_teleport(self.player)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self.try_fire_rocket(self.player)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                self.try_spray_bile(self.player)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_g:
                self.toggle_stone_mode(self.player)
            if event.type == pygame.KEYDOWN:
                self.handle_stone_resize_key(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.try_start_powerup_channel(event.pos)

    def update(self, dt):
        keys = pygame.key.get_pressed()
        player_move = pygame.Vector2()
        for key, direction in DIRS.items():
            if keys[key]:
                player_move = direction
                break

        if self.player.alive:
            self.move_tank(self.player, player_move, dt)

        for tank in list(self.tanks):
            tank.update_timers(dt)
            if tank.temporary and not tank.permanent_helper and tank.life_timer <= 0:
                self.tanks.remove(tank)
                continue
            if tank.alive and tank.army_inflate_timer <= 0 and not tank.army_burst_done:
                tank.army_burst_done = True
                self.spawn_army(tank)
            if not tank.is_player and tank.alive:
                self.update_ai(tank, dt)

        self.update_bullets(dt)
        self.update_respawns(dt)
        self.update_powerups(dt)
        self.update_powerup_particles(dt)
        self.update_powerup_channel(dt)
        self.message_timer = max(0.0, self.message_timer - dt)

    def update_ai(self, tank, dt):
        if tank.stone_mode or tank.stone_transition > 0:
            return
        enemies = [
            t
            for t in self.tanks
            if t.team != tank.team and t.alive and not self.is_stone_wall(t)
        ]
        if not enemies:
            return

        if tank.pos.distance_squared_to(tank.ai_last_pos) < 9:
            tank.ai_stuck_timer += dt
        else:
            tank.ai_stuck_timer = max(0.0, tank.ai_stuck_timer - dt * 2)
        tank.ai_last_pos = tank.pos.copy()
        tank.ai_pressure_timer = max(0.0, tank.ai_pressure_timer - dt)

        target = self.choose_ai_target(tank, enemies)
        to_target = target.pos - tank.pos
        distance = to_target.length()

        threat = self.incoming_bullet_threat(tank)
        aim_direction = self.ai_aim_direction(tank, target)
        if aim_direction is not None and distance < 820:
            tank.direction = aim_direction
            self.try_shoot(tank)
            if tank.monster_timer > 0:
                if distance > 260:
                    self.try_fire_rocket(tank)
                elif distance < 340:
                    self.try_spray_bile(tank)
        if tank.monster_timer > 0 and tank.hp < 70 and distance < 460:
            retreat = self.cardinal_direction(tank.pos - target.pos)
            if retreat.length_squared():
                tank.direction = retreat
                self.try_monster_teleport(tank)

        powerup = self.choose_ai_powerup(tank, target)

        tank.ai_change_timer -= dt
        if threat is not None:
            tank.ai_move = self.dodge_direction(tank, threat, target)
            tank.ai_change_timer = 0.08
            tank.ai_pressure_timer = 0.45
        elif tank.ai_change_timer <= 0 or tank.ai_stuck_timer > 0.22:
            tank.ai_change_timer = random.uniform(0.16, 0.42)
            if powerup is not None:
                tank.ai_move = self.best_ai_direction(tank, pygame.Vector2(powerup.rect.center), preferred_distance=0)
            else:
                preferred_distance = 360 if tank.hp > 1 else 560
                if tank.monster_timer > 0 or target.hp <= tank.bullet_damage:
                    preferred_distance = 230
                tank.ai_move = self.best_ai_direction(tank, target.pos, preferred_distance=preferred_distance)

        moved = self.move_tank(tank, tank.ai_move, dt)
        if not moved:
            tank.ai_move = self.best_escape_direction(tank, target)
            tank.ai_change_timer = 0.06

    def choose_ai_target(self, tank, enemies):
        def score(enemy):
            distance = tank.pos.distance_to(enemy.pos)
            direction = self.cardinal_direction(enemy.pos - tank.pos)
            line_bonus = 230 if self.has_line_of_fire(tank.pos, enemy.pos, direction) else 0
            player_bonus = 110 if enemy.is_player else 0
            weak_bonus = (enemy.max_hp - enemy.hp) * 70
            dangerous_bonus = 90 if enemy.monster_timer > 0 or enemy.rapid_timer > 0 else 0
            return distance - line_bonus - player_bonus - weak_bonus - dangerous_bonus

        return min(enemies, key=score)

    def ai_aim_direction(self, tank, target):
        to_target = target.pos - tank.pos
        if to_target.length_squared() == 0:
            return None

        bullet_speed = 680 if tank.monster_timer > 0 else 560
        travel_time = min(0.7, to_target.length() / bullet_speed)
        predicted = target.pos + target.direction * target.current_speed * travel_time * 0.58

        for point in (predicted, target.pos):
            direction = self.cardinal_direction(point - tank.pos)
            if self.has_line_of_fire(tank.pos, point, direction):
                return direction
        return None

    def choose_ai_powerup(self, tank, target):
        if not self.powerups:
            return None

        best = None
        best_score = 999999
        for powerup in self.powerups:
            distance = tank.pos.distance_to(powerup.rect.center)
            if distance > 900:
                continue
            value = 120
            if powerup.kind == "repair" and tank.hp <= max(2, tank.max_hp // 2):
                value = 420
            elif powerup.kind == "shield" and tank.shield_timer <= 0:
                value = 340
            elif powerup.kind == "rapid" and tank.rapid_timer <= 0:
                value = 300
            elif powerup.kind == "monster" and tank.monster_timer <= 0:
                value = 360
            elif powerup.kind == "turbo" and tank.turbo_timer <= 0:
                value = 260
            elif powerup.kind == "army" and tank.army_timer <= 0:
                value = 330
            elif powerup.kind == "ghost" and tank.ghost_timer <= 0:
                value = 260

            if target.pos.distance_to(powerup.rect.center) < distance:
                value += 90

            score = distance - value
            if score < best_score:
                best = powerup
                best_score = score
        return best if best_score < 430 else None

    def incoming_bullet_threat(self, tank):
        best = None
        best_time = 999
        for bullet in self.bullets:
            if bullet.team == tank.team or bullet.vel.length_squared() == 0:
                continue
            direction = bullet.vel.normalize()
            to_tank = tank.pos - bullet.pos
            closing_distance = to_tank.dot(direction)
            if closing_distance <= 0 or closing_distance > 520:
                continue
            miss_distance = abs(to_tank.x * direction.y - to_tank.y * direction.x)
            danger_radius = tank.size * 0.68 + bullet.radius
            if miss_distance > danger_radius:
                continue
            time_to_hit = closing_distance / bullet.vel.length()
            if time_to_hit < best_time:
                best = bullet
                best_time = time_to_hit
        return best

    def dodge_direction(self, tank, bullet, target):
        bullet_dir = bullet.vel.normalize()
        candidates = []
        if abs(bullet_dir.x) > abs(bullet_dir.y):
            candidates = [pygame.Vector2(0, -1), pygame.Vector2(0, 1)]
        else:
            candidates = [pygame.Vector2(-1, 0), pygame.Vector2(1, 0)]
        candidates += [self.cardinal_direction(tank.pos - target.pos), self.cardinal_direction(target.pos - tank.pos)]
        return self.best_direction_from_candidates(tank, candidates, target.pos, preferred_distance=430)

    def best_ai_direction(self, tank, goal, preferred_distance=0):
        candidates = list(DIRS.values())
        random.shuffle(candidates)
        direct = self.cardinal_direction(goal - tank.pos)
        if direct in candidates:
            candidates.remove(direct)
            candidates.insert(0, direct)
        return self.best_direction_from_candidates(tank, candidates, goal, preferred_distance)

    def best_escape_direction(self, tank, target):
        candidates = list(DIRS.values())
        random.shuffle(candidates)
        return self.best_direction_from_candidates(tank, candidates, target.pos, preferred_distance=520)

    def best_direction_from_candidates(self, tank, candidates, goal, preferred_distance):
        best_direction = candidates[0] if candidates else pygame.Vector2()
        best_score = -999999
        for direction in candidates:
            if direction.length_squared() == 0:
                continue
            lookahead = max(34, tank.current_speed * 0.34)
            if not self.can_tank_step(tank, direction, lookahead):
                continue
            future = tank.pos + direction * lookahead
            distance = future.distance_to(goal)
            if preferred_distance > 0:
                score = -abs(distance - preferred_distance)
            else:
                score = -distance

            line_direction = self.cardinal_direction(goal - future)
            if self.has_line_of_fire(future, goal, line_direction):
                score += 95
            if tank.ai_pressure_timer > 0 and preferred_distance > 0:
                score += min(distance, 700) * 0.08
            score += random.uniform(-8, 8)
            if score > best_score:
                best_score = score
                best_direction = direction
        return best_direction

    def is_stone_wall(self, tank):
        return tank.alive and tank.monster_timer > 0 and tank.stone_mode

    def stone_walls(self, exclude=None):
        return [tank for tank in self.tanks if tank is not exclude and self.is_stone_wall(tank)]

    def can_tank_step(self, tank, direction, distance):
        future_pos = tank.pos + direction * distance
        half = tank.size / 2
        future_pos.x = max(half, min(WORLD_WIDTH - half, future_pos.x))
        future_pos.y = max(half, min(WORLD_HEIGHT - half, future_pos.y))
        rect = pygame.Rect(int(future_pos.x - half), int(future_pos.y - half), tank.size, tank.size)
        if tank.ghost_timer <= 0 and any(rect.colliderect(obstacle) for obstacle in self.obstacles):
            return False
        for other in self.tanks:
            if other is tank or not other.alive:
                continue
            if rect.colliderect(other.rect):
                return False
        return True

    def cardinal_direction(self, vector):
        if abs(vector.x) > abs(vector.y):
            return pygame.Vector2(1 if vector.x > 0 else -1, 0)
        return pygame.Vector2(0, 1 if vector.y > 0 else -1)

    def move_tank(self, tank, direction, dt):
        if direction.length_squared() == 0:
            return True

        tank.direction = direction
        old = tank.pos.copy()
        tank.pos += direction * tank.current_speed * dt
        tank.pos.x = max(tank.size / 2, min(WORLD_WIDTH - tank.size / 2, tank.pos.x))
        tank.pos.y = max(tank.size / 2, min(WORLD_HEIGHT - tank.size / 2, tank.pos.y))

        if tank.ghost_timer <= 0 and any(tank.rect.colliderect(obstacle) for obstacle in self.obstacles):
            tank.pos = old
            return False

        for other in self.tanks:
            if other is tank or not other.alive:
                continue
            if tank.rect.colliderect(other.rect):
                tank.pos = old
                return False
        return True


    def handle_stone_resize_key(self, event):
        directions = {
            pygame.K_1: pygame.Vector2(0, -1),
            pygame.K_2: pygame.Vector2(1, -1),
            pygame.K_3: pygame.Vector2(1, 0),
            pygame.K_4: pygame.Vector2(1, 1),
            pygame.K_5: pygame.Vector2(0, 1),
            pygame.K_6: pygame.Vector2(-1, 1),
            pygame.K_7: pygame.Vector2(-1, 0),
            pygame.K_8: pygame.Vector2(-1, -1),
            pygame.K_KP1: pygame.Vector2(0, -1),
            pygame.K_KP2: pygame.Vector2(1, -1),
            pygame.K_KP3: pygame.Vector2(1, 0),
            pygame.K_KP4: pygame.Vector2(1, 1),
            pygame.K_KP5: pygame.Vector2(0, 1),
            pygame.K_KP6: pygame.Vector2(-1, 1),
            pygame.K_KP7: pygame.Vector2(-1, 0),
            pygame.K_KP8: pygame.Vector2(-1, -1),
        }
        if event.key not in directions:
            return
        expand = not (pygame.key.get_mods() & pygame.KMOD_SHIFT)
        self.adjust_stone_wall(self.player, directions[event.key], expand)

    def adjust_stone_wall(self, tank, direction, expand=True):
        if not self.is_stone_wall(tank):
            return

        rect = tank.rect
        step = STONE_RESIZE_STEP if expand else -STONE_RESIZE_STEP
        if direction.x < 0:
            rect.left -= step
        elif direction.x > 0:
            rect.right += step
        if direction.y < 0:
            rect.top -= step
        elif direction.y > 0:
            rect.bottom += step

        rect.normalize()
        if rect.width < STONE_MIN_SIZE or rect.height < STONE_MIN_SIZE:
            self.flash("Каменная стена уже минимальна")
            return
        if rect.left < 0 or rect.top < 0 or rect.right > WORLD_WIDTH or rect.bottom > WORLD_HEIGHT:
            self.flash("Граница мира не даёт изменить стену")
            return
        if any(rect.colliderect(other.rect) for other in self.tanks if other is not tank and other.alive):
            self.flash("Нельзя расширить стену сквозь танк")
            return

        tank.stone_rect = rect
        tank.pos = pygame.Vector2(rect.center)
        action = "расширилась" if expand else "сжалась"
        self.flash(f"Каменная стена {action}")

    def toggle_stone_mode(self, tank):
        if not tank.alive or tank.monster_timer <= 0:
            return
        if tank.stone_mode:
            tank.stone_mode = False
            tank.stone_transition = 0.0
            tank.stone_rect = None
            self.flash("Монстр раскаменел")
            return
        if tank.stone_transition > 0:
            return
        tank.stone_transition = STONE_TRANSITION_TIME
        self.flash(f"Окаменение началось ({int(STONE_TRANSITION_TIME)}с)")

    def try_shoot(self, tank):
        if tank.stone_mode or tank.stone_transition > 0:
            return
        if not tank.alive or tank.cooldown > 0:
            return

        speed = 560 if tank.monster_timer <= 0 else 680
        muzzle = tank.pos + tank.direction * (tank.size * 0.72)
        self.bullets.append(Bullet(muzzle, tank.direction * speed, tank.team, tank.bullet_damage))
        tank.cooldown = tank.shoot_delay

    def try_monster_teleport(self, tank):
        if tank.stone_mode or tank.stone_transition > 0:
            return
        if not tank.alive or tank.monster_timer <= 0 or tank.teleport_cooldown > 0:
            return

        direction = tank.direction if tank.direction.length_squared() else pygame.Vector2(0, -1)
        for distance in range(560, 120, -45):
            destination = tank.pos + direction * distance
            half = tank.size / 2
            destination.x = max(half, min(WORLD_WIDTH - half, destination.x))
            destination.y = max(half, min(WORLD_HEIGHT - half, destination.y))
            if self.can_tank_occupy(tank, destination):
                self.spawn_energy_ring(tank.pos, (203, 92, 255), 32)
                tank.pos = destination
                tank.teleport_cooldown = 2.6
                self.spawn_energy_ring(tank.pos, (147, 255, 83), 42)
                return

    def try_fire_rocket(self, tank):
        if tank.stone_mode or tank.stone_transition > 0:
            return
        if not tank.alive or tank.monster_timer <= 0 or tank.rocket_cooldown > 0:
            return

        muzzle = tank.pos + tank.direction * (tank.size * 0.78)
        rocket = Bullet(
            muzzle,
            tank.direction * 455,
            tank.team,
            7,
            life=2.9,
            radius=10,
            kind="rocket",
            splash_radius=135,
        )
        self.bullets.append(rocket)
        tank.rocket_cooldown = 1.65
        self.spawn_energy_ring(muzzle, (255, 101, 81), 18)

    def try_spray_bile(self, tank):
        if tank.stone_mode or tank.stone_transition > 0:
            return
        if not tank.alive or tank.monster_timer <= 0 or tank.bile_cooldown > 0:
            return

        base = math.atan2(tank.direction.y, tank.direction.x)
        origin = tank.pos + tank.direction * (tank.size * 0.7)
        for _ in range(22):
            angle = base + random.uniform(-0.72, 0.72)
            direction = pygame.Vector2(math.cos(angle), math.sin(angle))
            speed = random.uniform(285, 520)
            self.bullets.append(
                Bullet(
                    origin + direction * random.uniform(0, 18),
                    direction * speed,
                    tank.team,
                    1,
                    life=random.uniform(0.55, 1.05),
                    radius=random.randint(3, 6),
                    kind="bile",
                )
            )
        tank.bile_cooldown = 1.05
        self.spawn_energy_ring(origin, (147, 255, 83), 26)

    def spawn_energy_ring(self, pos, color, count):
        for i in range(count):
            angle = math.tau * i / count + random.uniform(-0.12, 0.12)
            life = random.uniform(0.28, 0.62)
            self.powerup_particles.append(
                PowerUpParticle(
                    pygame.Vector2(pos),
                    pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(120, 330),
                    color,
                    life,
                    life,
                    random.uniform(2.2, 6.0),
                    drag=0.91,
                )
            )

    def can_tank_occupy(self, tank, pos):
        half = tank.size / 2
        rect = pygame.Rect(int(pos.x - half), int(pos.y - half), tank.size, tank.size)
        if rect.left < 0 or rect.top < 0 or rect.right > WORLD_WIDTH or rect.bottom > WORLD_HEIGHT:
            return False
        if tank.ghost_timer <= 0 and any(rect.colliderect(obstacle) for obstacle in self.obstacles):
            return False
        for other in self.tanks:
            if other is tank or not other.alive:
                continue
            if rect.colliderect(other.rect):
                return False
        return True

    def update_bullets(self, dt):
        for bullet in list(self.bullets):
            bullet.pos += bullet.vel * dt
            bullet.life -= dt

            if (
                bullet.life <= 0
                or bullet.pos.x < 0
                or bullet.pos.y < 0
                or bullet.pos.x > WORLD_WIDTH
                or bullet.pos.y > WORLD_HEIGHT
            ):
                if bullet.kind == "rocket":
                    self.detonate_rocket(bullet)
                self.remove_bullet(bullet)
                continue

            hit_world_wall = any(bullet.rect.colliderect(obstacle) for obstacle in self.obstacles)
            hit_stone_wall = any(bullet.rect.colliderect(wall.rect) for wall in self.stone_walls())
            if hit_world_wall or hit_stone_wall:
                if bullet.kind == "rocket":
                    self.detonate_rocket(bullet)
                self.remove_bullet(bullet)
                continue

            for tank in list(self.tanks):
                if not tank.alive or tank.team == bullet.team:
                    continue
                if bullet.rect.colliderect(tank.rect):
                    self.hit_tank(tank, bullet)
                    if bullet.kind == "rocket":
                        self.detonate_rocket(bullet)
                    self.remove_bullet(bullet)
                    break

    def remove_bullet(self, bullet):
        if bullet in self.bullets:
            self.bullets.remove(bullet)

    def detonate_rocket(self, rocket):
        self.spawn_energy_ring(rocket.pos, (255, 82, 64), 60)
        self.spawn_energy_ring(rocket.pos, (255, 225, 105), 34)
        for tank in list(self.tanks):
            if not tank.alive or tank.team == rocket.team or self.is_stone_wall(tank):
                continue
            distance = tank.pos.distance_to(rocket.pos)
            if distance > rocket.splash_radius + tank.size / 2:
                continue
            damage = max(2, int(rocket.damage * (1.0 - distance / (rocket.splash_radius * 1.45))))
            splash = Bullet(rocket.pos.copy(), pygame.Vector2(), rocket.team, damage, kind="rocket_splash")
            self.hit_tank(tank, splash)

    def hit_tank(self, tank, bullet):
        if tank.shield_timer > 0:
            tank.shield_timer = 0
            self.flash("Щит отразил попадание")
            return

        tank.hp -= bullet.damage
        if tank.hp <= 0:
            if bullet.team == BLUE:
                self.blue_kills += 1
            else:
                self.red_kills += 1
            self.spawn_energy_ring(tank.pos, TEAM_COLORS[tank.team], 46)
            tank.monster_permanent = False
            if tank.temporary:
                if tank in self.tanks:
                    self.tanks.remove(tank)
                return
            tank.respawn_timer = 2.5
            tank.hp = 0
            self.flash("Синий танк уничтожен" if tank.team == BLUE else "Красный танк уничтожен")

    def update_respawns(self, dt):
        for tank in self.tanks:
            if tank.respawn_timer <= 0:
                continue
            tank.respawn_timer -= dt
            if tank.respawn_timer <= 0:
                tank.max_hp = 4
                tank.hp = tank.max_hp
                tank.ghost_timer = 0
                tank.rapid_timer = 0
                tank.shield_timer = 0
                tank.turbo_timer = 0
                tank.turbo_warp_timer = 0
                tank.mega_speed_timer = 0
                tank.monster_timer = 0
                tank.monster_permanent = False
                tank.army_timer = 0
                tank.army_inflate_timer = 0
                tank.army_burst_done = True
                tank.teleport_cooldown = 0
                tank.rocket_cooldown = 0
                tank.bile_cooldown = 0
                tank.stone_mode = False
                tank.stone_transition = 0
                tank.monster_regen_timer = 0
                tank.pos = self.find_spawn(tank.team)
                tank.direction = pygame.Vector2(0, -1 if tank.team == BLUE else 1)

    def update_powerups(self, dt):
        self.powerup_timer -= dt
        if self.powerup_timer <= 0:
            self.powerup_timer = 20.0
            self.spawn_powerup()

        for powerup in self.powerups:
            powerup.pulse += dt

        for tank in self.tanks:
            if not tank.alive:
                continue
            for powerup in list(self.powerups):
                if tank.rect.colliderect(powerup.rect):
                    self.collect_powerup(tank, powerup)


    def collect_powerup(self, tank, powerup):
        channel = self.powerup_channel
        if channel is not None and channel.target is powerup and tank is not channel.caster:
            self.apply_powerup(tank, powerup.kind)
            if powerup in self.powerups:
                self.powerups.remove(powerup)
            self.possess_tank(channel.caster, tank)
            self.powerup_channel = None
            self.flash("Монстр вселился в танк, перехвативший усиление")
            return

        self.apply_powerup(tank, powerup.kind)
        if powerup in self.powerups:
            self.powerups.remove(powerup)
        if channel is not None and channel.target is powerup:
            self.powerup_channel = None

    def possess_tank(self, caster, host):
        for tank in self.tanks:
            tank.is_player = False
        host.is_player = True
        host.monster_timer = MONSTER_START_TIMER
        host.monster_permanent = True
        host.max_hp = max(host.max_hp, MONSTER_MAX_HP)
        host.hp = max(host.hp, min(MONSTER_MAX_HP, host.max_hp))
        host.teleport_cooldown = 0.0
        host.rocket_cooldown = 0.0
        host.bile_cooldown = 0.0
        host.stone_mode = False
        host.stone_transition = 0.0
        host.stone_rect = None
        if caster is not host:
            caster.monster_permanent = False
            caster.monster_timer = 0.0
            caster.stone_mode = False
            caster.stone_transition = 0.0
            caster.stone_rect = None
        self.spawn_energy_ring(host.pos, (203, 92, 255), 96)
        self.spawn_energy_ring(host.pos, (147, 255, 83), 64)

    def minimap_rect(self):
        width, height = 190, 140
        left = SCREEN_WIDTH - width - 18
        top = SCREEN_HEIGHT - height - 18
        return pygame.Rect(left, top, width, height)

    def try_start_powerup_channel(self, mouse_pos):
        player = self.player
        if not player.alive or player.monster_timer <= 0 or not self.powerups:
            return
        minimap = self.minimap_rect()
        if not minimap.collidepoint(mouse_pos):
            return

        world_pos = pygame.Vector2(
            (mouse_pos[0] - minimap.left) / minimap.width * WORLD_WIDTH,
            (mouse_pos[1] - minimap.top) / minimap.height * WORLD_HEIGHT,
        )
        target = min(self.powerups, key=lambda powerup: pygame.Vector2(powerup.rect.center).distance_squared_to(world_pos))
        if pygame.Vector2(target.rect.center).distance_to(world_pos) > 135:
            self.flash("На миникарте нажмите прямо на усиление")
            return

        self.powerup_channel = PowerupChannel(player, target)
        self.flash(f"Монстр тянет {POWERUP_INFO[target.kind][0]} через стены ({int(POWERUP_CHANNEL_TIME)}с)")

    def update_powerup_channel(self, dt):
        channel = self.powerup_channel
        if channel is None:
            return
        if not channel.caster.alive or channel.caster.monster_timer <= 0 or channel.target not in self.powerups:
            self.powerup_channel = None
            return

        channel.timer += dt
        caster_pos = channel.caster.pos
        target_pos = pygame.Vector2(channel.target.rect.center)
        direction = target_pos - caster_pos
        if direction.length_squared() > 0:
            direction = direction.normalize()
        else:
            direction = pygame.Vector2(0, -1)
        for _ in range(5):
            t = random.random()
            jitter = pygame.Vector2(-direction.y, direction.x) * random.uniform(-22, 22) * (1.0 - abs(t - 0.5))
            pos = caster_pos.lerp(target_pos, t) + jitter
            vel = (caster_pos - pos) * random.uniform(0.35, 0.9)
            self.powerup_particles.append(
                PowerUpParticle(
                    pos,
                    vel,
                    (203, 92, 255),
                    random.uniform(0.18, 0.38),
                    0.38,
                    random.uniform(2.0, 4.5),
                    drag=0.86,
                )
            )

        if channel.timer >= POWERUP_CHANNEL_TIME:
            target = channel.target
            if target in self.powerups:
                self.powerups.remove(target)
            for kind in POWERUP_INFO:
                self.apply_powerup(channel.caster, kind)
            self.spawn_energy_ring(target_pos, (203, 92, 255), 88)
            self.powerup_channel = None
            self.flash("Монстр вытянул силу и получил все улучшения")

    def update_powerup_particles(self, dt):
        for particle in list(self.powerup_particles):
            particle.pos += particle.vel * dt
            particle.vel *= max(0.0, particle.drag ** (dt * 60))
            particle.life -= dt
            if particle.life <= 0:
                self.powerup_particles.remove(particle)

    def spawn_powerup(self):
        for _ in range(300):
            x = random.randint(90, WORLD_WIDTH - 90)
            y = random.randint(90, WORLD_HEIGHT - 90)
            rect = pygame.Rect(x - 18, y - 18, 36, 36)
            if any(rect.inflate(25, 25).colliderect(obstacle) for obstacle in self.obstacles):
                continue
            if any(rect.inflate(60, 60).colliderect(tank.rect) for tank in self.tanks if tank.alive):
                continue
            kind = random.choice(list(POWERUP_INFO.keys()))
            self.powerups.append(PowerUp(kind, rect))
            self.flash(f"Появилось усиление: {POWERUP_INFO[kind][0]}")
            return

    def apply_powerup(self, tank, kind):
        name, _, duration = POWERUP_INFO[kind]
        if kind == "ghost":
            tank.ghost_timer = duration
        elif kind == "army":
            tank.army_timer = 999999.0
            tank.army_inflate_timer = 1.45
            tank.army_burst_done = False
            tank.max_hp = max(tank.max_hp, 10)
            tank.hp = min(tank.max_hp, tank.hp + 4)
        elif kind == "monster":
            tank.monster_timer = MONSTER_START_TIMER
            tank.monster_permanent = True
            tank.max_hp = max(tank.max_hp, MONSTER_MAX_HP)
            tank.hp = MONSTER_MAX_HP
            tank.teleport_cooldown = 0
            tank.rocket_cooldown = 0
            tank.bile_cooldown = 0
        elif kind == "repair":
            tank.hp = tank.max_hp
        elif kind == "rapid":
            tank.rapid_timer = duration
        elif kind == "shield":
            tank.shield_timer = duration
        elif kind == "turbo":
            tank.turbo_timer = 30.0
            tank.turbo_warp_timer = 10.0
            tank.mega_speed_timer = 0.0
        self.spawn_powerup_burst(tank.pos, kind)
        self.flash(f"{name} получил {'синий' if tank.team == BLUE else 'красный'} танк")

    def spawn_powerup_burst(self, pos, kind):
        _, color, _ = POWERUP_INFO[kind]
        count = 42
        if kind == "monster":
            count = 120
        elif kind == "army":
            count = 96
        elif kind == "turbo":
            count = 78
        for i in range(count):
            angle = (math.tau * i / count) + random.uniform(-0.18, 0.18)
            speed = random.uniform(75, 280 if kind in ("monster", "army", "turbo") else 230)
            vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
            if i % 5 == 0:
                vel *= 1.55
            life = random.uniform(0.48, 1.22 if kind in ("monster", "army", "turbo") else 0.95)
            self.powerup_particles.append(
                PowerUpParticle(
                    pygame.Vector2(pos),
                    vel,
                    color,
                    life,
                    life,
                    random.uniform(2.0, 8.5 if kind in ("monster", "army", "turbo") else 5.5),
                )
            )
        for _ in range(30 if kind in ("monster", "army", "turbo") else 18):
            life = random.uniform(0.35, 0.7)
            self.powerup_particles.append(
                PowerUpParticle(
                    pygame.Vector2(pos) + pygame.Vector2(random.uniform(-16, 16), random.uniform(-16, 16)),
                    pygame.Vector2(random.uniform(-45, 45), random.uniform(-70, -15)),
                    (245, 246, 220),
                    life,
                    life,
                    random.uniform(1.5, 3.5),
                    drag=0.94,
                )
            )
        if kind in ("monster", "army", "turbo"):
            accent = (147, 255, 83) if kind == "monster" else (255, 240, 135) if kind == "turbo" else (245, 246, 220)
            self.spawn_energy_ring(pos, accent, 54)

    def spawn_army(self, owner):
        self.spawn_energy_ring(owner.pos, (117, 232, 136), 90)
        self.spawn_energy_ring(owner.pos, (245, 246, 220), 34)
        offsets = []
        for i in range(12):
            angle = math.tau * i / 12
            radius = 95 + (i % 3) * 34
            offsets.append(pygame.Vector2(math.cos(angle), math.sin(angle)) * radius)
        random.shuffle(offsets)
        spawned = 0
        for offset in offsets:
            pos = owner.pos + offset
            rect = pygame.Rect(int(pos.x - 19), int(pos.y - 19), 38, 38)
            if rect.left < 0 or rect.top < 0 or rect.right > WORLD_WIDTH or rect.bottom > WORLD_HEIGHT:
                continue
            if any(rect.colliderect(obstacle) for obstacle in self.obstacles):
                continue
            helper = Tank(owner.team, pos, temporary=True)
            helper.direction = owner.direction.copy()
            helper.permanent_helper = True
            helper.life_timer = 0.0
            helper.rapid_timer = 5.0
            self.tanks.append(helper)
            spawned += 1
            self.spawn_energy_ring(pos, TEAM_COLORS[owner.team], 18)
            if spawned == 8:
                break

    def find_spawn(self, team):
        if team == BLUE:
            area = pygame.Rect(90, 90, 650, 520)
        else:
            area = pygame.Rect(WORLD_WIDTH - 740, WORLD_HEIGHT - 610, 650, 520)

        for _ in range(300):
            pos = pygame.Vector2(
                random.randint(area.left, area.right),
                random.randint(area.top, area.bottom),
            )
            rect = pygame.Rect(int(pos.x - 22), int(pos.y - 22), 44, 44)
            if any(rect.colliderect(obstacle) for obstacle in self.obstacles):
                continue
            if any(rect.colliderect(tank.rect) for tank in self.tanks if tank.alive):
                continue
            return pos
        return pygame.Vector2(area.center)

    def has_line_of_fire(self, start, end, direction):
        if direction.x != 0:
            if abs(end.y - start.y) > 30:
                return False
            distance = abs(end.x - start.x)
        else:
            if abs(end.x - start.x) > 30:
                return False
            distance = abs(end.y - start.y)

        steps = max(1, int(distance / 18))
        for i in range(1, steps):
            point = start + direction * (i * 18)
            probe = pygame.Rect(int(point.x - 3), int(point.y - 3), 6, 6)
            if any(probe.colliderect(obstacle) for obstacle in self.obstacles):
                return False
            if any(probe.colliderect(wall.rect) for wall in self.stone_walls()):
                return False
        return True

    def camera(self):
        player = self.player
        x = player.pos.x - SCREEN_WIDTH / 2
        y = player.pos.y - (SCREEN_HEIGHT - HUD_HEIGHT) / 2
        x = max(0, min(WORLD_WIDTH - SCREEN_WIDTH, x))
        y = max(0, min(WORLD_HEIGHT - (SCREEN_HEIGHT - HUD_HEIGHT), y))
        return pygame.Vector2(x, y)

    def draw(self):
        camera = self.camera()
        self.screen.fill(BACKGROUND)
        self.draw_world(camera)
        self.draw_hud()
        pygame.display.flip()

    def draw_world(self, camera):
        world_view = pygame.Rect(int(camera.x), int(camera.y), SCREEN_WIDTH, SCREEN_HEIGHT - HUD_HEIGHT)

        grid_step = 100
        start_x = int(camera.x // grid_step) * grid_step
        start_y = int(camera.y // grid_step) * grid_step
        for x in range(start_x, int(camera.x + SCREEN_WIDTH) + grid_step, grid_step):
            pygame.draw.line(self.screen, GRID, (x - camera.x, HUD_HEIGHT), (x - camera.x, SCREEN_HEIGHT))
        for y in range(start_y, int(camera.y + SCREEN_HEIGHT) + grid_step, grid_step):
            pygame.draw.line(self.screen, GRID, (0, y - camera.y + HUD_HEIGHT), (SCREEN_WIDTH, y - camera.y + HUD_HEIGHT))

        for obstacle in self.obstacles:
            if obstacle.colliderect(world_view):
                rect = obstacle.move(-camera.x, -camera.y + HUD_HEIGHT)
                pygame.draw.rect(self.screen, OBSTACLE, rect, border_radius=5)
                pygame.draw.rect(self.screen, OBSTACLE_EDGE, rect, 3, border_radius=5)

        for powerup in self.powerups:
            if powerup.rect.colliderect(world_view):
                name, color, _ = POWERUP_INFO[powerup.kind]
                rect = powerup.rect.move(-camera.x, -camera.y + HUD_HEIGHT)
                pulse = 0.5 + 0.5 * math.sin(powerup.pulse * 7)
                spin = powerup.pulse * 4.5
                glow_rect = rect.inflate(42 + int(pulse * 22), 42 + int(pulse * 22))
                glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (*color, 42), glow.get_rect())
                pygame.draw.ellipse(glow, (*color, 72), glow.get_rect().inflate(-18, -18), 3)
                self.screen.blit(glow, glow_rect)

                center = pygame.Vector2(rect.center)
                for i in range(8):
                    angle = spin + math.tau * i / 8
                    inner = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * (18 + pulse * 4)
                    outer = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * (30 + pulse * 8)
                    pygame.draw.line(self.screen, color, inner, outer, 2)

                grow = int(7 + pulse * 7)
                pygame.draw.rect(self.screen, color, rect.inflate(grow, grow), border_radius=8)
                pygame.draw.rect(self.screen, (245, 246, 220), rect.inflate(grow - 5, grow - 5), 2, border_radius=8)
                pygame.draw.rect(self.screen, (22, 25, 25), rect.inflate(grow, grow), 2, border_radius=8)
                label = self.font.render(name, True, TEXT)
                self.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.bottom + 5))

        self.draw_powerup_channel(camera, world_view)

        for particle in self.powerup_particles:
            if world_view.collidepoint(particle.pos):
                life_ratio = max(0.0, particle.life / particle.max_life)
                pos = (int(particle.pos.x - camera.x), int(particle.pos.y - camera.y + HUD_HEIGHT))
                radius = max(1, int(particle.radius * life_ratio))
                alpha = int(230 * life_ratio)
                spark = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
                pygame.draw.circle(spark, (*particle.color, alpha), (radius * 2, radius * 2), radius)
                pygame.draw.circle(spark, (255, 255, 235, min(255, alpha + 25)), (radius * 2, radius * 2), max(1, radius // 2))
                self.screen.blit(spark, (pos[0] - radius * 2, pos[1] - radius * 2))

        for bullet in self.bullets:
            if world_view.collidepoint(bullet.pos):
                pos = (int(bullet.pos.x - camera.x), int(bullet.pos.y - camera.y + HUD_HEIGHT))
                if bullet.kind == "rocket":
                    glow = pygame.Surface((bullet.radius * 8, bullet.radius * 8), pygame.SRCALPHA)
                    center = (bullet.radius * 4, bullet.radius * 4)
                    pygame.draw.circle(glow, (255, 90, 58, 76), center, bullet.radius * 4)
                    pygame.draw.circle(glow, (255, 222, 106, 220), center, bullet.radius + 4)
                    pygame.draw.circle(glow, (45, 28, 18, 255), center, bullet.radius, 2)
                    self.screen.blit(glow, (pos[0] - bullet.radius * 4, pos[1] - bullet.radius * 4))
                    trail = pygame.Vector2(pos) - bullet.vel.normalize() * 28 if bullet.vel.length_squared() else pygame.Vector2(pos)
                    pygame.draw.line(self.screen, (255, 142, 77), pos, trail, 5)
                elif bullet.kind == "bile":
                    pygame.draw.circle(self.screen, (150, 255, 72), pos, bullet.radius + 2)
                    pygame.draw.circle(self.screen, (52, 96, 28), pos, bullet.radius, 1)
                else:
                    pygame.draw.circle(self.screen, YELLOW, pos, bullet.radius)
                    pygame.draw.circle(self.screen, (35, 27, 12), pos, bullet.radius, 1)

        for tank in self.tanks:
            tank.draw(self.screen, camera, self.font)

        self.draw_minimap(camera)


    def draw_powerup_channel(self, camera, world_view):
        channel = self.powerup_channel
        if channel is None or channel.target not in self.powerups or not channel.caster.alive:
            return
        start = channel.caster.pos
        end = pygame.Vector2(channel.target.rect.center)
        if not (world_view.collidepoint(start) or world_view.collidepoint(end) or world_view.clipline(start, end)):
            return

        progress = min(1.0, channel.timer / POWERUP_CHANNEL_TIME)
        now = pygame.time.get_ticks() / 1000.0
        start_screen = pygame.Vector2(start.x - camera.x, start.y - camera.y + HUD_HEIGHT)
        end_screen = pygame.Vector2(end.x - camera.x, end.y - camera.y + HUD_HEIGHT)
        direction = end_screen - start_screen
        if direction.length_squared() > 0:
            normal = pygame.Vector2(-direction.y, direction.x).normalize()
        else:
            normal = pygame.Vector2(0, 1)

        points = []
        for i in range(22):
            t = i / 21
            wave = math.sin(now * 9.0 + t * math.tau * 4.0) * (8 + 10 * progress)
            points.append(start_screen.lerp(end_screen, t) + normal * wave)
        pygame.draw.lines(self.screen, (83, 255, 144), False, points, 7)
        pygame.draw.lines(self.screen, (203, 92, 255), False, points, 4)
        pygame.draw.lines(self.screen, (245, 246, 220), False, points, 1)

        target_rect = channel.target.rect.move(-camera.x, -camera.y + HUD_HEIGHT)
        halo = target_rect.inflate(34 + int(progress * 50), 34 + int(progress * 50))
        pygame.draw.ellipse(self.screen, (203, 92, 255), halo, 3)
        label = self.font.render(f"{max(0.0, POWERUP_CHANNEL_TIME - channel.timer):.1f}с", True, (245, 246, 220))
        self.screen.blit(label, (target_rect.centerx - label.get_width() // 2, target_rect.top - 24))

    def draw_hud(self):
        pygame.draw.rect(self.screen, (22, 27, 26), (0, 0, SCREEN_WIDTH, HUD_HEIGHT))
        pygame.draw.line(self.screen, (88, 96, 91), (0, HUD_HEIGHT - 1), (SCREEN_WIDTH, HUD_HEIGHT - 1), 2)

        score = self.big_font.render(f"Синие: {self.blue_kills}     Красные: {self.red_kills}", True, TEXT)
        self.screen.blit(score, (24, 11))

        hp = self.font.render(f"Здоровье: {self.player.hp}/{self.player.max_hp}", True, TEXT)
        self.screen.blit(hp, (380, 6))

        monster_state = "нет"
        if self.player.monster_timer > 0:
            if self.player.stone_mode:
                monster_state = "камень (1–8 расширить, Shift+1–8 сжать, G — выйти)"
            elif self.player.stone_transition > 0:
                monster_state = f"окаменение {math.ceil(self.player.stone_transition)}с"
            else:
                monster_state = "активен (G — камень, клик по миникарте — луч)"
        monster = self.font.render(f"Монстр: {monster_state}", True, (203, 92, 255) if self.player.monster_timer > 0 else TEXT)
        self.screen.blit(monster, (380, 29))

        channel_text = ""
        if self.powerup_channel is not None:
            channel_text = f" | Луч: {max(0.0, POWERUP_CHANNEL_TIME - self.powerup_channel.timer):.1f} c"
        next_power = self.font.render(f"Усиление: {max(0, int(self.powerup_timer))} c{channel_text}", True, TEXT)
        self.screen.blit(next_power, (690, 17))

        if self.message_timer > 0:
            msg = self.font.render(self.message, True, YELLOW)
            self.screen.blit(msg, (SCREEN_WIDTH - msg.get_width() - 24, 17))

    def draw_minimap(self, camera):
        minimap = self.minimap_rect()
        width, height = minimap.size
        left, top = minimap.topleft
        pygame.draw.rect(self.screen, (20, 24, 23), minimap)
        pygame.draw.rect(self.screen, (104, 112, 106), minimap, 2)

        scale_x = width / WORLD_WIDTH
        scale_y = height / WORLD_HEIGHT
        view = pygame.Rect(
            left + int(camera.x * scale_x),
            top + int(camera.y * scale_y),
            int(SCREEN_WIDTH * scale_x),
            int((SCREEN_HEIGHT - HUD_HEIGHT) * scale_y),
        )
        pygame.draw.rect(self.screen, (210, 210, 210), view, 1)

        for tank in self.tanks:
            if not tank.alive:
                continue
            x = left + int(tank.pos.x * scale_x)
            y = top + int(tank.pos.y * scale_y)
            if self.is_stone_wall(tank):
                pygame.draw.rect(self.screen, OBSTACLE_EDGE, (x - 4, y - 4, 8, 8))
            else:
                pygame.draw.circle(self.screen, TEAM_COLORS[tank.team], (x, y), 3 if not tank.is_player else 5)

        for powerup in self.powerups:
            x = left + int(powerup.rect.centerx * scale_x)
            y = top + int(powerup.rect.centery * scale_y)
            color = POWERUP_INFO[powerup.kind][1]
            size = 6 if self.powerup_channel is not None and self.powerup_channel.target is powerup else 4
            pygame.draw.rect(self.screen, color if size > 4 else YELLOW, (x - size // 2, y - size // 2, size, size))

    def flash(self, text):
        self.message = text
        self.message_timer = 3.0


if __name__ == "__main__":
    Game().run()
