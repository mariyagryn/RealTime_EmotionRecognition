# core/analyzer.py
from __future__ import annotations
import time
import threading
import cv2
from ui.common import LABELS

_HAS_DEEPFACE = False
try:
    from deepface import DeepFace
    _HAS_DEEPFACE = True
except Exception:
    DeepFace = None

_HAS_FER = False
try:
    from fer import FER
    _HAS_FER = True
except Exception:
    FER = None

CV2_FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

class AnalyzerThread(threading.Thread):
    def __init__(self, analyze_every: float = 0.6):
        super().__init__(daemon=True)
        self.analyze_every = max(0.45, float(analyze_every or 0.6))
        self._stop = threading.Event()
        self._last_bgr = None
        self.current: tuple[str, float] = ("neutral", 0.6)
        self.probs = {k: 0.0 for k in LABELS}

        self._fer = None
        if _HAS_FER and not _HAS_DEEPFACE:
            try:
                self._fer = FER(mtcnn=False)
            except Exception:
                self._fer = None

    def stop(self):
        self._stop.set()

    def update_frame(self, bgr):
        if bgr is None:
            return
        try:
            h, w = bgr.shape[:2]
            if max(h, w) > 380:
                scale = 380.0 / max(h, w)
                bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        except Exception:
            pass
        self._last_bgr = bgr

    def _detect_face_crop(self, bgr):
        if bgr is None:
            return None
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            faces = CV2_FACE.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=3, minSize=(40, 40))
            if len(faces) == 0:
                return bgr
            x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
            pad = int(0.15 * max(w, h))
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(bgr.shape[1], x + w + pad)
            y1 = min(bgr.shape[0], y + h + pad)
            return bgr[y0:y1, x0:x1]
        except Exception:
            return bgr

    def _run_deepface(self, bgr_face):
        try:
            face_small = cv2.resize(bgr_face, (224, 224), interpolation=cv2.INTER_AREA)
            out = DeepFace.analyze(
                face_small,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="skip",
            )
            data = out[0] if isinstance(out, list) else out
            ems = data.get("emotion") or data.get("emotions") or {}

            probs = {}
            if isinstance(ems, dict) and ems:
                for k, v in ems.items():
                    if v is None:
                        continue
                    vv = float(v)
                    if vv > 1.0:
                        vv /= 100.0
                    probs[str(k).lower().strip()] = max(0.0, min(vv, 1.0))

            label, conf = ("neutral", 0.6)
            if probs:
                label, conf = max(probs.items(), key=lambda kv: kv[1])

            label = (label or "neutral").strip().lower()
            if label not in LABELS:
                label = "neutral"
            conf = float(max(0.0, min(conf, 1.0)))

            probs_norm = {k: float(probs.get(k, 0.0)) for k in LABELS}
            return (label, conf, probs_norm)
        except Exception:
            return ("neutral", 0.6, {k: 0.0 for k in LABELS})

    def _run_fer(self, bgr_face):
        try:
            if self._fer is None:
                return ("neutral", 0.6, {k: 0.0 for k in LABELS})
            rgb = cv2.cvtColor(bgr_face, cv2.COLOR_BGR2RGB)
            preds = self._fer.detect_emotions(rgb)
            if not preds:
                return ("neutral", 0.6, {k: 0.0 for k in LABELS})

            em = preds[0]["emotions"]
            probs = {str(k).lower(): float(v) for k, v in em.items()}
            label = max(probs.items(), key=lambda kv: kv[1])[0]
            conf = float(probs.get(label, 0.6))
            probs_norm = {k: float(probs.get(k, 0.0)) for k in LABELS}
            return (label, conf, probs_norm)
        except Exception:
            return ("neutral", 0.6, {k: 0.0 for k in LABELS})

    def run(self):
        last = 0.0
        while not self._stop.is_set():
            now = time.time()
            if self._last_bgr is not None and (now - last) >= self.analyze_every:
                face = self._detect_face_crop(self._last_bgr)
                label, conf, probs = ("neutral", 0.6, {k: 0.0 for k in LABELS})

                if _HAS_DEEPFACE and face is not None:
                    label, conf, probs = self._run_deepface(face)
                    if self._fer is not None and (not probs or conf <= 0.0):
                        label, conf, probs = self._run_fer(face)
                elif self._fer is not None and face is not None:
                    label, conf, probs = self._run_fer(face)

                self.current = (label, float(conf))
                self.probs = probs
                last = now
            time.sleep(0.01)
