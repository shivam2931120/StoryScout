from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_CONFIG_VERSION = "2.0-chunked-plot-profiles"
if os.getenv('STORYSCOUT_EMBEDDING_BACKEND')=='onnx':
    MODEL_CONFIG_VERSION += '-onnx-quint8-v1'
DEFAULT_TOP_K = 5
DEMO_FILES = {"book": DATA_DIR / "demo_books.csv", "movie": DATA_DIR / "demo_movies.csv"}
