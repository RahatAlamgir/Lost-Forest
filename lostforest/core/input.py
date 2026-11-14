"""Action-based input: keyboard + gamepad mapped to game actions.

Scenes ask `inp.held("left")` / `inp.pressed("jump")` instead of checking keys.
`pressed` and `released` stay true until `end_tick()` is called after the first
fixed-step update of a frame, so short taps are never lost.
"""
import pygame

KEYMAP = {
    "left":    (pygame.K_a, pygame.K_LEFT),
    "right":   (pygame.K_d, pygame.K_RIGHT),
    "up":      (pygame.K_w, pygame.K_UP),          # interact (doors, chests) / menu up
    "down":    (pygame.K_s, pygame.K_DOWN),        # fast drop, drop through planks / menu down
    "jump":    (pygame.K_SPACE,),
    "attack":  (pygame.K_x,),
    "dash":    (pygame.K_LSHIFT, pygame.K_RSHIFT),
    "pause":   (pygame.K_ESCAPE, pygame.K_p),
    "confirm": (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE),
    "back":    (pygame.K_ESCAPE, pygame.K_BACKSPACE),
}

# mouse buttons -> actions (1 = left, 3 = right)
MOUSEMAP = {
    "attack": (1,),
    "dash":   (3,),
}

# Joystick button indices (Xbox layout)
PADMAP = {
    "jump":    (0,),          # A
    "attack":  (2, 1),        # X, B
    "dash":    (5, 4),        # RB, LB
    "confirm": (0,),
    "back":    (1,),
    "pause":   (6, 7),        # Back / Start (varies by pad)
}
AXIS_DEADZONE = 0.4


class Input:
    def __init__(self):
        self._held = set()
        self._pressed = set()
        self._released = set()
        self._pad_held = set()
        self._mouse_held = set()
        self.joysticks = {}
        self.last_device = "keyboard"
        # mouse state for menus (positions are in game pixels thanks to pygame.SCALED)
        self.mouse_pos = (-1, -1)
        self.mouse_moved = False
        self.clicks = []           # [(button, (x, y))] this tick
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            self._add_joystick(i)

    def _add_joystick(self, index):
        try:
            js = pygame.joystick.Joystick(index)
            self.joysticks[js.get_instance_id()] = js
        except pygame.error:
            pass

    # ------------------------------------------------------------------
    def process_event(self, e):
        if e.type == pygame.KEYDOWN:
            self.last_device = "keyboard"
            for action, keys in KEYMAP.items():
                if e.key in keys:
                    self._held.add(action)
                    self._pressed.add(action)
        elif e.type == pygame.KEYUP:
            for action, keys in KEYMAP.items():
                if e.key in keys:
                    self._held.discard(action)
                    self._released.add(action)
        elif e.type == pygame.MOUSEMOTION:
            self.mouse_pos = e.pos
            self.mouse_moved = True
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self.last_device = "mouse"
            self.mouse_pos = e.pos
            self.clicks.append((e.button, e.pos))
            for action, buttons in MOUSEMAP.items():
                if e.button in buttons:
                    self._mouse_held.add(action)
                    self._pressed.add(action)
        elif e.type == pygame.MOUSEBUTTONUP:
            for action, buttons in MOUSEMAP.items():
                if e.button in buttons:
                    self._mouse_held.discard(action)
                    self._released.add(action)
        elif e.type == pygame.JOYBUTTONDOWN:
            self.last_device = "gamepad"
            for action, buttons in PADMAP.items():
                if e.button in buttons:
                    self._pad_held.add(action)
                    self._pressed.add(action)
        elif e.type == pygame.JOYBUTTONUP:
            for action, buttons in PADMAP.items():
                if e.button in buttons:
                    self._pad_held.discard(action)
                    self._released.add(action)
        elif e.type == pygame.JOYHATMOTION:
            self.last_device = "gamepad"
            hx, hy = e.value
            self._set_dir("left", hx < 0)
            self._set_dir("right", hx > 0)
            self._set_dir("up", hy > 0)
            self._set_dir("down", hy < 0)
        elif e.type == pygame.JOYAXISMOTION and e.axis in (0, 1):
            if e.axis == 0:
                self._set_dir("left", e.value < -AXIS_DEADZONE)
                self._set_dir("right", e.value > AXIS_DEADZONE)
            else:
                self._set_dir("up", e.value < -AXIS_DEADZONE)
                self._set_dir("down", e.value > AXIS_DEADZONE)
        elif e.type == pygame.JOYDEVICEADDED:
            self._add_joystick(e.device_index)
        elif e.type == pygame.JOYDEVICEREMOVED:
            self.joysticks.pop(e.instance_id, None)

    def _set_dir(self, action, on):
        if on and action not in self._pad_held:
            self._pad_held.add(action)
            self._pressed.add(action)
        elif not on and action in self._pad_held:
            self._pad_held.discard(action)
            self._released.add(action)

    # ------------------------------------------------------------------
    def held(self, action):
        return action in self._held or action in self._pad_held or action in self._mouse_held

    def pressed(self, action):
        return action in self._pressed

    def released(self, action):
        return action in self._released

    def axis_x(self):
        return (1 if self.held("right") else 0) - (1 if self.held("left") else 0)

    def press(self, action):
        """Simulate a single tap of an action this tick (used by mouse clicks on menus)."""
        self._pressed.add(action)

    def clicked(self, rect, button=1):
        """True if `button` was clicked inside rect this tick."""
        return any(b == button and rect.collidepoint(p) for b, p in self.clicks)

    def end_tick(self):
        self._pressed.clear()
        self._released.clear()
        self.clicks.clear()
        self.mouse_moved = False

    def reset(self):
        self._held.clear()
        self._pad_held.clear()
        self._mouse_held.clear()
        self.end_tick()

    # ---------------------------------------------------- scripted input (tests)
    def inject(self, action, down=True):
        if down:
            self._held.add(action)
            self._pressed.add(action)
        else:
            self._held.discard(action)
            self._released.add(action)
