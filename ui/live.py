# асинхронний Live-режим (стабілізація емоцій + логування сегментів)
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import cv2

from utils.app_settings import load as load_settings
from modules import stats
from utils.telemetry import log_emotion

from agent.capture import AsyncCamera
from agent.analyzer_fast import FastEmotionAnalyzer as EmotionAnalyzer

from config import (
    LABELS,
    DETECTORS,
    CAM_INDEX,
    RES_W, RES_H,
    NAV_H,
    WINDOW_TITLE,
)

try:
    from ui.common import draw_nav, draw_transparent_rect
except Exception:
    def draw_nav(frame, right_edge_x=None):
        pass
    def draw_transparent_rect(*_args, **_kwargs):
        pass

ANALYZE_EVERY = 1.0
MIN_CONF      = 48.0
HOLD_SEC      = 1.2

det_i   = 0
DETECTOR = DETECTORS[det_i]
running  = True
show_help = False


def _parse_resolution(s: str, fallback=(RES_W, RES_H)) -> tuple[int, int]:
    try:
        w, h = map(int, str(s).lower().split("x"))
        return w, h
    except Exception:
        return fallback


def run_live():
    global det_i, DETECTOR, running, show_help, ANALYZE_EVERY, MIN_CONF, HOLD_SEC

    cfg = load_settings()
    save_events = bool(cfg.get("privacy_save_stats", True))

    ANALYZE_EVERY = float(cfg.get("analyze_every", ANALYZE_EVERY))
    MIN_CONF      = float(cfg.get("min_conf",      MIN_CONF))
    HOLD_SEC      = float(cfg.get("hold_sec",      HOLD_SEC))
    ema_alpha     = float(cfg.get("ema", 0.3))
    det_name      = cfg.get("detector", DETECTOR)
    backend_name  = cfg.get("backend", "deepface")

    if det_name in DETECTORS:
        DETECTOR = det_name

    cam_w, cam_h = _parse_resolution(cfg.get("resolution", f"{RES_W}x{RES_H}"))
    cam_index    = int(cfg.get("camera_index", CAM_INDEX))

    cam = AsyncCamera(index=cam_index, width=cam_w, height=cam_h)
    an  = EmotionAnalyzer(alpha=ema_alpha, force_backend=backend_name)

    pool      = ThreadPoolExecutor(max_workers=1)
    pending   = None
    last_res  = None
    last_inf_t= 0.0

    fps, t_prev = 0.0, time.time()
    t_cum = {k: 0.0 for k in LABELS}

    stable          = None
    stable_since    = None
    candidate       = None
    candidate_since = 0.0

    cv2.namedWindow(WINDOW_TITLE)
    print("Keys: [D] switch detector | [Q] quit | [Esc] back to menu")

    try:
        while running:
            frame = cam.latest()
            if frame is None:
                time.sleep(0.01)
                continue

            now = time.time()
            dt  = now - t_prev
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

            label = None
            conf  = 0.0
            err   = None
            backend = backend_name

            if last_res:
                if isinstance(last_res, dict):
                    label   = last_res.get("dominant") or last_res.get("emotion") or "neutral"
                    conf    = float(last_res.get("conf", last_res.get("confidence", 0.0)))
                    if conf <= 1.0: conf *= 100.0
                    err     = last_res.get("error")
                    backend = last_res.get("backend", backend_name)
                else:
                    # tuple (label, conf) фолбек
                    label, conf = last_res
                    conf = float(conf)
                    if conf <= 1.0: conf *= 100.0

                cv2.putText(frame, f"backend: {backend}", (20, NAV_H + 54),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
                if err:
                    cv2.putText(frame, f"ERR: {str(err)[:60]}", (20, NAV_H + 78),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 1)

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
                            try:
                                log_emotion(label, conf, source=backend)
                            except Exception:
                                pass
                            stable, stable_since = label, now
                            candidate = None
                    else:
                        candidate = None
                else:
                    candidate = None

                shown = stable or label or "neutral"
                cv2.putText(
                    frame,
                    f"{shown} {conf:.1f}%",
                    (20, NAV_H + 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )
                if save_events:
                    try:
                        log_emotion(shown, conf, source=backend)
                    except Exception:
                        pass

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
            active_label = stable or (last_res and isinstance(last_res, dict) and last_res.get('dominant'))
            for k in ['happy', 'neutral', 'sad', 'angry', 'fear', 'surprise', 'disgust']:
                val = live_cum.get(k, 0.0)
                mm, ss = int(val) // 60, int(val) % 60
                active = (k == active_label)
                cv2.putText(
                    frame,
                    f"{k:<9} {mm:02d}:{ss:02d}",
                    (x0 + 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0) if active else (220, 220, 220),
                    2 if active else 1
                )
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

            cv2.imshow(WINDOW_TITLE, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                running = False
            elif key in (ord('d'), ord('D')):
                try:
                    det_i_local = (DETECTORS.index(DETECTOR) + 1) % len(DETECTORS)
                except ValueError:
                    det_i_local = 0
                DETECTOR = DETECTORS[det_i_local]
                print(f"[detector UI] -> {DETECTOR}")

    finally:
        end_now = time.time()
        if stable and stable_since:
            try:
                stats.add_segment(stable, int(stable_since), int(end_now))
            except Exception as e:
                print("[stats] final segment save error:", e)
        try:
            cam.stop()
        except Exception:
            pass
        try:
            if pending is not None and not pending.done():
                pending.cancel()
            pool.shutdown(wait=True, cancel_futures=True)
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
            time.sleep(0.1)
        except Exception:
            pass
