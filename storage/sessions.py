# збереження подій у sessions/<timestamp>/
import os, json, time, datetime
from typing import Dict, Optional

SESS_ROOT = "sessions"

def _tsdir(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d_%H-%M-%S")

class SessionWriter:
    def __init__(self, kind: str = "agent"):
        os.makedirs(SESS_ROOT, exist_ok=True)
        self.start_ts = time.time()
        self.dir = os.path.join(SESS_ROOT, _tsdir(self.start_ts))
        os.makedirs(self.dir, exist_ok=True)
        self.events_path = os.path.join(self.dir, "events.jsonl")
        self.summary_path = os.path.join(self.dir, "summary.json")
        self.counters: Dict[str, float] = {}
        self.last_label: Optional[str] = None
        self.last_change_ts: Optional[float] = None

    def append_event(self, emo: Dict, fps: Optional[float] = None):
        payload = {"ts": time.time(), "dominant": emo["dominant"], "conf": emo["conf"], "probs": emo["probs"], "fps": fps}
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        now = payload["ts"]
        if self.last_label is None:
            self.last_label, self.last_change_ts = emo["dominant"], now
        elif emo["dominant"] != self.last_label:
            dur = now - (self.last_change_ts or now)
            self.counters[self.last_label] = self.counters.get(self.last_label, 0.0) + dur
            self.last_label, self.last_change_ts = emo["dominant"], now

    def close(self):
        now = time.time()
        if self.last_label and self.last_change_ts:
            self.counters[self.last_label] = self.counters.get(self.last_label, 0.0) + (now - self.last_change_ts)
        summary = {
            "type": "agent",
            "start_ts": self.start_ts,
            "end_ts": now,
            "duration_sec": now - self.start_ts,
            "totals_sec": self.counters
        }
        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        return self.summary_path
