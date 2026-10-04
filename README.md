# 🚧 Smart Road Pothole Detection System

**AI-powered pothole detection with severity scoring using YOLOv8 for smart city infrastructure**

🔗 [Live Demo](https://huggingface.co/spaces/harshithapethuraj/pothole-detection) | 📓 [Colab Notebook](https://github.com/harshithapethuraj/pothole-detection-yolov8/blob/main/Pothole_Smart_Road_Monitoring.ipynb)

---

##  Problem

India has over 3 million km of road network. Pothole-related accidents cause thousands of deaths and injuries every year. Manual road inspection is slow, expensive, and inconsistent.

This project builds an automated system that:
- **Detects** potholes from dashcam/road images using YOLOv8
- **Classifies severity** as Minor, Moderate, or Severe
- **Deploys as a web app** for municipality officers to use directly

---

## 🎬 Demo

| Upload Image | Get Detection + Severity |
|---|---|
| Road image with potholes | Bounding boxes + severity color coding + confidence scores |

**Try it live**  [huggingface.co/spaces/harshithapethuraj/pothole-detection](https://huggingface.co/spaces/harshithapethuraj/pothole-detection)

---

##  Model Performance

| Metric | Baseline (COCO) | Fine-tuned (Ours) | Improvement |
|---|---|---|---|
| **mAP@50** | 0.6% | **75.1%** | +74.5% |
| **mAP@50-95** | 0.2% | **47.7%** | +47.5% |
| **Precision** | 1.8% | **84.2%** | +82.4% |
| **Recall** | 0.6% | **64.3%** | +63.7% |

- Model: YOLOv8n (3.2M parameters)
- Dataset: 665 annotated dashcam images (Kaggle)
- Training: 50 epochs on Google Colab T4 GPU

---

## 🔴🟡🟢 Severity Scoring

Beyond simple detection, each pothole is classified by repair urgency:

| Severity | Condition | Municipal Response |
|---|---|---|
| 🟢 **Minor** | Area < 2% of image | Routine monitoring |
| 🟡 **Moderate** | Area 2-5% of image | Priority repair within 2 weeks |
| 🔴 **Severe** | Area > 5% of image | Emergency response |

---

##  Project Structure

```
pothole-detection-yolov8/
│
├── app.py                              # Standalone Streamlit image demo
├── requirements.txt                    # Python dependencies (API + AI + demo)
├── Dockerfile                          # Docker config for HF Spaces
├── Pothole_Smart_Road_Monitoring.ipynb # Complete training notebook
├── README.md                           # This file
│
├── best.pt                             # Trained YOLOv8 weights (NOT committed)
├── roadguard.db                        # SQLite database (generated)
│
├── ai/
│   └── detector.py                     # Low-level YOLO wrapper helper
│
├── backend/                            # FastAPI application
│   ├── main.py                         # App, static mounts, page routes
│   ├── config.py                       # Paths, model lookup, severity rule
│   ├── database.py                     # SQLAlchemy engine / session
│   ├── models.py                       # ReportModel (reports table)
│   ├── schemas.py                      # Pydantic request/response models
│   │
│   ├── routers/
│   │   ├── detection.py                # Upload + run detection
│   │   ├── reports.py                  # Report log + summary
│   │   ├── map.py                      # GPS locations
│   │   ├── hotspots.py                 # Clustered hotspot zones
│   │   ├── three_d.py                  # 3D / immersive road view
│   │   ├── photogrammetry.py           # Real 3D reconstruction endpoints
│   │   └── routing.py                  # OSRM route planning proxy
│   │
│   └── services/
│       ├── detection_service.py        # YOLO + ByteTrack unique-pothole logic
│       ├── hotspot_service.py          # Hotspot aggregation
│       ├── location_service.py         # Haversine / clustering helpers
│       ├── three_d_service.py          # 3D scene + marker geometry
│       └── photogrammetry_service.py   # Sparse SfM -> road mesh (PLY) + JSON
│
├── frontend/                           # Served by FastAPI (no build step)
│   ├── index.html                      # Dashboard (analytics + charts)
│   ├── detect.html                     # Upload / video / live camera detection
│   ├── map.html                        # Leaflet hotspot map
│   ├── reports.html                     # Report audit register
│   ├── three_d.html                    # Immersive 3D / 360 road view
│   ├── css/                            # style.css, detect.css, map.css, ...
│   ├── js/                             # config.js, detect.js, map.js, ...
│   └── templates/
│       ├── 3d_view.html                # PLY mesh viewer (Jinja2)
│       └── navigation.html             # Route planner (Jinja2)
│
├── uploads/                            # Uploaded images / videos (generated)
└── results/                            # Annotated media + 3D artefacts (generated)
    ├── report_<id>_result.jpg
    ├── 3d_data/report_<id>.json        # Detection metadata for the 3D view
    ├── panorama/
    └── photogrammetry/report_<id>/     # frames/, dense/roadguard-road.ply
```

---

##  Running the Full RoadGuard AI App (FastAPI)

The FastAPI app serves both the JSON API **and** the frontend, so
one command is enough.

```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Put the trained weights in the project root (git-ignored)
#    best.pt   (or pothole_best.pt)

# 3. Start the server
python -m uvicorn backend.main:app --reload --port 8000
```

Then open:

| URL | Page |
|---|---|
| `http://127.0.0.1:8000/` | Dashboard / analytics |
| `http://127.0.0.1:8000/detect` | Upload image, video or use the live camera |
| `http://127.0.0.1:8000/map` | Hotspot map |
| `http://127.0.0.1:8000/reports` | Report register |
| `http://127.0.0.1:8000/3d` | Immersive 3D / 360° road view |
| `http://127.0.0.1:8000/navigation` | Route planner |
| `http://127.0.0.1:8000/docs` | Interactive OpenAPI docs |

**Weights lookup order** (`backend/config.py`):

1. `ROADGUARD_MODEL_PATH` environment variable
2. `best.pt` in the project root
3. `pothole_best.pt` in the project root
4. `ai/model/best.pt` / `ai/model/pothole_best.pt`
5. `models/`, `weights/`, `runs/**/weights/`

The model is loaded lazily on the first inference, so the dashboard,
map, reports and 3D pages still work before weights are added.

### Real 3D reconstruction

`POST /api/photogrammetry/reconstruct/{report_id}` runs
frame sampling → ORB feature matching → essential-matrix pose
recovery → triangulation, then fits a triangulated road surface
(with pothole depressions) and writes:

```
results/photogrammetry/report_<id>/roadguard-points.ply   # sparse SfM cloud
results/photogrammetry/report_<id>/dense/roadguard-road.ply
results/photogrammetry/report_<id>/roadguard_3d.json
```

Open the result in the mesh viewer with
`http://127.0.0.1:8000/3d-view?report_id=<id>`, or press
**⚙️ Build 3D Model** on the 3D page.

### Standalone Streamlit demo (image only)

```bash
streamlit run app.py
```

---

##  Configuration Notes

| Setting | Location |
|---|---|
| Upload folder | `backend/config.py` → `UPLOAD_DIR` |
| Results folder | `backend/config.py` → `RESULTS_DIR` |
| Database URL | `backend/config.py` → `DATABASE_URL` |
| Detection confidence | `backend/services/detection_service.py` |
| Model lookup | `backend/config.py` → `MODEL_CANDIDATES` |

**Per-report severity scale** (used by the API and stored in the database):

| Severity | Unique potholes |
|---|---|
| 🟢 LOW | 0 |
| 🟡 MODERATE | 1–2 |
| 🟠 HIGH | 3–5 |
| 🔴 CRITICAL | 6+ |

> The Streamlit demo (`app.py`) uses a different, area-based wording
> (Minor / Moderate / Severe) because it evaluates a single image.
> Hotspot **zones** (`hotspot_service.py`) also aggregate many reports
> and therefore use their own thresholds.

---


##  What's Inside the Notebook

The Colab notebook contains 20 sections with 73 cells:

**Data Pipeline**
- Kaggle API dataset loading (665 images, 42MB)
- Pascal VOC XML to YOLO TXT format conversion
- 80/10/10 train/valid/test split

**Exploratory Data Analysis (14 charts)**
- Dataset split distribution
- Annotation count analysis
- Sample images with ground truth boxes
- Bounding box size, shape, and location heatmap
- Image dimension analysis

**Training and Evaluation**
- Baseline evaluation (pretrained COCO YOLOv8n)
- YOLOv8n fine-tuning with AdamW optimizer
- Training curves (loss, precision, recall, mAP)
- Confusion matrix, PR curve, F1 curve
- Inference on held-out test images

**Advanced Analysis**
- Severity scoring (Minor / Moderate / Severe)
- Categorized failure analysis (small objects, shadows, low contrast)
- Augmentation ablation study (with vs without augmentation)
- Multi-model comparison (YOLOv8n vs YOLOv8s)
- Grad-CAM attention visualization
- GPS-based pothole mapping (Folium)
- ONNX edge deployment benchmarking
- Video inference demo
- Business impact analysis

---

##  Business Impact

| Method | Cost per km | Speed | Monthly Coverage |
|---|---|---|---|
| Manual inspection | ₹2,000-5,000 | 5-10 km/day | 200 km |
| AI dashcam system | ₹50-200 | 50+ km/hour | 5,000+ km |

**Estimated 90% cost reduction** and **25x more road coverage** per month.

---

##  Run Locally

```bash
# Clone the repo
git clone https://github.com/harshithapethuraj/pothole-detection-yolov8.git
cd pothole-detection-yolov8

# Install dependencies
pip install -r requirements.txt

# Download model weights from HF Space
# Place pothole_best.pt in the root directory

# Run the app
streamlit run app.py
```

---

##  Tech Stack

- **Model:** YOLOv8n (Ultralytics)
- **Training:** Google Colab (T4 GPU)
- **App:** Streamlit
- **Deployment:** Hugging Face Spaces (Docker)
- **Libraries:** OpenCV, Matplotlib, Seaborn, Folium, ONNX Runtime

---

##  Future Improvements

1. **Multi-dataset training** - merge with RDD2022 (47,000 images from 6 countries)
2. **GPS integration** - real dashcam EXIF metadata for location mapping
3. **Depth estimation** - stereo cameras for actual pothole depth
4. **Mobile app** - React Native + FastAPI for field inspectors
5. **Video streaming** - real-time dashcam processing at 25+ FPS
6. **Edge deployment** - TensorRT optimization for Jetson Nano



---

##  License

MIT License

---

*Built for the ATRISI Amplify Builder Challenge - an end-to-end ML project from data pipeline to deployed product.*
