from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_CONFIG_VERSION = "1.1"
DEFAULT_TOP_K = 5
DEMO_FILES = {"book": DATA_DIR / "demo_books.csv", "movie": DATA_DIR / "demo_movies.csv"}
