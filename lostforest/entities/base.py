"""Entity base class and tile/platform collision for physics bodies."""
import math

import pygame

from ..settings import TILE, GRAVITY, MAX_FALL_SPEED
from ..world.tiles import SOLID, ONEWAY


class Entity:
    """Anything that lives in the level. `rect` is the hitbox (pygame.FRect)."""

    solid_platform = False      # moving/falling platforms set this
    layer = 0                   # draw order: lower first

    def __init__(self, x, y, w, h):
        self.rect = pygame.FRect(x, y, w, h)
        self.alive = True
        self.level = None

    @property
    def center(self):
        return self.rect.center

    def update(self, dt):
        pass

    def draw(self, surface, cam_x, cam_y):
        pass


class Body(Entity):
    """An entity with velocity that collides with tiles and platforms."""

    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.ground_platform = None
        self.hit_wall = 0          # -1 left, +1 right
        self.hit_ceiling = False
        self.drop_through = 0.0    # timer: ignore one-way platforms while > 0
        self.gravity_scale = 1.0

    def apply_gravity(self, dt):
        self.vy = min(self.vy + GRAVITY * self.gravity_scale * dt, MAX_FALL_SPEED)

    def move(self, dt):
        """Move by velocity, resolving collisions axis by axis."""
        tm = self.level.tilemap
        self.hit_wall = 0
        self.hit_ceiling = False
        if self.drop_through > 0:
            self.drop_through -= dt

        # ---- horizontal
        dx = self.vx * dt
        if dx:
            self.rect.x += dx
            for tx, ty in tm.cells_in_rect(self.rect):
                if tm.kind(tx, ty) == SOLID:
                    if dx > 0:
                        self.rect.right = tx * TILE
                        self.hit_wall = 1
                    else:
                        self.rect.left = (tx + 1) * TILE
                        self.hit_wall = -1
                    self.vx = 0.0
                    break

        # ---- vertical
        dy = self.vy * dt
        old_bottom = self.rect.bottom
        self.rect.y += dy
        was_on_ground = self.on_ground
        self.on_ground = False
        self.ground_platform = None
        if dy > 0:
            landed_y = None
            for tx, ty in tm.cells_in_rect(self.rect):
                k = tm.kind(tx, ty)
                top = ty * TILE
                if k == SOLID:
                    landed_y = top if landed_y is None else min(landed_y, top)
                elif k == ONEWAY and self.drop_through <= 0 and old_bottom <= top + 0.5:
                    landed_y = top if landed_y is None else min(landed_y, top)
            # platforms (moving logs, falling planks)
            if self.drop_through <= 0:
                for p in self.level.platforms:
                    if not p.collidable:
                        continue
                    pr = p.rect
                    if (self.rect.right > pr.left and self.rect.left < pr.right
                            and old_bottom <= pr.top + max(0.0, p.dy) + 1.0 and self.rect.bottom >= pr.top):
                        if landed_y is None or pr.top <= landed_y:
                            landed_y = pr.top
                            self.ground_platform = p
            if landed_y is not None:
                self.rect.bottom = landed_y
                self.vy = 0.0
                self.on_ground = True
            else:
                self.ground_platform = None
        elif dy < 0:
            for tx, ty in tm.cells_in_rect(self.rect):
                if tm.kind(tx, ty) == SOLID:
                    self.rect.top = (ty + 1) * TILE
                    self.vy = 0.0
                    self.hit_ceiling = True
                    break
        return was_on_ground

    def ground_ahead(self, direction, probe=2):
        """True if there is ground just beyond our leading foot (used by walking AI)."""
        tm = self.level.tilemap
        x = self.rect.right + probe if direction > 0 else self.rect.left - probe
        tx = int(math.floor(x / TILE))
        ty = int(math.floor((self.rect.bottom + 1) / TILE))
        return tm.kind(tx, ty) in (SOLID, ONEWAY)

    def wall_ahead(self, direction, probe=1):
        tm = self.level.tilemap
        x = self.rect.right + probe if direction > 0 else self.rect.left - probe
        tx = int(math.floor(x / TILE))
        ty = int(math.floor((self.rect.bottom - 2) / TILE))
        ty2 = int(math.floor((self.rect.top + 1) / TILE))
        return tm.kind(tx, ty) == SOLID or tm.kind(tx, ty2) == SOLID
