#!/usr/bin/env python3
"""BUK AI: free fixtures with source diagnostics. No invented sportsbook prices."""
import datetime as dt, itertools, json, math, pathlib, urllib.request, urllib.error
from zoneinfo import ZoneInfo
WARSAW=ZoneInfo("Europe/Warsaw")
ROOT=pathlib.Path(__file__).resolve().parent
UTC=dt.timezone.utc
LEAGUES=[('Piłka nożna','soccer','eng.1'),('Piłka nożna','soccer','esp.1'),('Piłka nożna','soccer','ger.1'),('Piłka nożna','soccer','ita.1'),('Piłka nożna','soccer','fra.1'),('Piłka nożna','soccer','uefa.champions'),('Piłka nożna','soccer','pol.1'),('Piłka nożna','soccer','ned.1'),('Piłka nożna','soccer','por.1'),('Piłka nożna','soccer','usa.1'),('Piłka nożna','soccer','uefa.europa'),('Piłka nożna','soccer','eng.2'),('Piłka nożna','soccer','bra.1'),('Koszykówka','basketball','nba'),('Koszykówka','basketball','wnba'),('Koszykówka','basketball','mens-college-basketball'),('NHL','hockey','nhl')]

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; BUKAI/6.1; sports fixtures)', 'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=18) as response:return json.load(response)
    except urllib.error.HTTPError as e:raise RuntimeError('HTTP '+str(e.code)) from e
    except urllib.error.URLError as e:raise RuntimeError('Network: '+str(e.reason)[:100]) from e

def parse_date(s):
    try:return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(UTC)
    except (ValueError,AttributeError):return None

def win_rate(x):
    for r in x.get('records',[]):
        try:
            wins,losses=map(int,r['summary'].split('-')[:2]);
            if wins+losses:return (wins+1)/(wins+losses+2)
        except (ValueError,KeyError,TypeError):pass
    return None

def espn(now, sport, league, label, diagnostics):
    out=[]
    # ESPN's scoreboard dates parameter supports single-day YYYYMMDD more reliably than ranges.
    for day in range(0,5):
        date=(now.astimezone(WARSAW).date()+dt.timedelta(days=day)).strftime('%Y%m%d')
        url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={date}&limit=100'
        try:
            data=get(url);events=data.get('events',[])
            diagnostics.append({'source':f'ESPN {league} {date}','status':'ok','events':len(events)})
        except Exception as e:
            diagnostics.append({'source':f'ESPN {league} {date}','status':'error','detail':str(e)[:120]});continue
        for event in events:
            when=parse_date(event.get('date'))
            if not when or when<=now or when>now+dt.timedelta(days=6):continue
            competition=(event.get('competitions') or [{}])[0]
            teams=competition.get('competitors') or []
            home=next((x for x in teams if x.get('homeAway')=='home'),None)
            away=next((x for x in teams if x.get('homeAway')=='away'),None)
            if not home or not away:continue
            hr,ar=win_rate(home),win_rate(away)
            out.append({'id':f'{sport}-{league}-{event.get("id")}', 'sport':label,'league':league,'event':f'{home.get("team",{}).get("displayName","?")} — {away.get("team",{}).get("displayName","?")}', 'time':when.isoformat(), 'home_rate':hr,'away_rate':ar,'source':'ESPN','source_url':url})
    return out

def nhl(now, diagnostics):
    # Official NHL schedule API independent of ESPN; offers fixtures but not estimated odds.
    out=[]
    for day in (0,2,4):
        date=(now.astimezone(WARSAW).date()+dt.timedelta(days=day)).strftime('%Y-%m-%d')
        url=f'https://api-web.nhle.com/v1/schedule/{date}'
        try:
            data=get(url);weeks=data.get('gameWeek') or []
            games=[g for w in weeks for g in w.get('games',[])];diagnostics.append({'source':'NHL official '+date,'status':'ok','events':len(games)})
        except Exception as e:
            diagnostics.append({'source':'NHL official '+date,'status':'error','detail':str(e)[:120]});continue
        for g in games:
            when=parse_date(g.get('startTimeUTC'))
            if not when or when<=now or when>now+dt.timedelta(days=6):continue
            a=g.get('awayTeam',{});h=g.get('homeTeam',{})
            def name(t):return t.get('placeName',{}).get('default') or t.get('abbrev') or '?'
            out.append({'id':'nhl-'+str(g.get('id')),'sport':'NHL','league':'nhl','event':f'{name(h)} — {name(a)}','time':when.isoformat(),'home_rate':None,'away_rate':None,'source':'NHL official','source_url':url})
    return out

def enrich(x):
    # Only produce a selection if both teams have actual records; otherwise list fixture only.
    h,a=x.get('home_rate'),x.get('away_rate')
    if h is None or a is None:return x
    p=max(.34,min(.72,.5+(h-a)*.45+.045))
    if x['sport']=='Piłka nożna':p=min(.85,p+.18);market='1X (gospodarze lub remis)'
    else:market='Zwycięstwo gospodarzy (z dogrywką)'
    x.update(market=market,p_proxy=round(p,3),estimated_odds=round(1/p*1.07,2),reason=(f'Bilans zwycięstw gospodarzy w danych ESPN wynosi około {h:.0%}, a gości około {a:.0%}. ' + ('Proponowany rynek 1X obejmuje zwycięstwo gospodarzy lub remis. ' if x['sport']=='Piłka nożna' else 'Model rozważa zwycięstwo gospodarzy na podstawie porównania bilansów. ') + 'To uproszczona heurystyka bez uwzględnienia składów, kontuzji i rzeczywistych kursów.'),note='Eksperymentalny wskaźnik z bilansów; kurs NIE pochodzi z rynku i nie jest prognozą skalibrowaną.')
    return x

def build(now=None):
    now=now or dt.datetime.now(UTC);diagnostics=[];all_events=[]
    for label,sport,league in LEAGUES:all_events+=espn(now,sport,league,label,diagnostics)
    all_events+=nhl(now,diagnostics)
    unique={x['id']:x for x in all_events};events=sorted((enrich(x) for x in unique.values()),key=lambda x:x['time'])
    # Betting day: local 00:00 through next day 06:00, Europe/Warsaw.
    # Only future events are considered; overlap between adjacent betting days is intentional.
    dates=[(now.astimezone(WARSAW).date()+dt.timedelta(days=i)).isoformat() for i in range(5)]
    by_date={}
    for date in dates:
        start=dt.datetime.combine(dt.date.fromisoformat(date),dt.time.min,tzinfo=WARSAW)
        end=start+dt.timedelta(days=1,hours=6)
        daily=[x for x in events if x["time"] and start <= dt.datetime.fromisoformat(x["time"]).astimezone(WARSAW) <= end]
        by_date[date]=make_coupons(daily)
    selected=dates[0]
    return {'generated_at':now.isoformat(),'timezone':'Europe/Warsaw','betting_day_end':'06:00','available_dates':dates,'by_date':by_date,'events':events,'status':'ok' if events else 'no_data','fixtures':len(events),'eligible_picks':sum('estimated_odds' in x for x in events),'coupons':by_date[selected]['coupons'],'diagnostics':diagnostics,'errors':[d['source']+': '+d['detail'] for d in diagnostics if d['status']=='error'],'disclaimer':'Orientacyjne kursy są heurystyczne, nie rynkowe. Brak wiarygodnej oceny prawdopodobieństwa.'}

def make_coupons(events):
    picks=[x for x in events if 'estimated_odds' in x];coupons=[];used=set()
    for idx in range(3):
        best=None
        for n in (3,4,5):
            for combo in itertools.islice(itertools.combinations(picks[:26],n),12000):
                odds=math.prod(x['estimated_odds'] for x in combo)
                if odds<5 or (idx==0 and odds>9) or (idx==1 and not 7<=odds<=16) or (idx==2 and odds<12):continue
                overlap=sum(x['id'] in used for x in combo)
                score=(overlap*25+abs(odds-[6,10,18][idx])+max(0,2-len({x['league'] for x in combo}))*5)
                if best is None or score<best[0]:best=(score,combo,odds)
            if best:break
        if best:
            _,combo,odds=best;used.update(x['id'] for x in combo)
            coupons.append({'name':['Ostrożniejszy','Zrównoważony','Wysoki kurs'][idx],'picks':list(combo),'estimated_total_odds':round(odds,2),'warning':'Wyłącznie orientacyjne kursy z heurystyki; brak weryfikacji rynkowej i prawdopodobieństwa trafienia.'})
    return {'fixtures':len(events),'eligible_picks':len(picks),'coupons':coupons}

if __name__=='__main__':
    result=build();(ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data'/'daily.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('fixtures:',result['fixtures'],'eligible:',result['eligible_picks'],'coupons:',len(result['coupons']))
    print('sources:',len(result['diagnostics']),'errors:',len(result['errors']))
