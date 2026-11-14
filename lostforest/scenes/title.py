"""Title screen and main menu."""
import math

import pygame

from ..settings import VIEW_W, VIEW_H, TEXT, TEXT_GOLD, TEXT_DIM, SHADOW
from ..core.scene import Scene
from ..ui.widgets import Menu, MenuItem, draw_panel
from .common import backdrop, levels, start_level


class TitleScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self._build_menu()

    def _build_menu(self):
        save = self.app.save
        items = []
        if save.has_progress:
            items.append(MenuItem("CONTINUE", self._continue))
        items += [
            MenuItem("NEW GAME", self._new_game),
            MenuItem("SELECT LEVEL", self._level_select),
            MenuItem("ENDLESS RUN", self._endless),
            MenuItem("SETTINGS", self._settings),
            MenuItem("CONTROLS", self._controls),
            MenuItem("QUIT", self.app.quit),
        ]
        self.menu = Menu(self.app, items, spacing=14)

    def enter(self):
        self.audio.prepare_music()
        self.audio.play_music("menu")
        self._build_menu()

    # ------------------------------------------------------------------ actions
    def _continue(self):
        lv = levels(self.app)
        save = self.app.save
        # first unfinished level, or the last one played
        index = min(save.unlocked - 1, len(lv) - 1)
        start_level(self.app, max(0, index))

    def _new_game(self):
        if self.app.save.has_progress:
            from .overlays import ConfirmScene

            def yes():
                self.app.save.reset_progress()
                start_level(self.app, 0)
            self.app.scenes.push(ConfirmScene(self.app, "START A NEW GAME?\nYOUR PROGRESS WILL BE ERASED.", yes))
        else:
            start_level(self.app, 0)

    def _level_select(self):
        from .level_select import LevelSelectScene
        self.app.scenes.switch(LevelSelectScene(self.app))

    def _endless(self):
        from .endless import EndlessScene
        self.app.scenes.switch(EndlessScene(self.app))

    def _settings(self):
        from .options import SettingsScene
        self.app.scenes.push(SettingsScene(self.app))

    def _controls(self):
        from .options import ControlsScene
        self.app.scenes.push(ControlsScene(self.app))

    # ------------------------------------------------------------------ loop
    def update(self, dt):
        self.t += dt
        backdrop(self.app).update(dt)
        if not levels(self.app):
            return
        self.menu.update(dt)

    def draw(self, surface):
        backdrop(self.app).draw(surface)
        font = self.assets.font
        # title with a gentle float
        y = 30 + int(math.sin(self.t * 1.6) * 2)
        title = font.render("LOST FOREST", TEXT_GOLD, 4, None)
        shadow = font.render("LOST FOREST", (30, 22, 14), 4, None)
        x = (VIEW_W - title.get_width()) // 2
        surface.blit(shadow, (x + 3, y + 3))
        surface.blit(title, (x, y))
        font.draw(surface, "A TALE OF SWORD AND LEAF", (VIEW_W // 2, y + 36), TEXT, 1, SHADOW, align="center")

        if not levels(self.app):
            font.draw(surface, "NO LEVELS FOUND IN /levels", (VIEW_W // 2, 140), (255, 120, 100), 1, SHADOW, align="center")
            return
        h = self.menu.height() + 12
        draw_panel(surface, (VIEW_W // 2 - 70, 100, 140, h), alpha=210)
        self.menu.draw(surface, VIEW_W // 2, 107)
        font.draw(surface, "v1.0", (VIEW_W - 4, VIEW_H - 10), TEXT_DIM, 1, SHADOW, align="right")
