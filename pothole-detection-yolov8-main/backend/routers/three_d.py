# ==========================================================
# backend/routers/three_d.py
# ROADGUARD AI - 3D ROUTER
# ==========================================================

from fastapi import APIRouter


from backend.services.three_d_service import (

    build_3d_scene,

    get_3d_summary

)


router = APIRouter(

    prefix="/3d",

    tags=["3D Visualization"]

)


# ==========================================================
# TEST ROUTE
# ==========================================================

@router.get("/")
def three_d_home():

    return {

        "success": True,

        "message":
            "RoadGuard AI 3D Visualization API is working"

    }


# ==========================================================
# SAMPLE DATA
# ==========================================================

def get_sample_reports():

    return [

        {

            "latitude": 15.8281,

            "longitude": 78.0373,

            "pothole_count": 12,

            "severity": "HIGH",

            "location_name": "Road Zone A",

            "confidence": 0.92

        },

        {

            "latitude": 15.8290,

            "longitude": 78.0380,

            "pothole_count": 5,

            "severity": "MODERATE",

            "location_name": "Road Zone B",

            "confidence": 0.85

        },

        {

            "latitude": 15.8300,

            "longitude": 78.0390,

            "pothole_count": 22,

            "severity": "CRITICAL",

            "location_name": "Road Zone C",

            "confidence": 0.96

        }

    ]


# ==========================================================
# GET 3D SCENE
# ==========================================================

@router.get("/scene")
def get_scene():

    reports = get_sample_reports()


    return build_3d_scene(
        reports
    )


# ==========================================================
# GET 3D SUMMARY
# ==========================================================

@router.get("/summary")
def get_summary():

    reports = get_sample_reports()


    return get_3d_summary(
        reports
    )