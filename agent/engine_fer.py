# agent/engine_fer.py
from __future__ import annotations
import os, cv2, numpy as np

try:
    import mediapipe as mp
except Exception:
    mp = None

import onnxruntime as ort

FERPLUS_LABELS = ["neutral","happiness","surprise","sadness","anger","disgust","fear","contempt"]
UI_LABELS      = ['angry','disgust','fear','happy','sad','surprise','neutral']
MAP_TO_UI = {
    "neutral":"neutral","happiness":"happy","surprise":"surprise","sadness":"sad",
    "anger":"angry","disgust":"disgust","fear":"fear","contempt":"neutral",
}

class FerEngine:
    def __init__(self, model_path: str = "models/ferplus.onnx",
                 face_min_conf: float = 0.30,
                 pad_ratio: float = 0.25,
                 ema_alpha: float = 0.60,
                 use_ema: bool = True):
        self.face_min_conf = float(face_min_conf)
        self.pad_ratio = float(pad_ratio)
        self.use_ema = bool(use_ema)
        self.ema_alpha = float(ema_alpha)
        self.ema = None
        self._dbg_cnt = 0

        self.fd = None
        if mp is not None:
            try:
                self.fd = mp.solutions.face_detection.FaceDetection(
                    model_selection=0, min_detection_confidence=self.face_min_conf
                )
            except Exception:
                self.fd = None
        self.haar = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"FER+ model not found at {model_path}")
        self.sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name  = self.sess.get_inputs()[0].name
        self.output_name = self.sess.get_outputs()[0].name

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        x = x - np.max(x)
        ex = np.exp(x)
        return ex / np.sum(ex)

    def _crop_mp(self, frame_bgr):
        if self.fd is None: return None
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self.fd.process(rgb)
        if not res or not res.detections: return None
        d = max(res.detections, key=lambda d: d.score[0])
        if d.score[0] < self.face_min_conf: return None
        bb = d.location_data.relative_bounding_box
        x1 = int(max(0, bb.xmin) * w); y1 = int(max(0, bb.ymin) * h)
        x2 = int(min(1, bb.xmin + bb.width) * w); y2 = int(min(1, bb.ymin + bb.height) * h)
        pad = int(self.pad_ratio * max(x2-x1, y2-y1))
        x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad); y2 = min(h, y2 + pad)
        roi = frame_bgr[y1:y2, x1:x2]
        return roi if roi.size else None

    def _crop_haar(self, frame_bgr):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.haar.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
        if len(faces) == 0: return None
        x, y, w, h = max(faces, key=lambda f: f[2]*f[3])
        pad = int(self.pad_ratio * max(w, h))
        x1 = max(0, x - pad); y1 = max(0, y - pad)
        x2 = min(frame_bgr.shape[1], x + w + pad)
        y2 = min(frame_bgr.shape[0], y + h + pad)
        roi = frame_bgr[y1:y2, x1:x2]
        return roi if roi.size else None

    def _detect_face(self, frame_bgr):
        face = self._crop_mp(frame_bgr)
        if face is None:
            face = self._crop_haar(frame_bgr)
        return face

    def _prep_a(self, face_bgr):
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        gray = cv2.resize(gray, (64,64), interpolation=cv2.INTER_AREA)
        x = gray.astype(np.float32)/255.0
        x = (x - 0.5) / 0.5
        return np.expand_dims(x, (0,1))

    def _prep_b(self, face_bgr):
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        gray = cv2.resize(gray, (64,64), interpolation=cv2.INTER_AREA)
        x = gray.astype(np.float32)/255.0
        return np.expand_dims(x, (0,1))

    def _run_onnx(self, x):
        logits = self.sess.run([self.output_name], {self.input_name: x})[0].squeeze()
        return self._softmax(logits)

    def _to_ui7(self, probs8: np.ndarray):
        out = np.zeros(len(UI_LABELS), dtype=np.float32)
        for i, fer_label in enumerate(FERPLUS_LABELS):
            ui_idx = UI_LABELS.index(MAP_TO_UI[fer_label])
            out[ui_idx] += probs8[i]
        return out

    def infer(self, frame_bgr):
        face = self._detect_face(frame_bgr)
        if face is None:
            if self.ema is not None:
                idx = int(np.argmax(self.ema))
                return UI_LABELS[idx], float(self.ema[idx])
            return "neutral", 0.2

        p8_a = self._run_onnx(self._prep_a(face))
        p8_b = self._run_onnx(self._prep_b(face))
        p7_a = self._to_ui7(p8_a)
        p7_b = self._to_ui7(p8_b)
        cand = p7_a if p7_a[UI_LABELS.index("neutral")] < p7_b[UI_LABELS.index("neutral")] else p7_b

        if not self.use_ema or self.ema is None:
            self.ema = cand
        else:
            a = self.ema_alpha
            self.ema = a*cand + (1-a)*self.ema

        idx = int(np.argmax(self.ema))

        self._dbg_cnt += 1
        if self._dbg_cnt % 10 == 0:
            order = np.argsort(self.ema)[::-1][:3]
            print("FER+ top3:", [(UI_LABELS[i], float(self.ema[i])) for i in order])

        return UI_LABELS[idx], float(self.ema[idx])
