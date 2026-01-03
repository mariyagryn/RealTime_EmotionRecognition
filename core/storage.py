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
