"""Collectables: coins, the secret gem, potions, keys and treasure chests."""
import math
import random

import pygame

from .base import Body, Entity


class Pickup(Entity):
    layer = 3

    def __init__(self, x, y, image, w=None, h=None):
        iw, ih = image.get_size()
        w = w or iw
        h = h or ih
        super().__init__(x - w / 2, y - h / 2, w, h)
        self.image = image
        self.t = random.uniform(0, 6)
        self.base_y = self.rect.y

    def update(self, dt):
        self.t += dt
        self.rect.y = self.base_y + math.sin(self.t * 3) * 1.5
        player = self.level.player
        if not player.is_dead and self.rect.colliderect(player.rect):
            self.collect(player)

    def collect(self, player):
        self.alive = False

    def draw(self, surface, cam_x, cam_y):
        img = self.image
        surface.blit(img, (round(self.rect.centerx - img.get_width() / 2 - cam_x),
                           round(self.rect.centery - img.get_height() / 2 - cam_y)))


class Coin(Body):
    """Spinning coin. `loose` coins (from chests) fall and bounce."""
    layer = 3

    def __init__(self, x, y, image, loose=False, vx=0.0, vy=0.0):
        super().__init__(x - 4, y - 5, 8, 10)
        self.image = image
        self.t = random.uniform(0, 6)
        self.loose = loose
        self.vx, self.vy = vx, vy
        self.base_y = self.rect.y
        self.pickup_delay = 0.35 if loose else 0.0

    def update(self, dt):
        self.t += dt
        self.pickup_delay = max(0.0, self.pickup_delay - dt)
        if self.loose:
            self.apply_gravity(dt)
            vy_before = self.vy
            self.move(dt)
            if self.on_ground:
                self.vx *= 0.7
                if vy_before > 80:
                    self.vy = -vy_before * 0.4
                    self.on_ground = False
        else:
            self.rect.y = self.base_y + math.sin(self.t * 3) * 1.5
        player = self.level.player
        if self.pickup_delay <= 0 and not player.is_dead and self.rect.inflate(4, 4).colliderect(player.rect):
            self.alive = False
            lvl = self.level
            lvl.stats["coins"] += 1
            lvl.audio.play("coin")
            lvl.particles.sparkle(self.rect.centerx, self.rect.centery)

    def draw(self, surface, cam_x, cam_y):
        sx = abs(math.cos(self.t * 4))
        w = max(1, round(self.image.get_width() * sx))
        img = pygame.transform.scale(self.image, (w, self.image.get_height()))
        surface.blit(img, (round(self.rect.centerx - w / 2 - cam_x), round(self.rect.centery - img.get_height() / 2 - cam_y)))


class Gem(Pickup):
    """One hidden gem per level - saved permanently once found."""

    def update(self, dt):
        super().update(dt)
        if random.random() < dt * 4:
            self.level.particles.sparkle(self.rect.centerx, self.rect.centery, (150, 200, 255), 1)

    def collect(self, player):
        self.alive = False
        lvl = self.level
        lvl.stats["gem"] = True
        lvl.audio.play("gem")
        lvl.particles.ring(self.rect.centerx, self.rect.centery, 16, 90, (150, 200, 255))
        lvl.popup("SECRET GEM FOUND!", self.rect.centerx, self.rect.top - 6, (150, 200, 255))

    def draw(self, surface, cam_x, cam_y):
        glow = pygame.Surface((24, 24), pygame.SRCALPHA)
        a = int(60 + 30 * math.sin(self.t * 4))
        pygame.draw.circle(glow, (120, 180, 255, a), (12, 12), 10)
        surface.blit(glow, (self.rect.centerx - 12 - cam_x, self.rect.centery - 12 - cam_y))
        super().draw(surface, cam_x, cam_y)


class Potion(Pickup):
    def collect(self, player):
        if player.heal(1):
            self.alive = False
            self.level.audio.play("heal")
            self.level.particles.sparkle(self.rect.centerx, self.rect.centery, (255, 120, 120), 8)
            self.level.popup("+1", self.rect.centerx, self.rect.top - 4, (255, 140, 130))


class Key(Pickup):
    def collect(self, player):
        self.alive = False
        lvl = self.level
        lvl.has_key = True
        lvl.audio.play("key")
        lvl.particles.sparkle(self.rect.centerx, self.rect.centery, (255, 220, 120), 10)
        lvl.popup("KEY FOUND", self.rect.centerx, self.rect.top - 6, (255, 220, 120))


class Chest(Entity):
    """Open by attacking it or pressing UP next to it. Spills coins."""
    layer = 2
    COINS = 5

    def __init__(self, x, bottom, assets):
        super().__init__(x - 12, bottom - 18, 24, 18)
        self.closed_img = assets.props["chest"]
        self.open_img = assets.props["chest_open"]
        self.coin_img = assets.props["coin"]
        self.opened = False
        self.shake = 0.0

    def interact(self, player):
        self.open()

    def on_attack(self, player):
        self.open()

    def open(self):
        if self.opened:
            return
        self.opened = True
        lvl = self.level
        lvl.audio.play("chest")
        lvl.particles.sparkle(self.rect.centerx, self.rect.top, (255, 230, 140), 12)
        for i in range(self.COINS):
            vx = random.uniform(-70, 70)
            vy = random.uniform(-260, -180)
            lvl.add(Coin(self.rect.centerx, self.rect.top - 4, self.coin_img, loose=True, vx=vx, vy=vy))

    @property
    def prompt(self):
        return not self.opened

    def draw(self, surface, cam_x, cam_y):
        img = self.open_img if self.opened else self.closed_img
        surface.blit(img, (round(self.rect.centerx - 16 - cam_x), round(self.rect.bottom - 32 - cam_y)))
