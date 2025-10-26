# ui/live.py — асинхронний Live-режим без лагів (FER + стабілізація)
import time
import cv2
from concurrent.futures import ThreadPoolExecutor

from config import (
    LABELS, DETECTORS, CAM_INDEX, RES_W, RES_H, NAV_H, WINDOW_TITLE
)
from ui.common import draw_nav, draw_transparent_rect, blank_bg
from modules import stats

from agent.capture import AsyncCamera

from agent.engine_fer import FastFerAnalyzer as EmotionAnalyzer

ANALYZE_EVERY = 1.2
MIN_CONF      = 35.0
HOLD_SEC      = 1.0

# стан UI
det_i = 0
DETECTOR = DETECTORS[det_i]
show_help = False
logging_on = False
running = True

def _on_mouse(event, x, y, flags, param):
    """Мінімальний хендлер миші (можеш додати навігацію по кнопках зверху)."""
    pass

def run_live():
    global det_i, DETECTOR, running, show_help, logging_on
    running, show_help, logging_on = True, False, False

    cam = AsyncCamera(index=CAM_INDEX, width=RES_W, height=RES_H)
    an  = EmotionAnalyzer(alpha=0.3)

    pool = ThreadPoolExecutor(max_workers=1)
    pending = None
    last_res = None
    last_inf_t = 0.0

    fps, t_prev = 0.0, time.time()
    t_cum = {k: 0.0 for k in LABELS}

    stable = None
    stable_since = None
    candidate = None
    candidate_since = 0.0

    cv2.namedWindow(WINDOW_TITLE)
    cv2.setMouseCallback(WINDOW_TITLE, _on_mouse, param={"frame": None})
    print("Keys: [D] switch detector | [Q] quit | [Esc] back to menu")

    try:
        while running:
            frame = cam.latest()
            if frame is None:
                time.sleep(0.01)
                continue

            now = time.time()
            dt = now - t_prev
            t_prev = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            if (pending is None) and ((now - last_inf_t) >= ANALYZE_EVERY):
                pending = pool.submit(an.infer, frame.copy())
                last_inf_t = now

            if pending is not None and pending.done():
                try:
                    last_res = pending.result()
                except Exception:
                    last_res = None
                pending = None

            if last_res:
                label = last_res["dominant"]
                conf  = float(last_res["conf"])

                if stable is None:
                    stable, stable_since = label, now
                elif label != stable:
                    if conf >= MIN_CONF:
                        if candidate != label:
                            candidate, candidate_since = label, now
                        elif (now - candidate_since) >= HOLD_SEC:
                            if stable_since is not None:
                                try:
                                    stats.add_segment(stable, int(stable_since), int(now))
                                except Exception as e:
                                    print("[stats] segment save error:", e)
                                t_cum[stable] = t_cum.get(stable, 0.0) + (now - stable_since)
                            stable, stable_since = label, now
                            candidate = None
                    else:
                        candidate = None
                else:
                    candidate = None

                shown = stable or label
                cv2.putText(frame, f"{shown} {conf:.1f}%", (20, NAV_H + 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            panel_w = 260
            x0 = frame.shape[1] - panel_w

            live_cum = dict(t_cum)
            if stable and stable_since:
                live_cum[stable] = live_cum.get(stable, 0.0) + (now - stable_since)

            draw_nav(frame, right_edge_x=x0)
            cv2.rectangle(frame, (x0, 0), (frame.shape[1], frame.shape[0]), (30, 30, 30), -1)
            cv2.putText(frame, f"{DETECTOR} | {fps:,.1f} FPS", (x0 + 10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            cv2.putText(frame, "Time in emotions:", (x0 + 10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            y = 90
            active_label = stable or (last_res and last_res['dominant'])
            for k in ['happy', 'neutral', 'sad', 'angry', 'fear', 'surprise', 'disgust']:
                val = live_cum.get(k, 0.0)
                mm, ss = int(val) // 60, int(val) % 60
                active = (k == active_label)
                cv2.putText(frame, f"{k:<9} {mm:02d}:{ss:02d}",
                            (x0 + 10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 255, 0) if active else (220, 220, 220),
                            2 if active else 1)
                y += 28

            if show_help:
                lines = ["D switch detector", "Q quit", "Esc back to menu"]
                hx1, hy1 = 12, NAV_H + 10
                (tw, _), _ = cv2.getTextSize(max(lines, key=len), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                hw = tw + 30
                hh = 12 + len(lines) * 26
                draw_transparent_rect(frame, (hx1 - 6, hy1 - 8), (hx1 + hw, hy1 - 8 + hh), (0, 0, 0), 0.6)
                yy = hy1
                for hl in lines:
                    cv2.putText(frame, hl, (hx1, yy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
                    yy += 26

            cv2.setMouseCallback(WINDOW_TITLE, _on_mouse, param={"frame": frame})
            cv2.imshow(WINDOW_TITLE, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                running = False
            elif key in (ord('d'), ord('D')):
                det_i = (det_i + 1) % len(DETECTORS)
                DETECTOR = DETECTORS[det_i]
                print(f"[detector UI] -> {DETECTOR}")

    finally:
        end_now = time.time()
        if stable and stable_since:
            try:
                stats.add_segment(stable, int(stable_since), int(end_now))
            except Exception as e:
                print("[stats] final segment save error:", e)

        cam.stop()
        pool.shutdown(wait=False)
        cv2.imshow(WINDOW_TITLE, blank_bg())
