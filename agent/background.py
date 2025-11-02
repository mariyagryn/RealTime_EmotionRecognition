# agent/background.py — мінімальний запуск агенту (заглушка)
import time, threading
from utils.app_settings import load

def _loop():
    cfg = load()
    # TODO: підключити реальний AsyncCamera + EmotionAnalyzer
    while True:
        # тут буде аналіз кадрів з частотою cfg["analyze_every"]
        time.sleep(max(0.6, float(cfg.get("analyze_every", 1.2))))

def run_background():
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
