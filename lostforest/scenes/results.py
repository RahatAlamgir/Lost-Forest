"""Level-complete screen with animated stats, and the ending after the final level."""
import math

import pygame

from ..settings import VIEW_W, VIEW_H, TEXT, TEXT_GOLD, TEXT_GREEN, TEXT_DIM, SHADOW
from ..core.scene import Scene
from ..ui.hud import format_time
from ..ui.widgets import Menu, MenuItem, draw_panel
from .common import backdrop, levels, start_level


class ResultsScene(Scene):
    def __init__(self, app, index, stats):
        super().__init__(app)
        self.index = index
        self.stats = stats
        self.t = 0.0
        self.final = index >= len(levels(app)) - 1
        items = []
        if not self.final:
            items.append(MenuItem("NEXT LEVEL", lambda: start_level(app, index + 1)))
        items += [
            MenuItem("REPLAY", lambda: start_level(app, index)),
            MenuItem("LEVEL SELECT", self._level_select),
            MenuItem("MAIN MENU", self._title),
        ]
        self.menu = Menu(app, items, spacing=13)
        self.coin_shown = 0.0

    def enter(self):
        self.audio.play_music("menu")

    def _level_select(self):
        from .level_select import LevelSelectScene
        self.app.scenes.switch(LevelSelectScene(self.app, selected=min(self.index + 1, len(levels(self.app)) - 1)))

    def _title(self):
        from .title import TitleScene
        self.app.scenes.switch(TitleScene(self.app))

    def update(self, dt):
        self.t += dt
        backdrop(self.app).update(dt)
        target = self.stats["coins"]
        if self.t > 0.6 and self.coin_shown < target:
            before = int(self.coin_shown)
            self.coin_shown = min(target, self.coin_shown + dt * max(12, target * 1.5))
            if int(self.coin_shown) != before:
                self.audio.play("coin", 0.4)
        if self.t > 1.0:
            self.menu.update(dt)

    def draw(self, surface):
        backdrop(self.app).draw(surface)
        font = self.assets.font
        s = self.stats
        data = levels(self.app)[self.index]
        title = "THE FOREST IS SAFE!" if self.final else "LEVEL COMPLETE"
        y = 14 + int(math.sin(self.t * 2) * 1.5)
        font.draw(surface, title, (VIEW_W // 2, y), TEXT_GOLD, 2, SHADOW, align="center")
        font.draw(surface, data.name.upper(), (VIEW_W // 2, y + 20), TEXT, 1, SHADOW, align="center")

        panel = pygame.Rect(VIEW_W // 2 - 125, 50, 250, 96)
        draw_panel(surface, panel, alpha=225)
        rows = [
            ("TIME", format_time(s["time"]), TEXT_GREEN if s.get("new_best") else TEXT,
             "NEW BEST!" if s.get("new_best") else ""),
            ("COINS", f"{int(self.coin_shown)} / {s['coin_total']}",
             TEXT_GOLD if s["coins"] >= s["coin_total"] else TEXT, "ALL!" if s["coins"] >= s["coin_total"] else ""),
            ("ENEMIES", f"{s['enemies']} / {s['enemy_total']}", TEXT, ""),
            ("FALLS", str(s["deaths"]), TEXT, ""),
        ]
        if s.get("has_gem"):
            rows.append(("SECRET GEM", "FOUND" if s["gem"] else "MISSING", (150, 200, 255) if s["gem"] else TEXT_DIM, ""))
        for i, (label, value, color, note) in enumerate(rows):
            if self.t < 0.3 + i * 0.15:
                break
            ry = panel.y + 9 + i * 16
            font.draw(surface, label, (panel.x + 12, ry), TEXT, 1, SHADOW)
            font.draw(surface, value, (panel.x + 165, ry), color, 1, SHADOW, align="right")
            if note:
                font.draw(surface, note, (panel.x + 176, ry), TEXT_GREEN, 1, SHADOW)

        if self.final:
            msg = "THE SHADOWS LIFT AND THE OLD PATHS ARE OPEN AGAIN. THANK YOU FOR PLAYING!"
            for i, line in enumerate(font.wrap(msg, 300)):
                font.draw(surface, line, (VIEW_W // 2, panel.bottom + 6 + i * 10), TEXT, 1, SHADOW, align="center")
        if self.t > 1.0:
            mh = self.menu.height() + 10
            my = VIEW_H - mh - 30 if not self.final else VIEW_H - mh - 26
            draw_panel(surface, (VIEW_W // 2 - 60, my, 120, mh), alpha=215)
            self.menu.draw(surface, VIEW_W // 2, my + 6)
