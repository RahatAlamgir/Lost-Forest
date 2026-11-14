"""Endless Run mode: auto-running survival with score, speed ramp and a saved best score."""
import math

import pygame

from ..settings import VIEW_W, VIEW_H, TEXT, TEXT_GOLD, TEXT_DIM, TEXT_RED, TEXT_GREEN, SHADOW
from ..core.scene import Scene
from ..ui.widgets import Menu, MenuItem, draw_panel, dim_screen
from ..world.runner import RunWorld


class EndlessScene(Scene):
    hide_cursor = True
    display_name = "ENDLESS RUN"
    OVER_DELAY = 1.1

    def __init__(self, app):
        super().__init__(app)
        self.level = RunWorld(app)        # named `level` so pause/settings treat it like one
        self.t = 0.0
        self.over_shown = False
        self.result = None

    def enter(self):
        self.audio.play_music("forest")
        self.inp.reset()

    def restart(self):
        self.app.scenes.switch(EndlessScene(self.app))

    def handle_event(self, event):
        if (event.type == pygame.WINDOWFOCUSLOST and self.level.started
                and not self.level.player.is_dead):
            self.open_pause()

    def open_pause(self):
        from .overlays import PauseScene
        self.audio.play("pause")
        self.app.scenes.push(PauseScene(self.app, self))

    # ------------------------------------------------------------------ loop
    def update(self, dt):
        self.t += dt
        world = self.level
        inp = self.inp
        if not world.started:
            if inp.pressed("jump") or inp.pressed("attack") or inp.pressed("confirm"):
                world.start()
                self.audio.play("menu_select")
            elif inp.pressed("back"):
                from .title import TitleScene
                self.app.scenes.switch(TitleScene(self.app))
                return
        elif inp.pressed("pause") and not world.player.is_dead:
            self.open_pause()
            return
        world.update(dt)

        p = world.player
        if p.is_dead and p.dead_time > self.OVER_DELAY and not self.over_shown:
            self.over_shown = True
            score, dist = world.score, int(world.distance)
            new_best = self.app.save.record_endless(score, dist)
            self.result = {"score": score, "distance": dist, "coins": world.stats["coins"],
                           "kills": world.stats["enemies"], "new_best": new_best,
                           "best": self.app.save.endless["best_score"]}
            self.app.scenes.push(EndlessOverScene(self.app, self))

    # ------------------------------------------------------------------ drawing
    def draw(self, surface):
        world = self.level
        world.draw(surface)
        if world.started:
            self._hud(surface)
        else:
            self._ready(surface)

    def _hud(self, surface):
        font = self.assets.font
        world = self.level
        best = max(self.app.save.endless["best_score"], 0)
        score = world.score
        # score (big) with the best score underneath, top right
        w = 104
        x0 = VIEW_W - w - 4
        draw_panel(surface, (x0, 4, w, 34), alpha=200)
        flash = world.score_flash > 0           # just scored a kill: pulse the score
        color = TEXT_GOLD if (score > best or flash) else TEXT
        font.draw(surface, f"{score:06d}", (VIEW_W - 10, 8 - (1 if flash else 0)), color, 2, SHADOW,
                  align="right")
        font.draw(surface, f"BEST {max(best, score):06d}", (VIEW_W - 10, 26), TEXT_DIM, 1, SHADOW, align="right")
        # distance + coins + speed, top left
        draw_panel(surface, (4, 4, 92, 34), alpha=200)
        font.draw(surface, f"{int(world.distance)} M", (10, 9), TEXT, 1, SHADOW)
        surface.blit(self.assets.props["coin"], (10, 22))
        font.draw(surface, str(world.stats["coins"]), (20, 24), TEXT, 1, SHADOW)
        font.draw(surface, f"SPEED x{world.speed / 150:.1f}", (90, 24), TEXT_DIM, 1, SHADOW, align="right")

    def _ready(self, surface):
        font = self.assets.font
        rec = self.app.save.endless
        bob = int(math.sin(self.t * 2) * 2)
        title = font.render("ENDLESS RUN", TEXT_GOLD, 3, None)
        shadow = font.render("ENDLESS RUN", (30, 22, 14), 3, None)
        x = (VIEW_W - title.get_width()) // 2
        surface.blit(shadow, (x + 2, 36 + bob + 2))
        surface.blit(title, (x, 36 + bob))
        font.draw(surface, "RUN AS FAR AS YOU CAN. ONE HIT AND IT'S OVER.", (VIEW_W // 2, 66), TEXT, 1, SHADOW,
                  align="center")
        draw_panel(surface, (VIEW_W // 2 - 95, 82, 190, 54), alpha=225)
        font.draw(surface, f"BEST SCORE  {rec['best_score']:06d}", (VIEW_W // 2, 90), TEXT_GOLD, 1, SHADOW,
                  align="center")
        font.draw(surface, f"BEST DISTANCE  {rec['best_distance']} M", (VIEW_W // 2, 102), TEXT, 1, SHADOW,
                  align="center")
        font.draw(surface, f"RUNS  {rec['runs']}", (VIEW_W // 2, 114), TEXT_DIM, 1, SHADOW, align="center")
        if int(self.t * 2) % 2 == 0:
            font.draw(surface, "PRESS SPACE OR CLICK TO START", (VIEW_W // 2, 146), TEXT, 1, SHADOW,
                      align="center")
        font.draw(surface, "SPACE JUMP   CLICK ATTACK   SHIFT DASH   S FAST DROP   ESC BACK",
                  (VIEW_W // 2, VIEW_H - 14), TEXT_DIM, 1, SHADOW, align="center")


class EndlessOverScene(Scene):
    """Game-over card for Endless Run."""
    overlay = True

    def __init__(self, app, game):
        super().__init__(app)
        self.game = game
        self.t = 0.0
        self.menu = Menu(app, [
            MenuItem("RUN AGAIN", game.restart),
            MenuItem("MAIN MENU", self._title),
        ], spacing=14)
        if game.result and game.result["new_best"]:
            app.audio.play("gem")

    def _title(self):
        from .title import TitleScene
        self.app.scenes.switch(TitleScene(self.app))

    def update(self, dt):
        self.t += dt
        self.game.level.particles.update(dt)
        if self.t > 0.6:
            self.menu.update(dt)

    def draw(self, surface):
        r = self.game.result
        dim_screen(surface, int(min(1.0, self.t * 2.5) * 160))
        font = self.assets.font
        font.draw(surface, "GAME OVER", (VIEW_W // 2, 34), TEXT_RED, 3, SHADOW, align="center")
        panel = pygame.Rect(VIEW_W // 2 - 100, 66, 200, 86)
        draw_panel(surface, panel)
        rows = [("SCORE", f"{r['score']:06d}", TEXT_GOLD),
                ("DISTANCE", f"{r['distance']} M", TEXT),
                ("COINS", str(r["coins"]), TEXT),
                ("ENEMIES", str(r["kills"]), TEXT),
                ("BEST", f"{r['best']:06d}", TEXT_GREEN if r["new_best"] else TEXT_DIM)]
        for i, (label, value, color) in enumerate(rows):
            y = panel.y + 9 + i * 15
            font.draw(surface, label, (panel.x + 12, y), TEXT, 1, SHADOW)
            font.draw(surface, value, (panel.right - 12, y), color, 1, SHADOW, align="right")
        if r["new_best"] and int(self.t * 3) % 2 == 0:
            font.draw(surface, "NEW BEST SCORE!", (VIEW_W // 2, panel.bottom + 6), TEXT_GOLD, 1, SHADOW,
                      align="center")
        if self.t > 0.6:
            h = self.menu.height() + 12
            draw_panel(surface, (VIEW_W // 2 - 60, panel.bottom + 20, 120, h))
            self.menu.draw(surface, VIEW_W // 2, panel.bottom + 27)
