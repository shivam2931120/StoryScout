import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.config import DEMO_FILES
from src.data_loader import load_catalog
from src.retrieval import RetrievalIndex
from src.conversation import StoryScoutEngine

@pytest.fixture
def catalogs(): return {m: load_catalog(DEMO_FILES[m], m) for m in ("book", "movie")}

@pytest.fixture
def engine(catalogs): return StoryScoutEngine(catalogs, {m: RetrievalIndex(catalogs[m], mode="tfidf") for m in catalogs}, "tfidf")
