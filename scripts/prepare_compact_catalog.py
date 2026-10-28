"""Create a deterministic, source-backed subset for 512 MB hosting.

Preserves demo/reference titles, descriptions and known movie runtimes first.
Samples remaining source genres using stable hashes, never inventing records.
"""
from dataclasses import asdict
import gzip,hashlib,json,os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.data_loader import load_active_catalogs

def prepare():
    os.environ.pop('STORYSCOUT_CATALOG_PROFILE',None)
    catalogs=load_active_catalogs()
    result={}
    for domain,limit in [('book',1000),('movie',1500)]:
        items=catalogs[domain]
        def priority(x):
            return (not x.source.startswith('demo'),not bool(x.runtime_minutes if domain=='movie' else x.description_provenance),not bool(x.retrieval_text if domain=='movie' else x.subject_genres),hashlib.sha256(x.id.encode()).hexdigest())
        selected=sorted(items,key=priority)[:limit]
        result[domain]=[asdict(x) for x in sorted(selected,key=lambda x:x.id)]
    destination=ROOT/'data/compact/catalogs.json.gz'
    destination.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(destination,'wt',encoding='utf-8') as target:json.dump(result,target)
    summary={'profile':'compact','policy':'deterministic source-backed subset; demo first, then known movie runtimes and source plots; described books then subject mappings; stable SHA-256 tie breaking',
             'counts':{k:len(v) for k,v in result.items()},'source_counts':{k:len(v) for k,v in catalogs.items()}}
    (destination.parent/'manifest.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':prepare()
