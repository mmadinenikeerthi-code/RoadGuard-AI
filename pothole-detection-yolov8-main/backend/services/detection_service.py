# ==========================================================
# backend/services/detection_service.py
# ROADGUARD AI - YOLO DETECTION SERVICE
# ==========================================================

import os
from pathlib import Path
from typing import Dict, Any

import cv2
from ultralytics import YOLO


# ==========================================================
# PROJECT DIRECTORIES
# ==========================================================

# Project root:
# pothole-detection-yolov8-main/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

UPLOAD_DIR = PROJECT_ROOT / "uploads"
RESULTS_DIR = PROJECT_ROOT / "results"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# FIND YOLO MODEL
# ==========================================================

MODEL_CANDIDATES = [
    PROJECT_ROOT / "best.pt",
    PROJECT_ROOT / "models" / "best.pt",
    PROJECT_ROOT / "weights" / "best.pt",
    PROJECT_ROOT / "runs" / "detect" / "train" / "weights" / "best.pt",
    PROJECT_ROOT / "runs" / "detect" / "train2" / "weights" / "best.pt",
    PROJECT_ROOT / "runs" / "train" / "weights" / "best.pt",
]


def find_model() -> Path:
    """
    Find the trained YOLO model automatically.
    """

    for model_path in MODEL_CANDIDATES:
        if model_path.exists():
            print(f"[RoadGuard AI] YOLO model found: {model_path}")
            return model_path

    raise FileNotFoundError(
        "YOLO model best.pt was not found.\n"
        "Please place best.pt in the project root:\n"
        f"{PROJECT_ROOT / 'best.pt'}"
    )


MODEL_PATH = find_model()


# ==========================================================
# LOAD YOLO MODEL ONCE
# ==========================================================

print("[RoadGuard AI] Loading YOLO model...")

model = YOLO(str(MODEL_PATH))

print("[RoadGuard AI] YOLO model loaded successfully.")


# ==========================================================
# HELPERS
# ==========================================================

def resolve_media_path(media_path: str) -> Path:
    """
    Convert database path such as:
        uploads/video.mp4

    into:
        C:/.../pothole-detection-yolov8-main/uploads/video.mp4
    """

    path = Path(media_path)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def get_class_name(names, class_id: int) -> str:
    """
    Safely obtain YOLO class name.
    """

    try:
        if isinstance(names, dict):
            return str(names.get(class_id, "")).lower()

        if isinstance(names, list):
            return str(names[class_id]).lower()

    except Exception:
        pass

    return ""


def is_pothole_detection(names, class_id: int) -> bool:
    """
    Determine whether a detection represents a pothole.

    If the trained model contains only one class, every
    detection is treated as a pothole.

    If multiple classes exist, only classes containing
    'pothole' are counted.
    """

    class_name = get_class_name(names, class_id)

    # Single-class pothole model
    try:
        number_of_classes = len(names)
    except Exception:
        number_of_classes = 1

    if number_of_classes == 1:
        return True

    # Multi-class model
    return "pothole" in class_name


def calculate_severity(
    pothole_count: int,
    max_area_ratio: float,
    average_confidence: float
) -> str:
    """
    Calculate a simple explainable severity level.

    The score considers:
      - number of potholes
      - apparent pothole size
      - detection confidence

    This is a prototype severity calculation, not a
    physical road-engineering measurement.
    """

    if pothole_count <= 0:
        return "LOW"

    score = 0

    # Number of detected unique potholes
    if pothole_count >= 8:
        score += 3
    elif pothole_count >= 4:
        score += 2
    else:
        score += 1

    # Approximate bounding-box area
    if max_area_ratio >= 0.15:
        score += 3
    elif max_area_ratio >= 0.07:
        score += 2
    elif max_area_ratio >= 0.03:
        score += 1

    # Confidence
    if average_confidence >= 0.80:
        score += 2
    elif average_confidence >= 0.50:
        score += 1

    if score >= 7:
        return "CRITICAL"

    if score >= 5:
        return "HIGH"

    if score >= 3:
        return "MODERATE"

    return "LOW"


# ==========================================================
# IMAGE PROCESSING
# ==========================================================

def process_image(
    media_file: Path,
    report_id: int
) -> Dict[str, Any]:

    image = cv2.imread(str(media_file))

    if image is None:
        raise ValueError(
            f"Could not read image: {media_file}"
        )

    height, width = image.shape[:2]

    results = model.predict(
        source=image,
        conf=0.25,
        verbose=False
    )

    result = results[0]

    pothole_count = 0
    confidence_values = []
    max_area_ratio = 0.0

    annotated = image.copy()

    if result.boxes is not None:

        for i in range(len(result.boxes)):

            cls = int(result.boxes.cls[i].item())
            confidence = float(result.boxes.conf[i].item())

            if not is_pothole_detection(
                result.names,
                cls
            ):
                continue

            pothole_count += 1
            confidence_values.append(confidence)

            box = result.boxes.xyxy[i].cpu().numpy()

            x1, y1, x2, y2 = map(int, box)

            box_width = max(0, x2 - x1)
            box_height = max(0, y2 - y1)

            area_ratio = (
                (box_width * box_height)
                / float(width * height)
            )

            max_area_ratio = max(
                max_area_ratio,
                area_ratio
            )

            label = (
                f"Pothole "
                f"{confidence * 100:.0f}%"
            )

            cv2.rectangle(
                annotated,
                (x1, y1),
                (x2, y2),
                (0, 0, 255),
                2
            )

            cv2.putText(
                annotated,
                label,
                (x1, max(25, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2
            )

    average_confidence = (
        sum(confidence_values)
        / len(confidence_values)
        if confidence_values
        else 0.0
    )

    severity = calculate_severity(
        pothole_count,
        max_area_ratio,
        average_confidence
    )

    output_file = RESULTS_DIR / (
        f"report_{report_id}_result.jpg"
    )

    cv2.imwrite(
        str(output_file),
        annotated
    )

    return {
        "pothole_count": pothole_count,
        "confidence": average_confidence,
        "severity": severity,
        "result_path": f"results/{output_file.name}"
    }


# ==========================================================
# VIDEO PROCESSING
# ==========================================================

def process_video(
    media_file: Path,
    report_id: int
) -> Dict[str, Any]:

    cap = cv2.VideoCapture(str(media_file))

    if not cap.isOpened():
        raise ValueError(
            f"Could not open video: {media_file}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = 25.0

    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    if width <= 0 or height <= 0:
        cap.release()
        raise ValueError(
            "Invalid video dimensions."
        )

    output_file = RESULTS_DIR / (
        f"report_{report_id}_result.mp4"
    )

    # MP4 writer
    fourcc = cv2.VideoWriter_fourcc(
        *"mp4v"
    )

    writer = cv2.VideoWriter(
        str(output_file),
        fourcc,
        fps,
        (width, height)
    )

    if not writer.isOpened():
        cap.release()

        raise ValueError(
            "Could not create output video."
        )

    # ------------------------------------------------------
    # Tracking information
    # ------------------------------------------------------

    unique_track_ids = set()

    fallback_detection_count = 0

    confidence_values = []

    max_area_ratio = 0.0

    frame_count = 0

    try:

        while True:

            success, frame = cap.read()

            if not success:
                break

            frame_count += 1

            # ------------------------------------------------
            # YOLO + ByteTrack
            # ------------------------------------------------

            results = model.track(
                source=frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=0.25,
                verbose=False
            )

            result = results[0]

            annotated = frame.copy()

            frame_height, frame_width = frame.shape[:2]

            current_frame_detections = 0

            if result.boxes is not None:

                for i in range(len(result.boxes)):

                    cls = int(
                        result.boxes.cls[i].item()
                    )

                    confidence = float(
                        result.boxes.conf[i].item()
                    )

                    if not is_pothole_detection(
                        result.names,
                        cls
                    ):
                        continue

                    current_frame_detections += 1

                    confidence_values.append(
                        confidence
                    )

                    # ----------------------------------------
                    # Bounding box
                    # ----------------------------------------

                    box = (
                        result.boxes.xyxy[i]
                        .cpu()
                        .numpy()
                    )

                    x1, y1, x2, y2 = map(
                        int,
                        box
                    )

                    box_width = max(
                        0,
                        x2 - x1
                    )

                    box_height = max(
                        0,
                        y2 - y1
                    )

                    area_ratio = (
                        (box_width * box_height)
                        / float(
                            frame_width * frame_height
                        )
                    )

                    max_area_ratio = max(
                        max_area_ratio,
                        area_ratio
                    )

                    # ----------------------------------------
                    # Track ID
                    # ----------------------------------------

                    track_id = None

                    if result.boxes.id is not None:

                        try:
                            track_id = int(
                                result.boxes.id[i].item()
                            )
                        except Exception:
                            track_id = None

                    if track_id is not None:

                        unique_track_ids.add(
                            track_id
                        )

                    # ----------------------------------------
                    # Draw detection
                    # ----------------------------------------

                    cv2.rectangle(
                        annotated,
                        (x1, y1),
                        (x2, y2),
                        (0, 0, 255),
                        2
                    )

                    if track_id is not None:

                        label = (
                            f"Pothole #{track_id} "
                            f"{confidence * 100:.0f}%"
                        )

                    else:

                        label = (
                            f"Pothole "
                            f"{confidence * 100:.0f}%"
                        )

                    cv2.putText(
                        annotated,
                        label,
                        (
                            x1,
                            max(25, y1 - 10)
                        ),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 0, 255),
                        2
                    )

            # ------------------------------------------------
            # Fallback if tracker didn't return IDs
            # ------------------------------------------------

            if result.boxes is not None:

                if result.boxes.id is None:

                    fallback_detection_count += (
                        current_frame_detections
                    )

            # ------------------------------------------------
            # Information overlay
            # ------------------------------------------------

            cv2.putText(
                annotated,
                f"RoadGuard AI | Frame: {frame_count}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

            writer.write(annotated)

    finally:

        cap.release()
        writer.release()

    # ------------------------------------------------------
    # Determine final unique pothole count
    # ------------------------------------------------------

    if unique_track_ids:

        pothole_count = len(
            unique_track_ids
        )

    else:

        # If ByteTrack could not produce IDs,
        # use a conservative frame-based estimate.
        #
        # We don't want every frame detection to become
        # a separate pothole.

        if frame_count > 0:

            pothole_count = max(
                0,
                round(
                    fallback_detection_count
                    / max(1, frame_count // 10)
                )
            )

        else:

            pothole_count = 0

    # ------------------------------------------------------
    # Confidence
    # ------------------------------------------------------

    average_confidence = (
        sum(confidence_values)
        / len(confidence_values)
        if confidence_values
        else 0.0
    )

    # ------------------------------------------------------
    # Severity
    # ------------------------------------------------------

    severity = calculate_severity(
        pothole_count,
        max_area_ratio,
        average_confidence
    )

    return {
        "pothole_count": int(pothole_count),
        "confidence": float(
            average_confidence
        ),
        "severity": severity,
        "result_path": f"results/{output_file.name}"
    }


# ==========================================================
# MAIN PROCESSING FUNCTION
# ==========================================================

def process_media_detection(
    media_path: str,
    media_type: str,
    report_id: int
) -> Dict[str, Any]:

    media_file = resolve_media_path(
        media_path
    )

    if not media_file.exists():

        raise FileNotFoundError(
            f"Media file not found: {media_file}"
        )

    media_type = media_type.lower()

    print(
        f"[RoadGuard AI] Processing report "
        f"#{report_id}: {media_file.name}"
    )

    if media_type == "image":

        result = process_image(
            media_file,
            report_id
        )

    elif media_type == "video":

        result = process_video(
            media_file,
            report_id
        )

    else:

        raise ValueError(
            f"Unsupported media type: {media_type}"
        )

    print(
        f"[RoadGuard AI] Report #{report_id} complete:"
    )

    print(
        f"  Potholes: {result['pothole_count']}"
    )

    print(
        f"  Confidence: "
        f"{result['confidence'] * 100:.1f}%"
    )

    print(
        f"  Severity: {result['severity']}"
    )

    print(
        f"  Result: {result['result_path']}"
    )

    return result