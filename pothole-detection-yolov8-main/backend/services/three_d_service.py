# ==========================================================
# backend/services/three_d_service.py
# ROADGUARD AI - 3D VISUALIZATION SERVICE
# ==========================================================

from typing import List, Dict, Any


# ==========================================================
# SEVERITY COLORS
# ==========================================================

def get_severity_color(severity: str) -> str:

    colors = {

        "LOW": "#22c55e",

        "MODERATE": "#f59e0b",

        "HIGH": "#f97316",

        "CRITICAL": "#ef4444"

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

        pothole_count = int(
            pothole_count or 0
        )

    except (ValueError, TypeError):

        pothole_count = 0


    if pothole_count <= 0:

        return 1.0


    return min(

        max(
            pothole_count * 0.25,
            1.0
        ),

        6.0

    )


# ==========================================================
# NORMALIZE VALUE
# ==========================================================

def safe_float(value, default=0.0):

    try:

        return float(value)

    except (ValueError, TypeError):

        return default


# ==========================================================
# GET REPORT VALUES
# ==========================================================

def get_report_value(
    report: Any,
    key: str,
    default=None
):

    if isinstance(report, dict):

        return report.get(
            key,
            default
        )


    return getattr(
        report,
        key,
        default
    )


# ==========================================================
# BUILD SINGLE 3D OBJECT
# ==========================================================

def build_3d_object(
    report: Any,
    index: int = 0,
    base_latitude: float = None,
    base_longitude: float = None
) -> Dict[str, Any]:


    # ======================================================
    # GET ORIGINAL DATA
    # ======================================================

    latitude = safe_float(
        get_report_value(
            report,
            "latitude"
        )
    )


    longitude = safe_float(
        get_report_value(
            report,
            "longitude"
        )
    )


    pothole_count = get_report_value(
        report,
        "pothole_count",
        get_report_value(
            report,
            "potholes",
            0
        )
    )


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


    # ======================================================
    # CONVERT POTHOLE COUNT
    # ======================================================

    try:

        pothole_count = int(
            pothole_count or 0
        )

    except (ValueError, TypeError):

        pothole_count = 0


    # ======================================================
    # CREATE 3D X / Z COORDINATES
    # ======================================================

    if base_latitude is None:

        base_latitude = latitude


    if base_longitude is None:

        base_longitude = longitude


    # Convert GPS differences into visible 3D positions
    #
    # Multiplying makes small latitude/longitude differences
    # visible inside the Three.js scene.

    x = (
        longitude - base_longitude
    ) * 10000


    z = (
        latitude - base_latitude
    ) * 10000


    # If coordinates are too close together,
    # add a small spread so objects remain visible.

    if x == 0 and z == 0:

        x = index * 2


    # ======================================================
    # RETURN 3D OBJECT
    # ======================================================

    return {

        # Original GPS data

        "latitude": latitude,

        "longitude": longitude,


        # Three.js coordinates

        "x": round(x, 2),

        "y": 0,

        "z": round(z, 2),


        # Visualization data

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

            "objects": []

        }


    # ======================================================
    # FIND BASE GPS LOCATION
    # ======================================================

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


    # ======================================================
    # BUILD OBJECTS
    # ======================================================

    for index, report in enumerate(reports):

        try:

            object_3d = build_3d_object(

                report=report,

                index=index,

                base_latitude=base_latitude,

                base_longitude=base_longitude

            )


            objects.append(
                object_3d
            )


        except Exception as error:

            print(
                f"3D object error: {error}"
            )


            continue


    # ======================================================
    # RETURN SCENE
    # ======================================================

    return {

        "success": True,

        "total_objects": len(
            objects
        ),

        "objects": objects

    }


# ==========================================================
# GET 3D SUMMARY
# ==========================================================

def get_3d_summary(
    reports: List[Any]
) -> Dict[str, Any]:


    scene = build_3d_scene(
        reports
    )


    objects = scene.get(
        "objects",
        []
    )


    total_potholes = sum(

        obj.get(
            "pothole_count",
            0
        )

        for obj in objects

    )


    critical = sum(

        1

        for obj in objects

        if obj.get(
            "severity"
        ) == "CRITICAL"

    )


    high = sum(

        1

        for obj in objects

        if obj.get(
            "severity"
        ) == "HIGH"

    )


    moderate = sum(

        1

        for obj in objects

        if obj.get(
            "severity"
        ) == "MODERATE"

    )


    low = sum(

        1

        for obj in objects

        if obj.get(
            "severity"
        ) == "LOW"

    )


    return {

        "success": True,

        "total_locations": len(
            objects
        ),

        "total_potholes": total_potholes,

        "critical": critical,

        "critical_hotspots": critical,

        "high": high,

        "moderate": moderate,

        "low": low

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