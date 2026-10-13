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

def _inspect_ply_header(path: Path) -> Dict[str, Any]:
    """
    Read PLY header to count vertices and faces without loading point data into RAM.
    Works for both ASCII and binary PLYs.
    """
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return {"vertices": 0, "faces": 0, "is_mesh": False, "is_pointcloud": False}

    vertices = 0
    faces = 0
    try:
        with open(path, "rb") as f:
            for _ in range(40):
                line = f.readline().decode("latin-1", errors="ignore").strip()
                if line.startswith("element vertex"):
                    parts = line.split()
                    if len(parts) >= 3:
                        vertices = int(parts[2])
                elif line.startswith("element face"):
                    parts = line.split()
                    if len(parts) >= 3:
                        faces = int(parts[2])
                elif line == "end_header":
                    break
    except Exception:
        pass

    return {
        "vertices": vertices,
        "faces": faces,
        "is_mesh": faces > 0,
        "is_pointcloud": vertices > 0 and faces == 0,
    }


def get_reconstruction_paths(report_id: int) -> Dict[str, Any]:
    """
    Find real COLMAP reconstruction outputs without pretending that they
    exist when they do not. Distinguishes:
        NOT_STARTED
        FAILED
        SPARSE_ONLY
        DENSE_POINT_CLOUD
        MESH_AVAILABLE
    """

    report_dir = PHOTOGRAMMETRY_DIR / f"report_{report_id}"
    colmap_dir = report_dir / "colmap"

    # Mesh candidates in priority order (only valid if faces > 0)
    mesh_candidates = [
        report_dir / "roadguard-road.ply",
        colmap_dir / "delaunay_mesh.ply",
        report_dir / "dense" / "meshed-poisson.ply",
        report_dir / "dense" / "meshed-delaunay.ply",
        colmap_dir / "dense" / "meshed-poisson.ply",
        colmap_dir / "dense" / "meshed-delaunay.ply",
        report_dir / "dense" / "roadguard-road.ply",
        report_dir / "roadguard-road.obj",
        report_dir / "roadguard-road.glb",
        report_dir / "roadguard-road.gltf",
        report_dir / "dense" / "model.obj",
        report_dir / "dense" / "model.glb",
        report_dir / "dense" / "model.gltf",
        report_dir / "model.obj",
        report_dir / "model.glb",
        report_dir / "model.gltf",
    ]

    dense_cloud_candidates = [
        report_dir / "dense" / "fused.ply",
        colmap_dir / "dense" / "fused.ply",
    ]

    sparse_cloud_candidates = [
        report_dir / "roadguard-points.ply",
        colmap_dir / "sparse_points.ply",
        report_dir / "sparse" / "points3D.ply",
    ]

    mesh_path = None
    vertex_count = 0
    face_count = 0

    for path in mesh_candidates:
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            if path.suffix.lower() == ".ply":
                header = _inspect_ply_header(path)
                if header["is_mesh"]:
                    mesh_path = path
                    vertex_count = header["vertices"]
                    face_count = header["faces"]
                    break
            else:
                mesh_path = path
                break

    dense_pointcloud_path = None
    for path in dense_cloud_candidates:
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            header = _inspect_ply_header(path)
            if header["vertices"] > 0:
                dense_pointcloud_path = path
                if not vertex_count:
                    vertex_count = header["vertices"]
                break

    pointcloud_path = None
    for path in sparse_cloud_candidates:
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            header = _inspect_ply_header(path)
            if header["vertices"] > 0:
                pointcloud_path = path
                if not vertex_count:
                    vertex_count = header["vertices"]
                break

    # If roadguard-road.ply has 0 faces, it acts as a point cloud
    if not pointcloud_path and not dense_pointcloud_path:
        road_ply = report_dir / "roadguard-road.ply"
        if road_ply.exists() and road_ply.is_file() and road_ply.stat().st_size > 0:
            header = _inspect_ply_header(road_ply)
            if header["vertices"] > 0 and header["faces"] == 0:
                pointcloud_path = road_ply
                if not vertex_count:
                    vertex_count = header["vertices"]

    metadata_candidates = [
        report_dir / "roadguard_3d.json",
        report_dir / "metadata.json",
        THREE_D_DATA_DIR / f"report_{report_id}.json",
    ]

    metadata_path = None
    for path in metadata_candidates:
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            metadata_path = path
            break

    # Determine accurate status
    if mesh_path is not None:
        status = "MESH_AVAILABLE"
    elif dense_pointcloud_path is not None:
        status = "DENSE_POINT_CLOUD"
    elif pointcloud_path is not None:
        status = "SPARSE_ONLY"
    elif report_dir.exists() and (colmap_dir.exists() or (report_dir / "frames").exists()):
        status = "FAILED"
    else:
        status = "NOT_STARTED"

    reconstruction_available = status in ("MESH_AVAILABLE", "DENSE_POINT_CLOUD", "SPARSE_ONLY")

    return {
        "report_dir": report_dir,
        "mesh_path": mesh_path,
        "pointcloud_path": pointcloud_path or dense_pointcloud_path,
        "dense_pointcloud_path": dense_pointcloud_path,
        "metadata_path": metadata_path,
        "mesh_available": mesh_path is not None,
        "pointcloud_available": (pointcloud_path is not None or dense_pointcloud_path is not None),
        "metadata_available": metadata_path is not None,
        "status": status,
        "reconstruction_available": reconstruction_available,
        "vertex_count": vertex_count,
        "face_count": face_count,
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
    track_positions_map: Dict[Any, Any] = None,
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

    position_3d = detection.get("position_3d")
    if position_3d is None and track_positions_map:
        source_tracks = detection.get("source_track_ids") or []
        if isinstance(source_tracks, (list, tuple)):
            for tid in source_tracks:
                if tid in track_positions_map:
                    position_3d = track_positions_map[tid]
                    break
        tid = detection.get("track_id")
        if position_3d is None and tid in track_positions_map:
            position_3d = track_positions_map[tid]

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
        "position_3d": position_3d,
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

    if not paths["reconstruction_available"]:
        if paths["status"] == "FAILED":
            warnings.append(
                "COLMAP reconstruction failed for this report."
            )
        else:
            warnings.append(
                "COLMAP reconstruction not started or not available for this report."
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

    track_positions_map = {
        d.get("track_id"): d.get("position_3d")
        for d in detections
        if isinstance(d, dict) and d.get("track_id") and d.get("position_3d")
    }

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
            track_positions_map=track_positions_map,
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
                if paths["reconstruction_available"]
                else "UNAVAILABLE"
            ),

            "reconstruction_status": paths["status"],

            "is_360": bool(
                metadata.get(
                    "is_360",
                    False,
                )
            ),

            "reconstruction_available": paths["reconstruction_available"],

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
            "status": paths["status"],
            "vertex_count": paths["vertex_count"],
            "face_count": paths["face_count"],
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