"""Endless Run world: an infinitely generated forest strip.

* StreamMap    - tile columns generated on the fly ahead of the hero and dropped
                 behind him. It offers the same query API as TileMap, so the hero,
                 enemies and pickups work in it unchanged.
* RunGenerator - picks obstacle patterns (spikes, pits, water, steps, plank bridges,
                 snails, bees, boars) that get harder with distance. Gap widths are
                 derived from the current run speed so every gap stays jumpable.
* RunWorld     - the "level" object for endless mode: entities, camera, scoring,
                 speed ramp and forest colour changes.
"""
import random

import pygame

from .. import settings as S
from ..core.particles import ParticleSystem
from ..entities.enemies import Snail, Boar, Bee
from ..entities.items import Coin
from ..entities.objects import Decoration
from ..entities.player import Player
from .background import Background
from .tiles import EMPTY, SOLID, WATER, TERRAIN, autotile
from .tilemap import TileMap, _outlined, WATER_STRIP, CREST_H

TILE = S.TILE
H = 18                    # rows in the endless world (288 px tall)
BASE = 13                 # default ground row
G_MIN, G_MAX = 10, 14     # how high / low the ground may wander
THEMES = ["green", "yellow", "golden", "autumn", "dusk"]
THEME_TREES = {"green": "Green", "yellow": "Yellow", "golden": "Golden", "autumn": "Red", "dusk": "Dark"}
THEME_BUSH = {"green": "bush_green", "yellow": "bush_yellow", "golden": "bush_yellow",
              "autumn": "bush_olive", "dusk": "bush_dark"}
HERO_SCREEN_X = 130       # the hero stays this far from the left edge of the screen


# ======================================================================================
class StreamMap:
    """Tile columns created on demand. Columns left of x=0 are a solid wall."""

    # reuse the collision helpers from the normal tilemap - they only rely on kind()
    cells_in_rect = TileMap.cells_in_rect
    hazard_at = TileMap.hazard_at
    solid_ground_below = TileMap.solid_ground_below
    is_solid = TileMap.is_solid

    def __init__(self, assets):
        self.assets = assets
        self.h = H
        self.w = 10 ** 9
        self.pixel_h = H * TILE
        self.pixel_w = 10 ** 9
        self.cols = {}
        self.water_cells = []
        self._pieces = {}
        self._tile_cache = {}
        self._sheets = {"tiles": assets.tiles, "hive": assets.hive_sheet}
        surf = assets.tile(6, 19, 4, 1)
        self._crest = pygame.Surface((WATER_STRIP * 2, CREST_H), pygame.SRCALPHA)
        for i in range(2):
            self._crest.blit(surf, (i * WATER_STRIP, 0), (0, 0, WATER_STRIP, CREST_H))
        top = pygame.Color(pygame.transform.average_color(surf, (0, 8, WATER_STRIP, 8)))
        self._water_top = top
        self._water_deep = pygame.Color(int(top.r * 0.35), int(top.g * 0.45), int(top.b * 0.6))

    # ------------------------------------------------------------------ queries
    def char(self, x, y):
        col = self.cols.get(x)
        if col is None or not 0 <= y < H:
            return " "
        return col[y]

    def kind(self, x, y):
        if x < 0:
            return SOLID
        if not 0 <= y < H:
            return EMPTY
        col = self.cols.get(x)
        if col is None:
            return EMPTY
        return TERRAIN.get(col[y], EMPTY)

    def in_bounds(self, x, y):
        return 0 <= y < H and x in self.cols

    # ------------------------------------------------------------------ building
    def set_column(self, x, chars):
        self.cols[x] = chars
        # neighbours' auto-tiling may change now that this column exists
        self._pieces.pop(x - 1, None)

    def forget(self, before_x):
        for x in [x for x in self.cols if x < before_x]:
            del self.cols[x]
            self._pieces.pop(x, None)

    def _tile(self, sheet, col, row):
        key = (sheet, col, row)
        img = self._tile_cache.get(key)
        if img is None:
            img = self._sheets[sheet].subsurface((col * TILE, row * TILE, TILE, TILE))
            if sheet == "hive":
                img = _outlined(img, (236, 214, 170))
            self._tile_cache[key] = img
        return img

    def _column_pieces(self, x):
        cached = self._pieces.get(x)
        if cached is not None:
            return cached
        col = self.cols.get(x)
        if col is None:
            return None
        terrain, spikes, water = [], [], []
        for y in range(H):
            ch = col[y]
            if ch == "~":
                water.append((y, self.char(x, y - 1) != "~"))
                continue
            for c, r, dy, sheet in autotile(self, x, y):
                img = self._tile(sheet, c, r)
                if sheet == "hive":
                    spikes.append((img, (y + dy) * TILE + 1))
                else:
                    terrain.append((img, (y + dy) * TILE))
        pieces = (terrain, spikes, water)
        if x + 1 in self.cols:            # only cache once the right neighbour is known
            self._pieces[x] = pieces
        return pieces

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, cam_x, cam_y, t):
        x0 = cam_x // TILE - 1
        x1 = (cam_x + surface.get_width()) // TILE + 1
        late = []
        shift = int(t * 9) % WATER_STRIP
        for x in range(x0, x1 + 1):
            pieces = self._column_pieces(x)
            if pieces is None:
                continue
            terrain, spikes, water = pieces
            px = x * TILE - cam_x
            for y, top in water:
                py = y * TILE - cam_y
                k = min(1.0, (y - H + 4) / 4.0)
                col = self._water_top.lerp(self._water_deep, max(0.0, k))
                if top:
                    surface.fill(col, (px, py + 3, TILE, TILE - 3))
                    off = ((x * TILE) % WATER_STRIP + shift) % WATER_STRIP
                    surface.blit(self._crest, (px, py), (off, 0, TILE, CREST_H))
                else:
                    surface.fill(col, (px, py, TILE, TILE))
            for img, py in terrain:
                surface.blit(img, (px, py - cam_y))
            for img, py in spikes:
                late.append((img, (px, py - cam_y)))
        for img, pos in late:
            surface.blit(img, pos)


# ======================================================================================
class RunGenerator:
    """Writes columns into the StreamMap and spawns things that live on them."""

    def __init__(self, world, rng):
        self.world = world
        self.map = world.tilemap
        self.rng = rng
        self.x = 0
        self.g = BASE
        self.flat(28, coins=False, decor=True)      # safe runway at the start

    # ------------------------------------------------------------------ column writers
    def _ground(self, g, above=None):
        col = ["."] * H
        for y in range(g, H):
            col[y] = "#"
        if above:
            for row, ch in above.items():
                col[row] = ch
        return col

    def _put(self, col):
        self.map.set_column(self.x, col)
        self.x += 1

    def flat(self, n, coins=True, decor=True):
        start = self.x
        for _ in range(n):
            self._put(self._ground(self.g))
        if coins and n >= 6 and self.rng.random() < 0.45:
            self.coin_arc(start + 1, min(n - 2, 7))
        if decor:
            self.decorate(start, n)

    def spikes(self, n):
        for _ in range(n):
            self._put(self._ground(self.g, {self.g - 1: "^"}))

    def pit(self, n, water=False, plank=None):
        """A gap. plank=(offset, width, row) adds a one-way plank bridge piece."""
        for i in range(n):
            col = ["."] * H
            if water:
                for y in range(H - 3, H):
                    col[y] = "~"
            if plank and plank[0] <= i < plank[0] + plank[1]:
                col[plank[2]] = "="
            self._put(col)

    def step(self, dh):
        self.g = max(G_MIN, min(G_MAX, self.g + dh))

    # ------------------------------------------------------------------ things
    def coin_arc(self, x0, n):
        world, img = self.world, self.world.assets.props["coin"]
        for i in range(n):
            lift = 3 + int(2 * (1 - abs((i - (n - 1) / 2) / max(1, (n - 1) / 2)) ** 2))
            world.add(Coin((x0 + i) * TILE + 8, (self.g - lift) * TILE + 8, img))

    def coins_over(self, x0, n, row):
        img = self.world.assets.props["coin"]
        for i in range(0, n, 2):
            self.world.add(Coin((x0 + i) * TILE + 8, row * TILE + 8, img))

    def decorate(self, x0, n):
        rng, world, a = self.rng, self.world, self.world.assets
        theme = world.theme_name
        for x in range(x0 + 1, x0 + n - 1, 3):
            r = rng.random()
            px, bottom = x * TILE + 8, self.g * TILE
            if r < 0.10:
                img = a.trees[THEME_TREES[theme]][rng.choice(["xl", "l", "m"])]
                world.decor_back.append(Decoration(px, bottom + 6, img, "back", rng.random() < 0.5))
            elif r < 0.17:
                world.decor_back.append(Decoration(px, bottom + 6, a.props[THEME_BUSH[theme]], "back"))
            elif r < 0.25:
                name = rng.choice(["mushroom_s", "mushroom_s2", "mushroom_l", "lavender", "flower_blue", "fern"])
                world.decor_front.append(Decoration(px, bottom + (2 if name == "fern" else 0), a.props[name], "front"))

    def enemy(self, cls, x_tile, bottom_row, facing=-1):
        e = cls(x_tile * TILE + 8, bottom_row * TILE, self.world.assets)
        e.facing = facing
        e.hp = e.max_hp = 1              # at running speed every enemy falls to a single hit
        self.world.add(e)
        return e

    # ------------------------------------------------------------------ patterns
    def max_gap(self):
        """Widest gap (tiles) that a single running jump clears comfortably at this speed."""
        speed = self.world.speed
        return max(2, min(7, int(speed * 0.643 * 0.72 / TILE)))

    def spacing(self):
        """Breathing room after an obstacle: about 0.9 s of running, plus some variety."""
        return max(6, int(self.world.speed * 0.9 / TILE)) + self.rng.randint(0, 5)

    def segment(self):
        rng = self.rng
        d = self.world.metres_at(self.x)
        options = [("spikes", 4), ("snail", 3)]
        if d > 40:
            options += [("pit", 4), ("water", 2)]
        if d > 120:
            options += [("bee", 3), ("step_up", 2), ("step_down", 2)]
        if d > 220:
            options += [("boar", 2), ("plank", 2), ("spike_coins", 1)]
        if d > 400:
            options += [("combo", 3), ("bee_pit", 2)]
        kinds, weights = zip(*options)
        kind = rng.choices(kinds, weights)[0]
        gap = self.max_gap()

        if kind == "spikes":
            self.spikes(rng.randint(1, min(3, gap - 1)))
        elif kind == "spike_coins":
            x0 = self.x
            self.spikes(min(3, gap - 1))
            self.coins_over(x0 - 1, min(5, gap + 1), self.g - 4)
        elif kind == "pit":
            self.pit(rng.randint(2, gap))
        elif kind == "water":
            self.pit(rng.randint(2, gap), water=True)
        elif kind == "snail":
            self.flat(3, coins=False)
            self.enemy(Snail, self.x + 2, self.g)
            self.flat(4, coins=False)
        elif kind == "bee":
            self.flat(3, coins=False)
            self.enemy(Bee, self.x + 3, self.g - 2)
            self.flat(6, coins=False)
        elif kind == "boar":
            self.flat(4, coins=False)
            x0 = self.x
            self.flat(14, coins=False, decor=False)
            self.enemy(Boar, x0 + 11, self.g)
        elif kind == "step_up":
            if self.g - 2 < G_MIN:
                kind = "step_down"
            else:
                self.step(-rng.randint(1, 2))
                self.flat(3, coins=False)
        if kind == "step_down":
            self.step(rng.randint(1, 2))
            self.flat(3, coins=False)
        elif kind == "plank":
            n = gap + rng.randint(3, 5)
            mid = n // 2 - 1
            x0 = self.x
            self.pit(n, water=rng.random() < 0.5, plank=(mid, 3, self.g - 1))
            self.coins_over(x0 + mid, 3, self.g - 3)
        elif kind == "combo":
            self.spikes(rng.randint(1, 2))
            self.flat(max(4, gap), coins=False, decor=False)
            self.pit(rng.randint(2, max(2, gap - 1)), water=rng.random() < 0.4)
        elif kind == "bee_pit":
            x0 = self.x
            self.pit(rng.randint(2, max(2, gap - 1)))
            self.enemy(Bee, x0 + 1, self.g - 4)
        self.flat(self.spacing())

    def ensure(self, upto_x):
        while self.x < upto_x:
            self.segment()


# ======================================================================================
class RunCamera:
    """Keeps the hero at a fixed spot on screen (smooth, no lag) with optional shake."""

    def __init__(self):
        self.x = 0.0
        self.y = float(H * TILE - S.VIEW_H)
        self.shake_time = 0.0
        self.shake_strength = 0.0
        self.shake_enabled = True
        self.offset = (0, 0)

    def update(self, dt, player):
        self.x = max(0.0, player.rect.centerx - HERO_SCREEN_X)
        if self.shake_time > 0:
            self.shake_time -= dt
            s = self.shake_strength if self.shake_enabled else 0
            self.offset = (random.uniform(-s, s), random.uniform(-s, s))
        else:
            self.offset = (0, 0)

    def shake(self, strength=3.0, time=0.2):
        self.shake_strength = max(self.shake_strength if self.shake_time > 0 else 0, strength)
        self.shake_time = max(self.shake_time, time)

    def snap(self, cx, cy):
        self.x = max(0.0, cx - HERO_SCREEN_X)

    @property
    def ix(self):
        return int(round(self.x + self.offset[0]))

    @property
    def iy(self):
        return int(round(self.y + self.offset[1]))


# ======================================================================================
class RunWorld:
    """Plays the role of a Level for endless mode."""

    def __init__(self, app, seed=None):
        self.app = app
        self.assets = app.assets
        self.audio = app.audio
        self.input = app.input
        self.rng = random.Random(seed)
        self.tilemap = StreamMap(self.assets)
        self.enemies = []
        self.objects = []
        self.platforms = []
        self.decor_back = []
        self.decor_front = []
        self.popups = []
        self.particles = ParticleSystem()
        self.stats = {"coins": 0, "enemies": 0, "gem": False, "deaths": 0}
        self.has_key = False
        self.completed = False
        self.active_sign = None
        self.time = 0.0
        self.anim_time = 0.0
        self.hitstop_timer = 0.0
        self.leaf_timer = 0.0
        self.speed = S.ENDLESS_START_SPEED
        self.started = False
        self.milestone = 0
        self._distance = 0.0
        self.score_flash = 0.0

        self.theme_index = 0
        self.theme_name = THEMES[0]
        self.background = self._make_background(self.theme_name)
        self.theme = self.background.theme
        self.old_background = None
        self.theme_fade = 0.0
        self._fade_surface = pygame.Surface((S.VIEW_W, S.VIEW_H))

        self.camera = RunCamera()
        self.camera.shake_enabled = app.options.get("screen_shake", True)
        self.player = Player(5 * TILE, BASE * TILE, self.assets)
        self.player.level = self
        self.player.max_health = self.player.health = 1     # one hit ends the run
        self.start_x = self.player.rect.x
        self.generator = RunGenerator(self, self.rng)
        self.generator.ensure(60)
        self.camera.update(0, self.player)

    def _make_background(self, theme):
        return Background(self.assets, theme, 3000, H * TILE, seed=self.rng.randint(0, 9999))

    # ------------------------------------------------------------------ level API used by entities
    def add(self, entity):
        entity.level = self
        if hasattr(entity, "hittable"):
            self.enemies.append(entity)
        else:
            self.objects.append(entity)

    def popup(self, text, x, y, color=(255, 255, 255)):
        self.popups.append([text, float(x), float(y), 1.2, color])

    def hitstop(self, t):
        self.hitstop_timer = max(self.hitstop_timer, t)

    def complete(self):
        pass

    def on_enemy_killed(self, enemy):
        """Called by Enemy.die(): show the points right where the enemy fell."""
        self.popup(f"+{S.ENDLESS_KILL_POINTS}", enemy.rect.centerx, enemy.rect.top - 6, (255, 225, 120))
        self.score_flash = 0.35

    def _crash_check(self):
        """Running into a raised step ends the run. If the feet are only a few pixels
        short of the top, the hero is helped up onto it instead (fairness)."""
        p = self.player
        if p.hit_wall != 1 or p.is_dead:
            return
        tx = int((p.rect.right + 1) // TILE)
        ty = int((p.rect.bottom - 1) // TILE)
        top = ty
        while top > 0 and self.tilemap.kind(tx, top - 1) == SOLID:
            top -= 1
        if p.rect.bottom - top * TILE <= 7:
            p.rect.bottom = top * TILE
            p.rect.x += 2
            p.vy = 0
            p.vx = self.speed
            return
        p.health = 0
        p.die()
        p.vx, p.vy = -90.0, -180.0
        self.audio.play("hurt")
        self.particles.burst(p.rect.right, p.rect.centery, 12, 90, ((230, 220, 190), (255, 255, 255)), 0.4, 250)
        self.popup("CRASH!", p.rect.centerx, p.rect.top - 10, (240, 120, 100))

    # ------------------------------------------------------------------ scoring
    def metres_at(self, x_tile):
        return max(0.0, x_tile - self.start_x / TILE)

    @property
    def distance(self):
        """Metres run (1 tile = 1 metre). Frozen once the hero dies."""
        if not self.player.is_dead:
            self._distance = max(self._distance, (self.player.rect.x - self.start_x) / TILE)
        return self._distance

    @property
    def score(self):
        return (int(self.distance) + self.stats["coins"] * S.ENDLESS_COIN_POINTS
                + self.stats["enemies"] * S.ENDLESS_KILL_POINTS)

    def start(self):
        self.started = True
        self.player.auto_run = self.speed

    # ------------------------------------------------------------------ loop
    def update(self, dt):
        self.anim_time += dt
        if self.hitstop_timer > 0:
            self.hitstop_timer -= dt
            return
        p = self.player
        running = self.started and not p.is_dead
        if running:
            self.time += dt
            self.speed = min(S.ENDLESS_MAX_SPEED, self.speed + S.ENDLESS_ACCEL * dt)
            p.auto_run = self.speed
        p.control = self.started
        cam = self.camera
        self.generator.ensure(int((cam.x + S.VIEW_W) // TILE) + 60)

        p.update(dt)
        if running:
            self._crash_check()
        self.score_flash = max(0.0, self.score_flash - dt)
        left, right = cam.x - 120, cam.x + S.VIEW_W + 240
        for e in self.enemies:
            if left < e.rect.centerx < right or e.dying:
                e.update(dt)
        for o in self.objects:
            if left < o.rect.centerx < right:
                o.update(dt)
        cull = cam.x - 160
        self.enemies = [e for e in self.enemies if e.alive and e.rect.right > cull]
        self.objects = [o for o in self.objects if o.alive and o.rect.right > cull]
        self.decor_back = [d for d in self.decor_back if d.rect.right > cull]
        self.decor_front = [d for d in self.decor_front if d.rect.right > cull]
        self.tilemap.forget(int(cull // TILE) - 4)

        self.particles.update(dt)
        for pop in self.popups:
            pop[2] -= 18 * dt
            pop[3] -= dt
        self.popups = [q for q in self.popups if q[3] > 0]
        self._ambient(dt)
        if running:
            self._milestones()
            self._theme_check()
        if self.theme_fade > 0:
            self.theme_fade = max(0.0, self.theme_fade - dt / 1.5)
        cam.update(dt, p)

    def _milestones(self):
        m = int(self.distance // 250)
        if m > self.milestone:
            self.milestone = m
            self.audio.play("checkpoint", 0.6)
            p = self.player
            self.popup(f"{m * 250} M!", p.rect.centerx + 40, p.rect.top - 20, (255, 225, 120))

    def _theme_check(self):
        idx = int(self.distance // S.ENDLESS_THEME_EVERY) % len(THEMES)
        if idx != self.theme_index:
            self.theme_index = idx
            self.theme_name = THEMES[idx]
            self.old_background = self.background
            self.background = self._make_background(self.theme_name)
            self.theme = self.background.theme
            self.theme_fade = 1.0

    def _ambient(self, dt):
        cam = self.camera
        self.leaf_timer -= dt
        if self.leaf_timer <= 0:
            self.leaf_timer = 0.3
            self.particles.leaf(cam.x + random.uniform(0, S.VIEW_W + 120), cam.y - 6, self.theme["leaf"])
        if self.theme.get("fireflies") and random.random() < dt * 2.5:
            self.particles.firefly(cam.x + random.uniform(0, S.VIEW_W), cam.y + random.uniform(40, S.VIEW_H - 40))

    def draw(self, surface):
        cam = self.camera
        cx, cy = cam.ix, cam.iy
        self.background.draw(surface, cx, cy)
        if self.theme_fade > 0 and self.old_background is not None:
            self.old_background.draw(self._fade_surface, cx, cy)
            self._fade_surface.set_alpha(int(255 * self.theme_fade))
            surface.blit(self._fade_surface, (0, 0))
        view = pygame.Rect(cx - 140, cy - 120, S.VIEW_W + 280, S.VIEW_H + 240)
        for d in self.decor_back:
            if view.colliderect(d.rect):
                d.draw(surface, cx, cy)
        self.tilemap.draw(surface, cx, cy, self.anim_time)
        for d in self.decor_front:
            if view.colliderect(d.rect):
                d.draw(surface, cx, cy)
        things = [e for e in self.objects + self.enemies if view.colliderect(e.rect)]
        things.sort(key=lambda e: e.layer)
        for e in things:
            e.draw(surface, cx, cy)
        self.player.draw(surface, cx, cy)
        self.particles.draw(surface, cx, cy)
        self.background.draw_ambient(surface)
        font = self.assets.font
        for text, x, y, life, color in self.popups:
            if life > 0.2 or int(life * 20) % 2 == 0:
                font.draw(surface, text, (x - cx, y - cy), color, 1, (20, 16, 14), align="center")
