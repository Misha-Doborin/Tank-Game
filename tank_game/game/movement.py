from tank_game.common import *
from tank_game.entities import Ghost, Tank


class MovementMixin:
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
