# live-екран
import time, os, cv2, numpy as np
from deepface import DeepFace
from modules import stats
from config import (LABELS, DETECTORS, ALPHA, CAM_INDEX, RES_W, RES_H,
                    ANALYZE_EVERY, NAV_H, WINDOW_TITLE)
from ui.common import draw_nav, nav_hit, draw_transparent_rect, blank_bg
from utils.text import speak, fmt_s, draw_text_unicode

det_i = 0
DETECTOR = DETECTORS[det_i]

show_help = False
logging_on = False
running = True

def _on_mouse(event, x, y, flags, param):
    global running, show_help, logging_on
    if event == cv2.EVENT_LBUTTONUP:
        hit = nav_hit(x, y)
        if hit == "Exit":
            running = False
        elif hit == "Help":
            show_help = not show_help
        elif hit == "Snap":
            os.makedirs("logs", exist_ok=True)
            cv2.imwrite(f"logs/snap_{int(time.time())}.png", param["frame"])
        elif hit == "Log":
            logging_on = not logging_on

try:
    _ = DeepFace.analyze(np.zeros((224,224,3), dtype=np.uint8),
                         actions=['emotion'], detector_backend='opencv',
                         enforce_detection=False, silent=True)
except Exception:
    pass

def run_live():
    global det_i, DETECTOR, running, show_help, logging_on
    running, show_help, logging_on = True, False, False

    ema = None; fps = 0.0; t_prev = time.time()
    t_cum = {k: 0.0 for k in LABELS}
    curr = None; curr_start = None
    cooldown_s = 60; last_trigger_t = 0.0; msg = ""; msg_till = 0.0

    cap = cv2.VideoCapture(CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, RES_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RES_H)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    last_inf_t = 0.0
    last_result = None

    cv2.setMouseCallback(WINDOW_TITLE, _on_mouse, param={"frame": None})
    print("Keys: [D] switch detector  |  [Q] quit  |  [Esc] back to menu")

    while running:
        for _ in range(2): cap.grab()
        ok, frame = cap.read()
        if not ok:
            frame = blank_bg(sub="Camera error"); cv2.imshow(WINDOW_TITLE, frame); break

        now = time.time()
        dt = now - t_prev; t_prev = now
        if dt > 0: fps = 0.9*fps + 0.1*(1.0/dt)

        try:
            do_infer = (now - last_inf_t) >= ANALYZE_EVERY or last_result is None
            if do_infer:
                res = DeepFace.analyze(frame, actions=['emotion'],
                                       detector_backend=DETECTOR,
                                       enforce_detection=False, silent=True)
                last_result = res[0] if isinstance(res, list) else res
                last_inf_t = now

            r = last_result
            probs = np.array([r['emotion'][k] for k in LABELS], float)
            ema = probs if ema is None else ALPHA*probs + (1-ALPHA)*ema
            idx = int(np.argmax(ema)); dominant = LABELS[idx]; conf = float(ema[idx])

            if curr is None: curr, curr_start = dominant, now
            if dominant != curr:
                try:
                    if curr is not None and curr_start is not None:
                        stats.add_segment(curr, int(curr_start), int(now))
                except Exception as e:
                    print("[stats] segment save error:", e)
                if curr is not None and curr_start is not None:
                    t_cum[curr] += now - curr_start
                curr, curr_start = dominant, now

            live_cum = t_cum.copy()
            live_cum[curr] = live_cum.get(curr, 0.0) + (now - curr_start)

            since = now - curr_start
            if (now - last_trigger_t) > cooldown_s:
                if curr == 'sad' and since >= 10:
                    msg = "Бачу сум ≥ 10с. Тримайся!"; speak("Бачу сум. Тримайся, все буде добре.")
                    last_trigger_t = now; msg_till = now + 4
                elif curr == 'happy' and since >= 6:
                    msg = "Хеей! Сяєш від щастя!"; speak("Що сталося? Ти сяєш від щастя!")
                    last_trigger_t = now; msg_till = now + 4
                elif curr == 'neutral' and since >= 15:
                    msg = "Нудно? Давай мікрочелендж"; speak("Можливо, невеличкий челендж?")
                    last_trigger_t = now; msg_till = now + 4

            cv2.putText(frame, f"{dominant} {conf:.1f}%", (20, NAV_H+28),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

            reg = r.get('region', None)
            if reg:
                x,y,w,h = reg.get('x',0), reg.get('y',0), reg.get('w',0), reg.get('h',0)
                cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)

            panel_w = 260
            x0 = frame.shape[1] - panel_w

            draw_nav(frame, right_edge_x=x0)
            cv2.rectangle(frame, (x0,0), (frame.shape[1], frame.shape[0]), (30,30,30), -1)
            cv2.putText(frame, f"{DETECTOR} | {fps:,.1f} FPS", (x0+10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
            cv2.putText(frame, "Time in emotions:", (x0+10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)

            y = 90
            for k in ['happy','neutral','sad','angry','fear','surprise','disgust']:
                cv2.putText(frame, f"{k:<9} {fmt_s(live_cum.get(k,0.0))}",
                            (x0+10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0,255,0) if k==curr else (220,220,220), 2 if k==curr else 1)
                y += 28

            if show_help:
                lines = ["D switch detector", "Q quit", "Esc back to menu",
                         "Snap save frame", "Log toggle (reserved)"]
                hx1, hy1 = 12, NAV_H + 10
                (tw,_), _ = cv2.getTextSize(max(lines, key=len), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                hw = tw + 30; hh = 12 + len(lines)*26
                draw_transparent_rect(frame, (hx1-6, hy1-8), (hx1+hw, hy1-8+hh), (0,0,0), 0.6)
                yy = hy1
                for hl in lines:
                    cv2.putText(frame, hl, (hx1, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2, cv2.LINE_AA)
                    yy += 26

            if time.time() < msg_till and msg:
                y1 = frame.shape[0]-90; y2 = frame.shape[0]-28
                draw_transparent_rect(frame, (40,y1), (frame.shape[1]-40, y2), (0,0,0), 0.65)
                frame = draw_text_unicode(frame, msg, (60, y2-15), (0,255,255), 24)

        except Exception:
            cv2.putText(frame, "no face", (20, NAV_H+28), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

        cv2.setMouseCallback(WINDOW_TITLE, _on_mouse, param={"frame": frame})
        cv2.imshow(WINDOW_TITLE, frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            running = False
        elif key in (ord('d'), ord('D')):
            det_i = (det_i + 1) % len(DETECTORS); DETECTOR = DETECTORS[det_i]
            print(f"[detector] -> {DETECTOR}")

    end_now = time.time()
    if curr is not None and curr_start is not None:
        try: stats.add_segment(curr, int(curr_start), int(end_now))
        except Exception as e: print("[stats] final segment save error:", e)

    cap.release()
    cv2.imshow(WINDOW_TITLE, blank_bg())
