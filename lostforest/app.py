"""Application shell: window, main loop with fixed timestep, global hotkeys."""
import os
import sys

import pygame

from . import settings as S
from .core.assets import Assets
from .core.audio import Audio, SR
from .core.input import Input
from .core.save import SaveData
from .core.scene import SceneManager


class App:
    def __init__(self, headless=False):
        self.headless = headless
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.mixer.pre_init(SR, -16, 2, 512)
        pygame.init()
        if pygame.mixer.get_init() is None:
            try:
                pygame.mixer.init(SR, -16, 2, 512)
            except pygame.error:
                print("[audio] no audio device - running silent")

        self.save = SaveData()
        self.options = self.save.options
        pygame.display.set_caption(S.TITLE)
        self._create_window()
        self._set_icon()

        self.clock = pygame.time.Clock()
        # simulate at the monitor's refresh rate so every displayed frame gets exactly one update
        self.sim_hz = self._refresh_rate()
        self.dt = 1.0 / self.sim_hz
        self.assets = Assets()
        self.input = Input()
        self.audio = Audio(self.options)
        self.scenes = SceneManager()
        self.running = True
        self.fps_value = 0.0
        self.time = 0.0
        self.frame_count = 0
        self._cursor_hidden = False

    # ------------------------------------------------------------------ window
    def _create_window(self):
        flags = pygame.SCALED | pygame.RESIZABLE
        if self.options.get("fullscreen") and not self.headless:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((S.VIEW_W, S.VIEW_H), flags, vsync=1)
        except pygame.error:
            self.screen = pygame.display.set_mode((S.VIEW_W, S.VIEW_H), flags)

    def _refresh_rate(self):
        if self.headless:
            return S.FPS
        hz = 0
        try:
            hz = pygame.display.get_current_refresh_rate()
        except (pygame.error, AttributeError):
            try:
                hz = pygame.display.get_desktop_refresh_rates()[0]
            except (pygame.error, AttributeError, IndexError):
                hz = 0
        # unusual or unknown rates fall back to 60
        return hz if 60 <= hz <= 240 else S.FPS

    def _set_icon(self):
        try:
            sheet = pygame.image.load(str(S.ASSETS / "Character/Idle/Idle-Sheet.png"))
            icon = sheet.subsurface((16, 14, 32, 32))
            pygame.display.set_icon(icon)
        except (pygame.error, FileNotFoundError, ValueError):
            pass

    def toggle_fullscreen(self):
        self.options["fullscreen"] = not self.options["fullscreen"]
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error:
            self._create_window()
        self.save.save()

    # ------------------------------------------------------------------ loop
    def run(self, first_scene):
        self.scenes.switch(first_scene, fade=False)
        accumulator = 0.0
        dt = self.dt
        # vsync paces the loop; the cap only matters if the driver ignores vsync
        cap = self.sim_hz * 2
        while self.running:
            frame_dt = min(self.clock.tick(cap) / 1000.0, 0.1)
            self.fps_value = self.clock.get_fps()
            # vsync snapping: frame times that are within 2 ms of a whole number of refreshes
            # are treated as exact, so each displayed frame gets a steady number of updates
            # (no "0 updates, then 2 updates" hitches)
            for n in (1, 2, 3):
                if abs(frame_dt - n * dt) < 0.002:
                    frame_dt = n * dt
                    break
            for event in pygame.event.get():
                self._handle_event(event)
            accumulator += frame_dt
            steps = 0
            while accumulator >= dt - 1e-6 and steps < 5:
                self.step()
                accumulator -= dt
                steps += 1
            if steps == 5 or accumulator < 0:
                accumulator = 0.0
            self.render()
        pygame.quit()

    def step(self):
        self.scenes.update(self.dt)
        self.input.end_tick()
        self.audio.update()
        self.time += self.dt
        self.frame_count += 1

    def render(self):
        hide = bool(getattr(self.scenes.top, "hide_cursor", False))
        if hide != self._cursor_hidden:
            pygame.mouse.set_visible(not hide)
            self._cursor_hidden = hide
        self.screen.fill((0, 0, 0))
        self.scenes.draw(self.screen)
        if self.options.get("show_fps"):
            self.assets.font.draw(self.screen, f"{self.fps_value:4.0f} FPS", (S.VIEW_W - 4, S.VIEW_H - 11),
                                  S.TEXT, 1, S.SHADOW, align="right")
        pygame.display.flip()

    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.quit()
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
                self.toggle_fullscreen()
                return
        if event.type == pygame.WINDOWFOCUSLOST:
            self.input.reset()
        self.input.process_event(event)
        self.scenes.handle_event(event)

    def quit(self):
        self.save.save()
        self.running = False


def _report_crash():
    """Packaged builds have no console: write the error to a log and show a message box."""
    import traceback
    text = traceback.format_exc()
    log = S.SAVE_DIR / "crash.log"
    try:
        S.SAVE_DIR.mkdir(parents=True, exist_ok=True)
        log.write_text(text, encoding="utf-8")
    except OSError:
        pass
    print(text, file=sys.stderr)
    if S.FROZEN and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, f"Lost Forest crashed.\n\nDetails were saved to:\n{log}\n\n{text[-600:]}",
                "Lost Forest", 0x10)
        except Exception:
            pass


def _start_level_arg():
    """Developer shortcut: `--level N` jumps straight into level N (1-based)."""
    args = sys.argv[1:]
    if "--level" in args:
        try:
            return int(args[args.index("--level") + 1]) - 1
        except (IndexError, ValueError):
            pass
    return None


def main():
    from .scenes.title import TitleScene
    try:
        app = App()
        first = TitleScene(app)
        level = _start_level_arg()
        if "--endless" in sys.argv[1:]:
            from .scenes.endless import EndlessScene
            first = EndlessScene(app)
        elif level is not None:
            from .scenes.common import levels
            from .scenes.gameplay import GameplayScene
            if 0 <= level < len(levels(app)):
                first = GameplayScene(app, level)
        app.run(first)
    except Exception:
        _report_crash()
        sys.exit(1)
    sys.exit(0)
