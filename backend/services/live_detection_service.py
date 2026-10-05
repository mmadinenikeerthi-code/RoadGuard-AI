"""
RoadGuard AI
Live Detection Service

Responsibilities:
    - Load the RoadGuard YOLO model once.
    - Run inference on live camera frames.
    - Normalize YOLO detections.
    - Calculate detection severity.
    - Persist GPS-tagged pothole detections.
    - Keep database logic outside the WebSocket router.

Architecture:

    Browser Camera
          |
          v
    live_detection.py
          |
          v
    LiveDetectionService
          |
       YOLOv8
          |
          +------> detections
          |
          +------> database
          |
          v
    WebSocket response
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from backend.database import SessionLocal
from backend.models import ReportModel


logger = logging.getLogger(__name__)


class LiveDetectionService:
    """
    Application service for real-time pothole detection.

    The YOLO model is loaded once and reused for all frames.
    """

    def __init__(
        self,
        model_path: str | Path,
        confidence: float = 0.35,
        iou: float = 0.45,
    ) -> None:

        self.model_path = Path(model_path)

        self.confidence = confidence
        self.iou = iou

        self._model_lock = Lock()

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"YOLO model not found: {self.model_path}"
            )

        logger.info(
            "Loading RoadGuard YOLO model: %s",
            self.model_path,
        )

        self.model = YOLO(
            str(self.model_path)
        )

        logger.info(
            "RoadGuard YOLO model loaded successfully."
        )

    # =========================================================
    # YOLO DETECTION
    # =========================================================

    def detect(
        self,
        frame: np.ndarray,
    ) -> dict[str, Any]:
        """
        Run YOLO inference on one OpenCV frame.

        Returns:

        {
            "detections": [...],
            "pothole_count": 2
        }
        """

        if frame is None:
            raise ValueError(
                "Live detection received an empty frame."
            )

        if not isinstance(frame, np.ndarray):
            raise TypeError(
                "Live detection frame must be a NumPy array."
            )

        if frame.size == 0:
            raise ValueError(
                "Live detection frame is empty."
            )

        # YOLO inference.
        #
        # The lock protects model inference if multiple
        # WebSocket clients are connected simultaneously.
        with self._model_lock:

            results = self.model.predict(
                source=frame,
                conf=self.confidence,
                iou=self.iou,
                verbose=False,
            )

        detections: list[dict[str, Any]] = []

        for result in results:

            if result.boxes is None:
                continue

            names = result.names

            for box in result.boxes:

                confidence = float(
                    box.conf[0].item()
                )

                class_id = int(
                    box.cls[0].item()
                )

                coordinates = (
                    box.xyxy[0]
                    .detach()
                    .cpu()
                    .numpy()
                    .tolist()
                )

                x1, y1, x2, y2 = [
                    int(round(value))
                    for value in coordinates
                ]

                class_name = self._class_name(
                    names,
                    class_id,
                )

                severity = (
                    self._estimate_severity(
                        confidence=confidence,
                        bbox_width=max(0, x2 - x1),
                        bbox_height=max(0, y2 - y1),
                        frame_width=frame.shape[1],
                        frame_height=frame.shape[0],
                    )
                )

                detections.append({
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": round(
                        confidence,
                        4,
                    ),
                    "severity": severity,
                    "bbox": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                    },
                })

        return {
            "detections": detections,
            "pothole_count": len(detections),
        }

    # =========================================================
    # CLASS NAME
    # =========================================================

    @staticmethod
    def _class_name(
        names: Any,
        class_id: int,
    ) -> str:

        try:

            if isinstance(names, dict):
                return str(
                    names.get(
                        class_id,
                        f"class_{class_id}",
                    )
                )

            if isinstance(names, list):
                if 0 <= class_id < len(names):
                    return str(
                        names[class_id]
                    )

        except Exception:
            pass

        return f"class_{class_id}"

    # =========================================================
    # SEVERITY
    # =========================================================

    @staticmethod
    def _estimate_severity(
        confidence: float,
        bbox_width: int,
        bbox_height: int,
        frame_width: int,
        frame_height: int,
    ) -> str:
        """
        Estimate a UI/report severity level.

        This is intentionally conservative.

        It is NOT a physical pothole-depth measurement.

        A real depth/severity model can replace this later.
        """

        if frame_width <= 0 or frame_height <= 0:
            return "LOW"

        frame_area = (
            frame_width * frame_height
        )

        bbox_area = (
            max(0, bbox_width)
            * max(0, bbox_height)
        )

        area_ratio = (
            bbox_area / frame_area
        )

        if (
            confidence >= 0.80
            and area_ratio >= 0.12
        ):
            return "HIGH"

        if (
            confidence >= 0.60
            or area_ratio >= 0.05
        ):
            return "MEDIUM"

        return "LOW"

    # =========================================================
    # DATABASE
    # =========================================================

    def save_detection(
        self,
        detections: list[dict[str, Any]],
        latitude: float,
        longitude: float,
        gps_accuracy: float | None = None,
        timestamp: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Persist one live detection report.

        A report is created only when a valid GPS position
        is available.

        The service does NOT generate coordinates.
        """

        if not self._valid_coordinate(
            latitude,
            longitude,
        ):
            logger.warning(
                "Rejected live detection with invalid GPS: "
                "%s, %s",
                latitude,
                longitude,
            )

            return []

        if not detections:
            return []

        db = SessionLocal()

        saved: list[dict[str, Any]] = []

        try:

            confidence_values = [
                float(
                    detection.get(
                        "confidence",
                        0.0,
                    )
                )
                for detection in detections
            ]

            max_confidence = (
                max(confidence_values)
                if confidence_values
                else 0.0
            )

            severities = [
                str(
                    detection.get(
                        "severity",
                        "LOW",
                    )
                ).upper()
                for detection in detections
            ]

            severity = (
                "HIGH"
                if "HIGH" in severities
                else (
                    "MEDIUM"
                    if "MEDIUM" in severities
                    else "LOW"
                )
            )

            # One report represents the live detection event
            # at the current GPS location.
            report = ReportModel(
                media_type="live",
                media_path=None,
                result_path=None,
                lat=float(latitude),
                lon=float(longitude),
                location_name="Live GPS Location",
                pothole_count=len(
                    detections
                ),
                confidence=float(
                    max_confidence
                ),
                severity=severity,
            )

            db.add(report)

            db.commit()

            db.refresh(report)

            saved.append({
                "report_id": report.id,
                "latitude": report.lat,
                "longitude": report.lon,
                "pothole_count": (
                    report.pothole_count
                ),
                "confidence": round(
                    report.confidence,
                    4,
                ),
                "severity": report.severity,
                "gps_accuracy": gps_accuracy,
                "timestamp": (
                    timestamp
                    or datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            })

            logger.info(
                "Live pothole report saved: "
                "id=%s lat=%s lon=%s count=%s",
                report.id,
                latitude,
                longitude,
                len(detections),
            )

        except Exception:

            db.rollback()

            logger.exception(
                "Failed to save live detection report."
            )

            raise

        finally:

            db.close()

        return saved

    # =========================================================
    # GPS VALIDATION
    # =========================================================

    @staticmethod
    def _valid_coordinate(
        latitude: Any,
        longitude: Any,
    ) -> bool:

        try:

            lat = float(latitude)
            lon = float(longitude)

        except (
            TypeError,
            ValueError,
        ):
            return False

        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
        ):
            return False

        if not (
            -90.0 <= lat <= 90.0
        ):
            return False

        if not (
            -180.0 <= lon <= 180.0
        ):
            return False

        # Reject missing/default coordinates.
        if lat == 0.0 and lon == 0.0:
            return False

        return True