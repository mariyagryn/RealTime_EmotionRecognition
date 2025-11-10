# utils/telemetry.py
import os, json, time, threading
from datetime import datetime

ROOT = "sessions"

def _dir_for_now():
    d = datetime.now().strftime("%Y%m%d")
    p = os.path.join(ROOT, d)
    os.makedirs(p, exist_ok=True)
    return p

_lock = threading.Lock()

def log_emotion(emotion: str, conf: float, source="detector"):
    rec = {"ts": time.time(), "emotion": emotion, "conf": float(conf), "source": source}
    path = os.path.join(_dir_for_now(), "events.jsonl")
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    sp = os.path.join(os.path.dirname(path), "summary.json")
    data = {"total":0, "by_emotion":{}}
    if os.path.exists(sp):
        try: data = json.load(open(sp,"r",encoding="utf-8"))
        except: pass
    data["total"] += 1
    data["by_emotion"][emotion] = 1 + data["by_emotion"].get(emotion, 0)
    json.dump(data, open(sp,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
