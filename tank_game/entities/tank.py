from tank_game.common import *


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
            text = "СИЛА" if self.strength_timer > 9999 else f"СИЛА {math.ceil(self.strength_timer)}"
            labels.append((text, (255, 92, 92)))
        if self.speed_timer > 0:
            text = "СКОРОСТЬ" if self.speed_timer > 9999 else f"СКОРОСТЬ {math.ceil(self.speed_timer)}"
            labels.append((text, (255, 230, 90)))
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
