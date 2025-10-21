# Текстові та аудіо утиліти
import os, cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

def speak(t):
    try: os.system(f'say "{t}" &')
    except Exception: pass

def fmt_s(x: float) -> str:
    m = int(x)//60; s = int(x)%60
    return f"{m:02d}:{s:02d}"

def draw_text_unicode(frame_bgr, text, pos, color=(0,255,255), size=24):
    try:
        font_paths = [
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/SFNS.ttf"
        ]
        fp = next((p for p in font_paths if os.path.exists(p)), None)
        if fp is None: raise RuntimeError("no font")
        img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        draw.text(pos, text, font=ImageFont.truetype(fp, size),
                  fill=(color[2], color[1], color[0]))
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception:
        cv2.putText(frame_bgr, text.encode('ascii','ignore').decode(),
                    pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return frame_bgr
