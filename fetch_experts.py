"""Best-effort PUBLIC publication discovery. Never invent betting selections.
No paid APIs, authentication, or bypass of access controls.
"""
import json, re, urllib.request, urllib.error, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path

UA='BUKAI/7.4 (+public-source-check; no authentication)'
class Links(HTMLParser):
    def __init__(self): super().__init__();self.href=None;self.buf=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.href=dict(attrs).get('href');self.buf=[]
    def handle_data(self,data):
        if self.href is not None:self.buf.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href:
            title=' '.join(' '.join(self.buf).split());self.links.append((self.href,title));self.href=None

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/atom+xml,application/rss+xml'})
    with urllib.request.urlopen(req,timeout=15) as r:return r.read(750000).decode('utf-8','replace')

items=[];diagnostics=[]
def add(source,title,url,published=''):
    if not title or not url.startswith('https://'):return
    if any(i['url']==url for i in items):return
    items.append({'source':source,'title':title[:180],'url':url,'published':published[:35]})

# ZawodTyper: collect publicly linked daily pages and editor articles; no claims about exact bets.
for name,url in [('Zawód Typer — Typy Dnia','https://zawodtyper.pl/typy-dnia/'),('Zawód Typer — Typy redaktorów','https://zawodtyper.pl/')]:
    try:
        page=get(url);parser=Links();parser.feed(page);count=0
        for href,title in parser.links:
            if href.startswith('/') :href='https://zawodtyper.pl'+href
            if not href.startswith('https://zawodtyper.pl/'):continue
            if name.endswith('Typy Dnia'):
                ok=('typy-dnia' in href and href.rstrip('/')!='https://zawodtyper.pl/typy-dnia') and (re.search(r'\d{1,2}',title) or 'Typy Dnia' in title)
            else:
                ok=('typy' in title.lower() and (' - ' in title or ' vs ' in title.lower()) and href.rstrip('/')!='https://zawodtyper.pl')
            if ok:
                add(name,title,href);count+=1
            if count>=20:break
        diagnostics.append({'source':name,'status':f'Pobrano stronę; znaleziono {count} odnośników do materiałów'})
    except Exception as e:diagnostics.append({'source':name,'status':f'Nie udało się pobrać: {type(e).__name__}: {str(e)[:100]}'})

out={'updated_at':datetime.now(timezone.utc).isoformat(),'note':'Zawód Typer: materiały i linki, nie potwierdzone selekcje bukmacherskie','items':items[:60],'diagnostics':diagnostics}
Path('data').mkdir(exist_ok=True)
Path('data/expert_materials.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('Expert materials:',len(items),[(x['source'],x['status']) for x in diagnostics])
