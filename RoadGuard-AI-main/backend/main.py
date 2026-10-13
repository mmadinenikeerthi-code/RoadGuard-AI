
"""
============================================================
RoadGuard AI - FastAPI Application Entry Point
============================================================

Existing features:
- YOLO image/video detection
- Live WebSocket detection
- SQLite reports
- Leaflet / OpenStreetMap
- Hotspots and analytics
- COLMAP / Three.js reconstruction

Cesium features:
- Cesium ion token configuration
- GET /api/map/config
- GET /api/cesium/config (compatibility endpoint)
- Existing /3d-view page preserved
- Existing /3d API preserved
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.database import Base, engine
from backend import models

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
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"

UPLOADS_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"


# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
    logger.info("Environment configuration loaded.")

except ImportError:
    logger.warning(
        "python-dotenv is not installed. "
        "Install it using: pip install python-dotenv"
    )

CESIUM_ION_TOKEN = os.getenv(
    "CESIUM_ION_TOKEN",
    "",
).strip()

if CESIUM_ION_TOKEN:
    logger.info("Cesium ion token is configured.")
else:
    logger.warning(
        "CESIUM_ION_TOKEN is missing. "
        "Check the project-root .env file."
    )


# ============================================================
# REQUIRED DIRECTORIES
# ============================================================

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="RoadGuard AI",
    description=(
        "AI-powered pothole detection, "
        "live GPS road monitoring, "
        "OpenStreetMap visualization, "
        "Cesium satellite visualization, "
        "analytics, and COLMAP-based "
        "3D road reconstruction."
    ),
    version="2.3.0",
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
# CESIUM CONFIGURATION
# ============================================================

def get_cesium_config():
    """
    Return the Cesium configuration.

    Both Cesium configuration endpoints use this function
    to avoid inconsistent responses.
    """

    if not CESIUM_ION_TOKEN:
        return {
            "configured": False,
            "cesium_token": "",
            "message": (
                "Cesium ion token is missing. "
                "Add CESIUM_ION_TOKEN to the project-root .env file."
            ),
        }

    return {
        "configured": True,
        "cesium_token": CESIUM_ION_TOKEN,
        "message": "Cesium configuration loaded.",
    }


@app.get(
    "/api/map/config",
    tags=["Cesium Map"],
)
async def cesium_map_config():
    """Original Cesium configuration endpoint."""
    return get_cesium_config()


@app.get(
    "/api/cesium/config",
    tags=["Cesium Map"],
)
async def cesium_config():
    """
    Compatibility endpoint for the Cesium frontend.

    Fixes:
    Request failed (404): /api/cesium/config
    """
    return get_cesium_config()


# ============================================================
# STATIC FILE DIRECTORIES
# ============================================================

if FRONTEND_DIR.is_dir():
    app.mount(
        "/frontend",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="frontend",
    )

CSS_DIR = FRONTEND_DIR / "css"
JS_DIR = FRONTEND_DIR / "js"

if CSS_DIR.is_dir():
    app.mount(
        "/css",
        StaticFiles(directory=str(CSS_DIR)),
        name="css",
    )

if JS_DIR.is_dir():
    app.mount(
        "/js",
        StaticFiles(directory=str(JS_DIR)),
        name="js",
    )


# ============================================================
# UPLOADS
# ============================================================

if UPLOADS_DIR.is_dir():
    app.mount(
        "/uploads",
        StaticFiles(directory=str(UPLOADS_DIR)),
        name="uploads",
    )


# ============================================================
# RESULTS
# ============================================================

if RESULTS_DIR.is_dir():
    app.mount(
        "/results",
        StaticFiles(directory=str(RESULTS_DIR)),
        name="results",
    )


# ============================================================
# EXISTING API ROUTERS
# ============================================================

# YOLO detection
app.include_router(detection.router)

# Stored reports
app.include_router(reports.router)

# Existing Leaflet / OpenStreetMap API
app.include_router(map.router)

# Hotspot API
app.include_router(hotspots.router)

# COLMAP photogrammetry
app.include_router(photogrammetry.router)

# Existing 3D API
app.include_router(three_d.router)

# Live detection WebSocket
app.include_router(live_detection.router)

# Analytics
app.include_router(analytics.router)


# ============================================================
# ROOT PAGE
# ============================================================

@app.get("/", include_in_schema=False)
async def root():
    """Serve the application home page."""

    template_index = TEMPLATES_DIR / "index.html"
    frontend_index = FRONTEND_DIR / "index.html"

    if template_index.is_file():
        return FileResponse(str(template_index))

    if frontend_index.is_file():
        return FileResponse(str(frontend_index))

    return {
        "name": "RoadGuard AI",
        "status": "active",
        "version": "2.3.0",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "healthy",
        "service": "RoadGuard AI",
        "version": "2.3.0",
        "live_detection": "/api/live/detect",
        "map": "/map",
        "cesium_map_config": "/api/map/config",
        "cesium_config": "/api/cesium/config",
        "analytics": "/api/analytics",
        "three_d_api": "/3d",
        "three_d_viewer": "/3d-view",
    }


# ============================================================
# API INFORMATION
# ============================================================

@app.get("/api", tags=["System"])
async def api_info():
    return {
        "application": "RoadGuard AI",
        "version": "2.3.0",
        "modules": {
            "detection": True,
            "live_detection": True,
            "reports": True,
            "map": True,
            "cesium": True,
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
            "existing_provider": "OpenStreetMap",
            "existing_frontend": "Leaflet",
            "cesium_config": "/api/map/config",
            "cesium_config_compatibility": "/api/cesium/config",
        },
        "analytics": {
            "summary": "/api/analytics",
            "reports": "/api/analytics/reports",
            "page": "/analytics",
        },
        "reconstruction": {
            "engine": "COLMAP",
            "renderer": "Three.js",
            "viewer": "/3d-view",
            "api": "/3d",
        },
    }


# ============================================================
# FRONTEND PAGE HELPER
# ============================================================

def _page_path(filename: str) -> Path | None:
    """
    Find a page in frontend/templates/ first,
    then directly inside frontend/.
    """

    template_path = TEMPLATES_DIR / filename
    frontend_path = FRONTEND_DIR / filename

    if template_path.is_file():
        return template_path

    if frontend_path.is_file():
        return frontend_path

    return None


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    path = _page_path("index.html")

    if path:
        return FileResponse(str(path))

    return {"error": "Dashboard not found."}


# ============================================================
# DETECTION PAGE
# ============================================================

@app.get("/detect", include_in_schema=False)
async def detect_page():
    path = _page_path("detect.html")

    if path:
        return FileResponse(str(path))

    return {"error": "Detection page not found."}


# ============================================================
# MAP PAGE
# ============================================================

@app.get("/map", include_in_schema=False)
async def map_page():
    path = _page_path("map.html")

    if path:
        return FileResponse(str(path))

    return {"error": "Map page not found."}


# ============================================================
# REPORTS PAGE
# ============================================================

@app.get("/reports", include_in_schema=False)
async def reports_page():
    path = _page_path("reports.html")

    if path:
        return FileResponse(str(path))

    return {"error": "Reports page not found."}


# ============================================================
# ANALYTICS PAGE
# ============================================================

@app.get("/analytics", include_in_schema=False)
async def analytics_page():
    path = _page_path("analytics.html")

    if path:
        return FileResponse(str(path))

    return {
        "error": "Analytics page not found.",
        "expected_locations": [
            str(TEMPLATES_DIR / "analytics.html"),
            str(FRONTEND_DIR / "analytics.html"),
        ],
    }


# ============================================================
# 3D VIEWER PAGE
# ============================================================

# /3d-view = frontend HTML page
# /3d      = existing API from three_d.router

@app.get("/3d-view", include_in_schema=False)
async def three_d_page():
    path = _page_path("3d_view.html")

    if path:
        return FileResponse(str(path))

    return {
        "error": "3D viewer not found.",
        "expected_locations": [
            str(TEMPLATES_DIR / "3d_view.html"),
            str(FRONTEND_DIR / "3d_view.html"),
        ],
    }


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize missing database tables and log startup details.

    create_all creates missing tables; it does not migrate
    existing table schemas.
    """

    logger.info("========================================")
    logger.info("RoadGuard AI Engine Starting")
    logger.info("========================================")

    Base.metadata.create_all(bind=engine)

    logger.info("Database tables initialized.")
    logger.info("Project directory: %s", BASE_DIR)
    logger.info("Frontend directory: %s", FRONTEND_DIR)
    logger.info("Templates directory: %s", TEMPLATES_DIR)
    logger.info("Uploads directory: %s", UPLOADS_DIR)
    logger.info("Results directory: %s", RESULTS_DIR)

    logger.info("YOLO detection API registered.")
    logger.info("Live WebSocket: /api/live/detect")
    logger.info("Existing Leaflet map: /map")
    logger.info("Cesium config: /api/map/config")
    logger.info("Cesium compatibility: /api/cesium/config")
    logger.info("Reports page: /reports")
    logger.info("Analytics page: /analytics")
    logger.info("Analytics API: /api/analytics")
    logger.info("Analytics reports API: /api/analytics/reports")
    logger.info("3D viewer: /3d-view")
    logger.info("Existing 3D API: /3d")
    logger.info("Frontend static files: /frontend")
    logger.info("API documentation: /docs")


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("RoadGuard AI Engine shutting down.")
