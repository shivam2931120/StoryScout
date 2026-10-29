"""HTTP passage/provenance checks; behavioral regressions, not accuracy claims."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx


def verify(base_url):
    checks=[]
    with httpx.Client(base_url=base_url,timeout=120) as client:
        def record(name,condition):
            assert condition,name
            checks.append({'scenario':name,'passed':True})
        meta=client.get('/api/meta');meta.raise_for_status();meta=meta.json()
        record('Both domains have local semantic passages',all(meta['passages'][d]['count']>0 and 'semantic' in meta['passages'][d]['mode'] for d in ['book','movie']))
        record('Current compact narratives have complete window coverage',all(meta['passages'][d]['partial_records']==0 for d in ['book','movie']))
        response=client.post('/api/chat',json={'message':'two pen pals secretly agree to run away together on a New England island','state':{'media_selection':'movies'}})
        response.raise_for_status();body=response.json();rows=body['results']['movie']
        record('Source-checked focal detail retrieves Moonrise Kingdom first',bool(rows) and rows[0]['item']['id']=='movie_ml_94959')
        evidence=rows[0]['passage_match']
        record('Winning passage has ordinal and source provenance',bool(evidence) and 0<evidence['passage_number']<=evidence['passage_count'] and bool(evidence['source_url']))
        record('Passage evidence does not expose raw plot text',not any(key in evidence for key in ['text','quote','passage_text','body']))
        record('Many passages aggregate to unique catalog cards',len({x['item']['id'] for x in rows})==len(rows))
        evaluated=client.get('/api/evaluation');evaluated.raise_for_status();measured=evaluated.json()['passage_evaluation']
        record('Executed ablation available without full query payload',measured['focal_query_count']==10 and 'queries' not in measured and 'passages' in measured['results'])
    return {'executed_at':datetime.now(timezone.utc).isoformat(),'base_url':base_url,'method':'Developer-authored HTTP behavioral checks, not independent relevance ratings','checks':checks,'passed':len(checks),'passages':meta['passages']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output',default='output/passages/http-verification.json')
    args=parser.parse_args();result=verify(args.base_url)
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(f"Passed {result['passed']} passage/provenance checks; saved {target}")
