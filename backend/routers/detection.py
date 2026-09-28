# ==========================================================
# backend/routers/detection.py
# ROADGUARD AI - DETECTION ROUTER
#
# FLOW:
#
# Upload Image / Video
#        ↓
# Save Original Media
#        ↓
# Create Database Report
#        ↓
# Run YOLO Detection
#        ↓
# Save Detection Results
#        ↓
# Save 3D Metadata (Bounding Boxes / Coordinates)
#        ↓
# Database Updated
#        ↓
# Frontend 3D Visualization Can Use Report Data
# ==========================================================


import json
import shutil
import uuid

from pathlib import Path
from typing import Optional, Dict, Any

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


# ==========================================================
# ROADGUARD IMPORTS
# ==========================================================

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
# SUPPORTED IMAGE FORMATS
# ==========================================================

IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}


# ==========================================================
# SUPPORTED VIDEO FORMATS
# ==========================================================

VIDEO_EXTENSIONS = {
    "mp4",
    "avi",
    "mov",
    "mkv"
}


# ==========================================================
# SAVE 3D DETECTION METADATA
#
# This saves YOLO detection information so that the
# Three.js frontend can later create potholes in the
# correct relative positions on the 3D road.
# ==========================================================

def save_3d_metadata(
    report_id: int,
    detection_result: Dict[str, Any]
):

    try:

        # --------------------------------------------------
        # BASE BACKEND DIRECTORY
        # --------------------------------------------------

        base_dir = Path(__file__).resolve().parent.parent


        # --------------------------------------------------
        # CREATE:
        #
        # backend/results/3d_data/
        # --------------------------------------------------

        metadata_dir = (
            base_dir /
            "results" /
            "3d_data"
        )

        metadata_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        # --------------------------------------------------
        # JSON FILE
        #
        # Example:
        #
        # report_1.json
        # report_2.json
        # --------------------------------------------------

        metadata_file = (
            metadata_dir /
            f"report_{report_id}.json"
        )


        # --------------------------------------------------
        # GET DETECTIONS
        #
        # Different versions of detection_service.py may
        # return different key names.
        # --------------------------------------------------

        detections = (

            detection_result.get("detections")

            or

            detection_result.get("potholes")

            or

            detection_result.get("boxes")

            or

            []

        )


        # --------------------------------------------------
        # FRAME DIMENSIONS
        # --------------------------------------------------

        frame_width = detection_result.get(
            "frame_width",
            1920
        )

        frame_height = detection_result.get(
            "frame_height",
            1080
        )


        # --------------------------------------------------
        # CREATE METADATA
        # --------------------------------------------------

        metadata = {

            "success": True,

            "report_id": report_id,

            "pothole_count": detection_result.get(
                "pothole_count",
                0
            ),

            "severity": detection_result.get(
                "severity",
                "LOW"
            ),

            "confidence": detection_result.get(
                "confidence",
                0.0
            ),

            "frame_width": frame_width,

            "frame_height": frame_height,

            "detections": detections

        }


        # --------------------------------------------------
        # SAVE JSON
        # --------------------------------------------------

        with open(
            metadata_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                metadata,
                file,
                indent=4,
                default=str
            )


        print(
            f"[RoadGuard AI] "
            f"3D metadata saved successfully: "
            f"{metadata_file}"
        )


        # Return relative path

        return (
            f"results/3d_data/"
            f"report_{report_id}.json"
        )


    except Exception as error:

        print(
            f"[RoadGuard AI] "
            f"3D metadata saving error: {error}"
        )

        # Do not crash the entire detection process
        return None


# ==========================================================
# HELPER:
# UPDATE REPORT WITH DETECTION RESULTS
# ==========================================================

def update_report_with_detection(
    report: ReportModel,
    detection_result: Dict[str, Any]
):

    # ------------------------------------------------------
    # POTHOLE COUNT
    # ------------------------------------------------------

    report.pothole_count = int(
        detection_result.get(
            "pothole_count",
            0
        ) or 0
    )


    # ------------------------------------------------------
    # CONFIDENCE
    # ------------------------------------------------------

    report.confidence = float(
        detection_result.get(
            "confidence",
            0.0
        ) or 0.0
    )


    # ------------------------------------------------------
    # SEVERITY
    # ------------------------------------------------------

    report.severity = str(
        detection_result.get(
            "severity",
            "LOW"
        )
    ).upper()


    # ------------------------------------------------------
    # RESULT PATH
    # ------------------------------------------------------

    report.result_path = (
        detection_result.get(
            "result_path"
        )
    )


# ==========================================================
# UPLOAD + AUTOMATIC YOLO DETECTION
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


    # ======================================================
    # VALIDATE FILENAME
    # ======================================================

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No filename was provided."
        )


    # ======================================================
    # ORIGINAL FILENAME
    # ======================================================

    original_filename = file.filename


    # ======================================================
    # GET FILE EXTENSION
    # ======================================================

    extension = (

        original_filename
        .rsplit(".", 1)[-1]
        .lower()

        if "." in original_filename

        else ""

    )


    # ======================================================
    # DETERMINE MEDIA TYPE
    # ======================================================

    if extension in IMAGE_EXTENSIONS:

        media_type = "image"


    elif extension in VIDEO_EXTENSIONS:

        media_type = "video"


    else:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file format. "
                "Use JPG, JPEG, PNG, WEBP, "
                "MP4, AVI, MOV or MKV."
            )
        )


    # ======================================================
    # CREATE UPLOAD DIRECTORY
    # ======================================================

    upload_directory = Path(UPLOAD_DIR)

    upload_directory.mkdir(
        parents=True,
        exist_ok=True
    )


    # ======================================================
    # CREATE UNIQUE FILENAME
    # ======================================================

    safe_filename = (
        original_filename
        .replace(" ", "_")
    )


    unique_filename = (
        f"{uuid.uuid4().hex}_"
        f"{safe_filename}"
    )


    file_path = (
        upload_directory /
        unique_filename
    )


    # ======================================================
    # SAVE UPLOADED MEDIA
    # ======================================================

    try:

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not save uploaded file: "
                f"{str(error)}"
            )
        )


    # ======================================================
    # DATABASE MEDIA PATH
    # ======================================================

    relative_media_path = (
        f"uploads/{unique_filename}"
    )


    # ======================================================
    # CLEAN LOCATION NAME
    # ======================================================

    clean_location_name = (

        location_name.strip()

        if location_name
        and location_name.strip()

        else "Unknown Location"

    )


    # ======================================================
    # CREATE INITIAL DATABASE REPORT
    # ======================================================

    new_report = ReportModel(

        media_type=media_type,

        media_path=relative_media_path,

        latitude=latitude,

        longitude=longitude,

        location_name=clean_location_name,

        pothole_count=0,

        severity="LOW",

        confidence=0.0,

        result_path=None

    )


    # ======================================================
    # SAVE INITIAL REPORT
    # ======================================================

    try:

        db.add(new_report)

        db.commit()

        db.refresh(new_report)


    except Exception as error:

        db.rollback()


        # Delete uploaded file if database fails

        try:

            file_path.unlink(
                missing_ok=True
            )

        except Exception:

            pass


        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not create report: "
                f"{str(error)}"
            )
        )


    # ======================================================
    # RUN YOLO AUTOMATICALLY
    # ======================================================

    try:

        print(
            f"[RoadGuard AI] "
            f"Starting YOLO detection "
            f"for Report #{new_report.id}"
        )


        detection_result = (
            process_media_detection(

                media_path=relative_media_path,

                media_type=media_type,

                report_id=new_report.id

            )
        )


        # ==================================================
        # VALIDATE DETECTION RESULT
        # ==================================================

        if detection_result is None:

            detection_result = {}


        # ==================================================
        # UPDATE DATABASE WITH YOLO RESULTS
        # ==================================================

        update_report_with_detection(

            report=new_report,

            detection_result=detection_result

        )


        # ==================================================
        # SAVE 3D DETECTION METADATA
        #
        # YOLO boxes/coordinates are stored here.
        # ==================================================

        metadata_path = save_3d_metadata(

            report_id=new_report.id,

            detection_result=detection_result

        )


        # Optional: add metadata path dynamically for logs

        print(
            f"[RoadGuard AI] "
            f"3D metadata path: "
            f"{metadata_path}"
        )


        # ==================================================
        # SAVE DATABASE
        # ==================================================

        db.commit()

        db.refresh(new_report)


        print(
            f"[RoadGuard AI] "
            f"Report #{new_report.id} "
            f"saved successfully."
        )


        print(
            f"[RoadGuard AI] "
            f"Potholes detected: "
            f"{new_report.pothole_count}"
        )


        # ==================================================
        # RETURN REPORT
        # ==================================================

        return new_report


    except Exception as error:


        # ==================================================
        # DETECTION FAILED
        #
        # Keep report in database so it can be retried.
        # ==================================================

        db.rollback()


        failed_report = (

            db.query(ReportModel)

            .filter(
                ReportModel.id == new_report.id
            )

            .first()

        )


        if failed_report:

            failed_report.pothole_count = 0

            failed_report.confidence = 0.0

            failed_report.severity = "LOW"

            db.commit()


        print(
            f"[RoadGuard AI] "
            f"Detection Error: {error}"
        )


        raise HTTPException(
            status_code=500,
            detail=(
                f"AI detection failed: "
                f"{str(error)}"
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


    # ======================================================
    # GET REPORT
    # ======================================================

    report = (

        db.query(ReportModel)

        .filter(
            ReportModel.id == report_id
        )

        .first()

    )


    # ======================================================
    # REPORT NOT FOUND
    # ======================================================

    if not report:

        raise HTTPException(
            status_code=404,
            detail="Report not found."
        )


    # ======================================================
    # RUN DETECTION AGAIN
    # ======================================================

    try:


        print(
            f"[RoadGuard AI] "
            f"Retrying detection for "
            f"Report #{report.id}"
        )


        detection_result = (

            process_media_detection(

                media_path=report.media_path,

                media_type=report.media_type,

                report_id=report.id

            )

        )


        if detection_result is None:

            detection_result = {}


        # ==================================================
        # UPDATE REPORT
        # ==================================================

        update_report_with_detection(

            report=report,

            detection_result=detection_result

        )


        # ==================================================
        # SAVE UPDATED 3D METADATA
        # ==================================================

        metadata_path = save_3d_metadata(

            report_id=report.id,

            detection_result=detection_result

        )


        print(
            f"[RoadGuard AI] "
            f"Updated 3D metadata: "
            f"{metadata_path}"
        )


        # ==================================================
        # SAVE DATABASE
        # ==================================================

        db.commit()

        db.refresh(report)


        print(
            f"[RoadGuard AI] "
            f"Report #{report.id} "
            f"processed successfully."
        )


        return report


    except Exception as error:


        db.rollback()


        print(
            f"[RoadGuard AI] "
            f"Inference error: {error}"
        )


        raise HTTPException(
            status_code=500,
            detail=(
                f"Inference error: "
                f"{str(error)}"
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


    return report


# ==========================================================
# GET 3D METADATA FOR A REPORT
#
# Frontend can call:
#
# /api/detection/3d-metadata/1
# ==========================================================

@router.get(
    "/3d-metadata/{report_id}"
)
def get_3d_metadata(

    report_id: int

):


    # ======================================================
    # BACKEND DIRECTORY
    # ======================================================

    base_dir = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )


    # ======================================================
    # METADATA FILE
    # ======================================================

    metadata_file = (

        base_dir

        / "results"

        / "3d_data"

        / f"report_{report_id}.json"

    )


    # ======================================================
    # CHECK FILE
    # ======================================================

    if not metadata_file.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "3D metadata not found "
                "for this report."
            )
        )


    # ======================================================
    # READ JSON
    # ======================================================

    try:

        with open(
            metadata_file,
            "r",
            encoding="utf-8"
        ) as file:

            metadata = json.load(file)


        return {

            "success": True,

            "data": metadata

        }


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not read 3D metadata: "
                f"{str(error)}"
            )
        )


# ==========================================================
# END OF DETECTION ROUTER
# ==========================================================