"""Smooth-follow camera with look-ahead, level bounds and screen shake.

Pixel-perfect snapping: the camera position is rounded *relative to the followed
point* (the hero), not on its own. Rounding both separately makes the hero
wobble by a pixel against the scenery while it moves; rounding the offset keeps
the hero perfectly still on screen and the scenery scrolls in clean steps.
"""
import random

from ..settings import VIEW_W, VIEW_H


class Camera:
    def __init__(self, level_w, level_h):
        self.x = 0.0
        self.y = 0.0
        self.level_w = level_w
        self.level_h = level_h
        self.look = 0.0
        self.shake_time = 0.0
        self.shake_strength = 0.0
        self.shake_enabled = True
        self.offset = (0, 0)
        self.fx = 0.0            # followed point (world)
        self.fy = 0.0

    def _clamp(self, x, y):
        # levels smaller than the screen are pinned to the bottom / left edge
        x = max(0.0, min(x, self.level_w - VIEW_W)) if self.level_w >= VIEW_W else 0.0
        y = max(0.0, min(y, self.level_h - VIEW_H)) if self.level_h >= VIEW_H else float(self.level_h - VIEW_H)
        return x, y

    def snap(self, cx, cy):
        self.fx, self.fy = cx, cy
        self.x, self.y = self._clamp(cx - VIEW_W / 2, cy - VIEW_H * 0.58)

    def update(self, dt, cx, cy, facing, vy, grounded):
        self.fx, self.fy = cx, cy
        # look ahead in the facing direction
        self.look += (facing * 42 - self.look) * min(1.0, dt * 2.5)
        tx = cx + self.look - VIEW_W / 2
        ty = cy - VIEW_H * 0.58
        self.x += (tx - self.x) * min(1.0, dt * 6.0)
        # vertical: snappier while falling fast so the player can see below
        vfollow = 7.0 if (grounded or vy > 250) else 2.5
        self.y += (ty - self.y) * min(1.0, dt * vfollow)
        self.x, self.y = self._clamp(self.x, self.y)

        if self.shake_time > 0:
            self.shake_time -= dt
            s = self.shake_strength if self.shake_enabled else 0
            self.offset = (random.uniform(-s, s), random.uniform(-s, s))
        else:
            self.offset = (0, 0)

    def shake(self, strength=3.0, time=0.2):
        self.shake_strength = max(self.shake_strength if self.shake_time > 0 else 0, strength)
        self.shake_time = max(self.shake_time, time)

    def _snapped(self, focus, pos, offset, size, view):
        v = round(focus) - round(focus - pos) + round(offset)
        if size >= view:
            v = max(0, min(v, size - view))
        return int(v)

    @property
    def ix(self):
        return self._snapped(self.fx, self.x, self.offset[0], self.level_w, VIEW_W)

    @property
    def iy(self):
        if self.level_h < VIEW_H:
            return int(self.level_h - VIEW_H)
        return self._snapped(self.fy, self.y, self.offset[1], self.level_h, VIEW_H)
