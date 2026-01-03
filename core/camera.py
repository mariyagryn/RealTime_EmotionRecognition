# core/camera.py
from __future__ import annotations
import time
import threading
import cv2
from ui.common import parse_res

class Camera:
    def __init__(self, index: int = 0, resolution: str = "640x360"):
        self.index = int(index)
        try:
            self.cap = cv2.VideoCapture(self.index, cv2.CAP_AVFOUNDATION)
        except Exception:
            self.cap = cv2.VideoCapture(self.index)

        self.set_resolution(resolution)
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
        except Exception:
            pass

    def set_resolution(self, res_str: str) -> None:
        w, h = parse_res(res_str)
        if self.cap:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    def read(self):
        if not self.cap:
            return None
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass

class CaptureThread(threading.Thread):
    def __init__(self, cam: Camera):
        super().__init__(daemon=True)
        self.cam = cam
        self._stop = threading.Event()
        self.last_bgr = None

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            frame = self.cam.read()
            if frame is not None:
                self.last_bgr = frame
            time.sleep(0.003)
