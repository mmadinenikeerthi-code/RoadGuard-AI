# ==========================================================
# backend/config.py
# ROADGUARD AI CONFIGURATION
# ==========================================================

import os

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
#
# The trained weights are NOT committed to the repository
# (see .gitignore), and the Streamlit demo (app.py) and the
# API service previously looked for DIFFERENT file names.
#
# This is now the single source of truth for the lookup order:
#
#   1. ROADGUARD_MODEL_PATH environment variable
#   2. best.pt in the project root
#   3. pothole_best.pt in the project root
#   4. ai/model/*.pt
#   5. best.pt inside models/, weights/ or runs/**/weights/
# ==========================================================

MODEL_CANDIDATES = [

    BASE_DIR / "best.pt",

    BASE_DIR / "pothole_best.pt",

    MODEL_DIR / "best.pt",

    MODEL_DIR / "pothole_best.pt",

    BASE_DIR / "models" / "best.pt",

    BASE_DIR / "weights" / "best.pt",

    BASE_DIR / "runs" / "detect" / "train" / "weights" / "best.pt",

    BASE_DIR / "runs" / "detect" / "train2" / "weights" / "best.pt",

    BASE_DIR / "runs" / "detect" / "train3" / "weights" / "best.pt",

    BASE_DIR / "runs" / "train" / "weights" / "best.pt",

]


MODEL_FILENAME_HINT = "best.pt"


def resolve_model_path():
    """
    Return the first existing weights file, or None when the
    project has not been given any weights yet.

    Never raises, so the API can still start and serve the
    database-backed endpoints (reports / map / hotspots / 3D)
    before the model is downloaded.
    """

    override = os.environ.get("ROADGUARD_MODEL_PATH")

    if override:

        override_path = Path(override).expanduser()

        if override_path.exists():

            return override_path

    for candidate in MODEL_CANDIDATES:

        if candidate.exists():

            return candidate

    return None


def find_model_path() -> Path:
    """
    Same as resolve_model_path() but raises with an actionable
    message instead of returning None. Used by the detection
    service at inference time.
    """

    model_path = resolve_model_path()

    if model_path is None:

        raise FileNotFoundError(

            "\n[RoadGuard AI] ERROR: no YOLO weights were found.\n"

            f"Place '{MODEL_FILENAME_HINT}' in the project root:\n"

            f"    {BASE_DIR / MODEL_FILENAME_HINT}\n"

            "or point ROADGUARD_MODEL_PATH at the .pt file.\n"

        )

    return model_path


# First existing weights file at import time (may be None).
MODEL_PATH = resolve_model_path()


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