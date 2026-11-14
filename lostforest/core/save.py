"""Persistent progress and options, stored as JSON in saves/savegame.json."""
import json

from ..settings import SAVE_DIR, SAVE_FILE, DEFAULT_OPTIONS

SAVE_VERSION = 1


class SaveData:
    def __init__(self):
        self.options = dict(DEFAULT_OPTIONS)
        self.levels = {}          # level_id -> {"completed", "best_time", "best_coins", "gem"}
        self.unlocked = 1         # number of unlocked levels
        self.last_level = 0
        self.endless = {"best_score": 0, "best_distance": 0, "runs": 0}
        self.load()

    # ------------------------------------------------------------------ io
    def load(self):
        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        self.options.update({k: v for k, v in data.get("options", {}).items() if k in DEFAULT_OPTIONS})
        self.levels = data.get("levels", {}) or {}
        self.unlocked = max(1, int(data.get("unlocked", 1)))
        self.last_level = int(data.get("last_level", 0))
        endless = data.get("endless", {})
        if isinstance(endless, dict):
            for key in self.endless:
                try:
                    self.endless[key] = max(0, int(endless.get(key, 0)))
                except (TypeError, ValueError):
                    pass

    def save(self):
        data = {
            "version": SAVE_VERSION,
            "options": self.options,
            "levels": self.levels,
            "unlocked": self.unlocked,
            "last_level": self.last_level,
            "endless": self.endless,
        }
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = SAVE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(SAVE_FILE)
        except OSError as exc:
            print(f"[save] could not write save file: {exc}")

    # ------------------------------------------------------------------ progress
    @property
    def has_progress(self):
        return bool(self.levels) or self.unlocked > 1

    def level(self, level_id):
        return self.levels.get(level_id, {})

    def record_result(self, index, level_id, time, coins, gem):
        rec = self.levels.setdefault(level_id, {})
        new_best = "best_time" not in rec or time < rec["best_time"]
        rec["completed"] = True
        rec["best_time"] = min(time, rec.get("best_time", time))
        rec["best_coins"] = max(coins, rec.get("best_coins", 0))
        rec["gem"] = rec.get("gem", False) or gem
        self.unlocked = max(self.unlocked, index + 2)
        self.last_level = index
        self.save()
        return new_best

    def record_endless(self, score, distance):
        """Store an Endless Run result. Returns True if it is a new best score."""
        rec = self.endless
        new_best = score > rec["best_score"]
        rec["best_score"] = max(rec["best_score"], int(score))
        rec["best_distance"] = max(rec["best_distance"], int(distance))
        rec["runs"] += 1
        self.save()
        return new_best

    def reset_progress(self):
        self.levels = {}
        self.unlocked = 1
        self.last_level = 0
        self.endless = {"best_score": 0, "best_distance": 0, "runs": 0}
        self.save()
