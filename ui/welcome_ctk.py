# ui/welcome_ctk.py
from __future__ import annotations

import os
import sys
import subprocess
from tkinter import StringVar

import customtkinter as ctk
from PIL import Image, ImageDraw

from utils.app_settings import load as load_cfg, save as save_cfg


WINDOW_W = 1024
WINDOW_H = 640


def _asset_path(name: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", name)


PALETTES = {
    "dark": {
        "bg": "#020617",
        "card": "#040c24",
        "card_border": "#1e40af",
        "title": "#E8F1FF",
        "text": "#E8F1FF",
        "muted": "#94a3b8",
        "tagline": "#92C1FF",
        "menu_bg": "#020617",
        "menu_btn": "#111827",
        "menu_btn_h": "#1f2937",
        "menu_dd_bg": "#020617",
        "menu_dd_text": "#E8F1FF",
        "btn_text": "#020617",
    },
    "light": {
        "bg": "#EAF3FF",
        "card": "#F6FAFF",
        "card_border": "#7BB7FF",
        "title": "#0B1B33",
        "text": "#0B1B33",
        "muted": "#4B6A8F",
        "tagline": "#1C5DFF",
        "menu_bg": "#EEF6FF",
        "menu_btn": "#DDEEFF",
        "menu_btn_h": "#CFE6FF",
        "menu_dd_bg": "#F6FAFF",
        "menu_dd_text": "#0B1B33",
        "btn_text": "#061427",
    },
}


def _create_gradient_button_img(width: int = 190, height: int = 40, variant: str = "dark") -> Image.Image:
    if variant == "light":
        c1 = (40, 120, 255)
        c2 = (120, 190, 255)
    else:
        c1 = (0, 91, 197)
        c2 = (80, 140, 255)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for x in range(width):
        t = x / max(1, width - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line((x, 0, x, height), fill=(r, g, b, 255))

    radius = height // 2
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=255)

    img.putalpha(mask)
    return img


class WelcomeWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        cfg = load_cfg() or {}
        lang_default = str(cfg.get("language", "UA")).upper()
        theme_default = str(cfg.get("theme", "Dark")).capitalize()

        ctk.set_default_color_theme("dark-blue")
        ctk.set_appearance_mode("light" if theme_default.lower().startswith("light") else "dark")

        self.lang_var = StringVar(value="EN" if lang_default == "EN" else "UA")
        self.theme_var = StringVar(value="Light" if theme_default.lower().startswith("light") else "Dark")

        self.title("Emotion Analyzer — Welcome")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}+200+80")
        self.resizable(False, False)
        self._music_proc = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        bg_dark_path = _asset_path("background.png")
        bg_light_path = _asset_path("background_light.png")

        bg_dark = Image.open(bg_dark_path)
        bg_light = Image.open(bg_light_path) if os.path.exists(bg_light_path) else bg_dark

        self._bg_image = ctk.CTkImage(light_image=bg_light, dark_image=bg_dark, size=(WINDOW_W, WINDOW_H))
        self._bg_label = ctk.CTkLabel(self, image=self._bg_image, text="")
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.card = ctk.CTkFrame(self, width=340, height=310, border_width=1, corner_radius=14)
        self.card.place(x=60, rely=0.5, anchor="w")
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_propagate(False)

        top = ctk.CTkFrame(self.card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        top.grid_columnconfigure(0, weight=1)

        header_left = ctk.CTkFrame(top, fg_color="transparent")
        header_left.grid(row=0, column=0, sticky="w")

        self._logo_img = None
        self._logo_lbl = None
        self._title_lbl = None

        logo_dark_path = _asset_path("logo_face.png")
        logo_light_path = _asset_path("logo_face_light.png")

        try:
            logo_dark = Image.open(logo_dark_path)
            logo_light = Image.open(logo_light_path) if os.path.exists(logo_light_path) else logo_dark
            self._logo_img = ctk.CTkImage(light_image=logo_light, dark_image=logo_dark, size=(32, 32))
            self._logo_lbl = ctk.CTkLabel(header_left, image=self._logo_img, text="")
            self._logo_lbl.pack(side="left", padx=(0, 10))
        except Exception:
            self._logo_img = None

        self._title_lbl = ctk.CTkLabel(
            header_left,
            text="Emotion Analyzer",
            font=("Inter", 18, "bold"),
            wraplength=300,
        )
        self._title_lbl.pack(side="left", anchor="w")

        self.tagline_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=("Inter", 14, "bold"),
            justify="left",
            wraplength=300,
        )
        self.tagline_lbl.grid(row=1, column=0, sticky="w", padx=20, pady=(18, 6))

        self.features_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=("Inter", 13),
            justify="left",
            wraplength=280,
        )
        self.features_lbl.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 20))

        controls = ctk.CTkFrame(self.card, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 13))

        self._lang_lbl = ctk.CTkLabel(controls, text="Language", font=("Inter", 10))
        self._lang_lbl.grid(row=0, column=0, padx=(0, 6), sticky="w")

        self.lang_menu = ctk.CTkOptionMenu(
            controls,
            values=["UA", "EN"],
            variable=self.lang_var,
            font=("Inter", 10),
            width=70,
            corner_radius=14,
        )
        self.lang_menu.grid(row=0, column=1, padx=(0, 16), sticky="w")

        self._theme_lbl = ctk.CTkLabel(controls, text="Theme", font=("Inter", 10))
        self._theme_lbl.grid(row=0, column=2, padx=(0, 6), sticky="w")

        self.theme_menu = ctk.CTkOptionMenu(
            controls,
            values=["Dark", "Light"],
            variable=self.theme_var,
            font=("Inter", 10),
            width=70,
            corner_radius=14,
        )
        self.theme_menu.grid(row=0, column=3, sticky="w")

        grad_dark = _create_gradient_button_img(190, 40, variant="dark")
        grad_light = _create_gradient_button_img(190, 40, variant="light")
        self._btn_grad_img = ctk.CTkImage(light_image=grad_light, dark_image=grad_dark, size=(190, 40))

        self.primary_btn = ctk.CTkLabel(
            self.card,
            text="",
            image=self._btn_grad_img,
            compound="center",
            font=("Inter", 14, "bold"),
        )
        self.primary_btn.grid(row=4, column=0, padx=20, pady=(4, 10), sticky="w")
        self.primary_btn.bind("<Button-1>", lambda e: self._on_continue())
        self.primary_btn.bind("<Enter>", lambda e: self.primary_btn.configure(cursor="hand2"))
        self.primary_btn.bind("<Leave>", lambda e: self.primary_btn.configure(cursor=""))

        self.lang_var.trace_add("write", lambda *_: self._update_texts())
        self.theme_var.trace_add("write", lambda *_: self._apply_theme())

        self._apply_theme()
        self._update_texts()
        self._maybe_play_music()

    def _palette_key(self) -> str:
        return "light" if self.theme_var.get().lower().startswith("light") else "dark"

    def _apply_theme(self):
        is_light = self.theme_var.get().lower().startswith("light")
        ctk.set_appearance_mode("light" if is_light else "dark")

        pal = PALETTES[self._palette_key()]
        self.configure(fg_color=pal["bg"])
        self.card.configure(fg_color=pal["card"], border_color=pal["card_border"])
        self._title_lbl.configure(text_color=pal["title"])
        self.tagline_lbl.configure(text_color=pal["tagline"])
        self.features_lbl.configure(text_color=pal["muted"])

        self._lang_lbl.configure(text_color=pal["muted"])
        self._theme_lbl.configure(text_color=pal["muted"])

        for m in (self.lang_menu, self.theme_menu):
            m.configure(
                fg_color=pal["menu_bg"],
                button_color=pal["menu_btn"],
                button_hover_color=pal["menu_btn_h"],
                text_color=pal["text"],
                dropdown_fg_color=pal["menu_dd_bg"],
                dropdown_text_color=pal["menu_dd_text"],
            )

        self.primary_btn.configure(text_color=pal["btn_text"])

    def _update_texts(self):
        lang = self.lang_var.get().upper()
        if lang == "EN":
            tagline = "Your emotion-aware study & work companion"
            features = (
                "We track your emotions from the webcam and gently suggest micro-breaks "
                "so you burn out less while studying and working."
            )
            btn_text = "Start"
            self._lang_lbl.configure(text="Language")
            self._theme_lbl.configure(text="Theme")
        else:
            tagline = "Твій емоційно-чутливий асистент для навчання й роботи"
            features = (
                "Ми відстежуємо емоції з вебкамери та час від часу пропонуємо мікропаузи, "
                "щоб ти менше вигорав/ла під час навчання та роботи."
            )
            btn_text = "Почати"
            self._lang_lbl.configure(text="Language")
            self._theme_lbl.configure(text="Theme")

        self.tagline_lbl.configure(text=tagline)
        self.features_lbl.configure(text=features)
        self.primary_btn.configure(text=btn_text)

    def _maybe_play_music(self):
        if sys.platform != "darwin":
            return
        try:
            if getattr(self, "_music_proc", None) is not None:
                return
            path = _asset_path("welcome.mp3")
            if not os.path.exists(path):
                path = _asset_path("live.mp3")
            if os.path.exists(path):
                self._music_proc = subprocess.Popen(["afplay", path])
        except Exception:
            self._music_proc = None

    def _stop_music(self):
        try:
            if getattr(self, "_music_proc", None) is not None:
                self._music_proc.terminate()
                self._music_proc = None
        except Exception:
            pass

    def _on_continue(self):
        self._stop_music()

        cfg = load_cfg() or {}
        cfg["language"] = self.lang_var.get().upper()
        cfg["theme"] = "Light" if self.theme_var.get().lower().startswith("light") else "Dark"
        save_cfg(cfg)

        self.destroy()
        from ui.live import run_live
        run_live()

    def _on_close(self):
        self._stop_music()
        try:
            self.destroy()
        except Exception:
            pass


def show_welcome():
    app = WelcomeWindow()
    app.mainloop()


if __name__ == "__main__":
    show_welcome()
