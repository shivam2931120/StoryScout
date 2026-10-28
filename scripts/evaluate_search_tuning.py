"""Measure the reported preference bug and unseen follow-ups against the real API.

Source-genre judgments are mechanical metadata checks, not human relevance labels.
The saved v1 baseline was executed before the ranking/data changes.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir',default='artifacts/search_tuning')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    target=root/args.output_dir
    target.mkdir(parents=True,exist_ok=True)
    baseline=json.loads((root/'artifacts/search_tuning/preference_v1_baseline.json').read_text())
    rows=[]
    with httpx.Client(base_url=args.base_url,timeout=120) as client:
        meta=client.get('/api/meta').json()
        for genre in ('family','comedy','crime','mystery','science fiction'):
            response=client.post('/api/recommend',json={
                'message':'Recommend an uplifting family movie under two hours',
                'state':{'media_selection':'movies','preferences':{'preferred_genres':[genre],'max_runtime':120}},
                'per_domain':5})
            response.raise_for_status()
            data=response.json()
            recs=data['results'].get('movie',[])
            ids=[rec['item']['id'] for rec in recs]
            matches=sum(genre in rec['item']['genres'] for rec in recs)
            compliance=all(rec['item']['runtime_minutes'] is not None and rec['item']['runtime_minutes']<=120 and genre in rec['item']['genres'] for rec in recs)
            more=client.post('/api/chat',json={'message':'Show different recommendations','state':data['state'],'per_domain':5})
            more.raise_for_status()
            more_recs=more.json()['results'].get('movie',[])
            more_ids=[r['item']['id'] for r in more_recs]
            rows.append({'genre':genre,'ids':ids,'titles':[r['item']['title'] for r in recs],
                         'genre_matches':matches,'precision_at_5_source_genre':matches/5,
                         'hard_constraint_compliance':compliance,'eligible_candidates':data['trace']['retrieval']['movie']['eligible_count'],
                         'next_ids':more_ids,'next_titles':[r['item']['title'] for r in more_recs],
                         'repeat_count':len(set(ids)&set(more_ids)),
                         'next_constraint_compliance':all(r['item']['runtime_minutes'] is not None and r['item']['runtime_minutes']<=120 and genre in r['item']['genres'] for r in more_recs)})
        probes=[]
        for message in ('Find movies about a prison escape under 120 minutes','Recommend movies about artificial intelligence','I feel sad; suggest a cheerful movie under two hours'):
            first=client.post('/api/chat',json={'message':message,'per_domain':5})
            first.raise_for_status()
            data=first.json()
            follow=client.post('/api/chat',json={'message':'Make it shorter','state':data['state'],'per_domain':5})
            follow.raise_for_status()
            after=follow.json()
            probes.append({'query':message,'first_query':data['trace']['content_query'],'followup_query':after['trace']['content_query'],
                           'topic_preserved':data['state']['last_content_query']==after['state']['last_content_query'],
                           'mood':data['state']['preferences']['desired_mood'],
                           'titles':[r['item']['title'] for r in data['results'].get('movie',[])],
                           'shorter_max_runtime':after['state']['preferences']['max_runtime']})
    result={'executed_at_utc':datetime.now(timezone.utc).isoformat(),'method':'Executed HTTP preference edits; source genre/runtime checks; not independent human relevance evaluation.',
            'catalog':meta['counts'],'coverage':meta.get('coverage'),'active_modes':meta['modes'],
            'baseline':{'mean_source_genre_precision_at_5':sum(x['genre_matches'] for x in baseline['rows'])/25,
                        'unique_titles_across_five_preferences':len({i for x in baseline['rows'] for i in x['ids']})},
            'current':{'mean_source_genre_precision_at_5':statistics.mean(x['precision_at_5_source_genre'] for x in rows),
                       'unique_titles_across_five_preferences':len({i for x in rows for i in x['ids']}),
                       'all_hard_constraints_pass':all(x['hard_constraint_compliance'] and x['next_constraint_compliance'] for x in rows),
                       'all_next_picks_nonempty_and_unseen':all(x['next_ids'] and x['repeat_count']==0 for x in rows)},
            'rows':rows,'followups':probes}
    (target/'preference_v2_results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    assert result['current']['all_hard_constraints_pass']
    assert result['current']['all_next_picks_nonempty_and_unseen']
    assert all(p['topic_preserved'] for p in probes)


if __name__=='__main__': main()
