# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.database import engine, Base
from backend.routers import detection, reports, map
from backend.config import UPLOAD_DIR, RESULTS_DIR

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RoadGuard AI API",
    description="AI-Powered Pothole Detection & Location-Based Road Monitoring System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/results", StaticFiles(directory=RESULTS_DIR), name="results")

app.include_router(detection.router)
app.include_router(reports.router)
app.include_router(map.router)

@app.get("/")
def read_root():
    return {"status": "online", "system": "RoadGuard AI Engine Active"}