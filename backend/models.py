# ==========================================================
# backend/models.py
# ROADGUARD AI DATABASE MODELS
# ==========================================================

from sqlalchemy import (

    Column,

    Integer,

    String,

    Float,

    DateTime

)

from datetime import datetime


from backend.database import Base


# ==========================================================
# REPORT MODEL
# ==========================================================

class ReportModel(Base):


    # ======================================================
    # TABLE NAME
    # ======================================================

    __tablename__ = "reports"


    # ======================================================
    # PRIMARY KEY
    # ======================================================

    id = Column(

        Integer,

        primary_key=True,

        index=True

    )


    # ======================================================
    # MEDIA INFORMATION
    # ======================================================

    media_type = Column(

        String,

        nullable=False

    )


    media_path = Column(

        String,

        nullable=False

    )


    result_path = Column(

        String,

        nullable=True

    )


    # ======================================================
    # LOCATION
    # ======================================================

    latitude = Column(

        Float,

        nullable=True

    )


    longitude = Column(

        Float,

        nullable=True

    )


    location_name = Column(

        String,

        default="Unknown Location"

    )


    # ======================================================
    # AI DETECTION DATA
    # ======================================================

    pothole_count = Column(

        Integer,

        default=0

    )


    severity = Column(

        String,

        default="LOW"

    )


    confidence = Column(

        Float,

        default=0.0

    )


    # ======================================================
    # DATE AND TIME
    # ======================================================

    created_at = Column(

        DateTime,

        default=datetime.utcnow

    )