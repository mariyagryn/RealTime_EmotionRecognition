# ui/views/live_view.py
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
import cv2

from ui.common import LABELS, EMO_COLORS, fmt_mmss

_HAS_PIL = False
try:
    from PIL import Image, ImageTk  # type: ignore
    _HAS_PIL = True
except Exception:
    Image = None
    ImageTk = None


class LiveView(ctk.CTkFrame):
    """
    Чиста візуальна частина. Ніяких потоків/камери тут немає.
    LiveWindow ззовні:
      - підсовує кадри через show_frame(...)
      - оновлює FPS, емоції, статистику, рекордінг через методи нижче.
    """

    def __init__(
        self,
        parent,
        palette: dict,
        on_pause,
        on_snap,
        on_record,
        on_exit,
    ):
        super().__init__(parent, fg_color="transparent")
        self.palette = palette

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # ---------- canvas з відео ----------
        self.canvas = tk.Canvas(
            self,
            bg=self.palette["bg"],
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        self._fps_lbl = self.canvas.create_text(
            10, 10,
            anchor="nw",
            text="",
            fill="#9fb3c6",
            font=("Inter", 11, "bold"),
        )
        self._emo_lbl = self.canvas.create_text(
            10, 28,
            anchor="nw",
            text="",
            fill=self.palette["text"],
            font=("Inter", 12, "bold"),
        )

        self._tkimg = None
        self._img_id = None
        self._autosized = False

        # ---------- sidebar ----------
        self.sidebar = ctk.CTkFrame(
            self,
            fg_color=self.palette["panel"],
            corner_radius=14,
        )
        self.sidebar.grid(row=0, column=1, sticky="ns", padx=(6, 12), pady=12)
        self.sidebar.grid_rowconfigure(99, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="Live Controls",
            text_color=self.palette["text"],
            font=("Inter", 16, "bold"),
        ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")

        self.btn_pause = ctk.CTkButton(
            self.sidebar,
            text="Pause",
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_h"],
            text_color="black",
            command=on_pause,
        )
        self.btn_pause.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")

        self.btn_snap = ctk.CTkButton(
            self.sidebar,
            text="Snap",
            fg_color=self.palette["panel"],
            hover_color="#12243a",
            border_color=self.palette["border"],
            border_width=1,
            text_color=self.palette["text"],
            command=on_snap,
        )
        self.btn_snap.grid(row=2, column=0, padx=14, pady=8, sticky="ew")

        self._rec_led = ctk.CTkLabel(
            self.sidebar,
            text="● Not recording",
            text_color=self.palette["muted"],
        )
        self._rec_led.grid(row=3, column=0, padx=14, pady=(6, 6), sticky="w")

        self.btn_rec = ctk.CTkButton(
            self.sidebar,
            text="Start Recording",
            fg_color=self.palette["panel"],
            hover_color="#12243a",
            border_color=self.palette["border"],
            border_width=1,
            text_color=self.palette["text"],
            command=on_record,
        )
        self.btn_rec.grid(row=4, column=0, padx=14, pady=8, sticky="ew")

        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=self.palette["border"])
        sep.grid(row=9, column=0, sticky="ew", padx=14, pady=(8, 8))

        # ---------- Session stats ----------
        ctk.CTkLabel(
            self.sidebar,
            text="Session Stats",
            text_color=self.palette["text"],
            font=("Inter", 14, "bold"),
        ).grid(row=10, column=0, padx=14, pady=(0, 4), sticky="w")

        stats_tbl = ctk.CTkFrame(self.sidebar, fg_color=self.palette["panel"])
        stats_tbl.grid(row=11, column=0, padx=10, pady=(0, 8), sticky="ew")
        stats_tbl.grid_columnconfigure(0, weight=1)
        stats_tbl.grid_columnconfigure(1, weight=0)

        self._lbl_dom = ctk.CTkLabel(
            stats_tbl,
            text="Dominant: –",
            text_color=self.palette["muted"],
        )
        self._lbl_dom.grid(
            row=0, column=0, columnspan=2,
            padx=8, pady=(6, 6), sticky="w",
        )

        self._row_time: dict[str, ctk.CTkLabel] = {}
        self._row_frames: dict[str, ctk.CTkFrame] = {}
        self._row_labels: dict[str, ctk.CTkLabel] = {}

        r = 1
        for emo in LABELS:
            row = ctk.CTkFrame(
                stats_tbl,
                fg_color="transparent",
                corner_radius=999,
            )
            row.grid(
                row=r, column=0, columnspan=2,
                padx=0, pady=3, sticky="ew",
            )
            row.grid_columnconfigure(1, weight=1)

            dot = ctk.CTkFrame(
                row,
                width=10,
                height=10,
                corner_radius=99,
                fg_color=EMO_COLORS.get(emo, "#64748b"),
            )
            dot.grid(row=0, column=0, padx=(10, 10), pady=6, sticky="w")

            lab = ctk.CTkLabel(
                row,
                text=emo,
                text_color=self.palette["text"],
                font=("Inter", 13),
            )
            lab.grid(row=0, column=1, sticky="w")

            t = ctk.CTkLabel(
                row,
                text="00:00",
                text_color=self.palette["muted"],
                font=("Inter", 12),
            )
            t.grid(row=0, column=2, padx=(10, 10), sticky="e")

            self._row_frames[emo] = row
            self._row_labels[emo] = lab
            self._row_time[emo] = t
            r += 1

        # ---------- Hint для мікропауз ----------
        self._hint_lbl = ctk.CTkLabel(
            self.sidebar,
            text="",
            text_color="#a7f3d0",
            wraplength=260,
            justify="left",
        )
        self._hint_lbl.grid(row=15, column=0, padx=14, pady=(6, 10), sticky="w")

        self.btn_exit = ctk.CTkButton(
            self.sidebar,
            text="Exit",
            fg_color="#1f2937",
            hover_color="#111827",
            text_color="#ffffff",
            command=on_exit,
        )
        self.btn_exit.grid(row=98, column=0, padx=14, pady=(10, 10), sticky="ew")

    # ---------- API, яким керує LiveWindow ----------

    def set_paused(self, paused: bool):
        self.btn_pause.configure(text="Resume" if paused else "Pause")

    def set_recording(self, recording: bool):
        if recording:
            self._rec_led.configure(text="● Recording", text_color="#f87171")
            self.btn_rec.configure(text="Stop Recording")
        else:
            self._rec_led.configure(text="● Not recording", text_color=self.palette["muted"])
            self.btn_rec.configure(text="Start Recording")

    def flash_status(self, msg: str, recording: bool):
        self._rec_led.configure(text=f"• {msg}", text_color=self.palette["muted"])
        self.after(1500, lambda: self.set_recording(recording))

    def set_hint(self, text: str):
        self._hint_lbl.configure(text=text or "")

    def update_fps(self, fps: float):
        self.canvas.itemconfigure(self._fps_lbl, text=f"{fps:0.1f} FPS")

    def update_emotion(self, label: str, conf: float):
        self.canvas.itemconfigure(self._emo_lbl, text=f"{label}  {int(conf * 100)}%")

    def update_stats(self, totals: dict[str, float], dominant: str, last_label: str):
        for emo in LABELS:
            self._row_time[emo].configure(text=fmt_mmss(totals.get(emo, 0.0)))
        self._lbl_dom.configure(text=f"Dominant: {dominant}")

        last = (last_label or "").strip().lower()

        active_bg = self.palette.get("active_bg", "#0b2236")
        active_text = self.palette.get("active_text", "#ffffff")
        active_border = self.palette.get("active_border", self.palette.get("accent", "#3b82f6"))

        for emo, row in self._row_frames.items():
            is_active = (emo.lower() == last)
            if is_active:
                row.configure(
                    fg_color=active_bg,
                    border_width=2,
                    border_color=EMO_COLORS.get(emo, active_border),
                    corner_radius=999,
                )
                self._row_labels[emo].configure(text_color=active_text)
                self._row_time[emo].configure(text_color=active_text)
            else:
                row.configure(fg_color="transparent", border_width=0, corner_radius=999)
                self._row_labels[emo].configure(text_color=self.palette["text"])
                self._row_time[emo].configure(text_color=self.palette["muted"])

    def show_frame(self, bgr_frame):
        if bgr_frame is None:
            return

        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

        try:
            if _HAS_PIL and Image is not None and ImageTk is not None:
                img = Image.fromarray(rgb)
                self._tkimg = ImageTk.PhotoImage(img, master=self.canvas)
            else:
                ok, buf = cv2.imencode(".png", rgb)
                if ok:
                    self._tkimg = tk.PhotoImage(data=buf.tobytes(), master=self.canvas)
        except Exception:
            self._tkimg = None

        if self._tkimg is not None:
            if self._img_id is None:
                self._img_id = self.canvas.create_image(0, 0, image=self._tkimg, anchor="nw")
            else:
                self.canvas.itemconfigure(self._img_id, image=self._tkimg)

        # щоб FPS / emotion завжди були поверх відео
        for item in (self._fps_lbl, self._emo_lbl):
            try:
                self.canvas.tag_raise(item)
            except Exception:
                pass

        if not self._autosized:
            h, w = bgr_frame.shape[:2]
            sidebar_w = max(300, int(self.sidebar.winfo_width() or 300))
            padding = 40
            root_w = max(900, int(self.winfo_toplevel().winfo_width() or 900))
            max_w = max(420, root_w - sidebar_w - padding)
            scale = min(1.0, max_w / max(1, w))
            new_w, new_h = int(w * scale), int(h * scale)
            self.canvas.config(width=new_w, height=new_h)
            self._autosized = True
