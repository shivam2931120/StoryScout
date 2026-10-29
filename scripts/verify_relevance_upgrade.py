"""Executed HTTP checks for topic gates, partial results and context controls.

These are developer-authored behavioral checks, not human relevance ratings.
"""
import argparse
from datetime import datetime, timezone
import csv
import gzip
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]


def verify(base_url):
    checks=[]
    with httpx.Client(base_url=base_url,timeout=90) as client:
        def chat(message,state=None,action='auto',**extra):
            response=client.post('/api/chat',json={'message':message,'state':state or {},'search_action':action,**extra})
            response.raise_for_status()
            return response.json()
        def record(name,condition):
            assert condition,name
            checks.append({'scenario':name,'passed':True})
        meta=client.get('/api/meta').json()
        first=chat('Movies about spacecraft oxygen repair',{'media_selection':'movies','preferences':{'desired_mood':'dark'}})
        rows=first['results']['movie']
        record('Topic matching precedes mood bonuses',bool(rows) and all(x['score_components']['topic_lexical_similarity']>=.035 or (x['score_components']['topic_semantic_similarity'] or 0)>=.32 for x in rows))
        record('Mood prototype excluded from topic query','disturbing' not in first['trace']['retrieval']['movie']['topic_query'])
        refined=chat('Under 110 minutes',first['state'])
        record('Follow-up retains topic and enforces runtime','spacecraft' in refined['state']['last_content_query'] and all(x['item']['runtime_minutes']<=110 for x in refined['results']['movie']))
        fresh=chat('Fantasy movies about magic',refined['state'],action='new')
        record('New search clears prior criteria and topic',fresh['state']['preferences']['desired_mood'] is None and fresh['state']['preferences']['max_runtime'] is None and 'spacecraft' not in fresh['state']['last_content_query'] and len(fresh['state']['messages'])==3)
        fewer=chat('Mystery books under 300 pages')
        record('Return fewer matches rather than fill slots',0<len(fewer['results']['book'])<3)
        weak=chat('Movies about xqzvpr blorfzzz',{'media_selection':'movies','preferences':{'desired_mood':'dark'}})
        record('No matches for an unsupported topic',not any(weak['results'].values()) and 'topic strongly enough' in weak['reply'])
        lookup=chat('Love & Other Drugs',refined['state'])
        record('Exact title lookup survives relevance changes',lookup['title_matches'][0]['item']['id']=='movie_ml_82167')
        record('Recovered film plot appears in title details',bool(lookup['title_matches'][0]['item']['description']))
        record('Explicit language adjective is a filter',chat('English science fiction movies')['state']['preferences']['language']=='english')
        record('Book synopsis coverage increased',meta['coverage']['book']['descriptions']>20)
        with gzip.open(ROOT/'data/enriched/book_summaries.csv.gz','rt',newline='') as stream:
            summaries=list(csv.DictReader(stream))
        item=next((client.get('/api/items/'+row['id']).json() for row in summaries if client.get('/api/items/'+row['id']).json().get('description_status')=='source_generated'),None)
        record('Source-generated summaries disclosed independently of factual metadata',item is not None and item['page_count'] is None and item['year'] is None)
    return {'executed_at':datetime.now(timezone.utc).isoformat(),'base_url':base_url,'method':'Developer-authored HTTP behavior checks; not independent human relevance evaluation','checks':checks,'passed':len(checks),'meta':{'counts':meta['counts'],'coverage':meta['coverage'],'modes':meta['modes']}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output',default='artifacts/compact/relevance_upgrade_verification.json')
    args=parser.parse_args()
    result=verify(args.base_url)
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(f"Passed {result['passed']} topic/context/source checks; saved {target}")
