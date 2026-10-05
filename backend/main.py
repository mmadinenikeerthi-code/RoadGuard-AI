"""
============================================================
RoadGuard AI
FastAPI Application Entry Point
============================================================

Architecture
------------

YOLO Detection
      |
      +---- Normal image/video detection
      |
      +---- Live WebSocket detection
                    |
                    v
              GPS coordinates
                    |
                    v
              SQLite reports
                    |
                    v
              Leaflet / OSM


Analytics
      |
      v
  Stored ReportModel data
      |
      +---- Total reports
      +---- Total potholes
      +---- Severity statistics
      +---- Confidence statistics
      +---- Reports over time
      +---- Recent reports


Photogrammetry
      |
      v
    COLMAP
      |
      +---- Sparse reconstruction
      +---- Dense MVS
      +---- Point cloud
      +---- Real mesh
                    |
                    v
                Three.js

Important:
    - No procedural/fake road geometry.
    - No fake GPS coordinates.
    - No legacy navigation router.
    - 3D viewer uses /3d-view.
    - /3d remains the real 3D API endpoint.
    - Analytics uses real stored report data.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import (
    analytics,
    detection,
    hotspots,
    live_detection,
    map,
    photogrammetry,
    reports,
    three_d,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger("roadguard")


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"

UPLOADS_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"


# ============================================================
# DIRECTORIES
# ============================================================

UPLOADS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="RoadGuard AI",
    description=(
        "AI-powered pothole detection, "
        "live GPS road monitoring, "
        "OpenStreetMap visualization, "
        "analytics, "
        "and COLMAP-based 3D road reconstruction."
    ),
    version="2.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STATIC DIRECTORIES
# ============================================================

# ------------------------------------------------------------
# Main frontend directory
#
# Correct paths:
#
#   /frontend/css/style.css
#   /frontend/js/map.js
#   /frontend/js/detect.js
# ------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount(
        "/frontend",
        StaticFiles(
            directory=str(FRONTEND_DIR)
        ),
        name="frontend",
    )


# ------------------------------------------------------------
# STATIC COMPATIBILITY PATHS
#
# Some older/stale HTML pages still request:
#
#   /css/style.css
#   /js/config.js
#   /js/map.js
#   /js/detect.js
#
# These mounts make those paths work too.
#
# This does NOT replace /frontend/... paths.
# ------------------------------------------------------------

CSS_DIR = FRONTEND_DIR / "css"
JS_DIR = FRONTEND_DIR / "js"


if CSS_DIR.exists():
    app.mount(
        "/css",
        StaticFiles(
            directory=str(CSS_DIR)
        ),
        name="css",
    )


if JS_DIR.exists():
    app.mount(
        "/js",
        StaticFiles(
            directory=str(JS_DIR)
        ),
        name="js",
    )


# ------------------------------------------------------------
# UPLOADS
# ------------------------------------------------------------

if UPLOADS_DIR.exists():
    app.mount(
        "/uploads",
        StaticFiles(
            directory=str(UPLOADS_DIR)
        ),
        name="uploads",
    )


# ------------------------------------------------------------
# RESULTS
# ------------------------------------------------------------

if RESULTS_DIR.exists():
    app.mount(
        "/results",
        StaticFiles(
            directory=str(RESULTS_DIR)
        ),
        name="results",
    )


# ============================================================
# API ROUTERS
# ============================================================

# ------------------------------------------------------------
# YOLO DETECTION
# ------------------------------------------------------------

app.include_router(
    detection.router
)


# ------------------------------------------------------------
# REPORTS
# ------------------------------------------------------------

app.include_router(
    reports.router
)


# ------------------------------------------------------------
# OSM / LEAFLET MAP
# ------------------------------------------------------------

app.include_router(
    map.router
)


# ------------------------------------------------------------
# HOTSPOTS
# ------------------------------------------------------------

app.include_router(
    hotspots.router
)


# ------------------------------------------------------------
# PHOTOGRAMMETRY / COLMAP
# ------------------------------------------------------------

app.include_router(
    photogrammetry.router
)


# ------------------------------------------------------------
# REAL 3D API
#
# /3d/... = API
# /3d-view = HTML viewer
# ------------------------------------------------------------

app.include_router(
    three_d.router
)


# ------------------------------------------------------------
# LIVE DETECTION
#
# Camera + YOLO + GPS WebSocket
# ------------------------------------------------------------

app.include_router(
    live_detection.router
)


# ------------------------------------------------------------
# ANALYTICS
#
# Real analytics calculated from stored ReportModel records.
#
# Endpoints supplied by analytics.py:
#
#   /api/analytics
#   /api/analytics/reports
# ------------------------------------------------------------

app.include_router(
    analytics.router
)


# ============================================================
# ROOT
# ============================================================

@app.get(
    "/",
    include_in_schema=False,
)
async def root():
    """
    RoadGuard AI application home.
    """

    template_index = TEMPLATES_DIR / "index.html"
    frontend_index = FRONTEND_DIR / "index.html"

    if template_index.exists():
        return FileResponse(
            str(template_index)
        )

    if frontend_index.exists():
        return FileResponse(
            str(frontend_index)
        )

    return {
        "name": "RoadGuard AI",
        "status": "active",
        "version": "2.1.0",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health",
    tags=["System"],
)
async def health():
    return {
        "status": "healthy",
        "service": "RoadGuard AI",
        "version": "2.1.0",

        "live_detection":
            "/api/live/detect",

        "map":
            "OpenStreetMap / Leaflet",

        "analytics":
            "/api/analytics",

        "three_d":
            "COLMAP / Three.js",
    }


# ============================================================
# API INFORMATION
# ============================================================

@app.get(
    "/api",
    tags=["System"],
)
async def api_info():
    return {
        "application": "RoadGuard AI",

        "version": "2.1.0",

        "modules": {
            "detection": True,
            "live_detection": True,
            "reports": True,
            "map": True,
            "hotspots": True,
            "analytics": True,
            "photogrammetry": True,
            "three_d": True,
        },

        "detection": {
            "type": "YOLO",
        },

        "live_detection": {
            "protocol": "WebSocket",
            "endpoint": "/api/live/detect",
        },

        "mapping": {
            "provider": "OpenStreetMap",
            "frontend": "Leaflet",
        },

        "analytics": {
            "summary":
                "/api/analytics",

            "reports":
                "/api/analytics/reports",

            "page":
                "/analytics",
        },

        "reconstruction": {
            "engine": "COLMAP",
            "renderer": "Three.js",
            "viewer": "/3d-view",
        },
    }


# ============================================================
# PAGE HELPERS
# ============================================================

def _page_path(
    filename: str,
) -> Path | None:
    """
    Resolve a frontend page.

    Templates take priority over files directly
    inside frontend/.
    """

    template_path = TEMPLATES_DIR / filename
    frontend_path = FRONTEND_DIR / filename

    if template_path.exists():
        return template_path

    if frontend_path.exists():
        return frontend_path

    return None


# ============================================================
# FRONTEND PAGES
# ============================================================

# ------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------

@app.get(
    "/dashboard",
    include_in_schema=False,
)
async def dashboard():
    path = _page_path(
        "index.html"
    )

    if path:
        return FileResponse(
            str(path)
        )

    return {
        "error": "Dashboard not found."
    }


# ------------------------------------------------------------
# AI DETECTION PAGE
# ------------------------------------------------------------

@app.get(
    "/detect",
    include_in_schema=False,
)
async def detect_page():
    path = _page_path(
        "detect.html"
    )

    if path:
        return FileResponse(
            str(path)
        )

    return {
        "error": "Detection page not found."
    }


# ------------------------------------------------------------
# MAP PAGE
# ------------------------------------------------------------

@app.get(
    "/map",
    include_in_schema=False,
)
async def map_page():
    path = _page_path(
        "map.html"
    )

    if path:
        return FileResponse(
            str(path)
        )

    return {
        "error": "Map page not found."
    }


# ------------------------------------------------------------
# REPORTS PAGE
# ------------------------------------------------------------

@app.get(
    "/reports",
    include_in_schema=False,
)
async def reports_page():
    path = _page_path(
        "reports.html"
    )

    if path:
        return FileResponse(
            str(path)
        )

    return {
        "error": "Reports page not found."
    }


# ------------------------------------------------------------
# ANALYTICS PAGE
# ------------------------------------------------------------

@app.get(
    "/analytics",
    include_in_schema=False,
)
async def analytics_page():
    """
    RoadGuard AI Analytics dashboard.

    The page itself is only the frontend.
    Real analytics are loaded by analytics.html from:

        /api/analytics

    and:

        /api/analytics/reports
    """

    path = _page_path(
        "analytics.html"
    )

    if path:
        return FileResponse(
            str(path)
        )

    return {
        "error": "Analytics page not found.",
        "expected_locations": [
            str(TEMPLATES_DIR / "analytics.html"),
            str(FRONTEND_DIR / "analytics.html"),
        ],
    }


# ------------------------------------------------------------
# REAL COLMAP 3D VIEWER
# ------------------------------------------------------------

#
# IMPORTANT:
#
# /3d              = 3D API
# /3d-view         = visual HTML viewer
#
# Do NOT change /3d-view to /3d/.
#

@app.get(
    "/3d-view",
    include_in_schema=False,
)
async def three_d_page():

    path = _page_path(
        "3d_view.html"
    )

    if path:
        return FileResponse(
            str(path)
        )

    return {
        "error": "3D viewer not found."
    }


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    logger.info(
        "========================================"
    )

    logger.info(
        "RoadGuard AI Engine Starting"
    )

    logger.info(
        "========================================"
    )

    logger.info(
        "Project directory: %s",
        BASE_DIR,
    )

    logger.info(
        "Frontend directory: %s",
        FRONTEND_DIR,
    )

    logger.info(
        "Templates directory: %s",
        TEMPLATES_DIR,
    )

    logger.info(
        "Uploads directory: %s",
        UPLOADS_DIR,
    )

    logger.info(
        "Results directory: %s",
        RESULTS_DIR,
    )

    logger.info(
        "YOLO detection API registered"
    )

    logger.info(
        "Live WebSocket: /api/live/detect"
    )

    logger.info(
        "OSM / Leaflet map: /map"
    )

    logger.info(
        "Reports page: /reports"
    )

    logger.info(
        "Analytics page: /analytics"
    )

    logger.info(
        "Analytics API: /api/analytics"
    )

    logger.info(
        "Analytics reports API: "
        "/api/analytics/reports"
    )

    logger.info(
        "COLMAP 3D viewer: /3d-view"
    )

    logger.info(
        "3D API: /3d/"
    )

    logger.info(
        "Frontend static: /frontend"
    )

    logger.info(
        "Legacy CSS compatibility: /css"
    )

    logger.info(
        "Legacy JS compatibility: /js"
    )

    logger.info(
        "API documentation: /docs"
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():

    logger.info(
        "RoadGuard AI Engine shutting down."
    )