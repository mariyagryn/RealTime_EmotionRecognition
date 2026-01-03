# ui/common.py
from __future__ import annotations
import os

# UI palette
DARK = {
    "bg": "#020617",
    "panel": "#0b1220",
    "card": "#040c24",
    "card_soft": "#06122f",
    "border": "#1e40af",
    "text": "#E8F1FF",
    "muted": "#94a3b8",
    "accent": "#2563eb",
    "accent2": "#38bdf8",
    "chip": "#0b1b33",
    "chip_text": "#e5f0ff",
    "btn_text": "#020617",
    "menu_fg": "#020617",
    "menu_btn": "#111827",
    "menu_hover": "#1f2937",
    "menu_text": "#E8F1FF",
    "dropdown_fg": "#020617",
    "dropdown_text": "#E8F1FF",
}

LIGHT = {
    "bg": "#EEF6FF",
    "panel": "#F6FAFF",
    "card": "#F3F8FF",
    "card_soft": "#EAF2FF",
    "border": "#9BC3FF",
    "text": "#0B1B33",
    "muted": "#3B4A5C",
    "accent": "#2563eb",
    "accent2": "#0ea5e9",
    "chip": "#E7F1FF",
    "chip_text": "#0B1B33",
    "btn_text": "#0B1B33",
    "menu_fg": "#EAF2FF",
    "menu_btn": "#D8E9FF",
    "menu_hover": "#C7DFFF",
    "menu_text": "#0B1B33",
    "dropdown_fg": "#FFFFFF",
    "dropdown_text": "#0B1B33",
}

def palette_for(theme: str) -> dict:
    t = (theme or "Dark").lower()
    return LIGHT if t.startswith("light") else DARK

LABELS = ["happy", "neutral", "sad", "angry", "fear", "surprise", "disgust"]
EMO_COLORS = {
    "happy": "#22c55e",
    "neutral": "#94a3b8",
    "sad": "#60a5fa",
    "angry": "#ef4444",
    "fear": "#a78bfa",
    "surprise": "#f59e0b",
    "disgust": "#10b981",
}

def ui_asset(name: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)

def ensure_dirs() -> None:
    os.makedirs("sessions/snaps", exist_ok=True)
    os.makedirs("sessions/records", exist_ok=True)
    os.makedirs("sessions/reports", exist_ok=True)

def parse_res(s: str) -> tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        return 640, 360

def fmt_mmss(secs: float) -> str:
    s = int(max(0, secs))
    m = s // 60
    ss = s % 60
    return f"{m:02d}:{ss:02d}"

def fmt_hhmm(secs: float) -> str:
    s = int(max(0, secs))
    minutes = s // 60
    hours = minutes // 60
    minutes %= 60
    return f"{hours}h {minutes:02d}m"

# ---------- settings ----------
def load_settings_safe() -> dict:
    try:
        from utils.app_settings import load as load_cfg
        return dict(load_cfg() or {})
    except Exception:
        try:
            import json
            if os.path.exists("settings.json"):
                with open("settings.json", "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

def save_settings_safe(cfg: dict) -> None:
    try:
        from utils.app_settings import save as save_cfg
        save_cfg(cfg)
    except Exception:
        try:
            import json
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def pick_palette(theme: str) -> dict:
    t = (theme or "Dark").lower()
    return LIGHT if t.startswith("light") else DARK
