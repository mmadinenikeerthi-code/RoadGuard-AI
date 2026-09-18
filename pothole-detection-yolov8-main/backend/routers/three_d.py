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
    get_3d_summary,
    build_immersive_road_scene,
)


router = APIRouter(prefix="/3d", tags=["3D Visualization"])

BASE_DIR = Path(__file__).resolve().parent.parent
THREE_D_DATA_DIR = BASE_DIR / "results" / "3d_data"
THREE_D_DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_detection_metadata(report_id: int):
    metadata_file = THREE_D_DATA_DIR / f"report_{report_id}.json"
    if not metadata_file.exists():
        return {}
    try:
        with open(metadata_file, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as error:
        print(f"[3D] Could not load metadata for report {report_id}: {error}")
        return {}


def prepare_report(report):
    metadata = load_detection_metadata(report.id)
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
        "detections": metadata.get("detections", []),
        "frame_width": metadata.get("frame_width", 0),
        "frame_height": metadata.get("frame_height", 0)
    }


@router.get("/")
def three_d_home():
    return {"success": True, "message": "RoadGuard AI Real 3D Visualization API is working"}


@router.get("/scene")
def get_scene(db: Session = Depends(get_db)):
    reports = db.query(ReportModel).order_by(ReportModel.id.desc()).all()
    prepared_reports = [prepare_report(report) for report in reports]
    return build_3d_scene(prepared_reports)


@router.get("/scene/latest")
def get_latest_scene(db: Session = Depends(get_db)):
    report = db.query(ReportModel).order_by(ReportModel.id.desc()).first()
    if not report:
        return {
            "success": True, "message": "No detection reports available.",
            "total_objects": 0, "total_potholes": 0, "objects": [], "potholes": []
        }
    return build_3d_scene([prepare_report(report)])


@router.get("/scene/{report_id}")
def get_report_scene(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return build_3d_scene([prepare_report(report)])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    reports = db.query(ReportModel).order_by(ReportModel.id.desc()).all()
    prepared_reports = [prepare_report(report) for report in reports]
    return get_3d_summary(prepared_reports)


# ==========================================================
# NEW: IMMERSIVE 360° / RECONSTRUCTION ROAD VIEW FOR ONE REPORT
# ==========================================================

@router.get("/road-view/{report_id}")
def get_road_view(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    metadata = load_detection_metadata(report_id)
    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No 3D metadata found for this report yet.",
        )

    return build_immersive_road_scene(report, metadata)


@router.get("/road-view")
def get_latest_road_view(db: Session = Depends(get_db)):
    report = db.query(ReportModel).order_by(ReportModel.id.desc()).first()
    if not report:
        raise HTTPException(status_code=404, detail="No reports available.")

    metadata = load_detection_metadata(report.id)
    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No 3D metadata found for the latest report yet.",
        )

    return build_immersive_road_scene(report, metadata)


@router.get("/reports-list")
def get_reports_list(db: Session = Depends(get_db)):
    """
    Lightweight list for the report-selector dropdown in three_d.html.
    """
    reports = db.query(ReportModel).order_by(ReportModel.id.desc()).all()
    return {
        "success": True,
        "reports": [
            {
                "id": r.id,
                "media_type": r.media_type,
                "pothole_count": r.pothole_count,
                "severity": r.severity,
                "created_at": str(getattr(r, "created_at", "")),
            }
            for r in reports
        ],
    }