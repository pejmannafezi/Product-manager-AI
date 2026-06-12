import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = Path(os.environ.get("PMAI_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "app.db"
SCHEMA_PATH = APP_DIR / "schema.sql"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
TRANSLATIONS_DIR = APP_DIR / "translations"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AI_MODEL = os.environ.get("PMAI_AI_MODEL", "claude-sonnet-4-6")

SEED_VERSION = "1"
