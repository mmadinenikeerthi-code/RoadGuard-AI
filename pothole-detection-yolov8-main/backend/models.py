# backend/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from backend.database import Base

class ReportModel(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    media_type = Column(String, nullable=False) # image / video
    media_path = Column(String, nullable=False)
    result_path = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_name = Column(String, default="Unknown")
    pothole_count = Column(Integer, default=0)
    severity = Column(String, default="Minor")
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)