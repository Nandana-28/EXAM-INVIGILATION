from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import numpy as np


BBox = tuple[float, float, float, float]


@dataclass(slots=True)
class Detection:
    bbox: BBox
    confidence: float
    class_name: str
    class_id: int | None = None


@dataclass(slots=True)
class StableTrack:
    raw_id: int
    public_id: int | None
    role: Literal["candidate", "student", "invigilator"]
    bbox: BBox
    confidence: float
    hits: int
    first_seen_frame: int
    last_seen_frame: int
    lost_frames: int
    velocity: float
    standing_score: float
    moving_score: float
    appearance: np.ndarray | None = field(default=None, repr=False)

    @property
    def label(self) -> str:
        if self.role == "invigilator":
            return "Invigilator"
        if self.role == "student":
            return "Student"
        return "Candidate"


@dataclass(slots=True)
class ProctorEvent:
    classification: Literal["normal", "suspicious", "malicious"]
    activity_type: str
    confidence: float
    timestamp: datetime
    student_id: int | None
    priority: Literal["standard", "high"] = "standard"
    details: str | None = None
    source_bbox: BBox | None = None
    target_bbox: BBox | None = None
    object_bbox: BBox | None = None


@dataclass(slots=True)
class FrameAnalytics:
    processed_frames: int = 0
    normal_frames: int = 0
    suspicious_events: int = 0
    malicious_events: int = 0
