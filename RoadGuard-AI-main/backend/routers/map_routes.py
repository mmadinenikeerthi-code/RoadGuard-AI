
"""
RoadGuard AI - Cesium Map Routes

Endpoints:
    GET /api/cesium/config
    GET /api/cesium/reports
    GET /api/cesium/reports/{report_id}

The report data is read from:
    backend/data/road_locations.json

Only reports with real latitude and longitude coordinates
are returned as map markers. No fake GPS coordinates.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

logger = logging.getLogger("roadguard.cesium")

# ------------------------------------------------------------
# PATHS AND ENVIRONMENT
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "backend" / "data"
REPORTS_FILE = DATA_DIR / "road_locations.json"

load_dotenv(BASE_DIR / ".env")

router = APIRouter(
    prefix="/api/cesium",
    tags=["Cesium Map"],
)


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def read_reports() -> list[dict[str, Any]]:
    """Read road reports from the JSON data file."""

    if not REPORTS_FILE.exists():
        return []

    try:
        with REPORTS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            logger.warning(
                "Expected a JSON list in %s",
                REPORTS_FILE,
            )
            return []

        return [
            report for report in data
            if isinstance(report, dict)
        ]

    except (json.JSONDecodeError, OSError) as exc:
        logger.exception("Could not read road reports: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Could not read road report data.",
        ) from exc


def valid_coordinates(report: dict[str, Any]) -> bool:
    """Return True only for valid geographic coordinates."""

    try:
        latitude = float(report["latitude"])
        longitude = float(report["longitude"])
    except (KeyError, TypeError, ValueError):
        return False

    return (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def public_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return only fields needed by the map frontend."""

    return {
        "id": report.get("id"),
        "latitude": float(report["latitude"]),
        "longitude": float(report["longitude"]),
        "severity": report.get("severity", "unknown"),
        "confidence": report.get("confidence"),
        "status": report.get("status", "reported"),
        "description": report.get("description", "Road issue"),
        "image_url": report.get("image_url"),
    }


# ------------------------------------------------------------
# CESIUM CONFIGURATION
# ------------------------------------------------------------

@router.get("/config")
async def cesium_config():
    """
    Return Cesium ion configuration to the browser.

    The frontend needs this token to access authorized
    Cesium ion imagery and terrain assets.
    """

    token = os.getenv("CESIUM_ION_TOKEN", "").strip()

    return {
        "configured": bool(token),
        "cesium_token": token,
        "message": (
            "Cesium token configured."
            if token
            else "Set CESIUM_ION_TOKEN in the project root .env file."
        ),
    }


# ------------------------------------------------------------
# ROAD REPORTS
# ------------------------------------------------------------

@router.get("/reports")
async def get_cesium_reports():
    """Return reports that have valid GPS coordinates."""

    reports = read_reports()

    located_reports = [
        public_report(report)
        for report in reports
        if valid_coordinates(report)
    ]

    return {
        "count": len(located_reports),
        "reports": located_reports,
    }


@router.get("/reports/{report_id}")
async def get_cesium_report(report_id: str):
    """Return one GPS-located report."""

    for report in read_reports():
        if (
            str(report.get("id")) == report_id
            and valid_coordinates(report)
        ):
            return public_report(report)

    raise HTTPException(
        status_code=404,
        detail="GPS-located report not found.",
    )
