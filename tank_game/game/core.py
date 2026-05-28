from tank_game.common import *
from tank_game.entities import Ghost, Tank
from tank_game.game.ai import AIMixin
from tank_game.game.combat import CombatMixin
from tank_game.game.ghost_actions import GhostActionsMixin
from tank_game.game.movement import MovementMixin
from tank_game.game.powerups import PowerupMixin
from tank_game.game.render import RenderMixin
from tank_game.game.spawn import SpawnMixin


class Game(SpawnMixin, GhostActionsMixin, AIMixin, MovementMixin, CombatMixin, PowerupMixin, RenderMixin):
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
    def flash(self, text):
        self.message = text
        self.message_timer = 3.0
