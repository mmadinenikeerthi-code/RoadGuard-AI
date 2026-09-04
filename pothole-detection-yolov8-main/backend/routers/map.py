# backend/routers/map.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models import ReportModel
from backend.schemas import HotspotResponse
from backend.services.hotspot_service import get_hotspots_service

router = APIRouter(prefix="/api/map", tags=["Map Intelligence"])

@router.get("/reports")
def get_map_reports(db: Session = Depends(get_db)):
    reports = db.query(ReportModel).filter(ReportModel.latitude.isnot(None), ReportModel.longitude.isnot(None)).all()
    return [{
        "id": r.id,
        "latitude": r.latitude,
        "longitude": r.longitude,
        "location_name": r.location_name,
        "pothole_count": r.pothole_count,
        "severity": r.severity,
        "created_at": r.created_at
    } for r in reports]

@router.get("/hotspots", response_model=List[HotspotResponse])
def get_hotspots(db: Session = Depends(get_db)):
    return get_hotspots_service(db)