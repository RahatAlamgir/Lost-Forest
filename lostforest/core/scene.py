"""Scene base class and a stack-based scene manager with fade transitions."""
import pygame

from ..settings import VIEW_W, VIEW_H


class Scene:
    """Base scene. Overlays (pause, game over) set `overlay = True` so the scene
    below them keeps being drawn (but not updated)."""

    overlay = False

    def __init__(self, app):
        self.app = app

    @property
    def assets(self):
        return self.app.assets

    @property
    def inp(self):
        return self.app.input

    @property
    def audio(self):
        return self.app.audio

    def enter(self):
        pass

    def exit(self):
        pass

    def handle_event(self, event):
        pass

    def update(self, dt):
        pass

    def draw(self, surface):
        pass


class SceneManager:
    FADE_TIME = 0.28

    def __init__(self):
        self.stack = []
        self._pending = None          # (callable that mutates the stack)
        self._fade = 0.0              # 0 = clear, 1 = black
        self._fade_dir = 0
        self._fade_surface = pygame.Surface((VIEW_W, VIEW_H))
        self._fade_surface.fill((0, 0, 0))

    @property
    def top(self):
        return self.stack[-1] if self.stack else None

    @property
    def transitioning(self):
        return self._fade_dir != 0

    # ------------------------------------------------------------------ stack ops
    def switch(self, scene, fade=True):
        """Replace the whole stack with `scene`."""
        def action():
            while self.stack:
                self.stack.pop().exit()
            self.stack.append(scene)
            scene.enter()
        self._run(action, fade)

    def push(self, scene):
        self.stack.append(scene)
        scene.enter()

    def pop(self):
        if self.stack:
            self.stack.pop().exit()

    def _run(self, action, fade):
        if fade:
            # the newest request wins if one is already fading out
            self._pending = action
            self._fade_dir = 1
        else:
            self._pending = None
            self._fade_dir = -1 if self._fade > 0 else 0
            action()

    # ------------------------------------------------------------------ loop
    def handle_event(self, event):
        if self.top and not self.transitioning:
            self.top.handle_event(event)

    def update(self, dt):
        if self._fade_dir == 1:
            self._fade = min(1.0, self._fade + dt / self.FADE_TIME)
            if self._fade >= 1.0:
                if self._pending:
                    self._pending()
                    self._pending = None
                self._fade_dir = -1
            return
        if self._fade_dir == -1:
            self._fade = max(0.0, self._fade - dt / self.FADE_TIME)
            if self._fade <= 0.0:
                self._fade_dir = 0
        if self.top:
            self.top.update(dt)

    def draw(self, surface):
        # draw from the last non-overlay scene upwards
        start = len(self.stack) - 1
        while start > 0 and self.stack[start].overlay:
            start -= 1
        for scene in self.stack[max(0, start):]:
            scene.draw(surface)
        if self._fade > 0:
            self._fade_surface.set_alpha(int(255 * self._fade))
            surface.blit(self._fade_surface, (0, 0))
