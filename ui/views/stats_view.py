# ui/views/stats_view.py
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk

from ui.common import LABELS, EMO_COLORS, fmt_mmss, fmt_hhmm
from core.storage import load_stats_aggregate

# ---- I18N для статистики ----

PERIOD_KEYS = ["Today", "Last 7 days", "All time"]

STATS_I18N = {
    "UA": {
        "title": "Статистика сесій",
        "subtitle": "Час в кожній емоції.",
        "summary": "Сесій: {n}   |   Загальний час: {t}",
        "period_values": ["Сьогодні", "Останні 7 днів", "За весь час"],
        "export_pdf": "Експортувати в PDF",
        "no_data": "Даних поки що немає…",
    },
    "EN": {
        "title": "Session statistics",
        "subtitle": "Time in each emotion.",
        "summary": "Sessions: {n}   |   Total time: {t}",
        "period_values": ["Today", "Last 7 days", "All time"],
        "export_pdf": "Export to PDF",
        "no_data": "No data yet…",
    },
}


class StatsView(ctk.CTkFrame):
    def __init__(self, parent, palette: dict, lang: str, on_export_pdf):
        super().__init__(parent, fg_color="transparent")

        self.palette = palette
        self.lang = (lang or "UA").upper()
        self.on_export_pdf = on_export_pdf

        # поточний набір текстів
        self._texts = STATS_I18N.get(self.lang, STATS_I18N["UA"])

        # внутрішній ключ періоду для load_stats_aggregate
        self._period_key = "Today"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(self, fg_color=self.palette["panel"], corner_radius=18)
        card.grid(row=0, column=0, sticky="nsew", padx=32, pady=26)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(1, weight=1)
        card.grid_rowconfigure(2, weight=1)

        # ----- заголовок зліва -----
        header_left = ctk.CTkFrame(card, fg_color="transparent")
        header_left.grid(row=0, column=0, sticky="w", padx=26, pady=(18, 12))

        self.title_lbl = ctk.CTkLabel(
            header_left,
            text=self._texts["title"],
            font=("Inter", 18, "bold"),
            text_color=self.palette["text"],
        )
        self.title_lbl.pack(anchor="w")

        self.subtitle_lbl = ctk.CTkLabel(
            header_left,
            text=self._texts["subtitle"],
            font=("Inter", 12),
            text_color=self.palette["muted"],
        )
        self.subtitle_lbl.pack(anchor="w")

        # ----- хедер справа (період + summary + PDF) -----
        header_right = ctk.CTkFrame(card, fg_color="transparent")
        header_right.grid(row=0, column=1, sticky="e", padx=26, pady=(18, 12))

        self.summary_lbl = ctk.CTkLabel(
            header_right,
            text="",
            font=("Inter", 12),
            text_color=self.palette["muted"],
        )
        self.summary_lbl.grid(row=0, column=0, padx=(0, 18), sticky="e")

        # значення періоду, яке бачить юзер
        self.period_var = tk.StringVar(value=self._texts["period_values"][0])

        self.period_menu = ctk.CTkOptionMenu(
            header_right,
            values=self._texts["period_values"],
            variable=self.period_var,
            width=130,
            fg_color=self.palette["panel"],
            button_color=self.palette["accent"],
            button_hover_color=self.palette["accent_h"],
            text_color=self.palette["text"],
            command=self._on_period_change,
        )
        self.period_menu.grid(row=0, column=1, sticky="e")

        self.btn_export = ctk.CTkButton(
            header_right,
            text=self._texts["export_pdf"],
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_h"],
            text_color="black",
            height=28,
            corner_radius=18,
            command=self.on_export_pdf,
        )
        self.btn_export.grid(row=1, column=0, columnspan=2, pady=(8, 0), sticky="e")

        # ----- канваси -----
        self.bar_canvas = tk.Canvas(
            card,
            bg=self.palette["panel"],
            highlightthickness=0,
            bd=0,
            height=170,
        )
        self.bar_canvas.grid(
            row=1, column=0, columnspan=2,
            sticky="nsew", padx=26, pady=(0, 10),
        )

        self.pie_canvas = tk.Canvas(
            card,
            bg=self.palette["panel"],
            highlightthickness=0,
            bd=0,
            width=340,
            height=260,
        )
        self.pie_canvas.grid(
            row=2, column=0,
            sticky="w", padx=(26, 12), pady=(0, 22),
        )

        # ----- горизонтальні бари справа -----
        self.hbars_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.hbars_frame.grid(
            row=2, column=1,
            sticky="nsew", padx=(12, 26), pady=(0, 22),
        )
        self.hbars_frame.grid_columnconfigure(1, weight=1)

        self.pbars: dict[str, ctk.CTkProgressBar] = {}
        self.pbar_labels: dict[str, ctk.CTkLabel] = {}

        for i, emo in enumerate(LABELS):
            name_lbl = ctk.CTkLabel(
                self.hbars_frame,
                text=emo.capitalize(),
                font=("Inter", 12),
                text_color=self.palette["text"],
            )
            name_lbl.grid(row=i, column=0, padx=(0, 8), pady=4, sticky="w")

            pbar = ctk.CTkProgressBar(
                self.hbars_frame,
                height=8,
                fg_color="#020617",
                progress_color=EMO_COLORS.get(emo, self.palette["accent"]),
                corner_radius=50,
            )
            pbar.grid(row=i, column=1, padx=8, pady=4, sticky="ew")

            val_lbl = ctk.CTkLabel(
                self.hbars_frame,
                text="00:00  0%",
                font=("Inter", 11),
                text_color=self.palette["muted"],
            )
            val_lbl.grid(row=i, column=2, padx=(8, 0), pady=4, sticky="e")

            self.pbars[emo] = pbar
            self.pbar_labels[emo] = val_lbl

        card.bind("<Configure>", lambda _e: self.draw())
        self.draw()

    # ---------- API для LiveWindow ----------

    def set_lang(self, lang: str):
        """Викликається з LiveWindow при зміні мови."""
        self.lang = (lang or "UA").upper()
        self._texts = STATS_I18N.get(self.lang, STATS_I18N["UA"])

        # оновлюємо статичні тексти
        self.title_lbl.configure(text=self._texts["title"])
        self.subtitle_lbl.configure(text=self._texts["subtitle"])
        self.btn_export.configure(text=self._texts["export_pdf"])

        # оновлюємо список періодів, зберігаючи поточний key
        try:
            idx = PERIOD_KEYS.index(self._period_key)
        except ValueError:
            idx = 0

        self.period_menu.configure(values=self._texts["period_values"])
        self.period_var.set(self._texts["period_values"][idx])

        # перемалювати з новими підписами
        self.draw()

    # ---------- внутрішня логіка ----------

    def _on_period_change(self, shown_value: str):
        """Перекладаємо те, що бачить юзер, у внутрішній ключ."""
        values = self._texts["period_values"]
        try:
            idx = values.index(shown_value)
        except ValueError:
            idx = 0
        self._period_key = PERIOD_KEYS[idx]
        self.draw()

    def draw(self):
        # беремо агрегацію по внутрішньому ключу
        totals, sessions_count, total_sec = load_stats_aggregate(self._period_key)

        summary_text = self._texts["summary"].format(
            n=sessions_count,
            t=fmt_hhmm(total_sec),
        )
        self.summary_lbl.configure(text=summary_text)

        # якщо немає даних
        if total_sec <= 0:
            for cnv in (self.bar_canvas, self.pie_canvas):
                cnv.delete("all")
                w = int(cnv.winfo_width() or 300)
                h = int(cnv.winfo_height() or 120)
                cnv.create_text(
                    w // 2,
                    h // 2,
                    text=self._texts["no_data"],
                    fill=self.palette["muted"],
                    font=("Inter", 12),
                )
            for emo in LABELS:
                self.pbars[emo].set(0)
                self.pbar_labels[emo].configure(text="00:00  0%")
            return

        # ---------- bar chart ----------
        cnv = self.bar_canvas
        cnv.delete("all")
        W = int(cnv.winfo_width() or 640)
        H = int(cnv.winfo_height() or 170)

        margin_x = 40
        margin_y_top = 15
        margin_y_bottom = 32
        chart_w = W - 2 * margin_x
        chart_h = H - margin_y_top - margin_y_bottom
        max_val = max(totals.values()) or 1.0

        cnv.create_line(
            margin_x,
            H - margin_y_bottom,
            W - margin_x,
            H - margin_y_bottom,
            fill="#1f2937",
            width=1,
        )

        slot_w = chart_w / max(len(LABELS), 1)

        for i, emo in enumerate(LABELS):
            val = totals.get(emo, 0.0)
            ratio = val / max_val if max_val > 0 else 0
            bar_h = chart_h * ratio

            x_center = margin_x + slot_w * (i + 0.5)
            bw = slot_w * 0.5
            x0 = x_center - bw / 2
            x1 = x_center + bw / 2
            y1 = H - margin_y_bottom
            y0 = y1 - bar_h

            cnv.create_rectangle(
                x0, y0, x1, y1,
                fill=EMO_COLORS.get(emo, self.palette["accent"]),
                outline="",
            )
            cnv.create_text(
                x_center,
                H - margin_y_bottom + 14,
                text=emo.capitalize(),
                fill=self.palette["muted"],
                font=("Inter", 10),
            )

        # ---------- pie chart ----------
        pie = self.pie_canvas
        pie.delete("all")
        PW = int(pie.winfo_width() or 340)
        PH = int(pie.winfo_height() or 260)
        radius = min(PW, PH) * 0.45

        cx = PW / 2
        cy = PH / 2
        x0, y0 = cx - radius, cy - radius
        x1, y1 = cx + radius, cy + radius

        start_angle = 90.0
        for emo in LABELS:
            v = totals.get(emo, 0.0)
            if v <= 0:
                continue
            extent = 360.0 * (v / total_sec)
            pie.create_arc(
                x0, y0, x1, y1,
                start=start_angle,
                extent=-extent,
                style="pieslice",
                outline=self.palette["panel"],
                width=1,
                fill=EMO_COLORS.get(emo, self.palette["accent"]),
            )
            start_angle -= extent

        # оновлюємо праві прогрес-бари
        for emo in LABELS:
            sec = totals.get(emo, 0.0)
            pct = sec / total_sec if total_sec > 0 else 0.0
            self.pbars[emo].set(pct)
            self.pbar_labels[emo].configure(
                text=f"{fmt_mmss(sec)}  {int(pct * 100):02d}%"
            )
