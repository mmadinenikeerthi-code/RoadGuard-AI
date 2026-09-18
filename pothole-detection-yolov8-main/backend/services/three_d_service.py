# ==========================================================
# backend/services/three_d_service.py
# ROADGUARD AI - 3D + IMMERSIVE ROAD VIEW SERVICE
# ==========================================================

from typing import List, Dict, Any
from pathlib import Path


# ==========================================================
# SEVERITY COLORS
# ==========================================================

def get_severity_color(severity: str) -> str:
    colors = {
        "LOW": "#22c55e",
        "MODERATE": "#f59e0b",
        "HIGH": "#f97316",
        "CRITICAL": "#ef4444",
    }

    return colors.get(
        str(severity).upper(),
        "#64748b"
    )


# ==========================================================
# CALCULATE HEIGHT
# ==========================================================

def calculate_height(pothole_count: int) -> float:
    try:
        pothole_count = int(pothole_count or 0)
    except (ValueError, TypeError):
        pothole_count = 0

    if pothole_count <= 0:
        return 1.0

    return min(
        max(pothole_count * 0.25, 1.0),
        6.0
    )


# ==========================================================
# SAFE FLOAT
# ==========================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ==========================================================
# GET REPORT VALUE
# ==========================================================

def get_report_value(
    report: Any,
    key: str,
    default=None
):
    if isinstance(report, dict):
        return report.get(key, default)

    return getattr(report, key, default)


# ==========================================================
# BUILD SINGLE 3D OBJECT
# ==========================================================

def build_3d_object(
    report: Any,
    index: int = 0,
    base_latitude: float = None,
    base_longitude: float = None
) -> Dict[str, Any]:

    latitude = safe_float(
        get_report_value(report, "latitude")
    )

    longitude = safe_float(
        get_report_value(report, "longitude")
    )

    pothole_count = get_report_value(
        report,
        "pothole_count",
        get_report_value(report, "potholes", 0)
    )

    try:
        pothole_count = int(pothole_count or 0)
    except (ValueError, TypeError):
        pothole_count = 0

    severity = str(
        get_report_value(
            report,
            "severity",
            "LOW"
        )
    ).upper()

    location_name = get_report_value(
        report,
        "location_name",
        f"Road Location {index + 1}"
    )

    confidence = safe_float(
        get_report_value(
            report,
            "confidence",
            0
        )
    )

    if base_latitude is None:
        base_latitude = latitude

    if base_longitude is None:
        base_longitude = longitude

    x = (
        longitude - base_longitude
    ) * 10000

    z = (
        latitude - base_latitude
    ) * 10000

    if x == 0 and z == 0:
        x = index * 2

    return {
        "id": get_report_value(
            report,
            "id",
            index + 1
        ),

        "latitude": latitude,
        "longitude": longitude,

        "x": round(x, 2),
        "y": 0,
        "z": round(z, 2),

        "height": calculate_height(
            pothole_count
        ),

        "pothole_count": pothole_count,

        "severity": severity,

        "color": get_severity_color(
            severity
        ),

        "location_name": location_name,

        "confidence": confidence
    }


# ==========================================================
# BUILD 3D SCENE
# ==========================================================

def build_3d_scene(
    reports: List[Any]
) -> Dict[str, Any]:

    objects = []

    if not reports:
        return {
            "success": True,
            "total_objects": 0,
            "objects": [],
            "message": "No potholes detected in this analysis."
        }

    first_report = reports[0]

    base_latitude = safe_float(
        get_report_value(
            first_report,
            "latitude"
        )
    )

    base_longitude = safe_float(
        get_report_value(
            first_report,
            "longitude"
        )
    )

    for index, report in enumerate(reports):

        try:
            object_3d = build_3d_object(
                report=report,
                index=index,
                base_latitude=base_latitude,
                base_longitude=base_longitude
            )

            objects.append(object_3d)

        except Exception as error:
            print(
                f"[3D] Object error: {error}"
            )

    return {
        "success": True,

        "total_objects": len(objects),

        "objects": objects,

        "message": (
            "No potholes detected in this analysis."
            if not objects
            else "Detection reports loaded."
        )
    }


# ==========================================================
# 3D SUMMARY
# ==========================================================

def get_3d_summary(
    reports: List[Any]
) -> Dict[str, Any]:

    scene = build_3d_scene(reports)

    objects = scene.get(
        "objects",
        []
    )

    total_potholes = sum(
        obj.get("pothole_count", 0)
        for obj in objects
    )

    critical = sum(
        1
        for obj in objects
        if obj.get("severity") == "CRITICAL"
    )

    high = sum(
        1
        for obj in objects
        if obj.get("severity") == "HIGH"
    )

    moderate = sum(
        1
        for obj in objects
        if obj.get("severity") == "MODERATE"
    )

    low = sum(
        1
        for obj in objects
        if obj.get("severity") == "LOW"
    )

    return {
        "success": True,

        "total_locations": len(objects),

        "total_potholes": total_potholes,

        "critical": critical,
        "critical_hotspots": critical,

        "high": high,

        "moderate": moderate,

        "low": low
    }


# ==========================================================
# IMMERSIVE ROAD SCENE
#
# IMPORTANT:
# A normal forward-facing video is NOT a true 360° video.
#
# This endpoint prepares the media + detection metadata
# for the frontend immersive viewer.
#
# If actual 360° media is provided later, the frontend
# can display it as an equirectangular panorama.
# ==========================================================

def build_immersive_road_scene(
    report: Any,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:

    report_id = get_report_value(
        report,
        "id",
        None
    )

    media_type = str(
        get_report_value(
            report,
            "media_type",
            "unknown"
        )
    ).lower()

    media_path = get_report_value(
        report,
        "media_path",
        ""
    )

    result_path = get_report_value(
        report,
        "result_path",
        ""
    )

    pothole_count = get_report_value(
        report,
        "pothole_count",
        0
    )

    severity = str(
        get_report_value(
            report,
            "severity",
            "LOW"
        )
    ).upper()

    confidence = safe_float(
        get_report_value(
            report,
            "confidence",
            0
        )
    )

    latitude = safe_float(
        get_report_value(
            report,
            "latitude",
            0
        )
    )

    longitude = safe_float(
        get_report_value(
            report,
            "longitude",
            0
        )
    )

    location_name = get_report_value(
        report,
        "location_name",
        "Unknown"
    )

    # ------------------------------------------------------
    # Detection metadata
    # ------------------------------------------------------

    detections = metadata.get(
        "detections",
        []
    )

    unique_potholes = metadata.get(
        "unique_potholes",
        []
    )

    frame_width = metadata.get(
        "frame_width",
        0
    )

    frame_height = metadata.get(
        "frame_height",
        0
    )

    fps = metadata.get(
        "fps",
        0
    )

    duration = metadata.get(
        "duration",
        0
    )

    # ------------------------------------------------------
    # Determine viewer mode
    # ------------------------------------------------------
    #
    # We do NOT claim a normal video is real 360°.
    #

    is_true_360 = bool(
        metadata.get(
            "is_360",
            False
        )
    )

    if is_true_360:

        viewer_mode = "360_PANORAMA"

        viewer_description = (
            "True 360-degree panoramic media. "
            "Drag to look around the complete scene."
        )

    else:

        viewer_mode = "IMMERSIVE_RECONSTRUCTION"

        viewer_description = (
            "Immersive road visualization generated "
            "from available road media. "
            "The source media is not a true 360-degree "
            "camera recording."
        )

    # ------------------------------------------------------
    # Build pothole markers
    # ------------------------------------------------------

    pothole_markers = []

    source_potholes = (
        unique_potholes
        if unique_potholes
        else detections
    )

    for index, detection in enumerate(
        source_potholes
    ):

        if not isinstance(
            detection,
            dict
        ):
            continue

        marker = {
            "id": detection.get(
                "id",
                detection.get(
                    "track_id",
                    index + 1
                )
            ),

            "label": (
                f"Pothole #{index + 1}"
            ),

            "confidence": safe_float(
                detection.get(
                    "confidence",
                    detection.get(
                        "avg_confidence",
                        confidence
                    )
                )
            ),

            "severity": str(
                detection.get(
                    "severity",
                    severity
                )
            ).upper(),

            "x": safe_float(
                detection.get(
                    "center_x",
                    detection.get(
                        "x",
                        0
                    )
                )
            ),

            "y": safe_float(
                detection.get(
                    "center_y",
                    detection.get(
                        "y",
                        0
                    )
                )
            ),

            "width": safe_float(
                detection.get(
                    "width",
                    0
                )
            ),

            "height": safe_float(
                detection.get(
                    "height",
                    0
                )
            )
        }

        marker["color"] = get_severity_color(
            marker["severity"]
        )

        pothole_markers.append(
            marker
        )

    # ------------------------------------------------------
    # Return immersive scene
    # ------------------------------------------------------

    return {

        "success": True,

        "viewer": {
            "mode": viewer_mode,

            "is_360": is_true_360,

            "controls": {
                "mouse_drag": True,
                "horizontal_rotation": True,
                "vertical_rotation": True,
                "zoom": True
            },

            "description": viewer_description
        },

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

            "location_name": location_name
        },

        "media": {

            "source": media_path,

            "result": result_path,

            "frame_width": frame_width,

            "frame_height": frame_height,

            "fps": fps,

            "duration": duration
        },

        "potholes": pothole_markers,

        "total_potholes": len(
            pothole_markers
        ),

        "metadata": {

            "total_sampled_detections": len(
                detections
            ),

            "unique_potholes": len(
                unique_potholes
            )
        }
    }


# ==========================================================
# GET 3D SCENE SERVICE
# ==========================================================

def get_3d_scene_service(
    reports: List[Any]
) -> Dict[str, Any]:

    return build_3d_scene(
        reports
    )