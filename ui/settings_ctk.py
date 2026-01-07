# # ui/settings_ctk.py
# from __future__ import annotations
#
# import tkinter as tk
# import customtkinter as ctk
# from tkinter import messagebox
#
# from utils.app_settings import load as load_cfg, save as save_cfg
#
# PALETTE = {
#     "bg": "#020617",
#     "panel": "#020617",
#     "accent": "#00D1FF",
#     "accent_h": "#16E0FF",
#     "text": "#E8F1FF",
#     "muted": "#94a3b8",
#     "border": "#16324a",
# }
#
#
# class SettingsPanel(ctk.CTkFrame):
#     """
#     Панель налаштувань для вкладки Settings у головному вікні.
#     Ліва колонка – навігація, справа – різні секції (Dashboard, Devices, ...).
#     """
#
#     def __init__(self, master, **kwargs):
#         super().__init__(master, fg_color=PALETTE["bg"], **kwargs)
#
#         self.cfg = load_cfg()
#         self.lang = str(self.cfg.get("language", "UA")).upper()
#
#         self.grid_columnconfigure(0, weight=0)   # sidebar
#         self.grid_columnconfigure(1, weight=1)   # content
#         self.grid_rowconfigure(0, weight=1)
#
#         self._init_vars()
#         self._build_ui()
#
#     # ---------- state ----------
#     def _init_vars(self):
#         c = self.cfg
#
#         self.var_breathing = tk.BooleanVar(value=bool(c.get("rule_breathing", True)))
#         self.var_pomodoro = tk.BooleanVar(value=bool(c.get("rule_pomodoro", True)))
#         self.var_mirror = tk.BooleanVar(value=bool(c.get("rule_mirror", True)))
#         self.var_speech = tk.BooleanVar(value=bool(c.get("rule_speech", True)))
#
#         self.var_save_stats = tk.BooleanVar(value=bool(c.get("save_stats", True)))
#         self.var_save_frames = tk.BooleanVar(value=bool(c.get("save_frames", False)))
#         self.var_blur_faces = tk.BooleanVar(value=bool(c.get("blur_faces", False)))
#
#         res_default = str(c.get("resolution", "320x180"))
#         if "x" not in res_default:
#             res_default = "320x180"
#         self.var_resolution = tk.StringVar(value=res_default)
#
#         self.var_analyze_every = tk.DoubleVar(
#             value=float(c.get("analyze_every", 1.0))
#         )
#         self.var_ema = tk.DoubleVar(value=float(c.get("ema_smoothing", 0.32)))
#
#         self.var_tts = tk.BooleanVar(value=bool(c.get("tts_enabled", False)))
#         self.var_language = tk.StringVar(value=str(c.get("language", "UA")).upper())
#         theme_default = str(c.get("theme", "Dark")).capitalize()
#         self.var_theme = tk.StringVar(
#             value="Light" if theme_default.lower().startswith("light") else "Dark"
#         )
#
#     # ---------- layout ----------
#     def _build_ui(self):
#         # ----- sidebar -----
#         self.sidebar = ctk.CTkFrame(
#             self, fg_color=PALETTE["panel"], corner_radius=18
#         )
#         self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(16, 10), pady=(16, 24))
#         for i in range(10):
#             self.sidebar.grid_rowconfigure(i, weight=0)
#         self.sidebar.grid_rowconfigure(99, weight=1)
#
#         self._nav_buttons: dict[str, ctk.CTkButton] = {}
#
#         nav_items = [
#             ("Dashboard", "dashboard"),
#             ("Devices", "devices"),
#             ("Behavior & Rules", "rules"),
#             ("Privacy", "privacy"),
#             ("Performance", "performance"),
#             ("TTS & Language", "tts"),
#             ("Statistics", "statistics"),
#             ("Help / About", "help"),
#         ]
#
#         for i, (text, key) in enumerate(nav_items):
#             btn = ctk.CTkButton(
#                 self.sidebar,
#                 text=text,
#                 width=160,
#                 height=32,
#                 corner_radius=999,
#                 fg_color="transparent",
#                 hover_color="#0f172a",
#                 text_color=PALETTE["text"],
#                 border_width=0,
#                 anchor="w",
#                 font=("Inter", 13),
#                 command=lambda k=key: self._switch_section(k),
#             )
#             btn.grid(row=i, column=0, padx=10, pady=4, sticky="ew")
#             self._nav_buttons[key] = btn
#
#         # ----- content container -----
#         self.content = ctk.CTkFrame(
#             self, fg_color="transparent", corner_radius=0
#         )
#         self.content.grid(row=0, column=1, sticky="nsew", padx=(4, 24), pady=(16, 24))
#         self.content.grid_columnconfigure(0, weight=1)
#         self.content.grid_rowconfigure(0, weight=1)
#
#         # створюємо окремі фрейми-секції (поки що реальний контент тільки в Dashboard;
#         # решта – плейсхолдери, щоб було видно, що контент міняється)
#         self._sections: dict[str, ctk.CTkFrame] = {}
#         self._sections["dashboard"] = self._build_dashboard_section()
#         self._sections["devices"] = self._build_placeholder_section("Devices")
#         self._sections["rules"] = self._build_placeholder_section("Behavior & Rules")
#         self._sections["privacy"] = self._build_placeholder_section("Privacy")
#         self._sections["performance"] = self._build_placeholder_section("Performance")
#         self._sections["tts"] = self._build_placeholder_section("TTS & Language")
#         self._sections["statistics"] = self._build_placeholder_section("Statistics")
#         self._sections["help"] = self._build_placeholder_section("Help / About")
#
#         self._current_section: str | None = None
#         self._switch_section("dashboard")
#
#     # ---------- sections ----------
#     def _build_dashboard_section(self) -> ctk.CTkFrame:
#         """Основний дашборд (як на скріні)."""
#         root = ctk.CTkFrame(
#             self.content,
#             fg_color=PALETTE["panel"],
#             corner_radius=22,
#         )
#         root.grid_columnconfigure(0, weight=1)
#
#         # Enable tips
#         tips_block = ctk.CTkFrame(
#             root,
#             fg_color="#020617",
#             corner_radius=18,
#         )
#         tips_block.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 10))
#         tips_block.grid_columnconfigure((0, 1, 2, 3), weight=0)
#
#         title = "Enable tips" if self.lang == "EN" else "Увімкнути підказки"
#         ctk.CTkLabel(
#             tips_block,
#             text=title,
#             font=("Inter", 13, "bold"),
#             text_color=PALETTE["text"],
#         ).grid(row=0, column=0, columnspan=4, padx=16, pady=(10, 6), sticky="w")
#
#         def tip_label(txt):
#             if self.lang == "EN":
#                 return txt
#             mapping = {
#                 "Breathing": "Breathing",
#                 "Pomodoro": "Pomodoro",
#                 "Mirror": "Mirror",
#                 "Speech Light": "Speech Light",
#             }
#             return mapping.get(txt, txt)
#
#         ctk.CTkCheckBox(
#             tips_block,
#             text=tip_label("Breathing"),
#             variable=self.var_breathing,
#         ).grid(row=1, column=0, padx=(16, 12), pady=(4, 10), sticky="w")
#
#         ctk.CTkCheckBox(
#             tips_block,
#             text=tip_label("Pomodoro"),
#             variable=self.var_pomodoro,
#         ).grid(row=1, column=1, padx=(0, 12), pady=(4, 10), sticky="w")
#
#         ctk.CTkCheckBox(
#             tips_block,
#             text=tip_label("Mirror"),
#             variable=self.var_mirror,
#         ).grid(row=1, column=2, padx=(0, 12), pady=(4, 10), sticky="w")
#
#         ctk.CTkCheckBox(
#             tips_block,
#             text=tip_label("Speech Light"),
#             variable=self.var_speech,
#         ).grid(row=1, column=3, padx=(0, 16), pady=(4, 10), sticky="w")
#
#         # Data & privacy
#         stats_block = ctk.CTkFrame(
#             root,
#             fg_color="#020617",
#             corner_radius=18,
#         )
#         stats_block.grid(row=1, column=0, sticky="ew", padx=24, pady=8)
#         stats_block.grid_columnconfigure(0, weight=1)
#
#         label_stats_title = (
#             "Data & privacy" if self.lang == "EN" else "Дані та приватність"
#         )
#         ctk.CTkLabel(
#             stats_block,
#             text=label_stats_title,
#             font=("Inter", 13, "bold"),
#             text_color=PALETTE["text"],
#         ).grid(row=0, column=0, padx=16, pady=(10, 4), sticky="w")
#
#         label_stats = (
#             "Save statistics (events.jsonl)"
#             if self.lang == "EN"
#             else "Зберігати статистику (events.jsonl)"
#         )
#
#         ctk.CTkCheckBox(
#             stats_block,
#             text=label_stats,
#             variable=self.var_save_stats,
#         ).grid(row=1, column=0, padx=16, pady=(4, 4), sticky="w")
#
#         ctk.CTkCheckBox(
#             stats_block,
#             text="Save frames (OFF by default)"
#             if self.lang == "EN"
#             else "Зберігати кадри (за замовчуванням ВИМК.)",
#             variable=self.var_save_frames,
#         ).grid(row=2, column=0, padx=16, pady=4, sticky="w")
#
#         ctk.CTkCheckBox(
#             stats_block,
#             text="Blur faces in preview"
#             if self.lang == "EN"
#             else "Розмивати обличчя у превʼю",
#             variable=self.var_blur_faces,
#         ).grid(row=3, column=0, padx=16, pady=(4, 10), sticky="w")
#
#         # Performance
#         perf_block = ctk.CTkFrame(
#             root,
#             fg_color="#020617",
#             corner_radius=18,
#         )
#         perf_block.grid(row=2, column=0, sticky="ew", padx=24, pady=8)
#         perf_block.grid_columnconfigure(1, weight=1)
#
#         title_perf = "Performance" if self.lang == "EN" else "Продуктивність"
#         ctk.CTkLabel(
#             perf_block,
#             text=title_perf,
#             font=("Inter", 13, "bold"),
#             text_color=PALETTE["text"],
#         ).grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 6), sticky="w")
#
#         # Detector
#         ctk.CTkLabel(
#             perf_block,
#             text="Detector",
#             font=("Inter", 11),
#             text_color=PALETTE["muted"],
#         ).grid(row=1, column=0, padx=16, pady=4, sticky="w")
#         ctk.CTkLabel(
#             perf_block,
#             text=str(self.cfg.get("backend", "opencv")),
#             font=("Inter", 11),
#             text_color=PALETTE["text"],
#         ).grid(row=1, column=1, padx=16, pady=4, sticky="w")
#
#         # Resolution
#         ctk.CTkLabel(
#             perf_block,
#             text="Resolution",
#             font=("Inter", 11),
#             text_color=PALETTE["muted"],
#         ).grid(row=2, column=0, padx=16, pady=4, sticky="w")
#
#         res_menu = ctk.CTkOptionMenu(
#             perf_block,
#             values=["320x180", "480x270", "640x360", "1280x720"],
#             variable=self.var_resolution,
#             fg_color="#020617",
#             button_color="#0b1b30",
#             button_hover_color="#111827",
#             text_color=PALETTE["text"],
#             width=110,
#             corner_radius=14,
#         )
#         res_menu.grid(row=2, column=1, padx=16, pady=4, sticky="w")
#
#         # Analyze every
#         label_an = (
#             "Analyze every (s)"
#             if self.lang == "EN"
#             else "Аналізувати кожні (с)"
#         )
#         ctk.CTkLabel(
#             perf_block,
#             text=label_an,
#             font=("Inter", 11),
#             text_color=PALETTE["muted"],
#         ).grid(row=3, column=0, padx=16, pady=(8, 2), sticky="w")
#
#         self.slider_analyze = ctk.CTkSlider(
#             perf_block,
#             from_=0.4,
#             to=2.5,
#             number_of_steps=21,
#             variable=self.var_analyze_every,
#         )
#         self.slider_analyze.grid(
#             row=3, column=1, padx=16, pady=(8, 2), sticky="ew"
#         )
#
#         # EMA
#         label_ema = (
#             "EMA (smoothing)"
#             if self.lang == "EN"
#             else "EMA (згладжування)"
#         )
#         ctk.CTkLabel(
#             perf_block,
#             text=label_ema,
#             font=("Inter", 11),
#             text_color=PALETTE["muted"],
#         ).grid(row=4, column=0, padx=16, pady=(6, 4), sticky="w")
#
#         self.slider_ema = ctk.CTkSlider(
#             perf_block,
#             from_=0.05,
#             to=0.9,
#             number_of_steps=17,
#             variable=self.var_ema,
#         )
#         self.slider_ema.grid(
#             row=4, column=1, padx=16, pady=(6, 12), sticky="ew"
#         )
#
#         # TTS & language
#         tts_block = ctk.CTkFrame(
#             root,
#             fg_color="#020617",
#             corner_radius=18,
#         )
#         tts_block.grid(row=3, column=0, sticky="ew", padx=24, pady=(8, 18))
#         tts_block.grid_columnconfigure(1, weight=1)
#
#         ctk.CTkLabel(
#             tts_block,
#             text="TTS & language" if self.lang == "EN" else "Озвучка та мова",
#             font=("Inter", 13, "bold"),
#             text_color=PALETTE["text"],
#         ).grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 6), sticky="w")
#
#         ctk.CTkCheckBox(
#             tts_block,
#             text="TTS enabled" if self.lang == "EN" else "Увімкнути TTS",
#             variable=self.var_tts,
#         ).grid(row=1, column=0, padx=16, pady=(4, 8), sticky="w")
#
#         # Language
#         ctk.CTkLabel(
#             tts_block,
#             text="Language",
#             font=("Inter", 11),
#             text_color=PALETTE["muted"],
#         ).grid(row=2, column=0, padx=16, pady=4, sticky="w")
#
#         lang_menu = ctk.CTkOptionMenu(
#             tts_block,
#             values=["UA", "EN"],
#             variable=self.var_language,
#             fg_color="#020617",
#             button_color="#0b1b30",
#             button_hover_color="#111827",
#             text_color=PALETTE["text"],
#             width=80,
#             corner_radius=14,
#         )
#         lang_menu.grid(row=2, column=1, padx=16, pady=4, sticky="w")
#
#         # Theme
#         ctk.CTkLabel(
#             tts_block,
#             text="Theme",
#             font=("Inter", 11),
#             text_color=PALETTE["muted"],
#         ).grid(row=3, column=0, padx=16, pady=(4, 12), sticky="w")
#
#         theme_menu = ctk.CTkOptionMenu(
#             tts_block,
#             values=["Dark", "Light"],
#             variable=self.var_theme,
#             fg_color="#020617",
#             button_color="#0b1b30",
#             button_hover_color="#111827",
#             text_color=PALETTE["text"],
#             width=80,
#             corner_radius=14,
#         )
#         theme_menu.grid(row=3, column=1, padx=16, pady=(4, 12), sticky="w")
#
#         # Save buttons
#         btn_row = ctk.CTkFrame(root, fg_color="transparent")
#         btn_row.grid(row=4, column=0, padx=24, pady=(0, 18), sticky="e")
#
#         save_txt = "Save" if self.lang == "EN" else "Зберегти"
#         save_bg_txt = (
#             "Save & Run in Background"
#             if self.lang == "EN"
#             else "Зберегти й запустити в фоні"
#         )
#
#         btn_save = ctk.CTkButton(
#             btn_row,
#             text=save_txt,
#             fg_color=PALETTE["accent"],
#             hover_color=PALETTE["accent_h"],
#             text_color="#020617",
#             corner_radius=18,
#             width=140,
#             command=self._on_save,
#         )
#         btn_save.pack(side="right", padx=(8, 0))
#
#         btn_bg = ctk.CTkButton(
#             btn_row,
#             text=save_bg_txt,
#             fg_color="#0b1b30",
#             hover_color="#111827",
#             text_color=PALETTE["text"],
#             corner_radius=18,
#             width=200,
#             command=lambda: self._on_save(run_in_background=True),
#         )
#         btn_bg.pack(side="right", padx=(0, 8))
#
#         return root
#
#     def _build_placeholder_section(self, title: str) -> ctk.CTkFrame:
#         """Проста заглушка для інших пунктів меню, щоб було видно, що контент міняється."""
#         frame = ctk.CTkFrame(
#             self.content,
#             fg_color=PALETTE["panel"],
#             corner_radius=22,
#         )
#         frame.grid_columnconfigure(0, weight=1)
#         frame.grid_rowconfigure(0, weight=1)
#
#         txt = title
#         if self.lang != "EN":
#             # можна при бажанні перекласти, але не обов'язково
#             pass
#
#         ctk.CTkLabel(
#             frame,
#             text=txt,
#             font=("Inter", 18, "bold"),
#             text_color=PALETTE["text"],
#         ).grid(row=0, column=0, padx=24, pady=(24, 8), sticky="nw")
#
#         sub = (
#             "This section is not customized yet. "
#             "Main settings are available on the Dashboard."
#             if self.lang == "EN"
#             else "Ця секція поки що без окремих налаштувань. "
#                  "Основні параметри знаходяться на вкладці Dashboard."
#         )
#         ctk.CTkLabel(
#             frame,
#             text=sub,
#             font=("Inter", 12),
#             text_color=PALETTE["muted"],
#             wraplength=600,
#             justify="left",
#         ).grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nw")
#
#         return frame
#
#     # ---------- logic ----------
#     def _switch_section(self, key: str):
#         """Переключити видиму секцію справа + оновити стиль кнопок."""
#         if key == self._current_section:
#             return
#
#         # ховаємо всі секції
#         for f in self._sections.values():
#             f.grid_forget()
#
#         # показуємо потрібну
#         frame = self._sections.get(key)
#         if frame is not None:
#             frame.grid(row=0, column=0, sticky="nsew")
#
#         # оновлюємо стилі кнопок
#         for k, btn in self._nav_buttons.items():
#             if k == key:
#                 btn.configure(
#                     fg_color=PALETTE["accent"],
#                     text_color="#020617",
#                     font=("Inter", 13, "bold"),
#                 )
#             else:
#                 btn.configure(
#                     fg_color="transparent",
#                     text_color=PALETTE["text"],
#                     font=("Inter", 13),
#                 )
#
#         self._current_section = key
#
#     def _on_save(self, run_in_background: bool = False):
#         cfg = load_cfg()
#
#         cfg["rule_breathing"] = bool(self.var_breathing.get())
#         cfg["rule_pomodoro"] = bool(self.var_pomodoro.get())
#         cfg["rule_mirror"] = bool(self.var_mirror.get())
#         cfg["rule_speech"] = bool(self.var_speech.get())
#
#         cfg["save_stats"] = bool(self.var_save_stats.get())
#         cfg["save_frames"] = bool(self.var_save_frames.get())
#         cfg["blur_faces"] = bool(self.var_blur_faces.get())
#
#         cfg["resolution"] = self.var_resolution.get()
#         cfg["analyze_every"] = float(self.var_analyze_every.get())
#         cfg["ema_smoothing"] = float(self.var_ema.get())
#
#         cfg["tts_enabled"] = bool(self.var_tts.get())
#         cfg["language"] = self.var_language.get().upper()
#         cfg["theme"] = (
#             "Light"
#             if self.var_theme.get().lower().startswith("light")
#             else "Dark"
#         )
#
#         save_cfg(cfg)
#
#         msg = (
#             "Settings saved. Most changes will apply to new sessions."
#             if self.lang == "EN"
#             else "Налаштування збережено. Більшість змін застосуються під час нових сесій."
#         )
#         messagebox.showinfo("Settings", msg)
#
#         if run_in_background:
#             # тут потім можна буде додати логіку запуску в трей
#             pass
#
#
# # ---- окремий запуск (не обов'язково використовувати) ----
# def show_settings_gui():
#     ctk.set_default_color_theme("dark-blue")
#     ctk.set_appearance_mode("dark")
#
#     root = ctk.CTk()
#     root.title("Emotion — Dashboard")
#     root.geometry("1100x720+80+60")
#     root.grid_columnconfigure(0, weight=1)
#     root.grid_rowconfigure(0, weight=1)
#
#     panel = SettingsPanel(root)
#     panel.grid(row=0, column=0, sticky="nsew")
#
#     root.mainloop()
