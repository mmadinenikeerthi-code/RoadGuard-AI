# backend/routers/detection.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import shutil
import os
from backend.config import UPLOAD_DIR, RESULTS_DIR
from backend.database import get_db
from backend.models import ReportModel
from ai.detector import PotholeDetector

router = APIRouter(prefix="/api/detect", tags=["Detection"])
detector = PotholeDetector()

@router.post("/image")
async def detect_image(
    file: UploadFile = File(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
    location_name: str = Form("Unknown"),
    db: Session = Depends(get_db)
):
    file_path = os.path.join(UPLOAD_DIR, "images", file.filename)
    result_file_path = os.path.join(RESULTS_DIR, "images", file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    analysis, plotted_img = detector.predict_image(file_path)
    if "error" in analysis:
        raise HTTPException(status_code=500, detail=analysis["error"])
        
    import cv2
    cv2.imwrite(result_file_path, plotted_img)
    
    new_report = ReportModel(
        media_type="image",
        media_path=f"/uploads/images/{file.filename}",
        result_path=f"/results/images/{file.filename}",
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        pothole_count=analysis["pothole_count"],
        severity=analysis["severity"],
        confidence=analysis["confidence"]
    )
    
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    
    return {
        "success": True,
        "report_id": new_report.id,
        "analysis": analysis,
        "result_url": new_report.result_path
    }

@router.post("/video")
async def detect_video(
    file: UploadFile = File(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
    location_name: str = Form("Unknown"),
    db: Session = Depends(get_db)
):
    file_path = os.path.join(UPLOAD_DIR, "videos", file.filename)
    result_file_path = os.path.join(RESULTS_DIR, "videos", file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    analysis = detector.predict_video(file_path, result_file_path)
    
    pothole_count = analysis["total_potholes_detected"]
    severity = "Critical" if pothole_count > 10 else ("Moderate" if pothole_count > 3 else "Minor")
    
    new_report = ReportModel(
        media_type="video",
        media_path=f"/uploads/videos/{file.filename}",
        result_path=f"/results/videos/{file.filename}",
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        pothole_count=pothole_count,
        severity=severity,
        confidence=80.0
    )
    
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    
    return {
        "success": True,
        "report_id": new_report.id,
        "analysis": analysis,
        "result_url": new_report.result_path
    }