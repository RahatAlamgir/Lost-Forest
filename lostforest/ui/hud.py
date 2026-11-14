"""In-game heads-up display: health, coins, key, gem, timer, sign text and level banner."""
import math

import pygame

from ..settings import VIEW_W, VIEW_H, TEXT, TEXT_GOLD, SHADOW
from .widgets import draw_panel


def format_time(t):
    m = int(t // 60)
    s = t - m * 60
    return f"{m}:{s:04.1f}"


class HUD:
    def __init__(self, assets):
        self.assets = assets
        self.font = assets.font
        self.heart = assets.icons["heart"]
        self.heart_empty = assets.icons["heart_empty"]
        self.coin = assets.props["coin"]
        self.key = assets.props["key"]
        self.gem = assets.props["gem"]
        self.gem_dim = self.gem.copy()
        self.gem_dim.fill((70, 70, 80, 160), special_flags=pygame.BLEND_RGBA_MULT)
        self.shown_health = None
        self.pulse = 0.0
        self.coin_bump = 0.0
        self.last_coins = 0

    def update(self, dt, level):
        p = level.player
        if self.shown_health is None:
            self.shown_health = p.health
        if p.health != self.shown_health:
            self.pulse = 0.4
            self.shown_health = p.health
        self.pulse = max(0.0, self.pulse - dt)
        if level.stats["coins"] != self.last_coins:
            self.coin_bump = 0.2
            self.last_coins = level.stats["coins"]
        self.coin_bump = max(0.0, self.coin_bump - dt)

    def draw(self, surface, level, time_alive):
        p = level.player
        font = self.font
        # ---- health
        draw_panel(surface, (4, 4, 8 + p.max_health * 13 + 2, 22), alpha=200)
        for i in range(p.max_health):
            img = self.heart if i < p.health else self.heart_empty
            x = 9 + i * 13
            y = 8
            if self.pulse > 0 and i == p.health - (0 if self.pulse < 0.2 else 0):
                y += int(math.sin(self.pulse * 40) * 2)
            if p.health == 1 and i == 0:
                y += int(math.sin(time_alive * 12) * 1.2)
            surface.blit(img, (x, y))

        # ---- coins / key / gem
        x0 = 4
        draw_panel(surface, (x0, 28, 74, 16), alpha=200)
        cy = 32 - (2 if self.coin_bump > 0.1 else 0)
        surface.blit(self.coin, (x0 + 6, cy - 1))
        font.draw(surface, f"{level.stats['coins']}/{level.coin_total}", (x0 + 16, 33), TEXT, 1, SHADOW)
        if level.has_gem:
            surface.blit(self.gem if level.stats["gem"] else self.gem_dim, (x0 + 60, 31))
        if level.has_key:
            draw_panel(surface, (x0 + 78, 28, 20, 16), alpha=200)
            surface.blit(self.key, (x0 + 82, 32))

        # ---- timer
        t = format_time(level.time)
        w = font.line_width(t) + 12
        draw_panel(surface, (VIEW_W - w - 4, 4, w, 16), alpha=200)
        font.draw(surface, t, (VIEW_W - 10, 9), TEXT, 1, SHADOW, align="right")

        # ---- sign text
        if level.active_sign is not None:
            self._sign_box(surface, level.active_sign.text)

    def _sign_box(self, surface, text):
        font = self.font
        lines = font.wrap(text, 300)
        h = len(lines) * 10 + 12
        w = max(font.line_width(line) for line in lines) + 20
        rect = pygame.Rect((VIEW_W - w) // 2, VIEW_H - h - 10, w, h)
        draw_panel(surface, rect, alpha=230)
        for i, line in enumerate(lines):
            font.draw(surface, line, (VIEW_W // 2, rect.y + 7 + i * 10), TEXT, 1, SHADOW, align="center")

    def draw_banner(self, surface, level, t):
        """Level name card shown when a level starts."""
        if t > 3.0:
            return
        a = min(1.0, t / 0.4) * min(1.0, (3.0 - t) / 0.6)
        a = max(0.0, a)
        name = level.data.name.upper()
        sub = f"LEVEL {level.data.index + 1}"
        img = self.font.render(name, TEXT_GOLD, 2, SHADOW)
        sub_img = self.font.render(sub, TEXT, 1, SHADOW)
        band_h = 44
        band = pygame.Surface((VIEW_W, band_h), pygame.SRCALPHA)
        band.fill((10, 8, 6, int(150 * a)))
        y = 70
        surface.blit(band, (0, y))
        for im, yy in ((sub_img, y + 8), (img, y + 20)):
            im = im.copy()
            im.set_alpha(int(255 * a))
            surface.blit(im, ((VIEW_W - im.get_width()) // 2, yy))
        if level.data.subtitle:
            st = self.font.render(level.data.subtitle, TEXT, 1, SHADOW).copy()
            st.set_alpha(int(220 * a))
            surface.blit(st, ((VIEW_W - st.get_width()) // 2, y + band_h + 4))
