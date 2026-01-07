# ui/views/stats_view.py
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from ui.common import LABELS, EMO_COLORS, fmt_mmss, fmt_hhmm
from core.storage import load_stats_aggregate, load_moments_aggregate

PERIOD_KEYS = ["Today", "Last 7 days", "All time"]

STATS_I18N = {
    "UA": {
        "title": "Статистика сесій",
        "subtitle": "Час в кожній емоції.",
        "summary": "Сесій: {n}   |   Загальний час: {t}   |   Моментів: {m}",
        "period_values": ["Сьогодні", "Останні 7 днів", "За весь час"],
        "export_pdf": "Експортувати в PDF",
        "no_data": "Даних поки що немає…",
        "moments_title": "Моменти • {p}",
        "no_moments": "Немає моментів",
        "moments_word": "моментів",
    },
    "EN": {
        "title": "Session statistics",
        "subtitle": "Time in each emotion.",
        "summary": "Sessions: {n}   |   Total time: {t}   |   Moments: {m}",
        "period_values": ["Today", "Last 7 days", "All time"],
        "export_pdf": "Export to PDF",
        "no_data": "No data yet…",
        "moments_title": "Moments • {p}",
        "no_moments": "No moments",
        "moments_word": "moments",
    },
}


class StatsView(ctk.CTkFrame):
    def __init__(self, parent, palette: dict, lang: str, on_export_pdf, on_go_moments=None):
        super().__init__(parent, fg_color="transparent")

        self.palette = palette
        self.lang = (lang or "UA").upper()
        self._texts = STATS_I18N.get(self.lang, STATS_I18N["UA"])

        self.on_export_pdf = on_export_pdf
        self.on_go_moments = on_go_moments

        self._period_key = "Today"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(self, fg_color=self.palette["panel"], corner_radius=18)
        card.grid(row=0, column=0, sticky="nsew", padx=32, pady=26)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(1, weight=1)
        card.grid_rowconfigure(2, weight=1)

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

        header_right = ctk.CTkFrame(card, fg_color="transparent")
        header_right.grid(row=0, column=1, sticky="e", padx=26, pady=(18, 12))
        header_right.grid_columnconfigure(0, weight=1)

        self.summary_lbl = ctk.CTkLabel(
            header_right,
            text="",
            font=("Inter", 12),
            text_color=self.palette["muted"],
        )
        self.summary_lbl.grid(row=0, column=0, padx=(0, 18), sticky="e")

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
        self.btn_export.grid(row=1, column=0, pady=(8, 0), sticky="e")

        go_txt = "Go to Moments" if self.lang == "EN" else "Перейти до моментів"
        self.btn_go_moments = ctk.CTkButton(
            header_right,
            text=go_txt,
            height=28,
            corner_radius=18,
            fg_color=self.palette["control_bg"],
            hover_color=self.palette["hover"],
            text_color=self.palette["text"],
            command=(self.on_go_moments if self.on_go_moments else None),
        )
        self.btn_go_moments.grid(row=1, column=1, padx=(10, 0), pady=(8, 0), sticky="e")

        self.bar_canvas = tk.Canvas(
            card,
            bg=self.palette["panel"],
            highlightthickness=0,
            bd=0,
            height=170,
        )
        self.bar_canvas.grid(row=1, column=0, sticky="nsew", padx=(26, 12), pady=(0, 10))

        self.moments_pie_canvas = tk.Canvas(
            card,
            bg=self.palette["panel"],
            highlightthickness=0,
            bd=0,
            width=320,
            height=170,
        )
        self.moments_pie_canvas.grid(row=1, column=1, sticky="nsew", padx=(12, 26), pady=(0, 10))


        # ----- bottom row (pie + progress bars) -----
        self.pie_canvas = tk.Canvas(
            card,
            bg=self.palette["panel"],
            highlightthickness=0,
            bd=0,
            width=340,
            height=260,
        )
        self.pie_canvas.grid(row=2, column=0, sticky="nsew", padx=(26, 12), pady=(0, 22))

        self.hbars_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.hbars_frame.grid(row=2, column=1, sticky="nsew", padx=(12, 26), pady=(0, 22))
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

    # ---------- API ----------
    def set_lang(self, lang: str):
        self.lang = (lang or "UA").upper()
        self._texts = STATS_I18N.get(self.lang, STATS_I18N["UA"])

        self.title_lbl.configure(text=self._texts["title"])
        self.subtitle_lbl.configure(text=self._texts["subtitle"])
        self.btn_export.configure(text=self._texts["export_pdf"])
        self.btn_go_moments.configure(text=("Go to Moments" if self.lang == "EN" else "Перейти до моментів"))

        try:
            idx = PERIOD_KEYS.index(self._period_key)
        except ValueError:
            idx = 0
        self.period_menu.configure(values=self._texts["period_values"])
        self.period_var.set(self._texts["period_values"][idx])

        self.draw()

    def _on_period_change(self, shown_value: str):
        values = self._texts["period_values"]
        try:
            idx = values.index(shown_value)
        except ValueError:
            idx = 0
        self._period_key = PERIOD_KEYS[idx]
        self.draw()

    # ---------- drawing ----------
    def _draw_no_data(self):
        for cnv in (self.bar_canvas, self.pie_canvas, self.moments_canvas):
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

    def _draw_bar(self, totals: dict[str, float]):
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
            val = float(totals.get(emo, 0.0) or 0.0)
            ratio = val / max_val if max_val > 0 else 0.0
            bar_h = chart_h * ratio

            x_center = margin_x + slot_w * (i + 0.5)
            bw = slot_w * 0.5
            x0 = x_center - bw / 2
            x1 = x_center + bw / 2
            y1 = H - margin_y_bottom
            y0 = y1 - bar_h

            cnv.create_rectangle(x0, y0, x1, y1, fill=EMO_COLORS.get(emo, self.palette["accent"]), outline="")
            cnv.create_text(
                x_center,
                H - margin_y_bottom + 14,
                text=emo.capitalize(),
                fill=self.palette["muted"],
                font=("Inter", 10),
            )

    def _draw_emotions_pie(self, totals: dict[str, float], total_sec: float):
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
            v = float(totals.get(emo, 0.0) or 0.0)
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

    def _draw_moments_pie(self, moments_total: int, moments_by_emo: dict[str, int]):
        cnv = self.moments_pie_canvas

        cnv.delete("all")

        W = int(cnv.winfo_width() or 320)
        H = int(cnv.winfo_height() or 170)

        period_name = self.period_var.get()
        title = ("Moments • " + period_name) if self.lang == "EN" else ("Моменти • " + period_name)
        cnv.create_text(10, 10, text=title, fill=self.palette["muted"], font=("Inter", 12, "bold"), anchor="nw")

        # беремо моменти по ВСІХ емоціях (а не тільки trigger)
        vals = {e: int(moments_by_emo.get(e, 0) or 0) for e in LABELS}
        total = int(moments_total or 0)

        if total <= 0:
            msg = "No moments" if self.lang == "EN" else "Немає моментів"
            cnv.create_text(W // 2, H // 2, text=msg, fill=self.palette["muted"], font=("Inter", 12))
            return

        # відмалюємо тільки ті, де > 0
        items = [(emo, v) for emo, v in vals.items() if v > 0]
        items.sort(key=lambda x: x[1], reverse=True)

        # --- PIE (сектори) ---
        radius = min(W, H) * 0.40
        cx = W * 0.33
        cy = H * 0.60

        x0, y0 = cx - radius, cy - radius
        x1, y1 = cx + radius, cy + radius

        start_angle = 90.0
        for emo, v in items:
            extent = 360.0 * (v / total)
            cnv.create_arc(
                x0, y0, x1, y1,
                start=start_angle,
                extent=-extent,
                style="pieslice",
                outline=self.palette["panel"],
                width=1,
                fill=EMO_COLORS.get(emo, self.palette["accent"]),
            )
            start_angle -= extent

        # --- DONUT HOLE (якщо хочеш саме donut) ---
        # Якщо хочеш ЧИСТО pie без дірки — просто закоментуй цей блок.
        inner = radius * 0.55
        cnv.create_oval(cx - inner, cy - inner, cx + inner, cy + inner, fill=self.palette["panel"], outline="")

        cnv.create_text(cx, cy - 2, text=str(total), fill=self.palette["text"], font=("Inter", 18, "bold"))
        cnv.create_text(
            cx, cy + 18,
            text=("moments" if self.lang == "EN" else "моментів"),
            fill=self.palette["muted"],
            font=("Inter", 10),
        )

        # --- легенда справа ---
        lx = W * 0.62
        ly = H * 0.33
        step = 18

        for i, (emo, v) in enumerate(items[:6]):  # топ-6 щоб не розлазилось
            y = ly + i * step
            cnv.create_rectangle(lx, y, lx + 10, y + 10, fill=EMO_COLORS.get(emo, self.palette["accent"]), outline="")
            cnv.create_text(
                lx + 16, y + 5,
                text=f"{emo.capitalize()}: {v}",
                fill=self.palette["text"],
                font=("Inter", 11),
                anchor="w",
            )

        cnv.create_text(lx, ly + min(len(items), 6) * step + 10, text=f"Total: {total}", fill=self.palette["muted"],
                        font=("Inter", 10), anchor="w")

    def _update_progress_bars(self, totals: dict[str, float], total_sec: float):
        for emo in LABELS:
            sec = float(totals.get(emo, 0.0) or 0.0)
            pct = sec / total_sec if total_sec > 0 else 0.0
            self.pbars[emo].set(pct)
            self.pbar_labels[emo].configure(text=f"{fmt_mmss(sec)}  {int(pct * 100):02d}%")

    def draw(self):
        totals, sessions_count, total_sec = load_stats_aggregate(self._period_key)
        moments_total, moments_by_emo = load_moments_aggregate(self._period_key)

        self.summary_lbl.configure(
            text=self._texts["summary"].format(n=sessions_count, t=fmt_hhmm(total_sec), m=moments_total)
        )

        # moments donut малюємо завжди (навіть коли total_sec == 0)
        self._draw_moments_pie(moments_total, moments_by_emo)


        if total_sec <= 0:
            self._draw_no_data()
            # але moments donut щойно намалювали, тому перемалюємо його ще раз
            self._draw_moments_pie(moments_total, moments_by_emo)

            return

        self._draw_bar(totals)
        self._draw_emotions_pie(totals, total_sec)
        self._update_progress_bars(totals, total_sec)
