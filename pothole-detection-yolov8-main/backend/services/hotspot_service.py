# backend/services/hotspot_service.py
from sqlalchemy.orm import Session
from backend.models import ReportModel
from .location_service import calculate_distance, classify_hotspot

def get_hotspots_service(db: Session, radius_km: float = 1.0):
    reports = db.query(ReportModel).filter(ReportModel.latitude.isnot(None), ReportModel.longitude.isnot(None)).all()
    
    clusters = []
    
    for rep in reports:
        placed = False
        for cluster in clusters:
            # Check distance from cluster center / first item
            dist = calculate_distance(cluster["latitude"], cluster["longitude"], rep.latitude, rep.longitude)
            if dist <= radius_km:
                cluster["reports"].append(rep)
                cluster["total_potholes"] += rep.pothole_count
                placed = True
                break
        
        if not placed:
            clusters.append({
                "location_name": rep.location_name,
                "latitude": rep.latitude,
                "longitude": rep.longitude,
                "reports": [rep],
                "total_potholes": rep.pothole_count
            })
            
    hotspot_results = []
    for cluster in clusters:
        count = len(cluster["reports"])
        severities = [r.severity for r in cluster["reports"]]
        
        highest_severity = "Minor"
        if "Critical" in severities:
            highest_severity = "Critical"
        elif "Moderate" in severities:
            highest_severity = "Moderate"
            
        hotspot_results.append({
            "location_name": cluster["location_name"],
            "latitude": cluster["latitude"],
            "longitude": cluster["longitude"],
            "report_count": count,
            "total_potholes": cluster["total_potholes"],
            "highest_severity": highest_severity,
            "hotspot_level": classify_hotspot(count)
        })
        
    return hotspot_results