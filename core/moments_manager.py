# core/moments_manager.py
from __future__ import annotations

import os
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Deque, Optional, Tuple, List

try:
    import cv2
except Exception:
    cv2 = None

from core.storage import ensure_moments_storage, append_moment, MOMENTS_DIR


def _safe_filename(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9_\-]+", "_", s)
    return s.strip("_") or "moment"


@dataclass
class MomentConfig:
    fps: int = 15
    pre_sec: float = 2.0
    post_sec: float = 3.0

    min_conf: float = 0.65
    min_streak_sec: float = 2.0

    cooldown_sec: float = 20.0
    max_clip_sec: float = 8.0
    trigger_emotions: tuple[str, ...] = ("angry", "fear", "surprise", "sad", "disgust")


class MomentsManager:

    def __init__(self, session_id: str = "", cfg: MomentConfig | None = None):
        self.session_id = session_id or ""
        self.cfg = cfg or MomentConfig()

        ensure_moments_storage()

        self._buffer: Deque[Tuple[datetime, "object"]] = deque()
        self._buf_lock = threading.Lock()

        self._cur_emotion: str = ""
        self._cur_start: Optional[datetime] = None

        self._recording: bool = False
        self._record_emotion: str = ""
        self._record_conf: float = 0.0
        self._record_streak_sec: float = 0.0
        self._record_end: Optional[datetime] = None
        self._frames: List["object"] = []

        self._last_trigger: Optional[datetime] = None

    def update(self, emotion: str, conf: float, frame, session_time_sec: float = 0.0, ts=None):
        self._last_session_time_sec = float(session_time_sec)

        if cv2 is None:
            return

        ts = ts or datetime.now()
        emo = (emotion or "").strip().lower()

        if emo not in self.cfg.trigger_emotions:
            return

        self._push_frame(ts, frame)

        self._update_streak(emo, ts, conf)

        if self._recording:
            self._frames.append(frame)
            if self._record_end and ts >= self._record_end:
                self._finish_async()
            return

        if not emo:
            return
        if conf < self.cfg.min_conf:
            return

        streak_sec = self._get_streak_sec(ts)
        if streak_sec < self.cfg.min_streak_sec:
            return

        if self._last_trigger and (ts - self._last_trigger).total_seconds() < self.cfg.cooldown_sec:
            return

        self._start_recording(emo, conf, streak_sec, ts)

    def _push_frame(self, ts: datetime, frame) -> None:
        keep_sec = max(self.cfg.pre_sec + self.cfg.max_clip_sec + 1.0, 6.0)
        min_ts = ts - timedelta(seconds=keep_sec)

        with self._buf_lock:
            self._buffer.append((ts, frame))
            while self._buffer and self._buffer[0][0] < min_ts:
                self._buffer.popleft()

    def _update_streak(self, emo: str, ts: datetime, conf: float) -> None:
        if not emo or conf < self.cfg.min_conf:
            self._cur_emotion = ""
            self._cur_start = None
            return

        if emo != self._cur_emotion:
            self._cur_emotion = emo
            self._cur_start = ts

    def _get_streak_sec(self, ts: datetime) -> float:
        if not self._cur_start:
            return 0.0
        return max(0.0, (ts - self._cur_start).total_seconds())

    def _start_recording(self, emo: str, conf: float, streak_sec: float, ts: datetime) -> None:
        self._recording = True
        self._record_emotion = emo
        self._record_conf = float(conf)
        self._record_streak_sec = float(streak_sec)

        total = min(self.cfg.pre_sec + self.cfg.post_sec, self.cfg.max_clip_sec)
        self._record_end = ts + timedelta(seconds=total - self.cfg.pre_sec)

        start_cut = ts - timedelta(seconds=self.cfg.pre_sec)
        pre_frames: List["object"] = []
        with self._buf_lock:
            for t, fr in self._buffer:
                if t >= start_cut:
                    pre_frames.append(fr)

        self._frames = pre_frames[:]
        self._last_trigger = ts

    def _finish_async(self) -> None:
        frames = self._frames[:]
        emo = self._record_emotion
        conf = self._record_conf
        streak = self._record_streak_sec
        session_id = self.session_id
        ts_end = datetime.now()

        self._recording = False
        self._record_emotion = ""
        self._record_conf = 0.0
        self._record_streak_sec = 0.0
        self._record_end = None
        self._frames = []

        th = threading.Thread(
            target=self._write_clip_and_store,
            args=(frames, emo, conf, streak, session_id, ts_end),
            daemon=True,
        )
        th.start()

    def _write_clip_and_store(
        self,
        frames: List["object"],
        emo: str,
        conf: float,
        streak_sec: float,
        session_id: str,
        ts: datetime,
    ) -> None:
        if cv2 is None:
            return
        if not frames:
            return

        h, w = frames[0].shape[:2]

        stamp = ts.strftime("%Y%m%d_%H%M%S")
        fname = f"{stamp}_{_safe_filename(emo)}.mp4"
        out_path = os.path.join(MOMENTS_DIR, fname)

        fps = int(self.cfg.fps)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

        try:
            for fr in frames:
                if fr is None:
                    continue
                if fr.shape[0] != h or fr.shape[1] != w:
                    fr = cv2.resize(fr, (w, h))
                writer.write(fr)
        finally:
            writer.release()

        append_moment(
            {
                "timestamp": ts.isoformat(timespec="seconds"),
                "session_time_sec": f"{self._last_session_time_sec:.2f}",
                "emotion": emo,
                "conf": f"{conf:.4f}",
                "streak_sec": f"{streak_sec:.2f}",
                "session_id": session_id,
                "video_path": fname,
            }
        )
