import cv2
import threading, time
from collections import deque

class Camera:
    """Синхронний захват кадру заданого розміру (низька затримка)."""
    def __init__(self, index=0, width=320, height=180, backend=None):
        api = cv2.CAP_AVFOUNDATION if backend is None else backend
        self.cap = cv2.VideoCapture(index, api)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        try:
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        except Exception:
            pass
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cv2.setUseOptimized(True)
        try: cv2.setNumThreads(0)
        except Exception: pass

    def read_small(self):
        for _ in range(2):
            self.cap.grab()
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        if getattr(self, "cap", None):
            self.cap.release()

class AsyncCamera(Camera):
    """Асинхронний захват у фоні з буфером 1 кадр (для плавного UI)."""
    def __init__(self, index=0, width=320, height=180, backend=None):
        super().__init__(index=index, width=width, height=height, backend=backend)
        self._run = True
        self.q = deque(maxlen=1)
        self.th = threading.Thread(target=self._loop, daemon=True)
        self.th.start()

    def _loop(self):
        while self._run:
            f = super().read_small()
            if f is not None:
                self.q.append(f)
            else:
                time.sleep(0.01)

    def latest(self):
        return self.q[-1] if self.q else None

    def stop(self):
        self._alive = False
        try:
            self._t.join(timeout=1.0)
        except Exception:
            pass
        try:
            self.cap.release()
        except Exception:
            pass

