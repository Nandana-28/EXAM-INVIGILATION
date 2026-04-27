from __future__ import annotations

import logging
import os
from pathlib import Path

import cv2
import numpy as np

from backend.core.config import Settings, get_settings
from backend.ml.types import Detection

logger = logging.getLogger(__name__)


class YOLODetector:
    """YOLO wrapper restricted to person, phone, and paper-like object classes."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.model = None
        self.names: dict[int, str] = {}
        self.weights_loaded: str | None = None
        self._load_model()

    def _load_model(self) -> None:
        ultralytics_config_dir = self.settings.run_dir / "ultralytics"
        ultralytics_config_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(ultralytics_config_dir.resolve()))
        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover - depends on optional runtime package
            logger.warning("Ultralytics is not available. Detection will return no YOLO boxes: %s", exc)
            return

        for candidate in (self.settings.model_weights, self.settings.fallback_model_weights):
            try:
                self.model = YOLO(candidate)
                self.names = {int(k): str(v).lower() for k, v in self.model.names.items()}
                self.weights_loaded = candidate
                logger.info("Loaded YOLO weights: %s", candidate)
                return
            except Exception as exc:
                logger.warning("Could not load YOLO weights %s: %s", candidate, exc)

        logger.error("No YOLO model could be loaded. Set MODEL_WEIGHTS to a trained YOLO11+ checkpoint.")

    def detect(self, frame: np.ndarray) -> list[Detection]:
        detections: list[Detection] = []
        if self.model is not None:
            detections.extend(self._detect_yolo(frame))
        detections.extend(self._detect_paper_candidates(frame))
        return self._dedupe(detections)

    def _detect_yolo(self, frame: np.ndarray) -> list[Detection]:
        output: list[Detection] = []
        results = self.model.predict(
            frame,
            conf=self.settings.detection_confidence,
            verbose=False,
            device=self.settings.device,
        )
        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes.xyxy.detach().cpu().numpy()
            confidences = result.boxes.conf.detach().cpu().numpy()
            class_ids = result.boxes.cls.detach().cpu().numpy().astype(int)
            for bbox, conf, class_id in zip(boxes, confidences, class_ids):
                name = self._canonical_name(self.names.get(int(class_id), str(class_id)))
                if name is None:
                    continue
                output.append(
                    Detection(
                        bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                        confidence=float(conf),
                        class_name=name,
                        class_id=int(class_id),
                    )
                )
        return output

    def _canonical_name(self, class_name: str) -> str | None:
        normalized = class_name.strip().lower().replace("_", " ")
        if normalized in self.settings.person_names:
            return "person"
        if normalized in self.settings.phone_names:
            return "phone"
        if normalized in self.settings.paper_names:
            return "paper"
        return None

    def _detect_paper_candidates(self, frame: np.ndarray) -> list[Detection]:
        """Fallback paper detector for uncustomized COCO checkpoints.

        A trained checkpoint with a paper/document class is preferred. This fallback only emits
        paper candidates, never students, and uses conservative rectangular white-region tests.
        """

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white_mask = cv2.inRange(hsv, np.array([0, 0, 178]), np.array([180, 72, 255]))
        kernel = np.ones((5, 5), np.uint8)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        frame_area = frame.shape[0] * frame.shape[1]
        candidates: list[Detection] = []
        for contour in contours:
            contour_area = cv2.contourArea(contour)
            if contour_area < frame_area * 0.002 or contour_area > frame_area * 0.10:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            rect_area = max(1, w * h)
            extent = contour_area / rect_area
            ratio = max(w / max(1, h), h / max(1, w))
            if extent < 0.62 or ratio > 3.5:
                continue
            confidence = min(0.90, 0.72 + (extent - 0.62) * 0.42)
            candidates.append(Detection((float(x), float(y), float(x + w), float(y + h)), confidence, "paper"))
        return candidates

    @staticmethod
    def _dedupe(detections: list[Detection]) -> list[Detection]:
        ordered = sorted(detections, key=lambda item: item.confidence, reverse=True)
        kept: list[Detection] = []
        for detection in ordered:
            if any(detection.class_name == other.class_name and _iou(detection.bbox, other.bbox) > 0.55 for other in kept):
                continue
            kept.append(detection)
        return kept


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def model_path_exists(path: str) -> bool:
    return Path(path).exists() or path.endswith(".pt")
