# спільні UI-утиліти
import cv2
import numpy as np
from config import NAV_H, NAV_ITEMS

NAV_RECTS = []

def draw_transparent_rect(img, p1, p2, color=(30,30,30), alpha=0.85):
    overlay = img.copy()
    cv2.rectangle(overlay, p1, p2, color, -1)
    cv2.addWeighted(overlay, alpha, img, 1-alpha, 0, img)

def draw_nav(frame, right_edge_x):
    global NAV_RECTS
    NAV_RECTS = []
    draw_transparent_rect(frame, (0,0), (right_edge_x, NAV_H), (30,30,30), 0.9)
    x = 12; y1 = 6
    for name in NAV_ITEMS:
        (tw,_), _ = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
        w = tw + 28; h = NAV_H - 20
        x2 = min(x + w, right_edge_x - 12)
        if x2 <= x: break
        cv2.putText(frame, name, (x+14, y1+h-12), cv2.FONT_HERSHEY_SIMPLEX,
                    0.75, (255,255,255), 2, cv2.LINE_AA)
        NAV_RECTS.append((name, x, y1, x2, y1+h))
        x = x2 + 16

def nav_hit(x, y):
    for name, x1, y1, x2, y2 in NAV_RECTS:
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None

def blank_bg(w=960, h=540, title="EMOTION ANALYZER", sub=""):
    bg = np.zeros((h, w, 3), dtype=np.uint8)
    bg[:] = (20,20,25)
    (tw,_), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)
    cv2.putText(bg, title, ((w-tw)//2, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,255,255), 3, cv2.LINE_AA)
    if sub:
        (sw,_), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.putText(bg, sub, ((w-sw)//2, 115),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2, cv2.LINE_AA)
    return bg
