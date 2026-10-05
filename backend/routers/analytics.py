# ==========================================================
# ROADGUARD AI - ANALYTICS API
# backend/routers/analytics.py
# ==========================================================

from collections import Counter
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import func

from backend.database import SessionLocal
from backend.models import ReportModel


router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
)


# ==========================================================
# MAIN ANALYTICS ENDPOINT
# ==========================================================

@router.get("")
def get_analytics():
    """
    Return real analytics calculated from stored RoadGuard
    reports.

    No fake/demo values are generated here.
    """

    db = SessionLocal()

    try:
        reports = (
            db.query(ReportModel)
            .order_by(
                ReportModel.created_at.desc()
            )
            .all()
        )

        # --------------------------------------------------
        # EMPTY DATABASE
        # --------------------------------------------------

        if not reports:
            return {
                "success": True,
                "analytics": {
                    "total_reports": 0,
                    "total_potholes": 0,
                    "average_confidence": 0,
                    "severity": {
                        "CRITICAL": 0,
                        "HIGH": 0,
                        "MODERATE": 0,
                        "LOW": 0,
                    },
                    "media_types": {
                        "IMAGE": 0,
                        "VIDEO": 0,
                        "OTHER": 0,
                    },
                    "daily_reports": [],
                    "recent_reports": [],
                },
            }

        # --------------------------------------------------
        # BASIC COUNTS
        # --------------------------------------------------

        total_reports = len(reports)

        total_potholes = sum(
            int(report.pothole_count or 0)
            for report in reports
        )

        confidence_values = [
            float(report.confidence or 0)
            for report in reports
            if report.confidence is not None
        ]

        average_confidence = (
            sum(confidence_values)
            / len(confidence_values)
            if confidence_values
            else 0
        )

        # --------------------------------------------------
        # SEVERITY
        # --------------------------------------------------

        severity_counter = Counter()

        for report in reports:

            severity = (
                str(
                    report.severity or "LOW"
                )
                .upper()
            )

            if severity not in {
                "CRITICAL",
                "HIGH",
                "MODERATE",
                "LOW",
            }:
                severity = "LOW"

            severity_counter[severity] += 1

        severity = {
            "CRITICAL": severity_counter["CRITICAL"],
            "HIGH": severity_counter["HIGH"],
            "MODERATE": severity_counter["MODERATE"],
            "LOW": severity_counter["LOW"],
        }

        # --------------------------------------------------
        # MEDIA TYPES
        # --------------------------------------------------

        media_counter = Counter()

        for report in reports:

            media_type = (
                str(
                    report.media_type or "OTHER"
                )
                .upper()
            )

            if media_type not in {
                "IMAGE",
                "VIDEO",
            }:
                media_type = "OTHER"

            media_counter[media_type] += 1

        media_types = {
            "IMAGE": media_counter["IMAGE"],
            "VIDEO": media_counter["VIDEO"],
            "OTHER": media_counter["OTHER"],
        }

        # --------------------------------------------------
        # DAILY REPORTS
        # --------------------------------------------------

        daily_counter = Counter()

        for report in reports:

            created_at = report.created_at

            if not created_at:
                continue

            if isinstance(
                created_at,
                datetime
            ):
                date_key = (
                    created_at
                    .strftime("%Y-%m-%d")
                )
            else:
                date_key = str(
                    created_at
                )[:10]

            daily_counter[date_key] += 1

        daily_reports = [
            {
                "date": date,
                "reports": count,
            }
            for date, count
            in sorted(
                daily_counter.items()
            )
        ]

        # --------------------------------------------------
        # RECENT REPORTS
        # --------------------------------------------------

        recent_reports = []

        for report in reports[:20]:

            recent_reports.append({
                "id": report.id,

                "media_type":
                    report.media_type,

                "pothole_count":
                    int(
                        report.pothole_count or 0
                    ),

                "severity":
                    str(
                        report.severity or "LOW"
                    ).upper(),

                "confidence":
                    float(
                        report.confidence or 0
                    ),

                "location":
                    report.location_name
                    or "Unknown Location",

                "latitude":
                    float(
                        report.latitude or 0
                    ),

                "longitude":
                    float(
                        report.longitude or 0
                    ),

                "created_at":
                    (
                        report.created_at.isoformat()
                        if report.created_at
                        else None
                    ),
            })

        # --------------------------------------------------
        # RESPONSE
        # --------------------------------------------------

        return {
            "success": True,

            "analytics": {
                "total_reports":
                    total_reports,

                "total_potholes":
                    total_potholes,

                "average_confidence":
                    round(
                        average_confidence,
                        4
                    ),

                "severity":
                    severity,

                "media_types":
                    media_types,

                "daily_reports":
                    daily_reports,

                "recent_reports":
                    recent_reports,
            },
        }

    finally:
        db.close()


# ==========================================================
# RECENT REPORTS ENDPOINT
# ==========================================================

@router.get("/reports")
def get_analytics_reports():
    """
    Return stored reports for the analytics page.
    """

    db = SessionLocal()

    try:

        reports = (
            db.query(ReportModel)
            .order_by(
                ReportModel.created_at.desc()
            )
            .all()
        )

        return {
            "success": True,

            "reports": [
                {
                    "id": report.id,

                    "media_type":
                        report.media_type,

                    "pothole_count":
                        int(
                            report.pothole_count or 0
                        ),

                    "severity":
                        str(
                            report.severity or "LOW"
                        ).upper(),

                    "confidence":
                        float(
                            report.confidence or 0
                        ),

                    "location":
                        report.location_name
                        or "Unknown Location",

                    "latitude":
                        float(
                            report.latitude or 0
                        ),

                    "longitude":
                        float(
                            report.longitude or 0
                        ),

                    "created_at":
                        (
                            report.created_at.isoformat()
                            if report.created_at
                            else None
                        ),
                }
                for report in reports
            ],
        }

    finally:
        db.close()