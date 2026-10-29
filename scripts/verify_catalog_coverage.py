"""Round-trip every supplemental source identity through the real HTTP API."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.title_matching import title_key


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output',default='artifacts/entity_search/coverage.json')
    args=parser.parse_args();records=json.loads((ROOT/'data/enriched/supplemental_catalog.json').read_text())['records'];rows=[]
    with httpx.Client(base_url=args.base_url,timeout=120) as client:
        for item in records:
            query=f"Find a {item['media_type']} called {item['title']}"+(f" ({item['year']})" if item['year'] else '')
            response=client.post('/api/chat',json={'message':query});response.raise_for_status();body=response.json()
            matched=any(title_key(x['item']['title'])==title_key(item['title']) and x['item']['media_type']==item['media_type'] and (item['year'] is None or x['item']['year']==item['year']) and x.get('title_match_kind')=='exact' for x in body['title_matches'])
            rows.append({'query':query,'passed':bool(matched and not body['results']),'source_id':item['id'],'matched_ids':[x['item']['id'] for x in body['title_matches']]})
    output={'executed_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base_url,'method':'Source-snapshot title/media/year identity round-trip; not independent relevance ratings. Equivalent deduplicated IDs are accepted.','cases':len(rows),'passed':sum(x['passed'] for x in rows),'rows':rows}
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='rows'}))
    for row in rows:
        if not row['passed']:print(json.dumps(row))
    if output['passed']!=output['cases']:raise SystemExit(1)

if __name__=='__main__':main()
