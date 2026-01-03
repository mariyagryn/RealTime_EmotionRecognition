# ui/live_window.py
from __future__ import annotations

import os
import time
import threading
import random
from datetime import datetime

import tkinter as tk
from tkinter import messagebox as tk_messagebox
from tkinter import filedialog as tk_filedialog

import customtkinter as ctk
import cv2

from ui.common import (
    ensure_dirs,
    load_settings_safe,
    save_settings_safe,
    LABELS,
    parse_res,
)

from ui.views.live_view import LiveView
from ui.views.about_view import AboutView
from ui.views.stats_view import StatsView

from core.camera import Camera, CaptureThread
from core.analyzer import AnalyzerThread
from core.session_stats import LiveFlags, SessionStats
from core.storage import write_csv_summary, load_stats_aggregate

_HAS_REPORTLAB = False
try:
    import reportlab
    _HAS_REPORTLAB = True
except Exception:
    pass

_HAS_TTS = False
try:
    import pyttsx3

    _tts_engine = pyttsx3.init()
    _HAS_TTS = True
except Exception:
    _tts_engine = None

_HAS_SPEECHREC = False
try:
    import speech_recognition as sr

    _HAS_SPEECHREC = True
except Exception:
    sr = None


def _norm_theme(theme: str | None) -> str:
    t = (theme or "Dark").strip().lower()
    return "Light" if t.startswith("light") else "Dark"


def _palette_for(theme: str) -> dict:
    theme = _norm_theme(theme)

    if theme == "Light":
        base = {
            "bg": "#F6F9FF",
            "panel": "#FFFFFF",
            "panel_border": "#D7E2FF",
            "card": "#FFFFFF",
            "card_border": "#C7D2FE",
            "text": "#0B1220",
            "muted": "#475569",
            "accent": "#2563EB",
            "accent_2": "#3B82F6",
            "hover": "#E8F0FF",
            "control_bg": "#EEF4FF",
            "control_btn": "#E2ECFF",
            "control_hover": "#D6E6FF",
            "accent_h": "#1D4ED8",
            "border": "#C7D2FE",
            "active_bg": "#0B1D3A",
            "active_text": "#FFFFFF",
            "active_border": "#60A5FA",
        }
    else:
        base = {
            "bg": "#020617",
            "panel": "#020617",
            "panel_border": "#0B1D3A",
            "card": "#040c24",
            "card_border": "#1e40af",
            "text": "#E8F1FF",
            "muted": "#94a3b8",
            "accent": "#00D1FF",
            "accent_2": "#38bdf8",
            "hover": "#111827",
            "control_bg": "#0b1625",
            "control_btn": "#0b1625",
            "control_hover": "#111827",
            "accent_h": "#16E0FF",
            "border": "#1e40af",
            "active_bg": "#0B1625",
            "active_text": "#E8F1FF",
            "active_border": "#38BDF8",
        }

    return base


class BreakWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        palette: dict,
        kind: str,
        title: str,
        text: str,
        duration_sec: int | None,
        lang: str,
        on_done=None,
    ):
        super().__init__(parent)
        self._palette = palette
        self._kind = kind
        self._on_done = on_done

        self.title(title)
        self.configure(fg_color=palette["bg"])
        self.resizable(False, False)

        try:
            px = parent.winfo_rootx() + 80
            py = parent.winfo_rooty() + 100
            self.geometry(f"420x260+{px}+{py}")
        except Exception:
            self.geometry("420x260")

        frame = ctk.CTkFrame(self, fg_color=palette["panel"], corner_radius=18)
        frame.pack(expand=True, fill="both", padx=16, pady=16)

        title_lbl = ctk.CTkLabel(
            frame,
            text=title,
            font=("Inter", 18, "bold"),
            text_color=palette["text"],
        )
        title_lbl.pack(pady=(6, 4))

        body_lbl = ctk.CTkLabel(
            frame,
            text=text,
            font=("Inter", 13),
            text_color=palette["text"],
            wraplength=360,
            justify="left",
        )
        body_lbl.pack(pady=(0, 12), padx=8)

        self._timer_lbl = None
        self._remaining = None

        if duration_sec and duration_sec > 0:
            self._remaining = int(duration_sec)
            self._timer_lbl = ctk.CTkLabel(
                frame,
                text="",
                font=("Inter", 32, "bold"),
                text_color=palette["accent"],
            )
            self._timer_lbl.pack(pady=(0, 8))
            self._tick()

        btn_text = "Done" if lang == "EN" else "Готово"
        close_btn = ctk.CTkButton(
            frame,
            text=btn_text,
            fg_color=palette["accent"],
            hover_color=palette.get("accent_h", palette["accent"]),
            text_color="black",
            command=self._on_close,
        )
        close_btn.pack(pady=(4, 2))

        try:
            self.transient(parent)
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def _tick(self):
        if self._timer_lbl is None or self._remaining is None:
            return

        if self._remaining < 0:
            self._finish()
            return

        m = self._remaining // 60
        s = self._remaining % 60
        if m > 0:
            self._timer_lbl.configure(text=f"{m:01d}:{s:02d}")
        else:
            self._timer_lbl.configure(text=f"{s:02d}")

        self._remaining -= 1
        self.after(1000, self._tick)

    def _finish(self):
        cb = self._on_done
        self._on_done = None
        if cb:
            try:
                cb(self._kind)
            except Exception as e:
                print("BreakWindow callback error:", e)
        try:
            self.destroy()
        except Exception:
            pass

    def _on_close(self):
        self._finish()


class LiveWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()

        ensure_dirs()
        self.cfg = load_settings_safe() or {}

        self.flags = LiveFlags()
        self.stats = SessionStats()

        self._session_started_at = datetime.utcnow().isoformat()
        self._t0 = time.monotonic()
        self._last_tick = time.time()

        self._emotion_acc: dict[str, float] = {k: 0.0 for k in LABELS}
        self._streak_label: str | None = None
        self._streak_sec: float = 0.0
        self._last_suggestion_ts: float = 0.0

        self._conversation_active: bool = False
        self._last_convo_at: float = 0.0
        self._convo_cooldown: float = 45.0

        self._suggestion_cooldown: float = 90.0

        self._break_window: BreakWindow | None = None

        # settings
        lang0 = str(self.cfg.get("language", "UA")).upper()
        theme0 = _norm_theme(str(self.cfg.get("theme", "Dark")))

        self.lang_var = tk.StringVar(value="EN" if lang0 == "EN" else "UA")
        self.theme_is_dark = tk.BooleanVar(value=(theme0 == "Dark"))

        self.analyze_every = float(self.cfg.get("analyze_every", 0.6))
        self.resolution = str(self.cfg.get("resolution", "640x360"))
        self.cam_index = int(self.cfg.get("camera_index", 0))

        # theme engine
        ctk.set_default_color_theme("dark-blue")
        self._apply_theme(save=False, rebuild=False)

        # window
        self.title("Emotion — Live")
        self.geometry("1100x760+40+40")
        self.minsize(900, 600)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # UI containers
        self.header: ctk.CTkFrame | None = None
        self.main: ctk.CTkFrame | None = None
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._current_view = "live"

        self._build_header()
        self._build_views()
        self._switch_view("live")

        # camera
        self.camera = Camera(index=self.cam_index, resolution=self.resolution)
        self.cap_thread = CaptureThread(self.camera)
        self.cap_thread.start()

        self.analyzer = AnalyzerThread(analyze_every=self.analyze_every)
        self.analyzer.start()

        # recording
        self._writer = None
        self._rec_path: str | None = None

        # runtime
        self._fps_hist: list[float] = []
        self._after_id: str | None = None
        self._cam_wait_t0 = time.time()

        # keybinds
        self.bind("<Escape>", lambda _e: self._on_close())
        self.bind("<Command-q>", lambda _e: self._on_close())
        self.bind("<space>", lambda _e: self._toggle_pause())
        self.bind("s", lambda _e: self._snap())
        self.bind("r", lambda _e: self._toggle_recording())

        self.after(50, self._show_when_camera_ready)
        self._after_id = self.after(30, self._render)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _theme_name(self) -> str:
        return "Dark" if bool(self.theme_is_dark.get()) else "Light"

    def _apply_theme(self, save: bool = True, rebuild: bool = True):
        theme = self._theme_name()
        self.palette = _palette_for(theme)

        ctk.set_appearance_mode("dark" if theme == "Dark" else "light")

        try:
            self.configure(fg_color=self.palette["bg"])
        except Exception:
            pass

        if save:
            self.cfg["theme"] = theme
            save_settings_safe(dict(self.cfg))

        if rebuild and getattr(self, "header", None) is not None:
            self.after(10, lambda: self._rebuild_ui(keep_view=self._current_view))

    def _on_theme_toggle(self):
        self.after(10, lambda: self._apply_theme(save=True, rebuild=True))

    def _build_header(self):
        if self.header is not None and self.header.winfo_exists():
            try:
                self.header.destroy()
            except Exception:
                pass

        self.header = ctk.CTkFrame(
            self,
            fg_color=self.palette["panel"],
            height=46,
            corner_radius=0,
        )
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self.header,
            text="Emotion Analyzer",
            text_color=self.palette["text"],
            font=("Inter", 18, "bold"),
        )
        title.grid(row=0, column=0, padx=20, pady=8, sticky="w")

        right = ctk.CTkFrame(self.header, fg_color="transparent")
        right.grid(row=0, column=1, padx=18, pady=6, sticky="e")

        self._nav_buttons = {}

        def nav_btn(txt: str, name: str):
            b = ctk.CTkButton(
                right,
                text=txt,
                width=90,
                height=28,
                fg_color="transparent",
                hover_color=self.palette["hover"],
                text_color=self.palette["text"],
                corner_radius=999,
                font=("Inter", 13),
                command=lambda: self._switch_view(name),
            )
            b.pack(side="left", padx=6)
            self._nav_buttons[name] = b

            if name == "live":
                self.btn_live = b
            elif name == "about":
                self.btn_about = b
            elif name == "stats":
                self.btn_stats = b

        nav_btn("Live", "live")
        nav_btn("About", "about")
        nav_btn("Statistics", "stats")

        self.lang_menu = ctk.CTkOptionMenu(
            right,
            values=["UA", "EN"],
            variable=self.lang_var,
            width=90,
            height=30,
            fg_color=self.palette["control_bg"],
            button_color=self.palette["control_btn"],
            button_hover_color=self.palette["control_hover"],
            text_color=self.palette["text"],
            dropdown_fg_color=self.palette["panel"],
            dropdown_text_color=self.palette["text"],
            corner_radius=14,
            command=self._on_lang_change,
        )
        self.lang_menu.pack(side="left", padx=(10, 12))

        self.theme_switch = ctk.CTkSwitch(
            right,
            text="",
            variable=self.theme_is_dark,
            onvalue=True,
            offvalue=False,
            width=52,
            height=24,
            switch_width=40,
            switch_height=20,
            progress_color=self.palette["accent"],
            command=self._on_theme_toggle,
        )
        self.theme_switch.pack(side="left")

        self._apply_lang(self.lang_var.get())
        self._paint_nav_active()

    def _build_views(self):
        if self.main is not None and self.main.winfo_exists():
            try:
                self.main.destroy()
            except Exception:
                pass

        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=1, column=0, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # Live
        self.view_live = LiveView(
            parent=self.main,
            palette=self.palette,
            on_pause=self._toggle_pause,
            on_snap=self._snap,
            on_record=self._toggle_recording,
            on_exit=self._on_close,
        )
        self.view_live.grid(row=0, column=0, sticky="nsew")

        # About
        self.view_about = AboutView(
            self.main,
            palette=self.palette,
            get_lang=lambda: self.lang_var.get(),
        )

        # Stats
        self.view_stats = StatsView(
            self.main,
            self.palette,
            lang=self.lang_var.get(),
            on_export_pdf=self._export_stats_pdf,
        )

    def _rebuild_ui(self, keep_view: str = "live"):
        keep_view = keep_view or "live"
        self._current_view = keep_view

        self._build_header()
        self._build_views()
        self._switch_view(keep_view)

        try:
            self.view_live.set_paused(self.flags.paused)
        except Exception:
            pass
        try:
            self.view_live.set_recording(self.flags.recording)
        except Exception:
            pass

    def _paint_nav_active(self):
        for k, b in self._nav_buttons.items():
            try:
                b.configure(
                    text_color=self.palette["accent"]
                    if k == self._current_view
                    else self.palette["text"]
                )
            except Exception:
                pass

    def _switch_view(self, name: str):
        self._current_view = name

        for v in (self.view_live, self.view_about, self.view_stats):
            try:
                v.grid_forget()
            except Exception:
                pass

        if name == "live":
            self.view_live.grid(row=0, column=0, sticky="nsew")
            self.flags.paused = False
            try:
                self.view_live.set_paused(False)
            except Exception:
                pass
        elif name == "about":
            self.view_about.grid(row=0, column=0, sticky="nsew")
            self.flags.paused = True
            try:
                self.view_live.set_paused(True)
            except Exception:
                pass
        else:
            self.view_stats.grid(row=0, column=0, sticky="nsew")
            self.flags.paused = True
            try:
                self.view_live.set_paused(True)
            except Exception:
                pass

        self._paint_nav_active()

    def _on_lang_change(self, choice: str):
        lang = (choice or "UA").upper()

        self.cfg["language"] = lang
        save_settings_safe(dict(self.cfg))

        self.after(10, lambda: self._apply_lang(lang))

    def _apply_lang(self, lang: str):
        lang = (lang or "UA").upper()

        try:
            if lang == "EN":
                self.btn_live.configure(text="Live")
                self.btn_about.configure(text="About")
                self.btn_stats.configure(text="Statistics")
            else:
                self.btn_live.configure(text="Онлайн")
                self.btn_about.configure(text="Про застосунок")
                self.btn_stats.configure(text="Статистика")
        except Exception as e:
            print("Nav text update error:", e)

        try:
            if hasattr(self, "view_about") and self.view_about is not None:
                self.view_about.rebuild()
        except Exception as e:
            print("AboutView rebuild error:", e)

        try:
            if (
                    hasattr(self, "view_stats")
                    and self.view_stats is not None
                    and hasattr(self.view_stats, "set_lang")
            ):
                self.view_stats.set_lang(lang)
        except Exception as e:
            print("StatsView set_lang error:", e)

    def _toggle_pause(self):
        self.flags.paused = not self.flags.paused
        try:
            self.view_live.set_paused(self.flags.paused)
        except Exception:
            pass

    def _snap(self):
        frame = getattr(self, "_last_frame_bgr", None)
        if frame is None:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("sessions", "snaps", f"snap_{ts}.png")
        cv2.imwrite(path, frame)
        try:
            self.view_live.flash_status(f"Saved snap → {path}", self.flags.recording)
        except Exception:
            pass

    def _toggle_recording(self):
        if not self.flags.recording:
            frame = getattr(self, "_last_frame_bgr", None)
            if frame is None:
                w, h = parse_res(self.resolution)
            else:
                h, w = frame.shape[:2]

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._rec_path = os.path.join("sessions", "records", f"rec_{ts}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(self._rec_path, fourcc, 25.0, (w, h))

            self.flags.recording = True
            try:
                self.view_live.set_recording(True)
            except Exception:
                pass
        else:
            self.flags.recording = False
            try:
                if self._writer:
                    self._writer.release()
            except Exception:
                pass
            self._writer = None

            try:
                self.view_live.set_recording(False)
            except Exception:
                pass

            if self._rec_path:
                try:
                    self.view_live.flash_status(
                        f"Saved video → {self._rec_path}", self.flags.recording
                    )
                except Exception:
                    pass
            self._rec_path = None

    def _speak(self, text: str):
        if not text:
            return

        if getattr(self, "_speaking", False):
            return

        self._speaking = True

        def worker():
            try:
                if _HAS_TTS and _tts_engine is not None:
                    try:
                        _tts_engine.say(text)
                        _tts_engine.runAndWait()
                        return
                    except Exception as e:
                        print("TTS error:", e)

                try:
                    safe = text.replace('"', "")
                    os.system(f'say "{safe}"')
                except Exception as e:
                    print("macOS say error:", e)
            finally:
                self._speaking = False

        threading.Thread(target=worker, daemon=True).start()

    def _start_conversation(self, mood: str):
        if self._conversation_active:
            return

        now = time.monotonic()
        if (now - self._last_convo_at) < self._convo_cooldown:
            return

        self._conversation_active = True
        self._last_convo_at = now

        try:
            self.view_live.set_hint("")
        except Exception:
            pass

        lang = self.lang_var.get().upper()

        if lang == "EN":
            if mood == "happy":
                question = "You look very happy right now. What happened?"
                followup = "So what happened then?"
                replies = [
                    "Wow, that sounds really cool. I am happy for you.",
                    "Nice! I love hearing such positive news.",
                ]
            elif mood == "sad":
                question = "You look a bit sad. Do you want to tell me what happened?"
                followup = "I am still here if you want to share."
                replies = [
                    "Thank you for sharing this. It is important not to keep everything inside.",
                    "I am sorry it is hard right now. You are doing great just by talking about it.",
                ]
            else:
                question = "You have been neutral for a while. Are you focused or just tired?"
                followup = "So how are you really feeling?"
                replies = [
                    "Okay, thanks for being honest about your state.",
                    "Good that you keep track of how you feel.",
                ]
        else:
            if mood == "happy":
                question = "Ти зараз виглядаєш дуже щасливою. Що там сталося? 🙂"
                followup = "То що ж там таке? 🙂"
                replies = [
                    "Вау, звучить дуже круто! Я щиро рада за тебе 💙",
                    "Ого, от це новина! Хай такі моменти трапляються частіше.",
                ]
            elif mood == "sad":
                question = "Ти виглядаєш трошки засмучено. Хочеш розповісти, що сталося?"
                followup = "Я все ще тут, якщо захочеш поділитися."
                replies = [
                    "Дякую, що поділилася. Навіть просто проговорити це вже важливо.",
                    "Тримайся, будь ласка. Ти велика молодчинка, що не тримаєш усе в собі.",
                ]
            else:
                question = "Довго сидиш з таким нейтральним виразом. Ти зосереджена чи вже втомилася?"
                followup = "То як ти там, який настрій зараз?"
                replies = [
                    "Окей, дякую за чесність. Головне — прислухатись до себе.",
                    "Добре, що ти відстежуєш свій стан, це дуже корисна звичка.",
                ]

        def worker():
            try:
                self._speak(question)

                if not (_HAS_SPEECHREC and sr is not None):
                    time.sleep(4)
                    self._speak(followup)
                    return

                try:
                    recognizer = sr.Recognizer()
                    with sr.Microphone() as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        try:
                            audio = recognizer.listen(
                                source, timeout=6, phrase_time_limit=6
                            )
                        except sr.WaitTimeoutError:
                            audio = None
                except Exception as e:
                    print("Mic error:", e)
                    audio = None

                user_text = ""
                if audio is not None:
                    try:
                        lang_code = "en-US" if lang == "EN" else "uk-UA"
                        user_text = recognizer.recognize_google(
                            audio, language=lang_code
                        )
                        print("User said:", user_text)
                    except Exception as e:
                        print("Speech recognition error:", e)

                if user_text.strip():
                    self._speak(random.choice(replies))
                else:
                    self._speak(followup)
            finally:
                self._conversation_active = False

        threading.Thread(target=worker, daemon=True).start()

    def _open_break_window(self, kind: str, text: str, lang: str):
        try:
            if (
                self._break_window is not None
                and self._break_window.winfo_exists()
            ):
                self._break_window.destroy()
        except Exception:
            pass

        titles_ua = {
            "breathing": "Breathing break",
            "pomodoro": "Mini-Pomodoro",
            "mirror": "Mirror break",
            "speech": "Speech break",
        }
        titles_en = {
            "breathing": "Breathing break",
            "pomodoro": "Mini-Pomodoro",
            "mirror": "Mirror break",
            "speech": "Speech break",
        }

        durations = {
            "breathing": 60,
            "pomodoro": 5 * 60,
            "mirror": 45,
            "speech": 30,
        }

        title = (
            titles_en.get(kind, kind.title())
            if lang == "EN"
            else titles_ua.get(kind, kind.title())
        )
        dur = durations.get(kind)

        self._break_window = BreakWindow(
            parent=self,
            palette=self.palette,
            kind=kind,
            title=title,
            text=text,
            duration_sec=dur,
            lang=lang,
            on_done=self._on_break_finished,
        )

    def _show_hint(self, kind: str, current_label: str):
        lang = self.lang_var.get().upper()

        if lang == "EN":
            texts = {
                "breathing": "You look tense or sad. Take a 60-second breathing break: "
                             "4 seconds inhale – 4 seconds hold – 4 seconds exhale.",
                "pomodoro": "You have been neutral for a long time. Try a mini-Pomodoro: "
                            "5 minutes of focus and 1 minute of rest.",
                "mirror": "Your expression looks a bit angry. Stand up for a moment, "
                          "check your posture and relax your face and shoulders.",
                "speech": "You look very energized. Let's do a quick 30-second speech "
                          "about what you are working on.",
            }
        else:
            texts = {
                "breathing": "Виглядаєш трохи сумно/напружено. Зроби хвилинну дихальну паузу: "
                             "4 секунди вдих — 4 секунди затримка — 4 секунди видих.",
                "pomodoro": "Ти вже довго в нейтральному стані. Спробуй міні-Pomodoro: "
                            "5 хвилин фокусу і 1 хвилина відпочинку.",
                "mirror": "Міміка виглядає трохи сердитою. Встань, вирівняй спину, "
                          "розслаб шию, плечі й щелепу.",
                "speech": "Ти давно виглядаєш бадьоро. Давай 30 секунд вголос розкажеш, "
                          "над чим зараз працюєш.",
            }

        text = texts.get(kind, "")
        try:
            self.view_live.set_hint(text)
        except Exception:
            pass

        if kind in ("breathing", "pomodoro", "mirror"):
            if text:
                self._speak(text)
            self._open_break_window(kind, text, lang)
            return

        if kind == "speech":
            self._open_break_window(kind, text, lang)
            self._start_conversation(current_label or "happy")

    def _on_break_finished(self, kind: str):
        try:
            lang = self.lang_var.get().upper()
        except Exception:
            lang = "UA"

        if lang == "EN":
            messages = {
                "breathing": "Great job, you’ve completed your breathing break! 💙",
                "pomodoro": "Nice, you have finished this mini-Pomodoro. 🎯",
                "mirror": "Well done! A short posture reset is always a good idea. 🙂",
                "speech": "Cool, thanks for taking this little speech break. 💬",
            }
            default_msg = "Well done, you’ve completed this break!"
        else:
            messages = {
                "breathing": "Супер, ти зробила дихальну паузу! 💙",
                "pomodoro": "Круто, міні-Pomodoro завершено! 🎯",
                "mirror": "Молодець, трішки розім’ялася та поправила поставу. 🙂",
                "speech": "Клас, промова готова! Дякую, що поділилася. 💬",
            }
            default_msg = "Супер, ти впоралася з паузою! 💙"

        msg = messages.get(kind, default_msg)

        try:
            self.view_live.set_hint(msg)
        except Exception:
            pass

        try:
            self._speak(msg)
        except Exception as e:
            print("TTS praise error:", e)

        self._streak_label = None
        self._streak_sec = 0.0
        self._last_suggestion_ts = time.monotonic()

    def _update_suggestion_logic(self, label: str, dt: float):
        now = time.monotonic()

        try:
            if (
                    self._break_window is not None
                    and self._break_window.winfo_exists()
            ):
                self._streak_label = None
                self._streak_sec = 0.0
                return
        except Exception:
            pass

        if label == self._streak_label:
            self._streak_sec += dt
        else:
            self._streak_label = label
            self._streak_sec = dt

        COOLDOWN_SEC = getattr(self, "_suggestion_cooldown", 90.0)
        if (now - self._last_suggestion_ts) < COOLDOWN_SEC:
            return

        total_elapsed = now - self._t0
        triggered: str | None = None

        if label == "sad" and self._streak_sec >= 20.0:
            triggered = "breathing"

        elif label == "angry" and self._streak_sec >= 15.0:
            triggered = "mirror"

        elif (
                label == "neutral"
                and total_elapsed >= 1 * 60.0
                and self._streak_sec >= 1 * 60.0
        ):
            triggered = "pomodoro"

        elif label == "happy" and self._streak_sec >= 10.0:
            triggered = "speech"

        if not triggered:
            return

        self._last_suggestion_ts = now
        self._streak_sec = 0.0
        self._show_hint(triggered, current_label=label)

    def _show_when_camera_ready(self):
        if not self.winfo_exists():
            return

        if getattr(self.cap_thread, "last_bgr", None) is not None:
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception:
                pass
            return

        if (time.time() - self._cam_wait_t0) > 4.0:
            try:
                self.deiconify()
            except Exception:
                pass
            return

        self.after(50, self._show_when_camera_ready)

    def _render(self):
        t0 = time.time()

        if not self.flags.paused:
            frame = getattr(self.cap_thread, "last_bgr", None)
            if frame is not None:
                self._last_frame_bgr = frame
                self.analyzer.update_frame(frame)

                if self.flags.recording and self._writer is not None:
                    try:
                        self._writer.write(frame)
                    except Exception:
                        pass

                try:
                    self.view_live.show_frame(frame)
                except Exception:
                    pass

        spent = time.time() - t0
        fps = 1.0 / max(1e-6, spent)
        self._fps_hist.append(fps)
        if len(self._fps_hist) > 15:
            self._fps_hist.pop(0)
        avg = sum(self._fps_hist) / max(1, len(self._fps_hist))
        try:
            self.view_live.update_fps(avg)
        except Exception:
            pass

        label, conf = self.analyzer.current
        now = time.time()
        dt = now - getattr(self, "_last_tick", now)
        self._last_tick = now

        label = (label or "neutral").lower().strip()
        if label not in LABELS:
            label = "neutral"

        self.stats.add(label, dt)
        self.stats.last_label = label
        self.stats.recompute_dominant()

        break_active = False
        try:
            break_active = (
                    self._break_window is not None
                    and self._break_window.winfo_exists()
            )
        except Exception:
            break_active = False

        if not break_active:
            self._emotion_acc[label] = self._emotion_acc.get(label, 0.0) + dt
            self._update_suggestion_logic(label, dt)
        else:
            self._streak_label = None
            self._streak_sec = 0.0

        try:
            self.view_live.update_emotion(label, float(conf))
            self.view_live.update_stats(
                self.stats.totals, self.stats.dominant, self.stats.last_label
            )
        except Exception:
            pass

        self._after_id = self.after(33, self._render)

    def _export_stats_pdf(self):
        lang = self.lang_var.get().upper()
        period = getattr(
            self.view_stats, "period_var", tk.StringVar(value="Today")
        ).get()

        totals, sessions_count, total_sec = load_stats_aggregate(period)
        if total_sec <= 0 or sessions_count == 0:
            tk_messagebox.showinfo(
                "Export",
                "No data for this period."
                if lang == "EN"
                else "Немає даних за цей період.",
            )
            return

        if not _HAS_REPORTLAB:
            tk_messagebox.showwarning(
                "Export",
                "reportlab is not installed. Run `pip install reportlab`."
                if lang == "EN"
                else "reportlab не встановлено. Запусти `pip install reportlab`.",
            )
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"emotion_stats_{ts}.pdf"

        save_path = tk_filedialog.asksaveasfilename(
            title=("Save PDF" if lang == "EN" else "Зберегти PDF"),
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf")],
        )
        if not save_path:
            return

        from core.export_pdf import export_stats_pdf

        export_stats_pdf(
            save_path, period, totals, sessions_count, total_sec, lang=lang
        )
        tk_messagebox.showinfo(
            "Export",
            (
                f"PDF saved to:\n{save_path}"
                if lang == "EN"
                else f"PDF збережено:\n{save_path}"
            ),
        )

    def _cancel_timer(self):
        try:
            if self._after_id is not None:
                self.after_cancel(self._after_id)
        except Exception:
            pass
        self._after_id = None

    def _on_close(self):
        self._cancel_timer()

        try:
            if (
                self._break_window is not None
                and self._break_window.winfo_exists()
            ):
                self._break_window.destroy()
        except Exception:
            pass

        if self.flags.recording:
            try:
                if self._writer:
                    self._writer.release()
            except Exception:
                pass
        self._writer = None

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

        try:
            write_csv_summary(
                self._session_started_at,
                self.stats.totals,
                self.stats.dominant,
            )
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass
