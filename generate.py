#!/usr/bin/env python3
"""BUK AI: free fixtures with source diagnostics. No invented sportsbook prices."""
import datetime as dt, itertools, json, math, pathlib, urllib.request, urllib.error
from zoneinfo import ZoneInfo
WARSAW=ZoneInfo("Europe/Warsaw")
ROOT=pathlib.Path(__file__).resolve().parent
UTC=dt.timezone.utc
LEAGUES=[('Piłka nożna','soccer','eng.1'),('Piłka nożna','soccer','esp.1'),('Piłka nożna','soccer','ger.1'),('Piłka nożna','soccer','ita.1'),('Piłka nożna','soccer','fra.1'),('Piłka nożna','soccer','uefa.champions'),('Piłka nożna','soccer','pol.1'),('Piłka nożna','soccer','ned.1'),('Piłka nożna','soccer','por.1'),('Piłka nożna','soccer','usa.1'),('Piłka nożna','soccer','uefa.europa'),('Piłka nożna','soccer','eng.2'),('Piłka nożna','soccer','bra.1'),('Koszykówka','basketball','nba'),('Koszykówka','basketball','wnba'),('Koszykówka','basketball','mens-college-basketball'),('NHL','hockey','nhl'),('Tenis','tennis','atp'),('Tenis','tennis','wta')]

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

def competitor_name(x):
    return (x.get('team') or x.get('athlete') or {}).get('displayName') or x.get('displayName') or '?'

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
            if (not home or not away) and label=='Tenis' and len(teams)==2:
                home,away=teams
            if not home or not away:continue
            hr,ar=win_rate(home),win_rate(away)
            out.append({'id':f'{sport}-{league}-{event.get("id")}', 'sport':label,'league':league,'event':f'{competitor_name(home)} — {competitor_name(away)}', 'time':when.isoformat(), 'home_rate':hr,'away_rate':ar,'source':'ESPN','source_url':url})
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

def historical(now, events, diagnostics):
    from concurrent.futures import ThreadPoolExecutor
    leagues={(sport,league) for label,sport,league in LEAGUES if label!='Tenis' and (sport=='soccer' or any(e['league']==league for e in events))}
    jobs=[(sport,league,(now.astimezone(WARSAW).date()-dt.timedelta(days=i)).strftime('%Y%m%d')) for sport,league in leagues for i in range(1,91)]
    def fetch(job):
        sport,league,day=job
        url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={day}&limit=100'
        try:return league,get(url).get('events',[]),None
        except Exception as exc:return league,[],str(exc)
    rows={}; seen=set(); errors=0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for league,games,error in pool.map(fetch,jobs):
            if error:errors+=1;continue
            for game in games:
                c=(game.get('competitions') or [{}])[0]
                if not (c.get('status',{}).get('type',{}).get('completed') or game.get('status',{}).get('type',{}).get('completed')):continue
                teams=c.get('competitors',[]); key=(league,game.get('id'))
                if len(teams)!=2 or key in seen:continue
                try: scores=[float(t['score']) for t in teams]
                except (ValueError,KeyError,TypeError):continue
                seen.add(key)
                for i,t in enumerate(teams):
                    row=(game.get('date',''),scores[i],scores[1-i],key)
                    rows.setdefault((league,competitor_name(t)),[]).append(row)
                    if league not in ('nba','nhl','wnba','mens-college-basketball'):
                        rows.setdefault(('soccer-all',competitor_name(t)),[]).append(row)
    diagnostics.append({'source':'ESPN — wyniki 90 dni','status':'ok' if seen else 'error','events':len(seen),'detail':f'Nieudane zapytania: {errors}/{len(jobs)}'})
    return rows

def enrich(x, history, quotes=None):
    quotes=quotes or {}
    if x['sport']=='Tenis':
        x['rejection_reason']='Tylko terminarz: brak zweryfikowanej historii tenisowej';return x
    home,away=x['event'].split(' — ',1)
    scope='soccer-all' if x['sport']=='Piłka nożna' else x['league']
    h=sorted(history.get((scope,home),[]),reverse=True)[:12]; a=sorted(history.get((scope,away),[]),reverse=True)[:12]
    x['history_samples']=[len(h),len(a)]
    x['quoted_markets']=len(quotes)
    x['qualified_markets']=0
    if not quotes:
        x['rejection_reason']='Brak dopasowanych aktualnych kursów';return x
    if min(len(h),len(a))<5:
        x['rejection_reason']='Za mało meczów historycznych';return x
    candidates=[]
    def add(market,family,fh,fa):
        hh=sum(fh(r[1],r[2]) for r in h); aa=sum(fa(r[1],r[2]) for r in a)
        if min(hh/len(h),aa/len(a))<.55:return
        rate=(hh/len(h)+aa/len(a))/2
        if rate<.65:return
        if market not in quotes:return
        price,book,stamp=quotes[market]
        # Historical frequency is not a forecast. Shrink toward 0.5 for indicative price only.
        proxy=.5+(rate-.5)*.65
        candidates.append(dict(market=market,family=family,quality=round(rate*min(1,min(len(h),len(a))/10),4),estimated_odds=price,odds_book=book,odds_time=stamp,odds_verified=True,reason=f'{home}: {hh}/{len(h)}; {away}: {aa}/{len(a)} meczów zgodnych z kryterium. Próba: ostatnie maks. 12 meczów z 90 dni (piłka: także inne rozgrywki). Częstość historyczna {rate:.0%}, nie prognoza. Kurs z oferty wskazanego bukmachera.',historical_rate=round(rate,3)))
    if x['sport']=='Piłka nożna':
        for line in sorted({float(k.split()[-1]) for k in quotes if k.startswith('Gole ')}):
            add(f'Gole powyżej {line}','gole',lambda f,g:f+g>line,lambda f,g:f+g>line)
            add(f'Gole poniżej {line}','gole',lambda f,g:f+g<line,lambda f,g:f+g<line)
        add('Obie drużyny strzelą — tak','BTTS',lambda f,g:f>0 and g>0,lambda f,g:f>0 and g>0)
        add('Obie drużyny strzelą — nie','BTTS',lambda f,g:f==0 or g==0,lambda f,g:f==0 or g==0)
        add('1X','wynik',lambda f,g:f>=g,lambda f,g:f<=g)
        add('X2','wynik',lambda f,g:f<=g,lambda f,g:f>=g)
    else:
        lines=(4.5,5.5,6.5,7.5) if x['sport']=='NHL' else (195.5,205.5,215.5,225.5,235.5,245.5) if x['league']=='nba' else (135.5,145.5,155.5,165.5)
        unit='Bramki' if x['sport']=='NHL' else 'Punkty'
        for line in sorted({float(k.split()[-1]) for k in quotes if k.startswith(unit+' ')}):
            add(f'{unit} powyżej {line}','suma',lambda f,g:f+g>line,lambda f,g:f+g>line)
            add(f'{unit} poniżej {line}','suma',lambda f,g:f+g<line,lambda f,g:f+g<line)
    add('Zwycięstwo gospodarzy','wynik',lambda f,g:f>g,lambda f,g:f<g)
    add('Zwycięstwo gości','wynik',lambda f,g:f<g,lambda f,g:f>g)
    for market in quotes:
        if market.startswith('Handicap '):
            side, line=market.split()[1:]; line=float(line)
            if side=='gospodarzy':add(market,'handicap',lambda f,g:f-g+line>0,lambda f,g:g-f+line>0)
            elif side=='gości':add(market,'handicap',lambda f,g:g-f+line>0,lambda f,g:f-g+line>0)
    if candidates:
        candidates.sort(key=lambda c:(c['quality'],c['estimated_odds']),reverse=True)
        x['qualified_markets']=len(candidates);x.update(candidates[0]);x['markets']=candidates;x['source']='ESPN — zakończone mecze'
    else:x['rejection_reason']='Żaden rynek nie spełnił kryteriów historycznych'
    return x

def build(now=None):
    now=now or dt.datetime.now(UTC);diagnostics=[];all_events=[]
    for label,sport,league in LEAGUES:all_events+=espn(now,sport,league,label,diagnostics)
     # NHL: ESPN names and historical records use the same identifiers.
    tennis_file=ROOT/'data'/'tennis.json'
    if tennis_file.exists():
        try:
            tennis=json.loads(tennis_file.read_text(encoding='utf-8'))
            diagnostics.append({'source':'Live Tennis API','status':tennis.get('status','unknown'),'events':len(tennis.get('events',[])),'detail':tennis.get('detail','')})
            for event in tennis.get('events',[]):
                when=parse_date(event.get('time'))
                if when and now<when<now+dt.timedelta(days=6):all_events.append(event)
        except Exception as exc:diagnostics.append({'source':'Live Tennis API','status':'error','detail':str(exc)[:120]})
    unique={x['id']:x for x in all_events}
    history=historical(now,list(unique.values()),diagnostics)
    from odds import attach
    quotes=attach(list(unique.values()),get,parse_date,diagnostics,now)
    events=sorted((enrich(x, history, quotes.get(x['id'])) for x in unique.values()),key=lambda x:x['time'])
    from collections import Counter
    for league in sorted({x['league'] for x in events}):
        group=[x for x in events if x['league']==league]
        diagnostics.append({'source':'Analiza '+league,'status':'ok','events':len(group),'detail':str(dict(Counter(x.get('rejection_reason','Zakwalifikowany') for x in group)))})
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
    return {'generated_at':now.isoformat(),'timezone':'Europe/Warsaw','betting_day_end':'06:00','available_dates':dates,'by_date':by_date,'events':events,'status':'ok' if events else 'no_data','fixtures':len(events),'eligible_picks':sum('estimated_odds' in x for x in events),'coupons':by_date[selected]['coupons'],'diagnostics':diagnostics,'errors':[d['source']+': '+d['detail'] for d in diagnostics if d['status']=='error'],'disclaimer':'Kursy pochodzą z ofert bukmacherów; niekoniecznie Superbet. Brak wiarygodnej oceny prawdopodobieństwa.'}

def make_coupons(events):
    picks=sorted((x for x in events if 'estimated_odds' in x),key=lambda x:x.get('quality',0),reverse=True);coupons=[];used=set()
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
            coupons.append({'name':['Ostrożniejszy','Zrównoważony','Wysoki kurs'][idx],'picks':list(combo),'estimated_total_odds':round(odds,2),'warning':'Iloczyn kursów z ofert; nie jest gwarantowaną ofertą AKO jednego bukmachera.'})
    return {'fixtures':len(events),'eligible_picks':len(picks),'coupons':coupons}

if __name__=='__main__':
    result=build();(ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data'/'daily.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('fixtures:',result['fixtures'],'eligible:',result['eligible_picks'],'coupons:',len(result['coupons']))
    print('sources:',len(result['diagnostics']),'errors:',len(result['errors']))
