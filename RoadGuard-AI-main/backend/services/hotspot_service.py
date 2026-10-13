# ==========================================================
# backend/services/hotspot_service.py
# ROADGUARD AI - HOTSPOT SERVICE
# ==========================================================

from collections import defaultdict


# ==========================================================
# CALCULATE SEVERITY
# ==========================================================

def calculate_severity(pothole_count, average_confidence=0.0):

    pothole_count = pothole_count or 0

    try:
        pothole_count = int(pothole_count)
    except (ValueError, TypeError):
        pothole_count = 0

    try:
        average_confidence = float(average_confidence or 0.0)
    except (ValueError, TypeError):
        average_confidence = 0.0


    # ------------------------------------------------------
    # SEVERITY BASED ON POTHOLE COUNT
    # ------------------------------------------------------

    if pothole_count >= 20:
        return "CRITICAL"

    elif pothole_count >= 10:
        return "HIGH"

    elif pothole_count >= 5:
        return "MODERATE"

    return "LOW"


# ==========================================================
# GET HOTSPOT COLOR
# ==========================================================

def get_hotspot_color(severity):

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
# EXTRACT REPORT DATA
# ==========================================================

def extract_report_data(report):

    # ------------------------------------------------------
    # DICTIONARY REPORT
    # ------------------------------------------------------

    if isinstance(report, dict):

        latitude = report.get("latitude")

        longitude = report.get("longitude")

        pothole_count = report.get(
            "potholes",
            report.get("pothole_count", 0)
        )

        confidence = report.get(
            "confidence",
            0
        )

        location_name = report.get(
            "location_name",
            None
        )


    # ------------------------------------------------------
    # SQLALCHEMY REPORT MODEL
    # ------------------------------------------------------

    else:

        latitude = getattr(
            report,
            "latitude",
            None
        )

        longitude = getattr(
            report,
            "longitude",
            None
        )

        pothole_count = getattr(
            report,
            "pothole_count",
            0
        )

        confidence = getattr(
            report,
            "confidence",
            0
        )

        location_name = getattr(
            report,
            "location_name",
            None
        )


    return {

        "latitude": latitude,

        "longitude": longitude,

        "pothole_count": pothole_count,

        "confidence": confidence,

        "location_name": location_name

    }


# ==========================================================
# GENERATE HOTSPOTS
# ==========================================================

def generate_hotspots(reports):

    grouped_hotspots = defaultdict(list)


    # ======================================================
    # GROUP REPORTS BY NEARBY LOCATION
    # ======================================================

    for report in reports:

        data = extract_report_data(report)

        latitude = data.get("latitude")

        longitude = data.get("longitude")


        # --------------------------------------------------
        # SKIP REPORTS WITHOUT LOCATION
        # --------------------------------------------------

        if latitude is None or longitude is None:
            continue


        # --------------------------------------------------
        # CONVERT LOCATION TO FLOAT
        # --------------------------------------------------

        try:

            latitude = float(latitude)

            longitude = float(longitude)

        except (ValueError, TypeError):

            continue


        # --------------------------------------------------
        # GROUP NEARBY LOCATIONS
        #
        # 3 DECIMAL PLACES ≈ NEARBY GEOGRAPHICAL AREA
        # --------------------------------------------------

        location_key = (

            round(latitude, 3),

            round(longitude, 3)

        )


        grouped_hotspots[
            location_key
        ].append(report)


    # ======================================================
    # HOTSPOTS LIST
    # ======================================================

    hotspots = []

    hotspot_id = 1


    # ======================================================
    # CREATE HOTSPOTS
    # ======================================================

    for location_key, location_reports in grouped_hotspots.items():

        latitude, longitude = location_key


        # --------------------------------------------------
        # REPORT COUNT
        # --------------------------------------------------

        report_count = len(
            location_reports
        )


        # --------------------------------------------------
        # INITIAL VALUES
        # --------------------------------------------------

        total_potholes = 0

        confidences = []

        location_name = None


        # ==================================================
        # PROCESS REPORTS
        # ==================================================

        for report in location_reports:

            data = extract_report_data(report)


            potholes = data.get(
                "pothole_count",
                0
            )

            confidence = data.get(
                "confidence",
                0
            )

            name = data.get(
                "location_name",
                None
            )


            # ----------------------------------------------
            # ADD POTHOLES
            # ----------------------------------------------

            try:

                total_potholes += int(
                    potholes or 0
                )

            except (ValueError, TypeError):

                pass


            # ----------------------------------------------
            # ADD CONFIDENCE
            # ----------------------------------------------

            try:

                if confidence is not None:

                    confidence_value = float(
                        confidence
                    )

                    confidences.append(
                        confidence_value
                    )

            except (ValueError, TypeError):

                pass


            # ----------------------------------------------
            # GET LOCATION NAME
            # ----------------------------------------------

            if (

                not location_name

                and name

                and str(name).strip()

                and name not in [

                    "Unknown",

                    "Unknown Location",

                    "None"

                ]

            ):

                location_name = str(name)


        # ==================================================
        # CALCULATE AVERAGE CONFIDENCE
        # ==================================================

        if confidences:

            average_confidence = (

                sum(confidences)

                / len(confidences)

            )

        else:

            average_confidence = 0.0


        # ==================================================
        # DEFAULT LOCATION NAME
        # ==================================================

        if not location_name:

            location_name = (

                f"Location "

                f"{latitude:.4f}, "

                f"{longitude:.4f}"

            )


        # ==================================================
        # CALCULATE SEVERITY
        # ==================================================

        severity = calculate_severity(

            total_potholes,

            average_confidence

        )


        # ==================================================
        # CREATE HOTSPOT
        # ==================================================

        hotspot = {

            "id": hotspot_id,

            "latitude": latitude,

            "longitude": longitude,

            "location_name": location_name,

            "report_count": report_count,

            "pothole_count": total_potholes,

            "average_confidence": round(
                average_confidence,
                2
            ),

            "severity": severity,

            "color": get_hotspot_color(
                severity
            )

        }


        hotspots.append(
            hotspot
        )


        hotspot_id += 1


    # ======================================================
    # SEVERITY ORDER
    # ======================================================

    severity_order = {

        "CRITICAL": 4,

        "HIGH": 3,

        "MODERATE": 2,

        "LOW": 1

    }


    # ======================================================
    # SORT HOTSPOTS
    # ======================================================

    hotspots.sort(

        key=lambda hotspot: (

            severity_order.get(

                hotspot.get("severity"),

                0

            ),

            hotspot.get(

                "pothole_count",

                0

            )

        ),

        reverse=True

    )


    # ======================================================
    # RETURN HOTSPOTS
    # ======================================================

    return hotspots


# ==========================================================
# GET HOTSPOTS SERVICE
# ==========================================================

def get_hotspots_service(reports):

    return generate_hotspots(
        reports
    )


# ==========================================================
# GET HOTSPOT SUMMARY SERVICE
# ==========================================================

def get_hotspot_summary_service(reports):


    # ------------------------------------------------------
    # GENERATE HOTSPOTS
    # ------------------------------------------------------

    hotspots = generate_hotspots(
        reports
    )


    # ------------------------------------------------------
    # COUNT SEVERITY TYPES
    # ------------------------------------------------------

    critical = sum(

        1

        for hotspot in hotspots

        if hotspot.get("severity") == "CRITICAL"

    )


    high = sum(

        1

        for hotspot in hotspots

        if hotspot.get("severity") == "HIGH"

    )


    moderate = sum(

        1

        for hotspot in hotspots

        if hotspot.get("severity") == "MODERATE"

    )


    low = sum(

        1

        for hotspot in hotspots

        if hotspot.get("severity") == "LOW"

    )


    # ------------------------------------------------------
    # TOTAL POTHOLES
    # ------------------------------------------------------

    total_potholes = sum(

        hotspot.get(

            "pothole_count",

            0

        )

        for hotspot in hotspots

    )


    # ======================================================
    # RETURN SUMMARY
    # ======================================================

    return {

        "success": True,

        "total_reports": len(
            reports
        ),

        "total_potholes": total_potholes,

        "total_hotspots": len(
            hotspots
        ),

        "critical_hotspots": critical,

        "high_hotspots": high,

        "moderate_hotspots": moderate,

        "low_hotspots": low,

        "hotspots": hotspots

    }