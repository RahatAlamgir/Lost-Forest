"""Sound effects and music.

The art pack ships without audio, so every sound is synthesised at start-up
(classic square / triangle / noise chip sounds). To use real audio instead,
drop files into  Assets/Audio/sfx/<name>.wav|ogg  or  Assets/Audio/music/<name>.ogg|wav|mp3
and they will be used automatically.
"""
import math
import random
import wave
from array import array

import pygame

from ..settings import AUDIO_DIR, SAVE_DIR

SR = 22050
MUSIC_CACHE = SAVE_DIR / "cache"


# --------------------------------------------------------------------------- synthesis
def _osc(wave_type, phase):
    p = phase % 1.0
    if wave_type == "square":
        return 1.0 if p < 0.5 else -1.0
    if wave_type == "pulse":
        return 1.0 if p < 0.25 else -1.0
    if wave_type == "triangle":
        return 4.0 * abs(p - 0.5) - 1.0
    if wave_type == "saw":
        return 2.0 * p - 1.0
    if wave_type == "sine":
        return math.sin(phase * math.tau)
    return random.uniform(-1.0, 1.0)  # noise


def tone(dur, f0, f1=None, wave_type="square", vol=0.3, attack=0.005, curve=1.5, vibrato=0.0):
    """Mono float samples of a single (optionally sweeping) note."""
    f1 = f0 if f1 is None else f1
    n = max(1, int(SR * dur))
    out = [0.0] * n
    phase = 0.0
    lp = 0.0
    for i in range(n):
        k = i / n
        f = f0 + (f1 - f0) * k
        if vibrato:
            f *= 1.0 + vibrato * math.sin(i / SR * math.tau * 6)
        phase += f / SR
        v = _osc(wave_type, phase)
        if wave_type == "noise":           # f0 controls a crude low-pass for noise
            a = min(1.0, f / 4000.0)
            lp += (v - lp) * a
            v = lp * 1.6
        env = min(1.0, (i / SR) / attack) if attack > 0 else 1.0
        env *= (1.0 - k) ** curve
        out[i] = v * env * vol
    return out


def concat(*parts):
    out = []
    for p in parts:
        out.extend(p)
    return out


def mix(*parts):
    n = max(len(p) for p in parts)
    out = [0.0] * n
    for p in parts:
        for i, v in enumerate(p):
            out[i] += v
    return out


def arpeggio(freqs, step, wave_type="square", vol=0.25, tail=1.0):
    parts = []
    for i, f in enumerate(freqs):
        last = i == len(freqs) - 1
        parts.append(tone(step * (1 + (tail if last else 0)), f, wave_type=wave_type, vol=vol, curve=1.2))
    return concat(*parts)


def to_sound(samples):
    buf = array("h")
    for v in samples:
        s = int(max(-1.0, min(1.0, v)) * 32000)
        buf.append(s)
        buf.append(s)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def build_sfx():
    """name -> samples. Kept short; generated in well under a second."""
    return {
        "jump": tone(0.13, 260, 540, "square", 0.16, curve=1.0),
        "double_jump": mix(tone(0.14, 400, 820, "square", 0.13), tone(0.14, 800, 1600, "triangle", 0.12)),
        "land": tone(0.07, 900, 300, "noise", 0.35),
        "step": tone(0.03, 1200, 600, "noise", 0.12),
        "swing": tone(0.12, 2600, 900, "noise", 0.32, attack=0.02, curve=1.0),
        "swing2": tone(0.14, 3200, 700, "noise", 0.34, attack=0.02, curve=1.0),
        "dash": mix(tone(0.16, 1800, 4200, "noise", 0.3, attack=0.01, curve=1.2),
                    tone(0.12, 220, 440, "triangle", 0.18)),
        "hit": mix(tone(0.10, 240, 90, "square", 0.22), tone(0.08, 3000, 800, "noise", 0.3)),
        "stomp": tone(0.10, 300, 700, "square", 0.18),
        "clink": mix(tone(0.07, 1450, wave_type="triangle", vol=0.3), tone(0.09, 2180, wave_type="triangle", vol=0.18)),
        "enemy_die": concat(tone(0.06, 600, 500, "square", 0.18), tone(0.22, 500, 110, "square", 0.18)),
        "coin": concat(tone(0.05, 988, wave_type="square", vol=0.14, curve=0.3), tone(0.16, 1319, wave_type="square", vol=0.14)),
        "gem": arpeggio([660, 880, 1100, 1320, 1760], 0.055, "triangle", 0.3),
        "key": arpeggio([784, 1047, 1568], 0.07, "square", 0.13),
        "heal": tone(0.3, 440, 990, "triangle", 0.35, curve=0.8, vibrato=0.02),
        "hurt": mix(tone(0.24, 320, 110, "saw", 0.22), tone(0.12, 1500, 300, "noise", 0.2)),
        "death": tone(0.9, 420, 55, "square", 0.18, curve=0.8, vibrato=0.04),
        "checkpoint": arpeggio([523, 659, 784, 1047], 0.07, "triangle", 0.32, tail=2),
        "chest": concat(tone(0.06, 500, 200, "noise", 0.3), arpeggio([523, 784, 1047, 1319], 0.05, "square", 0.12)),
        "door": arpeggio([392, 523, 659, 784, 1047], 0.09, "square", 0.13, tail=3),
        "locked": tone(0.18, 150, 140, "square", 0.16, curve=0.5),
        "crumble": tone(0.35, 700, 150, "noise", 0.3, curve=0.7),
        "menu_move": tone(0.035, 660, wave_type="square", vol=0.1, curve=0.5),
        "menu_select": tone(0.09, 880, 1320, "square", 0.12),
        "menu_back": tone(0.08, 660, 440, "square", 0.1),
        "pause": arpeggio([784, 523], 0.05, "square", 0.1),
    }


# --------------------------------------------------------------------------- music
NOTE = {}
for _i, _name in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]):
    for _oct in range(1, 7):
        NOTE[f"{_name}{_oct}"] = 440.0 * 2 ** ((_i - 9) / 12 + (_oct - 4))

PROGRESSION = [
    ("A2", ["A4", "C5", "E5"]), ("F2", ["F4", "A4", "C5"]), ("C3", ["C4", "E4", "G4"]), ("G2", ["G4", "B4", "D5"]),
    ("A2", ["A4", "C5", "E5"]), ("F2", ["F4", "A4", "C5"]), ("G2", ["G4", "B4", "D5"]), ("E2", ["E4", "G#4", "B4"]),
]
MELODY = [
    [("E5", 2), ("D5", 1), ("C5", 1), ("A4", 3), (None, 1)],
    [("C5", 2), ("D5", 1), ("E5", 1), ("F5", 2), ("E5", 2)],
    [("G5", 3), ("E5", 1), ("C5", 2), ("D5", 2)],
    [("D5", 2), ("B4", 2), ("G4", 3), (None, 1)],
    [("E5", 2), ("A5", 2), ("G5", 1), ("E5", 1), ("D5", 2)],
    [("C5", 2), ("A4", 1), ("C5", 1), ("F5", 3), (None, 1)],
    [("D5", 2), ("G5", 2), ("F5", 1), ("E5", 1), ("D5", 2)],
    [("B4", 3), ("G#4", 1), ("E5", 4)],
]


def build_music(with_melody=True, bpm=100):
    eighth = 60.0 / bpm / 2
    bar_len = int(SR * eighth * 8)
    total = bar_len * len(PROGRESSION) * 2   # play the progression twice
    out = [0.0] * total

    def add(start, samples):
        end = min(total, start + len(samples))
        for i in range(start, end):
            out[i] += samples[i - start]

    for rep in range(2):
        for b, (bass, chord) in enumerate(PROGRESSION):
            bar_start = (rep * len(PROGRESSION) + b) * bar_len
            # bass: root on 1 & 5, fifth-ish pulse on others
            for e in range(8):
                f = NOTE[bass] * (1.5 if e in (3, 7) else 1.0)
                add(bar_start + int(e * eighth * SR), tone(eighth * 0.95, f, wave_type="triangle", vol=0.22, curve=0.6))
            # plucked arpeggio
            pattern = [0, 1, 2, 1, 0, 1, 2, 1]
            for e, idx in enumerate(pattern):
                f = NOTE[chord[idx]]
                add(bar_start + int(e * eighth * SR), tone(eighth * 0.9, f, wave_type="pulse", vol=0.035, curve=2.5))
            # melody on the second pass (and softly on the first)
            if with_melody:
                pos = 0
                vol = 0.07 if rep == 1 else 0.045
                for note, length in MELODY[b]:
                    if note:
                        add(bar_start + int(pos * eighth * SR),
                            tone(eighth * length * 0.95, NOTE[note], wave_type="triangle", vol=vol,
                                 attack=0.02, curve=0.9, vibrato=0.004))
                    pos += length
            # soft hi-hat on off-beats
            for e in (1, 3, 5, 7):
                add(bar_start + int(e * eighth * SR), tone(0.03, 7000, wave_type="noise", vol=0.03))
    return out


def _write_wav(path, samples):
    buf = array("h", (int(max(-1.0, min(1.0, v)) * 32000) for v in samples))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(buf.tobytes())


# --------------------------------------------------------------------------- manager
class Audio:
    def __init__(self, options):
        self.options = options
        self.enabled = pygame.mixer.get_init() is not None
        self.sounds = {}
        self.music_name = None
        self._waiting_for = None
        self._generator = None
        if not self.enabled:
            return
        pygame.mixer.set_num_channels(24)
        for name, samples in build_sfx().items():
            self.sounds[name] = self._override_sfx(name) or to_sound(samples)
        self.apply_volume()

    def _override_sfx(self, name):
        for ext in ("wav", "ogg"):
            p = AUDIO_DIR / "sfx" / f"{name}.{ext}"
            if p.exists():
                try:
                    return pygame.mixer.Sound(str(p))
                except pygame.error:
                    pass
        return None

    def apply_volume(self):
        if not self.enabled:
            return
        sv = self.options["sfx_volume"]
        for s in self.sounds.values():
            s.set_volume(sv)
        pygame.mixer.music.set_volume(self.options["music_volume"] * 0.8)

    def play(self, name, volume=1.0):
        if not self.enabled:
            return
        s = self.sounds.get(name)
        if s is None:
            return
        ch = s.play()
        if ch is not None and volume != 1.0:
            ch.set_volume(volume)

    # ------------------------------------------------------------------ music
    MUSIC_TRACKS = {"menu": dict(with_melody=False, bpm=84), "forest": dict(with_melody=True, bpm=100)}

    def _music_file(self, name):
        """Path of a playable file for this track, or None if it is still being generated."""
        for ext in ("ogg", "mp3", "wav"):
            p = AUDIO_DIR / "music" / f"{name}.{ext}"
            if p.exists():
                return p
        cached = MUSIC_CACHE / f"{name}_v1.wav"
        return cached if cached.exists() else None

    def _generate(self, names):
        for name in names:
            cached = MUSIC_CACHE / f"{name}_v1.wav"
            if cached.exists():
                continue
            try:
                MUSIC_CACHE.mkdir(parents=True, exist_ok=True)
                tmp = cached.with_suffix(".tmp")
                _write_wav(tmp, build_music(**self.MUSIC_TRACKS.get(name, self.MUSIC_TRACKS["forest"])))
                tmp.replace(cached)
            except OSError as exc:
                print(f"[audio] could not cache music: {exc}")

    def prepare_music(self):
        """Synthesise any missing music tracks on a background thread (first launch only)."""
        if not self.enabled or self._generator is not None:
            return
        missing = [n for n in self.MUSIC_TRACKS if self._music_file(n) is None]
        if missing:
            import threading
            self._generator = threading.Thread(target=self._generate, args=(missing,), daemon=True)
            self._generator.start()

    def play_music(self, name):
        if not self.enabled or name == self.music_name:
            return
        self.music_name = name
        path = self._music_file(name)
        if path is None:
            self.prepare_music()
            self._waiting_for = name      # start it as soon as it has been generated
            pygame.mixer.music.fadeout(300)
            return
        self._waiting_for = None
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.options["music_volume"] * 0.8)
            pygame.mixer.music.play(-1, fade_ms=600)
        except pygame.error as exc:
            print(f"[audio] music failed: {exc}")

    def update(self):
        """Called every frame: starts music that finished generating in the background."""
        if self._waiting_for and self._music_file(self._waiting_for) is not None:
            name = self._waiting_for
            self.music_name = None
            self.play_music(name)

    def stop_music(self, fade_ms=400):
        if self.enabled:
            pygame.mixer.music.fadeout(fade_ms)
        self.music_name = None
        self._waiting_for = None
