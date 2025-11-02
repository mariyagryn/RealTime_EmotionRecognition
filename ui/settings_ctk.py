# ui/settings_ctk.py
import threading
import customtkinter as ctk
from tkinter import StringVar, BooleanVar, DoubleVar, IntVar

# наші утиліти/фон
from utils.app_settings import load, save
from agent.background import run_background


class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Emotion — Dashboard")
        self.geometry("980x640")

        # тема/кольори
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        # конфіг і стан
        self.cfg = load()
        self.running_thread = None

        # ====== layout (2 колонки: sidebar | content) ======
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        ctk.CTkLabel(self.sidebar, text="🚀 EMOTION", font=("Inter", 18, "bold")).pack(padx=16, pady=(20, 8))

        btn_specs = [
            ("Dashboard",        self._show_dashboard),
            ("Devices",          self._show_devices),
            ("Behavior & Rules", self._show_rules),
            ("Privacy",          self._show_privacy),
            ("Performance",      self._show_perf),
            ("TTS & Language",   self._show_tts_lang),
            ("Statistics",       self._show_stats),
            ("Help / About",     self._show_help),
        ]
        for text, fn in btn_specs:
            ctk.CTkButton(self.sidebar, text=text, command=fn).pack(padx=16, pady=6, fill="x")

        # --- Content
        self.content = ctk.CTkFrame(self)
        self.content.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # --- Bottom actions
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
        bottom.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(bottom, text="Save",
                      command=self._on_save).grid(row=0, column=1, padx=6, sticky="e")
        ctk.CTkButton(bottom, text="Save & Run in Background",
                      command=self._on_save_and_run).grid(row=0, column=2, padx=6, sticky="w")
        ctk.CTkButton(bottom, text="Cancel", fg_color="#444", hover_color="#555",
                      command=self.destroy).grid(row=0, column=3, padx=6, sticky="w")

        # стартова сторінка
        self._show_dashboard()

    # ========== SERVICE/HELPERS ==========
    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _bind_bool(self, key):  return BooleanVar(value=bool(self.cfg.get(key)))
    def _bind_str(self, key):   return StringVar(value=str(self.cfg.get(key)))
    def _bind_float(self, key): return DoubleVar(value=float(self.cfg.get(key)))
    def _bind_int(self, key):   return IntVar(value=int(self.cfg.get(key)))

    def _L(self, parent, text, r, c=0, **kw):
        ctk.CTkLabel(parent, text=text, **kw).grid(row=r, column=c, sticky="w", padx=16, pady=8)

    # lazy-import прев’ю, щоб не тягнути cv2 на старті
    def _open_preview(self):
        try:
            from ui.preview import run_preview  # імпорт тут
            # опційно сховати вікно на час прев’ю
            try: self.withdraw()
            except Exception: pass
            run_preview()
        except Exception:
            import traceback; traceback.print_exc()
        finally:
            try: self.deiconify()
            except Exception: pass

    def _open_preview_threaded(self):
        try:
            from ui.preview import run_preview
            run_preview()
        except Exception:
            import traceback; traceback.print_exc()

    # ========== PAGES ==========
    def _show_dashboard(self):
        self._clear_content()
        f = ctk.CTkFrame(self.content)
        f.grid(sticky="nsew")
        f.grid_columnconfigure((0, 1), weight=1)

        # Background mode
        self.v_bg = self._bind_bool("background_mode")
        ctk.CTkSwitch(f, text="Background Mode (run in tray)", variable=self.v_bg)\
            .grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6), columnspan=2)

        # Quick tips (rules)
        self.v_rule_b  = self._bind_bool("rule_breathing")
        self.v_rule_p  = self._bind_bool("rule_pomodoro")
        self.v_rule_m  = self._bind_bool("rule_mirror")
        self.v_rule_sp = self._bind_bool("rule_speech")

        block = ctk.CTkFrame(f); block.grid(row=1, column=0, sticky="nsew", padx=8, pady=8, columnspan=2)
        self._L(block, "Enable tips:", 0, 0, font=("Inter", 14, "bold"))
        ctk.CTkCheckBox(block, text="Breathing",     variable=self.v_rule_b).grid(row=1, column=0, padx=16, pady=4, sticky="w")
        ctk.CTkCheckBox(block, text="Pomodoro",      variable=self.v_rule_p).grid(row=1, column=1, padx=16, pady=4, sticky="w")
        ctk.CTkCheckBox(block, text="Mirror",        variable=self.v_rule_m).grid(row=2, column=0, padx=16, pady=4, sticky="w")
        ctk.CTkCheckBox(block, text="Speech Light",  variable=self.v_rule_sp).grid(row=2, column=1, padx=16, pady=4, sticky="w")

        # Privacy (квік)
        self.v_stats  = self._bind_bool("privacy_save_stats")
        self.v_frames = self._bind_bool("privacy_save_frames")
        self.v_blur   = self._bind_bool("privacy_blur")

        p = ctk.CTkFrame(f); p.grid(row=2, column=0, sticky="nsew", padx=8, pady=8, columnspan=2)
        self._L(p, "Privacy:", 0, 0, font=("Inter", 14, "bold"))
        ctk.CTkCheckBox(p, text="Save statistics (events.jsonl)", variable=self.v_stats)\
            .grid(row=1, column=0, padx=16, pady=4, sticky="w")
        ctk.CTkCheckBox(p, text="Save frames (OFF by default)",   variable=self.v_frames)\
            .grid(row=1, column=1, padx=16, pady=4, sticky="w")
        ctk.CTkCheckBox(p, text="Blur faces in preview",          variable=self.v_blur)\
            .grid(row=2, column=0, padx=16, pady=4, sticky="w")

        # Performance (квік)
        self.v_detector   = self._bind_str("detector")
        self.v_resolution = self._bind_str("resolution")
        self.v_every      = self._bind_float("analyze_every")
        self.v_ema        = self._bind_float("ema")

        perf = ctk.CTkFrame(f); perf.grid(row=3, column=0, sticky="nsew", padx=8, pady=8, columnspan=2)
        self._L(perf, "Performance:", 0, 0, font=("Inter", 14, "bold"))
        self._L(perf, "Detector", 1)
        ctk.CTkOptionMenu(perf, values=["opencv", "mediapipe", "retinaface"], variable=self.v_detector)\
            .grid(row=1, column=1, padx=16, pady=4, sticky="ew")

        self._L(perf, "Resolution", 2)
        ctk.CTkOptionMenu(perf, values=["320x180", "480x270", "640x360"], variable=self.v_resolution)\
            .grid(row=2, column=1, padx=16, pady=4, sticky="ew")

        lbl_every = ctk.CTkLabel(perf, text=f"Analyze Every (s): {self.v_every.get():.1f}")
        lbl_every.grid(row=3, column=0, sticky="w", padx=16, pady=4)
        s_every = ctk.CTkSlider(perf, from_=0.6, to=2.0, number_of_steps=14, variable=self.v_every)
        s_every.grid(row=3, column=1, sticky="ew", padx=16, pady=4)
        s_every.configure(command=lambda v: lbl_every.configure(text=f"Analyze Every (s): {float(v):.1f}"))

        lbl_ema = ctk.CTkLabel(perf, text=f"EMA (smoothing): {self.v_ema.get():.2f}")
        lbl_ema.grid(row=4, column=0, sticky="w", padx=16, pady=4)
        s_ema = ctk.CTkSlider(perf, from_=0.10, to=0.90, number_of_steps=80, variable=self.v_ema)
        s_ema.grid(row=4, column=1, sticky="ew", padx=16, pady=4)
        s_ema.configure(command=lambda v: lbl_ema.configure(text=f"EMA (smoothing): {float(v):.2f}"))

        # TTS / Language / Theme + кнопка прев’ю
        self.v_tts   = self._bind_bool("tts_enabled")
        self.v_lang  = self._bind_str("language")
        self.v_theme = self._bind_str("theme")

        t = ctk.CTkFrame(f)
        t.grid(row=4, column=0, sticky="nsew", padx=8, pady=8, columnspan=2)

        ctk.CTkCheckBox(t, text="TTS Enabled", variable=self.v_tts).grid(row=0, column=0, padx=16, pady=4, sticky="w")

        self._L(t, "Language", 1)
        ctk.CTkOptionMenu(t, values=["UA", "EN"], variable=self.v_lang)\
            .grid(row=1, column=1, padx=16, pady=4, sticky="ew")

        self._L(t, "Theme", 2)
        ctk.CTkOptionMenu(t, values=["Dark", "Light"], variable=self.v_theme)\
            .grid(row=2, column=1, padx=16, pady=4, sticky="ew")

        # ✅ кнопка прев’ю (батько = t)
        ctk.CTkButton(
            t,
            text="Open Camera Preview",
            command=self._open_preview
        ).grid(row=3, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="ew")

    def _show_devices(self):
        self._clear_content()
        f = ctk.CTkFrame(self.content)
        f.grid(sticky="nsew")
        f.grid_columnconfigure((0, 1), weight=1)

        # Camera
        self.v_cam = self._bind_int("camera_index")
        self._L(f, "Camera index", 0)
        ctk.CTkOptionMenu(f, values=[str(i) for i in range(0, 5)], variable=self.v_cam)\
            .grid(row=0, column=1, padx=16, pady=8, sticky="ew")

        ctk.CTkButton(
            f, text="Open Preview",
            command=lambda: threading.Thread(target=self._open_preview_threaded, daemon=True).start()
        ).grid(row=1, column=1, padx=16, pady=8, sticky="e")

        # Mic
        self.v_mic = self._bind_str("mic_device")
        self._L(f, "Microphone (device name)", 2)
        ctk.CTkEntry(f, textvariable=self.v_mic).grid(row=2, column=1, padx=16, pady=8, sticky="ew")

        self.v_gain = self._bind_float("mic_gain")
        self._L(f, f"Mic gain: {self.v_gain.get():.2f}", 3)
        s = ctk.CTkSlider(f, from_=0.2, to=2.0, number_of_steps=18, variable=self.v_gain)
        s.grid(row=3, column=1, padx=16, pady=8, sticky="ew")
        s.configure(command=lambda v: [w.configure(text=f"Mic gain: {float(v):.2f}") for w in f.grid_slaves(row=3, column=0)])

    def _show_rules(self):
        self._clear_content()
        f = ctk.CTkFrame(self.content); f.grid(sticky="nsew"); f.grid_columnconfigure((0, 1), weight=1)

        # toggles
        self.v_rule_b  = self._bind_bool("rule_breathing")
        self.v_rule_p  = self._bind_bool("rule_pomodoro")
        self.v_rule_m  = self._bind_bool("rule_mirror")
        self.v_rule_sp = self._bind_bool("rule_speech")

        ctk.CTkCheckBox(f, text="Enable Breathing",     variable=self.v_rule_b).grid(row=0, column=0, padx=16, pady=6, sticky="w")
        ctk.CTkCheckBox(f, text="Enable Pomodoro",      variable=self.v_rule_p).grid(row=0, column=1, padx=16, pady=6, sticky="w")
        ctk.CTkCheckBox(f, text="Enable Mirror",        variable=self.v_rule_m).grid(row=1, column=0, padx=16, pady=6, sticky="w")
        ctk.CTkCheckBox(f, text="Enable Speech Light",  variable=self.v_rule_sp).grid(row=1, column=1, padx=16, pady=6, sticky="w")

        # thresholds
        self.v_sad = self._bind_int("rule_sad_sec")
        self.v_ang = self._bind_int("rule_angry_sec")
        self.v_neu = self._bind_int("rule_neutral_sec")
        self.v_nf  = self._bind_int("rule_noface_pct")
        self.v_cd  = self._bind_int("rule_cooldown_min")

        def row(r, label, var, suffix="s"):
            self._L(f, label, r)
            ctk.CTkEntry(f, textvariable=var).grid(row=r, column=1, padx=16, pady=6, sticky="ew")
            ctk.CTkLabel(f, text=suffix).grid(row=r, column=2, padx=6, sticky="w")

        row(2, "sad ≥ ",     self.v_sad)
        row(3, "angry ≥ ",   self.v_ang)
        row(4, "neutral ≥ ", self.v_neu)
        row(5, "noface ≥ ",  self.v_nf, "%")
        row(6, "cooldown",   self.v_cd, "min")

    def _show_privacy(self):
        self._clear_content()
        f = ctk.CTkFrame(self.content); f.grid(sticky="nsew")

        self.v_stats  = self._bind_bool("privacy_save_stats")
        self.v_frames = self._bind_bool("privacy_save_frames")
        self.v_blur   = self._bind_bool("privacy_blur")

        ctk.CTkCheckBox(f, text="Save statistics (events.jsonl)", variable=self.v_stats).pack(anchor="w", padx=16, pady=8)
        ctk.CTkCheckBox(f, text="Save frames (OFF by default)",   variable=self.v_frames).pack(anchor="w", padx=16, pady=8)
        ctk.CTkCheckBox(f, text="Blur faces in preview",          variable=self.v_blur).pack(anchor="w", padx=16, pady=8)

    def _show_perf(self):
        self._clear_content()
        f = ctk.CTkFrame(self.content); f.grid(sticky="nsew"); f.grid_columnconfigure((0, 1), weight=1)

        self.v_detector   = self._bind_str("detector")
        self.v_resolution = self._bind_str("resolution")
        self.v_every      = self._bind_float("analyze_every")
        self.v_ema        = self._bind_float("ema")

        self._L(f, "Detector", 0)
        ctk.CTkOptionMenu(f, values=["opencv", "mediapipe", "retinaface"], variable=self.v_detector)\
            .grid(row=0, column=1, padx=16, pady=8, sticky="ew")

        self._L(f, "Resolution", 1)
        ctk.CTkOptionMenu(f, values=["320x180", "480x270", "640x360"], variable=self.v_resolution)\
            .grid(row=1, column=1, padx=16, pady=8, sticky="ew")

        lbl_every = ctk.CTkLabel(f, text=f"Analyze Every (s): {self.v_every.get():.1f}")
        lbl_every.grid(row=2, column=0, padx=16, pady=8, sticky="w")
        s_every = ctk.CTkSlider(f, from_=0.6, to=2.0, number_of_steps=14, variable=self.v_every)
        s_every.grid(row=2, column=1, padx=16, pady=8, sticky="ew")
        s_every.configure(command=lambda v: lbl_every.configure(text=f"Analyze Every (s): {float(v):.1f}"))

        lbl_ema = ctk.CTkLabel(f, text=f"EMA (smoothing): {self.v_ema.get():.2f}")
        lbl_ema.grid(row=3, column=0, padx=16, pady=8, sticky="w")
        s_ema = ctk.CTkSlider(f, from_=0.10, to=0.90, number_of_steps=80, variable=self.v_ema)
        s_ema.grid(row=3, column=1, padx=16, pady=8, sticky="ew")
        s_ema.configure(command=lambda v: lbl_ema.configure(text=f"EMA (smoothing): {float(v):.2f}"))

    def _show_tts_lang(self):
        self._clear_content()
        f = ctk.CTkFrame(self.content); f.grid(sticky="nsew")

        self.v_tts   = self._bind_bool("tts_enabled")
        self.v_lang  = self._bind_str("language")
        self.v_theme = self._bind_str("theme")

        ctk.CTkCheckBox(f, text="TTS Enabled", variable=self.v_tts).pack(anchor="w", padx=16, pady=8)

        row = ctk.CTkFrame(f); row.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(row, text="Language", width=140).pack(side="left", padx=8)
        ctk.CTkOptionMenu(row, values=["UA", "EN"], variable=self.v_lang).pack(side="left", padx=8)

        row2 = ctk.CTkFrame(f); row2.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(row2, text="Theme", width=140).pack(side="left", padx=8)
        ctk.CTkOptionMenu(row2, values=["Dark", "Light"], variable=self.v_theme).pack(side="left", padx=8)

    def _show_stats(self):
        self._clear_content()
        f = ctk.CTkFrame(self.content); f.grid(sticky="nsew")
        ctk.CTkLabel(f, text="Statistics & Exports (soon)", font=("Inter", 16, "bold")).pack(padx=16, pady=16)
        ctk.CTkButton(f, text="Open Sessions Folder (soon)", state="disabled").pack(padx=16, pady=8)

    def _show_help(self):
        self._clear_content()
        f = ctk.CTkFrame(self.content); f.grid(sticky="nsew")
        help_txt = (
            "• Agent runs in background and proposes micro-breaks via notifications.\n"
            "• Hotkeys (planned): Pause/Resume Agent, Open Dashboard.\n"
            "• Data: sessions/<id>/events.jsonl, summary.json; logs/app.log.\n"
            "• Privacy: frames are OFF by default."
        )
        ctk.CTkLabel(f, text="Help / About", font=("Inter", 16, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(f, text=help_txt, justify="left").pack(anchor="w", padx=16, pady=8)

    # ========== SAVE / RUN ==========
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
            "rule_pomodoro":  self.v_rule_p.get(),
            "rule_mirror":    self.v_rule_m.get(),
            "rule_speech":    self.v_rule_sp.get(),

            "rule_sad_sec":     int(getattr(self, "v_sad",  self.cfg.get("rule_sad_sec", 60)).get()) if isinstance(getattr(self, "v_sad", None), IntVar) else int(self.cfg.get("rule_sad_sec", 60)),
            "rule_angry_sec":   int(getattr(self, "v_ang",  self.cfg.get("rule_angry_sec", 30)).get()) if isinstance(getattr(self, "v_ang", None), IntVar) else int(self.cfg.get("rule_angry_sec", 30)),
            "rule_neutral_sec": int(getattr(self, "v_neu",  self.cfg.get("rule_neutral_sec", 120)).get()) if isinstance(getattr(self, "v_neu", None), IntVar) else int(self.cfg.get("rule_neutral_sec", 120)),
            "rule_noface_pct":  int(getattr(self, "v_nf",   self.cfg.get("rule_noface_pct", 40)).get()) if isinstance(getattr(self, "v_nf", None), IntVar) else int(self.cfg.get("rule_noface_pct", 40)),
            "rule_cooldown_min":int(getattr(self, "v_cd",   self.cfg.get("rule_cooldown_min", 30)).get()) if isinstance(getattr(self, "v_cd", None), IntVar) else int(self.cfg.get("rule_cooldown_min", 30)),

            "camera_index": int(getattr(self, "v_cam", self.cfg.get("camera_index", 0)).get()) if isinstance(getattr(self, "v_cam", None), IntVar) else int(self.cfg.get("camera_index", 0)),
            "mic_device":   getattr(self, "v_mic",  StringVar(value=self.cfg.get("mic_device", ""))).get(),
            "mic_gain":     float(getattr(self, "v_gain", DoubleVar(value=self.cfg.get("mic_gain", 1.0))).get()),
        }

    def _on_save(self):
        self.cfg = save(self._collect_settings())

    def _on_save_and_run(self):
        self._on_save()
        self._run_emotion_analysis()

    def _run_emotion_analysis(self):
        """Запустити Emotion Analysis (FER) після збереження налаштувань."""
        try:
            # лінивий імпорт, щоб не тягнути cv2 при старті дашборду
            from ui.live import run_live
        except Exception as e:
            import traceback;
            traceback.print_exc()
            return

        # сховаємо дашборд на час Live-вікна
        try:
            self.withdraw()
        except:
            pass

        try:
            run_live()
        finally:
            try:
                self.deiconify()
            except:
                pass


def show_settings_gui():
    Dashboard().mainloop()


if __name__ == "__main__":
    show_settings_gui()
