#!/usr/bin/env python3
"""Optional free Live Tennis API integration. No fabricated matches or picks."""
import os,json,datetime as dt,urllib.request,urllib.error,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
KEY=os.environ.get('LIVE_TENNIS_API_KEY','').strip()
report={'source':'Live Tennis API','status':'not_configured','events':[],'detail':'Dodaj LIVE_TENNIS_API_KEY w GitHub Actions Secrets (darmowy klucz).'}
if KEY:
 try:
  req=urllib.request.Request('https://api.livetennisapi.com/api/public/v1/fixtures?limit=200',headers={'X-API-Key':KEY,'Accept':'application/json','User-Agent':'BUK-AI/7.6'})
  with urllib.request.urlopen(req,timeout=22) as r: payload=json.load(r)
  records=payload.get('data',[]) if isinstance(payload,dict) else []
  if isinstance(records,dict):records=records.get('items',[]) or records.get('fixtures',[])
  if not isinstance(records,list):records=[]
  now=dt.datetime.now(dt.timezone.utc)
  def player(p):
   if isinstance(p,str):return p
   if not isinstance(p,dict):return ''
   return p.get('name') or p.get('display_name') or p.get('full_name') or p.get('displayName') or ''
  for item in records:
   if not isinstance(item,dict):continue
   ts=item.get('scheduled_at') or item.get('start_time') or item.get('scheduled_start') or item.get('starts_at') or item.get('date')
   try:
    when=dt.datetime.fromisoformat(str(ts).replace('Z','+00:00'))
    if when.tzinfo is None:continue
    when=when.astimezone(dt.timezone.utc)
   except (ValueError,TypeError):continue
   if not now<when<now+dt.timedelta(days=6):continue
   a=player(item.get('player1') or item.get('player_1') or item.get('home_player') or item.get('home'))
   b=player(item.get('player2') or item.get('player_2') or item.get('away_player') or item.get('away'))
   players=item.get('players')
   if (not a or not b) and isinstance(players,list) and len(players)==2:a,b=player(players[0]),player(players[1])
   if not a or not b:continue
   report['events'].append({'id':'tennis-live-'+str(item.get('id') or len(report['events'])),'sport':'Tenis','league':str(item.get('tour') or item.get('tournament_name') or 'ATP/WTA/ITF'),'event':a+' — '+b,'time':when.isoformat(),'home_rate':None,'away_rate':None,'source':'Live Tennis API','source_url':'https://livetennisapi.com/','note':'Terminarz bez typów i kursów; darmowy plan nie zawiera modelu predykcyjnego.'})
  report.update(status='ok',detail='Pobrano '+str(len(report['events']))+' zaplanowanych meczów z kompletnymi nazwami i godziną.')
 except Exception as e:report.update(status='error',detail=str(e)[:180])
(ROOT/'data').mkdir(exist_ok=True)
(ROOT/'data'/'tennis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Tennis:',report['status'],len(report['events']),report['detail'])
