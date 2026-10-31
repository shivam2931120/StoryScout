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

# Explicit demonstration/reference coverage, using existing source-backed plots.
# These names retain real records; they never create titles or missing metadata.
IDENTIFICATION_ANCHORS = {
    'inception', 'the matrix', 'matrix, the', 'memento', 'titanic',
    'jurassic park', 'shutter island', 'the truman show', 'truman show, the',
    'the sixth sense', 'sixth sense, the', 'finding nemo', 'the lion king',
    'lion king, the', 'fight club', 'the prestige', 'prestige, the',
    'eternal sunshine of the spotless mind', 'the shawshank redemption',
    'shawshank redemption, the', 'forrest gump', 'the silence of the lambs',
    'silence of the lambs, the', 'the godfather', 'godfather, the',
}

def prepare():
    os.environ.pop('STORYSCOUT_CATALOG_PROFILE',None)
    catalogs=load_active_catalogs()
    result={}
    for domain,limit in [('book',1000),('movie',1500)]:
        items=catalogs[domain]
        def priority(x):
            return (not x.source.startswith('demo'),not (domain=='movie' and x.title.casefold() in IDENTIFICATION_ANCHORS and bool(x.retrieval_text)),not (x.id.startswith(('book_ol_','movie_wd_','movie_pub_')) and bool(x.description_provenance)),not bool(x.runtime_minutes if domain=='movie' else x.description_provenance),not bool(x.retrieval_text if domain=='movie' else x.subject_genres),hashlib.sha256(x.id.encode()).hexdigest())
        selected=sorted(items,key=priority)[:limit]
        result[domain]=[asdict(x) for x in sorted(selected,key=lambda x:x.id)]
    destination=ROOT/'data/compact/catalogs.json.gz'
    destination.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(destination,'wt',encoding='utf-8') as target:json.dump(result,target)
    # Full title identities remain searchable without expanding the embedding index.
    fields = {"id", "media_type", "title", "genres", "language", "year", "source", "source_url",
              "authors", "page_count", "publisher", "director", "runtime_minutes", "search_aliases",
              "title_aliases", "description_source", "description_source_url", "description_provenance", "metadata_provenance"}
    directory = []
    for items in catalogs.values():
        for item in items:
            record = {key: value for key, value in asdict(item).items() if key in fields and value}
            record["description"] = item.description[:650] if item.description_provenance or item.source.startswith('demo') else ""
            directory.append(record)
    with gzip.open(destination.parent/'titles.json.gz', 'wt', encoding='utf-8') as target:
        json.dump(directory, target, ensure_ascii=False)
    summary={'profile' :'compact','policy':'deterministic source-backed subset; demo first, then source-plotted identification reference titles, described supplemental titles, known movie runtimes/source plots and described books/subject mappings; stable SHA-256 tie breaking',
             'counts':{k:len(v) for k,v in result.items()},'source_counts':{k:len(v) for k,v in catalogs.items()}}
    (destination.parent/'manifest.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':prepare()
