"""Tile kinds, the level-map legend, and auto-tiling rules for the Lost Forest tileset."""

# Collision kinds
EMPTY = 0
SOLID = 1
ONEWAY = 2
WATER = 3
SPIKES = 4

# Map characters that produce terrain
TERRAIN = {
    "#": SOLID,    # grassy earth (auto-tiled)
    "R": SOLID,    # rocky earth (auto-tiled)
    "S": SOLID,    # mossy stone bricks
    "=": ONEWAY,   # wooden plank
    "_": ONEWAY,   # rope-bridge deck
    "~": WATER,
    "^": SPIKES,
}

# Auto-tile blocks in Tiles.png (tile coordinates).
# overhang row is drawn one tile ABOVE a top tile (grass blades / rock tops).
BLOCKS = {
    "#": {"overhang": 0, "top": 1, "middle": (2, 3), "bottom": 4, "cols": (0, 1, 2, 3, 4)},
    "R": {"overhang": 5, "top": 6, "middle": (7, 8), "bottom": 9, "cols": (0, 1, 2, 3, 4)},
}


def _hash(x, y):
    """Deterministic per-cell pseudo random (keeps variants stable between runs)."""
    h = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return h ^ (h >> 16)


def autotile(grid, x, y):
    """Return a list of (src_col, src_row, dy_tiles, sheet) pieces to draw for cell (x, y).

    sheet is "tiles" (Tiles.png) or "hive" (Hive.png).
    """
    ch = grid.char(x, y)

    def solid(cx, cy):
        return grid.kind(cx, cy) == SOLID

    def same(cx, cy, c=ch):
        return grid.char(cx, cy) == c

    if ch in BLOCKS:
        b = BLOCKS[ch]
        top = not solid(x, y - 1)
        bottom = not solid(x, y + 1) and grid.in_bounds(x, y + 1)
        left_open = not solid(x - 1, y)
        right_open = not solid(x + 1, y)
        if left_open and not right_open:
            col = b["cols"][0]
        elif right_open and not left_open:
            col = b["cols"][4]
        elif left_open and right_open:
            col = b["cols"][0] if _hash(x, y) & 1 else b["cols"][4]
        else:
            col = b["cols"][1 + _hash(x, y) % 3]
        pieces = []
        if top:
            pieces.append((col, b["top"], 0, "tiles"))
            pieces.append((col, b["overhang"], -1, "tiles"))
        elif bottom:
            pieces.append((col, b["bottom"], 0, "tiles"))
        else:
            pieces.append((col, b["middle"][(y + _hash(x, 0)) % 2], 0, "tiles"))
        return pieces

    if ch == "S":
        return [(10 + (x + _hash(0, y)) % 3, 12 + y % 2, 0, "tiles")]

    if ch == "=":
        l, r = same(x - 1, y), same(x + 1, y)
        col = 6 if (l and r) else (5 if r else (7 if l else 6))
        return [(col, 6, 0, "tiles")]

    if ch == "_":
        l, r = same(x - 1, y), same(x + 1, y)
        if not l:
            return [(5, 9, 0, "tiles")]
        if not r:
            return [(9, 9, 0, "tiles")]
        return [(6 + _hash(x, y) % 3, 9, 0, "tiles")]

    if ch == "^":
        return [(_hash(x, y) % 3, 10, 0, "hive")]

    # water is animated and drawn separately
    return []
