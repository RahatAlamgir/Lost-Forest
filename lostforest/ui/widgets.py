"""Reusable UI pieces: pixel panels and keyboard/gamepad driven menus."""
import math

import pygame

from ..settings import TEXT, TEXT_DIM, TEXT_GOLD, SHADOW

PANEL_BORDER = (28, 20, 16)
PANEL_FILL = (62, 45, 34)
PANEL_LIGHT = (104, 78, 54)
PANEL_DARK = (44, 32, 25)


def draw_panel(surface, rect, alpha=255, fill=PANEL_FILL):
    """Wooden pixel-art panel with a dark outline and bevel."""
    r = pygame.Rect(rect)
    panel = pygame.Surface(r.size, pygame.SRCALPHA)
    w, h = r.size
    panel.fill((*PANEL_BORDER, alpha), (1, 0, w - 2, h))
    panel.fill((*PANEL_BORDER, alpha), (0, 1, w, h - 2))
    panel.fill((*fill, alpha), (2, 1, w - 4, h - 2))
    panel.fill((*fill, alpha), (1, 2, w - 2, h - 4))
    panel.fill((*PANEL_LIGHT, alpha), (2, 2, w - 4, 1))
    panel.fill((*PANEL_DARK, alpha), (2, h - 3, w - 4, 1))
    surface.blit(panel, r.topleft)


def dim_screen(surface, alpha=150):
    shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    shade.fill((8, 10, 14, alpha))
    surface.blit(shade, (0, 0))


class MenuItem:
    def __init__(self, label, action=None, value=None, adjust=None, enabled=True):
        self.label = label            # str or callable -> str
        self.action = action          # called on confirm
        self.value = value            # callable -> str shown on the right (for options)
        self.adjust = adjust          # callable(direction) for left/right
        self.enabled = enabled

    def text(self):
        return self.label() if callable(self.label) else self.label


class Menu:
    """Vertical list menu. Up/Down to move, confirm to activate, Left/Right to adjust."""

    def __init__(self, app, items, width=180, spacing=16, scale=1):
        self.app = app
        self.items = items
        self.index = 0
        self.width = width
        self.spacing = spacing
        self.scale = scale
        self.time = 0.0
        self._rects = []          # clickable area of each item (filled in by draw)
        self._skip_disabled(1)

    def _skip_disabled(self, step):
        for _ in range(len(self.items)):
            if self.items[self.index].enabled:
                return
            self.index = (self.index + step) % len(self.items)

    def _mouse(self):
        """Hover to select, left-click to activate. On option rows left/right click = more/less."""
        inp = self.app.input
        audio = self.app.audio
        if inp.mouse_moved:
            for i, r in enumerate(self._rects):
                if r.collidepoint(inp.mouse_pos) and self.items[i].enabled and i != self.index:
                    self.index = i
                    audio.play("menu_move")
        for button, pos in inp.clicks:
            for i, r in enumerate(self._rects):
                item = self.items[i]
                if not r.collidepoint(pos) or not item.enabled:
                    continue
                self.index = i
                if item.adjust and button in (1, 3):
                    item.adjust(1 if button == 1 else -1)
                    audio.play("menu_move")
                elif item.action and button == 1:
                    audio.play("menu_select")
                    item.action()
                return True
        return False

    def update(self, dt):
        self.time += dt
        inp = self.app.input
        audio = self.app.audio
        if self._mouse():
            return
        if inp.pressed("down"):
            self.index = (self.index + 1) % len(self.items)
            self._skip_disabled(1)
            audio.play("menu_move")
        elif inp.pressed("up"):
            self.index = (self.index - 1) % len(self.items)
            self._skip_disabled(-1)
            audio.play("menu_move")
        item = self.items[self.index]
        if item.adjust and (inp.pressed("left") or inp.pressed("right")):
            item.adjust(1 if inp.pressed("right") else -1)
            audio.play("menu_move")
        elif inp.pressed("confirm") and item.action and item.enabled:
            audio.play("menu_select")
            item.action()

    def height(self):
        return len(self.items) * self.spacing

    def draw(self, surface, center_x, top, align="center"):
        font = self.app.assets.font
        self._rects = []
        for i, item in enumerate(self.items):
            y = top + i * self.spacing
            selected = i == self.index
            self._rects.append(pygame.Rect(center_x - self.width // 2 - 12, y - (self.spacing - 7) // 2 - 1,
                                           self.width + 24, self.spacing))
            color = TEXT_GOLD if selected else (TEXT if item.enabled else TEXT_DIM)
            label = item.text()
            if item.value:
                left = center_x - self.width // 2
                right = center_x + self.width // 2
                font.draw(surface, label, (left, y), color, self.scale, SHADOW)
                val = item.value()
                if selected and item.adjust:
                    val = f"< {val} >"
                font.draw(surface, val, (right, y), color, self.scale, SHADOW, align="right")
                if selected:
                    self._cursor(surface, left - 10, y)
            else:
                rect = font.draw(surface, label, (center_x, y), color, self.scale, SHADOW, align=align)
                if selected:
                    self._cursor(surface, rect.left - 10, y)

    def _cursor(self, surface, x, y):
        bob = int(round(math.sin(self.time * 8) * 1.5))
        cy = y + (7 * self.scale) // 2
        x += bob
        pygame.draw.polygon(surface, SHADOW, [(x + 1, cy - 3), (x + 5, cy + 1), (x + 1, cy + 5)])
        pygame.draw.polygon(surface, TEXT_GOLD, [(x, cy - 4), (x + 4, cy), (x, cy + 4)])
