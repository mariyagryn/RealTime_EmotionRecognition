# agent/core.py
from __future__ import annotations
import os, time, sys
from datetime import datetime

import cv2

from modules.rules import RuleConfig, RuleState, pick_suggestion
from modules import stats

def _parse_res(s: str) -> tuple[int,int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        return 320, 180

class Camera:
    def __init__(self, index=0, resolution="320x180"):
        self.index = int(index)
        try:
            self.cap = cv2.VideoCapture(self.index, cv2.CAP_AVFOUNDATION)
        except Exception:
            self.cap = cv2.VideoCapture(self.index)
        w, h = _parse_res(resolution)
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
        except Exception:
            pass

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        try:
            if self.cap: self.cap.release()
        except Exception:
            pass

_HAS_DEEPFACE=_HAS_FER=False
try:
    from deepface import DeepFace
    _HAS_DEEPFACE=True
except Exception:
    pass
try:
    from fer import FER
    _HAS_FER=True
except Exception:
    pass

import threading
CV2_FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
LABELS = ["happy","neutral","sad","angry","fear","surprise","disgust"]

class AnalyzerThread(threading.Thread):
    def __init__(self, backend: str, analyze_every: float):
        super().__init__(daemon=True)
        self.backend = backend
        self.analyze_every = max(0.5, float(analyze_every or 1.0))
        self._last_bgr = None
        self._stop = threading.Event()
        self.current = ("neutral", 0.6)
        self._fer = FER(mtcnn=False) if (backend=="fer" and _HAS_FER) else (FER(mtcnn=False) if _HAS_FER and not _HAS_DEEPFACE else None)

    def update_frame(self, bgr): self._last_bgr = bgr
    def stop(self): self._stop.set()

    def _detect_face_crop(self, bgr):
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            faces = CV2_FACE.detectMultiScale(gray, 1.05, 3, minSize=(40,40))
            if len(faces)==0: return bgr
            x,y,w,h = max(faces, key=lambda b:b[2]*b[3])
            pad = int(0.12*max(w,h))
            x0=max(0,x-pad); y0=max(0,y-pad); x1=min(bgr.shape[1], x+w+pad); y1=min(bgr.shape[0], y+h+pad)
            return bgr[y0:y1, x0:x1]
        except Exception:
            return bgr

    def _run_deepface(self, bgr):
        try:
            out = DeepFace.analyze(bgr, actions=["emotion"], enforce_detection=False, detector_backend="skip")
            data = out[0] if isinstance(out,list) else out
            ems = data.get("emotion") or data.get("emotions") or {}
            if isinstance(ems, dict) and ems:
                ems = {k.lower(): float(v) for k,v in ems.items() if v is not None}
                lab, conf = max(ems.items(), key=lambda kv: kv[1])
                if conf>1.0: conf/=100.0
            else:
                lab = (str(data.get("dominant_emotion") or "neutral")).lower()
                conf = float(data.get("emotion", {}).get(lab, 0.6))
                if conf>1.0: conf/=100.0
                if conf<=0.0: conf=0.6
            if lab not in LABELS: lab="neutral"
            return (lab, float(max(0.0, min(conf,1.0))))
        except Exception:
            return ("neutral", 0.6)

    def _run_fer(self, bgr):
        try:
            if not self._fer: return ("neutral", 0.6)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            preds = self._fer.detect_emotions(rgb)
            if not preds: return ("neutral", 0.6)
            em = preds[0]["emotions"]
            lab = max(em.items(), key=lambda kv: kv[1])[0].lower()
            conf = float(em[lab])
            return (lab, conf)
        except Exception:
            return ("neutral", 0.6)

    def run(self):
        last = 0.0
        while not self._stop.is_set():
            now = time.time()
            if self._last_bgr is not None and (now - last) >= self.analyze_every:
                face = self._detect_face_crop(self._last_bgr)
                lab, conf = ("neutral", 0.6)
                if face is not None:
                    if self.backend=="deepface" and _HAS_DEEPFACE:
                        lab, conf = self._run_deepface(face)
                        if conf<=0.0 and _HAS_FER: lab, conf = self._run_fer(face)
                    elif self.backend=="fer" and _HAS_FER:
                        lab, conf = self._run_fer(face)
                        if conf<=0.0 and _HAS_DEEPFACE: lab, conf = self._run_deepface(face)
                    else:
                        if _HAS_FER: lab, conf = self._run_fer(face)
                        elif _HAS_DEEPFACE: lab, conf = self._run_deepface(face)
                self.current = (lab, float(conf))
                last = now
            time.sleep(0.01)

def notify_mac(title: str, text: str):
    try:
        os.system(f"""osascript -e 'display notification "{text}" with title "{title}"'""")
    except Exception:
        pass

def run_agent(cfg: dict):
    res = str(cfg.get("resolution", "320x180"))
    cam_index = int(cfg.get("camera_index", 0))
    backend = str(cfg.get("backend", "deepface" if _HAS_DEEPFACE else ("fer" if _HAS_FER else "fer")))
    analyze_every = float(cfg.get("analyze_every", 1.0))

    cam = Camera(index=cam_index, resolution=res)
    an = AnalyzerThread(backend, analyze_every); an.start()

    rules = RuleConfig(
        sad_sec=int(cfg.get("rule_sad_sec", 60)),
        angry_sec=int(cfg.get("rule_angry_sec", 30)),
        neutral_sec=int(cfg.get("rule_neutral_sec", 120)),
        noface_pct=int(cfg.get("rule_noface_pct", 40)),
        cooldown_min=int(cfg.get("rule_cooldown_min", 30)),
        enable_breathing=bool(cfg.get("rule_breathing", True)),
        enable_pomodoro=bool(cfg.get("rule_pomodoro", True)),
        enable_mirror=bool(cfg.get("rule_mirror", True)),
        enable_speech=bool(cfg.get("rule_speech", True)),
    )
    rs = RuleState()
    emo_acc = {k:0.0 for k in LABELS}

    started = datetime.utcnow().isoformat()
    try:
        last_tick = time.time()
        while True:
            frame = cam.read()
            if frame is not None:
                an.update_frame(frame)

            lab, conf = an.current
            now = time.time()
            dt = now - last_tick
            last_tick = now

            if lab in LABELS:
                emo_acc[lab] += dt
                rs.feed_face_presence(True, dt)
                stats.log_event(lab, dt)  # подія в events.jsonl
            else:
                rs.feed_face_presence(False, dt)

            trig = None
            if emo_acc.get("sad",0.0)   >= rules.sad_sec:     trig = pick_suggestion("sad", rules)
            elif emo_acc.get("angry",0.0)>= rules.angry_sec:  trig = pick_suggestion("angry", rules)
            elif emo_acc.get("neutral",0.0)>=rules.neutral_sec: trig = pick_suggestion("neutral", rules)
            if trig is None and rs.noface_pct() >= float(rules.noface_pct):
                if rules.enable_mirror: trig = "mirror"

            if trig and rs.can_fire(rules.cooldown_min):
                notify_mac("Emotion", {
                    "breathing":"Breathing 2 min?",
                    "pomodoro":"Pomodoro 15 min?",
                    "mirror":"Mirror 1 min?",
                    "speech":"Speech practice 2 min?",
                }.get(trig, "Take a short break?"))
                rs.mark_fired()
                for k in emo_acc: emo_acc[k]=0.0

                if trig=="breathing":
                    try:
                        from ui.breathing import show_breathing
                        # fire-and-forget у бекграунді
                        import threading
                        threading.Thread(target=lambda: show_breathing(duration_sec=90), daemon=True).start()
                    except Exception:
                        pass

            time.sleep(0.05)
    finally:
        try: an.stop(); an.join(timeout=0.5)
        except Exception: pass
        try: cam.release()
        except Exception: pass
        # зведення сесії
        try:
            totals = {k: float(stats.totals_last_session().get(k,0.0)) if hasattr(stats,"totals_last_session") else {k:0.0 for k in LABELS}}
        except Exception:
            totals = {k:0.0 for k in LABELS}
        try:
            stats.write_session_summary(
                totals=totals,
                meta={"started_at": started, "ended_at": datetime.utcnow().isoformat(), "mode":"agent"}
            )
        except Exception:
            pass
