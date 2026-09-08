from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from backend.database import get_db
from backend.models import ReportModel
from backend.schemas import MapLocationResponse

router = APIRouter(
    prefix="/api/map",
    tags=["Map"]
)


@router.get("/locations", response_model=Dict[str, Any])
def get_map_locations(db: Session = Depends(get_db)):
    try:
        reports = db.query(ReportModel).filter(
            ReportModel.latitude.isnot(None),
            ReportModel.longitude.isnot(None)
        ).all()

        locations = [
            {
                "id": r.id,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "location_name": r.location_name or "Unknown Location",
                "pothole_count": r.pothole_count or 0,
                "severity": r.severity or "LOW",
                "confidence": r.confidence or 0.0
            }
            for r in reports
        ]

        return {
            "success": True,
            "locations": locations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving map locations: {str(e)}")