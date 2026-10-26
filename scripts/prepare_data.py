"""Validate bundled catalogs or user-supplied CSV paths."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DEMO_FILES
from src.data_loader import load_catalog

paths = {"book": Path(sys.argv[1]) if len(sys.argv) > 1 else DEMO_FILES["book"], "movie": Path(sys.argv[2]) if len(sys.argv) > 2 else DEMO_FILES["movie"]}
for media, path in paths.items():
    print(f"validated {media}: {len(load_catalog(path, media))} records from {path}")
