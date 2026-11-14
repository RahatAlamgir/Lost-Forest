"""Tile grid: collision queries, pre-rendered terrain and animated water."""
import math

import pygame

from ..settings import TILE
from .tiles import EMPTY, SOLID, ONEWAY, WATER, SPIKES, TERRAIN, autotile

WATER_STRIP = 4 * TILE   # the tileset's water strip is 4 tiles wide
CREST_H = 8              # rows of the surface tile used as the animated wave crest


def _outlined(img, color):
    """Copy of a tile with a 1px light outline so hazards read clearly on dark backgrounds."""
    w, h = img.get_size()
    mask = pygame.mask.from_surface(img)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    edge = mask.to_surface(setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((1, 0), (-1, 0), (0, -1)):
        out.blit(edge, (dx, dy))
    out.blit(img, (0, 0))
    return out


class TileMap:
    def __init__(self, rows, assets):
        self.h = len(rows)
        self.w = max(len(r) for r in rows) if rows else 0
        self.rows = [r.ljust(self.w) for r in rows]
        self.kinds = [[TERRAIN.get(c, EMPTY) for c in row] for row in self.rows]
        self.pixel_w = self.w * TILE
        self.pixel_h = self.h * TILE
        self.assets = assets
        self.water_cells = []
        self._build_surface()
        self._build_water()

    # ------------------------------------------------------------------ queries
    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def char(self, x, y):
        if 0 <= y < self.h and 0 <= x < self.w:
            return self.rows[y][x]
        return " "

    def kind(self, x, y):
        if x < 0 or x >= self.w:
            return SOLID                 # invisible walls at the level's sides
        if y < 0 or y >= self.h:
            return EMPTY                 # open sky above, bottomless pit below
        return self.kinds[y][x]

    def is_solid(self, x, y):
        return self.kind(x, y) == SOLID

    def cells_in_rect(self, rect):
        x0 = int(math.floor(rect.left / TILE))
        x1 = int(math.floor((rect.right - 0.001) / TILE))
        y0 = int(math.floor(rect.top / TILE))
        y1 = int(math.floor((rect.bottom - 0.001) / TILE))
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                yield tx, ty

    def hazard_at(self, rect):
        """Return the hazard kind (WATER / SPIKES) touched by rect, or None."""
        for tx, ty in self.cells_in_rect(rect):
            k = self.kind(tx, ty)
            if k == SPIKES:
                hr = pygame.FRect(tx * TILE + 2, ty * TILE + 7, TILE - 4, TILE - 7)
                if hr.colliderect(rect):
                    return SPIKES
            elif k == WATER:
                hr = pygame.FRect(tx * TILE, ty * TILE + 6, TILE, TILE - 6)
                if hr.colliderect(rect):
                    return WATER
        return None

    def solid_ground_below(self, x_px, y_px, max_tiles=1):
        """True if there is something to stand on within max_tiles below the point."""
        tx = int(x_px // TILE)
        ty = int(y_px // TILE)
        for dy in range(max_tiles + 1):
            if self.kind(tx, ty + dy) in (SOLID, ONEWAY):
                return True
        return False

    # ------------------------------------------------------------------ rendering
    def _build_surface(self):
        a = self.assets
        self.surface = pygame.Surface((self.pixel_w, self.pixel_h), pygame.SRCALPHA)
        sheets = {"tiles": a.tiles, "hive": a.hive_sheet}
        cache = {}
        late = []   # spikes are drawn last so grass overhangs never hide them
        for y in range(self.h):
            for x in range(self.w):
                for col, row, dy, sheet in autotile(self, x, y):
                    key = (sheet, col, row)
                    img = cache.get(key)
                    if img is None:
                        img = sheets[sheet].subsurface((col * TILE, row * TILE, TILE, TILE))
                        if sheet == "hive":
                            img = _outlined(img, (236, 214, 170))
                        cache[key] = img
                    if sheet == "hive":
                        late.append((img, (x * TILE, (y + dy) * TILE + 1)))
                    else:
                        self.surface.blit(img, (x * TILE, (y + dy) * TILE))
        for img, pos in late:
            self.surface.blit(img, pos)
        self._build_backwall()

    def _build_backwall(self):
        """Dark rock behind cave interiors: open cells with at least 3 tiles of solid
        ground directly above them, down to the cave floor. Without it, tunnels show
        open sky through them and the rock above looks like it is floating."""
        a = self.assets
        tiles = []
        for col in (1, 2, 3):
            for row in (7, 8):
                t = a.tile(col, row)
                t.fill((80, 72, 78, 255), special_flags=pygame.BLEND_RGBA_MULT)
                tiles.append(t)
        cave = [[False] * self.w for _ in range(self.h)]
        for x in range(self.w):
            y = 0
            while y < self.h:
                if self.kinds[y][x] == SOLID:
                    top = y
                    while y < self.h and self.kinds[y][x] == SOLID:
                        y += 1
                    if y - top >= 3 and y < self.h:
                        # open run below this rock, until the next solid tile
                        yy = y
                        while yy < self.h and self.kinds[yy][x] != SOLID:
                            yy += 1
                        if yy < self.h:            # needs a floor: it's a cave, not an overhang over a pit
                            for cy in range(y, yy):
                                cave[cy][x] = True
                        y = yy
                else:
                    y += 1
        self.backwall = None
        if not any(any(r) for r in cave):
            return
        self.backwall = pygame.Surface((self.pixel_w, self.pixel_h), pygame.SRCALPHA)
        for y in range(self.h):
            for x in range(self.w):
                if not cave[y][x]:
                    continue
                img = tiles[(x * 7 + y * 3) % len(tiles)]
                # fade towards the cave mouths
                depth = 0
                for d in range(1, 4):
                    if 0 <= x - d < self.w and cave[y][x - d] and 0 <= x + d < self.w and cave[y][x + d]:
                        depth = d
                    else:
                        break
                img = img.copy()
                img.set_alpha((110, 170, 220, 255)[depth])
                self.backwall.blit(img, (x * TILE, y * TILE))

    def draw_backwall(self, surface, cam_x, cam_y):
        if self.backwall is not None:
            surface.blit(self.backwall, (-cam_x, -cam_y))

    def _build_water(self):
        """Water is a depth-shaded body drawn *behind* the terrain (so it tucks under the
        rocky pool walls instead of floating between them), an animated wave crest on top,
        and a translucent front layer so anything inside the water looks submerged."""
        a = self.assets
        surf = a.tile(6, 19, 4, 1)
        # animated crest: the top rows of the tileset's water surface, doubled for wrap-around scrolling
        self._crest = pygame.Surface((WATER_STRIP * 2, CREST_H), pygame.SRCALPHA)
        for i in range(2):
            self._crest.blit(surf, (i * WATER_STRIP, 0), (0, 0, WATER_STRIP, CREST_H))
        top_col = pygame.Color(pygame.transform.average_color(surf, (0, 8, WATER_STRIP, 8)))
        deep_col = pygame.Color(int(top_col.r * 0.35), int(top_col.g * 0.45), int(top_col.b * 0.6))

        self.water_back = pygame.Surface((self.pixel_w, self.pixel_h), pygame.SRCALPHA)
        self.water_front = pygame.Surface((self.pixel_w, self.pixel_h), pygame.SRCALPHA)
        self.water_tops = []
        for y in range(self.h):
            for x in range(self.w):
                if self.kinds[y][x] != WATER:
                    continue
                top = self.kind(x, y - 1) != WATER
                self.water_cells.append((x, y, top))
                if top:
                    self.water_tops.append((x, y))
                # depth measured from this column's surface
                sy = y
                while self.kind(x, sy - 1) == WATER:
                    sy -= 1
                surface_px = sy * TILE + 3
                cell = pygame.Rect(x * TILE, y * TILE + (3 if top else 0), TILE, TILE - (3 if top else 0))
                back = cell.copy()
                if self.kind(x - 1, y) == SOLID:
                    back.x -= 6
                    back.w += 6
                if self.kind(x + 1, y) == SOLID:
                    back.w += 6
                if self.kind(x, y + 1) == SOLID:
                    back.h += 6
                for py in range(back.top, back.bottom):
                    k = min(1.0, max(0.0, (py - surface_px) / 70.0))
                    col = top_col.lerp(deep_col, k)
                    self.water_back.fill((col.r, col.g, col.b, 245), (back.x, py, back.w, 1))
                    if cell.top <= py < cell.bottom:
                        self.water_front.fill((col.r, col.g, col.b, 110), (cell.x, py, cell.w, 1))

    def draw(self, surface, cam_x, cam_y):
        surface.blit(self.surface, (-cam_x, -cam_y))

    def draw_water_back(self, surface, cam_x, cam_y, t):
        if not self.water_cells:
            return
        surface.blit(self.water_back, (-cam_x, -cam_y))
        sw, sh = surface.get_size()
        shift = int(t * 9) % WATER_STRIP
        bob = 1 if int(t * 2.5) % 2 else 0
        for x, y in self.water_tops:
            px, py = x * TILE - cam_x, y * TILE - cam_y
            if px < -TILE or px > sw or py < -TILE or py > sh:
                continue
            off = ((x * TILE) % WATER_STRIP + shift) % WATER_STRIP
            surface.blit(self._crest, (px, py + bob), (off, 0, TILE, CREST_H))

    def draw_water_front(self, surface, cam_x, cam_y):
        if self.water_cells:
            surface.blit(self.water_front, (-cam_x, -cam_y))
