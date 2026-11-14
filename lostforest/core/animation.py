"""Sprite-sheet animations with per-animation anchor points and flip / flash support."""
import pygame


def make_silhouette(surface, color=(255, 255, 255)):
    """Solid-colour copy of a sprite, used for the white 'hit flash'."""
    mask = pygame.mask.from_surface(surface)
    return mask.to_surface(setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))


class Animation:
    """A list of frames played at a fixed rate.

    anchor: the pixel inside each frame that lines up with the owner's anchor point
            (bottom-centre of its hitbox for ground units, centre for flyers).
    facing: the direction the artwork faces natively (+1 right, -1 left).
    """

    def __init__(self, frames, fps=10, loop=True, anchor=(0, 0), facing=1):
        self.frames = frames
        self.fps = fps
        self.loop = loop
        self.anchor = anchor
        self.facing = facing
        self._flipped = [pygame.transform.flip(f, True, False) for f in frames]
        self._flash = None
        self._flash_flipped = None

    def __len__(self):
        return len(self.frames)

    @property
    def duration(self):
        return len(self.frames) / self.fps

    def index_at(self, t):
        i = int(t * self.fps)
        if self.loop:
            return i % len(self.frames)
        return min(i, len(self.frames) - 1)

    def finished(self, t):
        return not self.loop and t >= self.duration

    def _ensure_flash(self):
        if self._flash is None:
            self._flash = [make_silhouette(f) for f in self.frames]
            self._flash_flipped = [pygame.transform.flip(f, True, False) for f in self._flash]

    def image(self, t, facing=1, flash=False):
        """Return (surface, anchor_x, anchor_y) for time t and desired facing."""
        i = self.index_at(t)
        flip = facing != self.facing
        if flash:
            self._ensure_flash()
            img = self._flash_flipped[i] if flip else self._flash[i]
        else:
            img = self._flipped[i] if flip else self.frames[i]
        ax, ay = self.anchor
        if flip:
            ax = img.get_width() - ax
        return img, ax, ay

    def draw(self, surface, t, pos, facing=1, flash=False, alpha=255):
        img, ax, ay = self.image(t, facing, flash)
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        surface.blit(img, (round(pos[0] - ax), round(pos[1] - ay)))


class AnimPlayer:
    """Tracks the current animation of an entity."""

    def __init__(self, animations, start):
        self.animations = animations
        self.name = start
        self.time = 0.0

    @property
    def current(self):
        return self.animations[self.name]

    def play(self, name, restart=False):
        if name != self.name or restart:
            self.name = name
            self.time = 0.0

    def update(self, dt):
        self.time += dt

    @property
    def frame(self):
        return self.current.index_at(self.time)

    @property
    def finished(self):
        return self.current.finished(self.time)

    def draw(self, surface, pos, facing=1, flash=False, alpha=255):
        self.current.draw(surface, self.time, pos, facing, flash, alpha)
