"""Loads every image the game uses and slices sprite sheets into animations / tiles.

All source rectangles for the Lost Forest art pack are defined here, so if the
art changes only this file needs updating.
"""
import pygame

from ..settings import ASSETS, TILE
from .animation import Animation
from .font import BitmapFont

# --------------------------------------------------------------------------
# Sprite-sheet definitions: (path, frame_w, frame_h, frame indices or None, fps, loop, anchor)
# --------------------------------------------------------------------------
PLAYER_ANIMS = {
    "idle":    ("Character/Idle/Idle-Sheet.png", 64, 80, None, 6, True, (32, 64)),
    "run":     ("Character/Run/Run-Sheet.png", 80, 80, None, 14, True, (43, 67)),
    "dash":    ("Character/Run/Run-Sheet.png", 80, 80, [2], 1, False, (43, 67)),
    "rise":    ("Character/Jumlp-All/Jump-All-Sheet.png", 64, 64, [2, 3, 4, 5, 6], 12, False, (26, 63)),
    "fall":    ("Character/Jumlp-All/Jump-All-Sheet.png", 64, 64, [7, 8, 9, 10, 11], 10, False, (26, 63)),
    "land":    ("Character/Jumlp-All/Jump-All-Sheet.png", 64, 64, [12, 13, 14], 20, False, (27, 64)),
    "attack1": ("Character/Attack-01/Attack-01-Sheet.png", 96, 80, [0, 1, 2, 3, 4], 16, False, (47, 64)),
    "attack2": ("Character/Attack-01/Attack-01-Sheet.png", 96, 80, [5, 6, 7], 13, False, (47, 64)),
    "dead":    ("Character/Dead/Dead-Sheet.png", 80, 64, None, 9, False, (31, 48)),
}

BOAR_ANIMS = {
    "idle": ("Mob/Boar/Idle/Idle-Sheet.png", 48, 32, None, 6, True, (24, 32)),
    "walk": ("Mob/Boar/Walk/Walk-Base-Sheet.png", 48, 32, None, 10, True, (24, 32)),
    "run":  ("Mob/Boar/Run/Run-Sheet.png", 48, 32, None, 16, True, (24, 32)),
    "hit":  ("Mob/Boar/Hit-Vanish/Hit-Sheet.png", 48, 32, None, 14, False, (24, 32)),
}

SNAIL_ANIMS = {
    "walk":   ("Mob/Snail/walk-Sheet.png", 48, 32, None, 8, True, (24, 32)),
    "hide":   ("Mob/Snail/Hide-Sheet.png", 48, 32, [0, 1, 2, 3], 14, False, (24, 32)),
    "shell":  ("Mob/Snail/Hide-Sheet.png", 48, 32, [4, 5, 6, 7], 6, True, (24, 32)),
    "unhide": ("Mob/Snail/Hide-Sheet.png", 48, 32, [3, 2, 1, 0], 12, False, (24, 32)),
    "dead":   ("Mob/Snail/Dead-Sheet.png", 48, 32, None, 12, False, (24, 32)),
}

BEE_ANIMS = {
    "fly":    ("Mob/Small Bee/Fly/Fly-Sheet.png", 64, 64, None, 14, True, (31, 32)),
    "attack": ("Mob/Small Bee/Attack/Attack-Sheet.png", 64, 64, None, 14, True, (31, 32)),
    "hit":    ("Mob/Small Bee/Hit/Hit-Sheet.png", 64, 64, None, 14, False, (31, 32)),
}

# Facing of the native artwork
PLAYER_FACING = 1   # hero faces right
MOB_FACING = -1     # all monsters face left

# --------------------------------------------------------------------------
# Single images (path, rect)
# --------------------------------------------------------------------------
PROPS = {
    "coin":        ("Assets/Tiles.png", (245, 339, 6, 9)),
    "key":         ("Assets/Tiles.png", (242, 323, 12, 7)),
    "potion":      ("Assets/Tiles.png", (242, 353, 12, 15)),
    "potion_blue": ("Assets/Tiles.png", (274, 353, 12, 15)),
    "chest":       ("Assets/Tiles.png", (288, 272, 32, 32)),
    "chest_open":  ("Assets/Tiles.png", (320, 272, 32, 32)),
    "gem":         ("Assets/Hive.png", (99, 99, 10, 10)),
    "lamp":        ("Assets/Hive.png", (112, 121, 16, 48)),
    "door":        ("Assets/Buildings.png", (341, 122, 38, 54)),
    "post":        ("Assets/Buildings.png", (226, 176, 12, 34)),
    "log":         ("Assets/Tiles.png", (164, 171, 75, 16)),
    "plank_small": ("Assets/Tiles.png", (80, 96, 48, 10)),
    # decoration
    "mushroom_s":  ("Assets/Tiles.png", (240, 240, 16, 16)),
    "mushroom_s2": ("Assets/Tiles.png", (240, 256, 16, 16)),
    "mushroom_l":  ("Assets/Tiles.png", (256, 240, 32, 32)),
    "mushroom_t":  ("Assets/Tiles.png", (288, 240, 32, 32)),
    "flower_blue": ("Assets/Tiles.png", (240, 272, 16, 32)),
    "lavender":    ("Assets/Tiles.png", (272, 272, 16, 32)),
    "reeds":       ("Assets/Tiles.png", (256, 304, 16, 32)),
    "fern":        ("Assets/Tiles.png", (316, 352, 40, 32)),
    "bush_green":  ("Assets/Tiles.png", (274, 5, 124, 43)),
    "bush_yellow": ("Assets/Tiles.png", (274, 53, 124, 43)),
    "bush_olive":  ("Assets/Tiles.png", (274, 101, 124, 43)),
    "bush_dark":   ("Assets/Tiles.png", (274, 149, 124, 43)),
    "rocks_a":     ("Assets/Tiles.png", (0, 336, 82, 32)),
    "rocks_b":     ("Assets/Tiles.png", (82, 336, 80, 32)),
    "rocks_c":     ("Assets/Tiles.png", (162, 336, 78, 32)),
    "rock_moss_l": ("Assets/Props-Rocks.png", (6, 2, 55, 78)),
    "rock_moss_m": ("Assets/Props-Rocks.png", (224, 6, 48, 42)),
    "rock_moss_s": ("Assets/Props-Rocks.png", (193, 18, 30, 30)),
    "rock_l":      ("Assets/Props-Rocks.png", (10, 166, 46, 34)),
    "rock_m":      ("Assets/Props-Rocks.png", (163, 166, 43, 34)),
    "rock_s":      ("Assets/Props-Rocks.png", (72, 177, 31, 23)),
    "fence":       ("Assets/Buildings.png", (168, 176, 36, 22)),
    "hive":        ("Assets/Tiles.png", (192, 104, 32, 48)),
}

HUD_ICONS = {
    "heart":       ("HUD/Base-01.png", (65, 145, 14, 14)),
    "heart_empty": ("HUD/Base-01.png", (65, 177, 14, 14)),
    "question":    ("HUD/Base-01.png", (0, 224, 16, 16)),
    "skull":       ("HUD/Base-01.png", (0, 256, 16, 16)),
    "clock":       ("HUD/Base-01.png", (0, 272, 16, 16)),
    "trophy":      ("HUD/Base-01.png", (48, 192, 16, 16)),
    "chest_icon":  ("HUD/Base-01.png", (32, 192, 16, 16)),
    "arrow_r":     ("HUD/Base-01.png", (0, 176, 16, 16)),
    "arrow_l":     ("HUD/Base-01.png", (0, 192, 16, 16)),
    "exclaim":     ("HUD/Base-01.png", (0, 208, 16, 16)),
}

TREE_COLOURS = ("Green", "Golden", "Red", "Yellow", "Dark")
TREE_RECTS = {   # complete trees (canopy + trunk), largest to smallest
    "xl": (0, 0, 107, 368),
    "l": (2, 391, 108, 313),
    "m": (4, 720, 88, 208),
    "s": (6, 944, 88, 144),
    "xs": (5, 1092, 70, 108),
}
TREE_SILHOUETTES = {
    "xl": (224, 0, 107, 368),
    "l": (226, 391, 108, 313),
    "m": (196, 720, 88, 208),
    "s": (198, 944, 88, 144),
}


class Assets:
    """Central cache of loaded graphics. Create once after the display exists."""

    def __init__(self):
        self._images = {}
        self.font = BitmapFont()
        self.player = self._anims(PLAYER_ANIMS, PLAYER_FACING)
        self.boar = self._anims(BOAR_ANIMS, MOB_FACING)
        self.snail = self._anims(SNAIL_ANIMS, MOB_FACING)
        self.bee = self._anims(BEE_ANIMS, MOB_FACING)
        self.props = {k: self.crop(p, r) for k, (p, r) in PROPS.items()}
        self.icons = {k: self.crop(p, r) for k, (p, r) in HUD_ICONS.items()}
        self.trees = {
            colour: {size: self.crop(f"Trees/{colour}-Tree.png", rect) for size, rect in TREE_RECTS.items()}
            for colour in TREE_COLOURS
        }
        self.tree_silhouettes = {
            size: self.crop("Trees/Dark-Tree.png", rect) for size, rect in TREE_SILHOUETTES.items()
        }
        self.sky = self.image("Background/Background.png")
        self.pines_dark = self.crop("Trees/Background.png", (704, 16, 96, 240))
        self.pines_light = self.crop("Trees/Background.png", (800, 16, 96, 240))
        self.tiles = self.image("Assets/Tiles.png")
        self.hive_sheet = self.image("Assets/Hive.png")

    # ------------------------------------------------------------------
    def image(self, rel):
        img = self._images.get(rel)
        if img is None:
            path = ASSETS / rel
            img = pygame.image.load(str(path)).convert_alpha()
            self._images[rel] = img
        return img

    def crop(self, rel, rect):
        return self.image(rel).subsurface(pygame.Rect(rect)).copy()

    def tile(self, col, row, w=1, h=1, sheet=None):
        """Crop a block of 16x16 tiles from Tiles.png (or another sheet)."""
        src = sheet if sheet is not None else self.tiles
        return src.subsurface((col * TILE, row * TILE, w * TILE, h * TILE)).copy()

    def _sheet_frames(self, rel, fw, fh, indices):
        sheet = self.image(rel)
        count = sheet.get_width() // fw
        idx = indices if indices is not None else range(count)
        return [sheet.subsurface((i * fw, 0, fw, fh)).copy() for i in idx]

    def _anims(self, table, facing):
        out = {}
        for name, (rel, fw, fh, idx, fps, loop, anchor) in table.items():
            out[name] = Animation(self._sheet_frames(rel, fw, fh, idx), fps, loop, anchor, facing)
        return out
