"""Animated forest scene used behind menus: scrolling parallax, ground and the running hero."""
import random

import pygame

from ..settings import VIEW_W, VIEW_H, TILE
from ..core.particles import ParticleSystem
from ..world.background import Background


class MenuBackdrop:
    def __init__(self, assets, theme="green", run=True):
        self.assets = assets
        self.bg = Background(assets, theme, 4000, VIEW_H, seed=7)
        self.cam_x = 0.0
        self.t = 0.0
        self.run = run
        self.particles = ParticleSystem()
        self.leaf = self.bg.theme["leaf"]
        # ground strip: grass top + middle row
        self.ground = pygame.Surface((TILE * 6, TILE * 3), pygame.SRCALPHA)
        for i in range(6):
            col = 1 + i % 3
            self.ground.blit(assets.tile(col, 0), (i * TILE, 0))
            self.ground.blit(assets.tile(col, 1), (i * TILE, TILE))
            self.ground.blit(assets.tile(col, 2), (i * TILE, TILE * 2))
        self.bush = assets.props["bush_green"]
        self.trees = [assets.trees["Green"]["m"], assets.trees["Green"]["s"], assets.trees["Green"]["l"]]
        rng = random.Random(3)
        self.scenery = []
        x = 0
        while x < 2400:
            kind = rng.choice(["tree", "tree", "bush", "mush"])
            self.scenery.append((x, kind, rng.randrange(3)))
            x += rng.randint(60, 140)

    def update(self, dt):
        self.t += dt
        if self.run:
            self.cam_x += 45 * dt
        self.particles.update(dt)
        if random.random() < dt * 3:
            self.particles.leaf(random.uniform(0, VIEW_W + 60), -6, self.leaf)

    def draw(self, surface, show_hero=True):
        cam = int(self.cam_x)
        self.bg.draw(surface, cam, 0)
        ground_y = VIEW_H - 34
        span = 2400
        for x, kind, var in self.scenery:
            sx = int((x - cam * 0.9) % span) - 100
            if kind == "tree":
                img = self.trees[var]
                surface.blit(img, (sx, ground_y + 8 - img.get_height()))
            elif kind == "bush":
                surface.blit(self.bush, (sx, ground_y + 8 - self.bush.get_height()))
        gw = self.ground.get_width()
        x = -(cam % gw)
        while x < VIEW_W:
            surface.blit(self.ground, (x, ground_y - TILE))
            x += gw
        for x, kind, var in self.scenery:
            if kind == "mush":
                img = self.assets.props["mushroom_s" if var else "mushroom_l"]
                sx = int((x - cam) % span) - 100
                surface.blit(img, (sx, ground_y - img.get_height()))
        if show_hero:
            anim = self.assets.player["run" if self.run else "idle"]
            anim.draw(surface, self.t, (VIEW_W // 2 - 120, ground_y), 1)
        self.particles.draw(surface, 0, 0)
