# екран меню
import cv2
from ui.common import draw_transparent_rect, blank_bg
from config import WINDOW_TITLE

MENU_BTNS = [
    ("Start Analysis", "start"),
    ("Statistics",    "stats"),
    ("Settings",      "settings"),
    ("Help",          "help"),
    ("Exit",          "exit"),
]
MENU_RECTS = []
MENU_CHOICE = None

def draw_menu_buttons(img):
    global MENU_RECTS
    MENU_RECTS = []
    h, w = img.shape[:2]
    btn_w, btn_h = 360, 56
    start_y, gap = 170, 18
    for i, (label, key) in enumerate(MENU_BTNS):
        x1 = (w - btn_w)//2; y1 = start_y + i*(btn_h + gap)
        x2, y2 = x1 + btn_w, y1 + btn_h
        draw_transparent_rect(img, (x1, y1), (x2, y2), (40,40,50), 0.7)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.putText(img, label, (x1 + (btn_w - tw)//2, y1 + (btn_h+th)//2 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2, cv2.LINE_AA)
        MENU_RECTS.append((key, x1, y1, x2, y2))

def _menu_hit(x, y):
    for key, x1, y1, x2, y2 in MENU_RECTS:
        if x1 <= x <= x2 and y1 <= y <= y2:
            return key
    return None

def _on_menu_mouse(event, x, y, flags, param):
    global MENU_CHOICE
    if event == cv2.EVENT_LBUTTONUP:
        hit = _menu_hit(x, y)
        if hit: MENU_CHOICE = hit

def show_menu():
    global MENU_CHOICE
    MENU_CHOICE = None
    sub = "The camera will not turn on until you start the analysis."
    bg = blank_bg(title="EMOTION ANALYZER", sub=sub)
    cv2.namedWindow(WINDOW_TITLE)
    cv2.setMouseCallback(WINDOW_TITLE, _on_menu_mouse)
    while True:
        frame = bg.copy()
        draw_menu_buttons(frame)
        cv2.imshow(WINDOW_TITLE, frame)
        key = cv2.waitKey(16) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            return "exit"
        if MENU_CHOICE:
            choice = MENU_CHOICE
            MENU_CHOICE = None
            return choice
