# agent/state.py — завантаження/збереження користувацьких налаштувань
import json, os
from dataclasses import dataclass, asdict

SETTINGS_PATH = "settings.json"

DEFAULTS = {
    "background_enabled": False,

    "camera_index": 0,
    "camera_resolution": [640, 360],   # варіанти у UI: 320x180, 480x270, 640x360
    "detector": "opencv",              # opencv / mediapipe / retinaface

    "analyze_every": 1.2,              # сек, у Live
    "ema_alpha": 0.3,

    "triggers": {                      # що агент може пропонувати
        "breathing": True,
        "pomodoro":  True,
        "mirror":    False,
        "speech":    False
    },

    "privacy": {
        "save_stats": True,
        "save_frames": False,
        "blur_faces":  False
    },

    "tts": {
        "enabled": True,
        "voice":   "default",
        "rate":    1.0
    },

    "ui": {
        "lang": "UA",
        "theme": "dark"
    }
}

_cache = None

def load_settings():
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}
    # shallow-merge з дефолтами
    def deep_merge(dst, src):
        for k, v in src.items():
            if isinstance(v, dict):
                dst[k] = deep_merge(dst.get(k, {}), v)
            else:
                dst.setdefault(k, v)
        return dst
    _cache = deep_merge(data, DEFAULTS.copy())
    return _cache

def save_settings(data):
    global _cache
    _cache = data
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# простий “пауза агенту”, якщо треба для прев’ю/налаштувань
_paused = False
def set_paused(v: bool):  # ui може викликати це, коли показує Preview
    global _paused
    _paused = bool(v)
def is_paused():
    return _paused
