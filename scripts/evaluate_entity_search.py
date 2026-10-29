"""Measure title recognition/routing separately from narrative relevance."""
import argparse,json,time,sys
from pathlib import Path
from datetime import datetime,timezone
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.title_matching import title_key


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output',default='artifacts/entity_search/local.json')
    args=parser.parse_args();benchmark=json.loads((ROOT/'data/entity_search_evaluation.json').read_text());rows=[]
    with httpx.Client(base_url=args.base_url,timeout=120) as client:
        for case in benchmark['queries']:
            for inherited in [False,True]:
                state={'media_selection':'movies','last_content_query':'space','preferences':{'desired_mood':'dark','language':'english','max_runtime':90}} if inherited else {}
                start=time.perf_counter();response=client.post('/api/chat',json={'message':case['query'],'state':state});response.raise_for_status();body=response.json()
                matches=body['title_matches'];kind=case['kind']
                if kind in {'exact','partial','suggestion'}:
                    passed=bool(matches) and not body['results'] and all((x.get('title_match_kind') or ('suggestion' if 'Possible title spelling' in x.get('explanation','') else 'exact'))==kind for x in matches) and any(title_key(case['title_contains']) in title_key(x['item']['title']) for x in matches)
                    if case.get('media'):passed=passed and all(x['item']['media_type']==case['media'] for x in matches)
                elif kind=='missing':passed=not matches and not body['results'] and 'not in the local title directory' in body['reply']
                elif kind=='missing_reference':passed=not matches and not body['results'] and 'could not identify the reference title' in body['reply']
                elif kind=='reference_suggestion':passed=not matches and not body['results'] and bool(body['choices']) and 'Did you mean' in body['reply']
                else:passed=not matches and body['trace']['intent']!='title_lookup'
                retained=not inherited or kind=='discovery' or all(body['state']['preferences'][k]==v for k,v in state['preferences'].items())
                rows.append({'query':case['query'],'expected_kind':kind,'inherited_context':inherited,'passed':bool(passed and retained),'retained_preferences':retained,'matched_ids':[x['item']['id'] for x in matches],'actual_kinds':[x.get('title_match_kind') or ('suggestion' if 'Possible title spelling' in x.get('explanation','') else 'exact') for x in matches],'latency_ms':round((time.perf_counter()-start)*1000,2),'reply':body['reply']})
    output={'executed_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base_url,'judgment_method':benchmark['judgment_method'],'limitations':benchmark['limitations'],'cases':len(rows),'passed':sum(x['passed'] for x in rows),'by_kind':{kind:{'cases':sum(r['expected_kind']==kind for r in rows),'passed':sum(r['expected_kind']==kind and r['passed'] for r in rows)} for kind in sorted({x['expected_kind'] for x in rows})},'rows':rows}
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='rows'}))
    for row in rows:
        if not row['passed']:print(json.dumps(row))
    if output['passed']!=output['cases']:raise SystemExit(1)

if __name__=='__main__':main()
