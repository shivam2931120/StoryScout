"""Reproducible, credential-free preparation of local plot text and metadata.

Original Wikipedia Plot column only; generated Summary columns are ignored.
Runtime/language are factual Wikidata statements (CC0), never NLP predictions.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import random
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_loader import load_active_catalogs
from src.preprocessing import normalize_text

CACHE = ROOT / 'artifacts/.cache/catalog_sources'
OUT = ROOT / 'data/enriched'
REVISION = 'a1feef074ae0580338cf2dd8e98a43ca98637fa6'
PLOT_URL = f'https://huggingface.co/datasets/vishnupriyavr/wiki-movie-plots-with-summaries/resolve/{REVISION}/wiki_movie_plots_deduped_with_summaries.csv'
LANGUAGES = {'en':'English','fr':'French','es':'Spanish','de':'German','hi':'Hindi','ja':'Japanese','it':'Italian','ko':'Korean','zh':'Chinese','ru':'Russian','pt':'Portuguese','sv':'Swedish','da':'Danish','ar':'Arabic','fa':'Persian','ta':'Tamil','te':'Telugu'}


def get(url, timeout=70):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'StoryScoutCollegeNLP/2.1 (local academic dataset preparation)', 'Accept':'application/json,text/csv;q=0.9,*/*;q=0.8'}), timeout=timeout)


def title_key(title):
    title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
    title = re.sub(r',\s*(The|A|An)$', lambda m: '', title, flags=re.I) if ',' in title else title
    return re.sub(r'^(the|a|an)\s+', '', normalize_text(title)).strip()


def prepare_plots():
    path = CACHE / 'wikipedia_movie_plots.csv'
    if not path.exists():
        print('Downloading the pinned Wikipedia plot corpus…', flush=True)
        with get(PLOT_URL, 120) as source, path.with_suffix('.part').open('wb') as target:
            while chunk := source.read(1024*1024): target.write(chunk)
        path.with_suffix('.part').replace(path)
    catalogs = load_active_catalogs()
    by_key = defaultdict(list)
    for item in catalogs['movie']:
        if item.year: by_key[(title_key(item.title), item.year)].append(item)
    matches = defaultdict(list)
    csv.field_size_limit(2_000_000)
    with path.open(encoding='utf-8-sig', newline='') as source:
        for row in csv.DictReader(source):
            try: year = int(row.get('Release Year', ''))
            except ValueError: continue
            key = (title_key(row.get('Title','')), year)
            plot = row.get('Plot','').strip()
            url = row.get('Wiki Page','').strip()
            if len(plot) < 100 or not url.startswith('https://en.wikipedia.org/wiki/'): continue
            if len(by_key.get(key, [])) == 1:
                matches[by_key[key][0].id].append((plot, url, row.get('Director','').strip()))
    fields = ['id','plot_text','opening_excerpt','director','source','source_url','license','corpus_revision']
    target = OUT / 'movie_plots.csv.gz'
    count = 0
    temporary=target.with_suffix('.tmp.gz')
    with gzip.open(temporary, 'wt', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fields); writer.writeheader()
        for item_id, values in sorted(matches.items()):
            # Multiple distinct source pages for one title/year are ambiguous.
            if len({x[1] for x in values}) != 1: continue
            plot, url, director = max(values, key=lambda x:len(x[0]))
            sentences = re.split(r'(?<=[.!?])\s+', plot)
            excerpt = ' '.join(sentences[:2])
            if len(excerpt) > 380: excerpt = excerpt[:377].rsplit(' ',1)[0] + '…'
            writer.writerow(dict(id=item_id, plot_text=plot[:18000], opening_excerpt=excerpt,
                director='' if director.lower() in {'unknown','n/a',''} else director,
                source='Wikipedia Movie Plots (Justin Robischon corpus)', source_url=url,
                license='CC BY-SA 4.0; see original Wikipedia page history', corpus_revision=REVISION))
            count += 1
    temporary.replace(target)
    print(f'Saved {count} exact, unambiguous title/year plot matches to {target}', flush=True)
    return {'matched':count,'source_url':PLOT_URL,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'generated_summary_columns_used':False}


def prepare_metadata(batch_size=150, max_batches=None):
    catalogs = load_active_catalogs()
    known = {item.id for item in catalogs['movie']}
    ids = {}
    with (ROOT/'data/source/movielens/links.csv').open(newline='') as source:
        for row in csv.DictReader(source):
            item_id = 'movie_ml_' + row['movieId']
            if item_id in known and row['imdbId'].strip(): ids['tt'+row['imdbId'].zfill(7)] = item_id
    ordered = sorted(ids)
    random.Random(42).shuffle(ordered)  # Reproducible coverage across years/genres for bounded preparation.
    batches = [ordered[i:i+batch_size] for i in range(0,len(ordered),batch_size)]
    if max_batches is not None: batches = batches[:max_batches]
    last_call=[0.0]

    def fetch(batch):
        key = hashlib.sha256('|'.join(batch).encode()).hexdigest()[:20]
        cached = CACHE / f'wikidata_{key}.json'
        if cached.exists(): return json.loads(cached.read_text())
        query = '''SELECT ?imdb ?film ?runtime ?unit ?langCode WHERE {
          VALUES ?imdb { %s }
          ?film wdt:P345 ?imdb .
          OPTIONAL { ?film p:P2047 ?statement . ?statement psv:P2047 ?duration; wikibase:rank ?rank .
            FILTER(?rank != wikibase:DeprecatedRank)
            ?duration wikibase:quantityAmount ?runtime; wikibase:quantityUnit ?unit . }
          OPTIONAL { ?film wdt:P364 ?language . ?language wdt:P218 ?langCode . }
        }''' % ' '.join(json.dumps(value) for value in batch)
        url = 'https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query':query,'format':'json'})
        for attempt in range(3):
            try:
                wait=max(0,62-(time.monotonic()-last_call[0]))
                if wait: time.sleep(wait)
                last_call[0]=time.monotonic()
                with get(url) as response: rows = json.load(response)['results']['bindings']
                cached.write_text(json.dumps(rows)); return rows
            except Exception as error:
                print(f'Wikidata batch retry {attempt+1}: {type(error).__name__} {str(error)[:120]}', flush=True)
                # The public endpoint may impose a one-request/minute outage rule.
                if getattr(error,'code',None)==429:
                    time.sleep(62)
                else: time.sleep(2*(attempt+1))
        return []

    runtimes, languages, urls = defaultdict(set), defaultdict(set), defaultdict(set)
    with ThreadPoolExecutor(max_workers=1) as pool:
        for number, rows in enumerate(pool.map(fetch,batches),1):
            for row in rows:
                item_id = ids[row['imdb']['value']]
                urls[item_id].add(row['film']['value'].replace('http://','https://'))
                if row.get('runtime') and row.get('unit'):
                    factor = {'Q7727':1, 'Q11574':1/60, 'Q25235':60}.get(row['unit']['value'].rsplit('/',1)[-1])
                    if factor:
                        value = float(row['runtime']['value'])*factor
                        if 1 <= value <= 1000 and abs(value-round(value)) < 1e-6: runtimes[item_id].add(round(value))
                code = row.get('langCode',{}).get('value')
                if code in LANGUAGES: languages[item_id].add(LANGUAGES[code])
            print(f'Wikidata {number}/{len(batches)} batches; {len(runtimes)} runtime candidates', flush=True)
    target = OUT/'movie_metadata.csv'
    fields=['id','runtime_minutes','language','source','source_url','license']
    count=0
    with target.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fields); writer.writeheader()
        for item_id in sorted(urls):
            if len(urls[item_id]) != 1: continue
            runtime = next(iter(runtimes[item_id])) if len(runtimes[item_id]) == 1 else ''
            language = '|'.join(sorted(languages[item_id]))
            if not runtime and not language: continue
            writer.writerow(dict(id=item_id,runtime_minutes=runtime,language=language,source='Wikidata',source_url=next(iter(urls[item_id])),license='CC0'))
            count+=1
    return {'records':count,'unique_runtime_records':sum(len(v)==1 for v in runtimes.values()),'batches_attempted':len(batches),'source':'Wikidata P345 exact external-ID join; P2047 duration quantity with explicit unit, P364 original language','ambiguous_values':'skipped'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plots-only',action='store_true')
    parser.add_argument('--metadata-only',action='store_true')
    parser.add_argument('--max-batches',type=int)
    parser.add_argument('--batch-size',type=int,default=150)
    args=parser.parse_args()
    CACHE.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    manifest_path=OUT/'nlp_sources_manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if not args.metadata_only: manifest['plots']=prepare_plots()
    if not args.plots_only: manifest['metadata']=prepare_metadata(batch_size=args.batch_size,max_batches=args.max_batches)
    existing=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    existing.update(manifest)
    manifest_path.write_text(json.dumps(existing,indent=2))
