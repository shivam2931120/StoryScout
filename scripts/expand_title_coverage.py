"""Credential-free, bounded coverage import; source facts never come from an LLM.

Open Library work identity/author/first publication metadata and short attributed
work-description excerpts; Wikidata CC0 film statements via the public QLever
mirror. Snapshots are committed so serving remains offline. Missing stays unknown.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib,json,re,sys,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.schemas import CatalogItem
from src.title_matching import title_key
from src.preferences import GENRES
CACHE=ROOT/'artifacts/.cache/coverage_sources'


def fetch(client,url,params=None):
    CACHE.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256((url+json.dumps(params,sort_keys=True)).encode()).hexdigest()
    path=CACHE/(key+'.json')
    if path.exists():return json.loads(path.read_text())
    time.sleep(1.1)
    response=client.get(url,params=params)
    if response.status_code==429:
        time.sleep(min(60,max(10,int(response.headers.get('Retry-After','30')))))
        response=client.get(url,params=params)
    response.raise_for_status();body=response.json()
    path.write_text(json.dumps(body));return body


def excerpt(text):
    text=re.sub(r'\s+',' ',text).strip()
    words=text.split()
    if len(words)>50:text=' '.join(words[:50])+'…'
    return text


def books(client,requested,failures):
    records=[]
    for title,author in requested:
        try:
            payload=fetch(client,'https://openlibrary.org/search.json',{'title':title,'author':author,'limit':5,'fields':'key,title,author_name,first_publish_year'})
            choices=[x for x in payload.get('docs',[]) if title_key(x['title'])==title_key(title)]
            if not choices:raise ValueError('No exact source title/author search match')
            found=choices[0];work=fetch(client,'https://openlibrary.org'+found['key']+'.json')
            description=work.get('description','');description=description.get('value','') if isinstance(description,dict) else description
            description=excerpt(description) if isinstance(description,str) else ''
            url='https://openlibrary.org'+found['key'];aliases=[x for x in work.get('alternative_titles',[]) if isinstance(x,str)][:10]
            if title=='Nineteen Eighty-Four':aliases+=['1984']
            if title=="Harry Potter and the Philosopher's Stone":aliases+=["Harry Potter and the Sorcerer's Stone"]
            record=CatalogItem(id='book_ol_'+found['key'].rsplit('/',1)[-1],media_type='book',title=found['title'],description=description or 'Source catalog metadata only; narrative synopsis unavailable.',authors=', '.join(found.get('author_name',[])) or None,year=None,source='openlibrary-catalog',source_url=url,title_aliases=aliases)
            record.metadata_provenance={field:{'source':'Open Library work/search API','url':url} for field in ['title','authors']}
            record.metadata_provenance['year']={'source':'Open Library edition-aggregated first_publish_year is unverified; field left unknown','url':url,'reported_value':str(found.get('first_publish_year',''))}
            if description:
                record.description_source='Open Library contributor work description (short excerpt; rights may vary)'
                record.description_source_url=url;record.description_provenance='Attributed source work-description excerpt; at most 50 words; not independently verified'
            records.append(asdict(record));print('book:',title,flush=True)
        except (httpx.HTTPError,ValueError,KeyError) as error:failures.append({'title':title,'domain':'book','error':str(error)[:160]})
    return records


def movies(client,requested,failures):
    records=[]
    for begin in range(0,len(requested),6):
        names=requested[begin:begin+6]
        values=' '.join(json.dumps(x)+'@en' for x in names)
        query='''PREFIX wd: <http://www.wikidata.org/entity/> PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX schema: <http://schema.org/>
PREFIX p: <http://www.wikidata.org/prop/> PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/> PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?item ?title ?date WHERE {
VALUES ?title { '''+values+''' }
?item rdfs:label ?title; wdt:P577 ?date; wdt:P31/rdfs:label ?type . FILTER(LANG(?type)="en" && REGEX(STR(?type),"film","i")) FILTER(?date >= "2019-01-01T00:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime>)
} LIMIT 3000'''
        try:
            rows=fetch(client,'https://qlever.dev/api/wikidata',{'query':query,'format':'json'})['results']['bindings']
            grouped={}
            for row in rows:grouped.setdefault(row['item']['value'],[]).append(row)
            for url,group in grouped.items():
                vals=lambda name:sorted({row[name]['value'] for row in group if name in row})
                title=vals('title')[0];years=[int(x[:4]) for x in vals('date')]
                runtime=vals('runtime');languages=vals('language');genres=[]
                for label in vals('genre'):
                    for genre in GENRES:
                        if re.search(r'\b'+re.escape(genre)+r'\b',label.lower()) and genre not in genres:genres.append(genre)
                record=CatalogItem(id='movie_wd_'+url.rsplit('/',1)[-1],media_type='movie',title=title,description='Source catalog metadata only; narrative synopsis unavailable.',year=min(years),source='wikidata-catalog',source_url=url.replace('http:','https:'),director=', '.join(vals('director')) or None,language=languages[0] if len(languages)==1 else 'Unknown',runtime_minutes=int(float(runtime[0])) if len(runtime)==1 and float(runtime[0]).is_integer() else None,genres=genres)
                record.metadata_provenance={name:{'source':'Wikidata CC0 statements via QLever; release year is earliest supplied release; ambiguous runtimes/languages left unknown','url':record.source_url} for name in ['year']}
                records.append(asdict(record));print('movie:',title,flush=True)
            matched={r['title'] for r in records}
            for name in names:
                if name not in matched:failures.append({'title':name,'domain':'movie','error':'No matching post-2018 film source record'})
        except (httpx.HTTPError,ValueError,KeyError) as error:
            failures.extend({'title':name,'domain':'movie','error':str(error)[:160]} for name in names)
    return records


def main():
    seed=json.loads((ROOT/'data/catalog/coverage_requests.json').read_text());failures=[]
    with httpx.Client(timeout=75,follow_redirects=True,headers={'User-Agent':'StoryScout/2.0 educational NLP catalog importer','Accept':'application/json'}) as client:
        records=books(client,seed['books'],failures)+movies(client,seed['movies'],failures)
    editorial=json.loads((ROOT/'data/catalog/editorial_descriptions.json').read_text())
    for title,entry in editorial['movies'].items():
        if title in seed['movies'] and not any(r['media_type']=='movie' and r['title']==title for r in records):
            if not entry.get('year'):continue
            records.append(asdict(CatalogItem(id='movie_pub_'+hashlib.sha256(entry['source_url'].encode()).hexdigest()[:12],media_type='movie',title=title,description='',year=entry['year'],source='publisher-catalog',source_url=entry['source_url'],metadata_provenance={'year':{'source':entry['source'],'url':entry['source_url']}})))
    for record in records:
        entry=editorial['movies'].get(record['title']) if record['media_type']=='movie' else None
        if entry:
            record.update(description=entry['description'],description_source=entry['source'],description_source_url=entry['source_url'],description_provenance='Original short developer paraphrase of linked distributor synopsis; no ending details')
            for field in ['runtime_minutes','genres']:
                if field in entry:
                    record[field]=entry[field]
                    record['metadata_provenance'][field]={'source':entry['source'],'url':entry['source_url']}
    destination=ROOT/'data/enriched/supplemental_catalog.json'
    # Import once, serve from the checked-in snapshot without external calls.
    destination.write_text(json.dumps({'records':records,'provenance':'Source API snapshot; no generated facts'},ensure_ascii=False,indent=2)+'\n')
    report={'acquired_at':datetime.now(timezone.utc).isoformat(),'counts':{d:sum(x['media_type']==d for x in records) for d in ['book','movie']},'failures':[f for f in failures if not any(r['title']==f['title'] and r['media_type']==f['domain'] for r in records)],'source_import_failures':failures,'sources':['https://openlibrary.org/dev/docs/api/search','https://openlibrary.org/developers/api','https://qlever.dev/wikidata','https://www.wikidata.org/wiki/Wikidata:Licensing'],'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}
    (ROOT/'data/enriched/supplemental_manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)

if __name__=='__main__':main()
