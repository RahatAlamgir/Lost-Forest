"""Build a single, small, shareable LostForest.exe with PyInstaller.

    python tools/build_exe.py

Output: dist/LostForest.exe   (temporary files go to build/)

Size savings:
  * only the PNG files the game actually loads are bundled (no .aseprite/.gif sources)
  * unused Python libraries are excluded (tkinter, ssl, email, numpy, ...)
  * unused pygame DLLs are dropped (fonts, JPEG/TIFF/WebP, OGG/Opus/MOD codecs, MIDI)
  * bytecode is compiled with -OO (no docstrings / asserts)
Requires:  pip install pyinstaller   (Pillow is optional, used only for the .ico icon)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
STAGE = BUILD / "stage"
DIST = ROOT / "dist"
sys.path.insert(0, str(ROOT))

# Python modules the game never uses
EXCLUDES = [
    "tkinter", "_tkinter", "unittest", "pydoc", "doctest", "email", "http", "xml", "xmlrpc",
    "sqlite3", "_sqlite3", "asyncio", "multiprocessing", "concurrent", "ssl", "_ssl",
    "hashlib", "_hashlib", "decimal", "_decimal", "bz2", "_bz2", "lzma", "_lzma",
    "unicodedata", "compression.zstd", "_zstd",
    "tarfile", "argparse", "pickle", "_pickle", "difflib", "statistics", "calendar",
    "datetime", "_pydatetime", "_datetime",
    "ftplib", "urllib", "socket", "_socket", "select", "selectors",
    "numpy", "PIL", "setuptools", "pkg_resources", "distutils",
    "pygame.examples", "pygame.tests", "pygame.docs", "pygame.freetype", "pygame._freetype",
    "pygame.ftfont", "pygame.font", "pygame.sysfont", "pygame.midi", "pygame.pypm",
    "pygame.camera", "pygame._camera", "pygame._camera_vidcapture", "pygame._camera_opencv",
    "pygame.surfarray", "pygame.sndarray", "pygame.gfxdraw", "pygame.scrap",
]

# pygame binaries the game never loads (verified: PNG art + WAV audio only)
DROP_BINARIES = [
    "sdl2_ttf", "freetype", "libjpeg", "libtiff", "libwebp", "libxmp", "libopus",
    "libogg", "libwavpack", "portmidi", "pypm", "_camera", "gfxdraw", "scrap",
    "font.cp", "_freetype", "libssl", "libcrypto", "_ssl", "_hashlib", "_socket",
    "_bz2", "_lzma", "_decimal", "_sqlite3", "sqlite3", "tcl", "tk",
    "unicodedata", "_zstd", "_sdl2\\",
]
DROP_DATAS = [".ttf", ".otf", "pygame/docs", "pygame/examples", "pygame/tests", "pygame\\docs",
              "pygame\\examples", "pygame\\tests"]


def used_assets():
    """Load every sprite the game uses (headless) and record which files were opened.

    Returns (files, crops): crops[rel] lists the rectangles cut from files that are
    *only* ever used through Assets.crop(); everything else in those files is unused."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))
    from lostforest.core import assets as assets_mod
    seen, direct, crops = set(), set(), {}
    original_image, original_crop = assets_mod.Assets.image, assets_mod.Assets.crop
    state = {"in_crop": False}

    def image(self, rel):
        seen.add(rel)
        if not state["in_crop"]:
            direct.add(rel)
        return original_image(self, rel)

    def crop(self, rel, rect):
        crops.setdefault(rel, []).append(tuple(rect))
        state["in_crop"] = True
        try:
            return original_crop(self, rel, rect)
        finally:
            state["in_crop"] = False

    assets_mod.Assets.image, assets_mod.Assets.crop = image, crop
    assets_mod.Assets()
    assets_mod.Assets.image, assets_mod.Assets.crop = original_image, original_crop
    seen.add("Character/Idle/Idle-Sheet.png")       # window icon
    direct.add("Character/Idle/Idle-Sheet.png")
    only_cropped = {rel: rects for rel, rects in crops.items() if rel not in direct}
    return sorted(seen), only_cropped


def copy_masked(src, dst, rects):
    """Copy an image keeping only the given rectangles (same size, so coordinates still
    match). Blank transparent space compresses to almost nothing."""
    import pygame
    img = pygame.image.load(str(src))
    out = pygame.Surface(img.get_size(), pygame.SRCALPHA)
    for r in rects:
        out.blit(img, r, r)
    pygame.image.save(out, str(dst))
    if dst.stat().st_size >= src.stat().st_size:    # not worth it - keep the original
        shutil.copy2(src, dst)


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    files, only_cropped = used_assets()
    import pygame
    pygame.init()
    for rel in files:
        dst = STAGE / "Assets" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel in only_cropped:
            copy_masked(ROOT / "Assets" / rel, dst, only_cropped[rel])
        else:
            shutil.copy2(ROOT / "Assets" / rel, dst)
    audio = ROOT / "Assets" / "Audio"                 # optional custom audio overrides
    if audio.exists():
        shutil.copytree(audio, STAGE / "Assets" / "Audio")
    (STAGE / "levels").mkdir(parents=True)
    for lvl in sorted((ROOT / "levels").glob("*.txt")):
        shutil.copy2(lvl, STAGE / "levels" / lvl.name)
    size = sum(p.stat().st_size for p in STAGE.rglob("*") if p.is_file())
    print(f"staged {len(files)} images + levels ({size / 1024:.0f} KB)")
    return make_icon()


def make_icon():
    """A 256px icon of the hero (needs Pillow to become an .ico; skipped otherwise)."""
    import pygame
    sheet = pygame.image.load(str(ROOT / "Assets/Character/Idle/Idle-Sheet.png"))
    frame = sheet.subsurface((16, 14, 32, 32))
    icon = pygame.transform.scale(frame, (256, 256))
    png = BUILD / "icon.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(icon, str(png))
    try:
        from PIL import Image
        ico = BUILD / "icon.ico"
        Image.open(png).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return ico
    except ImportError:
        print("Pillow not installed - building without a custom .exe icon")
        return None


SPEC = r'''
# Generated by tools/build_exe.py - do not edit by hand
ROOT = {root!r}
STAGE = {stage!r}
DROP_BINARIES = {drop_bin!r}
DROP_DATAS = {drop_datas!r}

a = Analysis(
    [ROOT + r"\main.py"],
    pathex=[ROOT],
    datas=[(STAGE + r"\Assets", "Assets"), (STAGE + r"\levels", "levels")],
    excludes={excludes!r},
    optimize=2,
)
a.binaries = [b for b in a.binaries if not any(d in b[0].lower() for d in DROP_BINARIES)]
# PyInstaller collects SDL DLLs twice (top level + pygame\). pygame's modules load the copy
# next to them, so the top-level duplicates can go.
_in_pygame = {{b[0].split("\\")[-1].lower() for b in a.binaries if b[0].lower().startswith("pygame\\")}}
a.binaries = [b for b in a.binaries if "\\" in b[0] or b[0].lower() not in _in_pygame]
a.datas = [d for d in a.datas if not any(x in d[0].lower() for x in DROP_DATAS)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="LostForest",
    console=False,
    debug=False,
    strip=False,
    upx=False,
    icon={icon!r},
)
'''


def build():
    icon = stage()
    spec = BUILD / "LostForest.spec"
    spec.write_text(SPEC.format(root=str(ROOT), stage=str(STAGE), drop_bin=DROP_BINARIES,
                                drop_datas=DROP_DATAS, excludes=EXCLUDES,
                                icon=str(icon) if icon else None), encoding="utf-8")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
           "--distpath", str(DIST), "--workpath", str(BUILD / "work"), str(spec)]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    exe = DIST / "LostForest.exe"
    print(f"\nbuilt {exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    build()
