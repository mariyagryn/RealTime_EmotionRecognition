# core/storage.py
from __future__ import annotations
import os
import csv
from datetime import datetime, timedelta
from ui.common import LABELS

def write_csv_summary(start_iso: str, totals: dict[str, float], dominant: str, path: str = "sessions/summary.csv") -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    headers = ["started_at", "ended_at", "duration_sec"] + [f"sec_{k}" for k in LABELS] + ["dominant"]

    end_iso = datetime.utcnow().isoformat()
    duration = sum(float(totals.get(k, 0.0) or 0.0) for k in LABELS)

    row = [start_iso, end_iso, f"{duration:.2f}"] + [f"{float(totals.get(k, 0.0) or 0.0):.2f}" for k in LABELS] + [dominant]

    write_header = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(headers)
        w.writerow(row)

def load_stats_aggregate(period: str, path: str = "sessions/summary.csv"):
    totals = {k: 0.0 for k in LABELS}
    sessions_count = 0

    if not os.path.exists(path):
        return totals, 0, 0.0

    today = datetime.utcnow().date()
    if period == "Today":
        def match(dt): return dt.date() == today
    elif period == "Last 7 days":
        start = today - timedelta(days=6)
        def match(dt): return dt.date() >= start
    else:
        def match(dt): return True

    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    started_at = row.get("started_at") or ""
                    dt = datetime.fromisoformat(started_at)
                except Exception:
                    continue
                if not match(dt):
                    continue

                sessions_count += 1
                for emo in LABELS:
                    key = f"sec_{emo}"
                    try:
                        totals[emo] += float(row.get(key, "0") or 0.0)
                    except Exception:
                        pass
    except Exception:
        pass

    total_sec = sum(totals.values())
    return totals, sessions_count, total_sec


import os
import csv
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any

_STORAGE_LOCK = threading.Lock()

STORAGE_DIR = "storage"
MOMENTS_DIR = os.path.join(STORAGE_DIR, "moments")
MOMENTS_CSV = os.path.join(MOMENTS_DIR, "moments.csv")

MOMENTS_FIELDS = [
    "timestamp",
    "session_time_sec",
    "emotion",
    "conf",
    "streak_sec",
    "session_id",
    "video_path",
]


def ensure_moments_storage() -> None:
    os.makedirs(MOMENTS_DIR, exist_ok=True)
    if not os.path.exists(MOMENTS_CSV):
        with _STORAGE_LOCK:
            if not os.path.exists(MOMENTS_CSV):
                with open(MOMENTS_CSV, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=MOMENTS_FIELDS)
                    w.writeheader()

def append_moment(row: Dict[str, Any]) -> None:
    ensure_moments_storage()

    safe = {k: row.get(k, "") for k in MOMENTS_FIELDS}
    ts = safe.get("timestamp", "")
    if isinstance(ts, datetime):
        safe["timestamp"] = ts.isoformat(timespec="seconds")

    with _STORAGE_LOCK:
        with open(MOMENTS_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=MOMENTS_FIELDS)
            w.writerow(safe)

def _parse_dt(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def load_moments_list(period: str = "All time") -> List[Dict[str, Any]]:
    ensure_moments_storage()
    period = (period or "All time").strip()

    now = datetime.now()
    if period == "Today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "Last 7 days":
        start = now - timedelta(days=7)
    else:
        start = None

    items: List[Dict[str, Any]] = []
    with _STORAGE_LOCK:
        with open(MOMENTS_CSV, "r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                ts = row.get("timestamp", "") or ""
                dt = _parse_dt(ts)
                if start and dt:
                    if dt < start:
                        continue
                elif start and not dt:
                    continue
                items.append(dict(row))

    def key_fn(x: Dict[str, Any]) -> float:
        dt = _parse_dt(x.get("timestamp", "") or "")
        return dt.timestamp() if dt else 0.0

    items.sort(key=key_fn, reverse=True)
    return items


def load_moments_aggregate(period: str = "All time"):
    items = load_moments_list(period) or []

    by_emotion = {k: 0 for k in LABELS}
    for row in items:
        emo = (row.get("emotion") or "").strip().lower()
        if emo in by_emotion:
            by_emotion[emo] += 1

    return len(items), by_emotion
