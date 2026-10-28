"""Exercise the real HTTP server and save actual end-to-end verification output."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import httpx


def verify(base_url: str, startup_timeout: int = 300) -> dict:
    with httpx.Client(base_url=base_url, timeout=65) as client:
        deadline=time.monotonic()+startup_timeout
        while time.monotonic()<deadline:
            try:
                response=client.get('/api/health',timeout=3)
                response.raise_for_status()
                if response.json()['status']=='ready':break
            except (httpx.HTTPError,ValueError):
                pass  # A newly started container may not have bound its port yet.
            time.sleep(1)
        else:
            raise RuntimeError(f'The application did not become ready within {startup_timeout} seconds.')
        meta = client.get('/api/meta')
        meta.raise_for_status()
        checks = []

        def chat(name, message, state=None, reference=None):
            start = time.perf_counter()
            payload = {'message': message, 'per_domain': 3}
            if state is not None: payload['state'] = state
            if reference: payload['reference_id'] = reference
            response = client.post('/api/chat', json=payload)
            response.raise_for_status()
            data = response.json()
            checks.append({'scenario': name, 'status': 'passed', 'latency_ms': round((time.perf_counter()-start)*1000, 1),
                           'returned_ids': {k: [x['item']['id'] for x in v] for k, v in data['results'].items()}})
            return data

        books = chat('Book recommendation', 'Suggest a mystery book under 300 pages')
        assert books['results']['book']
        assert all(x['item']['page_count'] and x['item']['page_count'] <= 300 for x in books['results']['book'])
        movies = chat('Movie recommendation', 'Recommend an uplifting movie under two hours')
        assert movies['results']['movie']
        assert all(x['item']['runtime_minutes'] and x['item']['runtime_minutes'] <= 120 for x in movies['results']['movie'])
        mixed = chat('Mixed recommendation', 'Find comforting books under 300 pages and movies under 110 minutes')
        assert mixed['results']['book'] and mixed['results']['movie']
        assert all(x['item']['page_count'] <= 300 for x in mixed['results']['book'])
        assert all(x['item']['runtime_minutes'] <= 110 for x in mixed['results']['movie'])
        cross = chat('Movie to books', 'Recommend books with similar themes', reference='movie_001')
        assert cross['results']['book'] and cross['state']['selected_reference_id'] == 'movie_001'
        other = chat('Book to movies', 'Recommend movies with similar themes', reference='book_001')
        assert other['results']['movie'] and other['state']['selected_reference_id'] == 'book_001'
        followup = chat('Follow-up and reference inheritance', 'Also show movies under 120 minutes. No horror.', cross['state'])
        assert followup['state']['selected_reference_id'] == 'movie_001'
        assert all(x['item']['runtime_minutes'] <= 120 and 'horror' not in x['item']['genres'] and x['item']['id'] != 'movie_001' for x in followup['results']['movie'])
        reset = chat('Reset preferences and reference', 'Reset my preferences', followup['state'])
        assert reset['state']['selected_reference_id'] is None
        assert reset['state']['preferences']['max_runtime'] is None
        assert reset['state']['preferences']['excluded_genres'] == []
        assert client.get('/').status_code == 200
        assert client.get('/api/ready').status_code == 200
        return {'executed_at_utc': datetime.now(timezone.utc).isoformat(), 'base_url': base_url,
                'catalog_counts': meta.json()['counts'], 'active_modes': meta.json()['modes'], 'checks': checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', default='artifacts/api_verification.json')
    parser.add_argument('--startup-timeout',type=int,default=300)
    args = parser.parse_args()
    result = verify(args.base_url,args.startup_timeout)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    print(f"Passed {len(result['checks'])} HTTP conversation scenarios; saved {target}")
