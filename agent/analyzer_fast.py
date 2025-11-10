# agent/analyzer_fast.py
from __future__ import annotations
import pkgutil, cv2, numpy as np

_HAS_DEEPFACE = pkgutil.find_loader("deepface") is not None
if _HAS_DEEPFACE:
    from deepface import DeepFace  # type: ignore

# опційний mediapipe для кращого кропу
try:
    import mediapipe as mp
except Exception:
    mp = None

class FastEmotionAnalyzer:
    def __init__(self, alpha: float = 0.35, force_backend: str = "auto"):
        self.alpha = float(alpha)
        self.prev = None
        self.backend = "deepface" if (force_backend in ("auto","deepface") and _HAS_DEEPFACE) else "dummy"

        # легкий детектор: MediaPipe → fallback Haar
        self.fd = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.35) if mp else None
        self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def _crop_face(self, frame_bgr):
        h, w = frame_bgr.shape[:2]

        # 1) MediaPipe (якщо є)
        if self.fd is not None:
            res = self.fd.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
            if res and res.detections:
                d = max(res.detections, key=lambda d: d.score[0])
                bb = d.location_data.relative_bounding_box
                x1 = int(max(0, bb.xmin) * w); y1 = int(max(0, bb.ymin) * h)
                x2 = int(min(1, bb.xmin + bb.width) * w); y2 = int(min(1, bb.ymin + bb.height) * h)
                pad = int(0.30 * max(x2 - x1, y2 - y1))  # щедрий паддинг
                x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
                x2 = min(w, x2 + pad); y2 = min(h, y2 + pad)
                roi = frame_bgr[y1:y2, x1:x2]
                if roi.size: return roi

        # 2) Haar (fallback)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.haar.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
        if len(faces):
            x, y, ww, hh = max(faces, key=lambda f: f[2]*f[3])
            pad = int(0.30 * max(ww, hh))
            x1 = max(0, x - pad); y1 = max(0, y - pad)
            x2 = min(w, x + ww + pad); y2 = min(h, y + hh + pad)
            roi = frame_bgr[y1:y2, x1:x2]
            if roi.size: return roi

        return None

    def _ema(self, emo: str, conf: float):
        if self.prev is None:
            self.prev = (emo, conf); return emo, conf
        pe, pc = self.prev
        blended = pc*(1-self.alpha) + conf*self.alpha
        out = emo if conf >= pc else pe
        self.prev = (out, blended)
        return out, blended

    def analyze(self, frame_bgr) -> dict:
        if self.backend != "deepface":
            return {"dominant": "neutral", "conf": 0.0, "backend": self.backend}

        try:
            face = self._crop_face(frame_bgr)
            if face is None:
                # нема обличчя — не шумимо
                emo, conf = self._ema("neutral", 0.0)
                return {"dominant": emo, "conf": conf, "backend": "deepface"}

            # легкий препроц для контрасту
            yuv = cv2.cvtColor(face, cv2.COLOR_BGR2YUV)
            yuv[...,0] = cv2.equalizeHist(yuv[...,0])
            face_eq = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

            # DeepFace на вже вирізаному обличчі (детекцію скіпаємо)
            res = DeepFace.analyze(
                img_path=face_eq,
                actions=["emotion"],
                detector_backend="skip",
                enforce_detection=False,
                silent=True
            )
            item = res[0] if isinstance(res, list) else res
            emo = item.get("dominant_emotion", "neutral")
            conf = float(item.get("emotion", {}).get(emo, 0.0))  # у %

        except Exception as e:
            return {"dominant": "neutral", "conf": 0.0, "backend": "deepface", "error": str(e)}

        emo, conf = self._ema(emo, conf)
        return {"dominant": emo, "conf": conf, "backend": "deepface"}

    # сумісний інтерфейс для live.py
    def infer(self, frame_bgr):
        return self.analyze(frame_bgr)
