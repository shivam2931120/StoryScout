"""Train and evaluate title vs plot genre classifiers on the SAME held-out IDs.

No genre strings are appended to inputs. Text fitting and threshold selection
use only training/validation records; plot-hash groups prevent duplicate leaks.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import pickle
import sys
import time
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.data_loader import load_active_catalogs


def run():
    started=time.perf_counter()
    items=[x for x in load_active_catalogs()['movie'] if x.retrieval_text and x.genres]
    if len(items)<200: raise SystemExit('Not enough source-labeled plot records to support this experiment.')
    groups=np.array([hashlib.sha256(' '.join(x.retrieval_text.lower().split()).encode()).hexdigest() for x in items])
    all_ids=np.arange(len(items))
    development,test=next(GroupShuffleSplit(n_splits=1,test_size=.20,random_state=42).split(all_ids,groups=groups))
    inner_train,inner_val=next(GroupShuffleSplit(n_splits=1,test_size=.20,random_state=43).split(development,groups=groups[development]))
    train,val=development[inner_train],development[inner_val]
    counts=Counter(g for i in train for g in items[i].genres)
    labels=sorted(g for g,count in counts.items() if count>=30)
    mlb=MultiLabelBinarizer(classes=labels)
    targets=mlb.fit_transform([[g for g in x.genres if g in labels] for x in items])
    results={'method':'Description-only supervised multilabel genre experiment; title baseline uses identical splits',
        'split':'Plot-hash GroupShuffleSplit: 20% test (seed 42); 20% of development for validation (seed 43)',
        'records':len(items),'train_records':len(train),'validation_records':len(val),'test_records':len(test),
        'test_ids':[items[i].id for i in test], 'label_training_support':dict(sorted((g,counts[g]) for g in labels)),
        'labels_not_appended_to_inputs':True,'models':{}}
    for name in ['title_only','plot_text']:
        texts=[x.title if name=='title_only' else x.retrieval_text for x in items]
        vectorizer=TfidfVectorizer(ngram_range=(1,2),stop_words='english',min_df=2,max_df=.98,max_features=24000,sublinear_tf=True)
        matrix=vectorizer.fit_transform([texts[i] for i in train])
        classifier=OneVsRestClassifier(LogisticRegression(C=2,class_weight='balanced',solver='liblinear',max_iter=300,random_state=42),n_jobs=1)
        classifier.fit(matrix,targets[train])
        probabilities=classifier.predict_proba(vectorizer.transform([texts[i] for i in val]))
        threshold=max([.25,.35,.45,.5],key=lambda t:f1_score(targets[val],probabilities>=t,average='micro',zero_division=0))
        # Refit learned vocabulary/weights on development only; test remains untouched.
        matrix=vectorizer.fit_transform([texts[i] for i in development])
        classifier.fit(matrix,targets[development])
        predictions=classifier.predict_proba(vectorizer.transform([texts[i] for i in test]))>=threshold
        report=classification_report(targets[test],predictions,target_names=labels,output_dict=True,zero_division=0)
        results['models'][name]={'threshold_selected_on_validation':threshold,'classification_report':report,'input_fields':['title'] if name=='title_only' else ['source plot text']}
        print(name,'held-out micro F1',report['micro avg']['f1-score'],flush=True)
        if name=='plot_text':
            with (ROOT/'artifacts/genre_description_model.pkl').open('wb') as handle:
                pickle.dump({'vectorizer':vectorizer,'classifier':classifier,'labels':labels,'threshold':threshold,'source':'Wikipedia plot text','dataset_hash':hashlib.sha256(''.join(groups).encode()).hexdigest()},handle)
            inferred=classifier.predict_proba(vectorizer.transform(texts))>=threshold
            by_id={item.id:[g for g,hit in zip(labels,inferred[i]) if hit] for i,item in enumerate(items)}
            (ROOT/'data/enriched/genre_predictions.json').write_text(json.dumps({'method':'locally trained TF-IDF + one-vs-rest logistic regression; predictions are separate from source genres','items':by_id}))
    results['elapsed_seconds']=round(time.perf_counter()-started,3)
    (ROOT/'artifacts/genre_text_results.json').write_text(json.dumps(results,indent=2))
    print('Saved held-out reports, model artifact, and separately marked predictions.',flush=True)

if __name__=='__main__': run()
