# modules/rules.py
from __future__ import annotations
import time
from dataclasses import dataclass

@dataclass
class RuleConfig:
    sad_sec: int = 60
    angry_sec: int = 30
    neutral_sec: int = 120
    noface_pct: int = 40           # %, обчислюємо у Live
    cooldown_min: int = 30         # хвилини
    enable_breathing: bool = True
    enable_pomodoro: bool = True
    enable_mirror: bool = True
    enable_speech: bool = True

class RuleState:
    def __init__(self):
        self._last_fire = 0.0
        self._noface_acc = 0.0
        self._seen_acc = 0.0

    def can_fire(self, cooldown_min: int) -> bool:
        return (time.time() - self._last_fire) >= (cooldown_min * 60)

    def mark_fired(self): self._last_fire = time.time()

    def feed_face_presence(self, has_face: bool, dt: float):
        self._seen_acc += dt
        if not has_face: self._noface_acc += dt

    def noface_pct(self) -> float:
        tot = max(1e-6, self._seen_acc)
        return 100.0 * (self._noface_acc / tot)

def pick_suggestion(label: str, cfg: RuleConfig) -> str | None:
    # Мапа: яку підказку давати під емоцію
    if label == "sad"     and cfg.enable_breathing: return "breathing"
    if label == "angry"   and cfg.enable_breathing: return "breathing"
    if label == "neutral" and cfg.enable_pomodoro:  return "pomodoro"
    # додаткові легкі тренування
    if cfg.enable_mirror and label in ("fear", "disgust", "surprise"): return "mirror"
    return None
