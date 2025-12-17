# ui/live.py
from __future__ import annotations

import os
import time
import threading
import random
import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import messagebox as tk_messagebox
from tkinter import filedialog as tk_filedialog


import customtkinter as ctk
import cv2

# ---------- optional deps ----------
_HAS_REPORTLAB = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas
    _HAS_REPORTLAB = True
except Exception:
    pass

_HAS_PIL = False
try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:
    Image = None
    ImageTk = None

_HAS_DEEPFACE = False
try:
    from deepface import DeepFace
    _HAS_DEEPFACE = True
except Exception:
    pass

_HAS_FER = False
try:
    from fer import FER
    _HAS_FER = True
except Exception:
    pass

def _ui_asset(name: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)

# ---------- settings ----------
def _load_settings_safe() -> dict:
    try:
        from utils.app_settings import load as load_cfg
        return dict(load_cfg() or {})
    except Exception:
        # fallback to settings.json if needed
        try:
            import json
            if os.path.exists("settings.json"):
                with open("settings.json", "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

def _save_settings_safe(cfg: dict) -> None:
    try:
        from utils.app_settings import save as save_cfg
        save_cfg(cfg)
    except Exception:
        try:
            import json
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


_APP_CFG = _load_settings_safe()

# ---------- UI palette ----------
PALETTE = {
    "bg": "#0b1727",
    "panel": "#020617",
    "accent": "#00D1FF",
    "accent_h": "#16E0FF",
    "text": "#E8F1FF",
    "muted": "#94a3b8",
    "border": "#16324a",
}

LABELS = ["happy", "neutral", "sad", "angry", "fear", "surprise", "disgust"]
EMO_COLORS = {
    "happy": "#22c55e",
    "neutral": "#94a3b8",
    "sad": "#60a5fa",
    "angry": "#ef4444",
    "fear": "#a78bfa",
    "surprise": "#f59e0b",
    "disgust": "#10b981",
}

# ---------- assistant copy + mode mapping ----------
EMO_TO_MODE = {
    "neutral": "pomodoro",
    "happy": "speech",
    "sad": "breathing",
    "angry": "mirror",
    "fear": "breathing",
    "surprise": "speech",
    "disgust": "mirror",
}

PRIMARY_LINE_UA = {
    "neutral":  "Ок, рівний стан. Хочеш увімкну Pomodoro 25/5?",
    "happy":    "Супер! Можна взяти складніше завдання, поки є заряд.",
    "sad":      "Ти не зобов’язана тягнути все одразу. Давай 60 секунд дихання?",
    "angry":    "Я поряд. Давай спершу заспокоїмо тіло, потім вирішимо проблему.",
    "fear":     "Ти в безпеці тут. Давай м’яко стабілізуємося й рухнемо далі.",
    "surprise": "Ого, щось різко змінилось. Хочеш швидко зафіксувати думку?",
    "disgust":  "Схоже, щось сильно не заходить. Хочеш зробити паузу?",
}

PRIMARY_LINE_EN = {
    "neutral":  "Steady mode. Want to start a 25/5 Pomodoro?",
    "happy":    "Nice energy. Want to take a harder task while the momentum is here?",
    "sad":      "You don’t have to carry it all. Want a 60-second breathing break?",
    "angry":    "I’m here. Let’s calm the body first, then solve the problem.",
    "fear":     "You’re safe here. Let’s gently stabilize and keep going.",
    "surprise": "Something changed fast. Want to capture a quick note?",
    "disgust":  "Seems like something really doesn’t sit right. Want a short pause?",
}

SUGGESTIONS_UA = {
    "breathing": [
        "Міні-пауза на 60 секунд? Вдих… видих…",
        "Здається, напруга піднялась. Давай 1 хвилину подихаємо.",
        "Зробимо коротке перезавантаження — 60 секунд дихання.",
    ],
    "pomodoro": [
        "Хочеш Pomodoro 25/5? Я допоможу тримати темп.",
        "Стабільний стан — саме час для фокус-сесії 25 хв.",
        "Давай спринт: 25 хв фокус → 5 хв перерва.",
    ],
    "mirror": [
        "Окей, стоп на 20 секунд: плечі вниз, щелепу розслаб.",
        "Мікро-reset: випрям спину й розслаб обличчя.",
        "Знімаємо напругу: довгий видих, а потім повертаємось до задачі.",
    ],
    "speech": [
        "Скажи вголос 1 речення: що ти зараз робиш і що далі.",
        "Швидкий фокус: озвуч одну наступну дію — і робимо її.",
        "30 секунд — сформулюй вголос, що саме треба зробити.",
    ],
}

SUGGESTIONS_EN = {
    "breathing": [
        "Want a 60-second breathing break? Inhale… exhale…",
        "Looks like tension is rising. Let’s breathe for one minute.",
        "Quick reset: 60 seconds of breathing.",
    ],
    "pomodoro": [
        "Want to start a 25/5 Pomodoro? I’ll keep the pace.",
        "Steady state — great time for a 25-minute focus block.",
        "Let’s do it: 25 min focus → 5 min break.",
    ],
    "mirror": [
        "Reset: shoulders down, unclench jaw, long exhale.",
        "Micro reset: posture + relaxed face.",
        "Long exhale first — then we solve it.",
    ],
    "speech": [
        "Say one sentence out loud: what are you doing and what’s next?",
        "Quick focus: state the next action and do it.",
        "30 seconds — verbalize the task clearly.",
    ],
}


# ---------- helpers ----------
def set_ctk_theme() -> None:
    theme = str(_APP_CFG.get("theme", "Dark")).lower()
    mode = "light" if theme.startswith("light") else "dark"
    ctk.set_appearance_mode(mode)
    ctk.set_default_color_theme("dark-blue")

def _ensure_dirs() -> None:
    os.makedirs("sessions/snaps", exist_ok=True)
    os.makedirs("sessions/records", exist_ok=True)
    os.makedirs("sessions/reports", exist_ok=True)

def _parse_res(s: str) -> tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        return 640, 360

def _fmt_mmss(secs: float) -> str:
    s = int(max(0, secs))
    m = s // 60
    ss = s % 60
    return f"{m:02d}:{ss:02d}"

def _fmt_hhmm(secs: float) -> str:
    s = int(max(0, secs))
    minutes = s // 60
    hours = minutes // 60
    minutes %= 60
    return f"{hours}h {minutes:02d}m"

# ---------- OpenCV face detector ----------
CV2_FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# ---------- data ----------
@dataclass
class LiveFlags:
    paused: bool = False
    recording: bool = False

@dataclass
class SessionStats:
    totals: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in LABELS})
    dominant: str = "–"
    last_label: str = "–"

    def add(self, label: str, secs: float) -> None:
        if label in self.totals:
            self.totals[label] += max(0.0, float(secs))

    def recompute_dominant(self) -> None:
        if not self.totals:
            self.dominant = "–"
            return
        self.dominant = max(self.totals.items(), key=lambda kv: kv[1])[0]

# ---------- camera + threads ----------
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
        w, h = _parse_res(res_str)
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

class AnalyzerThread(threading.Thread):
    def __init__(self, analyze_every: float = 0.6):
        super().__init__(daemon=True)
        self.analyze_every = max(0.45, float(analyze_every or 0.6))
        self._stop = threading.Event()
        self._last_bgr = None
        self.current: tuple[str, float] = ("neutral", 0.6)

        self._fer = None
        if _HAS_FER and not _HAS_DEEPFACE:
            try:
                self._fer = FER(mtcnn=False)
            except Exception:
                self._fer = None

    def stop(self):
        self._stop.set()

    def update_frame(self, bgr):
        if bgr is None:
            return
        # shrink frame a bit for speed
        try:
            h, w = bgr.shape[:2]
            if max(h, w) > 380:
                scale = 380.0 / max(h, w)
                bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        except Exception:
            pass
        self._last_bgr = bgr

    def _detect_face_crop(self, bgr):
        if bgr is None:
            return None
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            faces = CV2_FACE.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=3, minSize=(40, 40))
            if len(faces) == 0:
                return bgr
            x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
            pad = int(0.15 * max(w, h))
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(bgr.shape[1], x + w + pad)
            y1 = min(bgr.shape[0], y + h + pad)
            return bgr[y0:y1, x0:x1]
        except Exception:
            return bgr

    def _run_deepface(self, bgr_face):
        try:
            face_small = cv2.resize(bgr_face, (224, 224), interpolation=cv2.INTER_AREA)
            out = DeepFace.analyze(
                face_small,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="skip",
            )
            data = out[0] if isinstance(out, list) else out
            ems = data.get("emotion") or data.get("emotions") or {}

            probs = {}
            if isinstance(ems, dict) and ems:
                for k, v in ems.items():
                    if v is None:
                        continue
                    vv = float(v)
                    if vv > 1.0:
                        vv /= 100.0
                    probs[str(k).lower().strip()] = max(0.0, min(vv, 1.0))

            label, conf = "neutral", 0.6
            if probs:
                label, conf = max(probs.items(), key=lambda kv: kv[1])

            label = (label or "neutral").strip().lower()
            if label not in LABELS:
                label = "neutral"
            conf = float(max(0.0, min(conf, 1.0)))

            # нормалізуємо probs під LABELS
            probs_norm = {k: float(probs.get(k, 0.0)) for k in LABELS}
            return (label, conf, probs_norm)
        except Exception:
            return ("neutral", 0.6, {k: 0.0 for k in LABELS})

    def _run_fer(self, bgr_face):
        try:
            if self._fer is None:
                return ("neutral", 0.6, {k: 0.0 for k in LABELS})
            rgb = cv2.cvtColor(bgr_face, cv2.COLOR_BGR2RGB)
            preds = self._fer.detect_emotions(rgb)
            if not preds:
                return ("neutral", 0.6, {k: 0.0 for k in LABELS})

            em = preds[0]["emotions"]  # вже 0..1
            probs = {str(k).lower(): float(v) for k, v in em.items()}
            label = max(probs.items(), key=lambda kv: kv[1])[0]
            conf = float(probs.get(label, 0.6))
            probs_norm = {k: float(probs.get(k, 0.0)) for k in LABELS}
            return (label, conf, probs_norm)
        except Exception:
            return ("neutral", 0.6, {k: 0.0 for k in LABELS})

    def run(self):
        last = 0.0
        while not self._stop.is_set():
            now = time.time()
            if self._last_bgr is not None and (now - last) >= self.analyze_every:
                face = self._detect_face_crop(self._last_bgr)
                label, conf, probs = ("neutral", 0.6, {k: 0.0 for k in LABELS})

                if _HAS_DEEPFACE:
                    label, conf, probs = self._run_deepface(face)
                    if self._fer is not None and (not probs or conf <= 0.0):
                        label, conf, probs = self._run_fer(face)
                elif self._fer is not None:
                    label, conf, probs = self._run_fer(face)

                self.current = (label, float(conf))
                self.probs = probs
                last = now
            time.sleep(0.01)

# ---------- Timeline ----------
class TimelineWindow(tk.Toplevel):
    def __init__(self, parent: "LiveWindow"):
        super().__init__(parent)
        self.parent = parent
        self.title("Emotion — Timeline")
        self.configure(bg=PALETTE["bg"])
        self.geometry("820x230+80+80")
        self.resizable(True, False)

        self.canvas = tk.Canvas(self, bg=PALETTE["bg"], highlightthickness=0, bd=0, width=780, height=160)
        self.canvas.pack(padx=20, pady=(16, 10), fill="x")

        self.legend = tk.Frame(self, bg=PALETTE["bg"])
        self.legend.pack(padx=20, pady=(0, 16), fill="x")

        for i, lbl in enumerate(LABELS):
            sw = tk.Canvas(self.legend, width=14, height=14, bg=PALETTE["bg"], highlightthickness=0)
            sw.create_rectangle(0, 0, 14, 14, fill=EMO_COLORS[lbl], outline="")
            sw.grid(row=0, column=2 * i, padx=(0, 6))
            lab = tk.Label(self.legend, text=lbl, fg=PALETTE["text"], bg=PALETTE["bg"], font=("Inter", 11))
            lab.grid(row=0, column=2 * i + 1, padx=(0, 12))

        self._alive = True
        self.update_plot()
        self.after(1000, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self._alive = False
        try:
            self.destroy()
        except Exception:
            pass

    def _tick(self):
        if not self._alive:
            return
        self.update_plot()
        self.after(1000, self._tick)

    def update_plot(self):
        data = list(self.parent.timeline)
        W = int(self.canvas.winfo_width() or 780)
        H = int(self.canvas.winfo_height() or 160)
        self.canvas.delete("all")

        if not data:
            self.canvas.create_text(W // 2, H // 2, text="No data yet…", fill=PALETTE["muted"], font=("Inter", 12))
            return

        max_t = max(t for (t, _) in data) if data else 0.0
        px_per_sec = max(1, min(8, int(W / max(1, max_t + 1))))

        for (t, label) in data:
            x = int(t * px_per_sec)
            x = min(W - 1, max(0, x))
            color = EMO_COLORS.get(label, "#475569")
            self.canvas.create_line(x, 0, x, H, fill=color)

# ---------- Mode window ----------
class ModeWindow(ctk.CTkToplevel):
    def __init__(self, parent: "LiveWindow", mode: str, lang: str, headline: str):
        super().__init__(parent)
        self.parent = parent
        self.mode = mode
        self.lang = (lang or "UA").upper()

        self._after_id = None
        self._running = False
        self._remaining = 0
        self._phase = "focus"  # for pomodoro

        self.title(f"Emotion — {mode.capitalize()}")
        self.geometry("430x230+120+120")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["panel"])
        self.attributes("-topmost", True)

        self.grid_columnconfigure(0, weight=1)

        self.lbl_title = ctk.CTkLabel(self, text=mode.capitalize(), font=("Inter", 18, "bold"), text_color=PALETTE["text"])
        self.lbl_title.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self.lbl_headline = ctk.CTkLabel(self, text=headline, font=("Inter", 13), text_color=PALETTE["muted"],
                                         wraplength=390, justify="left")
        self.lbl_headline.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        self.lbl_timer = ctk.CTkLabel(self, text="", font=("Inter", 30, "bold"), text_color=PALETTE["accent"])
        self.lbl_timer.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="w")

        self.btn_row = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_row.grid(row=3, column=0, padx=16, pady=(0, 14), sticky="ew")
        self.btn_row.grid_columnconfigure((0, 1, 2), weight=1)

        self.btn_start = ctk.CTkButton(self.btn_row, text="Start",
                                       fg_color=PALETTE["accent"], hover_color=PALETTE["accent_h"],
                                       text_color="black", command=self.start)
        self.btn_start.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.btn_stop = ctk.CTkButton(self.btn_row, text="Stop",
                                      fg_color="#1f2937", hover_color="#111827",
                                      text_color=PALETTE["text"], command=self.stop)
        self.btn_stop.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        self.btn_close = ctk.CTkButton(self.btn_row, text="Close",
                                       fg_color=PALETTE["panel"], hover_color="#12243a",
                                       border_color=PALETTE["border"], border_width=1,
                                       text_color=PALETTE["text"], command=self._close)
        self.btn_close.grid(row=0, column=2, sticky="ew")

        self._setup_mode_defaults()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _fmt(self, sec: int) -> str:
        sec = max(0, int(sec))
        return f"{sec//60:02d}:{sec%60:02d}"

    def _update_timer_label(self):
        self.lbl_timer.configure(text=self._fmt(self._remaining))

    def _setup_mode_defaults(self):
        if self.mode == "breathing":
            self._remaining = 60
            self._update_timer_label()
            self.btn_start.configure(text="Дихання 60с" if self.lang == "UA" else "Breathing 60s")
            self.btn_close.configure(text="Закрити" if self.lang == "UA" else "Close")

        elif self.mode == "pomodoro":
            self._phase = "focus"
            self._remaining = 25 * 60
            self._update_timer_label()
            self.lbl_title.configure(text=("Помодоро" if self.lang == "UA" else "Pomodoro") + " · Focus")
            self.btn_start.configure(text="Старт 25:00" if self.lang == "UA" else "Start 25:00")
            self.btn_close.configure(text="Закрити" if self.lang == "UA" else "Close")

        elif self.mode == "mirror":
            self._remaining = 30
            self._update_timer_label()
            self.lbl_headline.configure(
                text=("Reset-чеклист:\n• плечі вниз\n• щелепу розслаб\n• довгий видих"
                      if self.lang == "UA" else
                      "Reset checklist:\n• shoulders down\n• unclench jaw\n• long exhale")
            )
            self.btn_start.configure(text="Reset 30с" if self.lang == "UA" else "Reset 30s")
            self.btn_close.configure(text="Закрити" if self.lang == "UA" else "Close")

        elif self.mode == "speech":
            self._remaining = 30
            self._update_timer_label()
            self.lbl_headline.configure(
                text=("Скажи вголос 1 речення: що ти зараз робиш і що далі?"
                      if self.lang == "UA" else
                      "Say one sentence out loud: what are you doing and what’s next?")
            )
            self.btn_start.configure(text="Почати 30с" if self.lang == "UA" else "Go 30s")
            self.btn_close.configure(text="Закрити" if self.lang == "UA" else "Close")

        self.btn_stop.configure(text="Стоп" if self.lang == "UA" else "Stop")

    def start(self):
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self):
        self._running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _beep(self):
        try:
            os.system('osascript -e "beep 1"')
        except Exception:
            pass

    def _tick(self):
        if not self._running:
            return
        self._remaining -= 1
        self._update_timer_label()

        if self._remaining <= 0:
            self._beep()
            if self.mode == "pomodoro":
                # auto switch focus <-> break
                if self._phase == "focus":
                    self._phase = "break"
                    self._remaining = 5 * 60
                    self.lbl_title.configure(text=("Помодоро" if self.lang == "UA" else "Pomodoro") + " · Break")
                else:
                    self._phase = "focus"
                    self._remaining = 25 * 60
                    self.lbl_title.configure(text=("Помодоро" if self.lang == "UA" else "Pomodoro") + " · Focus")
                self._update_timer_label()
                self._after_id = self.after(1000, self._tick)
                return

            self._running = False
            return

        self._after_id = self.after(1000, self._tick)

    def _close(self):
        self.stop()
        try:
            self.destroy()
        except Exception:
            pass


# ---------- main window ----------
class LiveWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        set_ctk_theme()
        _ensure_dirs()

        self.flags = LiveFlags()
        self.stats = SessionStats()

        self._session_started_at = datetime.utcnow().isoformat()
        self._t0 = time.monotonic()
        self._last_tick = time.time()
        self.timeline: list[tuple[float, str]] = []

        self._mode_win: ModeWindow | None = None
        self._last_suggestion_ts = 0.0
        self._streak_label: str | None = None
        self._streak_sec: float = 0.0

        self.title("Emotion — Live")
        self.configure(fg_color=PALETTE["bg"])
        self.geometry("1100x760+40+40")
        self.minsize(900, 600)

        # settings
        self.lang_var = tk.StringVar(value=str(_APP_CFG.get("language", "UA")).upper())
        self.theme_var = tk.StringVar(value=str(_APP_CFG.get("theme", "Dark")).capitalize())

        self.analyze_every = float(_APP_CFG.get("analyze_every", 0.6))
        self.min_conf_for_advice = float(_APP_CFG.get("min_conf_advice", 0.55))  # IMPORTANT
        self.resolution = str(_APP_CFG.get("resolution", "640x360"))
        self.cam_index = int(_APP_CFG.get("camera_index", 0))

        # layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_main()

        # camera / threads
        self.camera = Camera(index=self.cam_index, resolution=self.resolution)
        self.cap_thread = CaptureThread(self.camera)
        self.cap_thread.start()

        self.analyzer = AnalyzerThread(analyze_every=self.analyze_every)
        self.analyzer.start()

        # runtime vars
        self._tkimg = None
        self._img_id = None
        self._writer = None
        self._rec_path = None
        self._fps_hist: list[float] = []
        self._autosized = False

        self.bind("<Escape>", lambda e: self._on_close())
        self.bind("<Command-q>", lambda e: self._on_close())
        self.bind("<space>", lambda e: self._toggle_pause())
        self.bind("s", lambda e: self._snap())
        self.bind("r", lambda e: self._toggle_recording())

        self._current_view = None
        self._switch_view("live")

        self._cam_wait_t0 = time.time()
        self.after(50, self._show_when_camera_ready)

        self._after_id = self.after(30, self._render)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _show_when_camera_ready(self):
        # якщо вже закрили — не робимо нічого
        if not self.winfo_exists():
            return

        frame = getattr(self.cap_thread, "last_bgr", None)

        # показуємо, коли є перший кадр
        if frame is not None:
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception:
                pass
            return

        # safety: щоб не зависнути назавжди, показати через 4 сек навіть без кадру
        if (time.time() - getattr(self, "_cam_wait_t0", time.time())) > 4.0:
            try:
                self.deiconify()
            except Exception:
                pass
            return

        self.after(50, self._show_when_camera_ready)


    # ----- UI building -----
    def _build_header(self):
        self.header = ctk.CTkFrame(self, fg_color="#020617", height=46, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)
        self.header.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(self.header, text="Emotion Analyzer",
                    text_color=PALETTE["text"], font=("Inter", 18, "bold")
                    ).grid(row=0, column=0, padx=20, pady=8, sticky="w")

        nav = ctk.CTkFrame(self.header, fg_color="transparent")
        nav.grid(row=0, column=1, padx=18, pady=6, sticky="e")

        tabs = ctk.CTkFrame(nav, fg_color="transparent")
        tabs.pack(side="left", padx=(0, 14))

        toggles = ctk.CTkFrame(nav, fg_color="transparent")
        toggles.pack(side="right")

        self._nav_buttons: dict[str, ctk.CTkButton] = {}

        def _nav_btn(text: str, view_name: str):
            btn = ctk.CTkButton(
                tabs, text=text, width=90, height=28,
                fg_color="transparent", hover_color="#111827",
                text_color=PALETTE["text"], border_width=0,
                corner_radius=999, font=("Inter", 13),
                command=lambda v=view_name: self._switch_view(v),
            )
            btn.pack(side="left", padx=6)
            self._nav_buttons[view_name] = btn

        _nav_btn("Live", "live")
        _nav_btn("About", "about")
        _nav_btn("Statistics", "stats")

        self.lang_menu = ctk.CTkOptionMenu(
            toggles, values=["UA", "EN"], variable=self.lang_var,
            width=110, height=30,
            fg_color="#0b1625", button_color="#0b1625",
            button_hover_color="#111827", text_color=PALETTE["text"],
            corner_radius=14,
        )
        self.lang_menu.pack(side="left", padx=(0, 16))

        self.theme_switch = ctk.CTkSwitch(
            toggles, text="",
            variable=self.theme_var, onvalue="Dark", offvalue="Light",
            width=52, height=24, switch_width=40, switch_height=20,
            progress_color=PALETTE["accent"],
            command=self._on_theme_change,
        )
        self.theme_switch.pack(side="left")

        self.lang_var.trace_add("write", lambda *_: self._on_lang_change())

    def _build_main(self):
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=1, column=0, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.view_live = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_live.grid_columnconfigure(0, weight=1)
        self.view_live.grid_columnconfigure(1, weight=0)
        self.view_live.grid_rowconfigure(0, weight=1)

        self.view_about = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_stats = ctk.CTkFrame(self.main, fg_color="transparent")

        # live canvas
        self.canvas = tk.Canvas(self.view_live, bg=PALETTE["bg"], highlightthickness=0, bd=0, relief="flat")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        self._fps_lbl = self.canvas.create_text(10, 10, anchor="nw", text="", fill="#9fb3c6",
                                                font=("Inter", 11, "bold"))
        self._emo_lbl = self.canvas.create_text(10, 28, anchor="nw", text="", fill="#E8F1FF",
                                                font=("Inter", 12, "bold"))

        # sidebar
        self.sidebar = ctk.CTkFrame(self.view_live, fg_color=PALETTE["panel"], corner_radius=14)
        self.sidebar.grid(row=0, column=1, sticky="ns", padx=(6, 12), pady=12)
        self.sidebar.grid_rowconfigure(99, weight=1)

        ctk.CTkLabel(self.sidebar, text="Live Controls",
                     text_color=PALETTE["text"], font=("Inter", 16, "bold")
                     ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")

        self.btn_pause = ctk.CTkButton(self.sidebar, text="Pause",
                                       fg_color=PALETTE["accent"], hover_color=PALETTE["accent_h"],
                                       text_color="black", command=self._toggle_pause)
        self.btn_pause.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")

        self.btn_snap = ctk.CTkButton(self.sidebar, text="Snap",
                                      fg_color=PALETTE["panel"], hover_color="#12243a",
                                      border_color=PALETTE["border"], border_width=1,
                                      text_color=PALETTE["text"], command=self._snap)
        self.btn_snap.grid(row=2, column=0, padx=14, pady=8, sticky="ew")

        self._rec_led = ctk.CTkLabel(self.sidebar, text="● Not recording", text_color=PALETTE["muted"])
        self._rec_led.grid(row=3, column=0, padx=14, pady=(6, 6), sticky="w")

        self.btn_rec = ctk.CTkButton(self.sidebar, text="Start Recording",
                                     fg_color=PALETTE["panel"], hover_color="#12243a",
                                     border_color=PALETTE["border"], border_width=1,
                                     text_color=PALETTE["text"], command=self._toggle_recording)
        self.btn_rec.grid(row=4, column=0, padx=14, pady=8, sticky="ew")

        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=PALETTE["border"])
        sep.grid(row=9, column=0, sticky="ew", padx=14, pady=(8, 8))

        ctk.CTkLabel(self.sidebar, text="Session Stats",
                     text_color=PALETTE["text"], font=("Inter", 14, "bold")
                     ).grid(row=10, column=0, padx=14, pady=(0, 4), sticky="w")

        stats_tbl = ctk.CTkFrame(self.sidebar, fg_color=PALETTE["panel"])
        stats_tbl.grid(row=11, column=0, padx=10, pady=(0, 8), sticky="ew")
        stats_tbl.grid_columnconfigure(0, weight=1)
        stats_tbl.grid_columnconfigure(1, weight=0)

        self._lbl_dom = ctk.CTkLabel(stats_tbl, text="Dominant: –", text_color=PALETTE["muted"])
        self._lbl_dom.grid(row=0, column=0, columnspan=2, padx=8, pady=(6, 6), sticky="w")

        self._emo_row_frames = {}
        self._emo_row_dots = {}
        self._row_labels = {}
        self._row_time = {}

        r = 1
        for name in LABELS:
            row = ctk.CTkFrame(stats_tbl, fg_color="transparent", corner_radius=999)
            row.grid(row=r, column=0, columnspan=2, padx=0, pady=3, sticky="ew")

            row.grid_columnconfigure(1, weight=1)

            dot = ctk.CTkFrame(row, width=10, height=10, corner_radius=99, fg_color=EMO_COLORS.get(name, "#64748b"))
            dot.grid(row=0, column=0, padx=(10, 10), pady=6, sticky="w")

            lab = ctk.CTkLabel(row, text=name, text_color=PALETTE["text"], font=("Inter", 13))
            lab.grid(row=0, column=1, sticky="w")

            t = ctk.CTkLabel(row, text="00:00", text_color=PALETTE["muted"], font=("Inter", 12))
            t.grid(row=0, column=2, padx=(10, 10), sticky="e")

            self._emo_row_frames[name] = row
            self._emo_row_dots[name] = dot
            self._row_labels[name] = lab
            self._row_time[name] = t
            r += 1

        self._hint_lbl = ctk.CTkLabel(self.sidebar, text="", text_color="#a7f3d0", wraplength=260, justify="left")
        self._hint_lbl.grid(row=15, column=0, padx=14, pady=(6, 10), sticky="w")

        self.btn_exit = ctk.CTkButton(self.sidebar, text="Exit",
                                      fg_color="#1f2937", hover_color="#111827",
                                      text_color=PALETTE["text"], command=self._on_close)
        self.btn_exit.grid(row=98, column=0, padx=14, pady=(10, 10), sticky="ew")

        self._build_about_view()
        self._build_stats_view()

    def _build_about_view(self):
        self.view_about.grid_columnconfigure(0, weight=1)
        self.view_about.grid_rowconfigure(0, weight=1)

        # ---- фон ----
        self._about_bg_img = None
        if _HAS_PIL:
            try:
                bg_path = _ui_asset("background.jpg")
                if not os.path.exists(bg_path):
                    bg_path = _ui_asset("background.png")

                img = Image.open(bg_path)
                self._about_bg_img = ctk.CTkImage(light_image=img, dark_image=img, size=(1024, 640))
                self._about_bg_label = ctk.CTkLabel(self.view_about, image=self._about_bg_img, text="")
                self._about_bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            except Exception as e:
                print("Cannot load About background:", e)

        # ---- картка ----
        card = ctk.CTkFrame(
            self.view_about,
            fg_color="#020617",
            corner_radius=5,
            border_width=1,
            border_color="#1e40af",
        )
        card.place(relx=0.07, rely=0.18, anchor="nw", relwidth=0.40, relheight=0.60)

        # ---- тексти EN / UA ----
        lang = str(_APP_CFG.get("language", "UA")).upper()
        if lang == "EN":
            title = "What is Emotion Analyzer?"
            intro = (
                "Emotion Analyzer is a desktop assistant that helps you track "
                "your emotional state while studying or working at the computer."
            )
            bullets = [
                "Analyses emotions from your webcam in real time using deep learning models (DeepFace / FER).",
                "Measures how long you stay in each emotion and detects fatigue, stress or long neutral \"zoning out\".",
                "Suggests micro-break modes: Breathing, Pomodoro, Mirror and Speech to unload your mind and eyes.",
                "Saves statistics for every session and builds clear charts so you can see dynamics over time.",
            ]
        else:
            title = "Що таке Emotion Analyzer?"
            intro = (
                "Emotion Analyzer — це настільний асистент, який допомагає "
                "відстежувати твій емоційний стан під час навчання або роботи за компʼютером."
            )
            bullets = [
                "Аналізує емоції з вебкамери в реальному часі за допомогою моделей глибокого навчання (DeepFace / FER).",
                "Вимірює, скільки часу ти перебуваєш у кожній емоції, і помічає моменти втоми, стресу або довгого нейтрального «зависання».",
                "Пропонує режими мікропауз: Breathing, Pomodoro, Mirror та Speech, щоб розвантажити голову й очі.",
                "Зберігає статистику кожної сесії та будує зрозумілі графіки, щоб ти бачив/ла свою емоційну динаміку з часом.",
            ]

        ctk.CTkLabel(
            card,
            text=title,
            font=("Inter", 20, "bold"),
            text_color="#5df0ff",
            anchor="w",
            justify="left",
        ).pack(anchor="w", padx=26, pady=(22, 8))

        ctk.CTkLabel(
            card,
            text=intro,
            font=("Inter", 13),
            text_color=PALETTE["text"],
            justify="left",
            anchor="nw",
            wraplength=390,
        ).pack(anchor="w", padx=26, pady=(0, 14), fill="x")

        # ---- плюс-іконка ----
        self._about_plus_img = None
        if _HAS_PIL:
            try:
                plus_raw = Image.open(_ui_asset("plus.png"))
                self._about_plus_img = ctk.CTkImage(plus_raw, size=(18, 18))
            except Exception as e:
                print("Cannot load plus icon:", e)

        bullets_frame = ctk.CTkFrame(card, fg_color="transparent")
        bullets_frame.pack(anchor="w", padx=20, pady=(0, 20), fill="both", expand=True)

        for text in bullets:
            row = ctk.CTkFrame(bullets_frame, fg_color="transparent")
            row.pack(anchor="w", fill="x", pady=2)

            if self._about_plus_img is not None:
                ctk.CTkLabel(row, image=self._about_plus_img, text="").grid(
                    row=0, column=0, sticky="n", padx=(6, 10), pady=(3, 0)
                )
            else:
                ctk.CTkLabel(row, text="+", font=("Inter", 18, "bold"), text_color="#38bdf8").grid(
                    row=0, column=0, sticky="n", padx=(6, 10), pady=(3, 0)
                )

            ctk.CTkLabel(
                row,
                text=text,
                font=("Inter", 14),
                text_color=PALETTE["text"],
                justify="left",
                anchor="w",
                wraplength=390,
            ).grid(row=0, column=1, sticky="w")

    def _build_stats_view(self):
        for child in self.view_stats.winfo_children():
            child.destroy()

        self.view_stats.grid_columnconfigure(0, weight=1)
        self.view_stats.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(self.view_stats, fg_color=PALETTE["panel"], corner_radius=18)
        card.grid(row=0, column=0, sticky="nsew", padx=32, pady=26)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(0, weight=0)
        card.grid_rowconfigure(1, weight=1)
        card.grid_rowconfigure(2, weight=1)

        lang = self.lang_var.get().upper()
        title_txt = "Session statistics" if lang == "EN" else "Статистика сесій"
        subtitle_txt = (
            "View how much time you spent in each emotion." if lang == "EN"
            else "Подивись, скільки часу ти провів(ла) в кожній емоції."
        )

        header_left = ctk.CTkFrame(card, fg_color="transparent")
        header_left.grid(row=0, column=0, sticky="w", padx=26, pady=(18, 12))

        ctk.CTkLabel(header_left, text=title_txt, font=("Inter", 18, "bold"), text_color=PALETTE["text"]).pack(anchor="w")
        ctk.CTkLabel(header_left, text=subtitle_txt, font=("Inter", 12), text_color=PALETTE["muted"]).pack(anchor="w")

        header_right = ctk.CTkFrame(card, fg_color="transparent")
        header_right.grid(row=0, column=1, sticky="e", padx=26, pady=(18, 12))

        self._stats_summary_lbl = ctk.CTkLabel(header_right, text="", font=("Inter", 12), text_color=PALETTE["muted"])
        self._stats_summary_lbl.grid(row=0, column=0, padx=(0, 18), sticky="e")

        self._stats_period_var = tk.StringVar(value="Today")
        period_menu = ctk.CTkOptionMenu(
            header_right, values=["Today", "Last 7 days", "All time"],
            variable=self._stats_period_var, width=130,
            fg_color="#020617", button_color=PALETTE["accent"],
            button_hover_color=PALETTE["accent_h"], text_color=PALETTE["text"],
            command=lambda _v: self._draw_stats_charts(),
        )
        period_menu.grid(row=0, column=1, sticky="e")

        self._btn_export_pdf = ctk.CTkButton(
            header_right, text=("Export to PDF" if lang == "EN" else "Експортувати в PDF"),
            fg_color=PALETTE["accent"], hover_color=PALETTE["accent_h"],
            text_color="black", height=28, corner_radius=18,
            command=self._export_stats_pdf,
        )
        self._btn_export_pdf.grid(row=1, column=0, columnspan=2, pady=(8, 0), sticky="e")

        self._stats_bar_canvas = tk.Canvas(card, bg=PALETTE["panel"], highlightthickness=0, bd=0, height=170)
        self._stats_bar_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=26, pady=(0, 10))

        self._stats_pie_canvas = tk.Canvas(card, bg=PALETTE["panel"], highlightthickness=0, bd=0, width=340, height=260)
        self._stats_pie_canvas.grid(row=2, column=0, sticky="w", padx=(26, 12), pady=(0, 22))

        self._stats_hbars_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._stats_hbars_frame.grid(row=2, column=1, sticky="nsew", padx=(12, 26), pady=(0, 22))
        self._stats_hbars_frame.grid_columnconfigure(1, weight=1)

        self._stats_pbars = {}
        self._stats_pb_labels = {}

        for i, emo in enumerate(LABELS):
            name_lbl = ctk.CTkLabel(self._stats_hbars_frame, text=emo.capitalize(), font=("Inter", 12), text_color=PALETTE["text"])
            name_lbl.grid(row=i, column=0, padx=(0, 8), pady=4, sticky="w")

            pbar = ctk.CTkProgressBar(
                self._stats_hbars_frame, height=8, fg_color="#020617",
                progress_color=EMO_COLORS.get(emo, PALETTE["accent"]), corner_radius=50
            )
            pbar.grid(row=i, column=1, padx=8, pady=4, sticky="ew")

            val_lbl = ctk.CTkLabel(self._stats_hbars_frame, text="00:00  0%", font=("Inter", 11), text_color=PALETTE["muted"])
            val_lbl.grid(row=i, column=2, padx=(8, 0), pady=4, sticky="e")

            self._stats_pbars[emo] = pbar
            self._stats_pb_labels[emo] = val_lbl

        card.bind("<Configure>", lambda e: self._draw_stats_charts())
        self._draw_stats_charts()

    # ----- language/theme -----
    def _on_theme_change(self):
        theme = self.theme_var.get().lower()
        mode = "light" if theme.startswith("light") else "dark"
        ctk.set_appearance_mode(mode)
        _APP_CFG["theme"] = "Light" if mode == "light" else "Dark"
        _save_settings_safe(dict(_APP_CFG))

    def _on_lang_change(self):
        lang = self.lang_var.get().upper()
        _APP_CFG["language"] = lang
        _save_settings_safe(dict(_APP_CFG))
        self._build_about_view()
        self._build_stats_view()

    # ----- navigation -----
    def _switch_view(self, view: str):
        if view == self._current_view:
            return

        for frame in (self.view_live, self.view_about, self.view_stats):
            frame.grid_forget()

        if view == "live":
            self.view_live.grid(row=0, column=0, sticky="nsew")
        elif view == "about":
            self.view_about.grid(row=0, column=0, sticky="nsew")
        else:
            self.view_stats.grid(row=0, column=0, sticky="nsew")

        self.flags.paused = view != "live"
        self.btn_pause.configure(text="Resume" if self.flags.paused else "Pause")

        for name, btn in self._nav_buttons.items():
            if name == view:
                btn.configure(text_color=PALETTE["accent"], font=("Inter", 13, "bold"))
            else:
                btn.configure(text_color=PALETTE["text"], font=("Inter", 13))

        self._current_view = view

    # ----- controls -----

    def _toggle_pause(self):
        self.flags.paused = not self.flags.paused
        self.btn_pause.configure(text="Resume" if self.flags.paused else "Pause")

    def _snap(self):
        frame = getattr(self, "_last_frame_bgr", None)
        if frame is None:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("sessions", "snaps", f"snap_{ts}.png")
        cv2.imwrite(path, frame)
        self._flash_status(f"Saved snap → {path}")

    def _toggle_recording(self):
        if not self.flags.recording:
            frame = getattr(self, "_last_frame_bgr", None)
            if frame is None:
                w, h = _parse_res(self.resolution)
            else:
                h, w = frame.shape[:2]
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._rec_path = os.path.join("sessions", "records", f"rec_{ts}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(self._rec_path, fourcc, 25.0, (w, h))
            self.flags.recording = True
            self._rec_led.configure(text="● Recording", text_color="#f87171")
            self.btn_rec.configure(text="Stop Recording")
        else:
            self.flags.recording = False
            try:
                if self._writer:
                    self._writer.release()
            except Exception:
                pass
            self._writer = None
            self._rec_led.configure(text="● Not recording", text_color=PALETTE["muted"])
            self.btn_rec.configure(text="Start Recording")
            if self._rec_path:
                self._flash_status(f"Saved video → {self._rec_path}")
            self._rec_path = None

    def _flash_status(self, msg: str):
        self._rec_led.configure(text=f"• {msg}", text_color=PALETTE["muted"])
        self.after(
            1500,
            lambda: self._rec_led.configure(
                text="● Recording" if self.flags.recording else "● Not recording",
                text_color="#f87171" if self.flags.recording else PALETTE["muted"],
            ),
        )

    # ----- suggestions + mode window -----
    def _show_mode(self, mode: str, headline: str):
        lang = self.lang_var.get().upper()
        # show in sidebar
        self._hint_lbl.configure(text=headline)

        # open mode window
        try:
            if self._mode_win is not None and self._mode_win.winfo_exists():
                self._mode_win._close()
        except Exception:
            pass
        self._mode_win = ModeWindow(self, mode=mode, lang=lang, headline=headline)

    def _update_suggestion_logic(self, label: str, conf: float, dt: float):
        # ignore weak confidence to avoid spam
        if conf < self.min_conf_for_advice:
            return

        now = time.monotonic()

        # streak
        if label == self._streak_label:
            self._streak_sec += dt
        else:
            self._streak_label = label
            self._streak_sec = dt

        # cooldown
        COOLDOWN_SEC = float(_APP_CFG.get("advice_cooldown_sec", 90))
        if (now - self._last_suggestion_ts) < COOLDOWN_SEC:
            return

        total_elapsed = now - self._t0

        # thresholds
        need = {
            "sad": 20.0,
            "angry": 15.0,
            "fear": 15.0,
            "happy": 10.0,
            "neutral": 5 * 60.0,
            "surprise": 6.0,
            "disgust": 12.0,
        }.get(label, 20.0)

        if label == "neutral" and total_elapsed < 12 * 60:
            return

        if self._streak_sec < need:
            return

        lang = self.lang_var.get().upper()
        headline = (PRIMARY_LINE_EN if lang == "EN" else PRIMARY_LINE_UA).get(label, "")
        mode = EMO_TO_MODE.get(label)

        if not mode or not headline:
            return

        # make it a bit less repetitive
        pool = (SUGGESTIONS_EN if lang == "EN" else SUGGESTIONS_UA).get(mode, [])
        if pool and random.random() < 0.55:
            headline = random.choice(pool)

        self._last_suggestion_ts = now
        self._streak_sec = 0.0
        self._show_mode(mode, headline)

    # ----- stats + summary.csv -----
    def _update_stats_ui(self):
        for k, lab in self._row_time.items():
            lab.configure(text=_fmt_mmss(self.stats.totals.get(k, 0.0)))

        self._lbl_dom.configure(text=f"Dominant: {self.stats.dominant}")

        cur = self.stats.last_label

        for emo, row in self._emo_row_frames.items():
            active = (emo == cur)
            if active:
                row.configure(
                    fg_color="#0b2236",
                    border_width=2,
                    border_color=EMO_COLORS.get(emo, PALETTE["accent"]),
                    corner_radius=999,
                )
            else:
                row.configure(fg_color="transparent", border_width=0, corner_radius=999)
                self._row_labels[emo].configure(text_color=PALETTE["text"])

    def _write_csv_summary(self):
        try:
            os.makedirs("sessions", exist_ok=True)
            path = os.path.join("sessions", "summary.csv")
            headers = ["started_at", "ended_at", "duration_sec"] + [f"sec_{k}" for k in LABELS] + ["dominant"]

            start = self._session_started_at
            end = datetime.utcnow().isoformat()
            duration = sum(self.stats.totals.values())

            row = [start, end, f"{duration:.2f}"] + [f"{self.stats.totals.get(k, 0.0):.2f}" for k in LABELS] + [self.stats.dominant]

            write_header = not os.path.exists(path)
            with open(path, "a", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if write_header:
                    w.writerow(headers)
                w.writerow(row)
        except Exception as e:
            print("CSV summary write failed:", e)

    def _load_stats_aggregate(self, period: str):
        totals = {k: 0.0 for k in LABELS}
        sessions_count = 0
        total_sec = 0.0

        path = os.path.join("sessions", "summary.csv")
        if not os.path.exists(path):
            return totals, sessions_count, total_sec

        today = datetime.utcnow().date()
        if period == "Today":
            def match_row(dt): return dt.date() == today
        elif period == "Last 7 days":
            start = today - timedelta(days=6)
            def match_row(dt): return dt.date() >= start
        else:
            def match_row(dt): return True

        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        started_at = row.get("started_at")
                        if not started_at:
                            continue
                        dt = datetime.fromisoformat(started_at)
                    except Exception:
                        continue

                    if not match_row(dt):
                        continue

                    sessions_count += 1
                    for emo in LABELS:
                        key = f"sec_{emo}"
                        try:
                            totals[emo] += float(row.get(key, "0") or 0.0)
                        except Exception:
                            pass

            total_sec = sum(totals.values())
        except Exception as e:
            print("Stats aggregate error:", e)

        return totals, sessions_count, total_sec

    def _draw_stats_charts(self):
        if not hasattr(self, "_stats_bar_canvas"):
            return

        period = self._stats_period_var.get()
        totals, sessions_count, total_sec = self._load_stats_aggregate(period)

        lang = self.lang_var.get().upper()
        sessions_word = "Sessions" if lang == "EN" else "Сесій"
        total_time_word = "Total time" if lang == "EN" else "Загальний час"
        self._stats_summary_lbl.configure(text=f"{sessions_word}: {sessions_count}   |   {total_time_word}: {_fmt_hhmm(total_sec)}")

        # empty
        if total_sec <= 0.0:
            for cnv in (self._stats_bar_canvas, self._stats_pie_canvas):
                cnv.delete("all")
                w = int(cnv.winfo_width() or 300)
                h = int(cnv.winfo_height() or 120)
                cnv.create_text(w // 2, h // 2,
                                text=("No data yet…" if lang == "EN" else "Даних поки що немає…"),
                                fill=PALETTE["muted"], font=("Inter", 12))
            for emo in LABELS:
                self._stats_pbars[emo].set(0)
                self._stats_pb_labels[emo].configure(text="00:00  0%")
            return

        # bars
        cnv = self._stats_bar_canvas
        cnv.delete("all")
        W = int(cnv.winfo_width() or 640)
        H = int(cnv.winfo_height() or 170)

        margin_x = 40
        margin_y_top = 15
        margin_y_bottom = 32
        chart_w = W - 2 * margin_x
        chart_h = H - margin_y_top - margin_y_bottom
        max_val = max(totals.values()) or 1.0

        cnv.create_line(margin_x, H - margin_y_bottom, W - margin_x, H - margin_y_bottom, fill="#1f2937", width=1)

        slot_w = chart_w / max(len(LABELS), 1)
        for i, emo in enumerate(LABELS):
            val = totals.get(emo, 0.0)
            ratio = val / max_val if max_val > 0 else 0
            bar_h = chart_h * ratio
            x_center = margin_x + slot_w * (i + 0.5)
            bw = slot_w * 0.5

            x0 = x_center - bw / 2
            x1 = x_center + bw / 2
            y1 = H - margin_y_bottom
            y0 = y1 - bar_h

            cnv.create_rectangle(x0, y0, x1, y1, fill=EMO_COLORS.get(emo, PALETTE["accent"]), outline="")
            cnv.create_text(x_center, H - margin_y_bottom + 14, text=emo.capitalize(), fill=PALETTE["muted"], font=("Inter", 10))

        # pie
        pie = self._stats_pie_canvas
        pie.delete("all")
        PW = int(pie.winfo_width() or 340)
        PH = int(pie.winfo_height() or 260)

        radius = min(PW, PH) * 0.45
        cx = PW / 2
        cy = PH / 2
        x0, y0, x1, y1 = cx - radius, cy - radius, cx + radius, cy + radius

        start_angle = 90.0
        for emo in LABELS:
            val = totals.get(emo, 0.0)
            if val <= 0:
                continue
            extent = 360.0 * (val / total_sec)
            pie.create_arc(x0, y0, x1, y1, start=start_angle, extent=-extent,
                           style="pieslice", outline=PALETTE["panel"], width=1,
                           fill=EMO_COLORS.get(emo, PALETTE["accent"]))
            start_angle -= extent

        for emo in LABELS:
            sec = totals.get(emo, 0.0)
            pct = sec / total_sec if total_sec > 0 else 0.0
            self._stats_pbars[emo].set(pct)
            self._stats_pb_labels[emo].configure(text=f"{_fmt_mmss(sec)}  {int(pct * 100):02d}%")

    def _export_stats_pdf(self):
        period = self._stats_period_var.get()
        totals, sessions_count, total_sec = self._load_stats_aggregate(period)
        lang = self.lang_var.get().upper()

        if total_sec <= 0 or sessions_count == 0:
            tk_messagebox.showinfo(
                "Export",
                "No data for this period." if lang == "EN" else "Немає даних за цей період."
            )
            return

        if not _HAS_REPORTLAB:
            tk_messagebox.showwarning(
                "Export",
                "reportlab is not installed. Run `pip install reportlab`."
                if lang == "EN" else
                "reportlab не встановлено. Запусти `pip install reportlab`."
            )
            return

        # --- user chooses where to save ---
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"emotion_stats_{ts}.pdf"

        save_path = tk_filedialog.asksaveasfilename(
            title=("Save PDF" if lang == "EN" else "Зберегти PDF"),
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf")],
        )
        if not save_path:
            return  # user cancelled

        pdf_path = save_path

        # --- build PDF with charts ---
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas as pdf_canvas

        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics.charts.barcharts import VerticalBarChart
        from reportlab.graphics.charts.piecharts import Pie
        from reportlab.graphics import renderPDF

        c = pdf_canvas.Canvas(pdf_path, pagesize=A4)
        page_w, page_h = A4
        margin = 2 * cm

        # Header
        title = "Emotion Analyzer — Session statistics" if lang == "EN" else "Emotion Analyzer — Статистика сесій"
        c.setFont("Helvetica-Bold", 18)
        y = page_h - margin
        c.drawString(margin, y, title)

        c.setFont("Helvetica", 12)
        y -= 0.9 * cm
        if lang == "EN":
            c.drawString(margin, y, f"Period: {period}")
            y -= 0.65 * cm
            c.drawString(margin, y, f"Sessions: {sessions_count}")
            y -= 0.65 * cm
            c.drawString(margin, y, f"Total time: {_fmt_hhmm(total_sec)}")
        else:
            c.drawString(margin, y, f"Період: {period}")
            y -= 0.65 * cm
            c.drawString(margin, y, f"Сесій: {sessions_count}")
            y -= 0.65 * cm
            c.drawString(margin, y, f"Загальний час: {_fmt_hhmm(total_sec)}")

        y -= 0.6 * cm

        # Use minutes for nicer chart scales
        vals_min = [(float(totals.get(emo, 0.0) or 0.0) / 60.0) for emo in LABELS]
        max_val = max(vals_min) if vals_min else 1.0
        if max_val <= 0:
            max_val = 1.0

        # -------- Bar chart (top) --------
        bar_w = page_w - 2 * margin
        bar_h = 7.5 * cm
        bar_d = Drawing(bar_w, bar_h)

        bc = VerticalBarChart()
        bc.x = 0.8 * cm
        bc.y = 1.2 * cm
        bc.width = bar_w - 1.6 * cm
        bc.height = bar_h - 2.2 * cm
        bc.data = [vals_min]
        bc.categoryAxis.categoryNames = [e.capitalize() for e in LABELS]
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = max_val * 1.10
        bc.valueAxis.valueStep = max(1, int((max_val * 1.10) / 5))

        # Make it look cleaner (closer to your UI)
        bc.valueAxis.labels.fontName = "Helvetica"
        bc.valueAxis.labels.fontSize = 8
        bc.categoryAxis.labels.fontName = "Helvetica"
        bc.categoryAxis.labels.fontSize = 9
        bc.strokeColor = colors.HexColor("#1f2937")
        bc.bars.strokeColor = None

        # per-bar colors
        for i, emo in enumerate(LABELS):
            bc.bars[(0, i)].fillColor = colors.HexColor(EMO_COLORS.get(emo, "#94a3b8"))

        bar_d.add(bc)

        bar_y = y - bar_h
        renderPDF.draw(bar_d, c, margin, bar_y)

        # -------- Pie + legend (bottom) --------
        pie_w = 9.2 * cm
        pie_h = 9.2 * cm
        pie_d = Drawing(pie_w, pie_h)

        pie = Pie()
        pie.x = 0.6 * cm
        pie.y = 0.6 * cm
        pie.width = pie_w - 1.2 * cm
        pie.height = pie_h - 1.2 * cm
        pie.data = vals_min
        pie.labels = [""] * len(LABELS)  # no labels on slices (like your UI)
        pie.sideLabels = False

        for i, emo in enumerate(LABELS):
            pie.slices[i].fillColor = colors.HexColor(EMO_COLORS.get(emo, "#94a3b8"))
            pie.slices[i].strokeColor = colors.white
            pie.slices[i].strokeWidth = 0.3

        pie_d.add(pie)

        bottom_y = bar_y - 0.8 * cm - pie_h
        renderPDF.draw(pie_d, c, margin, bottom_y)

        # Legend/table to the right of pie
        table_x = margin + pie_w + 1.0 * cm
        table_y = bottom_y + pie_h - 0.3 * cm

        c.setFont("Helvetica-Bold", 12)
        c.drawString(table_x, table_y, "Emotion" if lang == "EN" else "Емоція")
        c.drawString(table_x + 6.0 * cm, table_y, "Time" if lang == "EN" else "Час")
        c.drawString(table_x + 9.0 * cm, table_y, "Share" if lang == "EN" else "Частка")

        c.setFont("Helvetica", 12)
        table_y -= 0.7 * cm

        total = total_sec if total_sec > 0 else 1.0
        for emo in LABELS:
            sec = float(totals.get(emo, 0.0) or 0.0)
            pct = int(round((sec / total) * 100)) if total_sec > 0 else 0

            # colored dot/square
            c.setFillColor(colors.HexColor(EMO_COLORS.get(emo, "#94a3b8")))
            c.rect(table_x, table_y - 0.18 * cm, 0.25 * cm, 0.25 * cm, stroke=0, fill=1)

            c.setFillColor(colors.black)
            c.drawString(table_x + 0.4 * cm, table_y, emo.capitalize())
            c.drawString(table_x + 6.0 * cm, table_y, _fmt_mmss(sec))
            c.drawString(table_x + 9.0 * cm, table_y, f"{pct}%")

            table_y -= 0.6 * cm

        c.showPage()
        c.save()

        tk_messagebox.showinfo(
            "Export",
            (f"PDF saved to:\n{pdf_path}" if lang == "EN" else f"PDF збережено:\n{pdf_path}")
        )

    # ----- render loop -----
    def _render(self):
        t0 = time.time()

        if not self.flags.paused:
            frame = getattr(self.cap_thread, "last_bgr", None)
            if frame is not None:
                self._last_frame_bgr = frame
                self.analyzer.update_frame(frame)

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # recording
                if self.flags.recording and self._writer is not None:
                    try:
                        self._writer.write(frame)
                    except Exception:
                        pass

                # show
                try:
                    if _HAS_PIL and Image is not None and ImageTk is not None:
                        img = Image.fromarray(frame_rgb)
                        self._tkimg = ImageTk.PhotoImage(img, master=self.canvas)
                    else:
                        ok, buf = cv2.imencode(".png", frame_rgb)
                        if ok:
                            self._tkimg = tk.PhotoImage(data=buf.tobytes(), master=self.canvas)
                except Exception:
                    self._tkimg = None

                if self._tkimg is not None:
                    if self._img_id is None:
                        self._img_id = self.canvas.create_image(0, 0, image=self._tkimg, anchor="nw")
                    else:
                        self.canvas.itemconfigure(self._img_id, image=self._tkimg)

                for item in (self._fps_lbl, self._emo_lbl):
                    try:
                        self.canvas.tag_raise(item)
                    except Exception:
                        pass

                if not self._autosized:
                    h, w = frame.shape[:2]
                    sidebar_w = max(300, int(self.sidebar.winfo_width() or 300))
                    padding = 40
                    max_w = max(420, self.winfo_width() - sidebar_w - padding)
                    scale = min(1.0, max_w / w)
                    new_w, new_h = int(w * scale), int(h * scale)
                    self.canvas.config(width=new_w, height=new_h)
                    self._autosized = True


        spent = time.time() - t0
        fps = 1.0 / max(1e-6, spent)
        self._fps_hist.append(fps)
        if len(self._fps_hist) > 15:
            self._fps_hist.pop(0)
        avg = sum(self._fps_hist) / max(1, len(self._fps_hist))
        self.canvas.itemconfigure(self._fps_lbl, text=f"{avg:0.1f} FPS")

        label, conf = self.analyzer.current
        now = time.time()
        dt = now - getattr(self, "_last_tick", now)
        self._last_tick = now

        label = (label or "neutral").lower().strip()
        if label not in LABELS:
            label = "neutral"

        # stats
        self.stats.add(label, dt)
        self.stats.last_label = label
        self.stats.recompute_dominant()
        self._update_stats_ui()

        # timeline
        elapsed = time.monotonic() - self._t0
        self.timeline.append((elapsed, label))
        if len(self.timeline) > 8000:
            self.timeline = self.timeline[-8000:]

        self.canvas.itemconfigure(self._emo_lbl, text=f"{label}  {int(conf * 100)}%")
        self._after_id = self.after(33, self._render)

    # ----- close -----
    def _cancel_timer(self):
        try:
            if getattr(self, "_after_id", None) is not None:
                self.after_cancel(self._after_id)
        except Exception:
            pass
        self._after_id = None

    def _on_close(self):
        self._cancel_timer()

        # close mode window
        try:
            if self._mode_win is not None and self._mode_win.winfo_exists():
                self._mode_win._close()
        except Exception:
            pass

        # stop recording
        if self.flags.recording:
            try:
                if self._writer:
                    self._writer.release()
            except Exception:
                pass
        self._writer = None

        # stop threads
        try:
            self.analyzer.stop()
        except Exception:
            pass
        try:
            self.cap_thread.stop()
        except Exception:
            pass

        try:
            self.camera.release()
        except Exception:
            pass

        # write summary
        try:
            self._write_csv_summary()
        except Exception as e:
            print("Cannot write session summary:", e)

        try:
            self.destroy()
        except Exception:
            pass


def run_live():
    app = LiveWindow()
    app.mainloop()
