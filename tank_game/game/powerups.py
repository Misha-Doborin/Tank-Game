from tank_game.common import *
from tank_game.entities import Ghost, Tank


class PowerupMixin:
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
        host.strength_timer = MONSTER_START_TIMER
        host.speed_timer = MONSTER_START_TIMER
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
