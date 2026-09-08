import math
from typing import List, Dict, Any

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates distance in meters between two GPS coordinates using Haversine formula."""
    R = 6371000  # Radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def cluster_pothole_hotspots(detections: List[Dict[str, Any]], radius_meters: float = 20.0) -> List[Dict[str, Any]]:
    """Groups detection points into hotspot clusters within a specified radius."""
    clusters = []
    
    for item in detections:
        lat = item.get("latitude")
        lon = item.get("longitude")
        if lat is None or lon is None:
            continue
            
        matched = False
        for cluster in clusters:
            dist = calculate_distance(lat, lon, cluster["center_lat"], cluster["center_lon"])
            if dist <= radius_meters:
                cluster["count"] += 1
                cluster["detections"].append(item)
                cluster["center_lat"] = sum(d["latitude"] for d in cluster["detections"]) / cluster["count"]
                cluster["center_lon"] = sum(d["longitude"] for d in cluster["detections"]) / cluster["count"]
                matched = True
                break
                
        if not matched:
            clusters.append({
                "cluster_id": len(clusters) + 1,
                "center_lat": lat,
                "center_lon": lon,
                "count": 1,
                "severity": item.get("severity", "medium"),
                "detections": [item]
            })
            
    return clusters