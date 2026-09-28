# ==========================================================
# backend/main.py
# ROADGUARD AI BACKEND
# ==========================================================

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# ==========================================================
# DATABASE
# ==========================================================

from backend.database import engine, Base


# ==========================================================
# IMPORT MODELS BEFORE CREATE_ALL
# ==========================================================

import backend.models


# ==========================================================
# ROUTERS
# ==========================================================

from backend.routers import (
    detection,
    reports,
    map,
    three_d,
    hotspots,
    routing,
    photogrammetry,
)


# ==========================================================
# CONFIG
# ==========================================================

from backend.config import (
    BASE_DIR,
    UPLOAD_DIR,
    RESULTS_DIR,
)


# ==========================================================
# CREATE DATABASE TABLES
# ==========================================================

Base.metadata.create_all(bind=engine)


# ==========================================================
# CREATE FASTAPI APPLICATION
# ==========================================================

app = FastAPI(
    title="RoadGuard AI API",
    description=(
        "AI-Powered Pothole Detection & "
        "Location-Based Road Monitoring System"
    ),
    version="1.0.0",
)


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# FRONTEND DIRECTORIES
# ==========================================================

FRONTEND_DIR = BASE_DIR / "frontend"

FRONTEND_CSS_DIR = (
    FRONTEND_DIR / "css"
)

FRONTEND_JS_DIR = (
    FRONTEND_DIR / "js"
)

FRONTEND_TEMPLATES_DIR = (
    FRONTEND_DIR / "templates"
)


# ==========================================================
# CREATE DIRECTORIES IF MISSING
# ==========================================================

for directory in (
    FRONTEND_DIR,
    FRONTEND_CSS_DIR,
    FRONTEND_JS_DIR,
    FRONTEND_TEMPLATES_DIR,
):

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ==========================================================
# TEMPLATE CONFIGURATION
# ==========================================================

templates = Jinja2Templates(
    directory=str(
        FRONTEND_TEMPLATES_DIR
    )
)


# ==========================================================
# STATIC FILES - FRONTEND
# ==========================================================

# /static -> frontend/
app.mount(
    "/static",
    StaticFiles(
        directory=str(
            FRONTEND_DIR
        )
    ),
    name="static",
)


# /css -> frontend/css
app.mount(
    "/css",
    StaticFiles(
        directory=str(
            FRONTEND_CSS_DIR
        )
    ),
    name="frontend-css",
)


# /js -> frontend/js
app.mount(
    "/js",
    StaticFiles(
        directory=str(
            FRONTEND_JS_DIR
        )
    ),
    name="frontend-js",
)


# ==========================================================
# STATIC FILES - UPLOADS
# ==========================================================

app.mount(
    "/uploads",
    StaticFiles(
        directory=str(
            UPLOAD_DIR
        )
    ),
    name="uploads",
)


# ==========================================================
# STATIC FILES - RESULTS
# ==========================================================

app.mount(
    "/results",
    StaticFiles(
        directory=str(
            RESULTS_DIR
        )
    ),
    name="results",
)


# ==========================================================
# API ROUTERS
# ==========================================================


# ----------------------------------------------------------
# Detection
# ----------------------------------------------------------

app.include_router(
    detection.router
)


# ----------------------------------------------------------
# Reports
# ----------------------------------------------------------

app.include_router(
    reports.router
)


# ----------------------------------------------------------
# Map
# ----------------------------------------------------------

app.include_router(
    map.router
)


# ----------------------------------------------------------
# 3D Visualization API
# ----------------------------------------------------------

app.include_router(
    three_d.router
)


# ----------------------------------------------------------
# Hotspots
# ----------------------------------------------------------

app.include_router(
    hotspots.router
)


# ----------------------------------------------------------
# Photogrammetry / COLMAP 3D Reconstruction
# ----------------------------------------------------------

app.include_router(
    photogrammetry.router,
    tags=["Photogrammetry"],
    include_in_schema=True,
)


# ----------------------------------------------------------
# Routing / Navigation
# ----------------------------------------------------------

app.include_router(
    routing.router
)


# ==========================================================
# FRONTEND PAGE HELPER
# ==========================================================

def _serve_page(
    filename: str,
) -> FileResponse:
    """
    Serve frontend HTML files from:

        frontend/templates/

    Example:

        frontend/templates/index.html
        frontend/templates/detect.html
        frontend/templates/map.html
        frontend/templates/reports.html
        frontend/templates/3d_view.html
        frontend/templates/navigation.html
    """

    page = (
        FRONTEND_TEMPLATES_DIR
        / filename
    )

    if not page.is_file():

        raise HTTPException(
            status_code=404,
            detail=(
                f"Frontend page not found: "
                f"{filename}"
            ),
        )

    return FileResponse(
        path=str(page)
    )


# ==========================================================
# FRONTEND PAGE ROUTES
# ==========================================================


# ----------------------------------------------------------
# Dashboard
# ----------------------------------------------------------

@app.get("/")
def read_root():

    return _serve_page(
        "index.html"
    )


# ----------------------------------------------------------
# Detection
# ----------------------------------------------------------

@app.get("/detect")
def detect_page():

    return _serve_page(
        "detect.html"
    )


# ----------------------------------------------------------
# Map
# ----------------------------------------------------------

@app.get("/map")
def map_page():

    return _serve_page(
        "map.html"
    )


# ----------------------------------------------------------
# Reports
# ----------------------------------------------------------

@app.get("/reports")
def reports_page():

    return _serve_page(
        "reports.html"
    )


# ----------------------------------------------------------
# Analytics
# ----------------------------------------------------------

@app.get("/analytics")
def analytics_page():

    # Your current project does not have
    # a separate analytics.html file.
    #
    # Therefore use the dashboard.

    return _serve_page(
        "index.html"
    )


# ----------------------------------------------------------
# 3D Road View
# ----------------------------------------------------------

@app.get("/3d")
def three_d_page():

    # IMPORTANT:
    #
    # This is the NEW RoadGuard 3D viewer.
    #
    # It loads:
    #
    # frontend/templates/3d_view.html
    #
    # which loads:
    #
    # frontend/js/roadguard-3d.js
    #
    # The JavaScript then loads the
    # COLMAP / photogrammetry PLY.
    #

    return _serve_page(
        "3d_view.html"
    )


# ----------------------------------------------------------
# Navigation
# ----------------------------------------------------------

@app.get("/navigation")
def navigation_page_direct():

    return _serve_page(
        "navigation.html"
    )


# ==========================================================
# DIRECT HTML PAGE ALIASES
# ==========================================================

FRONTEND_PAGES = {
    "index.html",
    "detect.html",
    "map.html",
    "reports.html",
    "3d_view.html",
    "navigation.html",
}


# ==========================================================
# FRIENDLY PAGE ALIASES
# ==========================================================

FRONTEND_PAGE_ALIASES = {

    # Old 3D page alias
    "three": "3d_view.html",

    # New RoadGuard 3D page
    "3d": "3d_view.html",

    # Navigation
    "navigation": "navigation.html",
}


# ==========================================================
# /page.html ROUTES
# ==========================================================

@app.get(
    "/{page_name}.html",
    response_class=HTMLResponse,
)
def html_page_alias(
    page_name: str,
):

    filename = (
        FRONTEND_PAGE_ALIASES.get(
            page_name,
            f"{page_name}.html",
        )
    )

    if filename not in FRONTEND_PAGES:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Page not found: "
                f"{filename}"
            ),
        )

    return _serve_page(
        filename
    )


# ==========================================================
# 3D ROAD INSPECTION PAGE
# ==========================================================

@app.get(
    "/3d-view",
    response_class=HTMLResponse,
)
async def three_d_view(
    request: Request,
):

    return templates.TemplateResponse(
        request,
        "3d_view.html",
        {},
    )


# ==========================================================
# NAVIGATION / ROUTE PLANNER PAGE
# ==========================================================

@app.get(
    "/navigation-view",
    response_class=HTMLResponse,
)
async def navigation_view(
    request: Request,
):

    return templates.TemplateResponse(
        request,
        "navigation.html",
        {},
    )


# ==========================================================
# API HEALTH CHECK
# ==========================================================

@app.get("/health")
def health_check():

    return {
        "success": True,
        "status": "healthy",
        "system": "RoadGuard AI",
    }