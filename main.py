# main.py — Real-Time Emotion Recognition (DeepFace + OpenCV)
# Keys: D — switch detector, Q — quit
import cv2, numpy as np, time, os
from deepface import DeepFace

LABELS = ['angry','disgust','fear','happy','sad','surprise','neutral']
DETECTORS = ['opencv','mediapipe','retinaface']  # press D to switch
det_i = 0
DETECTOR = DETECTORS[det_i]

ALPHA = 0.3
CAM_INDEX = 0
RES_W, RES_H = 960, 540

ema = None
fps = 0.0
t_prev = time.time()

t_cum = {k: 0.0 for k in LABELS}
curr = None
curr_start = None

cooldown_s = 60
last_trigger_t = 0.0
msg = ""
msg_till = 0.0

def speak(text):
    try: os.system(f'say "{text}" &')
    except Exception: pass

def fmt_s(x):
    m = int(x)//60; s = int(x)%60
    return f"{m:02d}:{s:02d}"

cap = cv2.VideoCapture(CAM_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, RES_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RES_H)

print("Keys: [D] switch detector  |  [Q] quit")

while True:
    ok, frame = cap.read()
    if not ok: break

    now = time.time()
    dt = now - t_prev; t_prev = now
    if dt > 0: fps = 0.9*fps + 0.1*(1.0/dt)

    try:
        res = DeepFace.analyze(frame, actions=['emotion'],
                               detector_backend=DETECTOR,
                               enforce_detection=False, silent=True)
        r = res[0] if isinstance(res, list) else res
        probs = np.array([r['emotion'][k] for k in LABELS], float)
        ema = probs if ema is None else ALPHA*probs + (1-ALPHA)*ema
        idx = int(np.argmax(ema)); dominant = LABELS[idx]; conf = float(ema[idx])

        if curr is None: curr, curr_start = dominant, now
        if dominant != curr:
            t_cum[curr] += now - curr_start
            curr, curr_start = dominant, now
        live_cum = t_cum.copy(); live_cum[curr] = live_cum.get(curr,0.0) + (now - curr_start)

        since = now - curr_start
        if (now - last_trigger_t) > cooldown_s:
            if curr == 'sad' and since >= 10:
                msg = "🤖 Бачу сум ≥10с. Тримайся!"; speak("Бачу сум. Тримайся, все буде добре.")
                last_trigger_t = now; msg_till = now + 4
            elif curr == 'happy' and since >= 6:
                msg = "🤖 Хеей! Сяєш від щастя 😄"; speak("Що сталося? Ти сяєш від щастя!")
                last_trigger_t = now; msg_till = now + 4
            elif curr == 'neutral' and since >= 15:
                msg = "🤖 Нудно? Давай мікрочелендж 💡"; speak("Можливо, невеличкий челендж?")
                last_trigger_t = now; msg_till = now + 4

        cv2.putText(frame, f"{dominant} {conf:.1f}%", (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

        reg = r.get('region', None)
        if reg:
            x,y,w,h = reg.get('x',0), reg.get('y',0), reg.get('w',0), reg.get('h',0)
            cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)

        panel_w = 260; x0 = frame.shape[1] - panel_w
        cv2.rectangle(frame, (x0,0), (frame.shape[1], frame.shape[0]), (30,30,30), -1)
        cv2.putText(frame, f"{DETECTOR} | {fps:,.1f} FPS", (x0+10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,0), 2)
        cv2.putText(frame, "Time in emotions:", (x0+10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
        y = 90
        for k in ['happy','neutral','sad','angry','fear','surprise','disgust']:
            cv2.putText(frame, f"{k:<9} {fmt_s(live_cum.get(k,0.0))}",
                        (x0+10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0,255,0) if k==curr else (220,220,220), 2 if k==curr else 1)
            y += 28

        if now < msg_till and msg:
            cv2.rectangle(frame, (40, frame.shape[0]-80), (frame.shape[1]-40, frame.shape[0]-30), (0,0,0), -1)
            cv2.putText(frame, msg, (60, frame.shape[0]-45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

    except Exception:
        cv2.putText(frame, "no face", (20,40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

    cv2.imshow("Emotion Recognition (Q quit | D detector)", frame)
    key = cv2.waitKey(1) & 0xFF
    if key in (ord('q'), ord('Q')):
        if curr is not None and curr_start is not None:
            t_cum[curr] += time.time() - curr_start
        break
    elif key in (ord('d'), ord('D')):
        det_i = (det_i + 1) % len(DETECTORS)
        DETECTOR = DETECTORS[det_i]
        print(f"[detector] -> {DETECTOR}")

cap.release(); cv2.destroyAllWindows()

print("\nSESSION SUMMARY:")
for k in ['happy','neutral','sad','angry','fear','surprise','disgust']:
    print(f"{k:>8}: {fmt_s(t_cum.get(k,0.0))}")
