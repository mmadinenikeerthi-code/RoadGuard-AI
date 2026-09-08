from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.models import ReportModel
from backend.schemas import ReportResponse, ReportSummary

router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"]
)


@router.get("", response_model=List[ReportResponse])
@router.get("/", response_model=List[ReportResponse])
def list_reports(db: Session = Depends(get_db)):
    return db.query(ReportModel).order_by(ReportModel.created_at.desc()).all()


@router.get("/summary", response_model=ReportSummary)
def get_reports_summary(db: Session = Depends(get_db)):
    reports = db.query(ReportModel).all()

    total_reports = len(reports)
    total_potholes = sum(r.pothole_count or 0 for r in reports)

    low = sum(1 for r in reports if r.severity == "LOW")
    moderate = sum(1 for r in reports if r.severity == "MODERATE")
    high = sum(1 for r in reports if r.severity == "HIGH")
    critical = sum(1 for r in reports if r.severity == "CRITICAL")

    return {
        "total_reports": total_reports,
        "total_potholes": total_potholes,
        "low_severity": low,
        "moderate_severity": moderate,
        "high_severity": high,
        "critical_severity": critical
    }


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report record not found.")
    return report


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report record not found.")

    db.delete(report)
    db.commit()
    return None