"""Central configuration for NoteVision AI."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
GENERATED_DIR = BASE_DIR / "generated"
import os
DB_PATH = Path(os.environ.get("NOTEVISION_DB", BASE_DIR / "data" / "notevision.db"))
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
CSS_PATH = BASE_DIR / "assets" / "styles.css"
DEMO_NOTES_PATH = BASE_DIR / "assets" / "demo_notes.txt"
LOGO_PATH = BASE_DIR / "assets" / "logo.svg"
FAVICON_PATH = BASE_DIR / "assets" / "favicon.png"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".pptx", ".ppt"}
MAX_FILE_MB = 20
MAX_PDF_PAGES = 30
MAX_SLIDES = 100
MIN_SLIDE_TEXT_CHARS = 15    # slides with less text than this have their pictures OCR-ed
PDF_RENDER_DPI = 200
OCR_LANG = "eng"

SUBJECTS = [
    "Computer Science", "Mathematics", "Physics", "Chemistry", "Biology",
    "Economics", "Commerce", "Languages", "History", "General",
]

QA_MIN_SCORE = 0.08        # minimum cosine similarity to trust a retrieved passage
QA_MIN_COVERAGE = 0.5      # share of question terms that must appear in the passage

for _d in (UPLOAD_DIR, GENERATED_DIR, DB_PATH.parent):
    _d.mkdir(parents=True, exist_ok=True)
