# utils/app_settings.py
from __future__ import annotations
import json, os
from typing import Any, Dict

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "settings.json")
_SETTINGS_PATH = os.path.abspath(_SETTINGS_PATH)

_DEFAULTS: Dict[str, Any] = {
    "background_mode": False,
    "backend": "deepface",
    "detector": "opencv",
    "resolution": "640x360",
    "camera_index": 0,
    "analyze_every": 1.0,
    "ema": 0.30,
    "min_conf": 48.0,
    "hold_sec": 1.2,
    "privacy_blur": False,
    "privacy_save_stats": True,
    "privacy_save_frames": False,
    "tts_enabled": False,
    "language": "UA",
    "theme": "Dark",
    "rule_breathing": False,
    "rule_pomodoro": False,
    "rule_mirror": False,
    "rule_speech": False,
    "rule_sad_sec": 60,
    "rule_angry_sec": 30,
    "rule_neutral_sec": 120,
    "rule_noface_pct": 40,
    "rule_cooldown_min": 30,
    # audio
    "mic_device": "",
    "mic_gain": 1.0,
}

def _merge_defaults(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(_DEFAULTS)
    out.update({k: v for k, v in (cfg or {}).items() if k in _DEFAULTS})
    return out

def load() -> Dict[str, Any]:
    cfg = {}
    if os.path.exists(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    cfg = _merge_defaults(cfg)
    return cfg

def save(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _merge_defaults(cfg)
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[settings] save error:", e)
    return cfg

def path() -> str:
    return _SETTINGS_PATH
