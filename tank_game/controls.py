import pygame

from tank_game.constants import *

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
