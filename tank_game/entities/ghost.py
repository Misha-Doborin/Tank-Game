from tank_game.common import *


class Ghost:
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.direction = pygame.Vector2(0, -1)
        self.speed = TANK_BASE_SPEED * GHOST_SPEED_MULT
        self.host = None
        self.mode = "free"
        self.cooldown = 0.0
        self.tentacle_cooldown = 0.0
        self.giant_cooldown = 0.0
        self.traitor_cooldown = 0.0
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
        self.giant_cooldown = max(0.0, self.giant_cooldown - dt)
        self.traitor_cooldown = max(0.0, self.traitor_cooldown - dt)
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
