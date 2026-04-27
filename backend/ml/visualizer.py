from __future__ import annotations

import cv2
import numpy as np

from backend.ml.geometry import center, union_box
from backend.ml.types import Detection, ProctorEvent, StableTrack


GREEN = (45, 180, 85)
RED = (45, 55, 215)
AMBER = (30, 170, 230)
WHITE = (255, 255, 255)
BLACK = (20, 24, 31)


def draw_frame(frame: np.ndarray, tracks: list[StableTrack], detections: list[Detection], events: list[ProctorEvent]) -> np.ndarray:
    canvas = frame.copy()
    for event in events:
        if event.activity_type == "paper_passing":
            canvas = apply_paper_heatmap(canvas, event)

    for detection in detections:
        if detection.class_name not in {"phone", "paper"}:
            continue
        color = AMBER if detection.class_name == "paper" else RED
        _draw_box(canvas, detection.bbox, color, f"{detection.class_name.title()} {detection.confidence:.0%}", thickness=2)

    for track in tracks:
        color = RED if track.role == "invigilator" else GREEN
        if track.role == "invigilator":
            label = "Invigilator ID: 1"
        else:
            label = f"Student ID: {track.public_id}"
        _draw_box(canvas, track.bbox, color, label, thickness=3)

    return canvas


def apply_paper_heatmap(frame: np.ndarray, event: ProctorEvent) -> np.ndarray:
    if event.source_bbox is None or event.target_bbox is None:
        return frame

    sx, sy = center(event.source_bbox)
    tx, ty = center(event.target_bbox)
    interaction = union_box(event.source_bbox, event.target_bbox)
    x1, y1, x2, y2 = [int(value) for value in interaction]
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w - 1, x2), min(h - 1, y2)

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.line(mask, (int(sx), int(sy)), (int(tx), int(ty)), 230, thickness=max(18, int((x2 - x1) * 0.08)))
    if event.object_bbox is not None:
        ox1, oy1, ox2, oy2 = [int(value) for value in event.object_bbox]
        cv2.rectangle(mask, (max(0, ox1), max(0, oy1)), (min(w - 1, ox2), min(h - 1, oy2)), 255, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), 22)
    heat = cv2.applyColorMap(mask, cv2.COLORMAP_JET)
    overlay = frame.copy()
    active = mask > 12
    overlay[active] = cv2.addWeighted(frame, 0.62, heat, 0.38, 0)[active]
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 95, 255), 2)
    return overlay


def _draw_box(frame: np.ndarray, bbox: tuple[float, float, float, float], color: tuple[int, int, int], label: str, thickness: int) -> None:
    x1, y1, x2, y2 = [int(round(value)) for value in bbox]
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w - 1, x2), min(h - 1, y2)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.56
    label_size, baseline = cv2.getTextSize(label, font, scale, 2)
    label_w, label_h = label_size
    label_y1 = max(0, y1 - label_h - baseline - 8)
    label_y2 = label_y1 + label_h + baseline + 8
    label_x2 = min(w - 1, x1 + label_w + 12)
    cv2.rectangle(frame, (x1, label_y1), (label_x2, label_y2), color, -1)
    cv2.putText(frame, label, (x1 + 6, label_y2 - baseline - 4), font, scale, WHITE, 2, cv2.LINE_AA)
