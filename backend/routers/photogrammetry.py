# ==========================================================
# backend/routers/photogrammetry.py
# ROADGUARD AI - PHOTOGRAMMETRY API ROUTER
# ==========================================================

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ReportModel
from backend.services.photogrammetry_service import (
    process_report_photogrammetry,
    get_reconstruction_status,
    get_reconstruction_metadata,
    get_reconstruction_mesh,
    get_engine_status,
)


router = APIRouter(
    prefix="/api/photogrammetry",
    tags=["Photogrammetry"],
)


# ==========================================================
# REPORT HELPER
# ==========================================================

def get_report_or_404(
    report_id: int,
    db: Session,
) -> ReportModel:

    report = (
        db.query(ReportModel)
        .filter(ReportModel.id == report_id)
        .first()
    )

    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found.",
        )

    return report


# ==========================================================
# RECONSTRUCTION ENGINE STATUS
#
# Declared in frontend/js/config.js as
# API_ENDPOINTS.photogrammetryEngine, but previously had no
# route registered, so the frontend call answered 404.
# ==========================================================

@router.get("/engine")
def get_engine_status_api():

    return get_engine_status()


# ==========================================================
# RUN PHOTOGRAMMETRY RECONSTRUCTION
# ==========================================================

@router.post("/reconstruct/{report_id}")
def reconstruct_report(
    report_id: int,
    db: Session = Depends(get_db),
):
    """
    Run photogrammetry / 3D reconstruction for one report.
    """

    report = get_report_or_404(
        report_id,
        db,
    )

    media_path = Path(str(report.media_path))

    if media_path.suffix.lower() not in {
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
    }:

        raise HTTPException(
            status_code=400,
            detail="Photogrammetry reconstruction requires a video report.",
        )

    try:

        result = process_report_photogrammetry(
            report_id=report_id,
            db=db,
        )

        return {
            "success": True,
            "message": "Photogrammetry reconstruction completed.",
            "result": result,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Photogrammetry reconstruction failed: {exc}",
        )


# ==========================================================
# RECONSTRUCTION STATUS
# ==========================================================

@router.get("/status/{report_id}")
def get_reconstruction_status_api(
    report_id: int,
):

    return get_reconstruction_status(
        report_id
    )


# ==========================================================
# RECONSTRUCTION METADATA
# ==========================================================

@router.get("/metadata/{report_id}")
def get_reconstruction_metadata_api(
    report_id: int,
):

    metadata = get_reconstruction_metadata(
        report_id
    )

    if metadata is None:

        raise HTTPException(
            status_code=404,
            detail="3D metadata not found. Run reconstruction first.",
        )

    return JSONResponse(
        content=metadata
    )


# ==========================================================
# RECONSTRUCTED ROAD MESH
# ==========================================================

@router.get("/mesh/{report_id}")
def get_reconstruction_mesh_api(
    report_id: int,
):

    mesh_path = get_reconstruction_mesh(
        report_id
    )

    if mesh_path is None:

        raise HTTPException(
            status_code=404,
            detail="3D road mesh not found. Run reconstruction first.",
        )

    return FileResponse(
        path=mesh_path,
        media_type="application/octet-stream",
        filename="roadguard-road.ply",
    )