from dataclasses import dataclass

import pygame


@dataclass
class Bullet:
    pos: pygame.Vector2
    vel: pygame.Vector2
    team: str
    damage: float
    life: float = 2.4
    radius: int = 5
    kind: str = "bullet"
    splash_radius: int = 0
    source: object = None

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.pos.x - self.radius),
            int(self.pos.y - self.radius),
            self.radius * 2,
            self.radius * 2,
        )


@dataclass
class PowerUp:
    kind: str
    rect: pygame.Rect
    pulse: float = 0.0


@dataclass
class PowerupChannel:
    caster: object
    target: PowerUp
    timer: float = 0.0


@dataclass
class PowerUpParticle:
    pos: pygame.Vector2
    vel: pygame.Vector2
    color: tuple
    life: float
    max_life: float
    radius: float
    drag: float = 0.88
