"""Lexical, semantic, and hybrid retrieval with hard filters before ranking."""
from __future__ import annotations
import hashlib, json, pickle, time, os
from functools import lru_cache
from pathlib import Path
import numpy as np
import sklearn
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .config import ARTIFACT_DIR, MODEL_NAME, MODEL_CONFIG_VERSION
from .preprocessing import build_query_text
from .relevance import topic_gate, quality_gate, preference_boost, POLICIES
from .schemas import CatalogItem, Preferences, Recommendation
from .query_understanding import MOOD_PROTOTYPES, THEME_PROTOTYPES, meaningful_query, content_chunks, build_search_query

@lru_cache(maxsize=1)
def _sentence_model():
    if os.getenv('STORYSCOUT_EMBEDDING_BACKEND')=='onnx':
        from .onnx_encoder import QuantizedMiniLM
        return QuantizedMiniLM()
    from sentence_transformers import SentenceTransformer
    try:
        from huggingface_hub import try_to_load_from_cache
        cached_config = try_to_load_from_cache(MODEL_NAME, "config.json")
    except Exception:
        cached_config = None
    local_only = isinstance(cached_config, str) and Path(cached_config).is_file()
    return SentenceTransformer(MODEL_NAME, device="cpu", local_files_only=local_only)


SEMANTIC_COSINE_FLOOR = 0.18
SEMANTIC_COSINE_CEILING = 0.62


def calibrate_semantic_scores(semantic: np.ndarray) -> np.ndarray:
    """Map weak semantic matches to zero instead of treating cosine 0 as 0.5."""
    return np.clip((semantic - SEMANTIC_COSINE_FLOOR) / (SEMANTIC_COSINE_CEILING - SEMANTIC_COSINE_FLOOR), 0.0, 1.0)


def combine_hybrid_scores(lexical: np.ndarray, semantic: np.ndarray) -> np.ndarray:
    """Blend lexical cosine [0, 1] with threshold-calibrated semantic cosine."""
    semantic_unit = calibrate_semantic_scores(semantic)
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
        self.last_diagnostics = {}
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
        vectorizer_config = json.dumps({"ngram_range": [1, 2], "min_df": 1, "sublinear_tf": True, "stop_words":"english", "max_features":60000}, sort_keys=True)
        lexical_key = hashlib.sha256((sklearn.__version__ + MODEL_CONFIG_VERSION + vectorizer_config + "\n".join(docs)).encode("utf-8")).hexdigest()
        lexical_file = self.artifact_dir / f"tfidf_{lexical_key}.pkl"
        if lexical_file.exists():
            with lexical_file.open("rb") as cache:
                self.vectorizer, self.matrix = pickle.load(cache)
        else:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, stop_words='english', max_features=60000)
            self.matrix = self.vectorizer.fit_transform(docs)
            with lexical_file.open("wb") as cache:
                pickle.dump((self.vectorizer, self.matrix), cache, protocol=pickle.HIGHEST_PROTOCOL)
        self.feature_names=self.vectorizer.get_feature_names_out()
        # Reuse the corpus vocabulary; title/entity matching is a separate small
        # sparse field, so names are not drowned out by long plot descriptions.
        self.title_matrix = self.vectorizer.transform([' '.join([item.title, *item.search_aliases]) for item in self.items])
        if self.mode in {"semantic", "hybrid"}:
            try:
                self.model = _sentence_model()
                digest = hashlib.sha256((MODEL_NAME + MODEL_CONFIG_VERSION + "\n".join(docs)).encode("utf-8")).hexdigest()
                embedding_file = self.artifact_dir / f"embeddings_{digest}.npy"
                manifest_file=self.artifact_dir/f"embedding_manifest_{self.items[0].media_type}.json"
                document_hashes=[hashlib.sha256(doc.encode()).hexdigest() for doc in docs]
                if embedding_file.exists():
                    self.embeddings = np.load(embedding_file, mmap_mode="r")
                else:
                    # Reuse unchanged documents after bounded metadata/catalog edits.
                    previous,lookup=None,{}
                    if manifest_file.exists():
                        try:
                            manifest=json.loads(manifest_file.read_text())
                            if manifest['model_config']==MODEL_NAME+MODEL_CONFIG_VERSION:
                                previous=np.load(self.artifact_dir/Path(manifest['file']).name,mmap_mode='r')
                                lookup={key:i for i,key in enumerate(manifest['document_hashes'])}
                                if len(previous)!=len(manifest['document_hashes']): previous,lookup=None,{}
                        except (OSError,ValueError,KeyError): previous,lookup=None,{}
                    # Mean-pooled beginning/middle/end chunks cover full plot text,
                    # instead of silently discarding everything beyond 256 tokens.
                    chunks, owners = [], []
                    for number, doc in enumerate(docs):
                        if document_hashes[number] in lookup: continue
                        parts = content_chunks(doc)
                        chunks.extend(parts); owners.extend([number]*len(parts))
                    encoded = self.model.encode(chunks, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True) if chunks else None
                    dimensions=encoded.shape[1] if encoded is not None else previous.shape[1]
                    self.embeddings = np.zeros((len(docs), dimensions), dtype=np.float32)
                    for number,key in enumerate(document_hashes):
                        if key in lookup: self.embeddings[number]=previous[lookup[key]]
                    if encoded is not None: np.add.at(self.embeddings, owners, encoded)
                    self.embeddings /= np.maximum(np.linalg.norm(self.embeddings, axis=1, keepdims=True), 1e-9)
                    np.save(embedding_file, self.embeddings)
                manifest_file.write_text(json.dumps({'model_config':MODEL_NAME+MODEL_CONFIG_VERSION,'file':embedding_file.name,'document_hashes':document_hashes}))
                self.semantic_available = True
            except Exception:
                self.semantic_available = False
        self._prepare_profiles(docs)
        self.preparation_seconds = time.perf_counter() - start

    def _prepare_profiles(self, docs):
        """Corpus TF-IDF keyphrases and local semantic prototype alignment."""
        terms = self.feature_names
        for number, item in enumerate(self.items):
            row = self.matrix[number]
            best = sorted(zip(row.indices,row.data),key=lambda pair:-pair[1])
            item.nlp_keywords = [str(terms[i]) for i,_ in best if len(str(terms[i]))>3 and not str(terms[i]).isdigit()][:6]
        self.mood_alignment = self._prototype_alignment(MOOD_PROTOTYPES)
        self.theme_alignment = self._prototype_alignment(THEME_PROTOTYPES)
        for number,item in enumerate(self.items):
            # Predicted tags are never written into catalog genres/moods/themes.
            has_text = bool(item.retrieval_text or item.description_provenance or item.source == 'demo')
            if has_text:
                item.inferred_moods = {name:round(float(values[number]),3) for name,values in self.mood_alignment.items() if values[number] >= .35}
                item.inferred_themes = {name:round(float(values[number]),3) for name,values in self.theme_alignment.items() if values[number] >= .35}
        digest=hashlib.sha256((MODEL_CONFIG_VERSION+'\n'.join(docs)).encode()).hexdigest()[:20]
        profile_file=self.artifact_dir/f'nlp_profiles_{digest}.json'
        if not profile_file.exists():
            profile_file.write_text(json.dumps({'method':'TF-IDF keyphrases + semantic prototype cosine; inferred tags are not verified facts',
                'items':{x.id:{'keyphrases':x.nlp_keywords,'inferred_moods':x.inferred_moods,'inferred_themes':x.inferred_themes} for x in self.items}}))

    def _prototype_alignment(self, prototypes):
        names=list(prototypes)
        if self.semantic_available:
            encoded=self.model.encode(list(prototypes.values()),normalize_embeddings=True,show_progress_bar=False)
            raw=np.asarray(self.embeddings @ np.asarray(encoded).T)
            # Fixed, documented scaling for soft alignment; not probabilities.
            aligned=np.clip((raw-.12)/.35,0,1)
        else:
            raw=cosine_similarity(self.matrix,self.vectorizer.transform(list(prototypes.values())))
            aligned=np.clip(raw*4,0,1)
        return {name:aligned[:,i] for i,name in enumerate(names)}

    def _hard_filter(self, item: CatalogItem, pref: Preferences) -> tuple[bool, list[str]]:
        notes = []
        if pref.language and pref.language.lower() not in item.language.lower().split('|'): notes.append(f"language is not {pref.language}")
        if pref.min_year is not None and (item.year is None or item.year < pref.min_year): notes.append(f"year is unknown or before {pref.min_year}")
        if pref.max_year is not None and (item.year is None or item.year > pref.max_year): notes.append(f"year is unknown or after {pref.max_year}")
        if item.media_type == "book" and pref.max_pages is not None and (item.page_count is None or item.page_count > pref.max_pages): notes.append(f"pages are unknown or over {pref.max_pages}")
        if item.media_type == "movie" and pref.max_runtime is not None and (item.runtime_minutes is None or item.runtime_minutes > pref.max_runtime): notes.append(f"runtime is unknown or over {pref.max_runtime}")
        if set(pref.excluded_genres) & set(item.genres): notes.append("excluded genre")
        if pref.preferred_genres and not set(pref.preferred_genres) & set(item.genres + item.subject_genres): notes.append('does not match a selected genre')
        if pref.excluded_genres and not item.genres: notes.append("genres are unknown; exclusion cannot be verified")
        # Verified warning labels can enforce negative content; unknown is not treated as safe.
        if "graphic violence" in pref.negative_content and "graphic violence" in item.verified_warnings: notes.append("verified graphic violence")
        return not notes, notes

    def search(self, query: str, pref: Preferences, top_k: int = 5, exclude_ids: set[str] | None = None, seen_ids: set[str] | None = None, topic_query: str | None = None) -> list[Recommendation]:
        exclude_ids = exclude_ids or set()
        eligible, eligible_indices, notes = [], [], {}
        rejected = Counter()
        for item_index, item in enumerate(self.items):
            ok, item_notes = self._hard_filter(item, pref)
            if ok and item.id not in exclude_ids:
                eligible.append(item)
                eligible_indices.append(item_index)
            notes[item.id] = item_notes
            rejected.update(item_notes)
        self.last_diagnostics = {'catalog_size':len(self.items),'eligible_count':len(eligible),'excluded_count':len(self.items)-len(eligible),
            'filter_rejections':dict(rejected),'plot_text_candidates':sum(bool(x.retrieval_text) for x in eligible),
            'selected_genre_policy':'match any selected source genre or documented source-subject mapping (OR)','diversification':'maximal marginal relevance, lambda=0.84',
            'ranking':'text similarity + active genre/mood/theme alignment + bounded novelty penalty'}
        if not eligible: return []
        original_query = query
        topic = build_search_query(original_query, pref)[1] if topic_query is None else topic_query
        query = meaningful_query(query)
        attributes = bool(pref.preferred_genres or pref.desired_mood or pref.themes)
        filter_only = not topic.strip() and not attributes
        qvector = self.vectorizer.transform([build_query_text(query)])
        lexical = cosine_similarity(self.matrix[eligible_indices], qvector).ravel() if query else np.zeros(len(eligible))
        topic_vector = self.vectorizer.transform([build_query_text(topic)])
        topic_lexical = cosine_similarity(self.matrix[eligible_indices], topic_vector).ravel() if topic.strip() else np.zeros(len(eligible))
        entity_lexical = cosine_similarity(self.title_matrix[eligible_indices], topic_vector).ravel() if topic.strip() else np.zeros(len(eligible))
        topic_lexical = np.maximum(topic_lexical, .30*entity_lexical)
        semantic = topic_semantic = None
        if self.semantic_available and query and not filter_only:
            texts = [build_query_text(query)] + ([build_query_text(topic)] if topic.strip() else [])
            encoded = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            semantic = cosine_similarity(encoded[:1], self.embeddings[eligible_indices]).ravel()
            if topic.strip():
                topic_semantic = cosine_similarity(encoded[1:2], self.embeddings[eligible_indices]).ravel()
        def text_similarity(lexical_values, semantic_values):
            if semantic_values is not None and self.mode == "semantic":
                return calibrate_semantic_scores(semantic_values)
            if semantic_values is not None and self.mode == "hybrid":
                return combine_hybrid_scores(lexical_values, semantic_values)
            return lexical_values
        general_scores = text_similarity(lexical, semantic)
        topic_scores = text_similarity(topic_lexical, topic_semantic) if topic.strip() else general_scores
        scores = .80*topic_scores + .20*general_scores if topic.strip() else general_scores
        text_scores = scores.copy()
        rich_text=np.array([bool(x.retrieval_text or x.description_provenance or x.source=='demo') for x in eligible])
        source_generated=np.array(['source-generated' in x.description_provenance.lower() for x in eligible])
        scores=scores*np.where(rich_text,np.where(source_generated,.85,1.0),.65)
        domain = self.items[0].media_type
        allowed = topic_gate(domain, topic_lexical, topic_semantic) if topic.strip() else np.ones(len(eligible), dtype=bool)
        genre=np.array([len(set(x.genres+x.subject_genres)&set(pref.preferred_genres))/max(len(pref.preferred_genres),1) for x in eligible])
        learned=np.array([len(set(x.predicted_genres)&set(pref.preferred_genres))/max(len(pref.preferred_genres),1) for x in eligible])
        mood=np.zeros(len(eligible)); theme=np.zeros(len(eligible))
        if pref.desired_mood:
            mood=self.mood_alignment.get(pref.desired_mood,np.zeros(len(self.items)))[eligible_indices].copy()
            for i,item in enumerate(eligible):
                if pref.desired_mood in item.mood_tags: mood[i]=1
        if pref.themes:
            parts=[]
            for name in pref.themes:
                values=self.theme_alignment.get(name,np.zeros(len(self.items)))[eligible_indices].copy()
                for i,item in enumerate(eligible):
                    if name in item.theme_tags: values[i]=1
                parts.append(values)
            theme=np.mean(parts,axis=0)
        if not topic.strip() and pref.preferred_genres:
            # Verified genre-only searches have a legitimate categorical match,
            # even when a metadata-only record has no descriptive text.
            scores = np.maximum(scores, .12*genre)
        base_scores = scores.copy()
        qualified, cutoff = quality_gate(domain, base_scores, allowed) if not filter_only else (allowed, 0.)
        scores = preference_boost(base_scores, genre, mood, theme, learned)
        self.last_diagnostics.update({'topic_query': topic[:800], 'query_strategy': 'separate topic and preference channels',
            'topic_relevance_rejections': int(np.count_nonzero(~allowed)),
            'quality_rejections': int(np.count_nonzero(~qualified)),
            'quality_score_floor': round(cutoff, 4), 'relevance_policy': POLICIES[domain],
            'ranking': 'topic relevance gate, bounded multiplicative preferences, quality cutoff, then diversity'})
        novelty=np.array([.035 if x.id in (seen_ids or set()) else 0 for x in eligible])
        scores=np.maximum(scores-novelty,0)
        if filter_only:
            # No fake relevance: use a varied sample of verified filter matches.
            # With only factual filters there is no text query to match. Use
            # source completeness and diversity, not alphabetical filler.
            scores = np.array([.06*bool(x.retrieval_text or x.description_provenance or x.source=='demo') + .025*(x.language.lower()!='unknown') + .025*(x.year is not None) + .02*bool(x.authors or x.director) + .01*bool(x.page_count or x.runtime_minutes) for x in eligible])
            pool=sorted(range(len(eligible)),key=lambda i:(eligible[i].id in (seen_ids or set()),-scores[i],eligible[i].id))[:80]
        else:
            positive=np.flatnonzero(qualified & (scores > 0))
            if not len(positive): return []
            pool=sorted(positive,key=lambda i:(-scores[i],eligible[i].id))[:80]
        # MMR penalizes near-duplicate narratives, without changing any filter.
        selected=[]
        original=np.array(eligible_indices)
        if self.semantic_available:
            pairwise=cosine_similarity(self.embeddings[original[pool]])
        else:
            pairwise=cosine_similarity(self.matrix[original[pool]])
        while pool and len(selected)<min(top_k,len(pool)):
            choices=[i for i in range(len(pool)) if i not in selected]
            best=max(choices,key=lambda i:(.84*float(scores[pool[i]])-.16*max((float(pairwise[i,j]) for j in selected),default=0),-i))
            selected.append(best)
        ranked=[pool[i] for i in selected]
        results = []
        for rank in ranked:
            semantic_score = None if semantic is None else float(semantic[rank])
            terms=[]
            if query:
                overlap=self.matrix[eligible_indices[rank]].multiply(qvector).tocoo()
                names=self.feature_names
                terms=[str(names[i]) for i,_ in sorted(zip(overlap.col,overlap.data),key=lambda pair:-pair[1])[:3]]
            results.append(Recommendation(item=eligible[rank], score=0. if filter_only else float(scores[rank]), lexical_score=float(lexical[rank]), semantic_score=semantic_score,
                filter_notes=['filter-only results; no text similarity signal'] if filter_only else [], matched_terms=terms,
                score_components={'text_similarity':round(float(text_scores[rank]),4),'genre_coverage':round(float(genre[rank]),4),'text_classifier_genre_match':round(float(learned[rank]),4),'mood_alignment':round(float(mood[rank]),4),'theme_alignment':round(float(theme[rank]),4),'topic_lexical_similarity':round(float(topic_lexical[rank]),4),'topic_semantic_similarity':None if topic_semantic is None else round(float(topic_semantic[rank]),4),'metadata_completeness':round(float(scores[rank]),4) if filter_only else None,'novelty_penalty':round(float(novelty[rank]),4)}))
        self.last_diagnostics['returned_count']=len(results)
        self.last_diagnostics['query_text']=query[:800]
        return results
