import cv2, numpy as np
from deepface import DeepFace

LABELS = ['angry','disgust','fear','happy','sad','surprise','neutral']

class EmotionAnalyzer:
    def __init__(self, detector_backend='opencv', alpha=0.3, scale_for_infer=0.5):
        self.detector = detector_backend
        self.alpha = alpha
        self.scale = float(scale_for_infer)
        self.ema = None
        _ = DeepFace.analyze(
            np.zeros((224,224,3), dtype=np.uint8),
            actions=['emotion'],
            detector_backend='opencv',
            enforce_detection=False, silent=True
        )

    def infer(self, frame_bgr):
        if self.scale != 1.0:
            frame_bgr = cv2.resize(frame_bgr, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)

        res = DeepFace.analyze(
            frame_bgr,
            actions=['emotion'],
            detector_backend=self.detector,
            enforce_detection=False,
            silent=True
        )
        r = res[0] if isinstance(res, list) else res

        has_face = bool(r.get('region'))

        probs_vec = np.array([r['emotion'][k] for k in LABELS], dtype=float) if has_face else (
            self.ema if self.ema is not None else np.zeros(len(LABELS), float)
        )
        self.ema = probs_vec if self.ema is None else self.alpha*probs_vec + (1-self.alpha)*self.ema
        idx = int(np.argmax(self.ema))

        return {
            "dominant": LABELS[idx],
            "conf": float(self.ema[idx]),
            "probs": {k: float(self.ema[i]) for i,k in enumerate(LABELS)},
            "has_face": has_face
        }
