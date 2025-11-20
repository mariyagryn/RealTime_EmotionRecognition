# ui/live.py
from __future__ import annotations
import os, time, threading
from dataclasses import dataclass, field
import csv
from datetime import datetime, timedelta
from tkinter import messagebox as tk_messagebox
import customtkinter as ctk
import tkinter as tk
import cv2
from modules import stats
from modules.rules import RuleConfig, RuleState, pick_suggestion

try:
    from utils.app_settings import load as _load_settings, save as _save_settings
    _APP_CFG = _load_settings()
except Exception:
    _APP_CFG = {}

    def _save_settings(cfg: dict):
        pass

_HAS_REPORTLAB = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas
    _HAS_REPORTLAB = True
except Exception:
    pass

_HAS_PIL = False
try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    pass

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

print("BACKENDS:", "deepface=" + str(_HAS_DEEPFACE), "fer=" + str(_HAS_FER))

CV2_FACE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

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

def set_ctk_theme():
    theme = str(_APP_CFG.get("theme", "Dark")).lower()
    mode = "light" if theme.startswith("light") else "dark"
    ctk.set_appearance_mode(mode)
    ctk.set_default_color_theme("dark-blue")

def _ensure_dirs():
    os.makedirs("sessions/snaps", exist_ok=True)
    os.makedirs("sessions/records", exist_ok=True)

def _parse_res(s: str) -> tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        return 480, 270

@dataclass
class LiveFlags:
    paused: bool = False
    recording: bool = False

@dataclass
class SessionStats:
    totals: dict = field(default_factory=lambda: {k: 0.0 for k in LABELS})
    dominant: str = "–"
    last_label: str = "–"

    def add(self, label: str, secs: float):
        if label in self.totals:
            self.totals[label] += max(0.0, secs)

    def recompute_dominant(self):
        if not self.totals:
            self.dominant = "–"
            return
        self.dominant = max(self.totals.items(), key=lambda kv: kv[1])[0]

class Camera:
    def __init__(self, index: int = 0, resolution: str = "480x270"):
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

    def set_resolution(self, res_str: str):
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

    def __init__(self, cam: "Camera"):
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
            time.sleep(0.002)

class AnalyzerThread(threading.Thread):

    def __init__(self, backend: str, analyze_every: float):
        super().__init__(daemon=True)
        self.backend = backend
        self.analyze_every = max(0.45, float(analyze_every or 0.6))
        self._last_bgr = None
        self._stop = threading.Event()
        self.current = ("neutral", 0.6)

        if backend == "fer" and _HAS_FER:
            self._fer = FER(mtcnn=False)
        elif _HAS_FER and not _HAS_DEEPFACE:
            self._fer = FER(mtcnn=False)
        else:
            self._fer = None

    def update_frame(self, bgr):
        try:
            now = time.time()
            if not hasattr(self, "_last_update") or (now - self._last_update) >= 0.25:
                h, w = bgr.shape[:2]
                if max(h, w) > 380:
                    scale = 380.0 / max(h, w)
                    bgr = cv2.resize(
                        bgr,
                        (int(w * scale), int(h * scale)),
                        interpolation=cv2.INTER_AREA,
                    )
                self._last_bgr = bgr
                self._last_update = now
        except Exception:
            self._last_bgr = bgr

    def stop(self):
        self._stop.set()

    def _detect_face_crop(self, bgr):
        if bgr is None:
            return None
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            faces = CV2_FACE.detectMultiScale(
                gray, scaleFactor=1.15, minNeighbors=3, minSize=(40, 40)
            )
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
            face_small = cv2.resize(
                bgr_face, (224, 224), interpolation=cv2.INTER_AREA
            )
            out = DeepFace.analyze(
                face_small,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="skip",
            )
            data = out[0] if isinstance(out, list) else out
            ems = data.get("emotion") or data.get("emotions") or {}
            label, conf = None, 0.0
            if isinstance(ems, dict) and ems:
                ems_norm = {
                    str(k).lower(): float(v) for k, v in ems.items() if v is not None
                }
                if ems_norm:
                    label, conf = max(ems_norm.items(), key=lambda kv: kv[1])
                    if conf > 1.0:
                        conf /= 100.0
            if not label:
                dom = data.get("dominant_emotion")
                if dom:
                    label = str(dom).lower().strip()
                    conf = float(data.get("emotion", {}).get(dom, 0.6))
                    if conf > 1.0:
                        conf /= 100.0
                    if conf <= 0.0:
                        conf = 0.6
            label = (label or "neutral").strip().lower()
            if label not in LABELS:
                label = "neutral"
            if conf <= 0.0:
                conf = 0.6
            return (label, float(max(0.0, min(conf, 1.0))))
        except Exception:
            return ("neutral", 0.6)

    def _run_fer(self, bgr_face):
        try:
            if self._fer is None:
                return ("neutral", 0.6)
            rgb = cv2.cvtColor(bgr_face, cv2.COLOR_BGR2RGB)
            preds = self._fer.detect_emotions(rgb)
            if not preds:
                return ("neutral", 0.6)
            em = preds[0]["emotions"]
            label = max(em.items(), key=lambda kv: kv[1])[0].lower()
            conf = float(em[label])
            return (label, conf)
        except Exception:
            return ("neutral", 0.6)

    def run(self):
        last = 0.0
        while not self._stop.is_set():
            now = time.time()
            if self._last_bgr is not None and (now - last) >= self.analyze_every:
                face = self._detect_face_crop(self._last_bgr)
                label, conf = ("neutral", 0.6)
                if face is not None:
                    if _HAS_DEEPFACE:
                        label, conf = self._run_deepface(face)
                        if conf <= 0.0 and self._fer is not None:
                            label, conf = self._run_fer(face)
                    elif self._fer is not None:
                        label, conf = self._run_fer(face)
                self.current = (label, float(conf))
                last = now
            time.sleep(0.01)

class TimelineWindow(tk.Toplevel):
    def __init__(self, parent: "LiveWindow"):
        super().__init__(parent)
        self.parent = parent
        self.title("Emotion — Timeline")
        self.configure(bg=PALETTE["bg"])
        self.resizable(True, False)
        self.geometry("820x230+80+80")

        self.canvas = tk.Canvas(
            self,
            bg=PALETTE["bg"],
            highlightthickness=0,
            bd=0,
            relief="flat",
            width=780,
            height=160,
        )
        self.canvas.pack(padx=20, pady=(16, 10), fill="x")

        self.legend = tk.Frame(self, bg=PALETTE["bg"])
        self.legend.pack(padx=20, pady=(0, 16), fill="x")
        for i, lbl in enumerate(LABELS):
            sw = tk.Canvas(
                self.legend,
                width=14,
                height=14,
                bg=PALETTE["bg"],
                highlightthickness=0,
            )
            sw.create_rectangle(0, 0, 14, 14, fill=EMO_COLORS[lbl], outline="")
            sw.grid(row=0, column=2 * i, padx=(0, 6))
            lab = tk.Label(
                self.legend,
                text=lbl,
                fg=PALETTE["text"],
                bg=PALETTE["bg"],
                font=("Inter", 11),
            )
            lab.grid(row=0, column=2 * i + 1, padx=(0, 12))

        self.update_plot()

        self._alive = True
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
            self.canvas.create_text(
                W // 2,
                H // 2,
                text="No data yet…",
                fill=PALETTE["muted"],
                font=("Inter", 12),
            )
            return

        max_t = max(t for (t, _) in data) if data else 0.0
        px_per_sec = max(1, min(8, int(W / max(1, max_t + 1))))

        for (t, label) in data:
            x = int(t * px_per_sec)
            x = min(W - 1, max(0, x))
            color = EMO_COLORS.get(label, "#475569")
            self.canvas.create_line(x, 0, x, H, fill=color)

        step = max(10, int((W / px_per_sec) / 8))
        for s in range(0, int(max_t) + 1, step):
            x = int(s * px_per_sec)
            self.canvas.create_line(x, 0, x, H, fill="#0b253d")
            self.canvas.create_text(
                x + 3,
                H - 10,
                text=str(s) + "s",
                anchor="w",
                fill="#5b7a94",
                font=("Inter", 10),
            )

class LiveWindow(ctk.CTk):
    def _write_csv_summary(self):
        try:
            os.makedirs("sessions", exist_ok=True)
            path = os.path.join("sessions", "summary.csv")
            headers = ["started_at", "ended_at", "duration_sec"] + [
                f"sec_{k}" for k in LABELS
            ] + ["dominant"]
            start = self._session_started_at
            end = datetime.utcnow().isoformat()
            duration = sum(self.stats.totals.values())
            row = [start, end, f"{duration:.2f}"] + [
                f"{self.stats.totals.get(k, 0.0):.2f}" for k in LABELS
            ] + [self.stats.dominant]
            write_header = not os.path.exists(path)
            with open(path, "a", encoding="utf-8") as f:
                if write_header:
                    f.write(",".join(headers) + "\n")
                f.write(",".join(map(str, row)) + "\n")
        except Exception as e:
            print("CSV summary write failed:", e)

    def __init__(self):
        super().__init__()
        set_ctk_theme()
        try:
            cv2.setNumThreads(2)
            cv2.useOptimized(True)
        except Exception:
            pass
        _ensure_dirs()
        self._session_started_at = datetime.utcnow().isoformat()

        self.title("Emotion — Live")
        self.configure(fg_color=PALETTE["bg"])

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        win_w = min(1100, max(900, sw - 80))
        win_h = min(770, max(600, sh - 120))
        self.geometry(f"{win_w}x{win_h}+40+40")
        self.minsize(820, 560)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkFrame(self, fg_color="#020617", height=46, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)
        self.header.grid_columnconfigure(1, weight=0)

        title_lbl = ctk.CTkLabel(
            self.header,
            text="Emotion Analyzer",
            text_color=PALETTE["text"],
            font=("Inter", 18, "bold"),
        )
        title_lbl.grid(row=0, column=0, padx=20, pady=8, sticky="w")

        lang_default = str(_APP_CFG.get("language", "UA")).upper()
        theme_default = str(_APP_CFG.get("theme", "Dark")).capitalize()

        self.lang_var = tk.StringVar(
            value="EN" if lang_default == "EN" else "UA"
        )
        self.theme_var = tk.StringVar(
            value="Light" if theme_default.lower().startswith("light") else "Dark"
        )

        nav = ctk.CTkFrame(self.header, fg_color="transparent")
        nav.grid(row=0, column=1, padx=18, pady=6, sticky="e")

        tabs = ctk.CTkFrame(nav, fg_color="transparent")
        tabs.pack(side="left", padx=(0, 14))

        toggles = ctk.CTkFrame(nav, fg_color="transparent")
        toggles.pack(side="right")

        self._nav_buttons: dict[str, ctk.CTkButton] = {}

        def _nav_btn(text: str, view_name: str):
            btn = ctk.CTkButton(
                tabs,
                text=text,
                width=80,
                height=28,
                fg_color="transparent",
                hover_color="#111827",
                text_color=PALETTE["text"],
                border_width=0,
                corner_radius=999,
                font=("Inter", 13),
                command=lambda v=view_name: self._switch_view(v),
            )
            btn.pack(side="left", padx=6)
            self._nav_buttons[view_name] = btn

        _nav_btn("Live", "live")
        _nav_btn("About", "about")
        _nav_btn("Statistics", "stats")
        _nav_btn("Settings", "settings")

        self.lang_menu = ctk.CTkOptionMenu(
            toggles,
            values=["UA", "EN"],
            variable=self.lang_var,
            width=110,
            height=30,
            fg_color="#0b1625",
            button_color="#0b1625",
            button_hover_color="#111827",
            text_color=PALETTE["text"],
            corner_radius=14,
        )
        self.lang_menu.pack(side="left", padx=(0, 16))

        self.theme_switch = ctk.CTkSwitch(
            toggles,
            text="",
            variable=self.theme_var,
            onvalue="Dark",
            offvalue="Light",
            width=52,
            height=24,
            switch_width=40,
            switch_height=20,
            progress_color=PALETTE["accent"],
        )
        self.theme_switch.pack(side="left")

        self.lang_var.trace_add("write", lambda *_: self._on_lang_change())
        self.theme_var.trace_add("write", lambda *_: self._on_theme_change())

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
        self.view_settings = ctk.CTkFrame(self.main, fg_color="transparent")

        self.canvas = tk.Canvas(
            self.view_live,
            bg=PALETTE["bg"],
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        self._fps_lbl = self.canvas.create_text(
            10,
            10,
            anchor="nw",
            text="",
            fill="#9fb3c6",
            font=("Inter", 11, "bold"),
        )
        self._emo_lbl = self.canvas.create_text(
            10,
            28,
            anchor="nw",
            text="",
            fill="#E8F1FF",
            font=("Inter", 12, "bold"),
        )
        self._status_lbl = self.canvas.create_text(
            10,
            46,
            anchor="nw",
            text="",
            fill="#9fb3c6",
            font=("Inter", 11),
        )

        self.sidebar = ctk.CTkFrame(
            self.view_live, fg_color=PALETTE["panel"], corner_radius=14
        )
        self.sidebar.grid(row=0, column=1, sticky="ns", padx=(6, 12), pady=12)
        for i in range(50):
            self.sidebar.grid_rowconfigure(i, weight=0)
        self.sidebar.grid_rowconfigure(99, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="Live Controls",
            text_color=PALETTE["text"],
            font=("Inter", 16, "bold"),
        ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")

        self.btn_pause = ctk.CTkButton(
            self.sidebar,
            text="Pause",
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_h"],
            text_color="black",
            command=self._toggle_pause,
        )
        self.btn_pause.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")

        self.btn_snap = ctk.CTkButton(
            self.sidebar,
            text="Snap",
            fg_color=PALETTE["panel"],
            hover_color="#12243a",
            border_color=PALETTE["border"],
            border_width=1,
            text_color=PALETTE["text"],
            command=self._snap,
        )
        self.btn_snap.grid(row=2, column=0, padx=14, pady=8, sticky="ew")

        self._rec_led = ctk.CTkLabel(
            self.sidebar, text="● Not recording", text_color=PALETTE["muted"]
        )
        self._rec_led.grid(row=3, column=0, padx=14, pady=(6, 6), sticky="w")

        self.btn_rec = ctk.CTkButton(
            self.sidebar,
            text="Start Recording",
            fg_color=PALETTE["panel"],
            hover_color="#12243a",
            border_color=PALETTE["border"],
            border_width=1,
            text_color=PALETTE["text"],
            command=self._toggle_recording,
        )
        self.btn_rec.grid(row=4, column=0, padx=14, pady=8, sticky="ew")

        self.btn_timeline = ctk.CTkButton(
            self.sidebar,
            text="Open Timeline",
            fg_color="#0d253c",
            hover_color="#0f2d49",
            text_color=PALETTE["text"],
            command=self._open_timeline,
        )
        self.btn_timeline.grid(row=5, column=0, padx=14, pady=(2, 8), sticky="ew")

        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=PALETTE["border"])
        sep.grid(row=9, column=0, sticky="ew", padx=14, pady=(8, 8))

        ctk.CTkLabel(
            self.sidebar,
            text="Session Stats",
            text_color=PALETTE["text"],
            font=("Inter", 14, "bold"),
        ).grid(row=10, column=0, padx=14, pady=(0, 4), sticky="w")

        stats_tbl = ctk.CTkFrame(self.sidebar, fg_color=PALETTE["panel"])
        stats_tbl.grid(row=11, column=0, padx=10, pady=(0, 8), sticky="ew")
        stats_tbl.grid_columnconfigure(0, weight=1)
        stats_tbl.grid_columnconfigure(1, weight=0)

        self._lbl_dom = ctk.CTkLabel(
            stats_tbl, text="Dominant: –", text_color=PALETTE["muted"]
        )
        self._lbl_dom.grid(
            row=0, column=0, columnspan=2, padx=8, pady=(6, 6), sticky="w"
        )

        self._row_labels: dict[str, ctk.CTkLabel] = {}
        self._row_time: dict[str, ctk.CTkLabel] = {}
        r = 1
        for name in LABELS:
            lab = ctk.CTkLabel(stats_tbl, text=name, text_color=PALETTE["text"])
            lab.grid(row=r, column=0, padx=8, pady=2, sticky="w")
            t = ctk.CTkLabel(stats_tbl, text="00:00", text_color=PALETTE["muted"])
            t.grid(row=r, column=1, padx=8, pady=2, sticky="e")
            self._row_labels[name] = lab
            self._row_time[name] = t
            r += 1

        self._hint_lbl = ctk.CTkLabel(self.sidebar, text="", text_color="#a7f3d0")
        self._hint_lbl.grid(row=15, column=0, padx=14, pady=(0, 8), sticky="w")

        self.btn_exit = ctk.CTkButton(
            self.sidebar,
            text="Exit",
            fg_color="#1f2937",
            hover_color="#111827",
            text_color=PALETTE["text"],
            command=self._on_close,
        )
        self.btn_exit.grid(row=98, column=0, padx=14, pady=(10, 10), sticky="ew")

        self._about_bg_img = None
        self._build_about_view()
        self._build_stats_view()
        self._build_settings_view()

        self.flags = LiveFlags()
        self.stats = SessionStats()
        self._after_id: str | None = None
        self._last_tick = time.time()
        self.timeline: list[tuple[float, str]] = []
        self._t0 = time.monotonic()

        default_res = str(_APP_CFG.get("resolution", "640x360"))
        if "x" not in default_res:
            default_res = "640x360"
        default_backend = "deepface" if _HAS_DEEPFACE else ("fer" if _HAS_FER else "dummy")
        cam_index = int(_APP_CFG.get("camera_index", 0))
        self.analyze_every = float(_APP_CFG.get("analyze_every", 0.5))
        self.min_conf = float(_APP_CFG.get("min_conf", 0.05))
        self.resolution = default_res
        self.backend = default_backend
        self.cam_index = cam_index

        self._tkimg = None
        self._img_id = None
        self._writer = None
        self._rec_path = None
        self._fps_hist: list[float] = []
        self._autosized = False

        self.camera = Camera(index=self.cam_index, resolution=self.resolution)
        self.cap_thread = CaptureThread(self.camera)
        self.cap_thread.start()

        self.analyzer = AnalyzerThread(self.backend, self.analyze_every)
        self.analyzer.start()

        self.rules_cfg = RuleConfig(
            sad_sec=int(_APP_CFG.get("rule_sad_sec", 60)),
            angry_sec=int(_APP_CFG.get("rule_angry_sec", 30)),
            neutral_sec=int(_APP_CFG.get("rule_neutral_sec", 120)),
            noface_pct=int(_APP_CFG.get("rule_noface_pct", 40)),
            cooldown_min=int(_APP_CFG.get("rule_cooldown_min", 30)),
            enable_breathing=bool(_APP_CFG.get("rule_breathing", True)),
            enable_pomodoro=bool(_APP_CFG.get("rule_pomodoro", True)),
            enable_mirror=bool(_APP_CFG.get("rule_mirror", True)),
            enable_speech=bool(_APP_CFG.get("rule_speech", True)),
        )
        self.rules_state = RuleState()
        self._emotion_acc = {k: 0.0 for k in LABELS}

        self.bind("<Escape>", lambda e: self._on_close())
        self.bind("<Command-q>", lambda e: self._on_close())
        self.bind("<space>", lambda e: self._toggle_pause())
        self.bind("s", lambda e: self._snap())
        self.bind("r", lambda e: self._toggle_recording())

        self._current_view = None
        self._switch_view("live")

        self._after_id = self.after(20, self._render)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_about_view(self):
        self.view_about.grid_columnconfigure(0, weight=1)
        self.view_about.grid_rowconfigure(0, weight=1)

        if _HAS_PIL:
            try:
                img = Image.open("ui/assets/background.jpg")
                self._about_bg_img = ctk.CTkImage(
                    light_image=img, dark_image=img, size=(1024, 640)
                )
                bg_label = ctk.CTkLabel(
                    self.view_about, image=self._about_bg_img, text=""
                )
                bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            except Exception as e:
                print("Cannot load About background:", e)

        card = ctk.CTkFrame(
            self.view_about,
            fg_color="#020617",
            corner_radius=18,
        )
        card.place(relx=0.07, rely=0.20, anchor="nw", relwidth=0.38, relheight=0.68)

        lang = str(_APP_CFG.get("language", "UA")).upper()
        if lang == "EN":
            title = "What is Emotion Analyzer?"
            body = (
                "Emotion Analyzer is a desktop assistant that helps you keep track of\n"
                "your emotional state while studying or working at the computer.\n\n"
                "• Captures your face from the webcam in real time.\n"
                "• Uses a deep learning model (DeepFace) to recognise seven basic\n"
                "  emotions: happy, neutral, sad, angry, fear, surprise, disgust.\n"
                "• Measures how long you stay in each emotional state during a session.\n"
                "• Detects patterns that may signal fatigue, stress or loss of focus.\n"
                "• Suggests short micro-breaks (breathing, Pomodoro, mirror, speech\n"
                "  tasks) so you feel less exhausted during study and work.\n"
                "• Saves anonymised statistics of every session so you can review your\n"
                "  emotional dynamics over time."
            )
        else:
            title = "Що таке Emotion Analyzer?"
            body = (
                "Emotion Analyzer — це настільний асистент, який допомагає відстежувати\n"
                "твій емоційний стан під час навчання або роботи за комп'ютером.\n\n"
                "• Захоплює обличчя з вебкамери в реальному часі.\n"
                "• Використовує модель глибокого навчання (DeepFace) для розпізнавання\n"
                "  семи базових емоцій: радість, нейтральний стан, смуток, злість,\n"
                "  страх, здивування, відраза.\n"
                "• Рахує, скільки часу ти перебуваєш у кожному емоційному стані.\n"
                "• Виявляє патерни, що можуть свідчити про втому, стрес або втрату\n"
                "  концентрації.\n"
                "• Пропонує короткі мікропаузи (breathing, Pomodoro, mirror, speech),\n"
                "  щоб зменшити відчуття емоційного вигорання.\n"
                "• Зберігає анонімну статистику кожної сесії, щоб ти міг/могла\n"
                "  переглядати свої емоційні зміни в часі."
            )

        ctk.CTkLabel(
            card, text=title, font=("Inter", 18, "bold"), text_color=PALETTE["text"]
        ).pack(anchor="w", padx=24, pady=(20, 12))

        body_label = ctk.CTkLabel(
            card,
            text=body,
            font=("Inter", 12),
            text_color=PALETTE["muted"],
            justify="left",
            anchor="nw",
            wraplength=420,
        )
        body_label.pack(anchor="w", padx=24, pady=(0, 22), fill="both", expand=False)

    def _build_stats_view(self):
        self.view_stats.grid_columnconfigure(0, weight=1)
        self.view_stats.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(
            self.view_stats,
            fg_color=PALETTE["panel"],
            corner_radius=18,
        )
        card.grid(row=0, column=0, sticky="nsew", padx=32, pady=26)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(0, weight=0)
        card.grid_rowconfigure(1, weight=1)
        card.grid_rowconfigure(2, weight=1)

        lang = str(_APP_CFG.get("language", "UA")).upper()
        if lang == "EN":
            title_txt = "Session statistics"
            subtitle_txt = (
                "View how much time you spent in each emotion.\n"
                "Choose a period and see the distribution for your recent sessions."
            )
            period_label_txt = "Period"
            sessions_word = "Sessions"
            total_time_word = "Total time"
        else:
            title_txt = "Статистика сесій"
            subtitle_txt = (
                "Подивись, скільки часу ти провів(ла) в кожній емоції.\n"
                "Обери період і переглянь розподіл для останніх сесій."
            )
            period_label_txt = "Період"
            sessions_word = "Сесій"
            total_time_word = "Загальний час"

        header_left = ctk.CTkFrame(card, fg_color="transparent")
        header_left.grid(row=0, column=0, sticky="w", padx=26, pady=(18, 12))

        ctk.CTkLabel(
            header_left,
            text=title_txt,
            font=("Inter", 18, "bold"),
            text_color=PALETTE["text"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_left,
            text=subtitle_txt,
            font=("Inter", 12),
            text_color=PALETTE["muted"],
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        header_right = ctk.CTkFrame(card, fg_color="transparent")
        header_right.grid(row=0, column=1, sticky="e", padx=26, pady=(18, 12))

        self._stats_summary_lbl = ctk.CTkLabel(
            header_right,
            text=f"{sessions_word}: 0   |   {total_time_word}: 0h 00m",
            font=("Inter", 12),
            text_color=PALETTE["muted"],
        )
        self._stats_summary_lbl.grid(row=0, column=0, padx=(0, 18), pady=(0, 0), sticky="e")

        if not hasattr(self, "_stats_period_var"):
            self._stats_period_var = tk.StringVar(value="Today")

        period_box = ctk.CTkFrame(header_right, fg_color="transparent")
        period_box.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            period_box,
            text=period_label_txt,
            font=("Inter", 11),
            text_color=PALETTE["muted"],
        ).pack(side="left", padx=(0, 6))

        period_menu = ctk.CTkOptionMenu(
            period_box,
            values=["Today", "Last 7 days", "All time"],
            variable=self._stats_period_var,
            width=120,
            fg_color="#020617",
            button_color=PALETTE["accent"],
            button_hover_color=PALETTE["accent_h"],
            text_color=PALETTE["text"],
            command=lambda _v: self._draw_stats_charts(),
        )
        period_menu.pack(side="left")
        export_text = "Export to PDF" if lang == "EN" else "Експортувати в PDF"

        self._btn_export_pdf = ctk.CTkButton(
            header_right,
            text=export_text,
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_h"],
            text_color="black",
            height=28,
            corner_radius=18,
            command=self._export_stats_pdf,
        )
        self._btn_export_pdf.grid(
            row=1, column=0, columnspan=2,
            padx=(0, 0), pady=(8, 0), sticky="e"
        )

        self._stats_bar_canvas = tk.Canvas(
            card,
            bg=PALETTE["panel"],
            highlightthickness=0,
            bd=0,
            relief="flat",
            height=170,
        )
        self._stats_bar_canvas.grid(
            row=1, column=0, columnspan=2,
            sticky="nsew", padx=26, pady=(0, 10)
        )

        self._stats_pie_canvas = tk.Canvas(
            card,
            bg=PALETTE["panel"],
            highlightthickness=0,
            bd=0,
            relief="flat",
            width=340,
            height=260,
        )
        self._stats_pie_canvas.grid(
            row=2, column=0,
            sticky="w", padx=(26, 12), pady=(0, 22)
        )

        self._stats_hbars_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._stats_hbars_frame.grid(
            row=2, column=1,
            sticky="nsew", padx=(12, 26), pady=(0, 22)
        )
        self._stats_hbars_frame.grid_columnconfigure(0, weight=0)  # назва
        self._stats_hbars_frame.grid_columnconfigure(1, weight=1)  # progress bar
        self._stats_hbars_frame.grid_columnconfigure(2, weight=0)  # час+%

        self._stats_pbars = {}
        self._stats_pb_labels = {}

        row_i = 0
        for emo in LABELS:
            color_box = tk.Canvas(
                self._stats_hbars_frame,
                width=10,
                height=10,
                bg=PALETTE["panel"],
                highlightthickness=0,
                bd=0,
            )
            color_box.create_rectangle(
                0, 0, 10, 10,
                fill=EMO_COLORS.get(emo, "#64748b"),
                outline="",
            )
            color_box.grid(row=row_i, column=0, padx=(0, 8), pady=4, sticky="w")

            name_lbl = ctk.CTkLabel(
                self._stats_hbars_frame,
                text=emo.capitalize(),
                font=("Inter", 12),
                text_color=PALETTE["text"],
            )
            name_lbl.grid(row=row_i, column=0, padx=(20, 8), pady=4, sticky="w")

            pbar = ctk.CTkProgressBar(
                self._stats_hbars_frame,
                height=8,
                fg_color="#020617",
                progress_color=EMO_COLORS.get(emo, PALETTE["accent"]),
                corner_radius=50,
            )
            pbar.grid(row=row_i, column=1, padx=8, pady=4, sticky="ew")

            val_lbl = ctk.CTkLabel(
                self._stats_hbars_frame,
                text="00:00  0%",
                font=("Inter", 11),
                text_color=PALETTE["muted"],
            )
            val_lbl.grid(row=row_i, column=2, padx=(8, 0), pady=4, sticky="e")

            self._stats_pbars[emo] = pbar
            self._stats_pb_labels[emo] = val_lbl
            row_i += 1

        card.bind("<Configure>", lambda e: self._draw_stats_charts())

        self._draw_stats_charts()
    def _load_stats_aggregate(self, period: str):
        import csv
        from datetime import datetime, timedelta

        totals = {k: 0.0 for k in LABELS}
        sessions_count = 0
        total_sec = 0.0

        path = os.path.join("sessions", "summary.csv")
        if not os.path.exists(path):
            return totals, sessions_count, total_sec

        today = datetime.utcnow().date()

        if period == "Today":
            def match_row(dt):
                return dt.date() == today
        elif period == "Last 7 days":
            start = today - timedelta(days=6)
            def match_row(dt):
                return dt.date() >= start
        else:
            def match_row(dt):
                return True

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
                            val = float(row.get(key, "0") or 0)
                        except Exception:
                            val = 0.0
                        totals[emo] += val

            total_sec = sum(totals.values())
        except Exception as e:
            print("Stats aggregate error:", e)

        return totals, sessions_count, total_sec

    def _draw_stats_charts(self):

        if not hasattr(self, "_stats_bar_canvas"):
            return

        period = getattr(self, "_stats_period_var", tk.StringVar(value="All time")).get()
        totals, sessions_count, total_sec = self._load_stats_aggregate(period)

        lang = str(_APP_CFG.get("language", "UA")).upper()
        if lang == "EN":
            sessions_word = "Sessions"
            total_time_word = "Total time"
        else:
            sessions_word = "Сесій"
            total_time_word = "Загальний час"

        if self._stats_summary_lbl is not None:
            self._stats_summary_lbl.configure(
                text=f"{sessions_word}: {sessions_count}   |   "
                     f"{total_time_word}: {self._fmt_hhmm(total_sec)}"
            )

        if total_sec <= 0.0:
            for cnv in (self._stats_bar_canvas, self._stats_pie_canvas):
                cnv.delete("all")
                w = int(cnv.winfo_width() or 300)
                h = int(cnv.winfo_height() or 120)
                cnv.create_text(
                    w // 2,
                    h // 2,
                    text="No data yet…" if lang == "EN" else "Даних поки що немає…",
                    fill=PALETTE["muted"],
                    font=("Inter", 12),
                )

            for emo in LABELS:
                if emo in self._stats_pbars:
                    self._stats_pbars[emo].set(0)
                if emo in self._stats_pb_labels:
                    self._stats_pb_labels[emo].configure(text="00:00  0%")
            return


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

        cnv.create_line(
            margin_x, H - margin_y_bottom,
            W - margin_x, H - margin_y_bottom,
            fill="#1f2937", width=1
        )

        bar_count = len(LABELS)
        slot_w = chart_w / max(bar_count, 1)

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

            cnv.create_rectangle(
                x0, y0, x1, y1,
                fill=EMO_COLORS.get(emo, PALETTE["accent"]),
                outline="",
            )
            cnv.create_text(
                x_center,
                H - margin_y_bottom + 14,
                text=emo.capitalize(),
                fill=PALETTE["muted"],
                font=("Inter", 10),
            )

        pie = self._stats_pie_canvas
        pie.delete("all")
        PW = int(pie.winfo_width() or 340)
        PH = int(pie.winfo_height() or 260)

        radius = min(PW, PH) * 0.45

        cx = PW / 2
        cy = PH / 2
        x0 = cx - radius
        y0 = cy - radius
        x1 = cx + radius
        y1 = cy + radius

        start_angle = 90.0
        for emo in LABELS:
            val = totals.get(emo, 0.0)
            if val <= 0:
                continue
            extent = 360.0 * (val / total_sec)
            pie.create_arc(
                x0, y0, x1, y1,
                start=start_angle,
                extent=-extent,
                style="pieslice",
                outline=PALETTE["panel"],
                width=1,
                fill=EMO_COLORS.get(emo, PALETTE["accent"]),
            )
            start_angle -= extent

        pie.create_oval(
            x0, y0, x1, y1,
            outline="#020617",
            width=2,
        )

        for emo in LABELS:
            sec = totals.get(emo, 0.0)
            pct = sec / total_sec if total_sec > 0 else 0.0
            if emo in self._stats_pbars:
                self._stats_pbars[emo].set(pct)
            if emo in self._stats_pb_labels:
                self._stats_pb_labels[emo].configure(
                    text=f"{self._fmt_mmss(sec)}  {int(pct * 100):02d}%"
                )

    def _fmt_hhmm(self, secs: float) -> str:
        s = int(max(0, secs))
        minutes = s // 60
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}h {minutes:02d}m"

    def _export_stats_pdf(self):
        period = getattr(self, "_stats_period_var", tk.StringVar(value="Today")).get()
        totals, sessions_count, total_sec = self._load_stats_aggregate(period)

        if total_sec <= 0 or sessions_count == 0:
            msg = "No data for this period." if self.lang_var.get().upper() == "EN" else "Немає даних за цей період."
            tk_messagebox.showinfo("Export", msg)
            return

        if not _HAS_REPORTLAB:
            msg = (
                "reportlab is not installed. Run `pip install reportlab`."
                if self.lang_var.get().upper() == "EN"
                else "Бібліотека reportlab не встановлена. Запустіть `pip install reportlab`."
            )
            tk_messagebox.showwarning("Export", msg)
            return

        os.makedirs(os.path.join("sessions", "reports"), exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join("sessions", "reports", f"emotion_stats_{ts}.pdf")

        c = pdf_canvas.Canvas(pdf_path, pagesize=A4)
        page_w, page_h = A4

        lang = str(_APP_CFG.get("language", "UA")).upper()

        title = (
            "Emotion Analyzer — Session statistics"
            if lang == "EN"
            else "Emotion Analyzer — Статистика сесій"
        )
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, page_h - 60, title)

        c.setFont("Helvetica", 11)
        if lang == "EN":
            c.drawString(40, page_h - 80, f"Period: {period}")
            c.drawString(40, page_h - 95, f"Sessions: {sessions_count}")
            c.drawString(40, page_h - 110, f"Total time: {self._fmt_hhmm(total_sec)}")
        else:
            c.drawString(40, page_h - 80, f"Період: {period}")
            c.drawString(40, page_h - 95, f"Сесій: {sessions_count}")
            c.drawString(40, page_h - 110, f"Загальний час: {self._fmt_hhmm(total_sec)}")

        y = page_h - 140
        c.setFont("Helvetica-Bold", 12)
        if lang == "EN":
            c.drawString(40, y, "Emotion")
            c.drawString(180, y, "Time")
            c.drawString(250, y, "Share")
        else:
            c.drawString(40, y, "Емоція")
            c.drawString(180, y, "Час")
            c.drawString(250, y, "Частка")

        y -= 18
        c.setFont("Helvetica", 11)

        total = total_sec if total_sec > 0 else 1.0

        for emo in LABELS:
            sec = float(totals.get(emo, 0.0) or 0.0)
            pct = int(round(sec / total * 100)) if total_sec > 0 else 0

            c.drawString(40, y, emo.capitalize())
            c.drawString(180, y, self._fmt_mmss(sec))
            c.drawString(250, y, f"{pct}%")

            bar_max = 180.0
            bar_w = bar_max * (sec / total)
            c.setFillColorRGB(0.0, 0.82, 1.0)
            c.rect(320, y - 4, bar_w, 6, fill=1, stroke=0)
            c.setFillColorRGB(0, 0, 0)

            y -= 16
            if y < 80:
                c.showPage()
                y = page_h - 60
                c.setFont("Helvetica", 11)

        c.showPage()
        c.save()

        msg_ok = (
            f"PDF saved to: {pdf_path}"
            if lang == "EN"
            else f"PDF збережено у файлі:\n{pdf_path}"
        )
        tk_messagebox.showinfo("Export", msg_ok)

    def _stats_period_changed(self, *_):
        key = self._stats_period_map.get(self._stats_period_var.get(), "today")
        self._stats_load_data(key)
        self._stats_draw()

    def _stats_load_data(self, key: str):

        totals = {k: 0.0 for k in LABELS}
        sessions = 0
        total_time = 0.0

        path = os.path.join("sessions", "summary.csv")
        if os.path.exists(path):
            now = datetime.utcnow()
            if key == "today":
                start_limit = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif key == "7d":
                start_limit = now - timedelta(days=7)
            elif key == "30d":
                start_limit = now - timedelta(days=30)
            else:
                start_limit = None

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        started = datetime.fromisoformat(row.get("started_at", ""))
                    except Exception:
                        started = None

                    if start_limit is not None and started is not None:
                        if started < start_limit:
                            continue

                    sessions += 1
                    try:
                        total_time += float(row.get("duration_sec", "0") or 0.0)
                    except Exception:
                        pass

                    for name in LABELS:
                        col = f"sec_{name}"
                        try:
                            totals[name] += float(row.get(col, "0") or 0.0)
                        except Exception:
                            pass

        self._stats_totals = totals
        self._stats_sessions = sessions
        self._stats_total_time = total_time

    def _stats_draw(self):

        tt = self._stats_total_time
        h = int(tt // 3600)
        m = int((tt % 3600) // 60)

        lang = "EN"
        try:
            lang = self.lang_var.get().upper()
        except Exception:
            lang = str(_APP_CFG.get("language", "UA")).upper()

        if lang == "EN":
            txt_summary = f"Sessions: {self._stats_sessions}  |  Total time: {h}h {m}m"
            txt_no = "No data for this period"
        else:
            txt_summary = f"Сесій: {self._stats_sessions}  |  Загальний час: {h} год {m} хв"
            txt_no = "Немає даних за цей період"

        self._stats_summary_lbl.configure(text=txt_summary)

        total_secs = sum(self._stats_totals.values())

        c = self._stats_bar_canvas
        c.delete("all")
        w = int(c.winfo_width() or 520)
        h_bar = int(c.winfo_height() or 130)

        if total_secs <= 0 or self._stats_sessions == 0:
            c.create_text(
                w // 2,
                h_bar // 2,
                text=txt_no,
                fill=PALETTE["muted"],
                font=("Inter", 12),
            )
        else:
            max_val = max(self._stats_totals.values()) or 1.0
            left_margin = 24
            right_margin = 24
            bottom = h_bar - 26
            top = 18
            area_w = w - left_margin - right_margin
            n = len(LABELS)
            bar_w = max(12, int(area_w / (n * 1.7)))
            gap = bar_w * 0.7

            for i, name in enumerate(LABELS):
                val = self._stats_totals.get(name, 0.0)
                ratio = val / max_val if max_val > 0 else 0.0
                bh = int((bottom - top) * ratio)

                x_center = left_margin + bar_w / 2 + i * (bar_w + gap)
                x0 = x_center - bar_w / 2
                x1 = x_center + bar_w / 2
                y1 = bottom
                y0 = bottom - bh

                color = EMO_COLORS.get(name, "#475569")
                c.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

                c.create_text(
                    x_center,
                    bottom + 10,
                    text=name.capitalize(),
                    fill=PALETTE["muted"],
                    font=("Inter", 9),
                )

            c.create_line(left_margin, bottom, w - right_margin, bottom, fill="#1f2933")

        pie = self._stats_pie_canvas
        pie.delete("all")
        for child in self._stats_legend.winfo_children():
            child.destroy()

        pw = int(pie.winfo_width() or 230)
        ph = int(pie.winfo_height() or 230)
        cx, cy = pw // 2, ph // 2
        r = min(pw, ph) // 2 - 12

        if total_secs <= 0 or self._stats_sessions == 0:
            pie.create_text(
                cx,
                cy,
                text=txt_no,
                fill=PALETTE["muted"],
                font=("Inter", 12),
                justify="center",
            )
            return

        start_angle = 0.0
        for name in LABELS:
            val = self._stats_totals.get(name, 0.0)
            if val <= 0:
                continue
            extent = 360.0 * val / total_secs
            color = EMO_COLORS.get(name, "#475569")
            pie.create_arc(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                start=start_angle,
                extent=extent,
                fill=color,
                outline=PALETTE["panel"],
            )
            start_angle += extent

        for i, name in enumerate(LABELS):
            val = self._stats_totals.get(name, 0.0)
            if val < 0.01:
                continue
            pct = (val / total_secs) * 100.0
            row = ctk.CTkFrame(self._stats_legend, fg_color="transparent")
            row.grid(row=i, column=0, sticky="w", pady=2)

            box = tk.Canvas(
                row,
                width=12,
                height=12,
                bg=PALETTE["panel"],
                highlightthickness=0,
                bd=0,
            )
            box.create_rectangle(0, 0, 12, 12, fill=EMO_COLORS.get(name, "#475569"), outline="")
            box.pack(side="left", padx=(0, 6))

            time_txt = self._fmt_mmss(val)
            label_txt = f"{name.capitalize():<8} {time_txt}  {pct:02.0f}%"

            ctk.CTkLabel(
                row,
                text=label_txt,
                font=("Inter", 11),
                text_color=PALETTE["text"],
            ).pack(side="left")

    def _load_summary_rows(self):
        path = os.path.join("sessions", "summary.csv")
        if not os.path.exists(path):
            return []

        import csv

        rows = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
        except Exception as e:
            print("Cannot read summary.csv:", e)
        return rows

    def _update_stats_view(self):
        if not hasattr(self, "_stats_canvas"):
            return

        from datetime import datetime, timedelta

        rows = self._load_summary_rows()
        lang = str(_APP_CFG.get("language", "UA")).upper()

        totals = {k: 0.0 for k in LABELS}
        selected_text = self._stats_period_var.get()
        code = getattr(self, "_stats_period_map", {}).get(selected_text, "7d")

        now = datetime.utcnow()
        sessions_count = 0

        for row in rows:
            try:
                started = datetime.fromisoformat(row.get("started_at", ""))
            except Exception:
                continue

            ok = False
            if code == "today":
                ok = started.date() == now.date()
            elif code == "yesterday":
                ok = started.date() == (now.date() - timedelta(days=1))
            elif code == "7d":
                ok = started >= now - timedelta(days=7)
            elif code == "30d":
                ok = started >= now - timedelta(days=30)
            elif code == "all":
                ok = True

            if not ok:
                continue

            sessions_count += 1
            for name in LABELS:
                key = f"sec_{name}"
                try:
                    v = float(row.get(key, "0") or 0.0)
                except Exception:
                    v = 0.0
                totals[name] += v

        total_sec = sum(totals.values())

        if total_sec <= 0 or sessions_count == 0:
            if lang == "EN":
                txt = self._stats_no_data_text
            else:
                txt = self._stats_no_data_text
        else:
            mins = int(total_sec // 60)
            hours = mins // 60
            mins = mins % 60
            if lang == "EN":
                time_text = f"{hours}h {mins}m"
            else:
                time_text = f"{hours} год {mins} хв"
            if lang == "EN":
                txt = f"{self._stats_summary_lbl.cget('text').split(' | ')[0] if ' | ' in self._stats_summary_lbl.cget('text') else ''}"

            if lang == "EN":
                txt = f"Sessions: {sessions_count}   |   Total time: {time_text}"
            else:
                txt = f"Кількість сесій: {sessions_count}   |   Загальний час: {time_text}"

        self._stats_summary_lbl.configure(text=txt)


        c = self._stats_canvas
        c.delete("all")

        W = max(260, int(c.winfo_width() or 260))
        H = max(220, int(c.winfo_height() or 220))
        radius = int(min(W, H) * 0.42)
        cx, cy = W // 2, H // 2

        if total_sec <= 0:

            c.create_text(
                W // 2,
                H // 2,
                text=self._stats_no_data_text,
                fill=PALETTE["muted"],
                font=("Inter", 13),
            )
        else:
            start = -90.0
            for name in LABELS:
                val = totals.get(name, 0.0)
                if val <= 0:
                    continue
                extent = (val / total_sec) * 360.0
                c.create_arc(
                    cx - radius,
                    cy - radius,
                    cx + radius,
                    cy + radius,
                    start=start,
                    extent=extent,
                    fill=EMO_COLORS.get(name, "#4b5563"),
                    outline=PALETTE["panel"],
                )
                start += extent

        for name, (time_lbl, pct_lbl) in self._stats_legend_rows.items():
            sec = totals.get(name, 0.0)
            time_lbl.configure(text=self._fmt_mmss(sec) if sec > 0 else "00:00")
            if total_sec > 0 and sec > 0:
                pct = sec / total_sec * 100.0
                pct_lbl.configure(text=f"{pct:0.0f}%")
            else:
                pct_lbl.configure(text="0%")

    def _build_settings_view(self):
        self.view_settings.grid_columnconfigure(0, weight=1)
        self.view_settings.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(
            self.view_settings, fg_color=PALETTE["panel"], corner_radius=18
        )
        card.place(relx=0.5, rely=0.5, anchor="c", relwidth=0.58, relheight=0.5)

        ctk.CTkLabel(
            card,
            text="Settings dashboard",
            font=("Inter", 18, "bold"),
            text_color=PALETTE["text"],
        ).pack(anchor="w", padx=22, pady=(18, 8))

        txt = (
            "Advanced settings (camera index, backend, and rules for breathing,\n"
            "Pomodoro, mirror and speech suggestions) are stored in settings.json\n"
            "and can be edited via a separate Settings window."
        )
        ctk.CTkLabel(
            card,
            text=txt,
            font=("Inter", 13),
            text_color=PALETTE["muted"],
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 18))

        btn = ctk.CTkButton(
            card,
            text="Open Settings window",
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_h"],
            text_color="black",
            corner_radius=18,
            command=self._open_settings_window,
        )
        btn.pack(padx=22, pady=(0, 18), anchor="w")

    def _open_settings_window(self):
        try:
            from ui.settings_ctk import show_settings_gui

            show_settings_gui()
        except Exception as e:
            print("Cannot open settings:", e)

    def _on_theme_change(self):
        theme = self.theme_var.get().lower()
        mode = "light" if theme.startswith("light") else "dark"
        ctk.set_appearance_mode(mode)
        _APP_CFG["theme"] = "Light" if mode == "light" else "Dark"
        try:
            _save_settings(dict(_APP_CFG))
        except Exception as e:
            print("Cannot save theme:", e)

    def _on_lang_change(self):
        lang = self.lang_var.get().upper()
        _APP_CFG["language"] = lang
        try:
            _save_settings(dict(_APP_CFG))
        except Exception as e:
            print("Cannot save language:", e)

        for frame in (self.view_about, self.view_stats, self.view_settings):
            for child in frame.winfo_children():
                child.destroy()
        self._build_about_view()
        self._build_stats_view()
        self._build_settings_view()

    def _switch_view(self, view: str):
        if view == self._current_view:
            return

        for frame in (
            self.view_live,
            self.view_about,
            self.view_stats,
            self.view_settings,
        ):
            frame.grid_forget()

        if view == "live":
            self.view_live.grid(row=0, column=0, sticky="nsew")
        elif view == "about":
            self.view_about.grid(row=0, column=0, sticky="nsew")
        elif view == "stats":
            self.view_stats.grid(row=0, column=0, sticky="nsew")
        elif view == "settings":
            self.view_settings.grid(row=0, column=0, sticky="nsew")

        self.flags.paused = view != "live"
        self.btn_pause.configure(text="Resume" if self.flags.paused else "Pause")

        for name, btn in self._nav_buttons.items():
            if name == view:
                btn.configure(
                    text_color=PALETTE["accent"],
                    font=("Inter", 13, "bold"),
                )
            else:
                btn.configure(
                    text_color=PALETTE["text"],
                    font=("Inter", 13),
                )

        self._current_view = view

    def _open_timeline(self):
        TimelineWindow(self)

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
                text_color="#f87171"
                if self.flags.recording
                else PALETTE["muted"],
            ),
        )

    def _fmt_mmss(self, secs: float) -> str:
        s = int(max(0, secs))
        m = s // 60
        ss = s % 60
        return f"{m:02d}:{ss:02d}"

    def _update_stats_ui(self):
        for k, lab in self._row_time.items():
            lab.configure(text=self._fmt_mmss(self.stats.totals.get(k, 0.0)))
        self._lbl_dom.configure(text=f"Dominant: {self.stats.dominant}")
        cur = self.stats.last_label
        for name, lab in self._row_labels.items():
            if name == cur:
                lab.configure(text_color="#0b1727", fg_color=PALETTE["accent"])
            else:
                lab.configure(text_color=PALETTE["text"], fg_color="transparent")

    def _cancel_timer(self):
        try:
            if self._after_id is not None:
                self.after_cancel(self._after_id)
        except Exception:
            pass
        self._after_id = None

    def _on_close(self):
        self._cancel_timer()
        if getattr(self.flags, "recording", False):
            try:
                if self._writer:
                    self._writer.release()
            except Exception:
                pass
        self._writer = None

        try:
            self.analyzer.stop()
            self.analyzer.join(timeout=0.5)
        except Exception:
            pass
        try:
            if hasattr(self, "cap_thread") and self.cap_thread:
                self.cap_thread.stop()
        except Exception:
            pass

        try:
            self.camera.release()
        except Exception:
            pass

        try:
            if hasattr(self, "_log_accum"):
                for k, v in self._log_accum.items():
                    if v > 0:
                        stats.log_event(k, v)
        except Exception:
            pass

        try:
            stats.write_session_summary(
                totals={k: float(v) for k, v in self.stats.totals.items()},
                meta={
                    "started_at": self._session_started_at,
                    "ended_at": datetime.utcnow().isoformat(),
                },
            )
            self._write_csv_summary()
        except Exception as e:
            print("Cannot write session summary:", e)

        try:
            self.destroy()
        except Exception:
            pass

    def _render(self):
        t0 = time.time()

        if not self.flags.paused:
            frame = getattr(self.cap_thread, "last_bgr", None)
            if frame is not None:
                self._last_frame_bgr = frame

                self.analyzer.update_frame(frame)

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                if self.flags.recording and self._writer is not None:
                    try:
                        self._writer.write(frame)
                    except Exception:
                        pass

                try:
                    if _HAS_PIL:
                        from PIL import Image, ImageTk

                        img = Image.fromarray(frame_rgb)
                        self._tkimg = ImageTk.PhotoImage(img, master=self.canvas)
                    else:
                        ok, buf = cv2.imencode(".png", frame_rgb)
                        if ok:
                            self._tkimg = tk.PhotoImage(
                                data=buf.tobytes(), master=self.canvas
                            )
                except Exception:
                    self._tkimg = None

                if self._tkimg is not None:
                    if self._img_id is None:
                        self._img_id = self.canvas.create_image(
                            0, 0, image=self._tkimg, anchor="nw"
                        )
                    else:
                        self.canvas.itemconfigure(self._img_id, image=self._tkimg)

                if not self._autosized:
                    h, w = frame.shape[:2]
                    sidebar_w = max(300, int(self.sidebar.winfo_width() or 300))
                    padding = 40
                    max_w = max(420, self.winfo_width() - sidebar_w - padding)
                    scale = min(1.0, max_w / w)
                    new_w, new_h = int(w * scale), int(h * scale)
                    self.canvas.config(width=new_w, height=new_h)
                    self._autosized = True

                self.canvas.tag_raise(self._fps_lbl)

        spent = time.time() - t0
        fps = 1.0 / max(1e-6, spent)
        self._fps_hist.append(fps)
        if len(self._fps_hist) > 15:
            self._fps_hist.pop(0)
        avg = sum(self._fps_hist) / max(1, len(self._fps_hist))
        self.canvas.itemconfigure(self._fps_lbl, text=f"{avg:0.1f} FPS")
        status = f"Cam {self.cam_index} · {self.backend} · {avg:0.0f} FPS"
        self.canvas.itemconfigure(self._status_lbl, text=status)

        label, conf = self.analyzer.current
        now = time.time()
        dt = now - getattr(self, "_last_tick", now)
        self._last_tick = now

        if label in LABELS:
            self.stats.add(label, dt)
            self.stats.last_label = label
            self.stats.recompute_dominant()
            self._update_stats_ui()

            elapsed = time.monotonic() - self._t0
            self.timeline.append((elapsed, label))
            if len(self.timeline) > 8000:
                self.timeline = self.timeline[-8000:]

            self._emotion_acc[label] = self._emotion_acc.get(label, 0.0) + dt
            self.rules_state.feed_face_presence(True, dt)

            accum = getattr(self, "_log_accum", {})
            accum[label] = accum.get(label, 0.0) + dt
            self._log_accum = accum
            if sum(accum.values()) >= 0.5:
                for k, v in list(accum.items()):
                    if v > 0:
                        stats.log_event(k, v)
                self._log_accum = {}
        else:
            self.rules_state.feed_face_presence(False, dt)

        self.canvas.itemconfigure(self._emo_lbl, text=f"{label}  {int(conf * 100)}%")
        self._after_id = self.after(33, self._render)

    def _show_hint(self, kind: str):
        text = {
            "breathing": "Try a 60s breathing break?",
            "pomodoro": "Short Pomodoro? 5 min focus → 1 min relax.",
            "mirror": "Step away / check posture & relax face 🙂",
            "speech": "Light speech practice for 30s?",
        }.get(kind, "")
        if not text:
            return
        self._hint_lbl.configure(text=f"Suggestion: {text}")
        try:
            os.system(
                f"""osascript -e 'display notification "{text}" with title "Emotion" sound name "Submarine"'"""
            )
        except Exception:
            pass


def run_live():
    app = LiveWindow()
    app.mainloop()
