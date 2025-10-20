from __future__ import annotations
import os, sqlite3, time
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict

DB_PATH = "stats.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS segments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  start_ts INTEGER NOT NULL,  -- unix seconds (UTC)
  end_ts   INTEGER NOT NULL,
  emotion  TEXT NOT NULL,
  source   TEXT DEFAULT 'app'  -- e.g., 'app' or 'import'
);
CREATE INDEX IF NOT EXISTS idx_segments_day ON segments(start_ts);

CREATE TABLE IF NOT EXISTS daily_totals(
  day TEXT NOT NULL,          -- YYYY-MM-DD (local)
  emotion TEXT NOT NULL,
  seconds REAL NOT NULL,
  PRIMARY KEY (day, emotion)
);
"""

def _connect():
    init = not os.path.exists(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    if init:
        con.executescript(SCHEMA)
        con.commit()
    return con

def _local_day(ts_utc: int) -> str:
    dt = datetime.fromtimestamp(ts_utc)
    return dt.strftime("%Y-%m-%d")

def add_segment(emotion: str, start_ts_utc: int, end_ts_utc: int):
    """Записати завершений сегмент та оновити денні підсумки."""
    if end_ts_utc <= start_ts_utc:
        return
    dur = end_ts_utc - start_ts_utc
    con = _connect()
    with con:
        con.execute(
            "INSERT INTO segments(start_ts,end_ts,emotion) VALUES (?,?,?)",
            (start_ts_utc, end_ts_utc, emotion)
        )
        day = _local_day(start_ts_utc)
        cur = con.execute(
            "SELECT seconds FROM daily_totals WHERE day=? AND emotion=?",
            (day, emotion)
        )
        row = cur.fetchone()
        if row is None:
            con.execute(
                "INSERT INTO daily_totals(day,emotion,seconds) VALUES (?,?,?)",
                (day, emotion, float(dur))
            )
        else:
            con.execute(
                "UPDATE daily_totals SET seconds=seconds+? WHERE day=? AND emotion=?",
                (float(dur), day, emotion)
            )

def get_daily_totals(day: str) -> Dict[str, float]:
    con = _connect()
    cur = con.execute(
        "SELECT emotion, seconds FROM daily_totals WHERE day=?",
        (day,)
    )
    return {emo: sec for emo, sec in cur.fetchall()}

def get_range_totals(day_from: str, day_to: str) -> Dict[str, float]:
    con = _connect()
    cur = con.execute(
        "SELECT emotion, SUM(seconds) FROM daily_totals WHERE day>=? AND day<=? GROUP BY emotion",
        (day_from, day_to)
    )
    return {emo: (sec or 0.0) for emo, sec in cur.fetchall()}
