from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations

from backend.core.config import Settings, get_settings
from backend.ml.geometry import between, center, contains_or_overlaps, expand_box, intersects, distance, union_box
from backend.ml.types import Detection, ProctorEvent, StableTrack


class CheatingRuleEngine:
    """Phone and paper-only alert engine.

    Body posture is intentionally not used. Person posture-like cues are only used by the tracker
    to separate a walking invigilator from seated students and are excluded from cheating alerts.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def evaluate(self, tracks: list[StableTrack], detections: list[Detection]) -> list[ProctorEvent]:
        now = datetime.now(timezone.utc)
        students = [track for track in tracks if track.role == "student" and track.public_id is not None]
        phones = [
            detection
            for detection in detections
            if detection.class_name == "phone" and detection.confidence >= self.settings.alert_confidence_threshold
        ]
        papers = [detection for detection in detections if detection.class_name == "paper" and detection.confidence >= 0.62]

        events: list[ProctorEvent] = []
        events.extend(self._phone_usage(now, students, phones))
        events.extend(self._paper_passing(now, students, papers))
        events.extend(self._suspicious_exchange(now, students, phones, events))
        return events

    def _phone_usage(self, now: datetime, students: list[StableTrack], phones: list[Detection]) -> list[ProctorEvent]:
        events: list[ProctorEvent] = []
        for phone in phones:
            owner = self._nearest_overlapping_student(phone, students)
            if owner is None:
                continue
            events.append(
                ProctorEvent(
                    classification="malicious",
                    activity_type="phone_usage",
                    confidence=phone.confidence,
                    timestamp=now,
                    student_id=owner.public_id,
                    priority="high",
                    details="High-confidence phone detected within the student interaction area.",
                    source_bbox=owner.bbox,
                    object_bbox=phone.bbox,
                )
            )
        return events

    def _paper_passing(self, now: datetime, students: list[StableTrack], papers: list[Detection]) -> list[ProctorEvent]:
        events: list[ProctorEvent] = []
        for paper in papers:
            pairs = []
            for left, right in combinations(students, 2):
                if not self._paper_in_transfer_zone(paper, left, right):
                    continue
                pair_distance = distance(left.bbox, right.bbox)
                interaction_width = max(1.0, union_box(left.bbox, right.bbox)[2] - union_box(left.bbox, right.bbox)[0])
                if pair_distance > interaction_width * 1.25:
                    continue
                pairs.append((left, right, pair_distance))
            if not pairs:
                continue
            source, target, _ = min(pairs, key=lambda item: item[2])
            confidence = min(0.99, max(0.86, paper.confidence, (source.confidence + target.confidence + paper.confidence) / 3.0))
            if confidence < self.settings.alert_confidence_threshold:
                continue
            events.append(
                ProctorEvent(
                    classification="malicious",
                    activity_type="paper_passing",
                    confidence=confidence,
                    timestamp=now,
                    student_id=source.public_id,
                    priority="high",
                    details=f"Paper detected in transfer zone between Student {source.public_id} and Student {target.public_id}.",
                    source_bbox=source.bbox,
                    target_bbox=target.bbox,
                    object_bbox=paper.bbox,
                )
            )
        return events

    def _suspicious_exchange(
        self,
        now: datetime,
        students: list[StableTrack],
        phones: list[Detection],
        existing_events: list[ProctorEvent],
    ) -> list[ProctorEvent]:
        if existing_events:
            return []
        events: list[ProctorEvent] = []
        for obj in phones:
            near_students = sorted(
                [student for student in students if distance(student.bbox, obj.bbox) < 165.0],
                key=lambda student: distance(student.bbox, obj.bbox),
            )
            if len(near_students) < 2:
                continue
            first, second = near_students[0], near_students[1]
            if obj.confidence < self.settings.alert_confidence_threshold:
                continue
            events.append(
                ProctorEvent(
                    classification="suspicious",
                    activity_type="suspicious_object_exchange",
                    confidence=obj.confidence,
                    timestamp=now,
                    student_id=first.public_id,
                    priority="standard",
                    details=f"{obj.class_name.title()} detected close to Student {first.public_id} and Student {second.public_id}.",
                    source_bbox=first.bbox,
                    target_bbox=second.bbox,
                    object_bbox=obj.bbox,
                )
            )
            break
        return events

    @staticmethod
    def _paper_in_transfer_zone(paper: Detection, left: StableTrack, right: StableTrack) -> bool:
        pair_box = union_box(left.bbox, right.bbox)
        zone = expand_box(pair_box, margin_x=55.0, margin_y=0.0)
        if not intersects(paper.bbox, zone):
            return False

        px, py = center(paper.bbox)
        lx, ly = center(left.bbox)
        rx, ry = center(right.bbox)
        min_x, max_x = sorted((lx, rx))
        pair_height = max(1.0, pair_box[3] - pair_box[1])
        hand_band_top = pair_box[1] + (pair_height * 0.38)
        hand_band_bottom = pair_box[1] + (pair_height * 0.96)
        horizontally_between = (min_x - 80.0) <= px <= (max_x + 80.0)
        in_hand_transfer_band = hand_band_top <= py <= hand_band_bottom
        return horizontally_between and in_hand_transfer_band and between(paper.bbox, left.bbox, right.bbox, margin=110.0)

    @staticmethod
    def _nearest_overlapping_student(detection: Detection, students: list[StableTrack]) -> StableTrack | None:
        candidates = [
            student
            for student in students
            if contains_or_overlaps(student.bbox, detection.bbox, min_overlap=0.08)
            or distance(student.bbox, detection.bbox) < 115.0
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda item: distance(item.bbox, detection.bbox))
