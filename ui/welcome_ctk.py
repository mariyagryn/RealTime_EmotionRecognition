# ui/welcome_ctk.py
from __future__ import annotations
import os
import sys
import subprocess

import customtkinter as ctk
from tkinter import StringVar
from PIL import Image

from utils.app_settings import load as load_cfg, save as save_cfg


PALETTE = {
    "bg":      "#020617",
    "panel":   "#020617",
    "accent":  "#00D1FF",
    "accent_h":"#16E0FF",
    "text":    "#E8F1FF",
    "muted":   "#94a3b8",
}

WINDOW_W = 1024
WINDOW_H = 640


def _asset_path(name: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", name)


class WelcomeWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        cfg = load_cfg()
        lang_default = str(cfg.get("language", "UA")).upper()
        theme_default = str(cfg.get("theme", "Dark")).capitalize()

        ctk.set_default_color_theme("dark-blue")
        ctk.set_appearance_mode(
            "light" if theme_default.lower().startswith("light") else "dark"
        )

        self.title("Emotion Analyzer — Welcome")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}+200+80")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["bg"])

        bg_path = _asset_path("background.jpg")
        bg_raw = Image.open(bg_path)
        self._bg_image = ctk.CTkImage(bg_raw, size=(WINDOW_W, WINDOW_H))

        bg_label = ctk.CTkLabel(self, image=self._bg_image, text="")
        bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.card = ctk.CTkFrame(
            self,
            fg_color="#020617",
            corner_radius=22,
            width=430,
            height=430,
        )
        self.card.place(x=60, rely=0.5, anchor="w")
        self.card.grid_columnconfigure(0, weight=1)

        self.lang_var = StringVar(value="EN" if lang_default == "EN" else "UA")
        self.theme_var = StringVar(
            value="Light" if theme_default.lower().startswith("light") else "Dark"
        )

        top = ctk.CTkFrame(self.card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)
        top.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(
            top,
            text="Emotion Analyzer",
            font=("Inter", 16, "bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            top, text="Language", text_color=PALETTE["muted"], font=("Inter", 12)
        ).grid(row=0, column=1, padx=(0, 4), sticky="e")

        lang_menu = ctk.CTkOptionMenu(
            top,
            values=["UA", "EN"],
            variable=self.lang_var,
            fg_color="#020617",
            button_color="#111827",
            button_hover_color="#1f2937",
            text_color=PALETTE["text"],
            dropdown_fg_color="#020617",
            dropdown_text_color=PALETTE["text"],
            font=("Inter", 12),
            width=70,
            corner_radius=14,
        )
        lang_menu.grid(row=0, column=2, padx=(0, 10), sticky="e")

        ctk.CTkLabel(
            top, text="Theme", text_color=PALETTE["muted"], font=("Inter", 12)
        ).grid(row=1, column=1, padx=(0, 4), pady=(6, 0), sticky="e")

        theme_menu = ctk.CTkOptionMenu(
            top,
            values=["Dark", "Light"],
            variable=self.theme_var,
            fg_color="#020617",
            button_color="#111827",
            button_hover_color="#1f2937",
            text_color=PALETTE["text"],
            dropdown_fg_color="#020617",
            dropdown_text_color=PALETTE["text"],
            font=("Inter", 12),
            width=70,
            corner_radius=14,
        )
        theme_menu.grid(row=1, column=2, padx=(0, 10), pady=(6, 0), sticky="e")

        self.title_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=("Inter", 24, "bold"),
            text_color=PALETTE["text"],
            justify="left",
        )
        self.title_lbl.grid(row=1, column=0, sticky="w", padx=20, pady=(24, 8))

        self.subtitle_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=("Inter", 13),
            text_color=PALETTE["muted"],
            justify="left",
        )
        self.subtitle_lbl.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 14))

        self.hint_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=("Inter", 11),
            text_color=PALETTE["muted"],
            justify="left",
        )
        self.hint_lbl.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 24))

        btn = ctk.CTkButton(
            self.card,
            text="Continue",
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_h"],
            text_color="black",
            corner_radius=20,
            width=190,
            height=38,
            command=self._on_continue,
        )
        btn.grid(row=4, column=0, padx=20, pady=(0, 24), sticky="w")

        self.lang_var.trace_add("write", lambda *_: self._update_texts())
        self.theme_var.trace_add("write", lambda *_: self._apply_theme())

        self._apply_theme()
        self._update_texts()
        self._maybe_play_music()

    def _apply_theme(self):
        theme = self.theme_var.get().lower()
        ctk.set_appearance_mode("light" if theme.startswith("light") else "dark")

    def _update_texts(self):
        lang = self.lang_var.get().upper()
        if lang == "EN":
            title = "Welcome to Emotion Analyzer"
            sub = (
                "We track your emotions from the webcam and\n"
                "gently suggest micro-breaks so you burn out less\n"
                "while studying and working."
            )
            hint = "You can change theme and language later in Settings."
        else:
            title = "Ласкаво просимо до Emotion Analyzer"
            sub = (
                "Ми відстежуємо емоції з вебкамери та час від часу\n"
                "пропонуємо мікропаузи, щоб ти менше вигорав/ла\n"
                "під час навчання та роботи."
            )
            hint = "Мову й тему можна змінити пізніше у розділі Settings."

        self.title_lbl.configure(text=title)
        self.subtitle_lbl.configure(text=sub)
        self.hint_lbl.configure(text=hint)

    def _maybe_play_music(self):
        try:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base, "assets", "welcome.mp3")
            if sys.platform == "darwin" and os.path.exists(path):
                subprocess.Popen(["afplay", path])
        except Exception:
            pass

    def _on_continue(self):
        cfg = load_cfg()
        cfg["language"] = self.lang_var.get().upper()
        cfg["theme"] = (
            "Light" if self.theme_var.get().lower().startswith("light") else "Dark"
        )
        save_cfg(cfg)

        self.destroy()
        from ui.live import run_live
        run_live()


def show_welcome():
    app = WelcomeWindow()
    app.mainloop()


if __name__ == "__main__":
    show_welcome()
