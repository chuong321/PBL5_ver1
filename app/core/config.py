"""Application configuration."""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]

# ==================== SERVER ====================
HOST = "0.0.0.0"
PORT = 8000
RELOAD = False
LOG_LEVEL = "info"

# ==================== DATABASE ====================
SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'database' / 'trash_classification.db'}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = False

# ==================== PATHS ====================
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
UPLOAD_FOLDER = BASE_DIR / "uploads"

# ==================== UPLOADS ====================
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# ==================== AI/ML ====================
MODEL_PATH = BASE_DIR / "model_weights" / "primary" / "best.pt"
MODEL_SECONDARY_PATH = BASE_DIR / "model_weights" / "secondary" / "best.pt"
BUFFER_SIZE = 1  # Process each image immediately

# ==================== MULTIPROCESSING ====================
PRIMARY_PROCESS_WORKERS = 2
SECONDARY_PROCESS_WORKERS = 1
QUEUE_TIMEOUT = 5
MAX_QUEUE_SIZE = 100

# Weight threshold (grams) - Dung de kiem tra co nuoc
WEIGHT_THRESHOLD = {
    "plastic_bottle": 50,
    "can": 30,
    "glass": 100,
    "default": 50,
}

# ==================== FASTAPI ====================
SECRET_KEY = "trash-classification-secret-2024"
DEBUG = False
TESTING = False

# CORS settings
CORS_ORIGINS = ["*"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# ==================== WEBSOCKET ====================
WEBSOCKET_RECONNECT_INTERVAL = 5
WEBSOCKET_MAX_CONNECTIONS = 10
WEBSOCKET_PING_INTERVAL = 30

# ==================== PERFORMANCE - YOLO1 (Primary) ====================
YOLO1_CONF = 0.1
YOLO1_IMGSZ = 320
YOLO1_DEVICE = "cpu"

# ==================== PERFORMANCE - YOLO2 (Secondary) ====================
YOLO2_CONF = 0.5
YOLO2_IMGSZ = 320
YOLO2_DEVICE = "cpu"

# Image compression
COMPOSITE_SIZE = (600, 400)
COMPOSITE_QUALITY = 85

# Database optimization
DB_POOL_SIZE = 10
DB_POOL_RECYCLE = 3600

# ==================== FEATURES ====================
ENABLE_AUTO_CLEANUP = True
CLEANUP_DAYS = 30
CLEANUP_INTERVAL = 86400

# ==================== LOGGING ====================
LOG_FILE = BASE_DIR / "logs" / "app.log"

# Create directories if not exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BASE_DIR / "database", exist_ok=True)
os.makedirs(BASE_DIR / "logs", exist_ok=True)
