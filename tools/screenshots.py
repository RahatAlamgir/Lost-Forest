"""Render README screenshots straight from the game (headless, no window needed).

    python tools/screenshots.py

Writes 960x540 PNGs (2x pixel scale) to docs/screenshots/.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from lostforest import settings as S  # noqa: E402
import lostforest.core.save as save_mod  # noqa: E402

# never touch the player's real save file
save_mod.SAVE_FILE = ROOT / "build" / "_screenshot_save.json"

from lostforest.app import App  # noqa: E402
from lostforest.scenes.gameplay import GameplayScene  # noqa: E402
from lostforest.scenes.title import TitleScene  # noqa: E402

OUT = ROOT / "docs" / "screenshots"
SCALE = 2
TILE = S.TILE

app = App(headless=True)
surface = pygame.Surface((S.VIEW_W, S.VIEW_H))


def frames(n, hold=(), tap=()):
    inp = app.input
    for a in hold:
        inp.inject(a, True)
    for a in tap:
        inp.inject(a, True)
    for i in range(n):
        app.step()
        if i == 0:
            for a in tap:
                if a not in hold:
                    inp.inject(a, False)
    for a in hold:
        inp.inject(a, False)
    inp.end_tick()


def save(name):
    app.scenes.draw(surface)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    pygame.image.save(pygame.transform.scale_by(surface, SCALE), str(path))
    print("wrote", path.relative_to(ROOT))


def find(level, ch, nth=0):
    """(column, row) of the nth occurrence of a map character, scanning left to right."""
    cells = sorted((x, y) for y, row in enumerate(level.data.rows) for x, c in enumerate(row) if c == ch)
    return cells[nth]


def start(index):
    app.scenes.switch(GameplayScene(app, index), fade=False)
    scene = app.scenes.top
    scene.t = 10.0                      # skip the level-name banner
    return scene.level


def place(level, x, bottom):
    p = level.player
    p.rect.midbottom = (x, bottom)
    p.vx = p.vy = 0
    level.camera.snap(*p.rect.center)


# ---------------------------------------------------------------------------------------- title
app.scenes.switch(TitleScene(app), fade=False)
frames(150)
save("title")

# ---------------------------------------------------------------------------------------- level 1: sword vs snail
lvl = start(0)
snail = next(e for e in lvl.enemies if type(e).__name__ == "Snail")
place(lvl, snail.rect.centerx - 140, snail.rect.bottom)
frames(40)
snail.facing = -1                          # walking towards the hero
lvl.player.rect.midbottom = (snail.rect.centerx - 62, snail.rect.bottom)
lvl.player.facing = 1
frames(2)
frames(6, tap=("attack",))                 # mid-swing, just before the blade connects
save("forest_edge")

# ---------------------------------------------------------------------------------------- level 2: inside the cave
lvl = start(1)
x, y = find(lvl, "h")                      # the potion lies inside the first cave
place(lvl, x * TILE - 90, (y + 1) * TILE)
frames(45, hold=("right",))
save("mossy_hollow")

# ---------------------------------------------------------------------------------------- level 3: bees over the log crossing
lvl = start(2)
x, y = find(lvl, "M")
place(lvl, (x - 3) * TILE, (y + 2) * TILE)
frames(60)
frames(14, hold=("right", "jump"), tap=("jump",))
save("bee_grove")

# ---------------------------------------------------------------------------------------- level 4: the ridge top
lvl = start(3)
x, y = find(lvl, "G")
place(lvl, (x - 6) * TILE, (y + 7) * TILE)
frames(30)
frames(12, hold=("right", "jump"), tap=("jump",))
save("autumn_ridge")

# ---------------------------------------------------------------------------------------- level 5: mid-air dash at dusk
lvl = start(4)
wx, wy, _ = next(c for c in lvl.tilemap.water_cells if c[2])
place(lvl, (wx - 2) * TILE, (wy - 2) * TILE)
frames(30)
frames(10, hold=("right", "jump"), tap=("jump",))
frames(5, hold=("right",), tap=("dash",))
save("heart_of_the_forest")

# ---------------------------------------------------------------------------------------- endless run
from lostforest.scenes.endless import EndlessScene  # noqa: E402
from lostforest.world.runner import RunWorld  # noqa: E402

app.scenes.switch(EndlessScene(app), fade=False)
scene = app.scenes.top
scene.level = world = RunWorld(app, seed=11)      # fixed seed -> same course every time
world.start()
p = world.player
tm = world.tilemap
for f in range(60 * 40):
    # tiny autopilot: jump when the ground ends, spikes or an enemy are just ahead
    ahead = int((p.rect.right + world.speed * 0.18) // TILE)
    g = int((p.rect.bottom + 1) // TILE)
    danger = tm.kind(ahead, g) == 0 or tm.kind(ahead, g - 1) in (1, 4) or any(
        0 < e.rect.left - p.rect.right < world.speed * 0.25 and abs(e.rect.bottom - p.rect.bottom) < 40
        for e in world.enemies if not e.dying)
    if p.on_ground and danger:
        frames(1, hold=("jump",), tap=("jump",))
    else:
        frames(1, hold=("jump",) if (not p.on_ground and p.vy < 0) else ())
    if world.distance > 160 and not p.on_ground and p.vy > -60 and world.enemies:
        break
save("endless_run")

try:
    save_mod.SAVE_FILE.unlink()
except OSError:
    pass
