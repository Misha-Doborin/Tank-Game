from tank_game.common import *
from tank_game.entities import Ghost, Tank


class GhostActionsMixin:
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
        target.strength_timer = MONSTER_START_TIMER
        target.speed_timer = MONSTER_START_TIMER
        self.ghost.pos = target.pos.copy()
        self.spawn_energy_ring(target.pos, (126, 216, 255), 64)
        self.flash(
            "Призрак управляет танком: сила 30 и скорость x3 включены всегда"
            if control
            else "Призрак дал танку волю: сила 30 и скорость x3 включены всегда"
        )
    def release_ghost_host(self, apply_weakness=True):
        host = self.ghost.host
        if host is not None:
            host.is_player = False
            host.strength_timer = 0.0
            host.speed_timer = 0.0
            if apply_weakness and host.alive:
                host.weak_timer = 15.0
                self.flash("После выселения танк ослаблен на 15 секунд")
            self.ghost.pos = host.pos.copy()
        self.ghost.host = None
        self.ghost.mode = "free"
    def ghost_power_target(self):
        return self.ghost.host if self.ghost.host is not None and self.ghost.host.alive else None
    def apply_ghost_strength(self):
        self.flash("Сила теперь постоянная: вселись в танк, и атака сразу станет 30")
    def apply_ghost_speed(self):
        self.flash("Скорость теперь постоянная: вселись в танк, и скорость сразу станет x3")
    def ghost_eat_obstacle(self):
        if self.ghost.tentacle_cooldown > 0:
            self.flash(f"Щупальце перезаряжается: {math.ceil(self.ghost.tentacle_cooldown)}с")
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
        self.ghost.tentacle_cooldown = GHOST_SUPER_COOLDOWN
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
        if self.ghost.giant_cooldown > 0:
            self.flash(f"Гигант перезаряжается: {math.ceil(self.ghost.giant_cooldown)}с")
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
        self.ghost.giant_cooldown = GHOST_SUPER_COOLDOWN
        self.spawn_energy_ring(center, (255, 88, 62), 180)
        self.flash("Гигант взорвался и разбросал танки по краям карты")
    def ghost_make_traitor(self):
        if self.ghost.traitor_cooldown > 0:
            self.flash(f"Предатель перезаряжается: {math.ceil(self.ghost.traitor_cooldown)}с")
            return
        target = self.nearest_tank(enemy=True, max_distance=330)
        if target is None:
            self.flash("Щупальце не достало вражеский танк")
            return
        origin = self.ghost.active_pos
        self.spawn_tentacle_effect(origin, target.pos, (86, 255, 120))
        target.traitor_timer = TRAITOR_TIME
        target.strength_timer = TRAITOR_TIME
        self.ghost.traitor_cooldown = GHOST_SUPER_COOLDOWN
        target.hp = min(target.max_hp, target.hp + 20)
        self.flash("Враг изрыгнут предателем: 30 секунд он бьёт своих и не трогает чужих")
