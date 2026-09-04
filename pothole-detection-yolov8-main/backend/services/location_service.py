# backend/services/location_service.py
import math

def calculate_distance(lat1, lon1, lat2, lon2):
    # Haversine formula to compute distance in kilometers
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon1 - lon2)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def classify_hotspot(report_count):
    if report_count >= 4:
        return "High"
    elif report_count >= 2:
        return "Moderate"
    else:
        return "Low"