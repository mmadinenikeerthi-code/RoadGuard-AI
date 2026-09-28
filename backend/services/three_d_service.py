# ==========================================================
# backend/services/three_d_service.py
# ROADGUARD AI - 3D SCENE SERVICE
# ==========================================================

from typing import List, Dict, Any
from pathlib import Path


# ==========================================================
# PATHS
# ==========================================================

SERVICE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SERVICE_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

RESULTS_DIR = PROJECT_ROOT / "results"
PHOTOGRAMMETRY_DIR = RESULTS_DIR / "photogrammetry"
THREE_D_DATA_DIR = RESULTS_DIR / "3d_data"


# ==========================================================
# SEVERITY
# ==========================================================

SEVERITY_COLORS = {
    "LOW": "#22c55e",
    "MODERATE": "#f59e0b",
    "HIGH": "#f97316",
    "CRITICAL": "#ef4444",
}


def get_severity_color(severity: str) -> str:
    return SEVERITY_COLORS.get(
        str(severity or "LOW").upper(),
        "#64748b",
    )


# ==========================================================
# SAFE HELPERS
# ==========================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_report_value(report: Any, key: str, default=None):
    if isinstance(report, dict):
        return report.get(key, default)

    return getattr(report, key, default)


# ==========================================================
# RECONSTRUCTION DISCOVERY
# ==========================================================

def get_reconstruction_paths(report_id: int) -> Dict[str, Any]:
    """
    Find reconstruction outputs without pretending that they
    exist when they do not.
    """

    report_dir = PHOTOGRAMMETRY_DIR / f"report_{report_id}"

    candidates = [
        report_dir / "dense" / "roadguard-road.ply",
        report_dir / "dense" / "fused.ply",
        report_dir / "roadguard-road.ply",
        report_dir / "roadguard-points.ply",
    ]

    mesh_path = None
    pointcloud_path = None

    for path in candidates:
        if path.exists():
            if path.name in {
                "roadguard-road.ply",
                "fused.ply",
            }:
                mesh_path = path
                break

            if path.name == "roadguard-points.ply":
                pointcloud_path = path

    metadata_candidates = [
        report_dir / "roadguard_3d.json",
        report_dir / "metadata.json",
        THREE_D_DATA_DIR / f"report_{report_id}.json",
    ]

    metadata_path = None

    for path in metadata_candidates:
        if path.exists():
            metadata_path = path
            break

    return {
        "report_dir": report_dir,
        "mesh_path": mesh_path,
        "pointcloud_path": pointcloud_path,
        "metadata_path": metadata_path,
        "mesh_available": mesh_path is not None,
        "pointcloud_available": pointcloud_path is not None,
        "metadata_available": metadata_path is not None,
    }


# ==========================================================
# RESULTS URL
#
# The served static root is RESULTS_DIR ("/results"). The
# reconstructed PLY can live either directly in
# results/photogrammetry/report_<id>/ or in its dense/
# subfolder, so the URL must be derived from the real file
# location instead of being hard-coded.
# ==========================================================

def build_results_url(path: Any) -> Any:

    if not path:
        return None

    try:

        relative = (
            Path(path)
            .resolve()
            .relative_to(RESULTS_DIR.resolve())
        )

    except (ValueError, OSError):

        return None

    return "/results/" + relative.as_posix()


# ==========================================================
# DETECTION RECORD NORMALISATION
#
# results/3d_data/report_<id>.json is written by
# backend/services/detection_service.py and stores nested
# objects:
#
#   detections[]       -> per-frame samples
#       {frame, track_id, confidence,
#        bbox{x1,y1,x2,y2}, center{x,y},
#        normalized{x,y,width,height}, position_3d{x,y,z}}
#
#   unique_potholes[]  -> one entry per pothole
#       {pothole_id, average_confidence,
#        center_normalized{x,y}, average_box{width,height},
#        visibility, frame_count, ...}
#
# Simpler/older metadata used flat keys (center_x, center_y,
# width, height, confidence). Both shapes are accepted here
# and returned with the flat keys the viewer consumes.
#
# The viewer maps centre coordinates onto a 0..1000 scale
# (frontend/js/three_d.js -> renderPotholeMarkers), so
# normalised 0..1 values are scaled by 1000.
# ==========================================================

def pick_first(mapping: Any, *keys: str) -> Any:

    for key in keys:

        if (
            isinstance(mapping, dict)
            and mapping.get(key) is not None
        ):

            return mapping[key]

    return None


def normalise_detection_record(
    detection: Dict[str, Any],
    index: int,
    fallback_confidence: float,
) -> Dict[str, Any]:

    center = detection.get("center") or {}
    normalized = detection.get("normalized") or {}
    center_normalized = (
        detection.get("center_normalized") or {}
    )
    average_box = detection.get("average_box") or {}

    pothole_id = pick_first(
        detection,
        "pothole_id",
        "id",
        "track_id",
    )

    if pothole_id is None:
        pothole_id = index + 1

    confidence_value = pick_first(
        detection,
        "confidence",
        "average_confidence",
        "avg_confidence",
    )

    if confidence_value is None:
        confidence_value = fallback_confidence

    center_x = pick_first(detection, "center_x", "x")

    if center_x is None:
        center_x = center.get("x")

    if center_x is None and center_normalized.get("x") is not None:
        center_x = safe_float(center_normalized.get("x")) * 1000

    if center_x is None and normalized.get("x") is not None:
        center_x = safe_float(normalized.get("x")) * 1000

    center_y = pick_first(detection, "center_y", "y")

    if center_y is None:
        center_y = center.get("y")

    if center_y is None and center_normalized.get("y") is not None:
        center_y = safe_float(center_normalized.get("y")) * 1000

    if center_y is None and normalized.get("y") is not None:
        center_y = safe_float(normalized.get("y")) * 1000

    width = pick_first(detection, "width")

    if width is None:
        width = average_box.get("width")

    if width is None:
        width = normalized.get("width")

    height = pick_first(detection, "height")

    if height is None:
        height = average_box.get("height")

    if height is None:
        height = normalized.get("height")

    return {
        "pothole_id": pothole_id,
        "confidence": safe_float(
            confidence_value,
            fallback_confidence,
        ),
        "center_x": safe_float(center_x, 0),
        "center_y": safe_float(center_y, 0),
        "width": safe_float(width, 0),
        "height": safe_float(height, 0),
        "position_3d": detection.get("position_3d"),
        "frame_count": detection.get("frame_count"),
        "visibility": detection.get("visibility"),
    }


# ==========================================================
# REPORT -> 3D OBJECT
# ==========================================================

def build_3d_object(
    report: Any,
    index: int = 0,
    base_latitude: float = None,
    base_longitude: float = None,
) -> Dict[str, Any]:

    latitude = safe_float(
        get_report_value(report, "latitude", 0)
    )

    longitude = safe_float(
        get_report_value(report, "longitude", 0)
    )

    pothole_count = get_report_value(
        report,
        "pothole_count",
        get_report_value(report, "potholes", 0),
    )

    try:
        pothole_count = int(pothole_count or 0)
    except (ValueError, TypeError):
        pothole_count = 0

    severity = str(
        get_report_value(
            report,
            "severity",
            "LOW",
        )
    ).upper()

    confidence = safe_float(
        get_report_value(
            report,
            "confidence",
            0,
        )
    )

    location_name = get_report_value(
        report,
        "location_name",
        "Unknown Location",
    )

    if base_latitude is None:
        base_latitude = latitude

    if base_longitude is None:
        base_longitude = longitude

    x = (longitude - base_longitude) * 10000
    z = (latitude - base_latitude) * 10000

    if abs(x) < 0.001 and abs(z) < 0.001:
        x = index * 2.5

    return {
        "id": get_report_value(
            report,
            "id",
            index + 1,
        ),
        "latitude": latitude,
        "longitude": longitude,
        "x": round(x, 3),
        "y": 0,
        "z": round(z, 3),
        "pothole_count": pothole_count,
        "severity": severity,
        "color": get_severity_color(severity),
        "location_name": location_name,
        "confidence": confidence,
    }


# ==========================================================
# SCENE
# ==========================================================

def build_3d_scene(reports: List[Any]) -> Dict[str, Any]:

    if not reports:
        return {
            "success": True,
            "total_objects": 0,
            "objects": [],
            "message": "No reports available.",
        }

    first = reports[0]

    base_latitude = safe_float(
        get_report_value(first, "latitude", 0)
    )

    base_longitude = safe_float(
        get_report_value(first, "longitude", 0)
    )

    objects = []

    for index, report in enumerate(reports):

        try:
            objects.append(
                build_3d_object(
                    report,
                    index,
                    base_latitude,
                    base_longitude,
                )
            )

        except Exception as error:
            print(
                f"[3D] Failed to build object: {error}"
            )

    return {
        "success": True,
        "total_objects": len(objects),
        "objects": objects,
        "message": "3D report data loaded.",
    }


# ==========================================================
# SUMMARY
# ==========================================================

def get_3d_summary(
    reports: List[Any],
) -> Dict[str, Any]:

    scene = build_3d_scene(reports)

    objects = scene.get("objects", [])

    return {
        "success": True,
        "total_locations": len(objects),
        "total_potholes": sum(
            int(obj.get("pothole_count", 0))
            for obj in objects
        ),
        "critical": sum(
            1 for obj in objects
            if obj.get("severity") == "CRITICAL"
        ),
        "high": sum(
            1 for obj in objects
            if obj.get("severity") == "HIGH"
        ),
        "moderate": sum(
            1 for obj in objects
            if obj.get("severity") == "MODERATE"
        ),
        "low": sum(
            1 for obj in objects
            if obj.get("severity") == "LOW"
        ),
    }


# ==========================================================
# IMMERSIVE ROAD SCENE
# ==========================================================

def build_immersive_road_scene(
    report: Any,
    metadata: Dict[str, Any],
    metadata_source: str = "",
) -> Dict[str, Any]:

    report_id = get_report_value(
        report,
        "id",
        None,
    )

    media_type = str(
        get_report_value(
            report,
            "media_type",
            "unknown",
        )
    ).lower()

    media_path = get_report_value(
        report,
        "media_path",
        "",
    )

    result_path = get_report_value(
        report,
        "result_path",
        "",
    )

    pothole_count = get_report_value(
        report,
        "pothole_count",
        0,
    )

    severity = str(
        get_report_value(
            report,
            "severity",
            "LOW",
        )
    ).upper()

    confidence = safe_float(
        get_report_value(
            report,
            "confidence",
            0,
        )
    )

    latitude = safe_float(
        get_report_value(
            report,
            "latitude",
            0,
        )
    )

    longitude = safe_float(
        get_report_value(
            report,
            "longitude",
            0,
        )
    )

    location_name = get_report_value(
        report,
        "location_name",
        "Unknown Location",
    )

    detections = metadata.get(
        "detections",
        [],
    )

    unique_potholes = metadata.get(
        "unique_potholes",
        [],
    )

    # Photogrammetry metadata (roadguard_3d.json) stores its
    # pothole list under "potholes".
    reconstruction_potholes = metadata.get(
        "potholes",
        [],
    )

    if unique_potholes:

        marker_source = "unique_potholes"

    elif detections:

        # Older reports have no deduplicated pothole list, so the
        # per-frame samples are shown instead of inventing one.
        marker_source = "detections"

    elif reconstruction_potholes:

        marker_source = "reconstruction_potholes"

    else:

        marker_source = "none"

    source_potholes = (
        unique_potholes
        or detections
        or reconstruction_potholes
        or []
    )

    paths = get_reconstruction_paths(report_id)

    # ------------------------------------------------------
    # WARNINGS
    #
    # These describe what is genuinely missing for this
    # report. Nothing is invented; the frontend shows them
    # verbatim so the user knows why a layer is empty.
    # ------------------------------------------------------

    warnings = []

    if not metadata:

        warnings.append(
            "Per-pothole 3D geometry is unavailable: no metadata "
            "file was found for this report (expected "
            "results/3d_data/report_<id>.json)."
        )

    elif not source_potholes:

        warnings.append(
            "Detection metadata was found for this report but it "
            "contains no pothole markers."
        )

    if not (
        paths["mesh_available"]
        or paths["pointcloud_available"]
    ):

        warnings.append(
            "No photogrammetry reconstruction exists for this "
            "report yet. Use \"Build 3D Model\" to create one."
        )

    if result_path:

        result_name = Path(str(result_path)).name

        if not (
            Path(str(result_path)).exists()
            or (RESULTS_DIR / result_name).exists()
        ):

            warnings.append(
                "The annotated result file for this report "
                f"({result_name}) is not present on disk."
            )

    markers = []

    for index, detection in enumerate(source_potholes):

        if not isinstance(detection, dict):
            continue

        severity_value = str(
            detection.get(
                "severity",
                severity,
            )
        ).upper()

        record = normalise_detection_record(
            detection,
            index,
            confidence,
        )

        marker = {
            "pothole_id": record["pothole_id"],

            "severity": severity_value,

            "confidence": record["confidence"],

            "center_x": record["center_x"],

            "center_y": record["center_y"],

            "width": record["width"],

            "height": record["height"],

            "position_3d": record["position_3d"],

            "color": get_severity_color(
                severity_value,
            ),

            "location": {
                "latitude": latitude,
                "longitude": longitude,
            },
        }

        markers.append(marker)

    return {
        "success": True,

        "viewer": {
            "mode": (
                "RECONSTRUCTION"
                if paths["mesh_available"]
                or paths["pointcloud_available"]
                else "SYNTHETIC_FALLBACK"
            ),

            "is_360": bool(
                metadata.get(
                    "is_360",
                    False,
                )
            ),

            "reconstruction_available": (
                paths["mesh_available"]
                or paths["pointcloud_available"]
            ),

            "mesh_available": paths[
                "mesh_available"
            ],

            "pointcloud_available": paths[
                "pointcloud_available"
            ],

            "metadata_source": (
                metadata_source
                if metadata_source
                else "none"
            ),

            "metadata_available": bool(
                metadata
            ),
        },

        # Real, computed reasons why a layer may be empty.
        "warnings": warnings,

        "report": {
            "id": report_id,
            "media_type": media_type,
            "media_path": media_path,
            "result_path": result_path,
            "pothole_count": pothole_count,
            "severity": severity,
            "confidence": confidence,
            "latitude": latitude,
            "longitude": longitude,
            "location_name": location_name,
        },

        "reconstruction": {
            # URLs are derived from the real file locations so
            # results/photogrammetry/report_<id>/roadguard-road.ply
            # and results/photogrammetry/report_<id>/dense/*.ply
            # are both served correctly.
            "mesh_url": build_results_url(
                paths["mesh_path"]
            ),

            "pointcloud_url": build_results_url(
                paths["pointcloud_path"]
            ),

            "metadata_url": build_results_url(
                paths["metadata_path"]
            ),
        },

        "potholes": markers,

        "total_potholes": len(markers),

        "metadata": {
            "total_sampled_detections": len(
                detections
            ),
            "unique_potholes": len(
                unique_potholes
            ),
            "marker_source": marker_source,
            "recorded_potholes": pothole_count,
            "metadata_source": (
                metadata_source
                if metadata_source
                else "none"
            ),
        },
    }


def get_3d_scene_service(
    reports: List[Any],
) -> Dict[str, Any]:

    return build_3d_scene(reports)