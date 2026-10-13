# ==========================================================
# backend/routers/hotspots.py
# ROADGUARD AI - HOTSPOTS API
# ==========================================================

from fastapi import (
    APIRouter,
    Depends
)

from sqlalchemy.orm import Session


# ==========================================================
# DATABASE
# ==========================================================

from backend.database import get_db


# ==========================================================
# MODEL
# ==========================================================

from backend.models import ReportModel


# ==========================================================
# HOTSPOT SERVICES
# ==========================================================

from backend.services.hotspot_service import (

    get_hotspots_service,

    get_hotspot_summary_service

)


# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(

    prefix="/hotspots",

    tags=["Hotspots"]

)


# ==========================================================
# ROOT / TEST ENDPOINT
# ==========================================================

@router.get("/")
def hotspots_home():

    return {

        "success": True,

        "message": "RoadGuard AI Hotspots API is working"

    }


# ==========================================================
# GET ALL HOTSPOTS
# ==========================================================

@router.get("")
def get_hotspots(

    db: Session = Depends(get_db)

):


    # ------------------------------------------------------
    # GET REPORTS FROM DATABASE
    # ------------------------------------------------------

    reports = (

        db.query(ReportModel)

        .order_by(

            ReportModel.created_at.desc()

        )

        .all()

    )


    # ------------------------------------------------------
    # GENERATE HOTSPOTS
    # ------------------------------------------------------

    hotspots = get_hotspots_service(
        reports
    )


    # ------------------------------------------------------
    # RETURN RESPONSE
    # ------------------------------------------------------

    return {

        "success": True,

        "total_reports": len(
            reports
        ),

        "total_hotspots": len(
            hotspots
        ),

        "hotspots": hotspots

    }


# ==========================================================
# GET HOTSPOT SUMMARY
# ==========================================================

@router.get("/summary")
def get_hotspot_summary(

    db: Session = Depends(get_db)

):


    # ------------------------------------------------------
    # GET REPORTS
    # ------------------------------------------------------

    reports = (

        db.query(ReportModel)

        .order_by(

            ReportModel.created_at.desc()

        )

        .all()

    )


    # ------------------------------------------------------
    # GENERATE SUMMARY
    # ------------------------------------------------------

    summary = get_hotspot_summary_service(
        reports
    )


    return summary


# ==========================================================
# GET HOTSPOTS BY SEVERITY
# ==========================================================

@router.get("/severity/{severity}")
def get_hotspots_by_severity(

    severity: str,

    db: Session = Depends(get_db)

):


    # ------------------------------------------------------
    # NORMALIZE SEVERITY
    # ------------------------------------------------------

    severity = severity.upper()


    # ------------------------------------------------------
    # VALID SEVERITY
    # ------------------------------------------------------

    valid_severities = [

        "LOW",

        "MODERATE",

        "HIGH",

        "CRITICAL"

    ]


    if severity not in valid_severities:

        return {

            "success": False,

            "message": (
                "Invalid severity. "
                "Use LOW, MODERATE, HIGH, or CRITICAL."
            ),

            "hotspots": []

        }


    # ------------------------------------------------------
    # GET REPORTS
    # ------------------------------------------------------

    reports = (

        db.query(ReportModel)

        .order_by(

            ReportModel.created_at.desc()

        )

        .all()

    )


    # ------------------------------------------------------
    # GENERATE HOTSPOTS
    # ------------------------------------------------------

    hotspots = get_hotspots_service(
        reports
    )


    # ------------------------------------------------------
    # FILTER HOTSPOTS
    # ------------------------------------------------------

    filtered_hotspots = [

        hotspot

        for hotspot in hotspots

        if hotspot.get("severity") == severity

    ]


    # ------------------------------------------------------
    # RETURN
    # ------------------------------------------------------

    return {

        "success": True,

        "severity": severity,

        "total_hotspots": len(
            filtered_hotspots
        ),

        "hotspots": filtered_hotspots

    }


# ==========================================================
# GET SINGLE HOTSPOT
# ==========================================================

@router.get("/{hotspot_id}")
def get_hotspot_by_id(

    hotspot_id: int,

    db: Session = Depends(get_db)

):


    # ------------------------------------------------------
    # GET REPORTS
    # ------------------------------------------------------

    reports = (

        db.query(ReportModel)

        .order_by(

            ReportModel.created_at.desc()

        )

        .all()

    )


    # ------------------------------------------------------
    # GENERATE HOTSPOTS
    # ------------------------------------------------------

    hotspots = get_hotspots_service(
        reports
    )


    # ------------------------------------------------------
    # FIND HOTSPOT
    # ------------------------------------------------------

    for hotspot in hotspots:

        if hotspot.get("id") == hotspot_id:

            return {

                "success": True,

                "hotspot": hotspot

            }


    # ------------------------------------------------------
    # NOT FOUND
    # ------------------------------------------------------

    return {

        "success": False,

        "message": "Hotspot not found"

    }