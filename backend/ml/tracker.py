from __future__ import annotations

from dataclasses import replace

import cv2
import numpy as np

from backend.core.config import Settings, get_settings
from backend.ml.geometry import center, height_width_ratio, iou
from backend.ml.types import Detection, StableTrack


class LockedByteTrack:
    """ByteTrack-inspired tracker with immutable public IDs.

    The tracker does two-stage high/low-confidence association like ByteTrack, but never recycles
    public IDs and never assigns a detection to a different public ID once a track is locked.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._next_raw_id = 1
        self._next_student_id = 2
        self._tracks: dict[int, StableTrack] = {}
        self._invigilator_raw_id: int | None = None

    def reset(self) -> None:
        self._next_raw_id = 1
        self._next_student_id = 2
        self._tracks.clear()
        self._invigilator_raw_id = None

    def update(self, person_detections: list[Detection], frame_index: int, frame: np.ndarray) -> list[StableTrack]:
        high = [det for det in person_detections if det.confidence >= self.settings.tracker_high_threshold]
        low = [
            det
            for det in person_detections
            if self.settings.tracker_low_threshold <= det.confidence < self.settings.tracker_high_threshold
        ]

        unmatched_tracks = set(self._tracks)
        matched_high = self._associate(high, unmatched_tracks, frame_index, frame, allow_create=True)
        unmatched_tracks -= matched_high
        self._associate(low, unmatched_tracks, frame_index, frame, allow_create=False)

        for raw_id, track in list(self._tracks.items()):
            if track.last_seen_frame != frame_index:
                self._tracks[raw_id] = replace(track, lost_frames=track.lost_frames + 1)

        self._assign_roles()
        return [
            track
            for track in self._tracks.values()
            if track.lost_frames == 0 and track.public_id is not None and track.role in {"student", "invigilator"}
        ]

    def _associate(
        self,
        detections: list[Detection],
        candidate_track_ids: set[int],
        frame_index: int,
        frame: np.ndarray,
        allow_create: bool,
    ) -> set[int]:
        matched_tracks: set[int] = set()
        unmatched_detections: list[Detection] = []

        for detection in sorted(detections, key=lambda det: det.confidence, reverse=True):
            best_id: int | None = None
            best_score = 0.0
            for raw_id in list(candidate_track_ids - matched_tracks):
                track = self._tracks[raw_id]
                score = self._match_score(track, detection, frame)
                if score > best_score:
                    best_score = score
                    best_id = raw_id
            if best_id is None or best_score < self.settings.tracker_match_threshold:
                unmatched_detections.append(detection)
                continue
            self._update_track(best_id, detection, frame_index, frame)
            matched_tracks.add(best_id)

        if allow_create:
            for detection in unmatched_detections:
                self._create_track(detection, frame_index, frame)

        return matched_tracks

    def _match_score(self, track: StableTrack, detection: Detection, frame: np.ndarray) -> float:
        spatial = iou(track.bbox, detection.bbox)
        tcx, tcy = center(track.bbox)
        dcx, dcy = center(detection.bbox)
        diag = max(1.0, (frame.shape[0] ** 2 + frame.shape[1] ** 2) ** 0.5)
        center_score = max(0.0, 1.0 - (((tcx - dcx) ** 2 + (tcy - dcy) ** 2) ** 0.5 / (diag * 0.20)))
        appearance = self._appearance_score(track.appearance, self._appearance(frame, detection.bbox))
        missing_penalty = max(0.55, 1.0 - min(track.lost_frames, 120) / 240.0)
        return ((0.56 * spatial) + (0.26 * center_score) + (0.18 * appearance)) * missing_penalty

    def _create_track(self, detection: Detection, frame_index: int, frame: np.ndarray) -> None:
        raw_id = self._next_raw_id
        self._next_raw_id += 1
        ratio = height_width_ratio(detection.bbox)
        standing = min(1.0, max(0.0, (ratio - 1.55) / 1.35))
        self._tracks[raw_id] = StableTrack(
            raw_id=raw_id,
            public_id=None,
            role="candidate",
            bbox=detection.bbox,
            confidence=detection.confidence,
            hits=1,
            first_seen_frame=frame_index,
            last_seen_frame=frame_index,
            lost_frames=0,
            velocity=0.0,
            standing_score=standing,
            moving_score=0.0,
            appearance=self._appearance(frame, detection.bbox),
        )

    def _update_track(self, raw_id: int, detection: Detection, frame_index: int, frame: np.ndarray) -> None:
        previous = self._tracks[raw_id]
        pcx, pcy = center(previous.bbox)
        dcx, dcy = center(detection.bbox)
        frame_diag = max(1.0, (frame.shape[0] ** 2 + frame.shape[1] ** 2) ** 0.5)
        velocity = ((dcx - pcx) ** 2 + (dcy - pcy) ** 2) ** 0.5 / frame_diag
        ratio = height_width_ratio(detection.bbox)
        standing = min(1.0, max(0.0, (ratio - 1.55) / 1.35))
        appearance = self._blend_appearance(previous.appearance, self._appearance(frame, detection.bbox))
        self._tracks[raw_id] = replace(
            previous,
            bbox=detection.bbox,
            confidence=detection.confidence,
            hits=previous.hits + 1,
            last_seen_frame=frame_index,
            lost_frames=0,
            velocity=(0.82 * previous.velocity) + (0.18 * velocity),
            standing_score=(0.86 * previous.standing_score) + (0.14 * standing),
            moving_score=(0.88 * previous.moving_score) + (0.12 * min(1.0, velocity * 36.0)),
            appearance=appearance,
        )

    def _assign_roles(self) -> None:
        if self._invigilator_raw_id is None:
            candidates = [
                track
                for track in self._tracks.values()
                if track.public_id is None
                and track.hits >= 3
                and self._is_invigilator_candidate(track)
                and track.lost_frames == 0
            ]
            if candidates:
                invigilator = max(candidates, key=lambda item: (item.standing_score * 2.0 + item.moving_score, item.hits))
                self._tracks[invigilator.raw_id] = replace(invigilator, role="invigilator", public_id=1)
                self._invigilator_raw_id = invigilator.raw_id

        for raw_id, track in list(self._tracks.items()):
            if track.public_id is not None:
                continue
            if track.hits < 5:
                continue
            if self._invigilator_raw_id is None and self._looks_standing(track):
                continue
            self._tracks[raw_id] = replace(track, role="student", public_id=self._next_student_id)
            self._next_student_id += 1

    @staticmethod
    def _looks_standing(track: StableTrack) -> bool:
        return track.standing_score >= 0.58

    @staticmethod
    def _is_invigilator_candidate(track: StableTrack) -> bool:
        strongly_standing = track.standing_score >= 0.68
        standing_and_moving = track.standing_score >= 0.52 and track.moving_score >= 0.05
        return strongly_standing or standing_and_moving

    @staticmethod
    def _appearance(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray | None:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten()

    @staticmethod
    def _appearance_score(a: np.ndarray | None, b: np.ndarray | None) -> float:
        if a is None or b is None:
            return 0.5
        score = cv2.compareHist(a.astype("float32"), b.astype("float32"), cv2.HISTCMP_CORREL)
        return float(max(0.0, min(1.0, (score + 1.0) / 2.0)))

    @staticmethod
    def _blend_appearance(a: np.ndarray | None, b: np.ndarray | None) -> np.ndarray | None:
        if a is None:
            return b
        if b is None:
            return a
        blended = (0.90 * a) + (0.10 * b)
        norm = np.linalg.norm(blended)
        return blended / norm if norm > 0 else blended
