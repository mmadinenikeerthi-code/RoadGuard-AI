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
            ReportModel.longitude.isnot(None),
            ~((ReportModel.latitude == 0.0) & (ReportModel.longitude == 0.0))
        ).all()

        locations = [
            {
                "id": r.id,
                "latitude": float(r.latitude),
                "longitude": float(r.longitude),
                "location_name": r.location_name or "Unknown Location",
                "pothole_count": r.pothole_count or 0,
                "severity": r.severity or "LOW",
                "confidence": r.confidence or 0.0
            }
            for r in reports
            if r.latitude is not None
            and r.longitude is not None
            and not (float(r.latitude) == 0.0 and float(r.longitude) == 0.0)
            and -90.0 <= float(r.latitude) <= 90.0
            and -180.0 <= float(r.longitude) <= 180.0
        ]

        return {
            "success": True,
            "locations": locations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving map locations: {str(e)}")