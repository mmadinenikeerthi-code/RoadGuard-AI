"""
RoadGuard AI
Live Detection WebSocket Router
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)

from backend.services.live_detection_service import (
    LiveDetectionService,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/live",
    tags=["Live Detection"],
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parents[2]

MODEL_PATH = BASE_DIR / "best.pt"


# ============================================================
# SERVICE
# ============================================================

live_service = LiveDetectionService(
    model_path=MODEL_PATH,
    confidence=0.35,
    iou=0.45,
)


# ============================================================
# FRAME LIMIT
# ============================================================

MAX_FRAME_BYTES = (
    5 * 1024 * 1024
)


# ============================================================
# GPS VALIDATION
# ============================================================

def valid_coordinate(
    latitude: Any,
    longitude: Any,
) -> bool:

    if latitude is None:
        return False

    if longitude is None:
        return False

    try:

        lat = float(latitude)
        lon = float(longitude)

    except (
        TypeError,
        ValueError,
    ):
        return False

    if not (
        np.isfinite(lat)
        and np.isfinite(lon)
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

    # Never use a default/fake coordinate.
    if lat == 0.0 and lon == 0.0:
        return False

    return True


# ============================================================
# FRAME DECODER
# ============================================================

def decode_frame(
    image_data: str,
) -> np.ndarray | None:

    if not image_data:
        return None

    try:

        # Browser sends:
        #
        # data:image/jpeg;base64,XXXX
        #
        # Strip the data URL prefix.

        if "," in image_data:

            image_data = (
                image_data.split(
                    ",",
                    1,
                )[1]
            )

        image_bytes = (
            base64.b64decode(
                image_data,
                validate=True,
            )
        )

    except (
        ValueError,
        binascii.Error,
    ):

        return None

    if not image_bytes:
        return None

    if len(image_bytes) > MAX_FRAME_BYTES:
        return None

    frame_buffer = np.frombuffer(
        image_bytes,
        dtype=np.uint8,
    )

    frame = cv2.imdecode(
        frame_buffer,
        cv2.IMREAD_COLOR,
    )

    return frame


# ============================================================
# WEBSOCKET
# ============================================================

@router.websocket("/detect")
async def live_detect(
    websocket: WebSocket,
) -> None:

    await websocket.accept()

    client_address = "unknown"

    if websocket.client:
        client_address = (
            websocket.client.host
        )

    logger.info(
        "Live detection connected: %s",
        client_address,
    )

    frame_number = 0

    try:

        while True:

            # ------------------------------------------------
            # RECEIVE FRAME
            # ------------------------------------------------

            raw_message = (
                await websocket.receive_text()
            )

            try:

                payload = json.loads(
                    raw_message
                )

            except json.JSONDecodeError:

                await websocket.send_json({
                    "success": False,
                    "error": (
                        "Invalid JSON payload."
                    ),
                })

                continue

            # ------------------------------------------------
            # EXTRACT DATA
            # ------------------------------------------------

            image_data = payload.get(
                "frame"
            )

            latitude = payload.get(
                "latitude"
            )

            longitude = payload.get(
                "longitude"
            )

            gps_accuracy = payload.get(
                "gps_accuracy"
            )

            # ------------------------------------------------
            # FRAME VALIDATION
            # ------------------------------------------------

            if not image_data:

                await websocket.send_json({
                    "success": False,
                    "error": (
                        "Camera frame missing."
                    ),
                })

                continue

            frame = decode_frame(
                image_data
            )

            if frame is None:

                await websocket.send_json({
                    "success": False,
                    "error": (
                        "Invalid or oversized "
                        "camera frame."
                    ),
                })

                continue

            # ------------------------------------------------
            # GPS VALIDATION
            # ------------------------------------------------

            has_valid_gps = valid_coordinate(
                latitude,
                longitude,
            )

            if has_valid_gps:

                latitude = float(
                    latitude
                )

                longitude = float(
                    longitude
                )

                if gps_accuracy is not None:

                    try:

                        gps_accuracy = float(
                            gps_accuracy
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        gps_accuracy = None

            else:

                latitude = None
                longitude = None
                gps_accuracy = None

            # ------------------------------------------------
            # YOLO
            # ------------------------------------------------

            try:

                detection_result = (
                    live_service.detect(
                        frame
                    )
                )

            except Exception:

                logger.exception(
                    "YOLO live inference failed."
                )

                await websocket.send_json({
                    "success": False,
                    "error": (
                        "YOLO live detection failed."
                    ),
                })

                continue

            frame_number += 1

            detections = (
                detection_result[
                    "detections"
                ]
            )

            pothole_count = len(
                detections
            )

            timestamp = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            # ------------------------------------------------
            # DATABASE
            # ------------------------------------------------

            saved_reports = []

            # Only persist potholes when GPS is real.
            if (
                pothole_count > 0
                and has_valid_gps
            ):

                try:

                    saved_reports = (
                        live_service.save_detection(
                            detections=detections,
                            latitude=latitude,
                            longitude=longitude,
                            gps_accuracy=gps_accuracy,
                            timestamp=timestamp,
                        )
                    )

                except Exception:

                    logger.exception(
                        "Could not save "
                        "live pothole report."
                    )

            # ------------------------------------------------
            # RESPONSE
            # ------------------------------------------------

            await websocket.send_json({

                "success": True,

                "timestamp": timestamp,

                "frame_number": frame_number,

                "location": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "accuracy": gps_accuracy,
                    "valid": has_valid_gps,
                },

                "pothole_count": pothole_count,

                "detections": detections,

                "saved_reports": saved_reports,

            })

    except WebSocketDisconnect:

        logger.info(
            "Live detection disconnected: %s",
            client_address,
        )

    except Exception:

        logger.exception(
            "Unexpected live detection error."
        )

        try:

            await websocket.close(
                code=1011
            )

        except Exception:
            pass