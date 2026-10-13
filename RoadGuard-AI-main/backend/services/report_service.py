
"""RoadGuard AI report data service."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("roadguard.report_service")

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "backend" / "data"
REPORTS_FILE = DATA_DIR / "road_locations.json"


def read_reports() -> list[dict[str, Any]]:
    """Read reports from the JSON data file."""

    if not REPORTS_FILE.exists():
        return []

    try:
        with REPORTS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("Road reports JSON must contain a list.")

        return [item for item in data if isinstance(item, dict)]

    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.exception("Unable to load road reports")
        raise RuntimeError("Unable to load road reports.") from exc


def has_valid_coordinates(report: dict[str, Any]) -> bool:
    """Check that latitude and longitude are valid."""

    try:
        latitude = float(report["latitude"])
        longitude = float(report["longitude"])
    except (KeyError, TypeError, ValueError):
        return False

    return (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def serialize_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return the fields needed by the map."""

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


def get_located_reports() -> list[dict[str, Any]]:
    """Return only reports with valid GPS coordinates."""

    return [
        serialize_report(report)
        for report in read_reports()
        if has_valid_coordinates(report)
    ]


def get_located_report(report_id: str) -> dict[str, Any] | None:
    """Find a GPS-located report by ID."""

    for report in read_reports():
        if (
            str(report.get("id")) == report_id
            and has_valid_coordinates(report)
        ):
            return serialize_report(report)

    return None
