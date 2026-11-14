"""Level furniture: checkpoints, exit doors, signs, moving and falling platforms, decoration."""
import math
import random

import pygame

from .base import Entity


class Decoration(Entity):
    """Static image anchored at its bottom-centre. depth: 'back' (behind terrain) or 'front'."""

    def __init__(self, x, bottom, image, depth="front", flip=False):
        w, h = image.get_size()
        super().__init__(x - w / 2, bottom - h, w, h)
        self.image = pygame.transform.flip(image, True, False) if flip else image
        self.depth = depth

    def draw(self, surface, cam_x, cam_y):
        surface.blit(self.image, (round(self.rect.x - cam_x), round(self.rect.y - cam_y)))


class Checkpoint(Entity):
    layer = 1

    def __init__(self, x, bottom, assets):
        super().__init__(x - 8, bottom - 48, 16, 48)
        self.image = assets.props["lamp"]
        self.active = False
        self.t = random.uniform(0, 5)

    def update(self, dt):
        self.t += dt
        p = self.level.player
        if not self.active and not p.is_dead and self.rect.inflate(8, 0).colliderect(p.rect):
            self.activate()
        if self.active and random.random() < dt * 3:
            self.level.particles.firefly(self.rect.centerx + random.uniform(-6, 6), self.rect.top + 8)

    def activate(self):
        self.active = True
        lvl = self.level
        for cp in lvl.objects:
            if isinstance(cp, Checkpoint) and cp is not self:
                cp.active = False
        lvl.checkpoint = (self.rect.centerx + 14, self.rect.bottom)
        lvl.player.heal(lvl.player.max_health)
        lvl.audio.play("checkpoint")
        lvl.particles.sparkle(self.rect.centerx, self.rect.top + 6, (255, 230, 140), 14)
        lvl.popup("CHECKPOINT", self.rect.centerx, self.rect.top - 8, (255, 230, 140))

    def draw(self, surface, cam_x, cam_y):
        x, y = round(self.rect.x - cam_x), round(self.rect.y - cam_y)
        if self.active:
            r = 16 + math.sin(self.t * 5) * 1.5
            glow = pygame.Surface((48, 48), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 210, 120, 50), (24, 24), int(r))
            pygame.draw.circle(glow, (255, 230, 160, 70), (24, 24), int(r * 0.55))
            surface.blit(glow, (x + 8 - 24, y + 6 - 24))
            surface.blit(self.image, (x, y))
        else:
            dim = self.image.copy()
            dim.fill((150, 150, 160, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(dim, (x, y))


class ExitDoor(Entity):
    layer = 1

    def __init__(self, x, bottom, assets, locked=False):
        super().__init__(x - 19, bottom - 54, 38, 54)
        self.image = assets.props["door"]
        self.locked = locked
        self.t = 0.0

    @property
    def prompt(self):
        return True

    def interact(self, player):
        lvl = self.level
        if self.locked and not lvl.has_key:
            lvl.audio.play("locked")
            lvl.popup("LOCKED - FIND THE KEY", self.rect.centerx, self.rect.top - 10, (240, 120, 100))
            return
        if self.locked:
            self.locked = False
        lvl.complete()

    def update(self, dt):
        self.t += dt

    def draw(self, surface, cam_x, cam_y):
        x, y = round(self.rect.x - cam_x), round(self.rect.y - cam_y)
        # warm light spilling from the doorway
        glow = pygame.Surface((70, 70), pygame.SRCALPHA)
        a = 40 + int(12 * math.sin(self.t * 3))
        pygame.draw.circle(glow, (255, 220, 140, a), (35, 35), 32)
        surface.blit(glow, (x + 19 - 35, y + 27 - 35))
        surface.blit(self.image, (x, y))
        if self.locked:
            key = self.level.assets.props["key"]
            surface.blit(key, (x + 13, y - 10 + round(math.sin(self.t * 4))))


class Sign(Entity):
    layer = 1

    def __init__(self, x, bottom, assets, text):
        super().__init__(x - 20, bottom - 34, 40, 34)
        self.post = assets.props["post"]
        self.icon = assets.icons["question"]
        self.text = text
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        if self.rect.colliderect(self.level.player.rect):
            self.level.active_sign = self

    def draw(self, surface, cam_x, cam_y):
        x = round(self.rect.centerx - cam_x)
        y = round(self.rect.bottom - cam_y)
        surface.blit(self.post, (x - 6, y - 34))
        board = pygame.Rect(x - 9, y - 32, 18, 14)
        pygame.draw.rect(surface, (40, 28, 20), board)
        pygame.draw.rect(surface, (156, 112, 70), board.inflate(-2, -2))
        pygame.draw.rect(surface, (120, 84, 52), (board.x + 2, board.bottom - 4, board.w - 4, 1))
        bob = round(math.sin(self.t * 3))
        self.level.assets.font.draw(surface, "?", (x, y - 30 + bob), (60, 40, 25), align="center")


class Platform(Entity):
    """Base for platforms the player can stand on (top surface only)."""
    layer = 2
    solid_platform = True

    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self.dx = 0.0
        self.dy = 0.0
        self.collidable = True

    def carry(self):
        """Move bodies standing on this platform along with it."""
        lvl = self.level
        for body in [lvl.player] + lvl.enemies:
            if getattr(body, "ground_platform", None) is self:
                body.rect.x += self.dx
                body.rect.bottom = self.rect.top


class MovingPlatform(Platform):
    SPEED = 42.0

    def __init__(self, x, y, end, assets):
        super().__init__(x, y + 3, 72, 9)
        self.image = assets.props["log"]
        self.start = pygame.Vector2(self.rect.topleft)
        self.end = pygame.Vector2(end[0], end[1] + 3)
        dist = (self.end - self.start).length()
        self.period = max(1.0, dist / self.SPEED) * 2
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        k = 0.5 - 0.5 * math.cos(self.t / self.period * math.tau)
        pos = self.start.lerp(self.end, k)
        self.dx = pos.x - self.rect.x
        self.dy = pos.y - self.rect.y
        self.rect.topleft = (pos.x, pos.y)
        self.carry()

    def draw(self, surface, cam_x, cam_y):
        surface.blit(self.image, (round(self.rect.x - 1 - cam_x), round(self.rect.y - 4 - cam_y)))


class FallingPlatform(Platform):
    SHAKE_TIME = 0.45
    RESPAWN_TIME = 3.0

    def __init__(self, x, y, assets):
        super().__init__(x, y, 48, 8)
        self.image = assets.props["plank_small"]
        self.home = pygame.Vector2(x, y)
        self.state = "idle"
        self.timer = 0.0
        self.vy = 0.0
        self.alpha = 255

    def update(self, dt):
        lvl = self.level
        self.dx = self.dy = 0.0
        if self.state == "idle":
            if lvl.player.ground_platform is self:
                self.state = "shake"
                self.timer = 0.0
                lvl.audio.play("crumble", 0.6)
        elif self.state == "shake":
            self.timer += dt
            if self.timer >= self.SHAKE_TIME:
                self.state = "fall"
                self.timer = 0.0
                self.vy = 0.0
        elif self.state == "fall":
            self.timer += dt
            self.vy = min(self.vy + 900 * dt, 400)
            self.dy = self.vy * dt
            self.rect.y += self.dy
            if self.timer > 0.6:
                self.collidable = False
            if self.timer > 1.5:
                self.state = "gone"
                self.timer = 0.0
        elif self.state == "gone":
            self.timer += dt
            if self.timer > self.RESPAWN_TIME and not self.rect.move_to(topleft=self.home).colliderect(lvl.player.rect):
                self.rect.topleft = self.home
                self.state = "idle"
                self.collidable = True
                self.alpha = 0
        if self.alpha < 255:
            self.alpha = min(255, self.alpha + dt * 600)
        self.carry()

    def draw(self, surface, cam_x, cam_y):
        if self.state == "gone":
            return
        ox = random.randint(-1, 1) if self.state == "shake" else 0
        img = self.image
        if self.alpha < 255:
            img = img.copy()
            img.set_alpha(int(self.alpha))
        surface.blit(img, (round(self.rect.x + ox - cam_x), round(self.rect.y - cam_y)))
