# ui/live.py
from __future__ import annotations
import os, time, threading
from dataclasses import dataclass, field
from datetime import datetime

import customtkinter as ctk
import tkinter as tk
import cv2

try:
    from utils.app_settings import load as _load_settings
    _APP_CFG = _load_settings()
except Exception:
    _APP_CFG = {}

_HAS_DEEPFACE = False
_HAS_FER = False
_HAS_PIL = False
try:
    from deepface import DeepFace
    _HAS_DEEPFACE = True
except Exception:
    pass

try:
    from fer import FER
    _HAS_FER = True
except Exception:
    pass

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:
    pass

PALETTE = {
    "bg":      "#081423",
    "panel":   "#0e1b2d",
    "accent":  "#00D1FF",
    "accent_h":"#16E0FF",
    "text":    "#E8F1FF",
    "muted":   "#94a3b8",
    "border":  "#16324a",
}
LABELS = ["happy","neutral","sad","angry","fear","surprise","disgust"]

def set_ctk_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

def _ensure_dirs():
    os.makedirs("sessions/snaps", exist_ok=True)
    os.makedirs("sessions/records", exist_ok=True)

def _parse_res(s: str) -> tuple[int,int]:
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
            self.dominant = "–"; return
        self.dominant = max(self.totals.items(), key=lambda kv: kv[1])[0]

class Camera:
    def __init__(self, index: int = 0, resolution: str = "480x270"):
        self.index = int(index)
        self.cap = cv2.VideoCapture(self.index)
        self.set_resolution(resolution)
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def set_resolution(self, res_str: str):
        w, h = _parse_res(res_str)
        if self.cap:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    def read(self):
        if not self.cap:
            return None
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        try:
            if self.cap: self.cap.release()
        except Exception:
            pass

class AnalyzerThread(threading.Thread):
    def __init__(self, backend: str, analyze_every: float):
        super().__init__(daemon=True)
        self.backend = backend
        self.analyze_every = max(0.25, float(analyze_every or 0.6))
        self._last_rgb = None
        self._stop = threading.Event()
        self.current = ("–", 0.0)
        self._fer = FER(mtcnn=True) if backend == "fer" and _HAS_FER else None

    def update_frame(self, rgb):
        self._last_rgb = rgb

    def stop(self):
        self._stop.set()

    def _run_deepface(self, img):
        try:
            out = DeepFace.analyze(
                img, actions=["emotion"], enforce_detection=False, detector_backend="skip"
            )

            data = out[0] if isinstance(out, list) else out
            ems = data.get("emotion") or {}
            if not ems:
                return ("neutral", 0.0)
            label = max(ems.items(), key=lambda kv: kv[1])[0].lower()
            conf = max(ems.values()) / 100.0
            return (label, conf)
        except Exception:
            return ("neutral", 0.0)

    def _run_fer(self, img):
        try:
            preds = self._fer.detect_emotions(img)
            if not preds:
                return ("neutral", 0.0)
            em = preds[0]["emotions"]
            label = max(em.items(), key=lambda kv: kv[1])[0].lower()
            conf = em[label]
            return (label, conf)
        except Exception:
            return ("neutral", 0.0)

    def run(self):
        last = 0.0
        while not self._stop.is_set():
            now = time.time()
            if self._last_rgb is not None and (now - last) >= self.analyze_every:
                if self.backend == "deepface" and _HAS_DEEPFACE:
                    self.current = self._run_deepface(self._last_rgb)
                elif self.backend == "fer" and _HAS_FER:
                    self.current = self._run_fer(self._last_rgb)
                else:
                    self.current = ("neutral", 0.0)  # dummy
                last = now
            time.sleep(0.01)

class LiveWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        set_ctk_theme()
        try:
            cv2.setNumThreads(2)
            cv2.useOptimized(True)
        except Exception:
            pass
        _ensure_dirs()

        self.title("Emotion — Live")
        self.configure(fg_color=PALETTE["bg"])

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        win_w = min(1100, max(900, sw - 80))
        win_h = min(720,  max(600, sh - 120))
        self.geometry(f"{win_w}x{win_h}+40+40")
        self.minsize(820, 560)

        self.flags = LiveFlags()
        self.stats = SessionStats()
        self._after_id: str | None = None
        self._last_tick = time.time()

        default_res = str(_APP_CFG.get("resolution", "480x270"))
        if "x" not in default_res: default_res = "480x270"
        default_backend = str(_APP_CFG.get("backend", "deepface"))
        cam_index = int(_APP_CFG.get("camera_index", 0))
        self.analyze_every = float(_APP_CFG.get("analyze_every", 0.6))

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg=PALETTE["bg"], highlightthickness=0, bd=0, relief="flat")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        self._fps_lbl = self.canvas.create_text(10, 10, anchor="nw",
                                                text="", fill="#9fb3c6",
                                                font=("Inter", 11, "bold"))

        self.sidebar = ctk.CTkFrame(self, fg_color=PALETTE["panel"], corner_radius=14)
        self.sidebar.grid(row=0, column=1, sticky="ns", padx=(6, 12), pady=12)
        for i in range(40):
            self.sidebar.grid_rowconfigure(i, weight=0)
        self.sidebar.grid_rowconfigure(99, weight=1)

        ctk.CTkLabel(self.sidebar, text="Live Controls",
                     text_color=PALETTE["text"], font=("Inter", 16, "bold"))\
            .grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")

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

        self.v_res = tk.StringVar(value=default_res)
        ctk.CTkLabel(self.sidebar, text="Resolution", text_color=PALETTE["text"])\
            .grid(row=5, column=0, padx=14, pady=(12, 6), sticky="w")
        self.opt_res = ctk.CTkOptionMenu(self.sidebar, values=["320x180","480x270","640x360"],
                                         variable=self.v_res, fg_color=PALETTE["panel"],
                                         button_color=PALETTE["accent"], button_hover_color=PALETTE["accent_h"],
                                         text_color=PALETTE["text"], command=self._on_change_res)
        self.opt_res.grid(row=6, column=0, padx=14, pady=(0, 12), sticky="ew")

        backend_values = []
        if _HAS_DEEPFACE: backend_values.append("deepface")
        if _HAS_FER:      backend_values.append("fer")
        backend_values.append("dummy")
        if default_backend not in backend_values:
            default_backend = backend_values[0]
        self.v_backend = tk.StringVar(value=default_backend)

        ctk.CTkLabel(self.sidebar, text="Backend", text_color=PALETTE["text"])\
            .grid(row=7, column=0, padx=14, pady=(6, 6), sticky="w")
        self.opt_backend = ctk.CTkOptionMenu(self.sidebar, values=backend_values,
                                             variable=self.v_backend, fg_color=PALETTE["panel"],
                                             button_color=PALETTE["accent"], button_hover_color=PALETTE["accent_h"],
                                             text_color=PALETTE["text"], command=self._on_change_backend)
        self.opt_backend.grid(row=8, column=0, padx=14, pady=(0, 6), sticky="ew")

        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=PALETTE["border"])
        sep.grid(row=9, column=0, sticky="ew", padx=14, pady=(8, 8))

        ctk.CTkLabel(self.sidebar, text="Session Stats", text_color=PALETTE["text"],
                     font=("Inter", 14, "bold")).grid(row=10, column=0, padx=14, pady=(0, 4), sticky="w")

        stats_tbl = ctk.CTkFrame(self.sidebar, fg_color=PALETTE["panel"])
        stats_tbl.grid(row=11, column=0, padx=10, pady=(0, 8), sticky="ew")
        stats_tbl.grid_columnconfigure(0, weight=1)
        stats_tbl.grid_columnconfigure(1, weight=0)

        self._lbl_dom = ctk.CTkLabel(stats_tbl, text="Dominant: –", text_color=PALETTE["muted"])
        self._lbl_dom.grid(row=0, column=0, columnspan=2, padx=8, pady=(6, 6), sticky="w")

        self._row_time = {}
        r = 1
        for name in LABELS:
            ctk.CTkLabel(stats_tbl, text=name, text_color=PALETTE["text"]) \
                .grid(row=r, column=0, padx=8, pady=2, sticky="w")
            t = ctk.CTkLabel(stats_tbl, text="00:00", text_color=PALETTE["muted"])
            t.grid(row=r, column=1, padx=8, pady=2, sticky="e")
            self._row_time[name] = t
            r += 1

        self.btn_exit = ctk.CTkButton(self.sidebar, text="Exit",
                                      fg_color="#1f2937", hover_color="#111827",
                                      text_color=PALETTE["text"], command=self._on_close)
        self.btn_exit.grid(row=98, column=0, padx=14, pady=(10, 10), sticky="ew")

        self.bind("<Escape>", lambda e: self._on_close())
        self.bind("<Command-q>", lambda e: self._on_close())

        self._tkimg = None
        self._img_id = None
        self._writer = None
        self._rec_path = None
        self._fps_hist: list[float] = []
        self._autosized = False

        self.camera = Camera(index=cam_index, resolution=self.v_res.get())
        self.analyzer = AnalyzerThread(self.v_backend.get(), self.analyze_every)
        self.analyzer.start()

        self._after_id = self.after(20, self._render)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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

    def _on_change_res(self, _=None):
        self.camera.set_resolution(self.v_res.get())
        self._autosized = False

    def _on_change_backend(self, _=None):
        try:
            self.analyzer.stop()
            self.analyzer.join(timeout=0.5)
        except Exception:
            pass
        self.analyzer = AnalyzerThread(self.v_backend.get(), self.analyze_every)
        self.analyzer.start()

    def _toggle_recording(self):
        if not self.flags.recording:
            w, h = _parse_res(self.v_res.get())
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._rec_path = os.path.join("sessions", "records", f"rec_{ts}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(self._rec_path, fourcc, 25.0, (w, h))
            self.flags.recording = True
            self._rec_led.configure(text="● Recording", text_color="#f87171")
            self.btn_rec.configure(text="Stop Recording")
            self._flash_status("Recording started")
        else:
            self.flags.recording = False
            try:
                if self._writer: self._writer.release()
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
        self.after(1800, lambda: self._rec_led.configure(
            text="● Recording" if self.flags.recording else "● Not recording",
            text_color="#f87171" if self.flags.recording else PALETTE["muted"]
        ))

    def _fmt_mmss(self, secs: float) -> str:
        s = int(max(0, secs)); m = s // 60; ss = s % 60
        return f"{m:02d}:{ss:02d}"

    def _update_stats_ui(self):
        for k, lab in self._row_time.items():
            lab.configure(text=self._fmt_mmss(self.stats.totals.get(k, 0.0)))
        self._lbl_dom.configure(text=f"Dominant: {self.stats.dominant}")

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
                if self._writer: self._writer.release()
            except Exception:
                pass
        self._writer = None

        try:
            self.analyzer.stop()
            self.analyzer.join(timeout=0.5)
        except Exception:
            pass

        try:
            self.camera.release()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass

        try:
            from ui.settings_ctk import show_settings_gui
            show_settings_gui()
        except Exception as e:
            print("Cannot open Dashboard:", e)

    def _render(self):
        t0 = time.time()

        if not self.flags.paused:
            frame = self.camera.read()
            if frame is not None:
                self._last_frame_bgr = frame
                if self.flags.recording and self._writer is not None:
                    try: self._writer.write(frame)
                    except Exception: pass

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.analyzer.update_frame(frame_rgb)

                if _HAS_PIL:
                    img = Image.fromarray(frame_rgb)
                    self._tkimg = ImageTk.PhotoImage(img, master=self.canvas)
                else:
                    ok, buf = cv2.imencode(".png", frame_rgb)
                    if ok: self._tkimg = tk.PhotoImage(data=buf.tobytes(), master=self.canvas)

                if self._img_id is None:
                    self._img_id = self.canvas.create_image(0, 0, image=self._tkimg, anchor="nw")
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
        if len(self._fps_hist) > 15: self._fps_hist.pop(0)
        avg = sum(self._fps_hist) / max(1, len(self._fps_hist))
        self.canvas.itemconfigure(self._fps_lbl, text=f"{avg:0.1f} FPS")

        label, _conf = self.analyzer.current
        now = time.time()
        dt = now - self._last_tick
        self._last_tick = now
        if label in LABELS:
            self.stats.add(label, dt)
            self.stats.recompute_dominant()
            self._update_stats_ui()

        self._after_id = self.after(16, self._render)


def run_live():
    app = LiveWindow()
    app.mainloop()
