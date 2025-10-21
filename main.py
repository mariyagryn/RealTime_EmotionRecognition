# app_menu.py — старт-меню + запуск Live-аналізу (DeepFace + OpenCV)
import os, time, cv2, numpy as np
from deepface import DeepFace
from modules import stats
from PIL import Image, ImageDraw, ImageFont

LABELS = ['angry','disgust','fear','happy','sad','surprise','neutral']
DETECTORS = ['opencv','mediapipe','retinaface']
det_i = 0
DETECTOR = DETECTORS[det_i]

ALPHA = 0.3
CAM_INDEX = 0
RES_W, RES_H = 480, 270
ANALYZE_EVERY = 0.50

NAV_H = 48
NAV_ITEMS = ["Help", "Snap", "Log", "Exit"]
NAV_RECTS = []

def speak(t):
    try: os.system(f'say "{t}" &')
    except Exception: pass

def fmt_s(x):
    m = int(x)//60; s = int(x)%60
    return f"{m:02d}:{s:02d}"

def draw_text_unicode(frame_bgr, text, pos, color=(0,255,255), size=24):
    try:
        font_paths = [
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/SFNS.ttf"
        ]
        fp = next((p for p in font_paths if os.path.exists(p)), None)
        if fp is None: raise RuntimeError("no font")
        img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        draw.text(pos, text, font=ImageFont.truetype(fp, size), fill=(color[2], color[1], color[0]))
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception:
        cv2.putText(frame_bgr, text.encode('ascii','ignore').decode(), pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return frame_bgr

def draw_transparent_rect(img, p1, p2, color=(30,30,30), alpha=0.85):
    overlay = img.copy()
    cv2.rectangle(overlay, p1, p2, color, -1)
    cv2.addWeighted(overlay, alpha, img, 1-alpha, 0, img)

def draw_nav(frame, right_edge_x):
    global NAV_RECTS
    NAV_RECTS = []
    draw_transparent_rect(frame, (0,0), (right_edge_x, NAV_H), (30,30,30), 0.9)
    x = 12; y1 = 6
    for name in NAV_ITEMS:
        (tw, th), _ = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
        w = tw + 28; h = NAV_H - 20
        x2 = min(x + w, right_edge_x - 12)
        if x2 <= x: break
        cv2.putText(frame, name, (x+14, y1+h-12), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2, cv2.LINE_AA)
        NAV_RECTS.append((name, x, y1, x2, y1+h))
        x = x2 + 16

def nav_hit(x, y):
    for name, x1, y1, x2, y2 in NAV_RECTS:
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None

MENU_BTNS = [
    ("Start Analysis", "start"),
    ("Statistics", "stats"),
    ("Settings", "settings"),
    ("Help", "help"),
    ("Exit", "exit"),
]

MENU_RECTS = []
MENU_CHOICE = None

def draw_menu_bg(w=960, h=540):
    bg = np.zeros((h, w, 3), dtype=np.uint8)
    bg[:] = (20,20,25)
    title = "EMOTION ANALYZER"
    (tw, th), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)
    cv2.putText(bg, title, ((w-tw)//2, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,255,255), 3, cv2.LINE_AA)
    sub = "The camera will not turn on until you start the analysis."
    (sw, sh), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.putText(bg, sub, ((w-sw)//2, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2, cv2.LINE_AA)
    return bg

def draw_menu_buttons(img):
    global MENU_RECTS
    MENU_RECTS = []
    h, w = img.shape[:2]
    btn_w, btn_h = 360, 56
    start_y = 170
    gap = 18
    for i, (label, key) in enumerate(MENU_BTNS):
        x1 = (w - btn_w)//2
        y1 = start_y + i*(btn_h + gap)
        x2, y2 = x1 + btn_w, y1 + btn_h
        draw_transparent_rect(img, (x1, y1), (x2, y2), (40,40,50), 0.7)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.putText(img, label, (x1 + (btn_w - tw)//2, y1 + (btn_h+th)//2 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2, cv2.LINE_AA)
        MENU_RECTS.append((key, x1, y1, x2, y2))

def menu_hit(x, y):
    for key, x1, y1, x2, y2 in MENU_RECTS:
        if x1 <= x <= x2 and y1 <= y <= y2:
            return key
    return None

def on_menu_mouse(event, x, y, flags, param):
    global MENU_CHOICE
    if event == cv2.EVENT_LBUTTONUP:
        hit = menu_hit(x, y)
        if hit:
            MENU_CHOICE = hit

def show_menu(window="Emotion App"):
    global MENU_CHOICE
    MENU_CHOICE = None
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_menu_mouse)
    bg = draw_menu_bg()
    while True:
        frame = bg.copy()
        draw_menu_buttons(frame)
        cv2.imshow(window, frame)
        key = cv2.waitKey(16) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            return "exit"
        if MENU_CHOICE is not None:
            choice = MENU_CHOICE
            MENU_CHOICE = None
            return choice

show_help = False
logging_on = False
running = True

def on_mouse(event, x, y, flags, param):
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

def run_live(window="Emotion App"):
    global det_i, DETECTOR, running, show_help, logging_on
    running = True; show_help = False; logging_on = False

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

    cv2.setMouseCallback(window, on_mouse, param={"frame": None})
    print("Keys: [D] switch detector  |  [Q] quit  |  [Esc] back to menu")

    while running:
        for _ in range(2):
            cap.grab()
        ok, frame = cap.read()
        if not ok:
            cv2.putText(frame, "camera error", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
            break

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

            if curr is None:
                curr, curr_start = dominant, now

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
                (tw, th), _ = cv2.getTextSize(max(lines, key=len), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                hw = tw + 30; hh = 12 + len(lines)*26
                draw_transparent_rect(frame, (hx1-6, hy1-8), (hx1+hw, hy1-8+hh), (0,0,0), 0.6)
                yy = hy1
                for hl in lines:
                    cv2.putText(frame, hl, (hx1, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2, cv2.LINE_AA)
                    yy += 26

            now2 = time.time()
            if now2 < msg_till and msg:
                y1 = frame.shape[0]-90; y2 = frame.shape[0]-28
                draw_transparent_rect(frame, (40,y1), (frame.shape[1]-40, y2), (0,0,0), 0.65)
                frame = draw_text_unicode(frame, msg, (60, y2-15), (0,255,255), 24)

        except Exception:
            cv2.putText(frame, "no face", (20, NAV_H+28), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

        cv2.setMouseCallback(window, on_mouse, param={"frame": frame})
        cv2.imshow(window, frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):   # Esc → назад у меню
            running = False
        elif key in (ord('d'), ord('D')):
            det_i = (det_i + 1) % len(DETECTORS)
            DETECTOR = DETECTORS[det_i]
            print(f"[detector] -> {DETECTOR}")

    end_now = time.time()
    if curr is not None and curr_start is not None:
        try:
            stats.add_segment(curr, int(curr_start), int(end_now))
        except Exception as e:
            print("[stats] final segment save error:", e)

    cap.release()
    cv2.imshow(window, draw_menu_bg())  # повертаємо фон меню

# ========= main =========
def main():
    win = "Emotion App"
    cv2.namedWindow(win)
    while True:
        choice = show_menu(win)
        if choice == "start":
            run_live(win)       # відкриваємо камеру тільки тут
        elif choice == "stats":
            # заглушка: просто покажемо повідомлення
            img = draw_menu_bg()
            msg = "Статистика: поки заглушка (експорт/перегляд сесій додамо далі)"
            (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(img, msg, ((img.shape[1]-tw)//2, img.shape[0]-60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,220,255), 2)
            cv2.imshow(win, img); cv2.waitKey(900)
        elif choice == "settings":
            img = draw_menu_bg()
            msg = "Налаштування: вибір камери/детектора/приватності (додамо далі)"
            (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(img, msg, ((img.shape[1]-tw)//2, img.shape[0]-60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,220,255), 2)
            cv2.imshow(win, img); cv2.waitKey(900)
        elif choice == "help":
            img = draw_menu_bg()
            msg = "Довідка: камера вмикається лише після 'Почати аналіз'"
            (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(img, msg, ((img.shape[1]-tw)//2, img.shape[0]-60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,220,255), 2)
            cv2.imshow(win, img); cv2.waitKey(900)
        else:
            break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
