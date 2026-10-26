"""Lexical, semantic, and hybrid retrieval with hard filters before ranking."""
from __future__ import annotations
import hashlib, json, pickle, time
from functools import lru_cache
from pathlib import Path
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .config import ARTIFACT_DIR, MODEL_NAME, MODEL_CONFIG_VERSION
from .preprocessing import build_query_text
from .schemas import CatalogItem, Preferences, Recommendation

@lru_cache(maxsize=1)
def _sentence_model():
    from sentence_transformers import SentenceTransformer
    try:
        from huggingface_hub import try_to_load_from_cache
        cached_config = try_to_load_from_cache(MODEL_NAME, "config.json")
    except Exception:
        cached_config = None
    local_only = isinstance(cached_config, str) and Path(cached_config).is_file()
    return SentenceTransformer(MODEL_NAME, device="cpu", local_files_only=local_only)


def combine_hybrid_scores(lexical: np.ndarray, semantic: np.ndarray) -> np.ndarray:
    """Blend lexical cosine [0, 1] and remapped semantic cosine [-1, 1]."""
    semantic_unit = np.clip((semantic + 1.0) / 2.0, 0.0, 1.0)
    return 0.45 * lexical + 0.55 * semantic_unit

class RetrievalIndex:
    def __init__(self, items: list[CatalogItem], mode: str = "hybrid", artifact_dir: Path = ARTIFACT_DIR):
        self.items, self.mode, self.artifact_dir = items, mode, artifact_dir
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.model = None
        self.embeddings = None
        self.semantic_available = False
        self.preparation_seconds = 0.0
        self._prepare()

    @property
    def active_mode(self) -> str:
        if self.mode == "tfidf": return "TF-IDF lexical"
        if self.mode == "semantic" and not self.semantic_available: return "TF-IDF fallback (semantic unavailable)"
        if self.mode == "hybrid" and not self.semantic_available: return "TF-IDF fallback (semantic unavailable)"
        return "hybrid (TF-IDF + sentence embeddings)" if self.mode == "hybrid" else "sentence embeddings"

    def _prepare(self) -> None:
        start = time.perf_counter()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        docs = [build_query_text(item.search_text) for item in self.items]
        vectorizer_config = json.dumps({"ngram_range": [1, 2], "min_df": 1, "sublinear_tf": True}, sort_keys=True)
        lexical_key = hashlib.sha256((sklearn.__version__ + MODEL_CONFIG_VERSION + vectorizer_config + "\n".join(docs)).encode("utf-8")).hexdigest()
        lexical_file = self.artifact_dir / f"tfidf_{lexical_key}.pkl"
        if lexical_file.exists():
            with lexical_file.open("rb") as cache:
                self.vectorizer, self.matrix = pickle.load(cache)
        else:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
            self.matrix = self.vectorizer.fit_transform(docs)
            with lexical_file.open("wb") as cache:
                pickle.dump((self.vectorizer, self.matrix), cache, protocol=pickle.HIGHEST_PROTOCOL)
        if self.mode in {"semantic", "hybrid"}:
            try:
                self.model = _sentence_model()
                digest = hashlib.sha256((MODEL_NAME + MODEL_CONFIG_VERSION + "\n".join(docs)).encode("utf-8")).hexdigest()
                embedding_file = self.artifact_dir / f"embeddings_{digest}.npy"
                if embedding_file.exists():
                    self.embeddings = np.load(embedding_file, mmap_mode="r")
                else:
                    self.embeddings = self.model.encode(docs, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)
                    np.save(embedding_file, self.embeddings)
                self.semantic_available = True
            except Exception:
                self.semantic_available = False
        self.preparation_seconds = time.perf_counter() - start

    def _hard_filter(self, item: CatalogItem, pref: Preferences) -> tuple[bool, list[str]]:
        notes = []
        if pref.language and item.language.lower() != pref.language.lower(): notes.append(f"language is not {pref.language}")
        if pref.min_year is not None and (item.year is None or item.year < pref.min_year): notes.append(f"year is unknown or before {pref.min_year}")
        if pref.max_year is not None and (item.year is None or item.year > pref.max_year): notes.append(f"year is unknown or after {pref.max_year}")
        if item.media_type == "book" and pref.max_pages is not None and (item.page_count is None or item.page_count > pref.max_pages): notes.append(f"pages are unknown or over {pref.max_pages}")
        if item.media_type == "movie" and pref.max_runtime is not None and (item.runtime_minutes is None or item.runtime_minutes > pref.max_runtime): notes.append(f"runtime is unknown or over {pref.max_runtime}")
        if set(pref.excluded_genres) & set(item.genres): notes.append("excluded genre")
        if pref.excluded_genres and not item.genres: notes.append("genres are unknown; exclusion cannot be verified")
        # Verified warning labels can enforce negative content; unknown is not treated as safe.
        if "graphic violence" in pref.negative_content and "graphic violence" in item.verified_warnings: notes.append("verified graphic violence")
        return not notes, notes

    def search(self, query: str, pref: Preferences, top_k: int = 5, exclude_ids: set[str] | None = None) -> list[Recommendation]:
        exclude_ids = exclude_ids or set()
        eligible, eligible_indices, notes = [], [], {}
        for item_index, item in enumerate(self.items):
            ok, item_notes = self._hard_filter(item, pref)
            if ok and item.id not in exclude_ids:
                eligible.append(item)
                eligible_indices.append(item_index)
            notes[item.id] = item_notes
        if not eligible: return []
        lexical = cosine_similarity(self.matrix[eligible_indices], self.vectorizer.transform([build_query_text(query)])).ravel()
        semantic = None
        if self.semantic_available:
            qemb = self.model.encode([build_query_text(query)], normalize_embeddings=True, show_progress_bar=False)
            semantic = cosine_similarity(qemb, self.embeddings[eligible_indices]).ravel()
        if semantic is not None and self.mode == "semantic": scores = semantic
        elif semantic is not None and self.mode == "hybrid": scores = combine_hybrid_scores(lexical, semantic)
        else: scores = lexical
        if not np.any(scores > 0):
            filter_only = any((pref.preferred_genres, pref.excluded_genres, pref.desired_mood, pref.themes, pref.language, pref.min_year is not None, pref.max_year is not None, pref.max_pages is not None, pref.max_runtime is not None, pref.negative_content))
            if not filter_only:
                return []
            def fallback_order(index: int) -> tuple:
                item = eligible[index]
                soft = len(set(item.genres) & set(pref.preferred_genres)) * 3
                soft += len(set(item.theme_tags) & set(pref.themes)) * 2
                if pref.desired_mood and pref.desired_mood in item.mood_tags:
                    soft += 1
                length = item.page_count if item.media_type == "book" else item.runtime_minutes
                return (-soft, length is None, length or 0, item.title.casefold())
            ranked = sorted(range(len(eligible)), key=fallback_order)[:top_k]
            return [Recommendation(item=eligible[index], score=0.0, lexical_score=0.0, filter_notes=["filter-only results; no text similarity signal"])
                    for index in ranked]
        positive = np.flatnonzero(scores > 0)
        eligible = [eligible[i] for i in positive]
        lexical = lexical[positive]
        scores = scores[positive]
        if semantic is not None:
            semantic = semantic[positive]
        ranked = np.argsort(-scores)[:top_k]
        results = []
        for rank in ranked:
            semantic_score = None if semantic is None else float(semantic[rank])
            results.append(Recommendation(item=eligible[rank], score=float(scores[rank]), lexical_score=float(lexical[rank]), semantic_score=semantic_score, filter_notes=[]))
        return results
