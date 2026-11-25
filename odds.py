import os, re, unicodedata, datetime as dt
from urllib.parse import urlencode
KEYS={'eng.1':'soccer_epl','esp.1':'soccer_spain_la_liga','ger.1':'soccer_germany_bundesliga','ita.1':'soccer_italy_serie_a','fra.1':'soccer_france_ligue_one','uefa.champions':'soccer_uefa_champs_league','uefa.europa':'soccer_uefa_europa_league','pol.1':'soccer_poland_ekstraklasa','ned.1':'soccer_netherlands_eredivisie','por.1':'soccer_portugal_primeira_liga','eng.2':'soccer_efl_champ','nba':'basketball_nba','nhl':'icehockey_nhl','wnba':'basketball_wnba','mens-college-basketball':'basketball_ncaab','usa.1':'soccer_usa_mls','bra.1':'soccer_brazil_campeonato'}
ALIASES=[('internazionale','inter milan','inter'),('bayern munich','bayern münchen'),('paris saint germain','psg'),('sporting cp','sporting lisbon'),('atletico madrid','atlético de madrid'),('club brugge','club brugge kv'),('slavia prague','slavia praha'),('manchester united','man united'),('manchester city','man city'),('as roma','roma'),('vfb stuttgart','stuttgart'),('shakhtar donetsk','shakhtar'),('lille','losc lille'),('viking fk','viking'),('sabah fk','sabah'),('fc barcelona','barcelona')]
def rawnorm(s):
 s=unicodedata.normalize('NFKD',s.lower()); return re.sub(r'[^a-z0-9]','', ''.join(c for c in s if not unicodedata.combining(c)))
ALIAS={rawnorm(v):rawnorm(group[0]) for group in ALIASES for v in group}
def norm(s):
 n=rawnorm(s);return ALIAS.get(n,n)
def attach(events,get,parse_date,diagnostics,now):
 key=os.getenv('ODDS_API_KEY'); data={}
 if not key:
  diagnostics.append(dict(source='The Odds API',status='error',detail='Brak ODDS_API_KEY'));return data
 # One region, two markets; maximum 10 leagues per run.
 leagues=sorted({e['league'] for e in events if e['league'] in KEYS},key=lambda l:(0 if l in ('uefa.champions','uefa.europa') else 1 if l in ('nba','nhl','eng.1','esp.1','ger.1','ita.1','fra.1') else 2,min(e['time'] for e in events if e['league']==l)))[:7]
 for league in leagues:
  try:
   rows=get('https://api.the-odds-api.com/v4/sports/'+KEYS[league]+'/odds/?'+urlencode(dict(apiKey=key,regions='eu',markets='h2h,totals',oddsFormat='decimal')))
   diagnostics.append(dict(source='The Odds API '+league,status='ok',events=len(rows)))
  except Exception:
   diagnostics.append(dict(source='The Odds API '+league,status='error',detail='Zapytanie nieudane; sprawdź limit i dostępność ligi'));continue
  matched=0
  for e in (x for x in events if x['league']==league):
   h,a=e['event'].split(' — ',1); t=parse_date(e['time']); matches=[r for r in rows if norm(r['home_team'])==norm(h) and norm(r['away_team'])==norm(a) and parse_date(r['commence_time']) and abs((parse_date(r['commence_time'])-t).total_seconds())<=1800]
   if len(matches)!=1:continue
   matched+=1
   quotes={}
   for b in matches[0].get('bookmakers',[]):
    for m in b.get('markets',[]):
     stamp=m.get('last_update') or b.get('last_update'); ts=parse_date(stamp)
     if not ts or not 0<=(now-ts).total_seconds()<=21600:continue
     for o in m.get('outcomes',[]):
      price=o.get('price',0); name=o.get('name'); point=o.get('point')
      if not isinstance(price,(int,float)) or not 1<price<100:continue
      if m['key']=='h2h': label='Zwycięstwo gospodarzy' if name==matches[0]['home_team'] else 'Zwycięstwo gości' if name==matches[0]['away_team'] else None
      elif m['key']=='totals' and isinstance(point,(int,float)) and point%1==.5 and name in ('Over','Under'):
       unit='Gole' if e['sport']=='Piłka nożna' else 'Bramki' if e['sport']=='NHL' else 'Punkty';label=f'{unit} {"powyżej" if name=="Over" else "poniżej"} {point}'
      else:continue
      if label:quotes.setdefault(label,[]).append((price,b.get('title',''),stamp))
   # Use a real quoted price nearest the median, not a synthetic average.
   data[e['id']]={label:sorted(q)[(len(q)-1)//2] for label,q in quotes.items()}
  diagnostics.append(dict(source="Dopasowanie "+league,status="ok",events=matched,detail=f"Dopasowano {matched} wydarzeń"))
 return data
