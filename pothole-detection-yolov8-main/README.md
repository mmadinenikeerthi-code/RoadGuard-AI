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
├── app.py                              # Streamlit web application
├── requirements.txt                    # Python dependencies
├── Dockerfile                          # Docker config for HF Spaces
├── Pothole_Smart_Road_Monitoring.ipynb # Complete training notebook
├── README.md                           # This file
└── .streamlit/
    └── config.toml                     # Streamlit configuration
```

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
