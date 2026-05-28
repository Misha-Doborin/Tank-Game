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

BACKGROUND = (50, 122, 56)
GRID = (66, 148, 74)
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
GHOST_TEAM = BLUE
GHOST_SPEED_MULT = 3.0
TANK_BASE_HP = 60
TANK_BASE_DAMAGE = 12.5
TANK_BASE_SPEED = 220.0
GHOST_ABILITY_TIME = 15.0
TRAITOR_TIME = 30.0
GIANT_TIME = 15.0

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
    damage: float
    life: float = 2.4
    radius: int = 5
    kind: str = "bullet"
    splash_radius: int = 0
    source: object = None

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


class Ghost:
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.direction = pygame.Vector2(0, -1)
        self.speed = TANK_BASE_SPEED * GHOST_SPEED_MULT
        self.host = None
        self.mode = "free"
        self.cooldown = 0.0
        self.tentacle_cooldown = 0.0
        self.giant_timer = 0.0
        self.giant_tanks = []
        self.giant_guns = []
        self.selected_gun = 0
        self.absorb_timer = 0.0
        self.size_bonus = 0

    @property
    def alive(self):
        return True

    @property
    def controlling_tank(self):
        return self.host is not None and self.mode == "control" and self.giant_timer <= 0

    @property
    def blessing_tank(self):
        return self.host is not None and self.mode == "bless" and self.giant_timer <= 0

    @property
    def active_pos(self):
        if self.giant_timer > 0:
            return self.pos
        if self.host is not None and self.host.alive:
            return self.host.pos
        return self.pos

    @property
    def giant_size(self):
        return 142 + self.size_bonus

    def update_timers(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.tentacle_cooldown = max(0.0, self.tentacle_cooldown - dt)
        self.absorb_timer = max(0.0, self.absorb_timer - dt)
        if self.absorb_timer <= 0:
            self.size_bonus = 0

    def draw(self, surface, camera, font):
        now = pygame.time.get_ticks() / 1000.0
        screen_pos = pygame.Vector2(self.active_pos.x - camera.x, self.active_pos.y - camera.y + HUD_HEIGHT)
        if self.giant_timer > 0:
            self.draw_giant(surface, screen_pos, font, now)
            return
        if self.host is not None:
            return

        pulse = 0.5 + 0.5 * math.sin(now * 6.5)
        radius = 24 + int(pulse * 7) + self.size_bonus
        ghost = pygame.Surface((radius * 5, radius * 5), pygame.SRCALPHA)
        center = pygame.Vector2(radius * 2.5, radius * 2.5)
        for i in range(10):
            angle = now * 1.7 + math.tau * i / 10
            end = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * (radius * (1.25 + 0.25 * math.sin(now * 4 + i)))
            pygame.draw.line(ghost, (35, 4, 46, 130), center, end, 5)
            pygame.draw.circle(ghost, (106, 12, 138, 105), end, 5)
        pygame.draw.ellipse(ghost, (18, 2, 28, 170), (radius, radius, radius * 3, radius * 3))
        pygame.draw.ellipse(ghost, (155, 226, 255, 60), (radius - 8, radius - 8, radius * 3 + 16, radius * 3 + 16), 3)
        eye_y = int(center.y - radius * 0.25)
        pygame.draw.circle(ghost, (255, 72, 96, 240), (int(center.x - radius * 0.42), eye_y), 5)
        pygame.draw.circle(ghost, (255, 72, 96, 240), (int(center.x + radius * 0.42), eye_y), 5)
        pygame.draw.arc(ghost, (230, 230, 240, 180), (center.x - radius * 0.6, center.y, radius * 1.2, radius * 0.7), 0.1, math.pi - 0.1, 2)
        surface.blit(ghost, (screen_pos.x - center.x, screen_pos.y - center.y))
        label = font.render("ПРИЗРАК", True, (184, 232, 255))
        surface.blit(label, (screen_pos.x - label.get_width() // 2, screen_pos.y + radius + 10))

    def draw_giant(self, surface, screen_pos, font, now):
        radius = self.giant_size
        body_rect = pygame.Rect(int(screen_pos.x - radius), int(screen_pos.y - radius * 0.72), radius * 2, int(radius * 1.44))
        giant = pygame.Surface(body_rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(giant, (24, 28, 30, 245), giant.get_rect())
        pygame.draw.ellipse(giant, (60, 72, 74, 240), giant.get_rect().inflate(-20, -24), 4)
        pygame.draw.ellipse(giant, (33, 105, 58, 230), giant.get_rect().inflate(-46, -54))
        center = pygame.Vector2(body_rect.width / 2, body_rect.height / 2)
        for i, angle in enumerate(self.giant_guns):
            mount = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * (radius * 0.58)
            end = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * (radius * 1.05)
            color = (245, 230, 120) if i == self.selected_gun else (20, 24, 24)
            pygame.draw.line(giant, color, mount, end, 10)
            pygame.draw.circle(giant, (16, 18, 18), mount, 12)
        surface.blit(giant, body_rect)
        label = font.render(f"ГИГАНТ {math.ceil(self.giant_timer)}с", True, (255, 214, 122))
        surface.blit(label, (screen_pos.x - label.get_width() // 2, body_rect.bottom + 6))


class Tank:
    def __init__(self, team, pos, is_player=False, temporary=False):
        self.team = team
        self.pos = pygame.Vector2(pos)
        self.is_player = is_player
        self.temporary = temporary
        self.direction = pygame.Vector2(0, -1 if team == BLUE else 1)
        self.speed = 220.0
        self.set_tank_stats()
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
        self.recoil_timer = 0.0
        self.strength_timer = 0.0
        self.speed_timer = 0.0
        self.weak_timer = 0.0
        self.traitor_timer = 0.0
        self.absorb_timer = 0.0
        self.absorb_hp_bonus = 0
        self.absorb_size_bonus = 0
        self.in_giant = False

    def set_tank_stats(self):
        self.max_hp = TANK_BASE_HP
        self.damage_mult = TANK_BASE_DAMAGE
        self.speed = TANK_BASE_SPEED
        self.hp = self.max_hp

    @property
    def alive(self):
        return not self.in_giant and self.respawn_timer <= 0.0 and self.hp > 0

    @property
    def size(self):
        base = 52 if self.monster_timer > 0 else 38
        return base + self.absorb_size_bonus

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
        if self.speed_timer > 0:
            speed *= 3.0
        if self.weak_timer > 0:
            speed *= 0.45
        if self.stone_transition > 0:
            return 0.0
        return speed

    @property
    def shoot_delay(self):
        if self.rapid_timer > 0:
            return 0.28
        return 1.05

    @property
    def bullet_damage(self):
        base = 2 if self.monster_timer > 0 else 1
        damage = 30.0 if self.strength_timer > 0 else base * self.damage_mult
        if self.weak_timer > 0:
            damage *= 0.45
        return max(1.0, damage)

    def update_timers(self, dt):
        was_monster = self.monster_timer > 0
        was_warping = self.turbo_warp_timer > 0
        self.cooldown = max(0.0, self.cooldown - dt)
        self.recoil_timer = max(0.0, self.recoil_timer - dt)
        self.teleport_cooldown = max(0.0, self.teleport_cooldown - dt)
        self.rocket_cooldown = max(0.0, self.rocket_cooldown - dt)
        self.bile_cooldown = max(0.0, self.bile_cooldown - dt)
        self.ghost_timer = max(0.0, self.ghost_timer - dt)
        self.rapid_timer = max(0.0, self.rapid_timer - dt)
        self.strength_timer = max(0.0, self.strength_timer - dt)
        self.speed_timer = max(0.0, self.speed_timer - dt)
        self.weak_timer = max(0.0, self.weak_timer - dt)
        self.traitor_timer = max(0.0, self.traitor_timer - dt)
        if self.absorb_timer > 0:
            self.absorb_timer = max(0.0, self.absorb_timer - dt)
            if self.absorb_timer <= 0 and self.absorb_hp_bonus:
                old_bonus = self.absorb_hp_bonus
                self.max_hp = max(TANK_BASE_HP, self.max_hp - old_bonus)
                self.hp = min(self.hp, self.max_hp)
                self.absorb_hp_bonus = 0
                self.absorb_size_bonus = 0
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
            self.set_tank_stats()
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
        if self.recoil_timer > 0:
            rect = rect.move(int(-self.direction.x * 5), int(-self.direction.y * 5))
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
        base_rect = body.get_rect()
        shadow = pygame.Rect(3, 5, rect.width - 6, rect.height - 6)
        hull = pygame.Rect(6, 4, rect.width - 12, rect.height - 8)
        pygame.draw.rect(body, (9, 12, 12, alpha), shadow, border_radius=7)
        pygame.draw.rect(body, (*color, alpha), hull, border_radius=6)
        pygame.draw.rect(body, (18, 22, 22, alpha), hull, 3, border_radius=6)

        track_color = (16, 18, 18, alpha)
        rubber = (35, 39, 38, alpha)
        left_track = pygame.Rect(1, 3, 9, rect.height - 6)
        right_track = pygame.Rect(rect.width - 10, 3, 9, rect.height - 6)
        pygame.draw.rect(body, track_color, left_track, border_radius=4)
        pygame.draw.rect(body, track_color, right_track, border_radius=4)
        for y in range(7, rect.height - 6, 7):
            pygame.draw.line(body, rubber, (2, y), (9, y + 2), 2)
            pygame.draw.line(body, rubber, (rect.width - 9, y + 2), (rect.width - 2, y), 2)

        panel = hull.inflate(-12, -14)
        pygame.draw.rect(body, (min(color[0] + 28, 255), min(color[1] + 28, 255), min(color[2] + 28, 255), alpha), panel, border_radius=4)
        pygame.draw.line(body, (235, 240, 230, min(alpha, 80)), (panel.left + 3, panel.top + 2), (panel.right - 4, panel.top + 1), 1)

        center = pygame.Vector2(rect.width / 2, rect.height / 2)
        barrel_end = center + self.direction * (rect.width * 0.68)
        barrel_root = center + self.direction * (rect.width * 0.12)
        pygame.draw.line(body, (8, 10, 10, alpha), barrel_root, barrel_end, 9)
        pygame.draw.line(body, (58, 64, 62, alpha), barrel_root, barrel_end, 4)
        muzzle = barrel_end + self.direction * 4
        pygame.draw.circle(body, (8, 9, 9, alpha), (int(muzzle.x), int(muzzle.y)), 4)
        pygame.draw.circle(body, (29, 34, 33, alpha), center, max(9, rect.width // 4))
        pygame.draw.circle(body, (75, 82, 80, alpha), center, max(5, rect.width // 7))
        if self.traitor_timer > 0:
            pygame.draw.line(body, (92, 255, 118, alpha), (5, 5), (rect.width - 5, rect.height - 5), 3)
            pygame.draw.line(body, (92, 255, 118, alpha), (rect.width - 5, 5), (5, rect.height - 5), 3)

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
        labels.append(("ТАНК", (245,246,220)))
        if self.is_player:
            labels.append(("ИГРОК", TEXT))
        if self.traitor_timer > 0:
            labels.append((f"ПРЕДАТЕЛЬ {math.ceil(self.traitor_timer)}", (92, 255, 118)))
        if self.strength_timer > 0:
            labels.append((f"СИЛА {math.ceil(self.strength_timer)}", (255, 92, 92)))
        if self.speed_timer > 0:
            labels.append((f"СКОРОСТЬ {math.ceil(self.speed_timer)}", (255, 230, 90)))
        if self.weak_timer > 0:
            labels.append((f"СЛАБ {math.ceil(self.weak_timer)}", (170, 170, 190)))
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
        self.ghost = Ghost((WORLD_WIDTH / 2, WORLD_HEIGHT / 2))

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
        blue_spawns = [(250 + (i % 5) * 90, 250 + (i // 5) * 90) for i in range(10)]
        red_spawns = [(WORLD_WIDTH - 250 - (i % 5) * 90, WORLD_HEIGHT - 250 - (i // 5) * 90) for i in range(10)]

        for pos in blue_spawns:
            self.tanks.append(Tank(BLUE, pos))
        for pos in red_spawns:
            self.tanks.append(Tank(RED, pos))

    @property
    def player(self):
        return self.ghost.host if self.ghost.host is not None else self.ghost

    @property
    def ghost_actor_pos(self):
        return self.ghost.active_pos

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
                self.ghost_fire()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                self.try_possess_nearest(control=True)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_o:
                self.try_possess_nearest(control=False)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_x:
                self.release_ghost_host()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_1:
                self.apply_ghost_strength()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_2:
                self.apply_ghost_speed()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_3:
                self.ghost_eat_obstacle()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_4:
                self.start_giant_tank()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_5:
                self.ghost_make_traitor()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                self.select_giant_gun(-1)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                self.select_giant_gun(1)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_z:
                self.rotate_selected_giant_gun(-0.22)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                self.rotate_selected_giant_gun(0.22)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_t and self.ghost.host is not None:
                self.try_monster_teleport(self.ghost.host)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r and self.ghost.host is not None:
                self.try_fire_rocket(self.ghost.host)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_f and self.ghost.host is not None:
                self.try_spray_bile(self.ghost.host)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.try_start_powerup_channel(event.pos)

    def update(self, dt):
        keys = pygame.key.get_pressed()
        player_move = pygame.Vector2()
        for key, direction in DIRS.items():
            if keys[key]:
                player_move = direction
                break

        self.ghost.update_timers(dt)
        if self.ghost.giant_timer > 0:
            self.update_giant(dt, player_move)
        elif self.ghost.controlling_tank and self.ghost.host.alive:
            self.move_tank(self.ghost.host, player_move, dt)
        elif self.ghost.host is None:
            self.move_ghost(player_move, dt)
        elif self.ghost.host is not None and not self.ghost.host.alive:
            self.release_ghost_host(apply_weakness=False)

        for tank in list(self.tanks):
            tank.update_timers(dt)
            if tank.temporary and not tank.permanent_helper and tank.life_timer <= 0:
                self.tanks.remove(tank)
                continue
            if tank.alive and tank.army_inflate_timer <= 0 and not tank.army_burst_done:
                tank.army_burst_done = True
                self.spawn_army(tank)
            if tank.alive and not (self.ghost.controlling_tank and tank is self.ghost.host):
                self.update_ai(tank, dt)

        self.update_bullets(dt)
        self.update_respawns(dt)
        self.update_powerups(dt)
        self.update_powerup_particles(dt)
        self.update_powerup_channel(dt)
        self.message_timer = max(0.0, self.message_timer - dt)

    def move_ghost(self, direction, dt):
        if direction.length_squared() == 0:
            return
        self.ghost.direction = direction
        self.ghost.pos += direction * self.ghost.speed * dt
        self.ghost.pos.x = max(16, min(WORLD_WIDTH - 16, self.ghost.pos.x))
        self.ghost.pos.y = max(16, min(WORLD_HEIGHT - 16, self.ghost.pos.y))

    def ghost_anchor(self):
        if self.ghost.host is not None and self.ghost.host.alive:
            return self.ghost.host
        return None

    def nearest_tank(self, team=None, enemy=False, max_distance=180):
        origin = self.ghost.active_pos
        candidates = []
        for tank in self.tanks:
            if not tank.alive:
                continue
            if enemy and tank.team == GHOST_TEAM:
                continue
            if team is not None and tank.team != team:
                continue
            candidates.append(tank)
        if not candidates:
            return None
        tank = min(candidates, key=lambda t: t.pos.distance_squared_to(origin))
        return tank if tank.pos.distance_to(origin) <= max_distance else None

    def try_possess_nearest(self, control):
        target = self.nearest_tank(team=GHOST_TEAM, max_distance=230)
        if target is None:
            self.flash("Рядом нет синего танка для вселения")
            return
        self.release_ghost_host(apply_weakness=self.ghost.host is not None and self.ghost.host is not target)
        self.ghost.host = target
        self.ghost.mode = "control" if control else "bless"
        target.is_player = control
        self.ghost.pos = target.pos.copy()
        self.spawn_energy_ring(target.pos, (126, 216, 255), 64)
        self.flash("Призрак управляет танком" if control else "Призрак дал танку волю, но оставил способности")

    def release_ghost_host(self, apply_weakness=True):
        host = self.ghost.host
        if host is not None:
            host.is_player = False
            if apply_weakness and host.alive:
                host.weak_timer = 15.0
                self.flash("После выселения танк ослаблен на 15 секунд")
            self.ghost.pos = host.pos.copy()
        self.ghost.host = None
        self.ghost.mode = "free"

    def ghost_power_target(self):
        return self.ghost.host if self.ghost.host is not None and self.ghost.host.alive else None

    def apply_ghost_strength(self):
        target = self.ghost_power_target() or self.nearest_tank(team=GHOST_TEAM, max_distance=260)
        if target is None:
            self.flash("Сила требует синий танк рядом или вселение")
            return
        target.strength_timer = GHOST_ABILITY_TIME
        self.spawn_energy_ring(target.pos, (255, 92, 92), 52)
        self.flash("Сила: атака танка стала 30 на 15 секунд")

    def apply_ghost_speed(self):
        target = self.ghost_power_target() or self.nearest_tank(team=GHOST_TEAM, max_distance=260)
        if target is None:
            self.flash("Скорость требует синий танк рядом или вселение")
            return
        target.speed_timer = GHOST_ABILITY_TIME
        self.spawn_energy_ring(target.pos, (255, 230, 90), 52)
        self.flash("Скорость: танк стал в 3 раза быстрее на 15 секунд")

    def ghost_eat_obstacle(self):
        if self.ghost.tentacle_cooldown > 0:
            return
        origin = self.ghost.active_pos
        direction = self.ghost.direction if self.ghost.direction.length_squared() else pygame.Vector2(0, -1)
        best = None
        best_dist = 999999
        for obstacle in self.obstacles:
            center = pygame.Vector2(obstacle.center)
            to_obstacle = center - origin
            projection = to_obstacle.dot(direction)
            side = abs(to_obstacle.x * direction.y - to_obstacle.y * direction.x)
            if 0 < projection < 320 and side < 95 and projection < best_dist:
                best = obstacle
                best_dist = projection
        if best is None:
            self.flash("Щупальце не нашло препятствие впереди")
            return
        self.obstacles.remove(best)
        self.ghost.tentacle_cooldown = 1.2
        target = self.ghost_power_target()
        if target is not None:
            target.absorb_timer = GHOST_ABILITY_TIME
            target.absorb_hp_bonus += 35
            target.absorb_size_bonus += 10
            target.max_hp += 35
            target.hp = min(target.max_hp, target.hp + 35)
        else:
            self.ghost.absorb_timer = GHOST_ABILITY_TIME
            self.ghost.size_bonus = 12
        self.spawn_tentacle_effect(origin, pygame.Vector2(best.center), (122, 15, 148))
        self.flash("Щупальце съело препятствие: размер и здоровье усилены на 15 секунд")

    def spawn_tentacle_effect(self, start, end, color):
        direction = end - start
        for i in range(36):
            t = i / 35
            point = start.lerp(end, t)
            wobble = pygame.Vector2(-direction.y, direction.x)
            if wobble.length_squared():
                wobble = wobble.normalize() * math.sin(t * math.tau * 3) * 16
            self.powerup_particles.append(PowerUpParticle(point + wobble, pygame.Vector2(), color, 0.55, 0.55, 5.0, drag=0.9))

    def start_giant_tank(self):
        if self.ghost.giant_timer > 0:
            return
        team_tanks = [tank for tank in self.tanks if tank.team == GHOST_TEAM and tank.alive]
        if len(team_tanks) < 10:
            self.flash("Гиганту нужны все 10 синих танков живыми")
            return
        self.release_ghost_host(apply_weakness=False)
        self.ghost.giant_timer = GIANT_TIME
        self.ghost.giant_tanks = team_tanks[:10]
        self.ghost.giant_guns = [math.tau * i / 10 for i in range(10)]
        self.ghost.selected_gun = 0
        self.ghost.pos = self.ghost.active_pos.copy()
        for tank in self.ghost.giant_tanks:
            tank.in_giant = True
            tank.is_player = False
            tank.pos = self.ghost.pos.copy()
        self.spawn_energy_ring(self.ghost.pos, (255, 214, 122), 140)
        self.flash("Призрак съел 10 танков и стал гигантом с 10 пушками на 15 секунд")

    def update_giant(self, dt, direction):
        self.ghost.giant_timer = max(0.0, self.ghost.giant_timer - dt)
        if direction.length_squared():
            self.ghost.direction = direction
            self.ghost.pos += direction * TANK_BASE_SPEED * 0.65 * dt
            r = self.ghost.giant_size
            self.ghost.pos.x = max(r, min(WORLD_WIDTH - r, self.ghost.pos.x))
            self.ghost.pos.y = max(r, min(WORLD_HEIGHT - r, self.ghost.pos.y))
        if self.ghost.giant_timer <= 0:
            self.end_giant_tank()

    def select_giant_gun(self, delta):
        if not self.ghost.giant_guns:
            return
        self.ghost.selected_gun = (self.ghost.selected_gun + delta) % len(self.ghost.giant_guns)

    def rotate_selected_giant_gun(self, delta):
        if self.ghost.giant_timer <= 0 or not self.ghost.giant_guns:
            return
        i = self.ghost.selected_gun
        self.ghost.giant_guns[i] = (self.ghost.giant_guns[i] + delta) % math.tau

    def ghost_fire(self):
        if self.ghost.giant_timer > 0:
            if self.ghost.cooldown > 0:
                return
            for angle in self.ghost.giant_guns:
                direction = pygame.Vector2(math.cos(angle), math.sin(angle))
                muzzle = self.ghost.pos + direction * (self.ghost.giant_size * 0.8)
                self.bullets.append(Bullet(muzzle, direction * 720, GHOST_TEAM, 30.0, life=2.4, radius=6, source=self.ghost))
            self.ghost.cooldown = 0.8
            self.spawn_energy_ring(self.ghost.pos, (255, 214, 122), 22)
        elif self.ghost.controlling_tank:
            self.try_shoot(self.ghost.host)
        else:
            self.flash("Пробел стреляет только в танке или гиганте")

    def end_giant_tank(self):
        center = self.ghost.pos.copy()
        tanks = list(self.ghost.giant_tanks)
        for tank in tanks:
            tank.in_giant = False
            tank.set_tank_stats()
            tank.pos = self.find_edge_spawn(tank)
            tank.direction = self.cardinal_direction(center - tank.pos)
        self.ghost.giant_tanks = []
        self.ghost.giant_guns = []
        self.ghost.giant_timer = 0.0
        self.spawn_energy_ring(center, (255, 88, 62), 180)
        self.flash("Гигант взорвался и разбросал танки по краям карты")

    def find_edge_spawn(self, tank):
        margins = [
            pygame.Rect(50, 50, WORLD_WIDTH - 100, 120),
            pygame.Rect(50, WORLD_HEIGHT - 170, WORLD_WIDTH - 100, 120),
            pygame.Rect(50, 50, 120, WORLD_HEIGHT - 100),
            pygame.Rect(WORLD_WIDTH - 170, 50, 120, WORLD_HEIGHT - 100),
        ]
        for _ in range(600):
            area = random.choice(margins)
            pos = pygame.Vector2(random.randint(area.left, area.right), random.randint(area.top, area.bottom))
            rect = pygame.Rect(int(pos.x - 22), int(pos.y - 22), 44, 44)
            if any(rect.colliderect(obstacle) for obstacle in self.obstacles):
                continue
            if any(other is not tank and other.alive and rect.colliderect(other.rect) for other in self.tanks):
                continue
            return pos
        return pygame.Vector2(90, 90)

    def ghost_make_traitor(self):
        target = self.nearest_tank(enemy=True, max_distance=330)
        if target is None:
            self.flash("Щупальце не достало вражеский танк")
            return
        origin = self.ghost.active_pos
        self.spawn_tentacle_effect(origin, target.pos, (86, 255, 120))
        target.traitor_timer = TRAITOR_TIME
        target.strength_timer = TRAITOR_TIME
        target.hp = min(target.max_hp, target.hp + 20)
        self.flash("Враг изрыгнут предателем: 30 секунд он бьёт своих и не трогает чужих")

    def update_ai(self, tank, dt):
        if tank.stone_mode or tank.stone_transition > 0:
            return
        if tank.traitor_timer > 0:
            enemies = [
                t
                for t in self.tanks
                if t is not tank and t.team == tank.team and t.alive and not self.is_stone_wall(t)
            ]
        else:
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
        old_stone_rect = tank.stone_rect.copy() if tank.stone_rect is not None else None
        delta = direction * tank.current_speed * dt

        if tank.stone_mode and tank.stone_rect is not None:
            rect = tank.stone_rect.move(int(delta.x), int(delta.y))
            if rect.left < 0:
                rect.move_ip(-rect.left, 0)
            if rect.right > WORLD_WIDTH:
                rect.move_ip(WORLD_WIDTH - rect.right, 0)
            if rect.top < 0:
                rect.move_ip(0, -rect.top)
            if rect.bottom > WORLD_HEIGHT:
                rect.move_ip(0, WORLD_HEIGHT - rect.bottom)
            tank.stone_rect = rect
            tank.pos = pygame.Vector2(rect.center)
        else:
            tank.pos += delta
            tank.pos.x = max(tank.size / 2, min(WORLD_WIDTH - tank.size / 2, tank.pos.x))
            tank.pos.y = max(tank.size / 2, min(WORLD_HEIGHT - tank.size / 2, tank.pos.y))

        if tank.ghost_timer <= 0 and any(tank.rect.colliderect(obstacle) for obstacle in self.obstacles):
            tank.pos = old
            tank.stone_rect = old_stone_rect
            return False

        for other in self.tanks:
            if other is tank or not other.alive:
                continue
            if tank.rect.colliderect(other.rect):
                tank.pos = old
                tank.stone_rect = old_stone_rect
                return False
        return True


    def handle_stone_resize_key(self, event):
        resize_actions = {
            pygame.K_1: ("north", "expand"),
            pygame.K_2: ("south", "expand"),
            pygame.K_3: ("east", "expand"),
            pygame.K_4: ("west", "expand"),
            pygame.K_5: ("north", "shrink"),
            pygame.K_6: ("south", "shrink"),
            pygame.K_7: ("east", "shrink"),
            pygame.K_8: ("west", "shrink"),
            pygame.K_KP1: ("north", "expand"),
            pygame.K_KP2: ("south", "expand"),
            pygame.K_KP3: ("east", "expand"),
            pygame.K_KP4: ("west", "expand"),
            pygame.K_KP5: ("north", "shrink"),
            pygame.K_KP6: ("south", "shrink"),
            pygame.K_KP7: ("east", "shrink"),
            pygame.K_KP8: ("west", "shrink"),
        }
        if event.key not in resize_actions:
            return
        boundary, action = resize_actions[event.key]
        self.adjust_stone_wall(self.player, boundary, action)

    def adjust_stone_wall(self, tank, boundary, action):
        if not self.is_stone_wall(tank):
            return

        rect = tank.rect
        if boundary == "north":
            rect.top += -STONE_RESIZE_STEP if action == "expand" else STONE_RESIZE_STEP
        elif boundary == "south":
            rect.bottom += STONE_RESIZE_STEP if action == "expand" else -STONE_RESIZE_STEP
        elif boundary == "east":
            rect.right += STONE_RESIZE_STEP if action == "expand" else -STONE_RESIZE_STEP
        elif boundary == "west":
            rect.left += -STONE_RESIZE_STEP if action == "expand" else STONE_RESIZE_STEP

        if rect.width < STONE_MIN_SIZE or rect.height < STONE_MIN_SIZE:
            self.flash("Каменная стена уже минимальна")
            return
        if rect.left < 0 or rect.top < 0 or rect.right > WORLD_WIDTH or rect.bottom > WORLD_HEIGHT:
            self.flash("Граница мира не даёт изменить стену")
            return
        if any(rect.colliderect(other.rect) for other in self.tanks if other is not tank and other.alive):
            self.flash("Нельзя менять стену сквозь танк")
            return

        tank.stone_rect = rect
        tank.pos = pygame.Vector2(rect.center)
        boundary_names = {"north": "северная", "south": "южная", "east": "восточная", "west": "западная"}
        action_text = "вытянута" if action == "expand" else "втянута"
        self.flash(f"{boundary_names[boundary].capitalize()} граница {action_text}")

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
        kind = "traitor" if tank.traitor_timer > 0 else "bullet"
        self.bullets.append(Bullet(muzzle, tank.direction * speed, tank.team, tank.bullet_damage, kind=kind, source=tank))
        tank.recoil_timer = 0.15
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
                if not tank.alive:
                    continue
                if bullet.kind == "traitor":
                    if tank.team != bullet.team or tank is bullet.source:
                        continue
                elif tank.team == bullet.team:
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
            if self.ghost.host is tank:
                self.release_ghost_host(apply_weakness=False)
            self.flash("Синий танк уничтожен" if tank.team == BLUE else "Красный танк уничтожен")

    def update_respawns(self, dt):
        for tank in self.tanks:
            if tank.respawn_timer <= 0:
                continue
            tank.respawn_timer -= dt
            if tank.respawn_timer <= 0:
                tank.set_tank_stats()
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
                tank.strength_timer = 0
                tank.speed_timer = 0
                tank.weak_timer = 0
                tank.traitor_timer = 0
                tank.absorb_timer = 0
                tank.absorb_hp_bonus = 0
                tank.absorb_size_bonus = 0
                tank.in_giant = False
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
        if channel is not None and channel.target is powerup:
            self.apply_powerup(tank, powerup.kind)
            if powerup in self.powerups:
                self.powerups.remove(powerup)
            self.powerup_channel = None
            self.flash("Танк перехватил притягиваемое усиление")
            return

        self.apply_powerup(tank, powerup.kind)
        if powerup in self.powerups:
            self.powerups.remove(powerup)
        if channel is not None and channel.target is powerup:
            self.powerup_channel = None

    def possess_tank(self, caster, host):
        if host not in self.tanks or not host.alive:
            return
        self.release_ghost_host(apply_weakness=self.ghost.host is not None and self.ghost.host is not host)
        self.ghost.host = host
        self.ghost.mode = "control"
        host.is_player = True
        self.ghost.pos = host.pos.copy()
        self.spawn_energy_ring(host.pos, (203, 92, 255), 96)
        self.spawn_energy_ring(host.pos, (147, 255, 83), 64)

    def minimap_rect(self):
        width, height = 190, 140
        left = SCREEN_WIDTH - width - 18
        top = SCREEN_HEIGHT - height - 18
        return pygame.Rect(left, top, width, height)

    def try_start_powerup_channel(self, mouse_pos):
        player = self.ghost
        if not self.powerups:
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
        if not channel.caster.alive or channel.target not in self.powerups:
            self.powerup_channel = None
            return

        channel.timer += dt
        caster_pos = channel.caster.active_pos if isinstance(channel.caster, Ghost) else channel.caster.pos
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
            recipient = self.ghost_power_target() or self.nearest_tank(team=GHOST_TEAM, max_distance=420)
            if recipient is not None:
                for kind in POWERUP_INFO:
                    self.apply_powerup(recipient, kind)
            self.spawn_energy_ring(target_pos, (203, 92, 255), 88)
            self.powerup_channel = None
            self.flash("Призрак вытянул силу через миникарту")

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
            kind = random.choice([kind for kind in POWERUP_INFO if kind != "army"])
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
        player_pos = self.ghost_actor_pos
        x = player_pos.x - SCREEN_WIDTH / 2
        y = player_pos.y - (SCREEN_HEIGHT - HUD_HEIGHT) / 2
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

        self.ghost.draw(self.screen, camera, self.font)
        self.draw_minimap(camera)


    def draw_powerup_channel(self, camera, world_view):
        channel = self.powerup_channel
        if channel is None or channel.target not in self.powerups or not channel.caster.alive:
            return
        start = channel.caster.active_pos if isinstance(channel.caster, Ghost) else channel.caster.pos
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

        if self.ghost.giant_timer > 0:
            state = f"Гигант: {math.ceil(self.ghost.giant_timer)}с | пушка {self.ghost.selected_gun + 1}/10"
        elif self.ghost.host is None:
            state = "Призрак свободен: P вселиться, O дать способности, 1 сила, 2 скорость, 3 препятствие, 4 гигант, 5 предатель"
        elif self.ghost.mode == "control":
            state = f"Управление танком HP {self.ghost.host.hp:.0f}/{self.ghost.host.max_hp} | X выйти"
        else:
            state = f"Танк сам едет HP {self.ghost.host.hp:.0f}/{self.ghost.host.max_hp} | способности доступны | X выйти"
        info = self.font.render(state, True, (184, 232, 255))
        self.screen.blit(info, (380, 6))

        timers = []
        host = self.ghost.host
        if host is not None:
            if host.strength_timer > 0:
                timers.append(f"сила {host.strength_timer:.0f}")
            if host.speed_timer > 0:
                timers.append(f"скорость {host.speed_timer:.0f}")
            if host.weak_timer > 0:
                timers.append(f"слабость {host.weak_timer:.0f}")
        next_power = self.font.render(f"Усиление: {max(0, int(self.powerup_timer))} c | {' | '.join(timers) if timers else 'обычные танки'}", True, TEXT)
        self.screen.blit(next_power, (380, 29))

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

        ghost_x = left + int(self.ghost.active_pos.x * scale_x)
        ghost_y = top + int(self.ghost.active_pos.y * scale_y)
        pygame.draw.circle(self.screen, (184, 232, 255), (ghost_x, ghost_y), 5, 1)

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
