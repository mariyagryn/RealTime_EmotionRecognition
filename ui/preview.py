# ui/preview.py
import cv2, time
from config import WINDOW_TITLE, CAM_INDEX
from agent.capture import Camera

def run_preview(width=640, height=360):
    cam = Camera(index=CAM_INDEX, width=width, height=height)
    cv2.namedWindow(WINDOW_TITLE)
    fps, t_prev = 0.0, time.time()
    print("[preview] Ultra-smooth mode (no analysis). Press Q/ESC to exit.")

    while True:
        frame = cam.read_small()
        if frame is None:
            time.sleep(0.01); continue

        now = time.time(); dt = now - t_prev; t_prev = now
        if dt > 0: fps = 0.9*fps + 0.1*(1.0/dt)
        cv2.putText(frame, f"Preview {fps:,.1f} FPS", (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2, cv2.LINE_AA)

        cv2.imshow(WINDOW_TITLE, frame)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord('q'), ord('Q'), 27):
            break

    cam.release()
    cv2.destroyWindow(WINDOW_TITLE)
