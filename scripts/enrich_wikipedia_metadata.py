"""Cache factual film-infobox runtime/language, joined by exact source page.

No language or runtime is predicted. Ambiguous runtime variants are skipped.
Only section zero is fetched; requests are bounded and resumable.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.prepare_nlp_catalog import LANGUAGES


def extract_fields(text):
    def field(name):
        hit=re.search(r'^\s*\|\s*'+name+r'\s*=(.*?)(?=^\s*\||^\s*}})',text,re.M|re.S|re.I)
        if not hit:return ''
        return re.sub(r'<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>|<!--.*?-->','',hit.group(1),flags=re.S)
    runtimes={int(x) for x in re.findall(r'\b(\d+)\s*(?:minutes?|mins?)\b',field('runtime'),re.I)}
    runtime=next(iter(runtimes)) if len(runtimes)==1 and 1<=next(iter(runtimes))<=1000 else None
    language=field('language')
    names=sorted(set(name for name in LANGUAGES.values() if re.search(r'\b'+re.escape(name)+r'\b',language,re.I)))
    return runtime,'|'.join(names)


def run(limit=1200):
    target=ROOT/'data/enriched/movie_metadata.csv'
    existing={}
    if target.exists():
        with target.open(newline='') as source:existing={r['id']:r for r in csv.DictReader(source)}
    with gzip.open(ROOT/'data/enriched/movie_plots.csv.gz','rt',encoding='utf-8',newline='') as source:
        records=[r for r in csv.DictReader(source) if r['id'] not in existing]
    random.Random(42).shuffle(records)
    records=records[:limit]
    titles={r['id']:urllib.parse.unquote(r['source_url'].split('/wiki/',1)[1]).replace('_',' ') for r in records}
    lookup={title:item_id for item_id,title in titles.items()}
    batches=[list(lookup)[i:i+30] for i in range(0,len(lookup),30)]
    cache=ROOT/'artifacts/.cache/wiki_infobox';cache.mkdir(parents=True,exist_ok=True)

    def fetch(batch):
        key=hashlib.sha256('|'.join(batch).encode()).hexdigest()[:20]
        path=cache/f'{key}.json'
        if path.exists():return json.loads(path.read_text())
        params={'action':'query','prop':'revisions','rvprop':'ids|content','rvslots':'main','rvsection':'0','titles':'|'.join(batch),'redirects':1,'format':'json','formatversion':2}
        url='https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode(params)
        for attempt in range(3):
            try:
                request=urllib.request.Request(url,headers={'User-Agent':'StoryScoutCollegeNLP/2.1 (bounded academic infobox preparation)'})
                with urllib.request.urlopen(request,timeout=45) as response:data=json.load(response)
                if 'query' not in data:raise ValueError(str(data.get('error','Missing API response'))[:150])
                path.write_text(json.dumps(data));return data
            except Exception as error:
                print(f'Infobox retry: {str(error)[:140]}',flush=True)
                time.sleep(3*(attempt+1))
        return {}

    added=0
    def save():
        fields=['id','runtime_minutes','language','source','source_url','license']
        temp=target.with_suffix('.tmp')
        with temp.open('w',encoding='utf-8',newline='') as handle:
            writer=csv.DictWriter(handle,fields);writer.writeheader();writer.writerows(existing[k] for k in sorted(existing))
        temp.replace(target)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for number,data in enumerate(pool.map(fetch,batches),1):
            query=data.get('query',{})
            redirects={x['from']:x['to'] for x in query.get('redirects',[])}
            pages={x['title']:x for x in query.get('pages',[])}
            for title in batches[number-1]:
                canonical=redirects.get(title,title)
                page=pages.get(canonical,{})
                revisions=page.get('revisions',[])
                if not revisions:continue
                revision=revisions[0]
                text=revision.get('slots',{}).get('main',{}).get('content','')
                runtime,language=extract_fields(text)
                if not runtime and not language:continue
                item_id=lookup[title]
                existing[item_id]={'id':item_id,'runtime_minutes':runtime or '', 'language':language,
                    'source':'Wikipedia film infobox (exact source page)', 'source_url':'https://en.wikipedia.org/w/index.php?oldid='+str(revision['revid']), 'license':'CC BY-SA 4.0; factual metadata extracted from a pinned page revision'}
                added+=1
            save()
            print(f'Infobox batch {number}/{len(batches)}: {added} new metadata records; {len(existing)} total',flush=True)
    manifest=ROOT/'data/enriched/nlp_sources_manifest.json'
    info=json.loads(manifest.read_text()) if manifest.exists() else {}
    info['wikipedia_infobox']={'added':added,'total_metadata_records':len(existing),'sample_seed':42,'requested_source_pages':len(records),'runtime_policy':'Accept a single explicit minutes value; ambiguous variants remain unknown','request_cache':'artifacts/.cache/wiki_infobox'}
    manifest.write_text(json.dumps(info,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--limit',type=int,default=1200)
    run(parser.parse_args().limit)
