# utils/app_settings.py
import json, os
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")

DEFAULTS = {
    "background_mode": False,

    "detector": "opencv",                 # opencv / mediapipe / retinaface
    "resolution": "320x180",              # 320x180 / 480x270 / 640x360
    "analyze_every": 1.2,                 # seconds
    "ema": 0.3,                           # 0.1..0.9

    "privacy_blur": False,
    "privacy_save_stats": True,
    "privacy_save_frames": False,

    "tts_enabled": True,
    "language": "UA",                     # UA / EN
    "theme": "Dark",                      # Dark / Light

    "rule_breathing": True,
    "rule_pomodoro":  True,
    "rule_mirror":    False,
    "rule_speech":    False,

    "rule_sad_sec": 60,
    "rule_angry_sec": 30,
    "rule_neutral_sec": 120,
    "rule_noface_pct": 40,
    "rule_cooldown_min": 30,

    # Devices (можемо заповнювати пізніше)
    "camera_index": 0,
    "mic_device": "",
    "mic_gain": 1.0
}

def load():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    # підлив дефолтів (щоб нові ключі не ламали старий settings.json)
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)
    return data

def save(cfg: dict):
    # гарантуємо всі ключі
    out = {**DEFAULTS, **cfg}
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out
