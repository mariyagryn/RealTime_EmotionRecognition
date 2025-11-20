# modules/stats.py
from __future__ import annotations
import os, json
from datetime import datetime, date
from collections import defaultdict

BASE = "sessions"

def _day_dir(d: date | None = None) -> str:
    d = d or date.today()
    path = os.path.join(BASE, d.strftime("%Y-%m-%d"))
    os.makedirs(path, exist_ok=True)
    return path

def log_event(label: str, seconds: float, ts: float | None = None):
    """Пише одну подію у JSONL: {"ts": "...", "label": "...", "seconds": ...}"""
    if seconds <= 0:
        return
    ts = ts or datetime.utcnow().timestamp()
    rec = {
        "ts": ts,
        "label": label,
        "seconds": float(seconds),
    }
    day = _day_dir()
    with open(os.path.join(day, "events.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def write_session_summary(totals: dict[str, float], meta: dict | None = None):
    """Оновлює/дописує summary.json (підсумки за сесію дня)."""
    day = _day_dir()
    path = os.path.join(day, "summary.json")
    data = {"sessions": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"sessions": []}
    entry = {
        "started_at": meta.get("started_at") if meta else None,
        "ended_at": meta.get("ended_at") if meta else None,
        "totals": totals,
    }
    data["sessions"].append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _iter_events_between(start_ymd: str, end_ymd: str):
    """Ітерує всі events.jsonl за діапазон дат [start..end]. Формат дат: 'YYYY-MM-DD'."""
    from datetime import datetime, timedelta
    def _to_date(s: str): return datetime.strptime(s, "%Y-%m-%d").date()
    d = _to_date(start_ymd); end = _to_date(end_ymd)
    while d <= end:
        path = os.path.join(BASE, d.strftime("%Y-%m-%d"), "events.jsonl")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        yield json.loads(line)
                    except Exception:
                        pass
        d += timedelta(days=1)

def get_range_totals(start_ymd: str, end_ymd: str) -> dict[str, float]:
    """Агрегація секунд за емоціями за період (для дашборда)."""
    totals = defaultdict(float)
    for rec in _iter_events_between(start_ymd, end_ymd):
        label = rec.get("label")
        sec = float(rec.get("seconds", 0.0) or 0.0)
        if label:
            totals[label] += max(0.0, sec)
    return dict(totals)
