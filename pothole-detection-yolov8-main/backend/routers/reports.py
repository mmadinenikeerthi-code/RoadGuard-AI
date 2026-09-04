# backend/routers/reports.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models import ReportModel
from backend.schemas import ReportResponse

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/", response_model=List[ReportResponse])
def get_all_reports(db: Session = Depends(get_db)):
    reports = db.query(ReportModel).order_by(ReportModel.created_at.desc()).all()
    return reports

@router.get("/{report_id}", response_model=ReportResponse)
def get_report_by_id(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report