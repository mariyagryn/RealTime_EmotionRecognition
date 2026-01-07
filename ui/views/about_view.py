from __future__ import annotations

import os
from pathlib import Path
import customtkinter as ctk

_HAS_PIL = False
try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    Image = None


class AboutView(ctk.CTkFrame):
    """
    About screen identical in style to old _build_about_view(),
    але з розширеним описом режимів мікропауз.
    """

    def __init__(self, parent, palette: dict, get_lang, assets_dir: str | None = None):
        super().__init__(parent, fg_color="transparent")

        self.palette = palette
        self.get_lang = get_lang

        # assets path
        if assets_dir:
            self._assets_dir = Path(assets_dir)
        else:
            # ui/views/about_view.py -> ui/assets
            self._assets_dir = Path(__file__).resolve().parents[1] / "assets"

        # refs для картинок
        self._about_bg_img = None
        self._about_plus_img = None
        self._about_bg_label = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build()

    def _asset(self, name: str) -> str:
        return str(self._assets_dir / name)

    def rebuild(self):
        """Перебудувати вʼюху (коли міняємо мову)."""
        for child in self.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self._about_bg_img = None
        self._about_plus_img = None
        self._about_bg_label = None
        self._build()

    def _build(self):
        # поточна мова
        lang = str(self.get_lang() or "UA").upper()

        # ---- фон ----
        if _HAS_PIL:
            try:
                bg_path = self._asset("background.jpg")
                if not os.path.exists(bg_path):
                    bg_path = self._asset("background.png")

                img = Image.open(bg_path)
                self._about_bg_img = ctk.CTkImage(
                    light_image=img,
                    dark_image=img,
                    size=(1024, 640),
                )
                self._about_bg_label = ctk.CTkLabel(
                    self,
                    image=self._about_bg_img,
                    text="",
                )
                self._about_bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            except Exception as e:
                print("Cannot load About background:", e)

        # ---- картка ----
        # для EN робимо вищу картку, щоб текст не обрізався
        card_height = 0.60 if lang != "EN" else 0.70

        card = ctk.CTkFrame(
            self,
            fg_color="#020617",
            corner_radius=5,
            border_width=1,
            border_color="#1e40af",
        )
        card.place(relx=0.07, rely=0.18, anchor="nw", relwidth=0.48, relheight=card_height)

        # ---- тексти EN / UA ----
        if lang == "EN":
            title = "What is MoodTracker?"
            intro = (
                "MoodTracker is a desktop assistant that helps you track "
                "your emotional state while studying or working at the computer."
            )
            bullets_main = [
                "Analyses emotions from your webcam in real time using deep learning models (DeepFace / FER).",
                "Measures how long you stay in each emotion and detects moments of fatigue, stress or long neutral “zoning out”.",
                "Saves statistics for every session and builds clear charts so you can see your emotional dynamics over time.",
            ]
            modes_caption = "How micro-break modes work:"
            bullets_modes = [
                "Breathing — a short guided breathing break (about 60 seconds) to lower tension and reset your focus.",
                "Pomodoro — suggests a small focus + rest cycle when you stay neutral for a long time, so you can change activity and avoid burnout.",
                "Mirror — reminds you to stand up for a moment, stretch your neck and shoulders, correct posture and relax your face muscles.",
                "Speech — a tiny voice dialogue: the app asks how you feel, listens to your answer and reacts with friendly comments.",
            ]
            wrap_main = 470
            wrap_bullets = 470
        else:
            title = "Що таке MoodTrackerr?"
            intro = (
                "MoodTracker — це настільний асистент, який допомагає "
                "відстежувати твій емоційний стан під час навчання або роботи за компʼютером."
            )
            bullets_main = [
                "Аналізує емоції з вебкамери в реальному часі за допомогою моделей глибокого навчання (DeepFace / FER).",
                "Вимірює, скільки часу ти перебуваєш у кожній емоції, і помічає моменти втоми, стресу або довгого нейтрального «зависання».",
                "Зберігає статистику кожної сесії та будує зрозумілі графіки, щоб ти бачив/ла свою емоційну динаміку з часом.",
            ]
            modes_caption = "Як працюють режими мікропауз:"
            bullets_modes = [
                "Breathing — коротка дихальна пауза приблизно на 60 секунд, щоб знизити напругу та перезавантажити увагу.",
                "Pomodoro — пропонує міні-цикл фокусу й відпочинку, коли ти довго сидиш у нейтральному стані, щоб змінити активність і не вигоріти.",
                "Mirror — нагадує встати, вирівняти спину, розімʼяти шию та плечі й розслабити мімічні мʼязи.",
                "Speech — невелика голосова розмова: застосунок запитує, як ти почуваєшся, «слухає» відповідь і реагує дружніми коментарями.",
            ]
            wrap_main = 430
            wrap_bullets = 430

        # ---- заголовок ----
        ctk.CTkLabel(
            card,
            text=title,
            font=("Inter", 20, "bold"),
            text_color="#5df0ff",
            anchor="w",
            justify="left",
        ).pack(anchor="w", padx=26, pady=(22, 8))

        # ---- вступ ----
        ctk.CTkLabel(
            card,
            text=intro,
            font=("Inter", 13),
            text_color=self.palette["text"],
            justify="left",
            anchor="nw",
            wraplength=wrap_main,
        ).pack(anchor="w", padx=26, pady=(0, 12), fill="x")

        # ---- плюс-іконка ----
        if _HAS_PIL:
            try:
                plus_raw = Image.open(self._asset("plus.png"))
                self._about_plus_img = ctk.CTkImage(plus_raw, size=(18, 18))
            except Exception as e:
                print("Cannot load plus icon:", e)

        def add_bullet_row(parent_frame, text: str):
            row = ctk.CTkFrame(parent_frame, fg_color="transparent")
            row.pack(anchor="w", fill="x", pady=2)

            if self._about_plus_img is not None:
                icon = ctk.CTkLabel(row, image=self._about_plus_img, text="")
            else:
                icon = ctk.CTkLabel(
                    row,
                    text="+",
                    font=("Inter", 18, "bold"),
                    text_color="#38bdf8",
                )
            icon.grid(row=0, column=0, sticky="n", padx=(6, 10), pady=(3, 0))

            txt_lbl = ctk.CTkLabel(
                row,
                text=text,
                font=("Inter", 14),
                text_color=self.palette["text"],
                justify="left",
                anchor="w",
                wraplength=wrap_bullets,
            )
            txt_lbl.grid(row=0, column=1, sticky="w")

        # ---- основні можливості ----
        bullets_frame_main = ctk.CTkFrame(card, fg_color="transparent")
        bullets_frame_main.pack(
            anchor="w",
            padx=20,
            pady=(0, 4),
            fill="both",
            expand=False,
        )
        for text in bullets_main:
            add_bullet_row(bullets_frame_main, text)

        # ---- підзаголовок режимів ----
        ctk.CTkLabel(
            card,
            text=modes_caption,
            font=("Inter", 14, "bold"),
            text_color="#a5f3fc",
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=26, pady=(4, 2))

        # ---- режими мікропауз ----
        bullets_frame_modes = ctk.CTkFrame(card, fg_color="transparent")
        bullets_frame_modes.pack(
            anchor="w",
            padx=20,
            pady=(0, 12),
            fill="both",
            expand=True,
        )
        for text in bullets_modes:
            add_bullet_row(bullets_frame_modes, text)
