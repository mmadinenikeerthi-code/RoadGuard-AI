# ==========================================================
# backend/services/detection_service.py
# ROADGUARD AI
# ==========================================================
#
# pothole_count = number of UNIQUE PHYSICAL POTHOLES.
#
# Pipeline:
#   YOLO -> ByteTrack -> raw tracks
#     -> Stage 0  (drop pure noise)
#     -> Stage A  (concurrent, high-IoU duplicate tracks)
#     -> Stage A2 (concurrent, spatially-adjacent fragments —
#                  handles static/CCTV cameras where YOLO splits
#                  one irregular pothole into several simultaneous
#                  boxes with LOW IoU to each other)
#     -> Stage B  (motion-compensated temporal stitching, for
#                  fragmented tracks separated by a time gap)
#     -> Stage C  (final quality/visibility validation on the
#                  MERGED clusters, not the raw tracks)
#
# "3D detections" / total_3d_detections = sampled per-frame
# visualization records. NEVER used as the pothole count.
#
# ==========================================================

import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import cv2
from ultralytics import YOLO


# ==========================================================
# PROJECT DIRECTORIES
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

UPLOAD_DIR = PROJECT_ROOT / "uploads"
RESULTS_DIR = PROJECT_ROOT / "results"
THREE_D_DATA_DIR = RESULTS_DIR / "3d_data"
PANORAMA_DIR = RESULTS_DIR / "panorama"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
THREE_D_DATA_DIR.mkdir(parents=True, exist_ok=True)
PANORAMA_DIR.mkdir(parents=True, exist_ok=True)


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
    for candidate in MODEL_CANDIDATES:
        if candidate.exists():
            print(f"[RoadGuard AI] YOLO model found: {candidate}")
            return candidate
    raise FileNotFoundError(
        "\n[RoadGuard AI] ERROR: best.pt was not found.\n"
        f"Place best.pt in the project root: {PROJECT_ROOT / 'best.pt'}\n"
    )


MODEL_PATH = find_model_path()
model = YOLO(str(MODEL_PATH))
print("[RoadGuard AI] YOLO model loaded successfully.")


# ==========================================================
# DETECTION SETTINGS
# ==========================================================

VIDEO_CONFIDENCE = 0.52
IMAGE_CONFIDENCE = 0.30

# --- Stage-0: lenient pre-admission (keeps real fragments alive) ---
CANDIDATE_MIN_FRAMES = 3
CANDIDATE_MIN_CONFIDENCE = 0.35

# --- Stage-A: concurrent, high-IoU duplicate-ID resolution ---
DUPLICATE_IOU_THRESHOLD = 0.35
DUPLICATE_MIN_OVERLAP_FRACTION = 0.50

# --- Stage-A2: concurrent spatial-proximity resolution ---
#
# Designed for static/CCTV cameras where YOLO can split one irregular
# pothole into several simultaneous bounding boxes that never overlap
# enough (low IoU) for Stage A to catch, and which Stage B intentionally
# skips because they coexist in time rather than being sequential.
#
CONCURRENT_SPATIAL_DISTANCE = 0.10
CONCURRENT_CENTER_DISTANCE_FACTOR = 0.75
CONCURRENT_MIN_OVERLAP_FRACTION = 0.60
CONCURRENT_MIN_TIME_OVERLAP = 0.60
CONCURRENT_SIZE_RATIO = 4.0
CONCURRENT_MIN_SPATIAL_MATCH_FRACTION = 0.60

# --- Stage-B: motion-compensated stitching (sequential fragments) ---
MAX_MERGE_GAP_SECONDS = 1.5
TRACK_MERGE_BASE_DISTANCE = 0.08          # normalized screen units
TRACK_MERGE_GROWTH_PER_FRAME = 0.003      # extra slack per frame of gap
TRACK_MERGE_MAX_DISTANCE = 0.30           # hard ceiling regardless of gap
AREA_RATIO_MAX = 3.5                      # max allowed size jump across a gap
VELOCITY_SAMPLE_POINTS = 5                # points used to fit exit/entry velocity

# --- Stage-C: final validation (applied to MERGED clusters) ---
MIN_TRACK_FRAMES = 12
MIN_TRACK_VISIBILITY = 0.40
MIN_TRACK_CONFIDENCE = 0.48

# 3D sampling / panorama
THREE_D_SAMPLE_SECONDS = 0.5
EQUIRECT_ASPECT_TOLERANCE = 0.12   # width/height within 12% of 2.0 -> treat as 360

# Two-pass annotation gives the output video consistent "Pothole #N" labels.
# Costs ~2x inference time on video. Set False for a faster single pass that
# labels boxes with raw ByteTrack IDs instead of final pothole numbers.
TWO_PASS_VIDEO_ANNOTATION = True


# ==========================================================
# BASIC UTILITIES
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


def calculate_severity(pothole_count: int, confidence: float) -> str:
    if pothole_count <= 0:
        return "LOW"
    if pothole_count <= 2:
        return "MODERATE"
    if pothole_count <= 5:
        return "HIGH"
    return "CRITICAL"


# ==========================================================
# GEOMETRY HELPERS
# ==========================================================

def iou(box_a: Tuple[float, float, float, float],
        box_b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def box_center_distance(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> float:
    """
    Euclidean distance between normalized box centers.
    """
    ax = (box_a[0] + box_a[2]) / 2.0
    ay = (box_a[1] + box_a[3]) / 2.0
    bx = (box_b[0] + box_b[2]) / 2.0
    by = (box_b[1] + box_b[3]) / 2.0

    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def box_dimensions(box: Tuple[float, float, float, float]) -> Tuple[float, float]:
    return (
        max(0.0, box[2] - box[0]),
        max(0.0, box[3] - box[1]),
    )


def boxes_are_spatially_related(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> bool:
    """
    Determines whether two boxes are close enough to potentially be
    different YOLO fragments of the SAME physical pothole.

    This intentionally does NOT require IoU overlap — adjacent (not
    overlapping) fragments of one irregular pothole are exactly the
    case this function needs to catch.
    """
    aw, ah = box_dimensions(box_a)
    bw, bh = box_dimensions(box_b)

    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return False

    area_a = aw * ah
    area_b = bw * bh

    size_ratio = max(area_a, area_b) / max(min(area_a, area_b), 1e-9)
    if size_ratio > CONCURRENT_SIZE_RATIO:
        return False

    distance = box_center_distance(box_a, box_b)

    diagonal_a = math.sqrt(aw ** 2 + ah ** 2)
    diagonal_b = math.sqrt(bw ** 2 + bh ** 2)

    spatial_threshold = max(
        CONCURRENT_SPATIAL_DISTANCE,
        CONCURRENT_CENTER_DISTANCE_FACTOR * ((diagonal_a + diagonal_b) / 2.0),
    )

    return distance <= spatial_threshold


def linear_velocity(points: List[Tuple[int, float]]) -> float:
    """
    Least-squares slope of value vs frame index.
    points = [(frame_number, value), ...]
    """
    n = len(points)
    if n < 2:
        return 0.0

    mean_frame = sum(p[0] for p in points) / n
    mean_value = sum(p[1] for p in points) / n

    numerator = sum((p[0] - mean_frame) * (p[1] - mean_value) for p in points)
    denominator = sum((p[0] - mean_frame) ** 2 for p in points)

    if denominator == 0:
        return 0.0

    return numerator / denominator


def estimate_exit_velocity(track: Dict[str, Any], n: int = VELOCITY_SAMPLE_POINTS):
    frames = track["frames"][-n:]
    centers = track["centers"][-n:]
    vx = linear_velocity(list(zip(frames, [c[0] for c in centers])))
    vy = linear_velocity(list(zip(frames, [c[1] for c in centers])))
    return vx, vy


def predicted_position(center, velocity, frames_ahead: float):
    return (
        center[0] + velocity[0] * frames_ahead,
        center[1] + velocity[1] * frames_ahead,
    )


def adaptive_merge_distance(gap_frames: int) -> float:
    distance = TRACK_MERGE_BASE_DISTANCE + TRACK_MERGE_GROWTH_PER_FRAME * gap_frames
    return min(distance, TRACK_MERGE_MAX_DISTANCE)


def area_ratio_compatible(area_a: float, area_b: float) -> bool:
    if area_a <= 0 or area_b <= 0:
        return True
    ratio = max(area_a, area_b) / min(area_a, area_b)
    return ratio <= AREA_RATIO_MAX


# ==========================================================
# UNION-FIND
# ==========================================================

class UnionFind:
    def __init__(self, items):
        self.parent = {item: item for item in items}

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def groups(self):
        buckets: Dict[Any, List[Any]] = {}
        for item in self.parent:
            root = self.find(item)
            buckets.setdefault(root, []).append(item)
        return list(buckets.values())


# ==========================================================
# TRACK RECORD
# ==========================================================

def create_track_record(track_id: int) -> Dict[str, Any]:
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
        "frame_box_map": {},
        "max_area_ratio": 0.0,
        "first_center": None,
        "last_center": None,
        "first_box": None,
        "last_box": None,
        "source_track_ids": [int(track_id)],
    }


def track_quality(track: Dict[str, Any]) -> Dict[str, Any]:
    frame_count = safe_int(track.get("frame_count", 0))
    first_frame = track.get("first_frame")
    last_frame = track.get("last_frame")

    if first_frame is None or last_frame is None:
        lifetime = frame_count
    else:
        lifetime = int(last_frame) - int(first_frame) + 1
    lifetime = max(lifetime, 1)

    visibility = frame_count / lifetime

    confidences = [safe_float(x) for x in track.get("confidences", [])]
    if confidences:
        average_confidence = sum(confidences) / len(confidences)
        sorted_conf = sorted(confidences)
        mid = len(sorted_conf) // 2
        if len(sorted_conf) % 2 == 0:
            median_confidence = (sorted_conf[mid - 1] + sorted_conf[mid]) / 2.0
        else:
            median_confidence = sorted_conf[mid]
    else:
        average_confidence = 0.0
        median_confidence = 0.0

    return {
        "frame_count": frame_count,
        "lifetime": lifetime,
        "visibility": visibility,
        "average_confidence": average_confidence,
        "median_confidence": median_confidence,
    }


def track_exit_area(track: Dict[str, Any]) -> float:
    areas = track.get("areas", [])
    return areas[-1] if areas else 0.0


def track_entry_area(track: Dict[str, Any]) -> float:
    areas = track.get("areas", [])
    return areas[0] if areas else 0.0


def flatten_source_ids(tracks: List[Dict[str, Any]]) -> List[int]:
    """
    Collects the full provenance (original raw ByteTrack IDs) across
    a group of tracks, regardless of how many prior stages already
    merged each one. Used so the final video-annotation ID map can
    label EVERY raw ByteTrack ID that contributed to a pothole, not
    just whichever ID happened to be "primary" at each stage.
    """
    ids = set()
    for track in tracks:
        ids.update(track.get("source_track_ids", [track["track_id"]]))
    return sorted(ids)


# ==========================================================
# STAGE A — CONCURRENT, HIGH-IOU DUPLICATE RESOLUTION
# ==========================================================

def resolve_concurrent_duplicates(
    tracks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Collapses tracks whose time ranges overlap AND whose boxes closely
    overlap spatially (high IoU) during that overlap — i.e. the same
    physical pothole was briefly assigned two ByteTrack IDs at once.
    """

    if not tracks:
        return []

    ids = [t["track_id"] for t in tracks]
    by_id = {t["track_id"]: t for t in tracks}
    uf = UnionFind(ids)

    dup_pairs_logged = []

    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            a, b = tracks[i], tracks[j]

            overlap_frames = set(a["frames"]) & set(b["frames"])
            if not overlap_frames:
                continue

            ious = []
            for frame in overlap_frames:
                box_a = a["frame_box_map"].get(frame)
                box_b = b["frame_box_map"].get(frame)
                if box_a is not None and box_b is not None:
                    ious.append(iou(box_a, box_b))

            if not ious:
                continue

            avg_iou = sum(ious) / len(ious)
            overlap_fraction = len(overlap_frames) / max(
                1, min(len(a["frames"]), len(b["frames"]))
            )

            if (
                avg_iou >= DUPLICATE_IOU_THRESHOLD
                and overlap_fraction >= DUPLICATE_MIN_OVERLAP_FRACTION
            ):
                uf.union(a["track_id"], b["track_id"])
                dup_pairs_logged.append(
                    (a["track_id"], b["track_id"], avg_iou, overlap_fraction)
                )

    for tid_a, tid_b, avg_iou, frac in dup_pairs_logged:
        print(
            f"[RoadGuard AI][Stage A] Track {tid_a} and {tid_b} look like "
            f"the SAME detection (avg IoU={avg_iou:.2f}, "
            f"overlap={frac:.0%}) -> collapsing."
        )

    combined: List[Dict[str, Any]] = []

    for group_ids in uf.groups():
        if len(group_ids) == 1:
            combined.append(by_id[group_ids[0]])
            continue

        group_tracks = [by_id[i] for i in group_ids]

        frame_data: Dict[int, Dict[str, Any]] = {}
        for t in group_tracks:
            for idx, frame in enumerate(t["frames"]):
                confidence = t["confidences"][idx]
                if frame not in frame_data or confidence > frame_data[frame]["confidence"]:
                    frame_data[frame] = {
                        "confidence": confidence,
                        "center": t["centers"][idx],
                        "box": t["boxes"][idx],
                        "area": t["areas"][idx],
                    }

        ordered_frames = sorted(frame_data.keys())

        primary_id = max(group_tracks, key=lambda t: t["frame_count"])["track_id"]

        merged_track = create_track_record(primary_id)
        merged_track["frames"] = ordered_frames
        merged_track["frame_count"] = len(ordered_frames)
        merged_track["confidences"] = [frame_data[f]["confidence"] for f in ordered_frames]
        merged_track["centers"] = [frame_data[f]["center"] for f in ordered_frames]
        merged_track["boxes"] = [frame_data[f]["box"] for f in ordered_frames]
        merged_track["areas"] = [frame_data[f]["area"] for f in ordered_frames]
        merged_track["frame_box_map"] = {f: frame_data[f]["box"] for f in ordered_frames}
        merged_track["first_frame"] = ordered_frames[0]
        merged_track["last_frame"] = ordered_frames[-1]
        merged_track["first_center"] = frame_data[ordered_frames[0]]["center"]
        merged_track["last_center"] = frame_data[ordered_frames[-1]]["center"]
        merged_track["first_box"] = frame_data[ordered_frames[0]]["box"]
        merged_track["last_box"] = frame_data[ordered_frames[-1]]["box"]
        merged_track["max_area_ratio"] = max(frame_data[f]["area"] for f in ordered_frames)
        # Preserve full provenance so Stage A2/B/video-annotation can
        # still find every raw ByteTrack ID that fed into this cluster.
        merged_track["source_track_ids"] = flatten_source_ids(group_tracks)

        combined.append(merged_track)

    return combined


# ==========================================================
# STAGE A2 — CONCURRENT SPATIAL-PROXIMITY MERGING
# ==========================================================

def merge_track_group(group_tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge multiple tracks while ensuring that each frame contributes
    at most one observation to the resulting physical pothole.
    """

    if len(group_tracks) == 1:
        return group_tracks[0]

    frame_data: Dict[int, Dict[str, Any]] = {}

    for track in group_tracks:
        for idx, frame in enumerate(track["frames"]):
            confidence = safe_float(track["confidences"][idx])
            center = track["centers"][idx]
            box = track["boxes"][idx]
            area = track["areas"][idx]

            # For a frame where several fragments exist, keep the
            # strongest observation.
            if frame not in frame_data or confidence > frame_data[frame]["confidence"]:
                frame_data[frame] = {
                    "confidence": confidence,
                    "center": center,
                    "box": box,
                    "area": area,
                }

    ordered_frames = sorted(frame_data.keys())

    primary_id = max(group_tracks, key=lambda t: t["frame_count"])["track_id"]

    merged = create_track_record(primary_id)

    merged["frames"] = ordered_frames
    merged["frame_count"] = len(ordered_frames)
    merged["confidences"] = [frame_data[f]["confidence"] for f in ordered_frames]
    merged["centers"] = [frame_data[f]["center"] for f in ordered_frames]
    merged["boxes"] = [frame_data[f]["box"] for f in ordered_frames]
    merged["areas"] = [frame_data[f]["area"] for f in ordered_frames]
    merged["frame_box_map"] = {f: frame_data[f]["box"] for f in ordered_frames}

    if ordered_frames:
        merged["first_frame"] = ordered_frames[0]
        merged["last_frame"] = ordered_frames[-1]
        merged["first_center"] = frame_data[ordered_frames[0]]["center"]
        merged["last_center"] = frame_data[ordered_frames[-1]]["center"]
        merged["first_box"] = frame_data[ordered_frames[0]]["box"]
        merged["last_box"] = frame_data[ordered_frames[-1]]["box"]

    merged["max_area_ratio"] = max(
        (t.get("max_area_ratio", 0.0) for t in group_tracks),
        default=0.0,
    )

    # Flatten provenance from every source track's OWN source_track_ids,
    # not just its raw track_id, so nothing gets lost across stages.
    merged["source_track_ids"] = flatten_source_ids(group_tracks)

    return merged


def resolve_concurrent_spatial_proximity(
    tracks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Stage A2.

    Handles the static-camera / CCTV failure mode:

        ONE physical pothole
              |
        YOLO produces multiple adjacent boxes (low IoU to each other)
              |
        ByteTrack creates multiple persistent IDs, coexisting the
        whole time -> Stage A can't catch them (IoU too low) and
        Stage B intentionally skips them (they never have a "gap",
        they're simultaneous, not sequential).

    Unlike Stage A, this stage does not depend on IoU at all. It
    requires:
      1. substantial temporal coexistence
      2. spatial proximity (not overlap) scaled to box size
      3. similar object scale
      4. a consistent spatial relationship across most of the
         overlapping frames (not just a lucky one-off match)
    """

    if not tracks:
        return []

    ids = [t["track_id"] for t in tracks]
    by_id = {t["track_id"]: t for t in tracks}
    uf = UnionFind(ids)

    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            a = tracks[i]
            b = tracks[j]

            frames_a = set(a["frames"])
            frames_b = set(b["frames"])
            overlap_frames = frames_a & frames_b

            if not overlap_frames:
                continue

            overlap_fraction = len(overlap_frames) / max(
                1, min(len(frames_a), len(frames_b))
            )
            if overlap_fraction < CONCURRENT_MIN_OVERLAP_FRACTION:
                continue

            earliest = min(a["first_frame"], b["first_frame"])
            latest = max(a["last_frame"], b["last_frame"])
            combined_lifetime = max(1, latest - earliest + 1)
            time_overlap_fraction = len(overlap_frames) / combined_lifetime

            if time_overlap_fraction < CONCURRENT_MIN_TIME_OVERLAP:
                continue

            spatial_matches = 0
            for frame in overlap_frames:
                box_a = a["frame_box_map"].get(frame)
                box_b = b["frame_box_map"].get(frame)
                if box_a is None or box_b is None:
                    continue
                if boxes_are_spatially_related(box_a, box_b):
                    spatial_matches += 1

            spatial_fraction = spatial_matches / len(overlap_frames)
            if spatial_fraction < CONCURRENT_MIN_SPATIAL_MATCH_FRACTION:
                continue

            uf.union(a["track_id"], b["track_id"])

            print(
                "[RoadGuard AI][Stage A2] "
                f"Tracks {a['track_id']} + {b['track_id']} appear to be "
                f"concurrent fragments of the SAME physical pothole "
                f"(overlap={overlap_fraction:.0%}, "
                f"time_overlap={time_overlap_fraction:.0%}, "
                f"spatial_match={spatial_fraction:.0%})"
            )

    merged_tracks = []
    for group_ids in uf.groups():
        group_tracks = [by_id[track_id] for track_id in group_ids]
        if len(group_tracks) == 1:
            merged_tracks.append(group_tracks[0])
        else:
            merged_tracks.append(merge_track_group(group_tracks))

    return merged_tracks


# ==========================================================
# STAGE B — MOTION-COMPENSATED FRAGMENT STITCHING (sequential)
# ==========================================================

def stitch_fragmented_tracks(
    tracks: List[Dict[str, Any]],
    fps: float,
) -> List[Dict[str, Any]]:

    if not tracks:
        return []

    max_gap_frames = max(1, int(fps * MAX_MERGE_GAP_SECONDS))

    ordered = sorted(tracks, key=lambda t: t["first_frame"])

    candidates = []  # (score, track_a_id, track_b_id)

    for i, track_a in enumerate(ordered):
        exit_velocity = estimate_exit_velocity(track_a)

        for track_b in ordered[i + 1:]:
            gap = track_b["first_frame"] - track_a["last_frame"]

            if gap < 0:
                continue
            if gap > max_gap_frames:
                break  # ordered by first_frame -> gaps only grow from here

            predicted = predicted_position(track_a["last_center"], exit_velocity, gap)
            distance = math.sqrt(
                (predicted[0] - track_b["first_center"][0]) ** 2
                + (predicted[1] - track_b["first_center"][1]) ** 2
            )

            threshold = adaptive_merge_distance(gap)
            size_ok = area_ratio_compatible(
                track_exit_area(track_a), track_entry_area(track_b)
            )

            if distance <= threshold and size_ok:
                candidates.append((distance, track_a["track_id"], track_b["track_id"]))

    candidates.sort(key=lambda c: c[0])

    ids = [t["track_id"] for t in ordered]
    by_id = {t["track_id"]: t for t in ordered}
    uf = UnionFind(ids)

    used_as_predecessor = set()
    used_as_successor = set()

    for distance, id_a, id_b in candidates:
        if id_a in used_as_predecessor or id_b in used_as_successor:
            continue
        if uf.find(id_a) == uf.find(id_b):
            continue
        uf.union(id_a, id_b)
        used_as_predecessor.add(id_a)
        used_as_successor.add(id_b)
        print(
            f"[RoadGuard AI][Stage B] Stitching track {id_a} -> {id_b} "
            f"(motion-compensated distance={distance:.4f})"
        )

    merged: List[Dict[str, Any]] = []

    for group_ids in uf.groups():
        group_tracks = sorted((by_id[i] for i in group_ids), key=lambda t: t["first_frame"])

        if len(group_tracks) == 1:
            merged.append(group_tracks[0])
            continue

        base = group_tracks[0]
        combined = create_track_record(base["track_id"])
        combined["frames"] = []
        combined["confidences"] = []
        combined["centers"] = []
        combined["boxes"] = []
        combined["areas"] = []
        combined["frame_box_map"] = {}

        for t in group_tracks:
            combined["frames"].extend(t["frames"])
            combined["confidences"].extend(t["confidences"])
            combined["centers"].extend(t["centers"])
            combined["boxes"].extend(t["boxes"])
            combined["areas"].extend(t["areas"])
            combined["frame_box_map"].update(t["frame_box_map"])

        combined["frame_count"] = len(combined["frames"])
        combined["first_frame"] = group_tracks[0]["first_frame"]
        combined["last_frame"] = group_tracks[-1]["last_frame"]
        combined["first_center"] = group_tracks[0]["first_center"]
        combined["last_center"] = group_tracks[-1]["last_center"]
        combined["first_box"] = group_tracks[0]["first_box"]
        combined["last_box"] = group_tracks[-1]["last_box"]
        combined["max_area_ratio"] = max(t["max_area_ratio"] for t in group_tracks)

        # FIX: flatten each track's OWN source_track_ids (which may already
        # carry multiple raw IDs merged by Stage A / A2), instead of just
        # using each track's primary track_id. Otherwise IDs merged in
        # earlier stages silently disappear from the final id_map used
        # for video annotation.
        combined["source_track_ids"] = flatten_source_ids(group_tracks)

        merged.append(combined)

    return merged


# ==========================================================
# CREATE UNIQUE POTHOLE METADATA
# ==========================================================

def create_unique_pothole_metadata(tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output = []

    for index, track in enumerate(tracks, start=1):
        centers = track.get("centers", [])
        boxes = track.get("boxes", [])
        confidences = track.get("confidences", [])

        average_x = sum(c[0] for c in centers) / len(centers) if centers else 0.5
        average_y = sum(c[1] for c in centers) / len(centers) if centers else 0.5

        average_width = sum(b[2] - b[0] for b in boxes) / len(boxes) if boxes else 0.0
        average_height = sum(b[3] - b[1] for b in boxes) / len(boxes) if boxes else 0.0

        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        quality = track_quality(track)

        output.append({
            "pothole_id": index,
            "source_track_ids": track.get("source_track_ids", [track.get("track_id")]),
            "frame_count": quality["frame_count"],
            "visibility": round(quality["visibility"], 4),
            "average_confidence": round(average_confidence, 4),
            "center_normalized": {
                "x": round(average_x, 6),
                "y": round(average_y, 6),
            },
            "average_box": {
                "width": round(average_width, 6),
                "height": round(average_height, 6),
            },
            "max_area_ratio": round(safe_float(track.get("max_area_ratio", 0.0)), 6),
            "first_frame": track.get("first_frame"),
            "last_frame": track.get("last_frame"),
        })

    return output


# ==========================================================
# FULL ASSOCIATION PIPELINE
# ==========================================================

def associate_tracks_into_potholes(
    raw_track_records: Dict[int, Dict[str, Any]],
    fps: float,
) -> Dict[str, Any]:
    """
    Runs Stage 0 (lenient admission) -> Stage A (concurrent, high-IoU
    dedup) -> Stage A2 (concurrent, spatially-adjacent fragment merge)
    -> Stage B (motion-compensated sequential stitching) -> Stage C
    (final validation).

    Returns debug info plus the final unique_potholes list.
    """

    raw_tracks = list(raw_track_records.values())
    print(f"[RoadGuard AI] Raw ByteTrack IDs: {len(raw_tracks)}")

    # --- per-track debug dump, as requested ---
    for track in raw_tracks:
        quality = track_quality(track)
        trajectory_preview = track["centers"][:3] + (
            ["..."] if len(track["centers"]) > 3 else []
        )
        print(
            f"TRACK {track['track_id']}:\n"
            f"  frames = {quality['frame_count']}\n"
            f"  visibility = {quality['visibility']:.0%}\n"
            f"  avg_confidence = {quality['average_confidence']:.2f}\n"
            f"  median_confidence = {quality['median_confidence']:.2f}\n"
            f"  trajectory = {trajectory_preview}"
        )

    # Stage 0: lenient admission (drop pure single-frame noise only)
    candidate_tracks = [
        t for t in raw_tracks
        if t["frame_count"] >= CANDIDATE_MIN_FRAMES
        and (sum(t["confidences"]) / len(t["confidences"])) >= CANDIDATE_MIN_CONFIDENCE
    ]
    print(f"[RoadGuard AI] Candidate tracks after noise filter: {len(candidate_tracks)}")

    # Stage A: concurrent, high-IoU duplicates
    deduplicated = resolve_concurrent_duplicates(candidate_tracks)
    print(f"[RoadGuard AI] Tracks after concurrent-duplicate resolution: {len(deduplicated)}")

    # Stage A2: concurrent, spatially-adjacent fragments (static-camera case)
    spatially_merged = resolve_concurrent_spatial_proximity(deduplicated)
    print(f"[RoadGuard AI] Tracks after concurrent spatial proximity merging: {len(spatially_merged)}")

    # Stage B: motion-compensated sequential stitching
    stitched = stitch_fragmented_tracks(spatially_merged, fps)
    print(f"[RoadGuard AI] Tracks after motion-compensated stitching: {len(stitched)}")

    # Stage C: final validation, on the MERGED clusters
    dynamic_min_frames = max(MIN_TRACK_FRAMES, int(fps * 0.5))

    confirmed = []
    rejected = []

    for track in stitched:
        quality = track_quality(track)
        passes = (
            quality["frame_count"] >= dynamic_min_frames
            and quality["visibility"] >= MIN_TRACK_VISIBILITY
            and quality["average_confidence"] >= MIN_TRACK_CONFIDENCE
            and quality["median_confidence"] >= MIN_TRACK_CONFIDENCE
        )
        (confirmed if passes else rejected).append(track)

    print(f"[RoadGuard AI] Confirmed physical potholes: {len(confirmed)}")
    print(f"[RoadGuard AI] Rejected clusters (noise/too weak): {len(rejected)}")

    unique_potholes = create_unique_pothole_metadata(confirmed)

    # id_map: raw ByteTrack id -> final pothole number, for video annotation
    id_map: Dict[int, int] = {}
    for pothole in unique_potholes:
        for source_id in pothole["source_track_ids"]:
            id_map[source_id] = pothole["pothole_id"]

    return {
        "raw_track_count": len(raw_tracks),
        "candidate_track_count": len(candidate_tracks),
        "deduplicated_track_count": len(deduplicated),
        "spatially_merged_track_count": len(spatially_merged),
        "merged_track_count": len(stitched),
        "confirmed_track_count": len(confirmed),
        "rejected_track_count": len(rejected),
        "unique_potholes": unique_potholes,
        "pothole_count": len(unique_potholes),
        "track_id_to_pothole_id": id_map,
    }


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
    media_format: str = "forward_facing",
    panorama_image: Optional[str] = None,
) -> str:
    output_path = THREE_D_DATA_DIR / f"report_{report_id}.json"

    metadata = {
        "report_id": report_id,
        "media_type": media_type,
        "media_format": media_format,   # "equirectangular_360" | "forward_facing"
        "panorama_image": panorama_image,
        "pothole_count": pothole_count,
        "total_3d_detections": len(detections),
        "confidence": round(confidence, 4),
        "severity": severity,
        "detections": detections,
        "unique_potholes": unique_potholes or [],
    }

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)

    print(f"[RoadGuard AI] 3D metadata saved: {output_path}")
    return str(output_path)


# ==========================================================
# CREATE DETECTION OBJECT (for 3D sampling)
# ==========================================================

def create_detection_object(
    box, confidence: float, frame_number: int,
    frame_width: int, frame_height: int,
    track_id: Optional[int] = None, class_name: str = "pothole",
) -> Dict[str, Any]:
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
    area_ratio = (width * height) / max(frame_width * frame_height, 1)

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
        "bbox": {"x1": round(x1, 2), "y1": round(y1, 2), "x2": round(x2, 2), "y2": round(y2, 2)},
        "center": {"x": round(center_x, 2), "y": round(center_y, 2)},
        "normalized": {
            "x": round(normalized_x, 6), "y": round(normalized_y, 6),
            "width": round(normalized_width, 6), "height": round(normalized_height, 6),
        },
        "area_ratio": round(area_ratio, 8),
        "position_3d": position_3d,
    }


# ==========================================================
# IMAGE PROCESSING (unchanged logic — one detection = one pothole)
# ==========================================================

def process_image(image_path: str, report_id: Optional[int] = None) -> Dict[str, Any]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    frame_height, frame_width = image.shape[:2]

    aspect_ratio = frame_width / max(frame_height, 1)
    is_equirect = abs(aspect_ratio - 2.0) <= EQUIRECT_ASPECT_TOLERANCE
    media_format = "equirectangular_360" if is_equirect else "forward_facing"

    results = model.predict(source=image, conf=IMAGE_CONFIDENCE, verbose=False)

    detections: List[Dict[str, Any]] = []
    confidence_values: List[float] = []
    pothole_index = 0

    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            confidence = safe_float(
                box.conf[0].item() if hasattr(box.conf[0], "item") else box.conf[0]
            )
            if confidence < IMAGE_CONFIDENCE:
                continue

            coordinates = box.xyxy[0].tolist()
            detection = create_detection_object(
                box=coordinates, confidence=confidence, frame_number=0,
                frame_width=frame_width, frame_height=frame_height,
                track_id=pothole_index, class_name="pothole",
            )
            detections.append(detection)
            confidence_values.append(confidence)

            x1, y1, x2, y2 = map(int, coordinates)
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                image, f"Pothole {pothole_index + 1} {confidence:.2f}",
                (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2,
            )
            pothole_index += 1

    pothole_count = len(detections)
    average_confidence = (
        sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    )
    severity = calculate_severity(pothole_count, average_confidence)

    result_path = None
    panorama_path = None

    if report_id is not None:
        result_path = RESULTS_DIR / f"report_{report_id}_result.jpg"
        cv2.imwrite(str(result_path), image)

        if is_equirect:
            panorama_path = PANORAMA_DIR / f"report_{report_id}.jpg"
            cv2.imwrite(str(panorama_path), cv2.imread(str(image_path)))

        save_3d_metadata(
            report_id=report_id, detections=detections, pothole_count=pothole_count,
            confidence=average_confidence, severity=severity, media_type="image",
            unique_potholes=detections, media_format=media_format,
            panorama_image=(f"panorama/report_{report_id}.jpg" if panorama_path else None),
        )

    print(f"[RoadGuard AI] Image processing complete: {pothole_count} potholes")

    return {
        "pothole_count": pothole_count,
        "confidence": average_confidence,
        "severity": severity,
        "result_path": str(result_path) if result_path else None,
        "detections": detections,
        "unique_potholes": detections,
        "media_format": media_format,
    }


# ==========================================================
# VIDEO TRACKING PASS (shared by counting pass + annotation pass)
# ==========================================================

def run_tracking_pass(
    video_path: str,
    fps: float,
    frame_width: int,
    frame_height: int,
    sample_interval: int,
    writer: Optional[cv2.VideoWriter],
    id_map: Optional[Dict[int, int]] = None,
):
    """
    One full pass over the video with YOLO.track().

    If `writer` is provided, annotated frames are written.
    If `id_map` is provided, boxes are labeled with the FINAL pothole
    number (drawn only for confirmed potholes); otherwise raw ByteTrack
    IDs are drawn and every track is written into `track_records`.
    """

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    video_model = YOLO(str(MODEL_PATH))

    track_records: Dict[int, Dict[str, Any]] = {}
    detections: List[Dict[str, Any]] = []
    confidence_values: List[float] = []
    frame_number = 0

    while True:
        success, frame = capture.read()
        if not success:
            break
        frame_number += 1

        results = video_model.track(
            source=frame, persist=True, tracker="bytetrack.yaml",
            conf=VIDEO_CONFIDENCE, verbose=False,
        )

        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes

            for i in range(len(boxes)):
                box = boxes[i]
                confidence = safe_float(
                    box.conf[0].item() if hasattr(box.conf[0], "item") else box.conf[0]
                )
                if confidence < VIDEO_CONFIDENCE:
                    continue
                confidence_values.append(confidence)

                coordinates = box.xyxy[0].tolist()
                x1, y1, x2, y2 = map(float, coordinates)
                center_x, center_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0

                normalized_center = (center_x / max(frame_width, 1), center_y / max(frame_height, 1))
                normalized_box = (
                    x1 / max(frame_width, 1), y1 / max(frame_height, 1),
                    x2 / max(frame_width, 1), y2 / max(frame_height, 1),
                )
                area_ratio = ((x2 - x1) * (y2 - y1)) / max(frame_width * frame_height, 1)

                track_id = None
                if boxes.id is not None:
                    try:
                        track_id = safe_int(
                            boxes.id[i].item() if hasattr(boxes.id[i], "item") else boxes.id[i]
                        )
                    except Exception:
                        track_id = None

                if track_id is not None:
                    if track_id not in track_records:
                        track_records[track_id] = create_track_record(track_id)
                    track = track_records[track_id]

                    track["frames"].append(frame_number)
                    track["frame_count"] += 1
                    if track["first_frame"] is None:
                        track["first_frame"] = frame_number
                        track["first_center"] = normalized_center
                        track["first_box"] = normalized_box
                    track["last_frame"] = frame_number
                    track["last_center"] = normalized_center
                    track["last_box"] = normalized_box
                    track["confidences"].append(confidence)
                    track["centers"].append(normalized_center)
                    track["boxes"].append(normalized_box)
                    track["areas"].append(area_ratio)
                    track["frame_box_map"][frame_number] = normalized_box
                    track["max_area_ratio"] = max(track["max_area_ratio"], area_ratio)

                if frame_number % sample_interval == 0:
                    detections.append(create_detection_object(
                        box=coordinates, confidence=confidence, frame_number=frame_number,
                        frame_width=frame_width, frame_height=frame_height,
                        track_id=track_id, class_name="pothole",
                    ))

                if writer is not None:
                    pothole_label = None
                    if id_map is not None:
                        if track_id in id_map:
                            pothole_label = f"Pothole #{id_map[track_id]}"
                        else:
                            continue  # unconfirmed detection: don't draw it
                    else:
                        pothole_label = f"Pothole ID:{track_id}"

                    ix1, iy1, ix2, iy2 = map(int, coordinates)
                    cv2.rectangle(frame, (ix1, iy1), (ix2, iy2), (0, 255, 0), 2)
                    cv2.putText(
                        frame, f"{pothole_label} {confidence:.2f}",
                        (ix1, max(20, iy1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2,
                    )

        if writer is not None:
            writer.write(frame)

    capture.release()

    return {
        "track_records": track_records,
        "detections": detections,
        "confidence_values": confidence_values,
    }


# ==========================================================
# PROCESS VIDEO
# ==========================================================

def process_video(video_path: str, report_id: Optional[int] = None) -> Dict[str, Any]:
    print()
    print("=" * 70)
    print("[RoadGuard AI] STARTING VIDEO PROCESSING")
    print("=" * 70)
    print(f"[RoadGuard AI] Video: {video_path}")

    probe = cv2.VideoCapture(str(video_path))
    if not probe.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    fps = safe_float(probe.get(cv2.CAP_PROP_FPS), 30.0) or 30.0
    frame_width = safe_int(probe.get(cv2.CAP_PROP_FRAME_WIDTH), 640)
    frame_height = safe_int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT), 480)
    total_frames = safe_int(probe.get(cv2.CAP_PROP_FRAME_COUNT), 0)
    probe.release()

    duration_seconds = total_frames / fps if total_frames > 0 else 0
    aspect_ratio = frame_width / max(frame_height, 1)
    is_equirect = abs(aspect_ratio - 2.0) <= EQUIRECT_ASPECT_TOLERANCE
    media_format = "equirectangular_360" if is_equirect else "forward_facing"

    print(f"[RoadGuard AI] FPS: {fps:.2f}")
    print(f"[RoadGuard AI] Resolution: {frame_width}x{frame_height} (aspect {aspect_ratio:.2f})")
    print(f"[RoadGuard AI] Media format detected: {media_format}")
    print(f"[RoadGuard AI] Frames: {total_frames}  Duration: {duration_seconds:.2f}s")

    sample_interval = max(1, int(fps * THREE_D_SAMPLE_SECONDS))

    # ---- PASS 1: pure tracking pass (no video written) ----
    pass_1 = run_tracking_pass(
        video_path=video_path, fps=fps, frame_width=frame_width, frame_height=frame_height,
        sample_interval=sample_interval, writer=None, id_map=None,
    )

    association = associate_tracks_into_potholes(pass_1["track_records"], fps)

    pothole_count = association["pothole_count"]
    unique_potholes = association["unique_potholes"]
    detections = pass_1["detections"]
    confidence_values = pass_1["confidence_values"]

    final_confidence = (
        sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    )
    severity = calculate_severity(pothole_count, final_confidence)

    # ---- PASS 2: annotation pass with FINAL pothole numbers ----
    result_path = None
    if report_id is not None:
        result_path = RESULTS_DIR / f"report_{report_id}_result.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(result_path), fourcc, fps, (frame_width, frame_height))

        if TWO_PASS_VIDEO_ANNOTATION:
            print("[RoadGuard AI] Running annotation pass with final pothole IDs "
                  "(NOTE: relies on YOLO/ByteTrack being deterministic across "
                  "passes for the same input).")
            run_tracking_pass(
                video_path=video_path, fps=fps, frame_width=frame_width, frame_height=frame_height,
                sample_interval=sample_interval, writer=writer,
                id_map=association["track_id_to_pothole_id"],
            )
        else:
            run_tracking_pass(
                video_path=video_path, fps=fps, frame_width=frame_width, frame_height=frame_height,
                sample_interval=sample_interval, writer=writer, id_map=None,
            )
        writer.release()

    # Panorama frame extraction (real 360 support)
    panorama_path = None
    if report_id is not None and is_equirect:
        capture = cv2.VideoCapture(str(video_path))
        mid_frame_index = total_frames // 2 if total_frames > 0 else 0
        capture.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_index)
        success, mid_frame = capture.read()
        if success:
            panorama_path = PANORAMA_DIR / f"report_{report_id}.jpg"
            cv2.imwrite(str(panorama_path), mid_frame)
            print(f"[RoadGuard AI] Extracted representative 360° frame: {panorama_path}")
        capture.release()

    metadata_path = None
    if report_id is not None:
        metadata_path = save_3d_metadata(
            report_id=report_id, detections=detections, pothole_count=pothole_count,
            confidence=final_confidence, severity=severity, media_type="video",
            unique_potholes=unique_potholes, media_format=media_format,
            panorama_image=(f"panorama/report_{report_id}.jpg" if panorama_path else None),
        )

    print()
    print("=" * 70)
    print(f"[RoadGuard AI] FINAL UNIQUE POTHOLES: {pothole_count}")
    print(f"[RoadGuard AI] Average confidence: {final_confidence:.2%}")
    print(f"[RoadGuard AI] Severity: {severity}")
    print(f"[RoadGuard AI] 3D frame detections (NOT pothole count): {len(detections)}")
    print("=" * 70)
    print()

    return {
        "pothole_count": pothole_count,
        "confidence": final_confidence,
        "severity": severity,
        "result_path": str(result_path) if result_path is not None else None,

        "raw_track_count": association["raw_track_count"],
        "candidate_track_count": association["candidate_track_count"],
        "deduplicated_track_count": association["deduplicated_track_count"],
        "spatially_merged_track_count": association["spatially_merged_track_count"],
        "merged_track_count": association["merged_track_count"],
        "confirmed_track_count": association["confirmed_track_count"],
        "rejected_track_count": association["rejected_track_count"],

        "three_d_detection_count": len(detections),
        "detections": detections,
        "unique_potholes": unique_potholes,
        "metadata_path": metadata_path,
        "media_format": media_format,
    }


# ==========================================================
# PROCESS MEDIA DISPATCHER
# ==========================================================

def process_media_detection(report_id: int, media_path: str, media_type: str) -> Dict[str, Any]:
    media_type = (media_type or "").lower().strip()

    print()
    print("[RoadGuard AI] Processing media:")
    print(f"  Report ID: {report_id}")
    print(f"  Media type: {media_type}")
    print(f"  Media path: {media_path}")

    if media_type in {"image", "jpg", "jpeg", "png", "webp"}:
        result = process_image(image_path=media_path, report_id=report_id)
    elif media_type in {"video", "mp4", "avi", "mov", "mkv", "webm"}:
        result = process_video(video_path=media_path, report_id=report_id)
    else:
        raise ValueError(f"Unsupported media type: {media_type}")

    print(f"[RoadGuard AI] Report #{report_id} processed successfully.")
    print(f"[RoadGuard AI] Potholes detected: {result.get('pothole_count', 0)}")

    return result