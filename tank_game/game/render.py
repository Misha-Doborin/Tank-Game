from tank_game.common import *
from tank_game.entities import Ghost, Tank


class RenderMixin:
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
            state = "Призрак свободен: P вселиться, O дать пассивы; 3 препятствие, 4 гигант, 5 предатель"
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
                timers.append("сила всегда" if host.strength_timer > 9999 else f"сила {host.strength_timer:.0f}")
            if host.speed_timer > 0:
                timers.append("скорость всегда" if host.speed_timer > 9999 else f"скорость {host.speed_timer:.0f}")
            if host.weak_timer > 0:
                timers.append(f"слабость {host.weak_timer:.0f}")
        cooldowns = []
        if self.ghost.tentacle_cooldown > 0:
            cooldowns.append(f"щуп. {self.ghost.tentacle_cooldown:.0f}")
        if self.ghost.giant_cooldown > 0:
            cooldowns.append(f"гигант {self.ghost.giant_cooldown:.0f}")
        if self.ghost.traitor_cooldown > 0:
            cooldowns.append(f"пред. {self.ghost.traitor_cooldown:.0f}")
        status = ' | '.join(timers + cooldowns) if timers or cooldowns else 'обычные танки'
        next_power = self.font.render(f"Усиление: {max(0, int(self.powerup_timer))} c | {status}", True, TEXT)
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
