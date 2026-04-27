from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

from backend.core.config import Settings, get_settings
from backend.db import repository
from backend.db.base import SessionLocal
from backend.db.schemas import AlertOut, ResultsOut, StateOut
from backend.ml.detector import YOLODetector
from backend.services.video_processor import ExamVideoProcessor, safe_source_name


class SessionManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.detector = YOLODetector(self.settings)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._session_id: int | None = None
        self._active = False
        self._current_frame = self._placeholder_frame()
        self._latest_alerts: deque[AlertOut] = deque(maxlen=self.settings.max_recent_alerts)
        self._results = ResultsOut(session_id=None, status="idle")
        self._error: str | None = None

    def start_live(self) -> ResultsOut:
        return self._start(self.settings.live_camera_index, "live")

    def start_upload(self, path: Path) -> ResultsOut:
        return self._start(str(path), "upload")

    def stop(self) -> ResultsOut:
        with self._lock:
            if not self._active:
                return self._results
            self._stop_event.set()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=10)
        with self._lock:
            if self._active:
                self._results.status = "stopping"
                self._results.message = "Stop requested; waiting for video source to release."
            return self._results

    def get_results(self) -> ResultsOut:
        with self._lock:
            return self._results

    def get_state(self) -> StateOut:
        with self._lock:
            return StateOut(
                active=self._active,
                session_id=self._session_id,
                status=self._results.status,
                latest_alerts=list(self._latest_alerts),
                results=self._results,
                error=self._error,
            )

    def mjpeg_stream(self):
        while True:
            with self._lock:
                frame = self._current_frame
                active = self._active
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(0.08 if active else 0.35)

    def _start(self, source: int | str, source_type: str) -> ResultsOut:
        with self._lock:
            if self._active:
                raise RuntimeError("A ProctorX session is already running. Stop it before starting another one.")
            self._stop_event = threading.Event()
            self._latest_alerts.clear()
            self._error = None
            self._current_frame = self._placeholder_frame("Starting ProctorX session...")

        with SessionLocal() as db:
            session = repository.create_session(db, source_type=source_type, source_name=safe_source_name(source))

        processor = ExamVideoProcessor(
            session_id=session.id,
            source=source,
            source_type=source_type,
            detector=self.detector,
            settings=self.settings,
            on_frame=self._on_frame,
            on_finish=self._on_finish,
        )
        thread = threading.Thread(target=processor.run, args=(self._stop_event,), daemon=True, name=f"proctorx-{session.id}")
        with self._lock:
            self._session_id = session.id
            self._results = ResultsOut(session_id=session.id, status="running", started_at=session.start_time, message="Session is running.")
            self._thread = thread
            self._active = True
        thread.start()
        return self._results

    def _on_frame(self, frame: bytes, alerts: list[AlertOut], results: ResultsOut) -> None:
        with self._lock:
            self._current_frame = frame
            for alert in alerts:
                self._latest_alerts.appendleft(alert)
            if self._active:
                self._results = results

    def _on_finish(self, results: ResultsOut, error: str | None) -> None:
        with self._lock:
            self._results = results
            self._error = error
            self._active = False

    @staticmethod
    def _placeholder_frame(message: str = "No active ProctorX session") -> bytes:
        frame = np.full((540, 960, 3), (238, 241, 244), dtype=np.uint8)
        cv2.rectangle(frame, (28, 28), (932, 512), (208, 216, 226), 2)
        cv2.putText(frame, message, (88, 268), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (50, 67, 86), 2, cv2.LINE_AA)
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
        return buffer.tobytes() if ok else b""
