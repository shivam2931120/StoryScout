"""Cached narrative passages, aggregated to one score per catalog record.

Only actual description/plot text is chunked. Source metadata placeholders are
not passages. Character offsets preserve provenance without copying full plots
into recommendation responses. Models are shared with document retrieval.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from scipy import sparse
from sklearn.preprocessing import normalize
from .config import MODEL_NAME, MODEL_CONFIG_VERSION
from .preprocessing import build_query_text

PASSAGE_CONFIG = {'version':'1.0', 'words':112, 'overlap':24, 'maximum':32, 'lexical_features':64, 'embedding_dtype':'float16'}
PASSAGE_WEIGHT = .45


def narrative_text(item):
    if item.retrieval_text:
        return item.retrieval_text
    if item.description_provenance or not item.source.startswith(('movielens','project-gutenberg')):
        return item.description if item.description.strip().lower() not in {'unknown','n/a','none'} else ''
    return ''


def passage_spans(text, words=112, overlap=24, maximum=32):
    """Overlapping word windows with exact offsets; bounded uniform sampling.

    All windows are retained for the current compact snapshot. If an imported
    record exceeds the cap, sample windows uniformly including both ends and
    disclose that coverage is partial, rather than silently taking its beginning.
    """
    if words < 1 or not 0 <= overlap < words or maximum < 2:
        raise ValueError('Invalid passage window configuration')
    tokens=list(re.finditer(r'\S+',text))
    if not tokens:
        return [], False
    starts=list(range(0,max(1,len(tokens)-words+1),words-overlap))
    last=max(0,len(tokens)-words)
    if starts[-1]!=last:
        starts.append(last)
    sampled=len(starts)>maximum
    if sampled:
        starts=[starts[i] for i in np.linspace(0,len(starts)-1,maximum,dtype=int)]
    return [(tokens[start].start(),tokens[min(start+words,len(tokens))-1].end()) for start in starts],sampled


def _pruned_rows(matrix, limit):
    """Bound sparse RAM; keep highest TF-IDF features and renormalize each row."""
    matrix=matrix.tocsr()
    indices=[]; values=[]; indptr=[0]
    for row in range(matrix.shape[0]):
        begin,end=matrix.indptr[row:row+2]
        weights=matrix.data[begin:end]
        keep=np.argsort(-weights,kind='stable')[:limit]
        cols=matrix.indices[begin:end][keep]
        order=np.argsort(cols)
        indices.extend(cols[order]); values.extend(weights[keep][order]); indptr.append(len(indices))
    result=sparse.csr_matrix((np.asarray(values,dtype=np.float32),np.asarray(indices,dtype=np.int32),np.asarray(indptr,dtype=np.int32)),shape=matrix.shape)
    return normalize(result,copy=False)


class PassageIndex:
    def __init__(self,items,vectorizer,lexical_key,artifact_dir,model=None):
        self.items=items; self.vectorizer=vectorizer; self.model=model
        self.embeddings=None; self.semantic_available=False; self.embedding_error=None
        self.sampled_records=[]
        bodies=[narrative_text(item) for item in items]
        rows=[]
        for owner,body in enumerate(bodies):
            spans,sampled=passage_spans(body,PASSAGE_CONFIG['words'],PASSAGE_CONFIG['overlap'],PASSAGE_CONFIG['maximum'])
            if sampled:self.sampled_records.append(items[owner].id)
            rows.extend((owner,start,end) for start,end in spans)
        self.spans=np.asarray(rows,dtype=np.int32).reshape(-1,3)
        self.counts=np.bincount(self.spans[:,0],minlength=len(items)) if len(rows) else np.zeros(len(items),dtype=int)
        self.starts=np.cumsum(np.r_[0,self.counts[:-1]])
        signature=json.dumps({'config':PASSAGE_CONFIG,'records':[(x.id,hashlib.sha256(body.encode()).hexdigest()) for x,body in zip(items,bodies)]},sort_keys=True)
        digest=hashlib.sha256(signature.encode()).hexdigest()
        directory=Path(artifact_dir)
        lexical_file=directory/f'passage_tfidf_{hashlib.sha256((digest+lexical_key).encode()).hexdigest()}.npz'
        if lexical_file.exists():
            self.matrix=sparse.load_npz(lexical_file)
        else:
            batches=[]
            for begin in range(0,len(rows),256):
                texts=[build_query_text(bodies[owner][start:end]) for owner,start,end in rows[begin:begin+256]]
                batches.append(_pruned_rows(vectorizer.transform(texts),PASSAGE_CONFIG['lexical_features']))
            self.matrix=sparse.vstack(batches,format='csr') if batches else sparse.csr_matrix((0,len(vectorizer.get_feature_names_out())),dtype=np.float32)
            temporary=lexical_file.with_suffix('.tmp.npz')
            sparse.save_npz(temporary,self.matrix);temporary.replace(lexical_file)
        if model is not None and rows:
            embedding_key=hashlib.sha256((digest+MODEL_NAME+MODEL_CONFIG_VERSION).encode()).hexdigest()
            embedding_file=directory/f'passages_{embedding_key}.npy'
            manifest_file=directory/f'passage_manifest_{items[0].media_type}.json'
            hashes=[hashlib.sha256(build_query_text(bodies[owner][start:end]).encode()).hexdigest() for owner,start,end in rows]
            config_key=MODEL_NAME+MODEL_CONFIG_VERSION+json.dumps(PASSAGE_CONFIG,sort_keys=True)
            try:
                if embedding_file.exists():
                    self.embeddings=np.load(embedding_file,mmap_mode='r')
                    if len(self.embeddings)!=len(rows):raise ValueError('Passage cache row mismatch')
                else:
                    old=None; lookup={}
                    if manifest_file.exists():
                        try:
                            meta=json.loads(manifest_file.read_text())
                            if meta['model_config']==config_key:
                                old=np.load(directory/Path(meta['file']).name,mmap_mode='r')
                                if len(old)==len(meta['hashes']):lookup={key:i for i,key in enumerate(meta['hashes'])}
                        except (OSError,ValueError,KeyError):old=None;lookup={}
                    missing=[i for i,key in enumerate(hashes) if key not in lookup]
                    pending=embedding_file.with_suffix('.tmp.npy')
                    output=None
                    for begin in range(0,len(missing),32):
                        ids=missing[begin:begin+32]
                        texts=[build_query_text(bodies[rows[i][0]][rows[i][1]:rows[i][2]]) for i in ids]
                        encoded=np.asarray(model.encode(texts,batch_size=8,normalize_embeddings=True,show_progress_bar=False,convert_to_numpy=True),dtype=np.float32)
                        encoded/=np.maximum(np.linalg.norm(encoded,axis=1,keepdims=True),1e-9)
                        if output is None:output=np.lib.format.open_memmap(pending,mode='w+',dtype=np.float16,shape=(len(rows),encoded.shape[1]))
                        output[ids]=encoded
                    if output is None:
                        output=np.lib.format.open_memmap(pending,mode='w+',dtype=np.float16,shape=(len(rows),old.shape[1]))
                    for i,key in enumerate(hashes):
                        if key in lookup:output[i]=old[lookup[key]]
                    output.flush();del output
                    pending.replace(embedding_file)
                    self.embeddings=np.load(embedding_file,mmap_mode='r')
                self.semantic_available=True
                manifest_file.write_text(json.dumps({'model_config':config_key,'file':embedding_file.name,'hashes':hashes}))
            except Exception as error:
                self.embeddings=None
                self.embedding_error=type(error).__name__
        self.indexed_records=int(np.count_nonzero(self.counts))

    @property
    def mode(self):
        if not self.indexed_records:return 'no narrative text'
        return 'TF-IDF + semantic passages' if self.semantic_available else 'TF-IDF passages'

    def score(self,query_vector,query_embedding,eligible_indices,mode,combine,calibrate):
        """Score eligible passages in bounded blocks; return one winner per item."""
        total=len(eligible_indices)
        mapping=np.full(len(self.items),-1,dtype=np.int32);mapping[eligible_indices]=np.arange(total)
        ids=np.flatnonzero(mapping[self.spans[:,0]]>=0)
        result={'score':np.zeros(total),'lexical':np.zeros(total),'semantic':np.zeros(total) if self.semantic_available and query_embedding is not None else None,
                'index':np.full(total,-1,dtype=np.int32),'coverage':np.zeros(total,dtype=np.int32)}
        qcols=query_vector.indices
        for start in range(0,len(ids),512):
            selected=ids[start:start+512]
            matrix=self.matrix[selected]
            lexical=(matrix @ query_vector.T).toarray().ravel()
            coverage=matrix[:,qcols].getnnz(axis=1) if len(qcols) else np.zeros(len(selected),dtype=int)
            semantic=None
            if result['semantic'] is not None:
                vectors=np.asarray(self.embeddings[selected],dtype=np.float32)
                semantic=np.clip(vectors @ query_embedding,-1,1)
            scores=calibrate(semantic) if semantic is not None and mode=='semantic' else combine(lexical,semantic) if semantic is not None and mode=='hybrid' else lexical
            supported=(lexical>=.12) & (coverage>=max(1,min(2,len(qcols))))
            if semantic is not None:supported |= semantic>=.40
            scores=np.where(supported,scores,0.)
            for offset,pid in enumerate(selected):
                owner=mapping[self.spans[pid,0]]
                if scores[offset]>result['score'][owner]:
                    result['score'][owner]=scores[offset]
                    result['lexical'][owner]=lexical[offset]
                    if semantic is not None:result['semantic'][owner]=semantic[offset]
                    result['index'][owner]=pid
                    result['coverage'][owner]=coverage[offset]
        return result

    def evidence(self,pid,lexical,semantic):
        owner,start,end=self.spans[pid]
        item=self.items[owner]
        return {'passage_number':int(pid-self.starts[owner]+1),'passage_count':int(self.counts[owner]),
                'source':item.text_source or item.description_source or ('Original demonstration description' if item.source=='demo' else item.source),
                'source_url':item.text_source_url or item.description_source_url or item.source_url,
                'source_generated':'source-generated' in item.description_provenance.lower(),
                'lexical_similarity':float(lexical),'semantic_similarity':None if semantic is None else float(semantic),
                'partial_coverage':item.id in self.sampled_records}
