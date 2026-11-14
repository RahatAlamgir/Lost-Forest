"""The main play scene: runs a Level, the HUD, pausing, death and completion flow."""
import pygame

from ..core.scene import Scene
from ..ui.hud import HUD
from ..world.level import Level
from .common import levels


class GameplayScene(Scene):
    hide_cursor = True        # the mouse is used for attack / dash, so hide the pointer while playing
    DEATH_DELAY = 1.6
    EXIT_DELAY = 1.3

    def __init__(self, app, index):
        super().__init__(app)
        self.index = index
        self.data = levels(app)[index]
        self.level = Level(self.data, app)
        self.hud = HUD(app.assets)
        self.t = 0.0
        self.exit_timer = 0.0
        self.finished = False
        self.game_over_shown = False

    @property
    def display_name(self):
        return self.data.name.upper()

    def enter(self):
        self.audio.play_music(self.data.music)
        self.inp.reset()

    # ------------------------------------------------------------------ events
    def handle_event(self, event):
        if event.type == pygame.WINDOWFOCUSLOST and not self.level.completed and not self.level.player.is_dead:
            self.open_pause()

    def open_pause(self):
        from .overlays import PauseScene
        self.audio.play("pause")
        self.app.scenes.push(PauseScene(self.app, self))

    def restart(self):
        self.app.scenes.switch(GameplayScene(self.app, self.index))

    def retry_from_checkpoint(self):
        self.level.respawn_player()
        self.game_over_shown = False
        self.hud.shown_health = None

    # ------------------------------------------------------------------ loop
    def update(self, dt):
        self.t += dt
        lvl = self.level
        if self.inp.pressed("pause") and not lvl.completed and not lvl.player.is_dead:
            self.open_pause()
            return
        lvl.update(dt)
        self.hud.update(dt, lvl)

        if lvl.player.is_dead and lvl.player.dead_time > self.DEATH_DELAY and not self.game_over_shown:
            self.game_over_shown = True
            from .overlays import GameOverScene
            self.app.scenes.push(GameOverScene(self.app, self))

        if lvl.completed and not self.finished:
            self.exit_timer += dt
            if self.exit_timer > self.EXIT_DELAY:
                self.finished = True     # only report the result once
                self._finish()

    def _finish(self):
        from .results import ResultsScene
        lvl = self.level
        stats = dict(lvl.stats)
        stats["time"] = lvl.time
        stats["coin_total"] = lvl.coin_total
        stats["enemy_total"] = lvl.enemy_total
        stats["has_gem"] = lvl.has_gem
        new_best = self.app.save.record_result(self.index, self.data.id, lvl.time, stats["coins"], stats["gem"])
        stats["new_best"] = new_best
        self.audio.stop_music(300)
        self.app.scenes.switch(ResultsScene(self.app, self.index, stats))

    def draw(self, surface):
        self.level.draw(surface)
        if not self.level.completed:
            self.hud.draw(surface, self.level, self.t)
        self.hud.draw_banner(surface, self.level, self.t)
        if self.level.completed:
            # fade to warm light as the hero walks through the door
            k = max(0.0, min(1.0, self.exit_timer / self.EXIT_DELAY))
            veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            veil.fill((255, 236, 190, int(200 * k)))
            surface.blit(veil, (0, 0))
