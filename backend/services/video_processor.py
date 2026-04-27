from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import cv2

from backend.core.config import Settings, get_settings
from backend.db import repository
from backend.db.base import SessionLocal
from backend.db.schemas import AlertOut, ResultsOut
from backend.ml.detector import YOLODetector
from backend.ml.rules import CheatingRuleEngine
from backend.ml.tracker import LockedByteTrack
from backend.ml.types import FrameAnalytics, ProctorEvent
from backend.ml.visualizer import draw_frame

logger = logging.getLogger(__name__)


FrameCallback = Callable[[bytes, list[AlertOut], ResultsOut], None]
FinishCallback = Callable[[ResultsOut, str | None], None]


class ExamVideoProcessor:
    def __init__(
        self,
        session_id: int,
        source: int | str,
        source_type: str,
        detector: YOLODetector,
        settings: Settings | None = None,
        on_frame: FrameCallback | None = None,
        on_finish: FinishCallback | None = None,
    ) -> None:
        self.session_id = session_id
        self.source = source
        self.source_type = source_type
        self.settings = settings or get_settings()
        self.detector = detector
        self.tracker = LockedByteTrack(self.settings)
        self.rules = CheatingRuleEngine(self.settings)
        self.analytics = FrameAnalytics()
        self.on_frame = on_frame
        self.on_finish = on_finish
        self._last_alert_at: dict[tuple[int | None, str], datetime] = {}
        self._seen_public_ids: dict[int, str] = {}
        self._started_at = datetime.now(timezone.utc)
        self._ended_at: datetime | None = None

    def run(self, stop_event: threading.Event) -> None:
        error: str | None = None
        status = "completed"
        capture = cv2.VideoCapture(self.source)
        try:
            if not capture.isOpened():
                raise RuntimeError(f"Could not open video source: {self.source}")

            frame_index = 0
            while not stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    break
                frame_index += 1
                if self.settings.frame_skip and frame_index % (self.settings.frame_skip + 1) != 0:
                    continue
                frame = self._resize(frame)
                self._process_frame(frame, frame_index)

            if stop_event.is_set():
                status = "stopped"
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            logger.exception("Processing failed")
            error = str(exc)
            status = "failed"
        finally:
            capture.release()
            self._ended_at = datetime.now(timezone.utc)
            with SessionLocal() as db:
                repository.finish_session(db, self.session_id, status=status)
                total_students, invigilator_detected = repository.count_students(db, self.session_id)
                risk_scores = repository.get_student_risk_scores(db, self.session_id)
            result = self._results(
                status=status,
                total_students=total_students,
                invigilator_detected=invigilator_detected,
                risk_scores=risk_scores,
            )
            if self.on_finish:
                self.on_finish(result, error)

    def _process_frame(self, frame, frame_index: int) -> None:
        detections = self.detector.detect(frame)
        person_detections = [detection for detection in detections if detection.class_name == "person"]
        tracks = self.tracker.update(person_detections, frame_index, frame)
        events = self.rules.evaluate(tracks, detections)

        with SessionLocal() as db:
            for track in tracks:
                if track.public_id is None:
                    continue
                label = "Invigilator" if track.role == "invigilator" else "Student"
                if self._seen_public_ids.get(track.public_id) != label or frame_index % 30 == 0:
                    repository.upsert_identity(db, self.session_id, track.public_id, label)
                    self._seen_public_ids[track.public_id] = label

            emitted = [event for event in events if self._should_emit(event)]
            alerts = [
                AlertOut.model_validate(
                    repository.create_alert(
                        db=db,
                        session_id=self.session_id,
                        student_id=event.student_id,
                        classification=event.classification,
                        activity_type=event.activity_type,
                        confidence=event.confidence,
                        priority=event.priority,
                        details=event.details,
                    )
                )
                for event in emitted
            ]
            total_students, invigilator_detected = repository.count_students(db, self.session_id)
            risk_scores = repository.get_student_risk_scores(db, self.session_id)

        self.analytics.processed_frames += 1
        if alerts:
            self.analytics.suspicious_events += sum(1 for alert in alerts if alert.type == "suspicious")
            self.analytics.malicious_events += sum(1 for alert in alerts if alert.type == "malicious")
        else:
            self.analytics.normal_frames += 1

        rendered = draw_frame(frame, tracks, detections, events)
        encoded = self._encode(rendered)
        if encoded and self.on_frame:
            self.on_frame(
                encoded,
                alerts,
                self._results(
                    status="running",
                    total_students=total_students,
                    invigilator_detected=invigilator_detected,
                    risk_scores=risk_scores,
                ),
            )

    def _should_emit(self, event: ProctorEvent) -> bool:
        if event.confidence < self.settings.alert_confidence_threshold:
            return False
        key = (event.student_id, event.activity_type)
        previous = self._last_alert_at.get(key)
        if previous is not None:
            elapsed = (event.timestamp - previous).total_seconds()
            if elapsed < self.settings.alert_cooldown_seconds:
                return False
        self._last_alert_at[key] = event.timestamp
        return True

    def _results(
        self,
        status: str,
        total_students: int,
        invigilator_detected: bool,
        risk_scores=None,
    ) -> ResultsOut:
        return ResultsOut(
            session_id=self.session_id,
            status=status,
            total_normal=self.analytics.normal_frames,
            total_suspicious=self.analytics.suspicious_events,
            total_malicious=self.analytics.malicious_events,
            total_students=total_students,
            invigilator_detected=invigilator_detected,
            processed_frames=self.analytics.processed_frames,
            started_at=self._started_at,
            ended_at=self._ended_at,
            student_risk_scores=risk_scores or [],
            message="Final analytics are frozen." if status in {"completed", "stopped", "failed"} else "Session is running.",
        )

    def _resize(self, frame):
        height, width = frame.shape[:2]
        if width <= self.settings.frame_width:
            return frame
        ratio = self.settings.frame_width / float(width)
        return cv2.resize(frame, (self.settings.frame_width, int(height * ratio)), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _encode(frame) -> bytes:
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
        if not ok:
            return b""
        return buffer.tobytes()


def safe_source_name(source: int | str) -> str:
    if isinstance(source, int):
        return f"camera:{source}"
    return Path(source).name
