# core/session_stats.py
from __future__ import annotations
from dataclasses import dataclass, field
from ui.common import LABELS

@dataclass
class LiveFlags:
    paused: bool = False
    recording: bool = False

@dataclass
class SessionStats:
    totals: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in LABELS})
    dominant: str = "–"
    last_label: str = "–"

    def add(self, label: str, secs: float) -> None:
        if label in self.totals:
            self.totals[label] += max(0.0, float(secs))

    def recompute_dominant(self) -> None:
        if not self.totals:
            self.dominant = "–"
            return
        self.dominant = max(self.totals.items(), key=lambda kv: kv[1])[0]
