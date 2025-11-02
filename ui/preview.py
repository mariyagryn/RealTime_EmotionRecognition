# ui/preview.py — простий попередній перегляд камери + FPS
import time, cv2
from utils.app_settings import load as load_settings

WINDOW_TITLE = "Camera Preview"

def _parse_resolution(s: str, fallback=(640, 360)):
    try:
        w, h = map(int, s.lower().split("x"))
        return (w, h)
    except Exception:
        return fallback

def run_preview():
    cfg = load_settings()
    cam_index = int(cfg.get("camera_index", 0))
    w, h = _parse_resolution(cfg.get("resolution", "640x360"))

    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FPS, 30)

    cv2.namedWindow(WINDOW_TITLE)
    fps, t_prev = 0.0, time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        now = time.time()
        dt = now - t_prev; t_prev = now
        if dt > 0: fps = 0.9*fps + 0.1*(1.0/dt)
        cv2.putText(frame, f"{w}x{h}  |  {fps:,.1f} FPS",
                    (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)
        cv2.imshow(WINDOW_TITLE, frame)
        k = cv2.waitKey(1) & 0xFF
        if k in (27, ord('q'), ord('Q')):
            break
    cap.release()
    cv2.destroyWindow(WINDOW_TITLE)
