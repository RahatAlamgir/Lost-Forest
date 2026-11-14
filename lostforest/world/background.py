"""Layered parallax forest background with per-theme colour grading."""
import random

import pygame

from ..settings import VIEW_W, VIEW_H

THEMES = {
    "green": {
        "tree": "Green", "bush": "bush_green", "leaf": (126, 170, 64),
        "sky": None, "far": (255, 255, 255), "mid": (230, 240, 235), "near": (255, 255, 255),
        "fireflies": False, "ambient": None,
    },
    "golden": {
        "tree": "Golden", "bush": "bush_yellow", "leaf": (226, 182, 64),
        "sky": (255, 236, 200), "far": (255, 236, 190), "mid": (240, 220, 180), "near": (235, 220, 190),
        "fireflies": False, "ambient": (255, 200, 120, 18),
    },
    "autumn": {
        "tree": "Red", "bush": "bush_olive", "leaf": (204, 92, 52),
        "sky": (255, 214, 190), "far": (240, 200, 180), "mid": (220, 180, 160), "near": (220, 190, 170),
        "fireflies": False, "ambient": (255, 140, 80, 22),
    },
    "yellow": {
        "tree": "Yellow", "bush": "bush_yellow", "leaf": (230, 210, 90),
        "sky": (240, 245, 220), "far": (240, 245, 220), "mid": (225, 230, 200), "near": (230, 230, 210),
        "fireflies": False, "ambient": None,
    },
    "dusk": {
        "tree": "Dark", "bush": "bush_dark", "leaf": (150, 120, 170),
        "sky": (120, 100, 170), "far": (110, 100, 160), "mid": (90, 80, 140), "near": (80, 76, 120),
        "fireflies": True, "ambient": (40, 20, 80, 70),
    },
}


def _tint(surface, color):
    if color is None:
        return surface
    s = surface.copy()
    s.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return s


class Background:
    def __init__(self, assets, theme_name, level_w, level_h, seed=0):
        self.theme = THEMES.get(theme_name, THEMES["green"])
        th = self.theme
        self.sky = _tint(assets.sky, th["sky"])
        self.far = _tint(assets.pines_light, th["far"])
        self.near = _tint(assets.pines_dark, th["near"])
        self.level_w = level_w
        self.level_h = level_h
        # sky gradient strip below the cloud picture so tall levels never show black
        self.sky_bottom = self.sky.get_at((self.sky.get_width() // 2, self.sky.get_height() - 2))
        # a row of big silhouetted trees on the mid layer, deterministic per level
        rng = random.Random(seed)
        self.mid_trees = []
        sizes = ["xl", "l", "l", "m"]
        x = -40
        span = int(level_w * 0.32 + VIEW_W + 200)
        while x < span:
            size = rng.choice(sizes)
            img = assets.tree_silhouettes[size]
            img = _tint(img, th["mid"])
            if rng.random() < 0.5:
                img = pygame.transform.flip(img, True, False)
            self.mid_trees.append((x, img))
            x += rng.randint(70, 150)
        self.mid_span = x + 40           # the row of trees repeats after this (endless mode)
        self.ambient = None
        if th["ambient"]:
            self.ambient = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
            self.ambient.fill(th["ambient"])

    def draw(self, surface, cam_x, cam_y):
        surface.fill(self.sky_bottom)
        # vertical parallax: how far down the level the camera is (0..1)
        max_y = max(1, self.level_h - VIEW_H)
        vy = cam_y / max_y
        sky_y = int(-vy * 12)
        surface.blit(self.sky, (0, sky_y))

        base = VIEW_H + 40 - int(vy * 30)
        self._tile_layer(surface, self.far, cam_x * 0.12, base - self.far.get_height() + 10)
        for x, img in self.mid_trees:
            sx = int((x - cam_x * 0.28 + 200) % self.mid_span) - 200
            if -img.get_width() < sx < VIEW_W:
                surface.blit(img, (sx, base + 26 - img.get_height()))
        self._tile_layer(surface, self.near, cam_x * 0.45, base - self.near.get_height() + 70)

    def draw_ambient(self, surface):
        if self.ambient is not None:
            surface.blit(self.ambient, (0, 0))

    @staticmethod
    def _tile_layer(surface, img, offset, y):
        w = img.get_width()
        x = -int(offset) % w - w
        while x < VIEW_W:
            surface.blit(img, (x, int(y)))
            x += w
