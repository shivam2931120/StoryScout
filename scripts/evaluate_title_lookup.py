"""Execute HTTP title-identity regressions separately from relevance benchmarks."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', default=str(ROOT/'artifacts/title_lookup_results.json'))
    args = parser.parse_args()
    benchmark = json.loads((ROOT/'data/title_lookup_evaluation.json').read_text())
    rows = []
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        for case in benchmark['queries']:
            for constrained in [False, True]:
                # Reproduce the screenshot: an earlier topic, dark mood, English.
                # The old selection must not hide an explicitly named book either.
                state = {'media_selection': 'movies', 'last_content_query': 'erotica',
                         'preferences': {'desired_mood': 'dark', 'language': 'english', 'max_runtime': 90}} if constrained else {}
                start = time.perf_counter()
                response = client.post('/api/chat', json={'message': case['query'], 'state': state})
                response.raise_for_status()
                body = response.json()
                ids = [rec['item']['id'] for rec in body['title_matches']]
                expected = case['expected_ids']
                # Selection disambiguates mixed book/movie names, without changing identity.
                if constrained and case['query'] == 'The Time Machine':
                    expected = ['movie_ml_3959', 'movie_ml_5171']
                prefs_retained = not constrained or all(body['state']['preferences'][k] == v for k, v in state['preferences'].items())
                suggestion_labeled = not case.get('approximate') or 'Did you mean' in body['reply']
                passed = set(ids) == set(expected) and not body['results'] and prefs_retained and suggestion_labeled and body['trace']['intent'] == 'title_lookup'
                rows.append({'query':case['query'], 'constrained':constrained, 'expected_ids':expected, 'actual_ids':ids,
                             'passed':passed, 'preferences_retained':prefs_retained, 'latency_ms':round((time.perf_counter()-start)*1000,2)})
    output = {'executed_at':datetime.now(timezone.utc).isoformat(), 'base_url':args.base_url,
              'judgment_method':benchmark['judgment_method'], 'limitations':benchmark['limitations'],
              'cases':len(rows), 'passed':sum(row['passed'] for row in rows), 'rows':rows}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k != 'rows'}))
    for row in rows:
        if not row['passed']:
            print(json.dumps(row))
    if output['passed'] != output['cases']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
