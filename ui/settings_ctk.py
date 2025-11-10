# ui/settings_ctk.py
from __future__ import annotations

import customtkinter as ctk
from tkinter import StringVar, BooleanVar, DoubleVar, IntVar
from utils.app_settings import load, save
import tkinter as tk

PALETTE = {
    "bg_panel":   "#0e1b2d",
    "bg_sidebar": "#0a1422",
    "accent":     "#00D1FF",
    "accent_h":   "#16E0FF",
    "muted":      "#94a3b8",
    "text":       "#E8F1FF",
    "border":     "#16324a",
}

def set_ctk_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

class Section(ctk.CTkFrame):
    def __init__(self, master, title: str = "", **kw):
        super().__init__(master, fg_color=PALETTE["bg_panel"], corner_radius=16, **kw)
        if title:
            ctk.CTkLabel(self, text=title, font=("Inter", 14, "bold"),
                         text_color=PALETTE["text"]).grid(row=0, column=0, sticky="w",
                                                          padx=16, pady=(12, 6), columnspan=2)

def subtle_button(master, **kw):
    return ctk.CTkButton(master, fg_color=PALETTE["bg_panel"], hover_color="#12243a",
                         border_color=PALETTE["border"], border_width=1,
                         text_color=PALETTE["text"], corner_radius=10, **kw)

def accent_button(master, **kw):
    return ctk.CTkButton(master, fg_color=PALETTE["accent"], hover_color=PALETTE["accent_h"],
                         text_color="black", corner_radius=10, **kw)

def accent_option(master, variable, values):
    return ctk.CTkOptionMenu(master, values=values, variable=variable,
                             fg_color=PALETTE["bg_panel"], button_color=PALETTE["accent"],
                             button_hover_color=PALETTE["accent_h"], text_color=PALETTE["text"],
                             dropdown_fg_color="#0f1d31", dropdown_text_color=PALETTE["text"],
                             dropdown_hover_color="#11243a", corner_radius=10)

class Dashboard(ctk.CTk):
    def report_callback_exception(self, exc, val, tb):
        import traceback; traceback.print_exception(exc, val, tb)

    def __init__(self):
        super().__init__()
        self.title("Emotion — Dashboard")
        self.geometry("1100x760")
        set_ctk_theme()
        self.configure(fg_color="#081423")
        self.stats_canvas: tk.Canvas | None = None
        self._render_job: str | None = None
        self.cfg = load()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=PALETTE["bg_sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="🚀 EMOTION", font=("Inter", 18, "bold"),
                     text_color=PALETTE["text"]).pack(padx=16, pady=(20, 10))

        self._nav_items = [
            ("Dashboard",        self._show_dashboard),
            ("Devices",          self._show_devices),
            ("Behavior & Rules", self._show_rules),
            ("Privacy",          self._show_privacy),
            ("Performance",      self._show_perf),
            ("TTS & Language",   self._show_tts_lang),
            ("Statistics",       self._show_stats),
            ("Help / About",     self._show_help),
        ]
        self._nav_buttons = {}
        for text, fn in self._nav_items:
            b = subtle_button(self.sidebar, text=text,
                              command=lambda f=fn, t=text: self._nav_go(f, t))
            b.pack(padx=16, pady=6, fill="x")
            self._nav_buttons[text] = b

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self.content.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(self, fg_color="transparent", height=56)
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12))
        bottom.grid_columnconfigure((0, 1, 2), weight=1)
        accent_button(bottom, text="Save", command=self._on_save)\
            .grid(row=0, column=1, padx=6, pady=8, sticky="e")
        subtle_button(bottom, text="Save & Run in Background", command=self._on_save_and_run)\
            .grid(row=0, column=2, padx=6, pady=8, sticky="w")

        self._nav_go(self._show_dashboard, "Dashboard")

    def _nav_go(self, fn, title: str):
        active = {"fg_color": PALETTE["accent"], "text_color": "black"}
        inactive = {"fg_color": PALETTE["bg_panel"], "text_color": PALETTE["text"]}
        for name, btn in self._nav_buttons.items():
            btn.configure(**(active if name == title else inactive))

        if title != "Statistics":
            self._leave_stats()

        for w in self.content.winfo_children():
            w.destroy()
        fn()

    def _leave_stats(self):
        if self._render_job:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None

        if self.stats_canvas and self.stats_canvas.winfo_exists():
            try:
                self.stats_canvas.destroy()
            except Exception:
                pass
        self.stats_canvas = None

    def _render_stats(self):
        c = self.stats_canvas
        if not c or not isinstance(c, tk.Canvas) or not c.winfo_exists():
            return

        try:
            c.delete("all")
            w = int(c.winfo_width() or 700)
            h = int(c.winfo_height() or 260)
            margin = 40
            c.create_rectangle(margin, h - 30, margin + 60, h - 10, width=0)
            c.create_text(margin + 30, h - 5, text="neutral", anchor="s")
        except tk.TclError:
            return

        if c.winfo_exists():
            self._render_job = c.after(500, self._render_stats)

    def _start_stats(self, parent):
        if self._render_job:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None

        if self.stats_canvas and self.stats_canvas.winfo_exists():
            self.stats_canvas.destroy()
        self.stats_canvas = None

        bg = getattr(self, "_bg", "#0f172a")
        self.stats_canvas = tk.Canvas(parent, height=260, bg=bg, highlightthickness=0)
        self.stats_canvas.pack(fill="x", padx=20, pady=(10, 0))

        self._render_stats()

    def _bind_bool(self, key):  return BooleanVar(value=bool(self.cfg.get(key)))
    def _bind_str(self, key):   return StringVar(value=str(self.cfg.get(key)))
    def _bind_float(self, key): return DoubleVar(value=float(self.cfg.get(key)))
    def _bind_int(self, key):   return IntVar(value=int(self.cfg.get(key)))
    def _L(self, parent, text, r, c=0, **kw):
        ctk.CTkLabel(parent, text=text, text_color=PALETTE["text"], **kw)\
            .grid(row=r, column=c, sticky="w", padx=16, pady=8)

    def _show_dashboard(self):
        f = Section(self.content); f.grid(sticky="ew"); f.grid_columnconfigure(0, weight=1)
        self.v_bg = self._bind_bool("background_mode")
        ctk.CTkSwitch(f, text="Background Mode (run in tray)", variable=self.v_bg,
                      progress_color=PALETTE["accent"]).grid(row=1, column=0, sticky="w",
                                                             padx=16, pady=(16, 6))

        tips = Section(self.content, "Enable tips"); tips.grid(sticky="ew", pady=(10, 6))
        tips.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.v_rule_b  = self._bind_bool("rule_breathing")
        self.v_rule_p  = self._bind_bool("rule_pomodoro")
        self.v_rule_m  = self._bind_bool("rule_mirror")
        self.v_rule_sp = self._bind_bool("rule_speech")
        ctk.CTkCheckBox(tips, text="Breathing", variable=self.v_rule_b).grid(row=1, column=0, padx=16, pady=4, sticky="w")
        ctk.CTkCheckBox(tips, text="Pomodoro", variable=self.v_rule_p).grid(row=1, column=1, padx=16, pady=4, sticky="w")
        ctk.CTkCheckBox(tips, text="Mirror",    variable=self.v_rule_m).grid(row=1, column=2, padx=16, pady=4, sticky="w")
        ctk.CTkCheckBox(tips, text="Speech Light", variable=self.v_rule_sp).grid(row=1, column=3, padx=16, pady=4, sticky="w")

        p = Section(self.content, "Privacy"); p.grid(sticky="ew", pady=(6, 6))
        self.v_stats  = self._bind_bool("privacy_save_stats")
        self.v_frames = self._bind_bool("privacy_save_frames")
        self.v_blur   = self._bind_bool("privacy_blur")
        ctk.CTkCheckBox(p, text="Save statistics (events.jsonl)", variable=self.v_stats)\
            .grid(row=0, column=0, padx=16, pady=6, sticky="w")
        ctk.CTkCheckBox(p, text="Save frames (OFF by default)", variable=self.v_frames)\
            .grid(row=1, column=0, padx=16, pady=6, sticky="w")
        ctk.CTkCheckBox(p, text="Blur faces in preview", variable=self.v_blur)\
            .grid(row=2, column=0, padx=16, pady=6, sticky="w")

        perf = Section(self.content, "Performance"); perf.grid(sticky="ew", pady=(6, 6))
        perf.grid_columnconfigure(1, weight=1)
        self.v_detector   = self._bind_str("detector")
        self.v_resolution = self._bind_str("resolution")
        self.v_every      = self._bind_float("analyze_every")
        self.v_ema        = self._bind_float("ema")
        self._L(perf, "Detector", 1)
        accent_option(perf, self.v_detector, ["opencv", "mediapipe", "retinaface"])\
            .grid(row=1, column=1, padx=16, pady=4, sticky="ew")
        self._L(perf, "Resolution", 2)
        accent_option(perf, self.v_resolution, ["320x180", "480x270", "640x360"])\
            .grid(row=2, column=1, padx=16, pady=4, sticky="ew")
        lbl_every = ctk.CTkLabel(perf, text=f"Analyze Every (s): {self.v_every.get():.1f}",
                                 text_color=PALETTE["muted"])
        lbl_every.grid(row=3, column=0, sticky="w", padx=16, pady=4)
        s_every = ctk.CTkSlider(perf, from_=0.6, to=2.0, number_of_steps=14,
                                variable=self.v_every, progress_color=PALETTE["accent"])
        s_every.grid(row=3, column=1, sticky="ew", padx=16, pady=4)
        s_every.configure(command=lambda v: lbl_every.configure(text=f"Analyze Every (s): {float(v):.1f}"))
        lbl_ema = ctk.CTkLabel(perf, text=f"EMA (smoothing): {self.v_ema.get():.2f}", text_color=PALETTE["muted"])
        lbl_ema.grid(row=4, column=0, sticky="w", padx=16, pady=4)
        s_ema = ctk.CTkSlider(perf, from_=0.10, to=0.90, number_of_steps=80,
                              variable=self.v_ema, progress_color=PALETTE["accent"])
        s_ema.grid(row=4, column=1, sticky="ew", padx=16, pady=4)
        s_ema.configure(command=lambda v: lbl_ema.configure(text=f"EMA (smoothing): {float(v):.2f}"))

        tts = Section(self.content); tts.grid(sticky="ew", pady=(6, 6)); tts.grid_columnconfigure(1, weight=1)
        self.v_tts   = self._bind_bool("tts_enabled")
        self.v_lang  = self._bind_str("language")
        self.v_theme = self._bind_str("theme")
        ctk.CTkCheckBox(tts, text="TTS Enabled", variable=self.v_tts)\
            .grid(row=0, column=0, padx=16, pady=6, sticky="w")
        self._L(tts, "Language", 1)
        accent_option(tts, self.v_lang, ["UA", "EN"]).grid(row=1, column=1, padx=16, pady=6, sticky="ew")
        self._L(tts, "Theme", 2)
        accent_option(tts, self.v_theme, ["Dark", "Light"]).grid(row=2, column=1, padx=16, pady=6, sticky="ew")

    def _show_devices(self):
        box = Section(self.content, "Devices"); box.grid(sticky="ew", pady=(10, 6))
        box.grid_columnconfigure(1, weight=1)
        self.v_cam = self._bind_int("camera_index")
        self._L(box, "Camera index", 1)
        accent_option(box, self.v_cam, [str(i) for i in range(0, 5)]).grid(row=1, column=1, padx=16, pady=8, sticky="ew")
        subtle_button(box, text="Open Preview", command=self._open_preview)\
            .grid(row=2, column=1, padx=16, pady=8, sticky="e")
        self.v_mic = self._bind_str("mic_device")
        self._L(box, "Microphone (device name)", 3)
        ctk.CTkEntry(box, textvariable=self.v_mic).grid(row=3, column=1, padx=16, pady=8, sticky="ew")
        self.v_gain = self._bind_float("mic_gain")
        lbl = ctk.CTkLabel(box, text=f"Mic gain: {self.v_gain.get():.2f}", text_color=PALETTE["muted"])
        lbl.grid(row=4, column=0, padx=16, pady=8, sticky="w")
        s = ctk.CTkSlider(box, from_=0.2, to=2.0, number_of_steps=18, variable=self.v_gain,
                          progress_color=PALETTE["accent"])
        s.grid(row=4, column=1, padx=16, pady=8, sticky="ew")
        s.configure(command=lambda v: lbl.configure(text=f"Mic gain: {float(v):.2f}"))

    def _show_rules(self):
        f = Section(self.content, "Behavior & Rules"); f.grid(sticky="ew", pady=(10, 6))
        f.grid_columnconfigure(1, weight=1)
        self.v_rule_b  = self._bind_bool("rule_breathing")
        self.v_rule_p  = self._bind_bool("rule_pomodoro")
        self.v_rule_m  = self._bind_bool("rule_mirror")
        self.v_rule_sp = self._bind_bool("rule_speech")
        ctk.CTkCheckBox(f, text="Enable Breathing", variable=self.v_rule_b).grid(row=1, column=0, padx=16, pady=6, sticky="w")
        ctk.CTkCheckBox(f, text="Enable Pomodoro",  variable=self.v_rule_p).grid(row=1, column=1, padx=16, pady=6, sticky="w")
        ctk.CTkCheckBox(f, text="Enable Mirror",    variable=self.v_rule_m).grid(row=2, column=0, padx=16, pady=6, sticky="w")
        ctk.CTkCheckBox(f, text="Enable Speech Light", variable=self.v_rule_sp).grid(row=2, column=1, padx=16, pady=6, sticky="w")
        self.v_sad = self._bind_int("rule_sad_sec")
        self.v_ang = self._bind_int("rule_angry_sec")
        self.v_neu = self._bind_int("rule_neutral_sec")
        self.v_nf  = self._bind_int("rule_noface_pct")
        self.v_cd  = self._bind_int("rule_cooldown_min")
        def row(r, label, var, suffix="s"):
            self._L(f, label, r)
            ctk.CTkEntry(f, textvariable=var).grid(row=r, column=1, padx=16, pady=6, sticky="ew")
            ctk.CTkLabel(f, text=suffix, text_color=PALETTE["muted"]).grid(row=r, column=2, padx=6, sticky="w")
        row(3, "sad ≥ ",     self.v_sad)
        row(4, "angry ≥ ",   self.v_ang)
        row(5, "neutral ≥ ", self.v_neu)
        row(6, "noface ≥ ",  self.v_nf, "%")
        row(7, "cooldown",   self.v_cd, "min")

    def _show_privacy(self):
        f = Section(self.content, "Privacy"); f.grid(sticky="ew", pady=(10, 6))
        self.v_stats  = self._bind_bool("privacy_save_stats")
        self.v_frames = self._bind_bool("privacy_save_frames")
        self.v_blur   = self._bind_bool("privacy_blur")
        ctk.CTkCheckBox(f, text="Save statistics (events.jsonl)", variable=self.v_stats)\
            .grid(row=0, column=0, padx=16, pady=8, sticky="w")
        ctk.CTkCheckBox(f, text="Save frames (OFF by default)",   variable=self.v_frames)\
            .grid(row=1, column=0, padx=16, pady=8, sticky="w")
        ctk.CTkCheckBox(f, text="Blur faces in preview",          variable=self.v_blur)\
            .grid(row=2, column=0, padx=16, pady=8, sticky="w")

    def _show_perf(self):
        f = Section(self.content, "Performance (detailed)"); f.grid(sticky="ew", pady=(10, 6))
        f.grid_columnconfigure(1, weight=1)
        self.v_backend   = self._bind_str("backend")
        self.v_detector  = self._bind_str("detector")
        self.v_resolution= self._bind_str("resolution")
        self.v_every     = self._bind_float("analyze_every")
        self.v_ema       = self._bind_float("ema")
        self.v_minconf   = self._bind_float("min_conf")
        self.v_hold      = self._bind_float("hold_sec")
        self._L(f, "Backend", 1)
        accent_option(f, self.v_backend, ["deepface", "fer", "dummy"]).grid(row=1, column=1, padx=16, pady=8, sticky="ew")
        self._L(f, "Detector", 2)
        accent_option(f, self.v_detector, ["opencv", "mediapipe", "retinaface"]).grid(row=2, column=1, padx=16, pady=8, sticky="ew")
        self._L(f, "Resolution", 3)
        accent_option(f, self.v_resolution, ["320x180", "480x270", "640x360"]).grid(row=3, column=1, padx=16, pady=8, sticky="ew")
        lbl_every = ctk.CTkLabel(f, text=f"Analyze Every (s): {self.v_every.get():.1f}", text_color=PALETTE["muted"])
        lbl_every.grid(row=4, column=0, padx=16, pady=8, sticky="w")
        s_every = ctk.CTkSlider(f, from_=0.6, to=2.0, number_of_steps=14, variable=self.v_every,
                                progress_color=PALETTE["accent"])
        s_every.grid(row=4, column=1, padx=16, pady=8, sticky="ew")
        s_every.configure(command=lambda v: lbl_every.configure(text=f"Analyze Every (s): {float(v):.1f}"))
        lbl_ema = ctk.CTkLabel(f, text=f"EMA (0.10–0.90): {self.v_ema.get():.2f}", text_color=PALETTE["muted"])
        lbl_ema.grid(row=5, column=0, padx=16, pady=8, sticky="w")
        s_ema = ctk.CTkSlider(f, from_=0.10, to=0.90, number_of_steps=80, variable=self.v_ema,
                              progress_color=PALETTE["accent"])
        s_ema.grid(row=5, column=1, padx=16, pady=8, sticky="ew")
        s_ema.configure(command=lambda v: lbl_ema.configure(text=f"EMA (0.10–0.90): {float(v):.2f}"))
        row = ctk.CTkFrame(f, fg_color=PALETTE["bg_panel"])
        row.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(8,4))
        row.grid_columnconfigure((0,1,2,3), weight=1)
        ctk.CTkLabel(row, text="Min confidence (%)", text_color=PALETTE["text"]).grid(row=0, column=0, padx=8, sticky="e")
        ctk.CTkEntry(row, textvariable=self.v_minconf).grid(row=0, column=1, padx=8, sticky="ew")
        ctk.CTkLabel(row, text="Hold sec", text_color=PALETTE["text"]).grid(row=0, column=2, padx=8, sticky="e")
        ctk.CTkEntry(row, textvariable=self.v_hold).grid(row=0, column=3, padx=8, sticky="ew")

    def _show_tts_lang(self):
        f = Section(self.content, "TTS & Language"); f.grid(sticky="ew", pady=(10, 6))
        self.v_tts   = self._bind_bool("tts_enabled")
        self.v_lang  = self._bind_str("language")
        self.v_theme = self._bind_str("theme")
        ctk.CTkCheckBox(f, text="TTS Enabled", variable=self.v_tts).grid(row=0, column=0, padx=16, pady=8, sticky="w")
        self._L(f, "Language", 1)
        accent_option(f, self.v_lang, ["UA", "EN"]).grid(row=1, column=1, padx=16, pady=8, sticky="ew")
        self._L(f, "Theme", 2)
        accent_option(f, self.v_theme, ["Dark", "Light"]).grid(row=2, column=1, padx=16, pady=8, sticky="ew")

    def _show_help(self):
        f = Section(self.content, "Help / About"); f.grid(sticky="ew", pady=(10, 6))
        txt = ("• Agent runs in background and proposes micro-breaks via notifications.\n"
               "• Hotkeys (planned): Pause/Resume Agent, Open Dashboard.\n"
               "• Data: sessions/<id>/events.jsonl, summary.json; logs/app.log.\n"
               "• Privacy: frames are OFF by default.")
        ctk.CTkLabel(f, text=txt, justify="left", text_color=PALETTE["text"]).grid(
            row=1, column=0, padx=16, pady=12, sticky="w"
        )

    def _open_preview(self):
        try:
            from ui.preview import run_preview
        except Exception as e:
            print("Preview import error:", e); return
        try: self.withdraw()
        except Exception: pass
        try: run_preview()
        except Exception as e: print("Preview crash:", e)
        finally:
            try: self.deiconify()
            except Exception: pass

    def _collect_settings(self):
        return {
            "background_mode": self.v_bg.get(),
            "detector": self.v_detector.get(),
            "resolution": self.v_resolution.get(),
            "analyze_every": float(self.v_every.get()),
            "ema": float(self.v_ema.get()),
            "privacy_blur": self.v_blur.get(),
            "privacy_save_stats": self.v_stats.get(),
            "privacy_save_frames": self.v_frames.get(),
            "tts_enabled": self.v_tts.get(),
            "language": self.v_lang.get(),
            "theme": self.v_theme.get(),
            "rule_breathing": self.v_rule_b.get(),
            "rule_pomodoro": self.v_rule_p.get(),
            "rule_mirror": self.v_rule_m.get(),
            "rule_speech": self.v_rule_sp.get(),
            "rule_sad_sec": int(getattr(self, "v_sad", 60).get()) if hasattr(self, "v_sad") else 60,
            "rule_angry_sec": int(getattr(self, "v_ang", 30).get()) if hasattr(self, "v_ang") else 30,
            "rule_neutral_sec": int(getattr(self, "v_neu", 120).get()) if hasattr(self, "v_neu") else 120,
            "rule_noface_pct": int(getattr(self, "v_nf", 40).get()) if hasattr(self, "v_nf") else 40,
            "rule_cooldown_min": int(getattr(self, "v_cd", 30).get()) if hasattr(self, "v_cd") else 30,
            "camera_index": int(getattr(self, "v_cam", 0).get()) if hasattr(self, "v_cam") else 0,
            "mic_device": getattr(self, "v_mic", StringVar(value="")).get(),
            "mic_gain": float(getattr(self, "v_gain", DoubleVar(value=1.0)).get()),
            "backend": getattr(self, "v_backend", self._bind_str("backend")).get(),
            "min_conf": float(getattr(self, "v_minconf", self._bind_float("min_conf")).get()),
            "hold_sec": float(getattr(self, "v_hold", self._bind_float("hold_sec")).get()),
        }

    def _on_save(self):
        self.cfg = save(self._collect_settings())

    def _on_save_and_run(self):
        self._on_save()
        try:
            from ui.live import run_live
        except Exception as e:
            print("Cannot import Live:", e); return
        try: self.withdraw()
        except Exception: pass
        try: run_live()
        except Exception as e: print("Live crashed:", e)
        finally:
            try: self.deiconify()
            except Exception: pass

    def _show_stats(self):
        from modules import stats
        import tkinter as tk

        root = Section(self.content, "Statistics")
        root.grid(sticky="ew", pady=(10, 6))
        root.grid_columnconfigure(0, weight=1)

        period = StringVar(value="today")
        accent_option(root, period, ["today", "yesterday", "7d", "30d"]).grid(
            row=1, column=0, padx=16, pady=8, sticky="w"
        )

        cards = ctk.CTkFrame(self.content, fg_color=PALETTE["bg_panel"], corner_radius=14)
        cards.grid(sticky="ew", padx=4, pady=6)
        cards.grid_columnconfigure((0, 1, 2), weight=1)
        lbl_dom = ctk.CTkLabel(cards, text="Dominant: –", text_color=PALETTE["text"])
        lbl_tot = ctk.CTkLabel(cards, text="Total time: 00:00:00", text_color=PALETTE["text"])
        lbl_nf = ctk.CTkLabel(cards, text="No face: –", text_color=PALETTE["text"])
        lbl_dom.grid(row=0, column=0, padx=16, pady=12, sticky="w")
        lbl_tot.grid(row=0, column=1, padx=16, pady=12, sticky="w")
        lbl_nf.grid(row=0, column=2, padx=16, pady=12, sticky="w")

        bg = self.content.cget("fg_color")
        if not bg or bg == "transparent":
            bg = self.cget("fg_color") or "#081423"

        canvas = tk.Canvas(
            self.content,
            height=220,
            bg=bg,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.stats_canvas = canvas
        self._render_job = None

        canvas.grid(sticky="ew", padx=8, pady=8)

        def _period_bounds(tag: str):
            from datetime import datetime, timedelta
            today = datetime.now().date()
            if tag == "today":
                a, b = today, today
            elif tag == "yesterday":
                a, b = today - timedelta(days=1), today - timedelta(days=1)
            elif tag == "7d":
                a, b = today - timedelta(days=6), today
            else:
                a, b = today - timedelta(days=29), today
            return a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")

        def _fmt(seconds: float):
            s = int(seconds);
            h = s // 3600;
            m = (s % 3600) // 60;
            ss = s % 60
            return f"{h:02d}:{m:02d}:{ss:02d}"

        def _export_csv():
            import csv, os
            a, b = _period_bounds(period.get())
            totals = stats.get_range_totals(a, b)
            os.makedirs("sessions/export", exist_ok=True)
            from datetime import datetime as _dt
            path = f"sessions/export/stats_{period.get()}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f);
                w.writerow(["emotion", "seconds"])
                for k, v in sorted(totals.items(), key=lambda x: -x[1]):
                    w.writerow([k, f"{v:.2f}"])
            print("Exported:", path)

        accent_button(self.content, text="Export CSV", command=_export_csv) \
            .grid(sticky="w", padx=16, pady=(0, 10))

        def _render(*_):
            if not canvas.winfo_exists():
                return

            a, b = _period_bounds(period.get())
            totals = stats.get_range_totals(a, b)
            canvas.delete("all")

            if not totals:
                lbl_dom.configure(text="Dominant: –")
                lbl_tot.configure(text="Total time: 00:00:00")
                lbl_nf.configure(text="No face: –")
                return

            total_time = sum(totals.values())
            dominant = max(totals.items(), key=lambda kv: kv[1])[0]
            nf_pct = "–"
            if "noface" in totals and total_time > 1e-6:
                nf_pct = f"{(totals['noface'] / total_time * 100):.0f}%"

            lbl_dom.configure(text=f"Dominant: {dominant}")
            lbl_tot.configure(text=f"Total time: {_fmt(total_time)}")
            lbl_nf.configure(text=f"No face: {nf_pct}")

            keys = [k for k in totals.keys() if k != "noface"] or list(totals.keys())
            values = [totals[k] for k in keys]

            W = max(600, self.content.winfo_width() - 40)
            H = 220
            canvas.configure(width=W, height=H)

            m = 28
            step = (W - 2 * m) / max(1, len(keys))
            bw = max(24, step * 0.7)
            vmax = max(values) if values else 1.0
            x = m
            for k in keys:
                v = totals[k]
                h = 0 if vmax <= 0 else (H - 2 * m) * (v / vmax)
                canvas.create_rectangle(x, H - m - h, x + bw, H - m, fill="#16E0FF", width=0)
                canvas.create_text(x + bw / 2, H - m + 12, text=k, fill="#9fb3c6", font=("Inter", 10))
                canvas.create_text(x + bw / 2, H - m - h - 12, text=_fmt(v), fill="#9fb3c6", font=("Inter", 10))
                x += step

        period.trace_add("write", _render)
        self.bind("<Configure>", _render)
        _render()


def show_settings_gui():
    Dashboard().mainloop()

if __name__ == "__main__":
    show_settings_gui()
