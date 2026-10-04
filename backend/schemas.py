from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class ReportBase(BaseModel):
    media_type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = "Unknown Location"


class ReportCreate(ReportBase):
    pass


class ReportResponse(ReportBase):
    id: int
    media_path: str
    result_path: Optional[str] = None
    pothole_count: int
    severity: str
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportSummary(BaseModel):
    total_reports: int
    total_potholes: int
    low_severity: int
    moderate_severity: int
    high_severity: int
    critical_severity: int


class MapLocationResponse(BaseModel):
    id: int
    latitude: float
    longitude: float
    location_name: str
    pothole_count: int
    severity: str
    confidence: float


class HotspotResponse(BaseModel):
    id: int
    latitude: float
    longitude: float
    location_name: str
    report_count: int
    pothole_count: int
    average_confidence: float
    severity: str
    color: str


class HotspotSummaryResponse(BaseModel):
    total_reports: int
    total_potholes: int
    active_hotspots: int
    critical_zones: int
    high_zones: int
    moderate_zones: int
    low_zones: int


class ThreeDReportItem(BaseModel):
    id: int
    latitude: float
    longitude: float
    location_name: str
    pothole_count: int
    severity: str
    confidence: float


class ThreeDDataResponse(BaseModel):
    success: bool
    total_potholes: int
    reports: List[ThreeDReportItem]