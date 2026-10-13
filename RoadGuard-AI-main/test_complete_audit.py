import sys
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app

def run_tests():
    client = TestClient(app)
    print("==================================================")
    print("ROADGUARD-AI COMPLETE AUDIT & VERIFICATION SUITE")
    print("==================================================")

    passed = 0
    total = 0

    # 1. Dashboard Root Route
    total += 1
    resp = client.get("/")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.text
    assert 'id="totalPotholes">0<' in html or 'id="totalPotholes">\n                            0' in html, "totalPotholes default should be 0"
    assert 'id="highRiskCount"' in html, "highRiskCount must exist"
    assert 'id="totalReportsCount"' in html, "totalReportsCount must exist"
    assert 'id="avgConfidence">--<' in html or 'id="avgConfidence">\n                            --' in html, "avgConfidence default should be --"
    assert 'class="welcome-banner"' in html, "Welcome banner must exist"
    assert 'id="recentDetectionsList"' in html, "Recent detections container must exist"
    assert 'class="empty-state-box"' in html, "Empty state box must exist"
    assert 'id="detectionProcessing"' in html, "Processing loader must exist in detection panel"
    assert 'id="detectionResultPanel"' in html, "Detection result panel must exist"
    print("[PASS] Test 1: Dashboard empty state HTML structure & defaults")
    passed += 1

    # 2. 3D View Page
    total += 1
    resp = client.get("/3d-view")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html_3d = resp.text
    assert 'importmap' in html_3d, "Three.js importmap must be in 3d_view.html"
    assert 'id="threeContainer"' in html_3d, "#threeContainer must exist"
    assert 'id="threeErrorOverlay"' in html_3d, "#threeErrorOverlay must exist"
    assert 'errorRetryBtn' in html_3d, "Retry button must exist"
    assert 'errorBuildModelBtn' in html_3d, "Build model button must exist"
    print("[PASS] Test 2: 3D View page template, importmap & error overlays")
    passed += 1

    # 3. Reports API
    total += 1
    resp = client.get("/api/reports/")
    assert resp.status_code == 200
    reports = resp.json()
    assert isinstance(reports, list), "Reports should be a list"
    print(f"[PASS] Test 3: GET /api/reports/ returns {len(reports)} stored reports")
    passed += 1

    # 4. Analytics API
    total += 1
    resp = client.get("/api/analytics")
    assert resp.status_code == 200
    analytics_data = resp.json()
    assert analytics_data.get("success") is True, "Analytics should succeed"
    print(f"[PASS] Test 4: GET /api/analytics returns valid stored analytics data")
    passed += 1

    # 5. 3D Reports List API
    total += 1
    resp = client.get("/3d/reports-list")
    assert resp.status_code == 200
    reports_3d = resp.json()
    assert "reports" in reports_3d
    print(f"[PASS] Test 5: GET /3d/reports-list returns catalog for 3D dropdown")
    passed += 1

    # 6. 3D Road View API with valid report
    total += 1
    resp = client.get("/3d/road-view/1")
    assert resp.status_code == 200
    rv = resp.json()
    assert rv.get("success") is True
    assert "viewer" in rv
    assert rv["viewer"]["reconstruction_available"] in (True, False)
    print(f"[PASS] Test 6: GET /3d/road-view/1 returns road view data (reconstruction_available: {rv['viewer']['reconstruction_available']})")
    passed += 1

    # 7. 3D Road View API with nonexistent report
    total += 1
    resp = client.get("/3d/road-view/999999")
    assert resp.status_code == 404
    print("[PASS] Test 7: GET /3d/road-view/999999 correctly returns HTTP 404")
    passed += 1

    # 8. Invalid Upload File
    total += 1
    resp = client.post(
        "/api/detection/upload",
        files={"file": ("invalid_script.exe", b"fake binary", "application/octet-stream")}
    )
    assert resp.status_code == 400
    print("[PASS] Test 8: POST /api/detection/upload rejects invalid file format with HTTP 400")
    passed += 1

    # 9. Real Upload & YOLO Inference Test
    total += 1
    test_image_path = Path("uploads") / "test_frame.jpg"
    assert test_image_path.exists(), f"{test_image_path} does not exist"
    with open(test_image_path, "rb") as f:
        file_bytes = f.read()

    resp = client.post(
        "/api/detection/upload",
        files={"file": ("test_frame.jpg", file_bytes, "image/jpeg")},
        data={"location_name": "Test Highway Segment"}
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    new_report = resp.json()
    assert "id" in new_report
    assert "pothole_count" in new_report
    assert "severity" in new_report
    assert "confidence" in new_report
    print(f"[PASS] Test 9: Real YOLOv8 upload & inference successful! Created Report #{new_report['id']}, Potholes: {new_report['pothole_count']}, Severity: {new_report['severity']}, Confidence: {new_report['confidence']:.2f}")
    passed += 1

    # 10. Repeated Upload Test
    total += 1
    resp2 = client.post(
        "/api/detection/upload",
        files={"file": ("test_frame_second.jpg", file_bytes, "image/jpeg")},
        data={"location_name": "Test Highway Segment 2"}
    )
    assert resp2.status_code == 201
    new_report2 = resp2.json()
    assert new_report2["id"] != new_report["id"], "Repeated upload should generate new unique report ID"
    print(f"[PASS] Test 10: Repeated upload successful! Created Report #{new_report2['id']}")
    passed += 1

    # 11. Verify 3D metadata for new report
    total += 1
    resp_3d = client.get(f"/3d/road-view/{new_report['id']}")
    assert resp_3d.status_code == 200
    new_rv = resp_3d.json()
    assert new_rv.get("success") is True
    print(f"[PASS] Test 11: 3D endpoint serves new Report #{new_report['id']} correctly")
    passed += 1

    print("==================================================")
    print(f"RESULTS: {passed}/{total} tests PASSED ({passed/total*100:.1f}%)")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
