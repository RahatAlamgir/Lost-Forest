"""Level checker and previewer.

    python tools/level_tool.py check            validate every level file
    python tools/level_tool.py preview [name]   render full-map PNGs into tools/previews/

The preview draws the real tiles, sprites and entities, which makes it easy to
spot misplaced platforms after editing a level text file.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from lostforest.world.level import discover_levels, Level  # noqa: E402

PREVIEW_DIR = ROOT / "tools" / "previews"
KNOWN = set(" .#RS=_~^PELC?MFohkGcsbzTtyumnfrwi-:")


def check(levels):
    ok = True
    for data in levels:
        problems = []
        rows = data.rows
        text = "".join(rows)
        if text.count("P") != 1:
            problems.append(f"needs exactly one 'P' (found {text.count('P')})")
        if text.count("E") + text.count("L") < 1:
            problems.append("no exit door ('E' or 'L')")
        if "L" in text and "k" not in text:
            problems.append("locked door 'L' but no key 'k'")
        if text.count("G") > 1:
            problems.append("more than one gem 'G'")
        if text.count("?") > len(data.signs):
            problems.append(f"{text.count('?')} signs on the map but only {len(data.signs)} 'sign:' lines")
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch not in KNOWN:
                    problems.append(f"unknown character {ch!r} at column {x}, row {y}")
        widths = {len(r) for r in rows}
        if len(widths) > 1:
            problems.append(f"rows have different widths {sorted(widths)} (they are padded, check alignment)")
        status = "OK " if not problems else "ERR"
        print(f"[{status}] {data.path.name}: {len(rows[0]) if rows else 0}x{len(rows)}  "
              f"coins={data.coin_total} gem={'yes' if data.has_gem else 'no'}")
        for p in problems:
            print("      -", p)
        ok = ok and not problems
    return ok


def preview(levels, only=None):
    from lostforest.app import App
    app = App(headless=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for data in levels:
        if only and only not in data.id:
            continue
        lvl = Level(data, app)
        w, h = lvl.width, lvl.height
        out = pygame.Surface((w, h))
        cam = lvl.camera
        # render in screen-sized tiles so the parallax looks right in each piece
        from lostforest.settings import VIEW_W, VIEW_H
        screen = pygame.Surface((VIEW_W, VIEW_H))
        for cy in range(0, h, VIEW_H):
            for cx in range(0, w, VIEW_W):
                cam.x = min(cx, max(0, w - VIEW_W))
                cam.y = min(cy, max(0, h - VIEW_H))
                cam.offset = (0, 0)
                lvl.draw(screen)
                out.blit(screen, (cam.ix, cam.iy))
        # entity hitboxes for debugging
        for e in lvl.enemies:
            pygame.draw.rect(out, (255, 60, 60), e.rect, 1)
        for p in lvl.platforms:
            if hasattr(p, "end"):
                pygame.draw.line(out, (255, 255, 0), p.start + (36, 0), p.end + (36, 0), 1)
        pygame.draw.rect(out, (60, 255, 60), lvl.player.rect, 1)
        path = PREVIEW_DIR / f"{data.id}.png"
        pygame.image.save(out, str(path))
        print("wrote", path)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    levels = discover_levels()
    if cmd == "check":
        sys.exit(0 if check(levels) else 1)
    elif cmd == "preview":
        preview(levels, sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print(__doc__)
