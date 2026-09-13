# ==========================================================
# backend/services/detection_service.py
# ROADGUARD AI
# ==========================================================
#
# Improved pothole detection/counting service
#
# IMPORTANT:
#   - 3D detections are per-frame visualization records.
#   - pothole_count is calculated from stable unique tracks.
#   - A physical pothole may generate multiple YOLO detections.
#   - ByteTrack IDs can fragment, so fragmented tracks are merged.
#
# ==========================================================

import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional

import cv2
from ultralytics import YOLO


# ==========================================================
# PROJECT DIRECTORIES
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

UPLOAD_DIR = PROJECT_ROOT / "uploads"
RESULTS_DIR = PROJECT_ROOT / "results"
THREE_D_DATA_DIR = RESULTS_DIR / "3d_data"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
THREE_D_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# FIND YOLO MODEL
# ==========================================================

MODEL_CANDIDATES = [
    PROJECT_ROOT / "best.pt",
    PROJECT_ROOT / "models" / "best.pt",
    PROJECT_ROOT / "weights" / "best.pt",

    PROJECT_ROOT / "runs" / "detect" / "train" / "weights" / "best.pt",
    PROJECT_ROOT / "runs" / "detect" / "train2" / "weights" / "best.pt",
    PROJECT_ROOT / "runs" / "detect" / "train3" / "weights" / "best.pt",

    PROJECT_ROOT / "runs" / "train" / "weights" / "best.pt",
]


def find_model_path() -> Path:
    """
    Find best.pt in the RoadGuard AI project.
    """

    for candidate in MODEL_CANDIDATES:
        if candidate.exists():
            print(f"[RoadGuard AI] YOLO model found: {candidate}")
            return candidate

    raise FileNotFoundError(
        "\n[RoadGuard AI] ERROR: best.pt was not found.\n"
        "Place best.pt in the project root:\n"
        f"{PROJECT_ROOT / 'best.pt'}\n"
    )


MODEL_PATH = find_model_path()


# ==========================================================
# GLOBAL MODEL
# ==========================================================
#
# Used for IMAGE processing.
#
# VIDEO processing intentionally creates a fresh YOLO
# instance so ByteTrack state from one video cannot leak
# into another video.
#
# ==========================================================

model = YOLO(str(MODEL_PATH))

print("[RoadGuard AI] YOLO model loaded successfully.")


# ==========================================================
# DETECTION SETTINGS
# ==========================================================

# Higher than the old 0.40 to reduce weak false positives.
VIDEO_CONFIDENCE = 0.52

# Image threshold.
IMAGE_CONFIDENCE = 0.30

# Minimum average confidence for a track.
MIN_TRACK_CONFIDENCE = 0.48

# Minimum number of frames a track must appear.
#
# This is additionally calculated dynamically from FPS.
MIN_TRACK_FRAMES = 12

# A track must be visible in enough of its lifetime.
#
# Example:
# first frame = 100
# last frame = 150
# actual detections = 30
#
# visibility = 30 / 51 = 0.588
#
MIN_TRACK_VISIBILITY = 0.50

# Maximum number of frames between fragmented tracks
# before we consider them potentially belonging to
# the same pothole.
MAX_TRACK_GAP = 30

# Maximum normalized distance between the END of one
# track and START of another track.
#
# This is deliberately moderate because the camera moves.
TRACK_MERGE_DISTANCE = 0.18

# Box-size similarity requirement is soft rather than strict.
MIN_SIZE_SIMILARITY = 0.25

# We sample 3D visualization detections at this interval.
THREE_D_SAMPLE_SECONDS = 0.5


# ==========================================================
# UTILITY FUNCTIONS
# ==========================================================

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def calculate_severity(
    pothole_count: int,
    confidence: float
) -> str:
    """
    Calculate report severity.

    This is based on the number of unique potholes,
    NOT the number of per-frame detections.
    """

    if pothole_count <= 0:
        return "LOW"

    if pothole_count <= 2:
        return "MODERATE"

    if pothole_count <= 5:
        return "HIGH"

    return "CRITICAL"


# ==========================================================
# 3D METADATA
# ==========================================================

def save_3d_metadata(
    report_id: int,
    detections: List[Dict[str, Any]],
    pothole_count: int,
    confidence: float,
    severity: str,
    media_type: str = "video",
    unique_potholes: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Save metadata used by RoadGuard AI's 3D viewer.

    IMPORTANT:
        detections = sampled frame detections.

        pothole_count = unique physical pothole estimate.

    Therefore:
        len(detections)
    can be much larger than:
        pothole_count
    """

    output_path = THREE_D_DATA_DIR / f"report_{report_id}.json"

    if unique_potholes is None:
        unique_potholes = []

    metadata = {
        "report_id": report_id,
        "media_type": media_type,

        # Final unique count.
        "pothole_count": pothole_count,

        # Number of sampled frame detections.
        "total_3d_detections": len(detections),

        "confidence": round(confidence, 4),
        "severity": severity,

        "detections": detections,

        # Useful for the 3D viewer.
        "unique_potholes": unique_potholes,
    }

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)

    print(
        f"[RoadGuard AI] 3D metadata saved successfully: "
        f"{output_path}"
    )

    return str(output_path)


# ==========================================================
# CREATE DETECTION OBJECT
# ==========================================================

def create_detection_object(
    box,
    confidence: float,
    frame_number: int,
    frame_width: int,
    frame_height: int,
    track_id: Optional[int] = None,
    class_name: str = "pothole",
) -> Dict[str, Any]:
    """
    Convert YOLO bounding box into normalized metadata.

    These 3D coordinates are RELATIVE visualization
    coordinates.

    They are NOT survey-grade physical coordinates.
    """

    x1, y1, x2, y2 = box

    x1 = clamp(float(x1), 0, frame_width)
    y1 = clamp(float(y1), 0, frame_height)
    x2 = clamp(float(x2), 0, frame_width)
    y2 = clamp(float(y2), 0, frame_height)

    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)

    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0

    normalized_x = center_x / max(frame_width, 1)
    normalized_y = center_y / max(frame_height, 1)

    normalized_width = width / max(frame_width, 1)
    normalized_height = height / max(frame_height, 1)

    area_ratio = (
        (width * height)
        / max(frame_width * frame_height, 1)
    )

    # Relative visualization coordinates.
    position_3d = {
        "x": round((normalized_x - 0.5) * 10.0, 4),
        "y": round((0.5 - normalized_y) * 6.0, 4),
        "z": round(clamp(area_ratio * 100.0, 0.0, 10.0), 4),
    }

    return {
        "frame": frame_number,

        "track_id": track_id,

        "class": class_name,

        "confidence": round(float(confidence), 4),

        "bbox": {
            "x1": round(x1, 2),
            "y1": round(y1, 2),
            "x2": round(x2, 2),
            "y2": round(y2, 2),
        },

        "center": {
            "x": round(center_x, 2),
            "y": round(center_y, 2),
        },

        "normalized": {
            "x": round(normalized_x, 6),
            "y": round(normalized_y, 6),
            "width": round(normalized_width, 6),
            "height": round(normalized_height, 6),
        },

        "area_ratio": round(area_ratio, 8),

        "position_3d": position_3d,
    }


# ==========================================================
# IMAGE PROCESSING
# ==========================================================

def process_image(
    image_path: str,
    report_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process a single image.

    For images, each final pothole detection is a unique
    detection because there is only one frame.
    """

    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    frame_height, frame_width = image.shape[:2]

    results = model.predict(
        source=image,
        conf=IMAGE_CONFIDENCE,
        verbose=False,
    )

    detections: List[Dict[str, Any]] = []

    confidence_values: List[float] = []

    pothole_index = 0

    for result in results:

        if result.boxes is None:
            continue

        for box in result.boxes:

            confidence = safe_float(
                box.conf[0].item()
                if hasattr(box.conf[0], "item")
                else box.conf[0]
            )

            if confidence < IMAGE_CONFIDENCE:
                continue

            coordinates = box.xyxy[0].tolist()

            detection = create_detection_object(
                box=coordinates,
                confidence=confidence,
                frame_number=0,
                frame_width=frame_width,
                frame_height=frame_height,
                track_id=pothole_index,
                class_name="pothole",
            )

            detections.append(detection)
            confidence_values.append(confidence)

            # Draw detection.
            x1, y1, x2, y2 = map(int, coordinates)

            cv2.rectangle(
                image,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2,
            )

            cv2.putText(
                image,
                f"Pothole {pothole_index + 1} "
                f"{confidence:.2f}",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2,
            )

            pothole_index += 1

    pothole_count = len(detections)

    average_confidence = (
        sum(confidence_values)
        / len(confidence_values)
        if confidence_values
        else 0.0
    )

    severity = calculate_severity(
        pothole_count,
        average_confidence,
    )

    result_path = None

    if report_id is not None:

        result_path = (
            RESULTS_DIR
            / f"report_{report_id}_result.jpg"
        )

        cv2.imwrite(
            str(result_path),
            image,
        )

        save_3d_metadata(
            report_id=report_id,
            detections=detections,
            pothole_count=pothole_count,
            confidence=average_confidence,
            severity=severity,
            media_type="image",
            unique_potholes=detections,
        )

    print(
        f"[RoadGuard AI] Image processing complete: "
        f"{pothole_count} potholes"
    )

    return {
        "pothole_count": pothole_count,
        "confidence": average_confidence,
        "severity": severity,
        "result_path": (
            str(result_path)
            if result_path
            else None
        ),
        "detections": detections,
        "unique_potholes": detections,
    }


# ==========================================================
# TRACK RECORD
# ==========================================================

def create_track_record(track_id: int) -> Dict[str, Any]:
    """
    Create internal track information.
    """

    return {
        "track_id": int(track_id),

        "frames": [],

        "frame_count": 0,

        "first_frame": None,

        "last_frame": None,

        "confidences": [],

        "centers": [],

        "boxes": [],

        "areas": [],

        "max_area_ratio": 0.0,

        "first_center": None,

        "last_center": None,

        "first_box": None,

        "last_box": None,
    }


# ==========================================================
# NORMALIZED CENTER DISTANCE
# ==========================================================

def normalized_center_distance(
    center_a,
    center_b,
) -> float:

    if center_a is None or center_b is None:
        return 999.0

    dx = float(center_a[0]) - float(center_b[0])
    dy = float(center_a[1]) - float(center_b[1])

    return math.sqrt(
        dx * dx +
        dy * dy
    )


# ==========================================================
# BOX SIZE SIMILARITY
# ==========================================================

def box_size_similarity(
    box_a,
    box_b,
) -> float:
    """
    Returns a value between 0 and 1.

    1.0 = almost identical size
    0.0 = very different size
    """

    if box_a is None or box_b is None:
        return 0.0

    wa = max(
        0.0001,
        float(box_a[2] - box_a[0]),
    )

    ha = max(
        0.0001,
        float(box_a[3] - box_a[1]),
    )

    wb = max(
        0.0001,
        float(box_b[2] - box_b[0]),
    )

    hb = max(
        0.0001,
        float(box_b[3] - box_b[1]),
    )

    width_similarity = min(wa, wb) / max(wa, wb)

    height_similarity = min(ha, hb) / max(ha, hb)

    return (
        width_similarity +
        height_similarity
    ) / 2.0


# ==========================================================
# TRACK QUALITY
# ==========================================================

def track_quality(
    track: Dict[str, Any]
) -> Dict[str, Any]:

    frame_count = safe_int(
        track.get("frame_count", 0)
    )

    first_frame = track.get("first_frame")
    last_frame = track.get("last_frame")

    if (
        first_frame is None
        or last_frame is None
    ):
        lifetime = frame_count
    else:
        lifetime = (
            int(last_frame)
            - int(first_frame)
            + 1
        )

    lifetime = max(lifetime, 1)

    visibility = (
        frame_count / lifetime
    )

    confidences = [
        safe_float(x)
        for x in track.get(
            "confidences",
            []
        )
    ]

    if confidences:

        average_confidence = (
            sum(confidences)
            / len(confidences)
        )

        sorted_confidences = sorted(
            confidences
        )

        middle = len(
            sorted_confidences
        ) // 2

        if len(sorted_confidences) % 2 == 0:

            median_confidence = (
                sorted_confidences[middle - 1]
                + sorted_confidences[middle]
            ) / 2.0

        else:

            median_confidence = (
                sorted_confidences[middle]
            )

    else:

        average_confidence = 0.0
        median_confidence = 0.0

    return {
        "frame_count": frame_count,

        "lifetime": lifetime,

        "visibility": visibility,

        "average_confidence":
            average_confidence,

        "median_confidence":
            median_confidence,
    }


# ==========================================================
# MERGE DUPLICATE / FRAGMENTED TRACKS
# ==========================================================

def merge_duplicate_tracks(
    tracks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge ByteTrack fragments that probably represent
    the same physical pothole.

    This works primarily on:
        previous track END
        vs
        next track START

    rather than comparing only global average centers.
    """

    if not tracks:
        return []

    # Sort by first appearance.
    ordered_tracks = sorted(
        tracks,
        key=lambda item: (
            item.get("first_frame")
            if item.get("first_frame") is not None
            else 999999
        ),
    )

    merged: List[Dict[str, Any]] = []

    for current in ordered_tracks:

        current_first = safe_int(
            current.get(
                "first_frame",
                0
            )
        )

        current_last = safe_int(
            current.get(
                "last_frame",
                0
            )
        )

        current_first_center = (
            current.get("first_center")
        )

        current_last_center = (
            current.get("last_center")
        )

        current_first_box = (
            current.get("first_box")
        )

        merged_into = None

        # Search backwards through already merged tracks.
        for previous in reversed(merged):

            previous_last = safe_int(
                previous.get(
                    "last_frame",
                    0
                )
            )

            previous_last_center = (
                previous.get("last_center")
            )

            previous_last_box = (
                previous.get("last_box")
            )

            # Only merge temporally close tracks.
            gap = (
                current_first
                - previous_last
            )

            # If tracks overlap in time, do not automatically
            # merge them. They may represent two potholes.
            if gap < 0:
                continue

            if gap > MAX_TRACK_GAP:
                break

            distance = normalized_center_distance(
                previous_last_center,
                current_first_center,
            )

            size_similarity = box_size_similarity(
                previous_last_box,
                current_first_box,
            )

            # Main condition.
            #
            # Either the centers are close,
            # OR they are reasonably close and their
            # bounding-box sizes are similar.
            if (
                distance <= TRACK_MERGE_DISTANCE
                and
                (
                    size_similarity
                    >= MIN_SIZE_SIMILARITY
                    or distance <= 0.10
                )
            ):

                merged_into = previous
                break

        if merged_into is None:

            # New physical pothole candidate.
            merged.append(
                dict(current)
            )

        else:

            # --------------------------------------------------
            # Merge current into previous
            # --------------------------------------------------

            previous_frames = merged_into.get(
                "frames",
                []
            )

            current_frames = current.get(
                "frames",
                []
            )

            merged_into["frames"] = (
                previous_frames
                + current_frames
            )

            merged_into["frame_count"] = len(
                merged_into["frames"]
            )

            merged_into["confidences"] = (
                merged_into.get(
                    "confidences",
                    []
                )
                +
                current.get(
                    "confidences",
                    []
                )
            )

            merged_into["centers"] = (
                merged_into.get(
                    "centers",
                    []
                )
                +
                current.get(
                    "centers",
                    []
                )
            )

            merged_into["boxes"] = (
                merged_into.get(
                    "boxes",
                    []
                )
                +
                current.get(
                    "boxes",
                    []
                )
            )

            merged_into["areas"] = (
                merged_into.get(
                    "areas",
                    []
                )
                +
                current.get(
                    "areas",
                    []
                )
            )

            merged_into["last_frame"] = max(
                safe_int(
                    merged_into.get(
                        "last_frame",
                        0
                    )
                ),
                current_last,
            )

            merged_into["last_center"] = (
                current_last_center
                if current_last_center is not None
                else merged_into.get(
                    "last_center"
                )
            )

            merged_into["last_box"] = (
                current.get("last_box")
                if current.get("last_box")
                is not None
                else merged_into.get(
                    "last_box"
                )
            )

            merged_into["max_area_ratio"] = max(
                safe_float(
                    merged_into.get(
                        "max_area_ratio",
                        0.0
                    )
                ),
                safe_float(
                    current.get(
                        "max_area_ratio",
                        0.0
                    )
                ),
            )

    return merged


# ==========================================================
# CREATE UNIQUE POTHOLE METADATA
# ==========================================================

def create_unique_pothole_metadata(
    tracks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Convert final merged tracks into one metadata object
    per unique pothole.
    """

    output = []

    for index, track in enumerate(
        tracks,
        start=1
    ):

        centers = track.get(
            "centers",
            []
        )

        boxes = track.get(
            "boxes",
            []
        )

        confidences = track.get(
            "confidences",
            []
        )

        if centers:

            average_x = (
                sum(
                    float(center[0])
                    for center in centers
                )
                / len(centers)
            )

            average_y = (
                sum(
                    float(center[1])
                    for center in centers
                )
                / len(centers)
            )

        else:

            average_x = 0.5
            average_y = 0.5

        if boxes:

            average_width = (
                sum(
                    float(box[2] - box[0])
                    for box in boxes
                )
                / len(boxes)
            )

            average_height = (
                sum(
                    float(box[3] - box[1])
                    for box in boxes
                )
                / len(boxes)
            )

        else:

            average_width = 0.0
            average_height = 0.0

        average_confidence = (
            sum(
                float(value)
                for value in confidences
            )
            / len(confidences)
            if confidences
            else 0.0
        )

        quality = track_quality(track)

        output.append(
            {
                "pothole_id": index,

                "original_track_id":
                    track.get("track_id"),

                "frame_count":
                    quality["frame_count"],

                "visibility":
                    round(
                        quality["visibility"],
                        4
                    ),

                "average_confidence":
                    round(
                        average_confidence,
                        4
                    ),

                "center_normalized": {
                    "x": round(
                        average_x,
                        6
                    ),
                    "y": round(
                        average_y,
                        6
                    ),
                },

                "average_box": {
                    "width": round(
                        average_width,
                        6
                    ),
                    "height": round(
                        average_height,
                        6
                    ),
                },
            }
        )

    return output


# ==========================================================
# PROCESS VIDEO
# ==========================================================

def process_video(
    video_path: str,
    report_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process a video using YOLO + ByteTrack.

    The final pothole count is based on STABLE UNIQUE TRACKS.

    It is NOT based on:
        - number of video frames
        - number of raw detections
        - number of 3D records
    """

    print()
    print("=" * 70)
    print("[RoadGuard AI] STARTING VIDEO PROCESSING")
    print("=" * 70)

    print(f"[RoadGuard AI] Video: {video_path}")

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():
        raise ValueError(
            f"Could not open video: {video_path}"
        )

    # ----------------------------------------------------------
    # VIDEO INFORMATION
    # ----------------------------------------------------------

    fps = safe_float(
        capture.get(
            cv2.CAP_PROP_FPS
        ),
        30.0,
    )

    if fps <= 0:
        fps = 30.0

    frame_width = safe_int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        ),
        640,
    )

    frame_height = safe_int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        ),
        480,
    )

    total_frames = safe_int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        ),
        0,
    )

    duration_seconds = (
        total_frames / fps
        if total_frames > 0
        else 0
    )

    print(
        f"[RoadGuard AI] FPS: {fps:.2f}"
    )

    print(
        f"[RoadGuard AI] Resolution: "
        f"{frame_width}x{frame_height}"
    )

    print(
        f"[RoadGuard AI] Frames: "
        f"{total_frames}"
    )

    print(
        f"[RoadGuard AI] Duration: "
        f"{duration_seconds:.2f}s"
    )

    # ----------------------------------------------------------
    # DYNAMIC MINIMUM TRACK LENGTH
    # ----------------------------------------------------------
    #
    # At least ~0.5 second of actual detections.
    #
    # For 30 FPS:
    # 0.5 * 30 = 15 frames
    #
    # ----------------------------------------------------------

    dynamic_min_frames = max(
        MIN_TRACK_FRAMES,
        int(fps * 0.5),
    )

    print(
        f"[RoadGuard AI] Minimum stable track frames: "
        f"{dynamic_min_frames}"
    )

    # ----------------------------------------------------------
    # OUTPUT VIDEO
    # ----------------------------------------------------------

    result_path = None

    if report_id is not None:

        result_path = (
            RESULTS_DIR
            / f"report_{report_id}_result.mp4"
        )

    writer = None

    if result_path is not None:

        fourcc = cv2.VideoWriter_fourcc(
            *"mp4v"
        )

        writer = cv2.VideoWriter(
            str(result_path),
            fourcc,
            fps,
            (
                frame_width,
                frame_height,
            ),
        )

    # ----------------------------------------------------------
    # IMPORTANT:
    #
    # USE A FRESH MODEL FOR THIS VIDEO.
    #
    # This prevents ByteTrack state from a previous video
    # from leaking into this video.
    # ----------------------------------------------------------

    video_model = YOLO(
        str(MODEL_PATH)
    )

    print(
        "[RoadGuard AI] Fresh YOLO tracker created "
        "for this video."
    )

    # ----------------------------------------------------------
    # TRACK STORAGE
    # ----------------------------------------------------------

    track_records: Dict[
        int,
        Dict[str, Any]
    ] = {}

    # Sampled detections for 3D visualization.
    detections: List[
        Dict[str, Any]
    ] = []

    confidence_values: List[
        float
    ] = []

    frame_number = 0

    # Every ~0.5 seconds.
    sample_interval = max(
        1,
        int(
            fps
            * THREE_D_SAMPLE_SECONDS
        ),
    )

    # ----------------------------------------------------------
    # FRAME LOOP
    # ----------------------------------------------------------

    while True:

        success, frame = capture.read()

        if not success:
            break

        frame_number += 1

        # ------------------------------------------------------
        # YOLO + BYTE TRACK
        # ------------------------------------------------------

        results = video_model.track(
            source=frame,

            persist=True,

            tracker="bytetrack.yaml",

            conf=VIDEO_CONFIDENCE,

            verbose=False,
        )

        # ------------------------------------------------------
        # PROCESS RESULTS
        # ------------------------------------------------------

        for result in results:

            if result.boxes is None:
                continue

            boxes = result.boxes

            for i in range(
                len(boxes)
            ):

                box = boxes[i]

                # Confidence.
                confidence = safe_float(
                    box.conf[0].item()
                    if hasattr(
                        box.conf[0],
                        "item"
                    )
                    else box.conf[0]
                )

                if (
                    confidence
                    < VIDEO_CONFIDENCE
                ):
                    continue

                confidence_values.append(
                    confidence
                )

                # Coordinates.
                coordinates = (
                    box.xyxy[0]
                    .tolist()
                )

                x1, y1, x2, y2 = map(
                    float,
                    coordinates
                )

                center_x = (
                    (x1 + x2)
                    / 2.0
                )

                center_y = (
                    (y1 + y2)
                    / 2.0
                )

                normalized_center = (
                    center_x
                    / max(
                        frame_width,
                        1
                    ),
                    center_y
                    / max(
                        frame_height,
                        1
                    ),
                )

                normalized_box = (
                    x1
                    / max(
                        frame_width,
                        1
                    ),
                    y1
                    / max(
                        frame_height,
                        1
                    ),
                    x2
                    / max(
                        frame_width,
                        1
                    ),
                    y2
                    / max(
                        frame_height,
                        1
                    ),
                )

                area_ratio = (
                    ((x2 - x1)
                     * (y2 - y1))
                    /
                    max(
                        frame_width
                        * frame_height,
                        1
                    )
                )

                # --------------------------------------------------
                # TRACK ID
                # --------------------------------------------------

                track_id = None

                if boxes.id is not None:

                    try:

                        track_id = safe_int(
                            boxes.id[i].item()
                            if hasattr(
                                boxes.id[i],
                                "item"
                            )
                            else boxes.id[i]
                        )

                    except Exception:
                        track_id = None

                # --------------------------------------------------
                # SAVE TRACK
                # --------------------------------------------------

                if track_id is not None:

                    if track_id not in track_records:

                        track_records[
                            track_id
                        ] = create_track_record(
                            track_id
                        )

                    track = track_records[
                        track_id
                    ]

                    track["frames"].append(
                        frame_number
                    )

                    track["frame_count"] += 1

                    if (
                        track["first_frame"]
                        is None
                    ):

                        track[
                            "first_frame"
                        ] = frame_number

                        track[
                            "first_center"
                        ] = normalized_center

                        track[
                            "first_box"
                        ] = normalized_box

                    track[
                        "last_frame"
                    ] = frame_number

                    track[
                        "last_center"
                    ] = normalized_center

                    track[
                        "last_box"
                    ] = normalized_box

                    track[
                        "confidences"
                    ].append(
                        confidence
                    )

                    track[
                        "centers"
                    ].append(
                        normalized_center
                    )

                    track[
                        "boxes"
                    ].append(
                        normalized_box
                    )

                    track[
                        "areas"
                    ].append(
                        area_ratio
                    )

                    track[
                        "max_area_ratio"
                    ] = max(
                        safe_float(
                            track.get(
                                "max_area_ratio",
                                0.0
                            )
                        ),
                        area_ratio,
                    )

                # --------------------------------------------------
                # 3D SAMPLE
                # --------------------------------------------------

                if (
                    frame_number
                    % sample_interval
                    == 0
                ):

                    detection = (
                        create_detection_object(
                            box=coordinates,
                            confidence=confidence,
                            frame_number=frame_number,
                            frame_width=frame_width,
                            frame_height=frame_height,
                            track_id=track_id,
                            class_name="pothole",
                        )
                    )

                    detections.append(
                        detection
                    )

                # --------------------------------------------------
                # DRAW DETECTION
                # --------------------------------------------------

                ix1, iy1, ix2, iy2 = map(
                    int,
                    coordinates
                )

                cv2.rectangle(
                    frame,
                    (ix1, iy1),
                    (ix2, iy2),
                    (0, 255, 0),
                    2,
                )

                label = (
                    f"Pothole"
                )

                if track_id is not None:

                    label += (
                        f" ID:{track_id}"
                    )

                label += (
                    f" {confidence:.2f}"
                )

                cv2.putText(
                    frame,
                    label,
                    (
                        ix1,
                        max(
                            20,
                            iy1 - 8
                        ),
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

        # ------------------------------------------------------
        # WRITE OUTPUT FRAME
        # ------------------------------------------------------

        if writer is not None:

            writer.write(
                frame
            )

    # ----------------------------------------------------------
    # CLEAN UP
    # ----------------------------------------------------------

    capture.release()

    if writer is not None:
        writer.release()

    # ----------------------------------------------------------
    # RAW TRACK INFORMATION
    # ----------------------------------------------------------

    raw_track_count = len(
        track_records
    )

    print(
        f"[RoadGuard AI] Raw ByteTrack IDs: "
        f"{raw_track_count}"
    )

    # ----------------------------------------------------------
    # FILTER TRACKS
    # ----------------------------------------------------------

    confirmed_tracks: List[
        Dict[str, Any]
    ] = []

    rejected_tracks: List[
        Dict[str, Any]
    ] = []

    for track in track_records.values():

        quality = track_quality(
            track
        )

        frame_count = quality[
            "frame_count"
        ]

        visibility = quality[
            "visibility"
        ]

        average_confidence = quality[
            "average_confidence"
        ]

        median_confidence = quality[
            "median_confidence"
        ]

        # ------------------------------------------------------
        # STABILITY REQUIREMENTS
        # ------------------------------------------------------

        passes_frame_count = (
            frame_count
            >= dynamic_min_frames
        )

        passes_visibility = (
            visibility
            >= MIN_TRACK_VISIBILITY
        )

        passes_average_confidence = (
            average_confidence
            >= MIN_TRACK_CONFIDENCE
        )

        passes_median_confidence = (
            median_confidence
            >= MIN_TRACK_CONFIDENCE
        )

        if (
            passes_frame_count
            and passes_visibility
            and passes_average_confidence
            and passes_median_confidence
        ):

            confirmed_tracks.append(
                track
            )

        else:

            rejected_tracks.append(
                track
            )

    confirmed_track_count = len(
        confirmed_tracks
    )

    rejected_track_count = len(
        rejected_tracks
    )

    print(
        f"[RoadGuard AI] Confirmed stable tracks: "
        f"{confirmed_track_count}"
    )

    print(
        f"[RoadGuard AI] Rejected weak tracks: "
        f"{rejected_track_count}"
    )

    # ----------------------------------------------------------
    # MERGE FRAGMENTED TRACKS
    # ----------------------------------------------------------

    merged_tracks = (
        merge_duplicate_tracks(
            confirmed_tracks
        )
    )

    merged_track_count = len(
        merged_tracks
    )

    print(
        f"[RoadGuard AI] Final unique potholes after "
        f"track merging: {merged_track_count}"
    )

    # ----------------------------------------------------------
    # FALLBACK
    # ----------------------------------------------------------
    #
    # If ByteTrack fails completely, do NOT count every
    # sampled detection.
    #
    # Instead return zero because counting noisy frame
    # detections would produce the exact problem we are
    # trying to fix.
    #
    # ----------------------------------------------------------

    if raw_track_count == 0:

        print(
            "[RoadGuard AI] No ByteTrack IDs found."
        )

        pothole_count = 0

        unique_potholes = []

    else:

        pothole_count = (
            merged_track_count
        )

        unique_potholes = (
            create_unique_pothole_metadata(
                merged_tracks
            )
        )

    # ----------------------------------------------------------
    # FINAL CONFIDENCE
    # ----------------------------------------------------------

    if confidence_values:

        final_confidence = (
            sum(
                confidence_values
            )
            /
            len(
                confidence_values
            )
        )

    else:

        final_confidence = 0.0

    # ----------------------------------------------------------
    # SEVERITY
    # ----------------------------------------------------------

    severity = calculate_severity(
        pothole_count,
        final_confidence,
    )

    # ----------------------------------------------------------
    # SAVE 3D METADATA
    # ----------------------------------------------------------

    metadata_path = None

    if report_id is not None:

        metadata_path = save_3d_metadata(
            report_id=report_id,
            detections=detections,
            pothole_count=pothole_count,
            confidence=final_confidence,
            severity=severity,
            media_type="video",
            unique_potholes=unique_potholes,
        )

    # ----------------------------------------------------------
    # FINAL LOG
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print(
        f"[RoadGuard AI] FINAL POTHOLES: "
        f"{pothole_count}"
    )
    print(
        f"[RoadGuard AI] Average confidence: "
        f"{final_confidence:.2%}"
    )
    print(
        f"[RoadGuard AI] Severity: "
        f"{severity}"
    )
    print(
        f"[RoadGuard AI] 3D frame detections: "
        f"{len(detections)}"
    )
    print("=" * 70)
    print()

    return {
        # ----------------------------------------------
        # FINAL USER-FACING COUNT
        # ----------------------------------------------
        "pothole_count": pothole_count,

        "confidence": final_confidence,

        "severity": severity,

        "result_path": (
            str(result_path)
            if result_path is not None
            else None
        ),

        # ----------------------------------------------
        # DEBUG INFORMATION
        # ----------------------------------------------
        "raw_track_count":
            raw_track_count,

        "confirmed_track_count":
            confirmed_track_count,

        "merged_track_count":
            merged_track_count,

        "rejected_track_count":
            rejected_track_count,

        # ----------------------------------------------
        # IMPORTANT:
        # This is NOT the pothole count.
        # ----------------------------------------------
        "three_d_detection_count":
            len(detections),

        # ----------------------------------------------
        # 3D metadata
        # ----------------------------------------------
        "detections":
            detections,

        "unique_potholes":
            unique_potholes,

        "metadata_path":
            metadata_path,
    }


# ==========================================================
# PROCESS MEDIA
# ==========================================================

def process_media_detection(
    report_id: int,
    media_path: str,
    media_type: str,
) -> Dict[str, Any]:
    """
    Main dispatcher used by the detection router.
    """

    media_type = (
        media_type or ""
    ).lower().strip()

    print()
    print(
        "[RoadGuard AI] Processing media:"
    )

    print(
        f"  Report ID: {report_id}"
    )

    print(
        f"  Media type: {media_type}"
    )

    print(
        f"  Media path: {media_path}"
    )

    # ----------------------------------------------------------
    # IMAGE
    # ----------------------------------------------------------

    if media_type in {
        "image",
        "jpg",
        "jpeg",
        "png",
        "webp",
    }:

        result = process_image(
            image_path=media_path,
            report_id=report_id,
        )

    # ----------------------------------------------------------
    # VIDEO
    # ----------------------------------------------------------

    elif media_type in {
        "video",
        "mp4",
        "avi",
        "mov",
        "mkv",
        "webm",
    }:

        result = process_video(
            video_path=media_path,
            report_id=report_id,
        )

    # ----------------------------------------------------------
    # UNKNOWN
    # ----------------------------------------------------------

    else:

        raise ValueError(
            f"Unsupported media type: "
            f"{media_type}"
        )

    # ----------------------------------------------------------
    # FINAL LOG
    # ----------------------------------------------------------

    print(
        f"[RoadGuard AI] Report #{report_id} "
        f"processed successfully."
    )

    print(
        f"[RoadGuard AI] Potholes detected: "
        f"{result.get('pothole_count', 0)}"
    )

    return result