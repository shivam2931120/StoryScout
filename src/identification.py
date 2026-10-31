"""Description-to-title identification, separate from recommendation preferences.

Local hybrid retrieval generates candidates. Clue-to-passage lexical evidence and
optional bounded Nemotron assessment rerank them; no model-created titles enter.
Scores are uncalibrated ranking signals, never probabilities of correctness.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from .schemas import Recommendation


@dataclass
class PlotClue:
    text: str
    uncertain: bool = False


def is_identification(text):
    lower=text.lower().replace("what's", "what is")
    return bool(re.search(r"\b(?:identify (?:this|a|the)|what (?:(?:is|was) (?:the |that )?)?(?:movie|film|book)|which (?:movie|film|book)|can(?:not|'t|’t) remember (?:the |its )?(?:name|title)|trying to remember|forgot (?:the |its )?(?:name|title)|a (?:man|woman|boy|girl) (?:who |goes |wakes |finds ))",lower))


def local_clues(text):
    text = re.sub(r"^(?:identify (?:this|the) (?:movie|film|book)|what (?:is|was) (?:the |that )?(?:movie|film|book)(?: where| about)?)[\s:?.]*", "", text, flags=re.I)
    parts = re.split(r"[.;!?\n]+|\b(?:and then|but|also)\b", text, flags=re.I)
    return [PlotClue(p.strip()[:240], bool(re.search(r"\b(maybe|perhaps|possibly|think|not sure)\b",p,re.I))) for p in parts if len(p.strip().split())>=3][:6] or [PlotClue(text[:240])]


def plot_text(item):
    if item.retrieval_text:
        return item.retrieval_text
    if item.source.startswith(('movielens','project-gutenberg','wikidata-catalog','openlibrary-catalog')) and not item.description_provenance:
        return ''
    return item.description


def lexical_query(index, text):
    """Vocabulary-constrained inflection expansion, retaining the original words."""
    extras=set()
    for word in re.findall(r'[a-z]+',text.lower()):
        if word in ENGLISH_STOP_WORDS or len(word)<4: continue
        forms={word+'s',word+'es'}
        if word.endswith('s'): forms.add(word[:-1])
        if word.endswith('es'): forms.add(word[:-2])
        if word.endswith('ies'): forms.add(word[:-3]+'y')
        for suffix in ('ing','ed'):
            if word.endswith(suffix): forms.update({word[:-len(suffix)],word[:-len(suffix)]+'e'})
        extras.update(form for form in forms if len(form)>2 and form in index.vectorizer.vocabulary_)
    return text+' '+' '.join(sorted(extras))


def recall_candidates(index, query, preferences):
    """Broad hybrid recall; recommendation diversity/cutoffs do not identify titles."""
    from .retrieval import _query_vector, combine_hybrid_scores, calibrate_semantic_scores
    vector=index.vectorizer.transform([lexical_query(index,query)])
    lexical=cosine_similarity(index.matrix,vector).ravel()
    semantic=None
    scores=lexical
    if index.semantic_available:
        semantic=cosine_similarity([_query_vector(index.model,query)],index.embeddings).ravel()
        scores=calibrate_semantic_scores(semantic) if index.mode=='semantic' else combine_hybrid_scores(lexical,semantic)
    ranked=sorted(range(len(index.items)),key=lambda i:(-scores[i],index.items[i].id))
    results=[]
    for i in ranked:
        item=index.items[i]
        if not plot_text(item).strip() or not index._hard_filter(item,preferences)[0]: continue
        if lexical[i]<.04 and (semantic is None or semantic[i]<.32): continue
        results.append(Recommendation(item=item,score=float(scores[i]),lexical_score=float(lexical[i]),semantic_score=float(semantic[i]) if semantic is not None else None))
        if len(results)==12: break
    return results


def identify(engine, text, state):
    clues = local_clues(text)
    extraction = 'local clause rules'
    interpreter = engine.query_interpreter
    if interpreter and hasattr(interpreter, 'identify_task'):
        payload = interpreter.identify_task('extract', {'description':text}, [])
        if isinstance(payload, dict) and isinstance(payload.get('clues'),list):
            validated=[]
            for row in payload['clues'][:6]:
                if isinstance(row,dict) and type(row.get('text')) is str and 5<=len(row['text'])<=240 and row['text'].casefold() in text.casefold() and type(row.get('uncertain',False)) is bool:
                    validated.append(PlotClue(row['text'], row.get('uncertain',False)))
            if validated:
                clues=validated; extraction='Nemotron source-span extraction'
    query=' '.join(c.text for c in clues)
    factual=state.preferences.clone()
    factual.desired_mood=None; factual.themes=[]; factual.positive_content=[]
    found={}
    engine.last_diagnostics={}
    for domain in engine._active_domains(state.media_selection):
        index=engine.indexes[domain]
        # Whole-description recall plus per-clue recall uses the existing local
        # document and passage indexes. No preference mood/theme inference here.
        for search in [query]+[c.text for c in clues[:3]]:
            narrative=index.search(search,factual,top_k=12,topic_query=search)
            for rec in narrative+recall_candidates(index,search,factual):
                if plot_text(rec.item).strip():
                    old=found.get(rec.item.id)
                    if old is None or rec.score>old.score: found[rec.item.id]=rec
        engine.last_diagnostics[domain]=dict(index.last_diagnostics)
    candidates=sorted(found.values(),key=lambda r:(-r.score,r.item.id))[:8]
    documents={}; evidence={}
    for rec in candidates:
        index=engine.indexes[rec.item.media_type]
        text_source=plot_text(rec.item)
        sentences=[s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',text_source) if s.strip()]
        # Bound a long source without asking the model to read full copyrighted plots.
        sentences=[s[:500] for s in sentences][:240]
        vectors=index.vectorizer.transform(sentences)
        rows=[]; excerpts=[]
        for number,clue in enumerate(clues):
            q=index.vectorizer.transform([lexical_query(index,clue.text)])
            values=cosine_similarity(vectors,q).ravel()
            best=int(np.argmax(values))
            overlap=set(index.feature_names[q.indices]) & set(index.feature_names[vectors[best].indices])
            overlap={term for term in overlap if ' ' not in term}
            if values[best]>=.18 and len(overlap)>=2:
                rows.append({'clue':number,'verdict':'text_overlap','quote':sentences[best][:200], 'method':'local TF-IDF passage overlap'})
            excerpts.append(sentences[best])
        documents[rec.item.id]=text_source[:1000]+'\n'+' '.join(dict.fromkeys(excerpts))[:1200]
        evidence[rec.item.id]=rows
    source_plots={rec.item.id:plot_text(rec.item) for rec in candidates}
    assessment='local passage overlap'
    if candidates and interpreter and hasattr(interpreter,'identify_task'):
        payload=interpreter.identify_task('assess', {'clues':[{'text':c.text,'uncertain':c.uncertain} for c in clues]},
            [{'id':r.item.id,'title':r.item.title,'passages':documents[r.item.id]} for r in candidates])
        if isinstance(payload,dict) and isinstance(payload.get('evidence'),list):
            accepted={}
            for row in payload['evidence'][:48]:
                if not isinstance(row,dict): continue
                item_id=row.get('id'); clue=row.get('clue'); quote=row.get('quote'); verdict=row.get('verdict')
                if item_id not in documents or type(clue) is not int or not 0<=clue<len(clues): continue
                if verdict not in {'supported','contradicted'} or type(quote) is not str or not 10<=len(quote)<=500: continue
                # Tolerate typography/JSON apostrophe escaping while returning
                # only the actual source span; no paraphrase can pass this check.
                quote=quote.replace("\\'", "'").replace('’', "'").replace('“', '"').replace('”', '"')
                pattern=r'\s+'.join(re.escape(word).replace("'", "['’]").replace('"', '["“”]') for word in quote.split())
                source_match=re.search(pattern,source_plots[item_id],re.I)
                if not source_match or not re.search(pattern,documents[item_id],re.I): continue
                # Display the original source span, preserving its typography.
                quote=source_match.group(0)[:200]
                if any(x['clue']==clue for x in accepted.get(item_id,[])): continue
                accepted.setdefault(item_id,[]).append({'clue':clue,'verdict':verdict,'quote':quote,'method':'Nemotron inference; quote checked against source passage'})
            if accepted:
                evidence.update(accepted); assessment='Nemotron clue comparison with source-quote validation'
    for rec in candidates:
        rows=evidence[rec.item.id]
        weights=[.5 if c.uncertain else 1. for c in clues]
        total=sum(weights) or 1
        support=sum(weights[r['clue']] for r in rows if r['verdict'] in {'supported','text_overlap'})/total
        contradictions=sum(weights[r['clue']] for r in rows if r['verdict']=='contradicted')/total
        rec.score=.65*rec.score+.35*support-.4*contradictions
        rec.score_components.update(clue_coverage=round(support,4),clue_contradictions=round(contradictions,4))
        rec.explanation='Possible description match. '+('Clue evidence: '+ '; '.join(f'“{r["quote"]}” ({r["verdict"].replace("_"," ")})' for r in rows[:2]) if rows else 'Narrative similarity only; your specific clues remain unverified.')
    candidates.sort(key=lambda r:(-r.score,r.item.id))
    # No invented confidence percentages. Contradictions visibly lower rank;
    # incomplete evidence always leaves identification open to clarification.
    floor=max(.08, .55*candidates[0].score) if candidates else .08
    candidates=[r for r in candidates if r.score>=floor][:5]
    question='What is one specific scene, character name, or unusual object you remember?'
    if len(candidates)>=2:
        a,b=candidates[:2]
        if ('animation' in a.item.genres)!=('animation' in b.item.genres): question='Was the story animated or live action?'
        elif a.item.media_type!=b.item.media_type: question='Do you remember reading this story or watching it?'
        elif a.item.year and b.item.year and abs(a.item.year-b.item.year)>=15: question=f'Do you remember the release or publication year? The leading candidates span {min(a.item.year,b.item.year)} to {max(a.item.year,b.item.year)}.'
    engine.last_interpretation={'status': 'used' if extraction.startswith('Nemotron') or assessment.startswith('Nemotron') else 'fallback' if interpreter and hasattr(interpreter,'identify_task') else 'not_needed', 'purpose':'plot clue extraction and source-grounded comparison'}
    details={'clues':[{'text':c.text,'uncertain':c.uncertain} for c in clues], 'extraction':extraction,'assessment':assessment,
             'question':question,'candidate_count':len(candidates),'status':'possible_matches' if candidates else 'insufficient_evidence',
             'limitation':'Candidates depend on catalog plot coverage. Ranking scores are not confidence probabilities.'}
    results={domain:[r for r in candidates if r.item.media_type==domain] for domain in engine._active_domains(state.media_selection)}
    reply=('These are possible matches to your description. ' if candidates else 'I could not find a supported match in the described catalog. ')+question
    return reply,results,details
