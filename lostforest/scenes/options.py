"""Settings and controls screens (usable from the title or the pause menu)."""
import pygame

from ..settings import VIEW_W, VIEW_H, TEXT, TEXT_GOLD, TEXT_DIM, SHADOW
from ..core.scene import Scene
from ..ui.widgets import Menu, MenuItem, draw_panel, dim_screen


def _pct(v):
    return f"{int(round(v * 100))}%"


class SettingsScene(Scene):
    overlay = True

    def __init__(self, app):
        super().__init__(app)
        o = app.options

        def vol(key):
            def adjust(d):
                o[key] = max(0.0, min(1.0, round(o[key] + d * 0.1, 2)))
                app.audio.apply_volume()
            return adjust

        def toggle(key):
            def adjust(_d=1):
                o[key] = not o[key]
            return adjust

        def toggle_fs(_d=1):
            app.toggle_fullscreen()

        self.menu = Menu(app, [
            MenuItem("MUSIC", value=lambda: _pct(o["music_volume"]), adjust=vol("music_volume")),
            MenuItem("SOUND FX", value=lambda: _pct(o["sfx_volume"]), adjust=vol("sfx_volume")),
            MenuItem("FULLSCREEN", toggle_fs, value=lambda: "ON" if o["fullscreen"] else "OFF", adjust=toggle_fs),
            MenuItem("SCREEN SHAKE", toggle("screen_shake"), value=lambda: "ON" if o["screen_shake"] else "OFF",
                     adjust=toggle("screen_shake")),
            MenuItem("SHOW FPS", toggle("show_fps"), value=lambda: "ON" if o["show_fps"] else "OFF",
                     adjust=toggle("show_fps")),
            MenuItem("RESET PROGRESS", self._reset),
            MenuItem("BACK", self._back),
        ], width=170, spacing=14)

    def _reset(self):
        from .overlays import ConfirmScene
        self.app.scenes.push(ConfirmScene(self.app, "ERASE ALL PROGRESS?\nTHIS CANNOT BE UNDONE.", self.app.save.reset_progress))

    def _back(self):
        self.app.save.save()
        # apply screen shake to a running level, if any
        for scene in self.app.scenes.stack:
            lvl = getattr(scene, "level", None)
            if lvl is not None:
                lvl.camera.shake_enabled = self.app.options["screen_shake"]
        self.app.scenes.pop()

    def update(self, dt):
        if self.inp.pressed("back"):
            self.audio.play("menu_back")
            self._back()
            return
        self.menu.update(dt)

    def draw(self, surface):
        dim_screen(surface, 170)
        font = self.assets.font
        font.draw(surface, "SETTINGS", (VIEW_W // 2, 40), TEXT_GOLD, 2, SHADOW, align="center")
        h = self.menu.height() + 14
        draw_panel(surface, (VIEW_W // 2 - 110, 70, 220, h))
        self.menu.draw(surface, VIEW_W // 2, 78)
        font.draw(surface, "LEFT / RIGHT TO CHANGE", (VIEW_W // 2, 70 + h + 8), TEXT_DIM, 1, SHADOW, align="center")


CONTROLS = [
    ("MOVE", "A / D", "D-PAD / STICK"),
    ("JUMP", "SPACE", "A"),
    ("DOUBLE JUMP", "SPACE IN MID-AIR", "A IN MID-AIR"),
    ("ATTACK", "LEFT CLICK / X", "X / B"),
    ("COMBO", "ATTACK TWICE", "ATTACK TWICE"),
    ("DASH", "RIGHT CLICK / SHIFT", "RB / LB"),
    ("FAST DROP", "HOLD S IN MID-AIR", "HOLD DOWN"),
    ("DROP THROUGH", "S ON A PLANK", "DOWN ON A PLANK"),
    ("INTERACT", "W", "UP"),
    ("PAUSE", "ESC / P", "START"),
    ("FULLSCREEN", "F11", ""),
]
ROW = 15


class ControlsScene(Scene):
    overlay = True

    def update(self, dt):
        inp = self.inp
        if inp.pressed("back") or inp.pressed("confirm") or inp.pressed("pause") or inp.clicks:
            self.audio.play("menu_back")
            self.app.scenes.pop()

    def draw(self, surface):
        dim_screen(surface, 180)
        font = self.assets.font
        font.draw(surface, "CONTROLS", (VIEW_W // 2, 18), TEXT_GOLD, 2, SHADOW, align="center")
        panel = pygame.Rect(24, 40, VIEW_W - 48, len(CONTROLS) * ROW + 26)
        draw_panel(surface, panel)
        font.draw(surface, "KEYBOARD + MOUSE", (panel.x + 130, panel.y + 8), TEXT_DIM, 1, SHADOW)
        font.draw(surface, "GAMEPAD", (panel.x + 300, panel.y + 8), TEXT_DIM, 1, SHADOW)
        for i, (action, kb, pad) in enumerate(CONTROLS):
            y = panel.y + 22 + i * ROW
            font.draw(surface, action, (panel.x + 12, y), TEXT_GOLD, 1, SHADOW)
            font.draw(surface, kb, (panel.x + 130, y), TEXT, 1, SHADOW)
            font.draw(surface, pad, (panel.x + 300, y), TEXT, 1, SHADOW)
        font.draw(surface, "TIP: DASH WORKS IN MID-AIR. FAST DROP ONTO ENEMIES TO STOMP THEM!",
                  (VIEW_W // 2, panel.bottom + 6), TEXT, 1, SHADOW, align="center")
