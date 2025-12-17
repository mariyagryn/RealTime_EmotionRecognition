# ui/welcome_ctk.py
from __future__ import annotations
import os
import sys
import subprocess

import customtkinter as ctk
from tkinter import StringVar
from PIL import Image, ImageDraw

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


def _create_gradient_button_img(width: int = 190, height: int = 40) -> Image.Image:
    """Градієнтна pill-кнопка cyan → blue як на макеті."""
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
        self._music_proc = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ---------- background ----------
        bg_path = _asset_path("background.png")
        bg_raw = Image.open(bg_path)
        self._bg_image = ctk.CTkImage(bg_raw, size=(WINDOW_W, WINDOW_H))
        bg_label = ctk.CTkLabel(self, image=self._bg_image, text="")
        bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # ---------- card ----------
        self.card = ctk.CTkFrame(
            self,
            fg_color="#040c24",
            width=340,
            height=310,
            border_width=1,
            border_color="#1e40af",  # темно-синій неон

        )
        self.card.place(x=60, rely=0.5, anchor="w")
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_propagate(False)

        self.lang_var = StringVar(value="EN" if lang_default == "EN" else "UA")
        self.theme_var = StringVar(
            value="Light" if theme_default.lower().startswith("light") else "Dark"
        )

        # ---------- header: тільки logo + назва ----------
        top = ctk.CTkFrame(self.card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        top.grid_columnconfigure(0, weight=1)

        header_left = ctk.CTkFrame(top, fg_color="transparent")
        header_left.grid(row=0, column=0, sticky="w")

        try:
            logo_raw = Image.open(_asset_path("logo_face.png"))
            self._logo_img = ctk.CTkImage(logo_raw, size=(32, 32))
            ctk.CTkLabel(header_left, image=self._logo_img, text="").pack(
                side="left", padx=(0, 10)
            )
        except Exception:
            self._logo_img = None

        ctk.CTkLabel(
            header_left,
            text="Emotion Analyzer",
            font=("Inter", 18, "bold"),
            text_color=PALETTE["text"],
            wraplength=300,
        ).pack(side="left", anchor="w")

        # ---------- hero text ----------
        self.tagline_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=("Inter", 14, "bold"),
            text_color="#92C1FF",
            justify="left",
            wraplength=300,
        )
        self.tagline_lbl.grid(row=1, column=0, sticky="w", padx=20, pady=(18, 6))

        self.features_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=("Inter", 13),
            text_color=PALETTE["muted"],
            justify="left",
            wraplength=280,
        )
        self.features_lbl.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 20))

        # ---------- Language / Theme ПІД текстом ----------
        controls = ctk.CTkFrame(self.card, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 13))
        controls.grid_columnconfigure(1, weight=0)
        controls.grid_columnconfigure(3, weight=0)

        # language row
        ctk.CTkLabel(
            controls, text="Language", text_color=PALETTE["muted"], font=("Inter", 10)
        ).grid(row=0, column=0, padx=(0, 6), sticky="w")

        lang_menu = ctk.CTkOptionMenu(
            controls,
            values=["UA", "EN"],
            variable=self.lang_var,
            fg_color="#020617",
            button_color="#111827",
            button_hover_color="#1f2937",
            text_color=PALETTE["text"],
            dropdown_fg_color="#020617",
            dropdown_text_color=PALETTE["text"],
            font=("Inter", 10),
            width=70,
            corner_radius=14,

        )
        lang_menu.grid(row=0, column=1, padx=(0, 16), sticky="w")

        # theme row
        ctk.CTkLabel(
            controls, text="Theme", text_color=PALETTE["muted"], font=("Inter", 10)
        ).grid(row=0, column=2, padx=(0, 6), sticky="w")

        theme_menu = ctk.CTkOptionMenu(
            controls,
            values=["Dark", "Light"],
            variable=self.theme_var,
            fg_color="#020617",
            button_color="#111827",
            button_hover_color="#1f2937",
            text_color=PALETTE["text"],
            dropdown_fg_color="#020617",
            dropdown_text_color=PALETTE["text"],
            font=("Inter", 10),
            width=70,
            corner_radius=14,
        )
        theme_menu.grid(row=0, column=3, sticky="w")

        # ---------- gradient "button" ----------
        grad_pil = _create_gradient_button_img(190, 40)
        self._btn_grad_img = ctk.CTkImage(light_image=grad_pil, size=(190, 40))

        self.primary_btn = ctk.CTkLabel(
            self.card,
            text="",
            image=self._btn_grad_img,
            compound="center",
            text_color="#020617",
            font=("Inter", 14, "bold"),
        )
        self.primary_btn.grid(row=4, column=0, padx=20, pady=(4, 10), sticky="w")
        self.primary_btn.bind("<Button-1>", lambda e: self._on_continue())
        self.primary_btn.bind("<Enter>", lambda e: self.primary_btn.configure(cursor="hand2"))

        # реакції на зміну мови/теми
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
            tagline = "Your emotion-aware study & work companion"
            features = (
                "We track your emotions from the webcam and gently suggest micro-breaks so you burn out less while studying and working."
            )
            btn_text = "Start"
        else:
            tagline = "Твій емоційно-чутливий асистент для навчання й роботи"
            features = (
                "Ми відстежуємо емоції з вебкамери та час від часу пропонуємо мікропаузи, щоб ти менше вигорав/ла під час навчання та роботи."
            )
            btn_text = "Почати"

        self.tagline_lbl.configure(text=tagline)
        self.features_lbl.configure(text=features)
        self.primary_btn.configure(text=btn_text)

    def _maybe_play_music(self):
        # macOS: граємо через afplay
        if sys.platform != "darwin":
            return

        try:
            # якщо вже грає — не стартуємо знов
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
        cfg = load_cfg()
        cfg["language"] = self.lang_var.get().upper()
        cfg["theme"] = (
            "Light" if self.theme_var.get().lower().startswith("light") else "Dark"
        )
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
