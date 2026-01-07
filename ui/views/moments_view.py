# ui/views/moments_view.py
from __future__ import annotations

import os
import sys
import subprocess
from datetime import datetime

import tkinter as tk
import customtkinter as ctk

from ui.common import EMO_COLORS
from core.storage import load_moments_list


class MomentsView(ctk.CTkFrame):
    def __init__(self, parent, palette: dict, lang: str):
        super().__init__(parent, fg_color="transparent")

        self.palette = palette
        self.lang = (lang or "UA").upper()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(self, fg_color=self.palette["panel"], corner_radius=18)
        card.grid(row=0, column=0, sticky="nsew", padx=32, pady=26)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(18, 12))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        text_frame = ctk.CTkFrame(header, fg_color="transparent")
        text_frame.grid(row=0, column=0, sticky="w")

        self.title_lbl = ctk.CTkLabel(
            text_frame,
            text="",
            font=("Inter", 18, "bold"),
            text_color=self.palette["text"],
        )
        self.title_lbl.pack(anchor="w")

        self.subtitle_lbl = ctk.CTkLabel(
            text_frame,
            text="",
            font=("Inter", 12),
            text_color=self.palette["muted"],
        )
        self.subtitle_lbl.pack(anchor="w")

        right_frame = ctk.CTkFrame(header, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="e")

        self.summary_lbl = ctk.CTkLabel(
            right_frame,
            text="",
            font=("Inter", 12),
            text_color=self.palette["muted"],
        )
        self.summary_lbl.grid(row=0, column=0, padx=(0, 18), sticky="e")

        self.period_var = tk.StringVar(value="Today")
        self.period_menu = ctk.CTkOptionMenu(
            right_frame,
            values=["Today", "Last 7 days", "All time"],
            variable=self.period_var,
            width=130,
            fg_color=self.palette["panel"],
            button_color=self.palette["accent"],
            button_hover_color=self.palette["accent_h"],
            text_color=self.palette["text"],
            command=lambda _v: self.draw(),
        )
        self.period_menu.grid(row=0, column=1, sticky="e")

        self.list_frame = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.list_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=26,
            pady=(0, 22),
        )
        self.list_frame.grid_columnconfigure(0, weight=0)
        self.list_frame.grid_columnconfigure(1, weight=1)
        self.list_frame.grid_columnconfigure(2, weight=0)

        self._update_texts()
        self.draw()


    def set_lang(self, lang: str):
        self.lang = (lang or "UA").upper()
        self._update_texts()
        self.draw()


    def _update_texts(self):
        if self.lang == "EN":
            self.title_lbl.configure(text="Emotional moments")
            self.subtitle_lbl.configure(
                text="Short screen recordings saved in key emotional states."
            )
        else:
            self.title_lbl.configure(text="Емоційні моменти")
            self.subtitle_lbl.configure(
                text="Короткі записи екрана в особливих емоційних станах."
            )

    def draw(self):
        period = self.period_var.get()
        moments = load_moments_list(period)

        if self.lang == "EN":
            word = "moments"
            no_data = "No emotional moments yet for this period."
        else:
            word = "моментів"
            no_data = "Емоційних моментів за цей період поки немає."

        self.summary_lbl.configure(text=f"{len(moments)} {word}")

        for child in self.list_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        if not moments:
            ctk.CTkLabel(
                self.list_frame,
                text=no_data,
                font=("Inter", 12),
                text_color=self.palette["muted"],
                wraplength=600,
                justify="left",
            ).grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=6)
            return

        for idx, row in enumerate(moments):
            emo_raw = (row.get("emotion") or "").strip()
            emo = emo_raw.capitalize()
            color = EMO_COLORS.get(emo_raw.lower(), self.palette["accent"])

            ts_str = row.get("timestamp") or ""
            try:
                dt = datetime.fromisoformat(ts_str)
                date_txt = dt.strftime("%Y-%m-%d")
                time_txt = dt.strftime("%H:%M:%S")
            except Exception:
                date_txt = ts_str
                time_txt = ""

            streak = row.get("streak_sec") or row.get("streak") or 0
            try:
                streak_f = float(streak)
            except Exception:
                streak_f = 0.0

            conf = row.get("conf") or row.get("confidence") or 0
            try:
                conf_f = float(conf)
            except Exception:
                conf_f = 0.0

            sess = row.get("session_id") or row.get("session") or ""
            video_path = row.get("video_path") or row.get("path") or ""

            dot = ctk.CTkFrame(
                self.list_frame,
                width=10,
                height=10,
                fg_color=color,
                corner_radius=999,
            )
            dot.grid(row=idx, column=0, padx=(6, 10), pady=8, sticky="n")

            text_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            text_frame.grid(row=idx, column=1, sticky="w", pady=4)

            if self.lang == "EN":
                line1 = f"{date_txt}  •  {time_txt}  •  {emo}"
                if sess:
                    line1 += f"  •  Session {sess}"
                line2 = (
                    f"Streak: {streak_f:0.0f}s   |   "
                    f"Confidence: {int(conf_f * 100)}%"
                )
            else:
                line1 = f"{date_txt}  •  {time_txt}  •  {emo}"
                if sess:
                    line1 += f"  •  Сесія {sess}"
                line2 = (
                    f"Тривалість емоції: {streak_f:0.0f} с   |   "
                    f"Впевненість: {int(conf_f * 100)}%"
                )

            ctk.CTkLabel(
                text_frame,
                text=line1,
                font=("Inter", 13, "bold"),
                text_color=self.palette["text"],
                anchor="w",
                justify="left",
            ).pack(anchor="w")

            ctk.CTkLabel(
                text_frame,
                text=line2,
                font=("Inter", 11),
                text_color=self.palette["muted"],
                anchor="w",
                justify="left",
            ).pack(anchor="w", pady=(2, 0))

            btn_txt = "Open" if self.lang == "EN" else "Відкрити"
            ctk.CTkButton(
                self.list_frame,
                text=btn_txt,
                width=80,
                height=26,
                fg_color=self.palette["accent"],
                hover_color=self.palette["accent_h"],
                text_color="black",
                command=lambda p=video_path: self._open_moment(p),
            ).grid(row=idx, column=2, padx=(10, 6), pady=6, sticky="e")

    def _open_moment(self, path: str):
        if not path:
            print("No moment path")
            return

        if not os.path.isabs(path):
            candidate = os.path.join("storage", "moments", path)
            if os.path.exists(candidate):
                path = candidate

        if not os.path.exists(path):
            print("Moment video not found:", path)
            return

        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print("Open moment error:", e)
