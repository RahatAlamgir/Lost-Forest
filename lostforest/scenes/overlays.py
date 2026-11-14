"""Overlay scenes drawn on top of another scene: pause, game over, confirmation."""
import pygame

from ..settings import VIEW_W, VIEW_H, TEXT, TEXT_GOLD, TEXT_RED, SHADOW
from ..core.scene import Scene
from ..ui.widgets import Menu, MenuItem, draw_panel, dim_screen


class PauseScene(Scene):
    overlay = True

    def __init__(self, app, game):
        super().__init__(app)
        self.game = game
        self.menu = Menu(app, [
            MenuItem("RESUME", self.resume),
            MenuItem("RESTART LEVEL", self.restart),
            MenuItem("SETTINGS", self.settings),
            MenuItem("CONTROLS", self.controls),
            MenuItem("QUIT TO MENU", self.quit_to_menu),
        ], spacing=14)

    def resume(self):
        self.app.scenes.pop()
        self.inp.reset()

    def restart(self):
        self.game.restart()

    def settings(self):
        from .options import SettingsScene
        self.app.scenes.push(SettingsScene(self.app))

    def controls(self):
        from .options import ControlsScene
        self.app.scenes.push(ControlsScene(self.app))

    def quit_to_menu(self):
        from .title import TitleScene
        self.app.scenes.switch(TitleScene(self.app))

    def update(self, dt):
        if self.inp.pressed("pause") or self.inp.pressed("back"):
            self.audio.play("menu_back")
            self.resume()
            return
        self.menu.update(dt)

    def draw(self, surface):
        dim_screen(surface, 150)
        font = self.assets.font
        font.draw(surface, "PAUSED", (VIEW_W // 2, 62), TEXT_GOLD, 3, SHADOW, align="center")
        h = self.menu.height() + 12
        draw_panel(surface, (VIEW_W // 2 - 70, 100, 140, h))
        self.menu.draw(surface, VIEW_W // 2, 107)
        font.draw(surface, self.game.display_name, (VIEW_W // 2, 100 + h + 10), TEXT, 1, SHADOW, align="center")


class GameOverScene(Scene):
    overlay = True

    def __init__(self, app, game):
        super().__init__(app)
        self.game = game
        self.t = 0.0
        self.menu = Menu(app, [
            MenuItem("TRY AGAIN", self.retry),
            MenuItem("RESTART LEVEL", self.restart),
            MenuItem("QUIT TO MENU", self.quit_to_menu),
        ], spacing=14)

    def retry(self):
        self.app.scenes.pop()
        self.game.retry_from_checkpoint()
        self.inp.reset()

    def restart(self):
        self.game.restart()

    def quit_to_menu(self):
        from .title import TitleScene
        self.app.scenes.switch(TitleScene(self.app))

    def update(self, dt):
        self.t += dt
        self.game.level.particles.update(dt)
        if self.t > 0.4:
            self.menu.update(dt)

    def draw(self, surface):
        dim_screen(surface, int(min(1.0, self.t * 2) * 170))
        font = self.assets.font
        font.draw(surface, "YOU FELL", (VIEW_W // 2, 62), TEXT_RED, 3, SHADOW, align="center")
        font.draw(surface, "THE FOREST IS NOT DONE WITH YOU YET", (VIEW_W // 2, 88), TEXT, 1, SHADOW, align="center")
        h = self.menu.height() + 12
        draw_panel(surface, (VIEW_W // 2 - 70, 110, 140, h))
        self.menu.draw(surface, VIEW_W // 2, 117)


class ConfirmScene(Scene):
    overlay = True

    def __init__(self, app, message, on_yes, on_no=None):
        super().__init__(app)
        self.message = message
        self.on_yes = on_yes
        self.on_no = on_no
        self.menu = Menu(app, [MenuItem("NO", self.no), MenuItem("YES", self.yes)], spacing=14)

    def yes(self):
        self.app.scenes.pop()
        self.on_yes()

    def no(self):
        self.app.scenes.pop()
        if self.on_no:
            self.on_no()

    def update(self, dt):
        if self.inp.pressed("back"):
            self.audio.play("menu_back")
            self.no()
            return
        self.menu.update(dt)

    def draw(self, surface):
        dim_screen(surface, 160)
        font = self.assets.font
        lines = self.message.split("\n")
        w = max(font.line_width(l) for l in lines) + 30
        h = len(lines) * 10 + self.menu.height() + 24
        rect = pygame.Rect((VIEW_W - w) // 2, (VIEW_H - h) // 2, w, h)
        draw_panel(surface, rect)
        for i, line in enumerate(lines):
            font.draw(surface, line, (VIEW_W // 2, rect.y + 9 + i * 10), TEXT, 1, SHADOW, align="center")
        self.menu.draw(surface, VIEW_W // 2, rect.y + 16 + len(lines) * 10)
