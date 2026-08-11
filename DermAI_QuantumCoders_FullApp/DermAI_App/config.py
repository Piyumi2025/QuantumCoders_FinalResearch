"""Application configuration.

Database selection is driven entirely by the DATABASE_URL environment variable.
  * Default (no env)  -> SQLite file at instance/dermai.db  (zero-setup demo)
  * MySQL             -> set DATABASE_URL, e.g.
        mysql+pymysql://USER:PASSWORD@HOST:3306/dermai
  * PostgreSQL        -> postgresql+psycopg2://USER:PASSWORD@HOST:5432/dermai
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")

    # --- database ---
    # Permanent default: WAMP MySQL (root, blank password, localhost:3306, db 'dermai').
    # If you set a MySQL root password or use port 3308, edit WAMP_MYSQL_URL below.
    # An env var DATABASE_URL, if present, still overrides this.
    WAMP_MYSQL_URL = "mysql+pymysql://root:@localhost:3306/dermai"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", WAMP_MYSQL_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- uploads ---
    UPLOAD_DIR = BASE_DIR / "uploads"
    MODELS_DIR = BASE_DIR / "models_store"
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024          # 12 MB request cap
    ALLOWED_EXT = {"jpg", "jpeg", "png", "tiff", "tif", "webp", "bmp"}
    MAX_IMAGE_MB = 10
    MIN_RESOLUTION = 299
    BLUR_THRESHOLD = 40.0                          # Laplacian variance floor

    # --- model / inference ---
    CLASSES = ["Melanoma", "BCC", "SCC", "MCC"]
    IMG_SIZE = 299
    FUSION_IMAGE_WEIGHT = 0.60
    FUSION_SYMPTOM_WEIGHT = 0.40
    UNCERTAIN_THRESHOLD = 0.50                     # confidence below -> "Uncertain"
    WEIGHTS_FILE = os.environ.get("WEIGHTS_FILE", str(BASE_DIR / "models_store" / "dermai_best.pth"))
