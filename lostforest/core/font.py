"""A crisp 5x7 bitmap font so text stays pixel-perfect at the low internal resolution.

Lower-case letters are rendered as upper-case. Glyphs are trimmed to their used
columns, giving proportional spacing.
"""
import pygame

_GLYPHS = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": [".#.", "##.", ".#.", ".#.", ".#.", ".#.", "###"],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    ".": [".", ".", ".", ".", ".", ".", "#"],
    ",": ["..", "..", "..", "..", "..", ".#", "#."],
    "!": ["#", "#", "#", "#", "#", ".", "#"],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    ":": [".", "#", ".", ".", ".", "#", "."],
    ";": ["..", ".#", "..", "..", "..", ".#", "#."],
    "'": ["#", "#", ".", ".", ".", ".", "."],
    '"': ["#.#", "#.#", "...", "...", "...", "...", "..."],
    "-": ["....", "....", "....", "####", "....", "....", "...."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    "=": ["....", "....", "####", "....", "####", "....", "...."],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "/": ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
    "(": ["..#", ".#.", "#..", "#..", "#..", ".#.", "..#"],
    ")": ["#..", ".#.", "..#", "..#", "..#", ".#.", "#.."],
    "<": ["...#", "..#.", ".#..", "#...", ".#..", "..#.", "...#"],
    ">": ["#...", ".#..", "..#.", "...#", "..#.", ".#..", "#..."],
    "%": ["##..#", "##.#.", "...#.", "..#..", ".#...", ".#.##", "#..##"],
    "*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
    "#": [".#.#.", "#####", ".#.#.", ".#.#.", "#####", ".#.#.", "....."],
    "x": [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    "^": ["..#..", ".#.#.", "#...#", ".....", ".....", ".....", "....."],
}

GLYPH_H = 7
SPACE_W = 3
LETTER_SPACING = 1
LINE_SPACING = 3


class BitmapFont:
    """Renders text with the built-in 5x7 glyph set at integer scales."""

    def __init__(self):
        self._masks = {}
        for ch, rows in _GLYPHS.items():
            w = len(rows[0])
            surf = pygame.Surface((w, GLYPH_H), pygame.SRCALPHA)
            for y, row in enumerate(rows):
                for x, c in enumerate(row):
                    if c == "#":
                        surf.set_at((x, y), (255, 255, 255, 255))
            self._masks[ch] = surf
        self._cache = {}

    def _glyph(self, ch):
        if ch in self._masks:
            return self._masks[ch]
        up = ch.upper()
        return self._masks.get(up, self._masks["?"])

    def line_width(self, text, scale=1):
        w = 0
        for ch in text:
            if ch == " ":
                w += SPACE_W + LETTER_SPACING
            else:
                w += self._glyph(ch).get_width() + LETTER_SPACING
        return max(0, w - LETTER_SPACING) * scale

    def size(self, text, scale=1):
        lines = text.split("\n")
        w = max(self.line_width(line, scale) for line in lines)
        h = (len(lines) * (GLYPH_H + LINE_SPACING) - LINE_SPACING) * scale
        return w, h

    def render(self, text, color=(255, 255, 255), scale=1, shadow=None):
        """Return a surface with the text. `shadow` is an optional colour drawn 1px down-right."""
        key = (text, tuple(color), scale, tuple(shadow) if shadow else None)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        w, h = self.size(text, 1)
        pad = 1 if shadow else 0
        base = pygame.Surface((w + pad, h + pad), pygame.SRCALPHA)
        for layer_col, off in ((shadow, 1), (color, 0)) if shadow else ((color, 0),):
            y = off
            for line in text.split("\n"):
                x = off
                for ch in line:
                    if ch == " ":
                        x += SPACE_W + LETTER_SPACING
                        continue
                    g = self._glyph(ch).copy()
                    g.fill((*layer_col[:3], 255), special_flags=pygame.BLEND_RGBA_MULT)
                    base.blit(g, (x, y))
                    x += g.get_width() + LETTER_SPACING
                y += GLYPH_H + LINE_SPACING
        if scale != 1:
            base = pygame.transform.scale(base, (base.get_width() * scale, base.get_height() * scale))
        if len(self._cache) > 600:
            self._cache.clear()
        self._cache[key] = base
        return base

    def draw(self, surface, text, pos, color=(255, 255, 255), scale=1, shadow=None, align="left"):
        """Draw text. align: left | center | right (relative to pos x)."""
        img = self.render(text, color, scale, shadow)
        x, y = pos
        if align == "center":
            x -= img.get_width() // 2
        elif align == "right":
            x -= img.get_width()
        surface.blit(img, (int(x), int(y)))
        return img.get_rect(topleft=(int(x), int(y)))

    def wrap(self, text, max_width, scale=1):
        """Greedy word wrap to a list of lines."""
        lines = []
        for para in text.split("\n"):
            words = para.split(" ")
            cur = ""
            for word in words:
                test = word if not cur else cur + " " + word
                if self.line_width(test, scale) <= max_width:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = word
            lines.append(cur)
        return lines
