# ==========================================================
# backend/config.py
# ROADGUARD AI CONFIGURATION
# ==========================================================

from pathlib import Path


# ==========================================================
# BASE DIRECTORY
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ==========================================================
# PROJECT DIRECTORIES
# ==========================================================

BACKEND_DIR = BASE_DIR / "backend"

AI_DIR = BASE_DIR / "ai"

MODEL_DIR = AI_DIR / "model"


# ==========================================================
# DATABASE
# ==========================================================

DATABASE_URL = "sqlite:///./roadguard.db"


# ==========================================================
# UPLOAD DIRECTORY
# ==========================================================

UPLOAD_DIR = BASE_DIR / "uploads"

# Alternative name for compatibility
UPLOADS_DIR = UPLOAD_DIR


# ==========================================================
# RESULTS DIRECTORY
# ==========================================================

RESULTS_DIR = BASE_DIR / "results"

# Alternative name for compatibility
RESULT_DIR = RESULTS_DIR


# ==========================================================
# MODEL PATH
# ==========================================================

MODEL_PATH = MODEL_DIR / "pothole_best.pt"


# ==========================================================
# SERVER CONFIGURATION
# ==========================================================

HOST = "127.0.0.1"

PORT = 8000


# ==========================================================
# CREATE REQUIRED DIRECTORIES
# ==========================================================

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================================
# DETECTION SETTINGS
# ==========================================================

CONFIDENCE_THRESHOLD = 0.25

IOU_THRESHOLD = 0.45


# ==========================================================
# SEVERITY CALCULATION
# ==========================================================

def calculate_severity(pothole_count):

    pothole_count = pothole_count or 0

    try:

        pothole_count = int(pothole_count)

    except (ValueError, TypeError):

        pothole_count = 0


    if pothole_count >= 20:

        return "CRITICAL"


    elif pothole_count >= 10:

        return "HIGH"


    elif pothole_count >= 5:

        return "MODERATE"


    return "LOW"