import streamlit as st
import cv2
import numpy as np
import tempfile
import os
from ultralytics import YOLO
from PIL import Image

st.set_page_config(page_title="Pothole Detection", page_icon="🚧", layout="wide")

@st.cache_resource
def load_model():
    return YOLO("pothole_best.pt")

model = load_model()

def get_severity(box_area, img_area):
    ratio = box_area / img_area
    if ratio > 0.05:
        return "Severe", (226, 75, 74), "🔴"
    elif ratio > 0.02:
        return "Moderate", (239, 159, 39), "🟡"
    else:
        return "Minor", (76, 175, 80), "🟢"

st.title("🚧 Smart Road Pothole Detection System")
st.markdown("AI-powered pothole detection with severity scoring")

conf_threshold = st.sidebar.slider("Confidence Threshold", 0.10, 0.95, 0.25, 0.05)
st.sidebar.markdown("---")
st.sidebar.markdown("**Model:** YOLOv8n (3.2M params)")
st.sidebar.markdown("**mAP@50:** 75.1%")
st.sidebar.markdown("**Precision:** 84.2%")
st.sidebar.markdown("**Recall:** 64.3%")
st.sidebar.markdown("---")
st.sidebar.markdown("🟢 Minor - area < 2%")
st.sidebar.markdown("🟡 Moderate - area 2-5%")
st.sidebar.markdown("🔴 Severe - area > 5%")

tab1, tab2, tab3 = st.tabs(["📷 Image", "🎥 Video", "📊 Dashboard"])

with tab1:
    uploaded = st.file_uploader("Upload a road image", type=["jpg", "jpeg", "png"], key="img")

    if uploaded is not None:
        try:
            file_bytes = np.asarray(bytearray(uploaded.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_h, img_w = img.shape[:2]
            img_area = img_h * img_w

            results = model.predict(source=img_rgb, conf=conf_threshold, verbose=False)
            result = results[0]

            detections = []
            annotated = img_rgb.copy()

            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                conf = float(box.conf[0])
                box_area = (x2 - x1) * (y2 - y1)
                sev_name, sev_rgb, sev_icon = get_severity(box_area, img_area)
                area_pct = box_area / img_area * 100
                detections.append({"severity": sev_name, "icon": sev_icon, "confidence": conf, "area_pct": area_pct})

                cv2.rectangle(annotated, (x1, y1), (x2, y2), sev_rgb, 3)
                label = f"{sev_name} {conf:.0%}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(annotated, (x1, y1 - th - 10), (x1 + tw + 4, y1), sev_rgb, -1)
                cv2.putText(annotated, label, (x1 + 2, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            col1, col2 = st.columns([2, 1])

            with col1:
                st.image(annotated, caption="Detection Results")

            with col2:
                st.markdown("### Summary")
                st.metric("Total Potholes", len(detections))

                sev_counts = {"Minor": 0, "Moderate": 0, "Severe": 0}
                for d in detections:
                    sev_counts[d["severity"]] += 1

                c1, c2, c3 = st.columns(3)
                c1.metric("🟢", sev_counts["Minor"])
                c2.metric("🟡", sev_counts["Moderate"])
                c3.metric("🔴", sev_counts["Severe"])

                if detections:
                    avg_conf = np.mean([d["confidence"] for d in detections])
                    st.metric("Avg Confidence", f"{avg_conf:.0%}")

                    for i, d in enumerate(detections, 1):
                        st.markdown(f"{d['icon']} **#{i}** {d['severity']} - {d['confidence']:.0%} - {d['area_pct']:.1f}%")

                if sev_counts["Severe"] > 0:
                    st.error("Emergency repair recommended!")
                elif sev_counts["Moderate"] > 0:
                    st.warning("Schedule priority repair")
                elif len(detections) > 0:
                    st.success("Minor damage - routine monitoring")
                else:
                    st.info("No potholes detected")

        except Exception as e:
            st.error(f"Error processing image: {str(e)}")

with tab2:
    st.info("Upload a dashcam video clip to analyze")
    video = st.file_uploader("Upload video", type=["mp4", "avi"], key="vid")

    if video is not None:
        try:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(video.read())
            tfile.close()

            cap = cv2.VideoCapture(tfile.name)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = max(int(cap.get(cv2.CAP_PROP_FPS)), 1)

            progress = st.progress(0)
            frame_display = st.empty()
            frame_count = 0
            total_det = 0
            process_every = max(1, fps // 3)

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1
                progress.progress(min(frame_count / max(total_frames, 1), 1.0))

                if frame_count % process_every == 0:
                    res = model.predict(source=frame, conf=conf_threshold, verbose=False)
                    total_det += len(res[0].boxes)
                    ann = cv2.cvtColor(res[0].plot(), cv2.COLOR_BGR2RGB)
                    frame_display.image(ann)

            cap.release()
            os.unlink(tfile.name)
            progress.empty()

            st.markdown("### Video Summary")
            c1, c2 = st.columns(2)
            c1.metric("Frames", frame_count)
            c2.metric("Total Detections", total_det)

        except Exception as e:
            st.error(f"Error: {str(e)}")

with tab3:
    st.markdown("### Model Performance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("mAP@50", "75.1%")
    c2.metric("Precision", "84.2%")
    c3.metric("Recall", "64.3%")
    c4.metric("Model", "YOLOv8n")

    st.markdown("### Baseline vs Fine-tuned")
    st.markdown("""
| Metric | Baseline | Fine-tuned | Improvement |
|---|---|---|---|
| mAP@50 | 0.6% | 75.1% | +74.5% |
| mAP@50-95 | 0.2% | 47.7% | +47.5% |
| Precision | 1.8% | 84.2% | +82.4% |
| Recall | 0.6% | 64.3% | +63.7% |
    """)

    st.markdown("### Severity Scoring")
    st.markdown("""
| Severity | Condition | Action |
|---|---|---|
| 🟢 Minor | Area < 2% | Routine monitoring |
| 🟡 Moderate | Area 2-5% | Priority repair - 2 weeks |
| 🔴 Severe | Area > 5% | Emergency response |
    """)

    st.markdown("### Business Impact")
    st.markdown("""
| Method | Cost/km | Speed | Monthly Coverage |
|---|---|---|---|
| Manual | ₹2,000-5,000 | 5-10 km/day | 200 km |
| AI System | ₹50-200 | 50+ km/hr | 5,000+ km |
    """)

    st.markdown("---")
    st.markdown("Built for **ATRISI Amplify Builder Challenge**")