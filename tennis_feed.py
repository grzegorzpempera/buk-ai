#!/usr/bin/env python3
"""BUK AI tennis fixtures: official Live Tennis API FREE /fixtures schema."""
import collections
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
KEY = os.environ.get('LIVE_TENNIS_API_KEY', '').strip()
URL = 'https://api.livetennisapi.com/api/public/v1/fixtures?limit=200'
now = dt.datetime.now(dt.timezone.utc)
report = {
    'source': 'Live Tennis API', 'status': 'not_configured',
    'generated_at': now.isoformat(), 'events': [],
    'detail': '', 'diagnostics': {'key_configured': bool(KEY), 'api_records': 0,
                                'rejected': {}, 'http_status': None}
}
rejected = collections.Counter()


def parse_time(raw):
    if not raw:
        return None
    try:
        value = dt.datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        if value.tzinfo is None:
            return None
        return value.astimezone(dt.timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


if not KEY:
    report['detail'] = 'Brak LIVE_TENNIS_API_KEY w środowisku kroku workflow.'
else:
    try:
        request = urllib.request.Request(URL, headers={
            'X-API-Key': KEY, 'Accept': 'application/json', 'User-Agent': 'BUK-AI/7.7'
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            report['diagnostics']['http_status'] = response.status
            payload = json.load(response)
        if not isinstance(payload, dict):
            raise ValueError('Odpowiedź API nie jest obiektem JSON')
        records = payload.get('data')
        if not isinstance(records, list):
            raise ValueError('Brak tablicy data w odpowiedzi API; pola: ' + ', '.join(sorted(payload.keys())[:12]))
        report['diagnostics']['api_records'] = len(records)
        report['diagnostics']['meta_count'] = (payload.get('meta') or {}).get('count') if isinstance(payload.get('meta'), dict) else None
        for fixture in records:
            if not isinstance(fixture, dict):
                rejected['nieprawidlowy_rekord'] += 1
                continue
            if str(fixture.get('status') or '').lower() in ('cancelled', 'finished', 'postponed', 'live'):
                rejected['nie_nadchodzacy_status'] += 1
                continue
            when = parse_time(fixture.get('start_time'))
            if when is None:
                rejected['brak_godziny_startu'] += 1
                continue
            if not (now < when <= now + dt.timedelta(days=7)):
                rejected['poza_zakresem_7_dni'] += 1
                continue
            p1 = str(fixture.get('player1_name') or '').strip()
            p2 = str(fixture.get('player2_name') or '').strip()
            if not p1 or not p2:
                rejected['brak_nazw_zawodnikow'] += 1
                continue
            report['events'].append({
                'id': 'tennis-live-' + str(fixture.get('id') or len(report['events'])),
                'sport': 'Tenis', 'league': str(fixture.get('tournament') or fixture.get('tour') or 'Tenis'),
                'event': p1 + ' — ' + p2, 'time': when.isoformat(),
                'home_rate': None, 'away_rate': None,
                'source': 'Live Tennis API', 'source_url': 'https://livetennisapi.com/',
                'note': 'Terminarz bez prognozy wyniku i kursu.'
            })
        report['events'].sort(key=lambda e: e['time'])
        report['status'] = 'ok' if report['events'] else 'empty'
        report['detail'] = f"API: {len(records)} rekordów; poprawne mecze: {len(report['events'])}."
    except urllib.error.HTTPError as exc:
        report['status'] = 'error'
        report['diagnostics']['http_status'] = exc.code
        report['detail'] = f'HTTP {exc.code}: problem z kluczem, limitem lub żądaniem (401/429).'
    except Exception as exc:
        report['status'] = 'error'
        report['detail'] = f'{type(exc).__name__}: {str(exc)[:150]}'
report['diagnostics']['rejected'] = dict(rejected)
(ROOT / 'data').mkdir(exist_ok=True)
(ROOT / 'data' / 'tennis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('Tennis:', report['status'], report['detail'])
print('Tennis diagnostics:', json.dumps(report['diagnostics'], ensure_ascii=False))
