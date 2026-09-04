# backend/schemas.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ReportCreate(BaseModel):
    media_type: str
    media_path: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = "Unknown"
    pothole_count: int
    severity: str
    confidence: float

class ReportResponse(ReportCreate):
    id: int
    result_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class HotspotResponse(BaseModel):
    location_name: str
    latitude: float
    longitude: float
    report_count: int
    total_potholes: int
    highest_severity: str
    hotspot_level: str