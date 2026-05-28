from tank_game.common import *
from tank_game.entities import Ghost, Tank


class CombatMixin:
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
