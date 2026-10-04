# ai/detector.py
from ultralytics import YOLO
import cv2
import numpy as np
import os

class PotholeDetector:
    def __init__(self, model_path="ai/model/pothole_best.pt"):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            if os.path.exists(self.model_path):
                self.model = YOLO(self.model_path)
            else:
                # Fallback to standard nano model if custom weights are missing for testing structure
                print(f"Warning: {self.model_path} not found. Loading yolov8n.pt as placeholder.")
                self.model = YOLO("yolov8n.pt")
        except Exception as e:
            print(f"Error loading model: {e}")

    def predict_image(self, image_path, conf_threshold=0.25):
        if not self.model:
            return {"error": "Model not loaded"}, []

        results = self.model(image_path, conf=conf_threshold)
        detections = []
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                b = box.xyxy[0].tolist()  # get box coordinates [x1, y1, x2, y2]
                c = box.conf[0].item()
                cls = int(box.cls[0].item())
                
                # Simple rule-based severity derived from confidence and size
                box_area = (b[2] - b[0]) * (b[3] - b[1])
                severity = "Minor"
                if c > 0.75 or box_area > 50000:
                    severity = "Critical"
                elif c > 0.5 or box_area > 20000:
                    severity = "Moderate"

                detections.append({
                    "bounding_box": [round(coord, 2) for coord in b],
                    "confidence": round(c * 100, 2),
                    "severity": severity,
                    "class_id": cls
                })

        pothole_count = len(detections)
        overall_severity = "Minor"
        if any(d["severity"] == "Critical" for d in detections):
            overall_severity = "Critical"
        elif any(d["severity"] == "Moderate" for d in detections):
            overall_severity = "Moderate"

        avg_conf = sum([d["confidence"] for d in detections]) / pothole_count if pothole_count > 0 else 0.0

        return {
            "pothole_count": pothole_count,
            "confidence": round(avg_conf, 2),
            "severity": overall_severity,
            "detections": detections
        }, results[0].plot()

    def predict_video(self, video_path, output_path, conf_threshold=0.25):
        cap = cv2.VideoCapture(video_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        total_frames = 0
        total_potholes_detected = 0
        frame_detections = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            total_frames += 1
            results = self.model(frame, conf=conf_threshold, verbose=False)
            res_plotted = results[0].plot()
            out.write(res_plotted)
            
            count = len(results[0].boxes)
            total_potholes_detected += count

        cap.release()
        out.release()

        return {
            "total_frames": total_frames,
            "total_potholes_detected": total_potholes_detected,
            "output_video": output_path
        }