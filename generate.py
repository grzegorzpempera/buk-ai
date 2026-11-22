#!/usr/bin/env python3
"""Free public ESPN fixtures -> illustrative probability-model coupons; no bookmaker odds."""
import json, urllib.request, datetime, math, itertools, pathlib, random
ROOT=pathlib.Path(__file__).parent
SPORTS=[('Piłka nożna','soccer','eng.1'),('Piłka nożna','soccer','esp.1'),('Piłka nożna','soccer','ger.1'),('Piłka nożna','soccer','ita.1'),('Piłka nożna','soccer','fra.1'),('Piłka nożna','soccer','uefa.champions'),('Koszykówka','basketball','nba'),('NHL','hockey','nhl')]
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'BUK-AI/6.0 (public sports fixture demo)','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
def record(competitor):
 for r in competitor.get('records',[]):
  s=r.get('summary','')
  try:
   nums=[int(v) for v in s.split('-')]
   if len(nums)>=2 and sum(nums[:2])>0:return (nums[0]+1)/(sum(nums[:2])+2)
  except (ValueError,TypeError):pass
 return None
def build():
 now=datetime.datetime.now(datetime.timezone.utc); picks=[]; errors=[]
 for name,sport,league in SPORTS:
  try:
   url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={(now+datetime.timedelta(days=1)).strftime("%Y%m%d")}-{(now+datetime.timedelta(days=4)).strftime("%Y%m%d")}&limit=100'
   payload=get(url)
   for event in payload.get('events',[]):
    if event.get('status',{}).get('type',{}).get('completed'):continue
    try: dt=datetime.datetime.fromisoformat(event['date'].replace('Z','+00:00'))
    except (KeyError,ValueError):continue
    if dt<=now or dt>now+datetime.timedelta(days=5):continue
    comp=(event.get('competitions') or [{}])[0]
    teams=comp.get('competitors',[])
    if len(teams)!=2:continue
    home=next((x for x in teams if x.get('homeAway')=='home'),None)
    away=next((x for x in teams if x.get('homeAway')=='away'),None)
    if not home or not away:continue
    h=home.get('team',{}).get('displayName','Gospodarze'); a=away.get('team',{}).get('displayName','Goście')
    hr,ar=record(home),record(away)
    if hr is None or ar is None:continue # No unsupported guesses
    # illustrative win chance proxy, NOT calibrated probability
    p=max(.34,min(.72,.5+(hr-ar)*.45+.045))
    if sport=='soccer':
     # draw-aware approximation; estimate home-or-draw rather than pure 1X2
     p=min(.85,p+.18); market='1X (gospodarze lub remis)'
    else:market='Zwycięstwo gospodarzy (z dogrywką)'
    # odds are reciprocal of proxy probability plus an illustrative margin, NOT observed prices
    estimated=round(1/p*1.07,2)
    picks.append({'id':str(event.get('id',f'{league}-{dt.isoformat()}'))+'-'+league,'sport':name,'league':league,'event':f'{h} — {a}','time':dt.isoformat(),'market':market,'p_proxy':round(p,3),'estimated_odds':estimated,'source':'ESPN — terminarz i bilans zespołów','source_url':url,'note':'Wskaźnik heurystyczny oparty na bilansie drużyn; nie jest skalibrowaną prognozą ani kursem bukmachera.'})
  except Exception as exc:errors.append(f'{league}: {type(exc).__name__}')
 picks.sort(key=lambda x:(x['time'],x['event']))
 coupons=[]; used=set()
 for level in range(3):
  options=[]
  for n in (3,4,5,6):
   if len(picks)<n:continue
   # deterministic bounded combinations; prioritize diversity and no duplicate matches
   candidates=picks[:32]
   for combo in itertools.islice(itertools.combinations(candidates,n),0,15000):
    if len({x['id'] for x in combo})!=n:continue
    odds=math.prod(x['estimated_odds'] for x in combo)
    if odds<5:continue
    if level==0 and odds>9:continue
    if level==1 and not (7<=odds<=16):continue
    if level==2 and odds<12:continue
    p=math.prod(x['p_proxy'] for x in combo)
    overlap=len({x['id'] for x in combo}&used)
    # encourage multiple leagues; these are not independent probability estimates
    score=overlap*20+abs(odds-[6,10,18][level])+max(0,2-len({x['league'] for x in combo}))*5
    options.append((score,combo,odds,p))
   if options:break
  if options:
   _,combo,odds,p=min(options,key=lambda x:x[0]);used.update(x['id'] for x in combo)
   coupons.append({'name':['Ostrożniejszy','Zrównoważony','Wysoki kurs'][level],'picks':list(combo),'estimated_total_odds':round(odds,2),'proxy_joint':round(p,4),'warning':'Kurs orientacyjny wyliczony z heurystyki, nie z oferty bukmachera. Iloczyn wskaźników nie jest wiarygodną oceną prawdopodobieństwa kuponu.'})
 return {'generated_at':now.isoformat(),'status':'ok' if picks else 'no_data','fixtures':len(picks),'coupons':coupons,'errors':errors,'disclaimer':'Automatyczna demonstracja wyłącznie na podstawie publicznych terminarzy i bilansów ESPN. Nie są to zweryfikowane typy z serwisów typerskich ani kursy Superbet. Brak kalibracji modelu i rynkowych kursów; nie traktuj procentów jako prawdopodobieństwa trafienia.'}
if __name__=='__main__':
 output=build();(ROOT/'data').mkdir(exist_ok=True);(ROOT/'data'/'daily.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');print('fixtures',output['fixtures'],'coupons',len(output['coupons']),'errors',output['errors'])
