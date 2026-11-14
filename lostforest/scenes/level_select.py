"""Level select: shows every level with lock state, best time, coins and gem."""
import math

import pygame

from ..settings import VIEW_W, VIEW_H, TEXT, TEXT_GOLD, TEXT_DIM, TEXT_GREEN, SHADOW
from ..core.scene import Scene
from ..ui.hud import format_time
from ..ui.widgets import draw_panel
from .common import backdrop, levels, start_level

ROW_H = 26
VISIBLE = 6


class LevelSelectScene(Scene):
    def __init__(self, app, selected=None):
        super().__init__(app)
        self.levels = levels(app)
        save = app.save
        default = min(save.unlocked - 1, len(self.levels) - 1)
        self.index = default if selected is None else selected
        self.scroll = 0
        self.t = 0.0
        self.row_rects = {}       # level index -> clickable rect (filled by draw)

    def enter(self):
        self.audio.play_music("menu")

    def unlocked(self, i):
        return i < self.app.save.unlocked

    def update(self, dt):
        self.t += dt
        backdrop(self.app).update(dt)
        inp = self.inp
        n = len(self.levels)
        # mouse: hover selects a row, clicking a row plays it, clicking the footer goes back
        if inp.mouse_moved:
            for i, r in self.row_rects.items():
                if r.collidepoint(inp.mouse_pos) and i != self.index:
                    self.index = i
                    self.audio.play("menu_move")
        for i, r in self.row_rects.items():
            if inp.clicked(r):
                self.index = i
                inp.press("confirm")          # handled just below like a key press
                break
        if inp.clicked(pygame.Rect(0, VIEW_H - 20, VIEW_W, 20)):
            inp.press("back")
        if inp.pressed("down"):
            self.index = (self.index + 1) % n
            self.audio.play("menu_move")
        elif inp.pressed("up"):
            self.index = (self.index - 1) % n
            self.audio.play("menu_move")
        elif inp.pressed("confirm"):
            if self.unlocked(self.index):
                self.audio.play("menu_select")
                start_level(self.app, self.index)
            else:
                self.audio.play("locked")
        elif inp.pressed("back"):
            self.audio.play("menu_back")
            from .title import TitleScene
            self.app.scenes.switch(TitleScene(self.app))
        if self.index < self.scroll:
            self.scroll = self.index
        elif self.index >= self.scroll + VISIBLE:
            self.scroll = self.index - VISIBLE + 1

    def draw(self, surface):
        backdrop(self.app).draw(surface, show_hero=False)
        font = self.assets.font
        font.draw(surface, "SELECT LEVEL", (VIEW_W // 2, 14), TEXT_GOLD, 2, SHADOW, align="center")
        panel = pygame.Rect(40, 40, VIEW_W - 80, VISIBLE * ROW_H + 12)
        draw_panel(surface, panel, alpha=225)
        save = self.app.save
        self.row_rects = {}
        for row in range(VISIBLE):
            i = self.scroll + row
            if i >= len(self.levels):
                break
            data = self.levels[i]
            y = panel.y + 6 + row * ROW_H
            self.row_rects[i] = pygame.Rect(panel.x + 6, y, panel.w - 12, ROW_H - 2)
            selected = i == self.index
            open_ = self.unlocked(i)
            if selected:
                hl = pygame.Surface((panel.w - 12, ROW_H - 2), pygame.SRCALPHA)
                hl.fill((255, 220, 140, 40 + int(20 * math.sin(self.t * 5))))
                surface.blit(hl, (panel.x + 6, y))
            color = TEXT_GOLD if selected else (TEXT if open_ else TEXT_DIM)
            font.draw(surface, f"{i + 1}", (panel.x + 18, y + 9), color, 1, SHADOW, align="center")
            if not open_:
                font.draw(surface, "LOCKED", (panel.x + 34, y + 5), TEXT_DIM, 1, SHADOW)
                font.draw(surface, "FINISH THE PREVIOUS LEVEL", (panel.x + 34, y + 15), TEXT_DIM, 1, SHADOW)
                continue
            font.draw(surface, data.name.upper(), (panel.x + 34, y + 5), color, 1, SHADOW)
            rec = save.level(data.id)
            if rec.get("completed"):
                font.draw(surface, "CLEAR", (panel.x + 34, y + 15), TEXT_GREEN, 1, SHADOW)
                font.draw(surface, f"BEST {format_time(rec['best_time'])}", (panel.x + 72, y + 15), TEXT, 1, SHADOW)
            else:
                font.draw(surface, "NEW", (panel.x + 34, y + 15), TEXT_DIM, 1, SHADOW)
            # coins + gem on the right
            right = panel.right - 14
            coins = rec.get("best_coins", 0)
            surface.blit(self.assets.props["coin"], (right - 74, y + 8))
            font.draw(surface, f"{coins}/{data.coin_total}", (right - 64, y + 9), color, 1, SHADOW)
            if data.has_gem:
                gem = self.assets.props["gem"]
                if not rec.get("gem"):
                    gem = gem.copy()
                    gem.fill((60, 60, 70, 140), special_flags=pygame.BLEND_RGBA_MULT)
                surface.blit(gem, (right - 10, y + 7))
        if self.scroll > 0:
            font.draw(surface, "^", (VIEW_W // 2, panel.y - 8), TEXT, 1, SHADOW, align="center")
        if self.scroll + VISIBLE < len(self.levels):
            font.draw(surface, "MORE", (VIEW_W // 2, panel.bottom + 2), TEXT, 1, SHADOW, align="center")
        font.draw(surface, "ENTER / CLICK: PLAY    ESC: BACK", (VIEW_W // 2, VIEW_H - 14), TEXT, 1, SHADOW,
                  align="center")
