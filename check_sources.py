"""Lightweight source availability monitor; does NOT scrape or import betting picks."""
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

SOURCES = [
    ('Zawód Typer — Typy Dnia', 'https://zawodtyper.pl/typy-dnia/'),
    ('Zawód Typer — Kupony graczy', 'https://zawodtyper.pl/kupony-graczy/'),
    ('ESPN — NBA', 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'),
    ('NHL — terminarz', 'https://api-web.nhle.com/v1/schedule/now'),
]

def check(name, url):
    req = urllib.request.Request(url, headers={'User-Agent': 'BUKAI/7.3 (source availability check)', 'Accept': 'text/html,application/json'})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            r.read(512)
            code = r.status
            return {'name': name, 'url': url, 'status': 'dostępne' if code == 200 else f'HTTP {code}', 'http_code': code}
    except urllib.error.HTTPError as e:
        return {'name': name, 'url': url, 'status': f'HTTP {e.code}', 'http_code': e.code}
    except Exception as e:
        return {'name': name, 'url': url, 'status': 'błąd połączenia', 'detail': str(e)[:160]}

if __name__ == '__main__':
    out = {'checked_at': datetime.now(timezone.utc).isoformat(), 'note': 'Test dostępności stron, nie pobieranie typów ani kursów', 'sources': [check(*x) for x in SOURCES]}
    Path('data').mkdir(exist_ok=True)
    Path('data/sources.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Source checks:', [(x['name'], x['status']) for x in out['sources']])
