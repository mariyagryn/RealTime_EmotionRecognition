import cv2
from config import WINDOW_TITLE
from ui.menu import show_menu
from ui.live import run_live
from ui.common import blank_bg
from ui.preview import run_preview
from agent.state import set_paused

def main():
    cv2.namedWindow(WINDOW_TITLE)
    while True:
        choice = show_menu()
        if choice == "start":
            run_live()
        elif choice == "stats":
            img = blank_bg(sub="Statistics: coming soon…")
            cv2.imshow(WINDOW_TITLE, img); cv2.waitKey(900)
        elif choice == "settings":
            img = blank_bg(sub="Settings: camera/detector/privacy — coming soon…")
            cv2.imshow(WINDOW_TITLE, img); cv2.waitKey(900)
        elif choice == "help":
            img = blank_bg(sub="Help: the camera turns on only after 'Start Analysis'")
            cv2.imshow(WINDOW_TITLE, img); cv2.waitKey(900)
        elif choice == "preview":
            run_preview(width=640, height=360)
        elif choice == "preview":
            set_paused(True)
            try:
                run_preview(width=640, height=360)
            finally:
                set_paused(False)
        else:
            break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
import sys
if len(sys.argv) > 1 and "--background" in sys.argv:
    from agent.background import run_background
    run_background(loop_delay=1.0, cam_index=0, width=320, height=180, detector="opencv")
    sys.exit(0)
