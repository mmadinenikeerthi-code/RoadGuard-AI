# ==========================================================
# backend/routers/three_d.py
# ROADGUARD AI - 3D VISUALIZATION ROUTER
# ==========================================================

from pathlib import Path
import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ReportModel

from backend.services.three_d_service import (
    build_3d_scene,
    get_3d_summary,
    build_immersive_road_scene,
    get_reconstruction_paths,
)


router = APIRouter(
    prefix="/3d",
    tags=["3D Visualization"],
)


# ==========================================================
# PATHS
#
# backend/routers/three_d.py -> parents[0]=routers,
# parents[1]=backend, parents[2]=project root.
#
# The project root is the single source of truth, matching
# backend/services/detection_service.py (three_d_service.py
# and photogrammetry_service.py already resolve it this way).
#
# LEGACY_THREE_D_DATA_DIR is the old, incorrect location that
# this router used to read/write (backend/results/3d_data).
# It is still read so metadata written by the buggy version
# is not silently ignored.
# ==========================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]

PROJECT_ROOT = BACKEND_DIR.parent

RESULTS_DIR = PROJECT_ROOT / "results"

THREE_D_DATA_DIR = RESULTS_DIR / "3d_data"

LEGACY_THREE_D_DATA_DIR = (
    BACKEND_DIR
    / "results"
    / "3d_data"
)

THREE_D_DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def _read_metadata_file(metadata_file: Path):
    """
    Read one metadata JSON file. Returns {} on any failure.
    """

    if not metadata_file.exists():
        return {}

    try:

        with open(
            metadata_file,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            f"[3D] Metadata error "
            f"({metadata_file}): {error}"
        )

        return {}


def load_detection_metadata(
    report_id: int,
):
    """
    Read the YOLO detection metadata for a report.

    Looks in the current location first, then the legacy
    backend/results/3d_data location.
    """

    for metadata_file in (
        THREE_D_DATA_DIR / f"report_{report_id}.json",
        LEGACY_THREE_D_DATA_DIR / f"report_{report_id}.json",
    ):

        metadata = _read_metadata_file(
            metadata_file
        )

        if metadata:
            return metadata

    return {}


def load_report_metadata(
    report_id: int,
):
    """
    Return (metadata, source) for a report.

    Order of preference:

        1. results/3d_data/report_<id>.json
           (YOLO boxes; richest data)

        2. backend/results/3d_data/report_<id>.json
           (legacy location written by the older buggy router)

        3. results/photogrammetry/report_<id>/roadguard_3d.json
           (real photogrammetry reconstruction output)

    Returns ({}, None) when nothing exists. This is normal
    for reports whose detection metadata was never saved, and
    callers must handle it without inventing data.
    """

    metadata = load_detection_metadata(
        report_id
    )

    if metadata:

        return metadata, "detection_metadata"

    reconstruction_paths = get_reconstruction_paths(
        report_id
    )

    metadata_path = reconstruction_paths.get(
        "metadata_path"
    )

    if metadata_path:

        metadata = _read_metadata_file(
            metadata_path
        )

        if metadata:

            return metadata, "reconstruction_metadata"

    return {}, None


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
        "detections": metadata.get(
            "detections",
            [],
        ),
        "unique_potholes": metadata.get(
            "unique_potholes",
            [],
        ),
        "frame_width": metadata.get(
            "frame_width",
            0,
        ),
        "frame_height": metadata.get(
            "frame_height",
            0,
        ),
    }


@router.get("/")
def three_d_home():

    return {
        "success": True,
        "message": (
            "RoadGuard AI 3D API is working"
        ),
    }


@router.get("/scene")
def get_scene(
    db: Session = Depends(get_db),
):

    reports = (
        db.query(ReportModel)
        .order_by(
            ReportModel.id.desc()
        )
        .all()
    )

    return build_3d_scene(
        [
            prepare_report(report)
            for report in reports
        ]
    )


@router.get("/scene/latest")
def get_latest_scene(
    db: Session = Depends(get_db),
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
            "total_objects": 0,
            "objects": [],
            "message": "No reports available.",
        }

    return build_3d_scene(
        [prepare_report(report)]
    )


@router.get("/scene/{report_id}")
def get_report_scene(
    report_id: int,
    db: Session = Depends(get_db),
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
            detail="Report not found.",
        )

    return build_3d_scene(
        [prepare_report(report)]
    )


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
):

    reports = (
        db.query(ReportModel)
        .order_by(
            ReportModel.id.desc()
        )
        .all()
    )

    return get_3d_summary(
        [
            prepare_report(report)
            for report in reports
        ]
    )


@router.get("/road-view/{report_id}")
def get_road_view(
    report_id: int,
    db: Session = Depends(get_db),
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
            detail="Report not found.",
        )

    # ------------------------------------------------------
    # A report is allowed to exist without 3D metadata.
    #
    # Detection metadata (results/3d_data/report_<id>.json)
    # is only written when the detection pipeline runs, so
    # older reports can legitimately have no per-pothole
    # geometry.
    #
    # This endpoint previously answered 404 in that case,
    # which made the whole 3D page blank because the frontend
    # had nothing to render.
    #
    # The scene is now always returned, the report row
    # supplies the real counts, and missing data is surfaced
    # through the payload "warnings" list instead of hiding
    # the page.
    # ------------------------------------------------------

    metadata, metadata_source = load_report_metadata(
        report_id
    )

    return build_immersive_road_scene(
        report,
        metadata,
        metadata_source=metadata_source,
    )


@router.get("/road-view")
def get_latest_road_view(
    db: Session = Depends(get_db),
):

    report = (
        db.query(ReportModel)
        .order_by(
            ReportModel.id.desc()
        )
        .first()
    )

    if not report:

        raise HTTPException(
            status_code=404,
            detail="No reports available.",
        )

    metadata, metadata_source = load_report_metadata(
        report.id
    )

    return build_immersive_road_scene(
        report,
        metadata,
        metadata_source=metadata_source,
    )


@router.get("/reports-list")
def get_reports_list(
    db: Session = Depends(get_db),
):

    reports = (
        db.query(ReportModel)
        .order_by(
            ReportModel.id.desc()
        )
        .all()
    )

    return {
        "success": True,
        "reports": [
            {
                "id": report.id,
                "media_type": report.media_type,
                "pothole_count": (
                    report.pothole_count
                ),
                "severity": report.severity,
                "created_at": str(
                    getattr(
                        report,
                        "created_at",
                        "",
                    )
                ),
            }
            for report in reports
        ],
    }