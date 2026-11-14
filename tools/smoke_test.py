"""Headless smoke test: drives menus and every level with scripted input.

    python tools/smoke_test.py            run all checks
    python tools/smoke_test.py --shots    also save screenshots to tools/shots/

Exits with code 1 if anything raises or a check fails.
"""
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from lostforest import settings as S  # noqa: E402

# keep the player's real save untouched
S.SAVE_FILE = ROOT / "tools" / "_smoke_save.json"
import lostforest.core.save as save_mod  # noqa: E402
save_mod.SAVE_FILE = S.SAVE_FILE

from lostforest.app import App  # noqa: E402
from lostforest.scenes.title import TitleScene  # noqa: E402
from lostforest.scenes.gameplay import GameplayScene  # noqa: E402
from lostforest.scenes.common import levels  # noqa: E402

SHOTS = "--shots" in sys.argv
SHOT_DIR = ROOT / "tools" / "shots"
failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print("  FAIL:", msg)


class Driver:
    def __init__(self):
        self.app = App(headless=True)
        self.app.scenes.switch(TitleScene(self.app), fade=False)
        self.held = set()
        self.surf = pygame.Surface((S.VIEW_W, S.VIEW_H))

    def step(self, n=1, hold=(), tap=()):
        """Advance n frames. `hold` keys stay down (pressed only when newly held);
        `tap` keys are pressed for a single frame."""
        inp = self.app.input
        hold = set(hold)
        for a in self.held - hold:
            inp.inject(a, False)
        for a in hold - self.held:
            inp.inject(a, True)
        for a in tap:
            if a in hold and a in self.held:
                inp.inject(a, False)      # re-press a key that was already held
            inp.inject(a, True)
        self.held = hold
        for i in range(n):
            self.app.step()
            self.app.scenes.draw(self.surf)      # render every frame so drawing bugs are caught too
            if i == 0:
                for a in tap:
                    if a not in hold:
                        inp.inject(a, False)
        if n == 0:
            inp.end_tick()

    def settle(self):
        self.step(40)   # let fades finish

    def shot(self, name):
        if not SHOTS:
            return
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        surf = pygame.Surface((S.VIEW_W, S.VIEW_H))
        self.app.scenes.draw(surf)
        pygame.image.save(pygame.transform.scale_by(surf, 2), str(SHOT_DIR / f"{name}.png"))

    @property
    def top(self):
        return self.app.scenes.top


def test_menus(d):
    print("menus")
    d.settle()
    d.shot("01_title")
    check(isinstance(d.top, TitleScene), "title scene shown")
    title = d.top

    def choose(label):
        """Move the title menu cursor to `label` with the keyboard and confirm."""
        labels = [it.text() for it in title.menu.items]
        target = labels.index(label)
        while title.menu.index != target:
            d.step(1, tap=("down",))
        d.step(1, tap=("confirm",))

    # open controls and settings and back out
    choose("CONTROLS"); d.step(5)
    d.shot("02_controls")
    check(type(d.top).__name__ == "ControlsScene", "controls screen opens")
    d.step(1, tap=("back",)); d.step(5)
    choose("SETTINGS"); d.step(5)
    d.shot("03_settings")
    d.step(1, tap=("right",)); d.step(1, tap=("back",)); d.step(5)
    check(isinstance(d.top, TitleScene), "back to title after settings")
    # level select
    choose("SELECT LEVEL"); d.settle()
    d.shot("04_level_select")
    check(type(d.top).__name__ == "LevelSelectScene", "level select opens")
    d.step(1, tap=("back",)); d.settle()
    # endless run from the menu
    title = d.top
    choose("ENDLESS RUN"); d.settle()
    check(type(d.top).__name__ == "EndlessScene", "endless run opens from the title menu")
    d.step(1, tap=("back",)); d.settle()
    check(isinstance(d.top, TitleScene), "ESC on the endless start screen returns to the title")


def predict_landing(lvl, x, bottom, vx, vy, max_t=1.6):
    """Simulate a ballistic arc. Returns 'ground', 'hazard' or 'pit'."""
    from lostforest.world.tiles import SOLID, ONEWAY, WATER, SPIKES
    tm = lvl.tilemap
    dt = 1 / 60
    t = 0.0
    while t < max_t:
        vy = min(vy + S.GRAVITY * dt, S.MAX_FALL_SPEED)
        nb = bottom + vy * dt
        x += vx * dt
        if vy > 0 and t > 0.08:          # skip the tile we start on
            for px in (x - 5, x + 5):
                tx = int(px // 16)
                for ty in range(int(bottom // 16), int(nb // 16) + 1):
                    k = tm.kind(tx, ty)
                    top = ty * 16
                    if (k in (SOLID, ONEWAY) and tm.kind(tx, ty - 1) != SOLID
                            and bottom <= top + 0.5 <= nb + 0.5):
                        return "ground"
                    if k in (WATER, SPIKES) and nb >= top + 6:
                        return "hazard"
            for p in lvl.platforms:
                if p.collidable and p.rect.left < x < p.rect.right and bottom <= p.rect.top <= nb:
                    return "ground"
        bottom = nb
        if bottom > tm.pixel_h + 32:
            return "pit"
        t += dt
    return "pit"


def play_bot(d, index, seconds=70, trace=False):
    """Hold right, jump at walls/gaps, swing at enemies. Returns furthest x reached."""
    d.app.scenes.switch(GameplayScene(d.app, index), fade=False)
    d.held = set()          # entering a level resets the input state
    game = d.top
    lvl = game.level
    furthest = 0
    stuck = 0
    last_x = 0
    frames = int(seconds * S.FPS)
    tm = lvl.tilemap
    jump_hold = 0
    wait = 0
    for f in range(frames):
        if not isinstance(d.top, GameplayScene):
            break
        p = lvl.player
        hold = ["right"]
        tap = []
        # swing only when something is in reach
        if any(e.alive and not e.dying and 0 < e.rect.centerx - p.rect.centerx < 46
               and abs(e.rect.centery - p.rect.centery) < 40 for e in lvl.enemies) and p.state != "attack":
            tap.append("attack")
        edge_ahead = not tm.solid_ground_below(p.rect.right + 4, p.rect.bottom + 1, 0) and p.ground_platform is None
        wall_ahead = tm.is_solid(int((p.rect.right + 10) // 16), int((p.rect.bottom - 4) // 16))
        spikes_ahead = any(tm.kind(int((p.rect.right + dx) // 16), int((p.rect.bottom - 4) // 16)) == 4
                           for dx in (6, 12))
        edge_ahead = edge_ahead or spikes_ahead
        if p.on_ground and p.hurt_timer <= 0:
            jump_land = predict_landing(lvl, p.rect.centerx, p.rect.bottom, S.RUN_SPEED, S.JUMP_VELOCITY)
            if wall_ahead or p.hit_wall or (spikes_ahead and jump_land == "ground"):
                tap.append("jump")
                jump_hold = 24
            elif edge_ahead or (p.ground_platform is not None and
                                p.rect.right + 6 > p.ground_platform.rect.right):
                walk_land = predict_landing(lvl, p.rect.centerx + 8, p.rect.bottom, S.RUN_SPEED, 0)
                if walk_land == "ground" and wait < 120:
                    pass                          # safe to just walk off
                elif jump_land == "ground" or wait > 180:
                    tap.append("jump")
                    jump_hold = 24
                    wait = 0
                else:
                    hold.remove("right")           # wait for a platform to come by
                    wait += 1
        elif not p.on_ground and p.can_double and p.vy > -40:
            land = predict_landing(lvl, p.rect.centerx, p.rect.bottom, S.RUN_SPEED, p.vy)
            if land != "ground":
                if predict_landing(lvl, p.rect.centerx, p.rect.bottom, S.RUN_SPEED, S.DOUBLE_JUMP_VELOCITY) == "ground" \
                        or p.vy > 150:
                    tap.append("jump")
                    jump_hold = 20
        if "right" in hold and abs(p.rect.x - last_x) < 0.3 and p.on_ground:
            stuck += 1
            if stuck % 30 == 0:
                tap.append("jump")
                jump_hold = 24
        else:
            stuck = 0
        last_x = p.rect.x
        if jump_hold > 0:
            jump_hold -= 1
            hold.append("jump")
        if f % 4 == 0:
            tap.append("up")
        d.step(1, hold=hold, tap=tap)
        furthest = max(furthest, p.rect.right)
        if trace and f % 30 == 0:
            print(f"    t={f / 60:5.1f} col={p.rect.centerx / 16:6.1f} row={p.rect.bottom / 16:5.1f} "
                  f"hp={p.health} ground={p.on_ground} state={p.state}")
        if lvl.player.is_dead and lvl.player.dead_time > 2.0:
            # game over overlay: choose "try again"
            d.step(30)
            d.step(1, tap=("confirm",))
            d.step(2)
        if index == 0 and f == 200:
            d.shot("05_gameplay_l1")
        if lvl.completed:
            break
    return furthest, lvl


def test_levels(d):
    for i, data in enumerate(levels(d.app)):
        print(f"level {i + 1}: {data.name}")
        furthest, lvl = play_bot(d, i)
        pct = 100 * furthest / lvl.width
        print(f"  bot reached {pct:.0f}% of the level, coins {lvl.stats['coins']}/{lvl.coin_total}, "
              f"enemies {lvl.stats['enemies']}/{lvl.enemy_total}, falls {lvl.stats['deaths']}, done={lvl.completed}")
        check(furthest > 0, f"{data.name}: player moved")
        if SHOTS:
            d.shot(f"10_level{i + 1}_end")


def test_mechanics(d):
    print("mechanics")
    d.app.scenes.switch(GameplayScene(d.app, 0), fade=False)
    game = d.top
    lvl = game.level
    p = lvl.player
    d.step(30)
    check(p.on_ground, "player lands on the ground at start")
    x0 = p.rect.x
    d.step(30, hold=("right",))
    check(p.rect.x > x0 + 20, "player runs right")
    d.step(1, tap=("jump",), hold=("jump",))
    d.step(10, hold=("jump",))
    check(not p.on_ground and p.vy < 0 or p.rect.bottom < 15 * 16, "player jumps")
    d.step(60)
    # attack starts
    d.step(1, tap=("attack",))
    check(p.state == "attack", "attack starts")
    d.step(4, tap=("attack",))
    d.step(25)
    # damage + invulnerability
    hp = p.health
    p.take_damage(1, p.rect.centerx - 10)
    p.take_damage(1, p.rect.centerx - 10)
    check(p.health == hp - 1, "invulnerability prevents double hits")
    # pause overlay
    d.step(60)
    d.step(1, tap=("pause",))
    d.step(2)
    check(type(d.top).__name__ == "PauseScene", "pause opens")
    d.shot("06_pause")
    d.step(1, tap=("pause",))
    d.step(2)
    check(isinstance(d.top, GameplayScene), "pause closes")
    # death -> game over -> retry
    p.invuln = 0
    p.health = 1
    p.take_damage(1, p.rect.centerx)
    d.step(int(2.2 * S.FPS))
    check(type(d.top).__name__ == "GameOverScene", "game over shows after death")
    d.shot("07_game_over")
    d.step(30)
    d.step(1, tap=("confirm",))
    d.step(5)
    check(isinstance(d.top, GameplayScene) and not p.is_dead and p.health == p.max_health, "retry respawns player")
    # level completion flow
    door = next(o for o in lvl.objects if type(o).__name__ == "ExitDoor")
    p.rect.midbottom = door.rect.midbottom
    d.step(2)
    d.step(1, tap=("up",))
    d.step(int(2.0 * S.FPS))
    check(type(d.top).__name__ == "ResultsScene", "results screen after entering the door")
    d.step(90)
    d.shot("08_results")
    check(d.app.save.unlocked >= 2, "level 2 unlocked after finishing level 1")


def click(d, pos, button=1):
    """Feed a real mouse move + click through the input system."""
    inp = d.app.input
    inp.process_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
    d.step(1)
    inp.process_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))
    d.step(1)
    inp.process_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button))
    d.step(1)


def test_mouse_menus(d):
    print("mouse menus")
    d.app.scenes.switch(TitleScene(d.app), fade=False)
    d.step(3)
    title = d.top
    labels = [it.text() for it in title.menu.items]
    rect = title.menu._rects[labels.index("SELECT LEVEL")]
    click(d, rect.center)
    d.settle()
    check(type(d.top).__name__ == "LevelSelectScene", "clicking SELECT LEVEL opens level select")
    ls = d.top
    d.step(2)
    click(d, ls.row_rects[0].center)
    d.settle()
    check(isinstance(d.top, GameplayScene), "clicking a level row starts it")
    d.app.render()
    check(d.app._cursor_hidden, "cursor hidden during gameplay")


def test_moves(d):
    print("dash / fast drop / drop-through")
    d.app.scenes.switch(GameplayScene(d.app, 0), fade=False)
    d.held = set()
    lvl = d.top.level
    p = lvl.player
    d.step(20)
    x0 = p.rect.x
    d.step(1, tap=("dash",))
    check(p.state == "dash", "dash starts on the ground")
    d.step(12)
    check(p.rect.x - x0 > 45, f"ground dash covers distance ({p.rect.x - x0:.0f}px)")
    check(p.state == "normal", "dash ends")
    d.step(30)
    # air dash: once per jump
    d.step(1, tap=("jump",), hold=("jump",))
    d.step(10, hold=("jump",))
    d.step(1, tap=("dash",))
    check(p.state == "dash" and not p.on_ground, "air dash works")
    d.step(int(S.DASH_TIME * 60) + 2)
    p.dash_cooldown = 0          # isolate the "one air dash per jump" rule from the cooldown
    still_airborne = not p.on_ground
    d.step(1, tap=("dash",))
    check(still_airborne and p.state != "dash", "only one air dash per jump")
    d.step(80)
    check(p.on_ground, "landed after air dash")
    # fast drop
    d.step(1, tap=("jump",), hold=("jump",))
    d.step(8, hold=("jump",))
    d.step(12, hold=("down",))
    check(p.vy > S.MAX_FALL_SPEED * 0.9 or p.on_ground, f"fast drop speeds up the fall (vy={p.vy:.0f})")
    d.step(60)
    # drop through a plank with S
    plank_y = None
    for ty, row in enumerate(lvl.data.rows):
        tx = row.find("=")
        if tx >= 0:
            plank_y, plank_x = ty, tx
            break
    p.rect.midbottom = (plank_x * 16 + 24, plank_y * 16)
    p.vy = 0
    d.step(5)
    check(p.on_ground, "standing on a plank")
    d.step(1, tap=("down",))
    d.step(15)
    check(p.rect.top > plank_y * 16, "S drops through the plank")


def test_no_stacking(d):
    print("enemies don't stack")
    from lostforest.entities.enemies import Snail
    d.app.scenes.switch(GameplayScene(d.app, 0), fade=False)
    lvl = d.top.level
    p = lvl.player
    base = lvl.enemies[0]
    x = p.rect.centerx + 120
    a = Snail(x - 30, p.rect.bottom, d.app.assets)
    b = Snail(x + 30, p.rect.bottom, d.app.assets)
    a.facing, b.facing = 1, -1
    lvl.add(a)
    lvl.add(b)
    worst = 0
    for _ in range(300):
        d.step(1)
        worst = max(worst, a.rect.clip(b.rect).w)
    check(worst < 4, f"two snails walking into each other turn around (max overlap {worst:.0f}px)")


def test_enemy_hazards(d):
    print("enemies vs hazards")
    from lostforest.entities.enemies import Boar, Snail
    d.app.scenes.switch(GameplayScene(d.app, 1), fade=False)     # level 2 has a spike strip + boar
    lvl = d.top.level
    p = lvl.player
    tm = lvl.tilemap
    # find a spike tile sitting on the ground
    spike = next((x, y) for y, row in enumerate(lvl.data.rows) for x, c in enumerate(row) if c == "^")
    sx, sy = spike
    p.rect.midbottom = (sx * 16 - 100, (sy + 1) * 16)
    p.invuln = 99
    # a snail patrolling towards the spikes turns around instead of walking in
    s = Snail(sx * 16 - 40, (sy + 1) * 16, d.app.assets)
    s.facing = 1
    lvl.add(s)
    for _ in range(240):
        d.step(1)
    check(s.alive and not s.dying, "patrolling snail avoids spikes")
    # a boar charging across the spikes dies on them
    b = Boar(sx * 16 + 60, (sy + 1) * 16, d.app.assets)
    b.facing = -1
    lvl.add(b)
    before = lvl.stats["enemies"]
    b.set_state("charge")
    for _ in range(120):
        d.step(1)
        if b.state != "charge" and not b.dying:
            b.set_state("charge")
    check(b.dying or not b.alive, "charging boar dies on spikes")
    check(lvl.stats["enemies"] > before, "spike kill counts as a defeated enemy")
    # an enemy knocked into water dies
    wx, wy, _ = next(c for c in tm.water_cells if c[2])
    s2 = Snail(wx * 16 + 8, wy * 16 + 12, d.app.assets)
    lvl.add(s2)
    p.rect.midbottom = (s2.rect.centerx, s2.rect.bottom - 220)   # nearby (enemies only update near the hero)
    p.vy = 0
    for _ in range(25):
        d.step(1)
    check(s2.dying or not s2.alive, "snail in water dies")


def test_endless(d):
    print("endless run")
    from lostforest.scenes.endless import EndlessScene, EndlessOverScene
    d.app.save.endless = {"best_score": 0, "best_distance": 0, "runs": 0}
    d.app.scenes.switch(EndlessScene(d.app), fade=False)
    d.held = set()
    scene = d.top
    w = scene.level
    p = w.player
    d.step(30)
    check(not w.started and p.rect.x == w.start_x, "endless waits for the player to start")
    # this hero never jumps, so give him flat ground while scoring is checked
    gen = w.generator
    real_segment = type(gen).segment
    gen.segment = lambda: gen.flat(20, coins=False)
    for x in range(int(p.rect.right // 16), gen.x):
        w.tilemap.set_column(x, gen._ground(gen.g))
    d.step(1, tap=("jump",))
    check(w.started, "jump starts the run")
    d.step(240)
    check(w.distance > 20 and w.speed > 150 and not p.is_dead,
          f"hero auto-runs and speeds up ({w.distance:.0f} m)")
    check(len(w.tilemap.cols) < 400, "old ground columns are dropped (memory stays bounded)")
    # generate far ahead to make sure every pattern type can be built without errors
    target = gen.x + 3000
    while gen.x < target:
        real_segment(gen)
    check(len(w.enemies) > 0, "generator spawns enemies")
    check(all(e.hp == 1 for e in w.enemies), "endless enemies fall to a single hit")
    # attacking an enemy gives points straight away
    from lostforest.entities.enemies import Snail
    snail = w.generator.enemy(Snail, int(p.rect.right // 16) + 2, int(p.rect.bottom // 16))
    before = w.score
    snail.take_hit(1, 1, 100)
    check(snail.dying and w.score == before + S.ENDLESS_KILL_POINTS, "one sword hit kills and scores +25")
    check(any(pop[0] == f"+{S.ENDLESS_KILL_POINTS}" for pop in w.popups), "+25 popup shown")
    score_before = w.score
    p.invuln = 0
    p.take_damage(1, p.rect.centerx - 5)
    check(p.is_dead, "one hit ends the run")
    d.step(120)
    check(isinstance(d.top, EndlessOverScene), "game-over screen appears")
    rec = d.app.save.endless
    check(rec["best_score"] == score_before and rec["runs"] == 1, f"best score saved ({rec})")
    d.step(60)
    d.step(1, tap=("confirm",))      # RUN AGAIN
    d.step(30)
    check(isinstance(d.top, EndlessScene) and not d.top.level.started, "run again restarts endless mode")

    # running into a raised step ends the run (instead of stopping the hero)
    w = d.top.level
    p = w.player
    d.step(1, tap=("confirm",))
    tm = w.tilemap
    gx = int(p.rect.right // 16) + 5
    g = int(p.rect.bottom // 16)
    for x in range(gx, gx + 6):
        tm.set_column(x, ["."] * (g - 3) + ["#"] * (len(tm.cols[x]) - (g - 3)))
    for _ in range(90):
        d.step(1)
        if p.is_dead:
            break
    check(p.is_dead, "crashing into a 3-tile step ends the run")
    # a step the hero is *almost* on top of is forgiven (he is helped up)
    d.app.scenes.switch(EndlessScene(d.app), fade=False)
    d.held = set()
    w = d.top.level
    p = w.player
    d.step(1, tap=("confirm",))
    d.step(30)
    gx = int(p.rect.right // 16) + 1
    g = int(p.rect.bottom // 16)
    for x in range(gx, gx + 8):
        w.tilemap.set_column(x, ["."] * (g - 1) + ["#"] * (len(w.tilemap.cols[x]) - (g - 1)))
    p.rect.bottom = (g - 1) * 16 + 5          # feet 5 px below the step's top
    p.vy = 0
    d.step(20)
    check(not p.is_dead and p.rect.bottom <= (g - 1) * 16 + 0.5, "near-miss on a step is forgiven")
    # the speed ramp is gentle: still well below the cap after 30 s
    w.speed = S.ENDLESS_START_SPEED
    w.player.invuln = 999
    t_speed = S.ENDLESS_START_SPEED + S.ENDLESS_ACCEL * 30
    check(t_speed < 200, f"speed after 30 s would be {t_speed:.0f} px/s (gentle ramp)")


def test_platforms(d):
    print("platforms / hazards")
    lv = levels(d.app)
    # level 2 has falling planks over water
    d.app.scenes.switch(GameplayScene(d.app, 1), fade=False)
    lvl = d.top.level
    p = lvl.player
    import re
    falling = [q for q in lvl.platforms if type(q).__name__ == "FallingPlatform"]
    expected = sum(len(re.findall("F+", row)) for row in lvl.data.rows)
    check(len(falling) == expected and expected > 0, f"level 2 spawns all {expected} falling planks")
    fp = falling[0]
    p.rect.midbottom = (fp.rect.centerx, fp.rect.top - 2)
    p.vy = 0
    d.step(5)
    check(p.ground_platform is fp, "player stands on falling plank")
    d.step(60)
    check(fp.state in ("fall", "gone"), "falling plank falls after being stood on")
    # water hazard returns player to safe ground with one heart lost
    d.step(120)
    hp = p.health
    p.invuln = 0
    water = lvl.tilemap.water_cells[0]
    p.rect.midbottom = (water[0] * 16 + 8, water[1] * 16 + 14)
    d.step(2)
    check(p.health == hp - 1 and lvl.tilemap.hazard_at(p.rect) is None, "water costs a heart and respawns")

    # level 3 has moving logs, a key and a locked door
    d.app.scenes.switch(GameplayScene(d.app, 2), fade=False)
    lvl = d.top.level
    p = lvl.player
    movers = [q for q in lvl.platforms if type(q).__name__ == "MovingPlatform"]
    expected = sum(row.count("M") for row in lvl.data.rows)
    check(len(movers) == expected and expected > 0, f"level 3 spawns all {expected} moving logs")
    m = next(q for q in movers if q.end.y == q.start.y)      # a horizontal one
    d.step(5)
    p.rect.midbottom = (m.rect.centerx, m.rect.top - 1)
    p.vy = 0
    d.step(3)
    x_before = p.rect.centerx
    offset_before = p.rect.centerx - m.rect.centerx
    d.step(60)
    check(p.ground_platform is m, "player rides moving log")
    check(abs((p.rect.centerx - m.rect.centerx) - offset_before) < 2, "player is carried with the log")
    door = next(o for o in lvl.objects if type(o).__name__ == "ExitDoor")
    check(door.locked, "level 3 door is locked")
    p.rect.midbottom = door.rect.midbottom
    p.vy = 0
    d.step(3)
    d.step(1, tap=("up",))
    d.step(3)
    check(not lvl.completed, "locked door refuses without key")
    lvl.has_key = True
    d.step(1, tap=("up",))
    d.step(3)
    check(lvl.completed, "door opens with key")


def test_enemies(d):
    print("enemies")
    d.app.scenes.switch(GameplayScene(d.app, 0), fade=False)
    lvl = d.top.level
    p = lvl.player
    snail = next(e for e in lvl.enemies if type(e).__name__ == "Snail")
    p.rect.midbottom = (snail.rect.centerx - 100, snail.rect.bottom)   # enemies only think near the player
    d.step(5)
    snail.take_hit(1, 1, 100)
    check(snail.state == "hide" and snail.hp == 1, "snail hides after first hit")
    d.step(20)
    snail.take_hit(1, 1, 100)
    check(snail.hp == 1, "shell blocks hits")
    d.step(int(2.5 * S.FPS))
    check(snail.state == "walk", "snail comes back out")
    snail.take_hit(1, 1, 100)
    check(snail.dying, "snail dies on second real hit")
    boar = next(e for e in lvl.enemies if type(e).__name__ == "Boar")
    boar.set_state("patrol")
    p.rect.midbottom = (boar.rect.centerx + 90 * boar.facing, boar.rect.bottom)
    p.vy = 0
    p.invuln = 5
    states = set()
    for _ in range(40):
        d.step(1)
        states.add(boar.state)
    check("alert" in states or "charge" in states, "boar notices the player in front of it")
    # bees: level 3 - use the bee nearest the start, which hovers over open ground
    d.app.scenes.switch(GameplayScene(d.app, 2), fade=False)
    lvl = d.top.level
    p = lvl.player
    bee = min((e for e in lvl.enemies if type(e).__name__ == "Bee"), key=lambda e: e.rect.x)
    p.rect.midbottom = (bee.rect.centerx + 24, 15 * 16)
    p.vy = 0
    p.invuln = 5
    states = set()
    for _ in range(240):
        d.step(1)
        states.add(bee.state)
    check("dive" in states, "bee dives at a nearby player")


def main():
    d = Driver()
    tests = [test_menus, test_mouse_menus, test_mechanics, test_moves, test_no_stacking, test_enemies,
             test_enemy_hazards, test_platforms, test_endless, test_levels]
    for t in tests:
        try:
            t(d)
        except Exception:
            traceback.print_exc()
            failures.append(f"{t.__name__} raised")
    try:
        S.SAVE_FILE.unlink()
    except OSError:
        pass
    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
