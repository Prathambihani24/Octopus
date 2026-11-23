#!/usr/bin/env python3
"""Bounded official-document discovery pipeline. No model tokens or API keys."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import socket
import time
from urllib.parse import urljoin, urlsplit, urldefrag
import urllib.request
from research import extract_signals, SIGNALS

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.skip = [], [], 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer'): self.skip += 1
        if tag == 'a':
            self.links.extend(v for k,v in attrs if k == 'href' and v)
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer') and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())

def public_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError('Only public HTTPS documentation URLs are allowed')
    if p.hostname == 'localhost' or p.hostname.endswith(('.localhost','.local')):
        raise ValueError('Private network destinations are not allowed')
    try:
        addresses = socket.getaddrinfo(p.hostname,443)
    except socket.gaierror:
        if not urllib.request.getproxies().get('https'): raise
        addresses = []  # Configured HTTPS proxy resolves remote hostnames.
    for result in addresses:
        if not ipaddress.ip_address(result[4][0]).is_global:
            raise ValueError('Private network destinations are not allowed')
    return url

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(url, cache, refresh=False):
    key = hashlib.sha256(url.encode()).hexdigest()
    path = cache / (key + '.json')
    if path.exists() and not refresh:
        record = json.loads(path.read_text())
        if record.get('status') == 'read': return {**record, 'cached': True}
    record = {'url':url, 'checked_at':datetime.now(timezone.utc).isoformat(), 'cached':False}
    try:
        public_url(url)
        req = urllib.request.Request(url,headers={'User-Agent':'OctopusResearch/2.0 (public documentation research)'})
        with urllib.request.build_opener(Redirects()).open(req,timeout=12) as response:
            raw = response.read(1_000_001)
            content_type = response.headers.get('Content-Type','')
            if not any(x in content_type for x in ('text/', 'json', 'xml')):
                raise ValueError('Unsupported document content type')
            text = raw[:1_000_000].decode('utf-8',errors='replace')
            links = []
            if 'html' in content_type:
                parser = Document(); parser.feed(text)
                text, links = '\n'.join(parser.parts), parser.links
            links += re.findall(r'\]\((https?://[^\s)]+|/[^\s)]+)\)', text)
            record.update(status='read',resolved_url=response.geturl(),text=text,
                          links=[urldefrag(urljoin(response.geturl(),x))[0] for x in links],
                          sha256=hashlib.sha256(raw).hexdigest(),truncated=len(raw)>1_000_000)
    except (OSError, ValueError) as exc:
        record.update(status='unavailable',error=type(exc).__name__,text='',links=[])
    cache.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(record,ensure_ascii=False))
    return record

def priority(url):
    terms = ['authentication','authorization','oauth','api-key','pricing','getting-started','quickstart','mcp','overview','api','docs']
    return sum(20-i for i,term in enumerate(terms) if term in url.lower())

def extract_evidence(record):
    # Exact short excerpts are candidates only. Negation and product scope need review.
    result = []
    text = record.get('text','')
    for field,rules in SIGNALS.items():
        for label,pattern in rules.items():
            match = re.search(pattern,text,re.I)
            if match:
                start,end = max(0,match.start()-45), min(len(text),match.end()+95)
                result.append({'field':field,'value':label,'url':record.get('resolved_url',record['url']),
                               'excerpt':' '.join(text[start:end].split()),'status':'candidate'})
    return result

def run(app, website, out, max_pages=10, refresh=False):
    start = time.monotonic()
    if not 2 <= max_pages <= 30: raise ValueError('Page budget must be 2–30')
    p = urlsplit(website)
    if p.scheme != 'https' or not p.hostname: raise ValueError('Provide an HTTPS website or docs URL')
    root = p.hostname.removeprefix('www.')
    def allowed(url):
        host = urlsplit(url).hostname or ''
        return url.startswith('https://') and (host == root or host.endswith('.'+root))
    out.mkdir(parents=True,exist_ok=True)
    cache = out.parent / '.doc-cache'
    pending = [website, urljoin(website,'/llms.txt')]
    visited, records = set(), []
    while pending and len(visited) < max_pages:
        batch = [u for u in sorted(set(pending),key=lambda u:(-priority(u),u)) if u not in visited][:min(4,max_pages-len(visited))]
        if not batch: break
        visited.update(batch)
        with ThreadPoolExecutor(max_workers=4) as pool:
            fresh = list(pool.map(lambda u:fetch(u,cache,refresh), batch))
        records.extend(fresh)
        pending = [u for u in pending if u not in visited]
        for doc in fresh:
            pending.extend(u for u in doc.get('links',[]) if allowed(u) and priority(u)>0 and u not in visited)
    evidence = [e for doc in records for e in extract_evidence(doc)]
    fields = {f:sorted({e['value'] for e in evidence if e['field']==f}) for f in SIGNALS}
    readable = sum(r['status']=='read' for r in records)
    result = {'app':app,'website':website,'method':'bounded official-domain discovery; deterministic candidate extraction',
        'checked_at':datetime.now(timezone.utc).isoformat(),'budget_pages':max_pages,'pages_attempted':len(records),
        'pages_read':readable,'elapsed_seconds':round(time.monotonic()-start,2),'model_tokens':0,
        'fields':fields,'evidence':evidence,
        'prototype':'Needs review' if readable else 'Blocked: documentation unavailable',
        'production':'Unconfirmed; verify credentials, scopes, plan and distribution approval',
        'blockers':[f+' evidence missing' for f,values in fields.items() if not values],
        'review_required':['Confirm vendor/product identity','Resolve negation and API versus MCP scope',
                           'Verify prototype and production entitlement separately','Confirm useful actions and API breadth'],
        'documents':[{k:v for k,v in r.items() if k not in ('text','links')} for r in records]}
    (out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
    # Preserve fetched document text locally for reproducibility; do not deploy full vendor documents.
    (out/'documents.json').write_text(json.dumps(records,ensure_ascii=False))
    escape = html.escape
    rows = ''.join('<tr>'+''.join('<td>'+escape(str(e[k]))+'</td>' for k in ('field','value','excerpt','url'))+'</tr>' for e in evidence)
    (out/'report.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+escape(app)+' research</title><style>body{max-width:1100px;margin:40px auto;padding:20px;font:16px/1.6 sans-serif}td,th{padding:12px;border-bottom:1px solid #ccc;text-align:left;overflow-wrap:anywhere}table{width:100%;table-layout:fixed}</style><h1>'+escape(app)+' — research candidates</h1><p>'+str(readable)+' pages read. Model tokens: 0. All findings need scope and entitlement review.</p><p>Production: '+escape(result['production'])+'</p><table><tr><th>Field</th><th>Candidate</th><th>Evidence excerpt</th><th>Source</th></tr>'+rows+'</table>')
    return result

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--app'); cli.add_argument('--website'); cli.add_argument('--batch',type=Path)
    cli.add_argument('--out',type=Path,default=Path('output/new-app'))
    cli.add_argument('--max-pages',type=int,default=10); cli.add_argument('--refresh',action='store_true')
    args=cli.parse_args()
    if args.batch:
        seeds=json.loads(args.batch.read_text())
        if not isinstance(seeds,list) or len(seeds)>100: cli.error('Batch must be a list of at most 100 app/website objects')
    elif args.app and args.website: seeds=[{'app':args.app,'website':args.website}]
    else: cli.error('Use --app and --website, or --batch seeds.json')
    for index,seed in enumerate(seeds):
        destination=args.out/str(index+1) if args.batch else args.out
        result=run(seed['app'],seed['website'],destination,args.max_pages,args.refresh)
        print(json.dumps({k:result[k] for k in ('app','pages_read','pages_attempted','model_tokens','prototype')}))
if __name__=='__main__': main()
