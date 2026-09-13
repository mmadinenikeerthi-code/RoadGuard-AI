# ==========================================================
# backend/main.py
# ROADGUARD AI BACKEND
# ==========================================================

from fastapi import FastAPI
from fastapi.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles


# ==========================================================
# DATABASE
# ==========================================================

from backend.database import (

    engine,

    Base

)


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

    hotspots

)


# ==========================================================
# CONFIG
# ==========================================================

from backend.config import (

    BASE_DIR,

    UPLOAD_DIR,

    RESULTS_DIR

)


# ==========================================================
# CREATE DATABASE TABLES
# ==========================================================

Base.metadata.create_all(

    bind=engine

)


# ==========================================================
# CREATE FASTAPI APPLICATION
# ==========================================================

app = FastAPI(

    title="RoadGuard AI API",

    description=(

        "AI-Powered Pothole Detection & "
        "Location-Based Road Monitoring System"

    ),

    version="1.0.0"

)


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)


# ==========================================================
# STATIC FILES - UPLOADS
# ==========================================================

app.mount(

    "/uploads",

    StaticFiles(

        directory=str(UPLOAD_DIR)

    ),

    name="uploads"

)


# ==========================================================
# STATIC FILES - RESULTS
# ==========================================================

app.mount(

    "/results",

    StaticFiles(

        directory=str(RESULTS_DIR)

    ),

    name="results"

)


# ==========================================================
# INCLUDE DETECTION ROUTER
# ==========================================================

app.include_router(

    detection.router

)


# ==========================================================
# INCLUDE REPORTS ROUTER
# ==========================================================

app.include_router(

    reports.router

)


# ==========================================================
# INCLUDE MAP ROUTER
# ==========================================================

app.include_router(

    map.router

)


# ==========================================================
# INCLUDE 3D ROUTER
# ==========================================================

app.include_router(

    three_d.router

)


# ==========================================================
# INCLUDE HOTSPOTS ROUTER
# ==========================================================

app.include_router(

    hotspots.router

)


# ==========================================================
# ROOT ENDPOINT
# ==========================================================

@app.get("/")
def read_root():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


# ==========================================================
# API HEALTH CHECK
# ==========================================================

@app.get("/health")
def health_check():

    return {

        "success": True,

        "status": "healthy",

        "system": "RoadGuard AI"

    }