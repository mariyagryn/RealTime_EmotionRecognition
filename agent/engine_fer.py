# ШВИДКИЙ аналізатор емоцій на базі fer (CPU-friendly).
import cv2, numpy as np
from fer import FER

LABELS = ['angry','disgust','fear','happy','sad','surprise','neutral']

class FastFerAnalyzer:
    def __init__(self, alpha: float = 0.3, mtcnn: bool = False):
        self.det = FER(mtcnn=mtcnn)
        self.alpha = alpha
        self.ema = None

    def infer(self, frame_bgr):

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        faces = self.det.detect_emotions(rgb)
        has_face = bool(faces)
        if has_face:
            face = max(faces, key=lambda f: max(f["emotions"].values()))
            probs_vec = np.array([face["emotions"].get(k, 0.0) for k in LABELS], dtype=float)
        else:
            probs_vec = self.ema if self.ema is not None else np.zeros(len(LABELS), float)

        self.ema = probs_vec if self.ema is None else self.alpha*probs_vec + (1-self.alpha)*self.ema
        idx = int(np.argmax(self.ema))
        return {
            "dominant": LABELS[idx],
            "conf": float(self.ema[idx] * 100.0),
            "probs": {k: float(self.ema[i] * 100.0) for i, k in enumerate(LABELS)},
            "has_face": has_face,
        }
