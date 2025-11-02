# ui/background.py
import cv2
from agent.capture import AsyncCamera

def main():
    cam = AsyncCamera()
    win = "Camera Preview (press q)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    while True:
        ok, frame = cam.read()
        if not ok:
            break
        cv2.imshow(win, frame)
        if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
            break
    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
