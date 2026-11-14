"""Global constants and tuning values for Lost Forest.

Everything that a designer might want to tweak (screen size, physics feel,
enemy stats) lives here so it can be adjusted without digging through code.
"""
import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
# When packaged as an .exe (PyInstaller), game files are unpacked to a temporary
# folder, so saves and the music cache go to %APPDATA%\LostForest instead.
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    SAVE_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "LostForest"
else:
    ROOT = Path(__file__).resolve().parent.parent
    SAVE_DIR = ROOT / "saves"
ASSETS = ROOT / "Assets"
AUDIO_DIR = ASSETS / "Audio"          # optional: drop .wav/.ogg files here to override synth sounds
LEVELS_DIR = ROOT / "levels"
SAVE_FILE = SAVE_DIR / "savegame.json"

# --------------------------------------------------------------------------
# Display
# --------------------------------------------------------------------------
TITLE = "Lost Forest"
VIEW_W, VIEW_H = 480, 270        # internal (pixel-art) resolution
FPS = 60                         # default simulation rate (the game runs at the monitor's refresh rate)
DT = 1.0 / FPS
TILE = 16

# --------------------------------------------------------------------------
# Player physics (pixels, seconds)
# --------------------------------------------------------------------------
GRAVITY = 1150.0
MAX_FALL_SPEED = 430.0
RUN_SPEED = 130.0
GROUND_ACCEL = 1300.0
GROUND_DECEL = 1600.0
AIR_ACCEL = 900.0
AIR_DECEL = 500.0
JUMP_VELOCITY = -370.0
DOUBLE_JUMP_VELOCITY = -320.0
JUMP_CUT_MULTIPLIER = 0.45       # velocity kept when jump is released early
COYOTE_TIME = 0.10
JUMP_BUFFER_TIME = 0.12
STOMP_BOUNCE = -290.0

DASH_SPEED = 340.0               # horizontal speed during a dash
DASH_TIME = 0.16                 # how long a dash lasts
DASH_COOLDOWN = 0.35             # time before you can dash again (one air dash per jump)
FAST_FALL_GRAVITY = 2.6          # gravity multiplier while holding DOWN in the air
FAST_FALL_SPEED = 680.0          # terminal speed while fast-dropping

PLAYER_HITBOX = (12, 34)
PLAYER_MAX_HEALTH = 5
PLAYER_INVULN_TIME = 1.1
PLAYER_KNOCKBACK = (170.0, -220.0)
ATTACK_MOVE_FACTOR = 0.35        # ground speed multiplier while swinging

# --------------------------------------------------------------------------
# Enemies
# --------------------------------------------------------------------------
SNAIL_SPEED = 18.0
SNAIL_HP = 2
SNAIL_HIDE_TIME = 1.6

BOAR_WALK_SPEED = 32.0
BOAR_CHARGE_SPEED = 165.0
BOAR_HP = 3
BOAR_SIGHT_RANGE = 150.0

BEE_HP = 1
BEE_SIGHT_RANGE = 125.0
BEE_DIVE_SPEED = 175.0

# --------------------------------------------------------------------------
# Endless Run
# --------------------------------------------------------------------------
ENDLESS_START_SPEED = 150.0      # px/s at the start of a run
ENDLESS_MAX_SPEED = 290.0        # reached after about 2.5 minutes
ENDLESS_ACCEL = 0.9              # speed gained per second (slow, steady ramp)
ENDLESS_THEME_EVERY = 500        # metres between forest colour changes
ENDLESS_COIN_POINTS = 10
ENDLESS_KILL_POINTS = 25

# --------------------------------------------------------------------------
# Colours
# --------------------------------------------------------------------------
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
TEXT = (246, 238, 214)
TEXT_DIM = (150, 140, 120)
TEXT_GOLD = (240, 196, 72)
TEXT_RED = (214, 76, 64)
TEXT_GREEN = (126, 200, 90)
SHADOW = (24, 20, 18)
OVERLAY = (10, 12, 16)

# --------------------------------------------------------------------------
# Default user settings (overridden by save file)
# --------------------------------------------------------------------------
DEFAULT_OPTIONS = {
    "music_volume": 0.6,
    "sfx_volume": 0.8,
    "fullscreen": False,
    "screen_shake": True,
    "show_fps": False,
}
