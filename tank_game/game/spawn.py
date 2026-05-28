from tank_game.common import *
from tank_game.entities import Ghost, Tank


class SpawnMixin:
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
