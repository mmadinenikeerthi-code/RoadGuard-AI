# ==========================================================
# backend/routers/detection.py
# ROADGUARD AI - DETECTION ROUTER
# ==========================================================

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    status
)

from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ReportModel
from backend.schemas import ReportResponse
from backend.config import UPLOAD_DIR

from backend.services.detection_service import (
    process_media_detection
)


# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(
    prefix="/api/detection",
    tags=["Detection"]
)


# ==========================================================
# SUPPORTED FORMATS
# ==========================================================

IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

VIDEO_EXTENSIONS = {
    "mp4",
    "avi",
    "mov",
    "mkv"
}


# ==========================================================
# UPLOAD + DETECT
# ==========================================================

@router.post(
    "/upload",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_media(
    file: UploadFile = File(...),

    latitude: Optional[float] = Form(None),

    longitude: Optional[float] = Form(None),

    location_name: Optional[str] = Form(
        "Unknown Location"
    ),

    db: Session = Depends(get_db)
):

    # ------------------------------------------------------
    # Validate filename
    # ------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No filename was provided."
        )

    original_filename = file.filename

    extension = (
        original_filename
        .rsplit(".", 1)[-1]
        .lower()
        if "." in original_filename
        else ""
    )

    # ------------------------------------------------------
    # Determine media type
    # ------------------------------------------------------

    if extension in IMAGE_EXTENSIONS:

        media_type = "image"

    elif extension in VIDEO_EXTENSIONS:

        media_type = "video"

    else:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file format. "
                "Use JPG, PNG, WEBP, MP4, AVI, MOV or MKV."
            )
        )

    # ------------------------------------------------------
    # Create unique filename
    #
    # This prevents two uploads having the same filename
    # from overwriting each other.
    # ------------------------------------------------------

    unique_filename = (
        f"{uuid.uuid4().hex}_{original_filename}"
    )

    file_path = Path(
        UPLOAD_DIR
    ) / unique_filename

    # ------------------------------------------------------
    # Save uploaded media
    # ------------------------------------------------------

    try:

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not save uploaded file: {str(e)}"
            )
        )

    # ------------------------------------------------------
    # Database media path
    # ------------------------------------------------------

    relative_media_path = (
        f"uploads/{unique_filename}"
    )

    # ------------------------------------------------------
    # Create initial database report
    # ------------------------------------------------------

    new_report = ReportModel(

        media_type=media_type,

        media_path=relative_media_path,

        latitude=latitude,

        longitude=longitude,

        location_name=(
            location_name.strip()
            if location_name
            else "Unknown Location"
        ),

        pothole_count=0,

        severity="LOW",

        confidence=0.0,

        result_path=None
    )

    try:

        db.add(new_report)

        db.commit()

        db.refresh(new_report)

    except Exception as e:

        db.rollback()

        # Delete uploaded file if database insertion fails
        try:
            file_path.unlink(
                missing_ok=True
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not create report: {str(e)}"
            )
        )

    # ------------------------------------------------------
    # RUN YOLO AUTOMATICALLY
    # ------------------------------------------------------

    try:

        detection_result = (
            process_media_detection(
                media_path=relative_media_path,

                media_type=media_type,

                report_id=new_report.id
            )
        )

        # --------------------------------------------------
        # Update database with ACTUAL AI results
        # --------------------------------------------------

        new_report.pothole_count = int(
            detection_result.get(
                "pothole_count",
                0
            )
        )

        new_report.confidence = float(
            detection_result.get(
                "confidence",
                0.0
            )
        )

        new_report.severity = str(
            detection_result.get(
                "severity",
                "LOW"
            )
        ).upper()

        new_report.result_path = (
            detection_result.get(
                "result_path"
            )
        )

        db.commit()

        db.refresh(new_report)

        print(
            f"[RoadGuard AI] "
            f"Report #{new_report.id} saved successfully."
        )

        return new_report

    except Exception as e:

        # --------------------------------------------------
        # Detection failed
        #
        # Keep the report in database so user can retry
        # through /process/{report_id}
        # --------------------------------------------------

        db.rollback()

        failed_report = db.query(
            ReportModel
        ).filter(
            ReportModel.id == new_report.id
        ).first()

        if failed_report:

            failed_report.pothole_count = 0
            failed_report.confidence = 0.0
            failed_report.severity = "LOW"

            db.commit()

        raise HTTPException(
            status_code=500,
            detail=(
                f"AI detection failed: {str(e)}"
            )
        )


# ==========================================================
# MANUAL PROCESS / RETRY
# ==========================================================

@router.post(
    "/process/{report_id}",
    response_model=ReportResponse
)
def process_report(
    report_id: int,
    db: Session = Depends(get_db)
):

    report = db.query(
        ReportModel
    ).filter(
        ReportModel.id == report_id
    ).first()

    if not report:

        raise HTTPException(
            status_code=404,
            detail="Report not found."
        )

    try:

        detection_res = (
            process_media_detection(
                media_path=report.media_path,

                media_type=report.media_type,

                report_id=report.id
            )
        )

        report.pothole_count = int(
            detection_res.get(
                "pothole_count",
                0
            )
        )

        report.confidence = float(
            detection_res.get(
                "confidence",
                0.0
            )
        )

        report.severity = str(
            detection_res.get(
                "severity",
                "LOW"
            )
        ).upper()

        report.result_path = (
            detection_res.get(
                "result_path"
            )
        )

        db.commit()

        db.refresh(report)

        return report

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Inference error: {str(e)}"
            )
        )


# ==========================================================
# GET DETECTION STATUS
# ==========================================================

@router.get(
    "/{report_id}",
    response_model=ReportResponse
)
def get_detection_status(
    report_id: int,
    db: Session = Depends(get_db)
):

    report = db.query(
        ReportModel
    ).filter(
        ReportModel.id == report_id
    ).first()

    if not report:

        raise HTTPException(
            status_code=404,
            detail="Report not found."
        )

    return report