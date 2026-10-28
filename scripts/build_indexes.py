from pathlib import Path
import sys, json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import ARTIFACT_DIR
from src.data_loader import load_active_catalogs
from src.retrieval import RetrievalIndex

for media, items in load_active_catalogs().items():
    print(f"Preparing {media}: {len(items):,} records", flush=True)
    index = RetrievalIndex(items, mode="hybrid")
    (ARTIFACT_DIR / f"{media}_index_meta.json").write_text(json.dumps({"records":len(items),"active_mode":index.active_mode,"preparation_seconds":index.preparation_seconds,"model":"sentence-transformers/all-MiniLM-L6-v2","embeddings_cached":index.semantic_available}, indent=2))
    print(media, index.active_mode, f"{index.preparation_seconds:.3f}s", flush=True)
