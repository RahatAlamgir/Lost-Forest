"""Level files: parsing the text format and building the playable world.

Level file layout (see levels/README.md for the full legend):

    name: Forest Edge
    theme: green
    sign: Text shown by the first ? sign
    sign: Text for the second ? sign
    ---
    <map rows>
"""
import random

import pygame

from ..settings import LEVELS_DIR, TILE, VIEW_W, VIEW_H
from ..core.camera import Camera
from ..core.particles import ParticleSystem
from ..entities.enemies import ENEMY_TYPES
from ..entities.items import Coin, Gem, Potion, Key, Chest
from ..entities.objects import (Checkpoint, ExitDoor, Sign, MovingPlatform, FallingPlatform, Decoration)
from ..entities.player import Player
from .background import Background
from .tilemap import TileMap
from .tiles import WATER, SPIKES

ENTITY_CHARS = set("PELC?MFohkGcsbzTtyumnfrwi-:")


class LevelData:
    """The parsed contents of a level file (no pygame objects)."""

    def __init__(self, path, index):
        self.path = path
        self.index = index
        self.id = path.stem
        self.meta = {}
        self.signs = []
        self.rows = []
        self._parse(path.read_text(encoding="utf-8"))
        self.name = self.meta.get("name", self.id)
        self.theme = self.meta.get("theme", "green")
        self.music = self.meta.get("music", "forest")
        self.subtitle = self.meta.get("subtitle", "")

    def _parse(self, text):
        lines = text.replace("\t", "    ").splitlines()
        in_map = False
        for line in lines:
            if not in_map:
                if line.strip() == "---":
                    in_map = True
                    continue
                if not line.strip() or line.lstrip().startswith(";"):
                    continue
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if key == "sign":
                        self.signs.append(value.replace("\\n", "\n"))
                    else:
                        self.meta[key] = value
            else:
                self.rows.append(line.rstrip("\n"))
        # trim trailing empty lines
        while self.rows and not self.rows[-1].strip():
            self.rows.pop()

    @property
    def coin_total(self):
        coins = sum(r.count("o") for r in self.rows)
        chests = sum(r.count("c") for r in self.rows)
        return coins + chests * Chest.COINS

    @property
    def has_gem(self):
        return any("G" in r for r in self.rows)


def discover_levels():
    files = sorted(LEVELS_DIR.glob("*.txt"))
    return [LevelData(p, i) for i, p in enumerate(files)]


class Level:
    """A running level: owns the tilemap, entities, camera and particles."""

    def __init__(self, data, app):
        self.data = data
        self.app = app
        self.assets = app.assets
        self.audio = app.audio
        self.input = app.input
        self.rng = random.Random(data.id)

        terrain_rows = ["".join(" " if c in ENTITY_CHARS or c == "." else c for c in row) for row in data.rows]
        self.tilemap = TileMap(terrain_rows, self.assets)
        self.width = self.tilemap.pixel_w
        self.height = self.tilemap.pixel_h

        self.player = None
        self.enemies = []
        self.objects = []
        self.platforms = []
        self.decor_back = []
        self.decor_front = []
        self.popups = []
        self.particles = ParticleSystem()
        seed = sum(ord(c) * (i + 1) for i, c in enumerate(data.id))
        self.background = Background(self.assets, data.theme, self.width, self.height, seed=seed)
        self.theme = self.background.theme

        self.stats = {"coins": 0, "enemies": 0, "gem": False, "deaths": 0}
        self.coin_total = data.coin_total
        self.has_gem = data.has_gem
        self.enemy_total = 0
        self.has_key = False
        self.completed = False
        self.time = 0.0
        self.anim_time = 0.0       # keeps running after the level ends (water, ambience)
        self.hitstop_timer = 0.0
        self.active_sign = None
        self.leaf_timer = 0.0

        self._spawn_entities()
        if self.player is None:
            raise ValueError(f"{data.path.name}: no player start 'P' in map")
        self.checkpoint = (self.player.rect.centerx, self.player.rect.bottom)
        self.camera = Camera(self.width, self.height)
        self.camera.shake_enabled = app.options.get("screen_shake", True)
        self.camera.snap(*self.player.rect.center)

    # ------------------------------------------------------------------ building
    def _spawn_entities(self):
        a = self.assets
        rows = self.data.rows
        # sign texts are handed out left-to-right across the map
        sign_cells = sorted((x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == "?")
        sign_text = {cell: (self.data.signs[i] if i < len(self.data.signs) else "...")
                     for i, cell in enumerate(sign_cells)}
        theme = self.theme
        tree_set = a.trees[theme["tree"]]
        visited_f = set()
        for ty, row in enumerate(rows):
            for tx, ch in enumerate(row):
                cx = tx * TILE + TILE / 2
                bottom = (ty + 1) * TILE
                top = ty * TILE
                if ch == "P":
                    self.player = Player(cx, bottom, a)
                    self.player.level = self
                elif ch in ("E", "L"):
                    self.add(ExitDoor(cx, bottom, a, locked=(ch == "L")))
                elif ch == "C":
                    self.add(Checkpoint(cx, bottom, a))
                elif ch == "?":
                    self.add(Sign(cx, bottom, a, sign_text[(tx, ty)]))
                elif ch == "M":
                    end = self._track_end(rows, tx, ty)
                    self.add(MovingPlatform(tx * TILE, top, end, a))
                elif ch == "F" and (tx, ty) not in visited_f:
                    n = 0
                    while tx + n < len(row) and row[tx + n] == "F":
                        visited_f.add((tx + n, ty))
                        n += 1
                    fp = FallingPlatform(tx * TILE, top, a)
                    fp.rect.w = n * TILE
                    fp.image = self._plank_image(n)
                    fp.home = pygame.Vector2(tx * TILE, top)
                    self.add(fp)
                elif ch == "o":
                    self.add(Coin(cx, top + TILE / 2, a.props["coin"]))
                elif ch == "h":
                    self.add(Potion(cx, top + TILE / 2, a.props["potion"]))
                elif ch == "k":
                    self.add(Key(cx, top + TILE / 2, a.props["key"]))
                elif ch == "G":
                    self.add(Gem(cx, top + TILE / 2, a.props["gem"]))
                elif ch == "c":
                    self.add(Chest(cx, bottom, a))
                elif ch in ENEMY_TYPES:
                    enemy = ENEMY_TYPES[ch](cx, bottom, a)
                    self.add(enemy)
                    self.enemy_total += 1
                elif ch == "T":
                    self._decor(cx, bottom + 6, tree_set["xl"], "back")
                elif ch == "t":
                    self._decor(cx, bottom + 6, tree_set["m"], "back")
                elif ch == "y":
                    self._decor(cx, bottom + 4, tree_set["s"], "back")
                elif ch == "u":
                    self._decor(cx, bottom + 6, a.props[theme["bush"]], "back")
                elif ch == "m":
                    self._decor(cx, bottom, a.props[self.rng.choice(["mushroom_s", "mushroom_s2"])], "front")
                elif ch == "n":
                    self._decor(cx, bottom, a.props[self.rng.choice(["mushroom_l", "mushroom_t"])], "front")
                elif ch == "f":
                    self._decor(cx, bottom, a.props["fence"], "front")
                elif ch == "r":
                    name = self.rng.choice(["rock_moss_s", "rock_s", "rock_m", "rock_moss_m"])
                    self._decor(cx, bottom + 2, a.props[name], "back")
                elif ch == "w":
                    self._decor(cx, bottom, a.props[self.rng.choice(["lavender", "flower_blue", "reeds"])], "front")
                elif ch == "i":
                    self._decor(cx, bottom + 2, a.props["fern"], "front")

    def _decor(self, x, bottom, image, depth):
        d = Decoration(x, bottom, image, depth, flip=self.rng.random() < 0.5)
        (self.decor_back if depth == "back" else self.decor_front).append(d)

    def _track_end(self, rows, tx, ty):
        """Moving platform path: each '-' to the right of M is one tile of horizontal travel,
        each ':' below M is one tile of vertical travel."""
        n = 0
        while tx + 1 + n < len(rows[ty]) and rows[ty][tx + 1 + n] == "-":
            n += 1
        if n:
            return ((tx + n) * TILE, ty * TILE)
        m = 0
        while ty + 1 + m < len(rows) and tx < len(rows[ty + 1 + m]) and rows[ty + 1 + m][tx] == ":":
            m += 1
        return (tx * TILE, (ty + m) * TILE)

    def _plank_image(self, n):
        a = self.assets
        img = pygame.Surface((n * TILE, 10), pygame.SRCALPHA)
        for i in range(n):
            col = 5 if i == 0 else (7 if i == n - 1 else 6)
            img.blit(a.tiles, (i * TILE, 0), (col * TILE, 6 * TILE, TILE, 10))
        return img

    def add(self, entity):
        entity.level = self
        if hasattr(entity, "hittable"):
            self.enemies.append(entity)
        elif getattr(entity, "solid_platform", False):
            self.platforms.append(entity)
        else:
            self.objects.append(entity)

    # ------------------------------------------------------------------ events
    def popup(self, text, x, y, color=(255, 255, 255)):
        self.popups.append([text, float(x), float(y), 1.4, color])

    def hitstop(self, t):
        self.hitstop_timer = max(self.hitstop_timer, t)

    def complete(self):
        if not self.completed:
            self.completed = True
            self.player.state = "exit"
            self.audio.play("door")

    def respawn_player(self):
        self.stats["deaths"] += 1
        self.player.respawn(self.checkpoint)
        self.camera.snap(*self.player.rect.center)

    def try_interact(self):
        """UP pressed: use the door / chest the player is standing at."""
        for obj in self.objects:
            if hasattr(obj, "interact") and obj.rect.colliderect(self.player.rect):
                obj.interact(self.player)
                return True
        return False

    # ------------------------------------------------------------------ loop
    def update(self, dt):
        self.anim_time += dt
        if self.hitstop_timer > 0:
            self.hitstop_timer -= dt
            return
        self.time += dt if not self.completed else 0
        self.active_sign = None
        for p in self.platforms:
            p.update(dt)
        self.player.update(dt)
        if self.input.pressed("up") and not self.player.is_dead and self.player.state != "exit":
            self.try_interact()
        for e in self.enemies:
            # only simulate enemies near the camera (saves time on big maps)
            if abs(e.rect.centerx - self.player.rect.centerx) < VIEW_W * 1.2 or e.dying:
                e.update(dt)
        for o in self.objects:
            o.update(dt)
        self.enemies = [e for e in self.enemies if e.alive]
        self.objects = [o for o in self.objects if o.alive]
        self.particles.update(dt)
        for pop in self.popups:
            pop[2] -= 18 * dt
            pop[3] -= dt
        self.popups = [p for p in self.popups if p[3] > 0]
        self._ambient(dt)
        p = self.player
        self.camera.update(dt, p.rect.centerx, p.rect.centery, p.facing, p.vy, p.on_ground)

    def _ambient(self, dt):
        cam = self.camera
        self.leaf_timer -= dt
        if self.leaf_timer <= 0:
            self.leaf_timer = 0.35
            x = cam.x + random.uniform(0, VIEW_W + 60)
            self.particles.leaf(x, cam.y - 6, self.theme["leaf"])
        if self.theme.get("fireflies") and random.random() < dt * 2.5:
            self.particles.firefly(cam.x + random.uniform(0, VIEW_W), cam.y + random.uniform(40, VIEW_H - 20))
        # bubbles rising in water that is on screen
        cells = self.tilemap.water_cells
        if cells and random.random() < dt * 25:
            x, y, top = random.choice(cells)
            px, py = x * TILE + random.uniform(2, 14), y * TILE + random.uniform(4, 14)
            if not top and cam.x - 16 < px < cam.x + VIEW_W + 16 and cam.y - 16 < py < cam.y + VIEW_H + 16:
                depth = 0
                while self.tilemap.kind(x, y - depth - 1) == WATER:
                    depth += 1
                self.particles.add(px, py, 0, -22, (depth * TILE + 6) / 22, (190, 230, 255), size=1)

    def draw(self, surface):
        cam = self.camera
        cx, cy = cam.ix, cam.iy
        self.background.draw(surface, cx, cy)
        self.tilemap.draw_backwall(surface, cx, cy)
        view = pygame.Rect(cx - 140, cy - 120, VIEW_W + 280, VIEW_H + 240)
        for d in self.decor_back:
            if view.colliderect(d.rect):
                d.draw(surface, cx, cy)
        self.tilemap.draw_water_back(surface, cx, cy, self.anim_time)
        self.tilemap.draw(surface, cx, cy)
        for d in self.decor_front:
            if view.colliderect(d.rect):
                d.draw(surface, cx, cy)
        drawables = [e for e in self.objects + self.platforms + self.enemies if view.colliderect(e.rect)]
        drawables.sort(key=lambda e: e.layer)
        for e in drawables:
            e.draw(surface, cx, cy)
        self.player.draw(surface, cx, cy)
        self.tilemap.draw_water_front(surface, cx, cy)
        self.particles.draw(surface, cx, cy)
        self.background.draw_ambient(surface)
        self._draw_prompts(surface, cx, cy)
        font = self.assets.font
        for text, x, y, life, color in self.popups:
            if life > 0.2 or int(life * 20) % 2 == 0:
                font.draw(surface, text, (x - cx, y - cy), color, 1, (20, 16, 14), align="center")

    def _draw_prompts(self, surface, cx, cy):
        p = self.player
        if p.is_dead or p.state == "exit":
            return
        for obj in self.objects:
            if getattr(obj, "prompt", False) and obj.rect.colliderect(p.rect):
                x = obj.rect.centerx - cx
                y = obj.rect.top - cy - 14 + round(abs(((self.time * 2) % 2) - 1) * 2)
                pygame.draw.rect(surface, (20, 16, 14), (x - 8, y - 1, 17, 11))
                pygame.draw.rect(surface, (240, 220, 170), (x - 7, y, 15, 9))
                label = "^" if self.input.last_device == "gamepad" else "W"
                self.assets.font.draw(surface, label, (x + 1, y + 1), (40, 30, 20), align="center")
                break
