# ==========================================================
# backend/routers/three_d.py
# ROADGUARD AI - REAL 3D VISUALIZATION ROUTER
# ==========================================================

from pathlib import Path
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ReportModel

from backend.services.three_d_service import (
    build_3d_scene,
    get_3d_summary
)


# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(
    prefix="/3d",
    tags=["3D Visualization"]
)


# ==========================================================
# 3D DATA DIRECTORY
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

THREE_D_DATA_DIR = (
    BASE_DIR / "results" / "3d_data"
)

THREE_D_DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================================
# LOAD DETECTION METADATA
# ==========================================================

def load_detection_metadata(report_id: int):

    metadata_file = (
        THREE_D_DATA_DIR /
        f"report_{report_id}.json"
    )

    if not metadata_file.exists():

        return {}

    try:

        with open(
            metadata_file,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            f"[3D] Could not load metadata "
            f"for report {report_id}: {error}"
        )

        return {}


# ==========================================================
# CONVERT DATABASE REPORT TO 3D REPORT
# ==========================================================

def prepare_report(report):

    metadata = load_detection_metadata(
        report.id
    )

    return {

        "id": report.id,

        "media_type": report.media_type,

        "media_path": report.media_path,

        "result_path": report.result_path,

        "latitude": report.latitude,

        "longitude": report.longitude,

        "location_name": report.location_name,

        "pothole_count": report.pothole_count,

        "severity": report.severity,

        "confidence": report.confidence,

        # Individual YOLO detections

        "detections": metadata.get(
            "detections",
            []
        ),

        "frame_width": metadata.get(
            "frame_width",
            0
        ),

        "frame_height": metadata.get(
            "frame_height",
            0
        )

    }


# ==========================================================
# HOME
# ==========================================================

@router.get("/")
def three_d_home():

    return {

        "success": True,

        "message":
            "RoadGuard AI Real 3D Visualization API is working"

    }


# ==========================================================
# GET COMPLETE REAL 3D SCENE
# ==========================================================

@router.get("/scene")
def get_scene(
    db: Session = Depends(get_db)
):

    reports = (

        db.query(ReportModel)

        .order_by(
            ReportModel.id.desc()
        )

        .all()

    )

    prepared_reports = [

        prepare_report(report)

        for report in reports

    ]

    return build_3d_scene(
        prepared_reports
    )


# ==========================================================
# GET LATEST REPORT 3D SCENE
# ==========================================================

@router.get("/scene/latest")
def get_latest_scene(
    db: Session = Depends(get_db)
):

    report = (

        db.query(ReportModel)

        .order_by(
            ReportModel.id.desc()
        )

        .first()

    )

    if not report:

        return {

            "success": True,

            "message":
                "No detection reports available.",

            "total_objects": 0,

            "total_potholes": 0,

            "objects": [],

            "potholes": []

        }

    prepared_report = prepare_report(
        report
    )

    return build_3d_scene(
        [prepared_report]
    )


# ==========================================================
# GET SPECIFIC REPORT 3D SCENE
# ==========================================================

@router.get("/scene/{report_id}")
def get_report_scene(
    report_id: int,

    db: Session = Depends(get_db)
):

    report = (

        db.query(ReportModel)

        .filter(
            ReportModel.id == report_id
        )

        .first()

    )

    if not report:

        raise HTTPException(

            status_code=404,

            detail="Report not found."

        )

    prepared_report = prepare_report(
        report
    )

    return build_3d_scene(
        [prepared_report]
    )


# ==========================================================
# GET 3D SUMMARY
# ==========================================================

@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db)
):

    reports = (

        db.query(ReportModel)

        .order_by(
            ReportModel.id.desc()
        )

        .all()

    )

    prepared_reports = [

        prepare_report(report)

        for report in reports

    ]

    return get_3d_summary(
        prepared_reports
    )