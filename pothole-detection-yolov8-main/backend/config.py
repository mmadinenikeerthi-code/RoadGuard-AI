# backend/config.py
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'database', 'roadguard.db')}"

UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')

os.makedirs(os.path.join(UPLOAD_DIR, 'images'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, 'videos'), exist_ok=True)
os.makedirs(os.path.join(RESULTS_DIR, 'images'), exist_ok=True)
os.makedirs(os.path.join(RESULTS_DIR, 'videos'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'database'), exist_ok=True)