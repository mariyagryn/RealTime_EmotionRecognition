# швидкий аналіз: mediapipe знаходить bbox, DeepFace аналізує лише кроп
import cv2, numpy as np
import mediapipe as mp
from deepface import DeepFace

LABELS = ['angry','disgust','fear','happy','sad','surprise','neutral']

class FastEmotionAnalyzer:
    def __init__(self, alpha=0.3, face_min_conf=0.6):
        self.alpha = alpha
        self.ema = None
        self.face_min_conf = face_min_conf
        self.fd = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)
        _ = DeepFace.analyze(np.zeros((224,224,3), dtype=np.uint8),
                             actions=['emotion'], detector_backend='opencv',
                             enforce_detection=False, silent=True)

    def _crop_face(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self.fd.process(rgb)
        if not res.detections:
            return None
        d = max(res.detections, key=lambda d: d.score[0])
        if d.score[0] < self.face_min_conf:
            return None
        bb = d.location_data.relative_bounding_box
        x1 = int(max(0, bb.xmin) * w); y1 = int(max(0, bb.ymin) * h)
        x2 = int(min(1, bb.xmin + bb.width) * w); y2 = int(min(1, bb.ymin + bb.height) * h)
        pad = int(0.08 * max(x2-x1, y2-y1))
        x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad); y2 = min(h, y2 + pad)
        face = frame_bgr[y1:y2, x1:x2]
        return face if face.size else None

    def infer(self, frame_bgr):
        face = self._crop_face(frame_bgr)
        has_face = face is not None
        if has_face:
            face_small = cv2.resize(face, (224,224), interpolation=cv2.INTER_AREA)
            res = DeepFace.analyze(face_small, actions=['emotion'],
                                   detector_backend='skip',
                                   enforce_detection=False, silent=True)
            r = res[0] if isinstance(res, list) else res
            probs_vec = np.array([r['emotion'][k] for k in LABELS], dtype=float)
        else:
            probs_vec = self.ema if self.ema is not None else np.zeros(len(LABELS), float)

        self.ema = probs_vec if self.ema is None else 0.3*probs_vec + 0.7*(self.ema)
        idx = int(np.argmax(self.ema))
        return {
            "dominant": LABELS[idx],
            "conf": float(self.ema[idx]),
            "probs": {k: float(self.ema[i]) for i,k in enumerate(LABELS)},
            "has_face": has_face
        }
