"""Conservative, deterministic evidence checks. Support is not a truth guarantee."""
import re
from urllib.parse import urlsplit
from research import SIGNALS

SCOPES = ('api', 'mcp', 'webhook', 'unknown')

def scope_for(url, sentence):
    path = urlsplit(url).path.lower()
    if 'webhook' in path: return 'webhook'
    if re.search(r'(?:^|[/_-])mcp(?:[/_.-]|$)', path): return 'mcp'
    lower = sentence.lower()
    if re.search(r'webhook.{0,80}(?:sign|secret|auth)|(?:sign|secret).{0,80}webhook', lower): return 'webhook'
    if re.search(r'\bmcp\b|model context protocol', lower): return 'mcp'
    if re.search(r'api|auth|oauth|graphql|rest',path) or re.search(r'\bapi\b|authenticat|authorization|requests?',lower): return 'api'
    return 'unknown'

def verify_documents(documents):
    evidence=[]
    for doc in documents:
        if doc.get('status')!='read': continue
        url=doc.get('resolved_url',doc['url'])
        text=doc.get('text','')
        # Exclude serialized navigation/JS leaked into rendered documentation.
        text=' '.join(line.strip() for line in text.splitlines() if not re.search(r'_jsx|_jsxs|children:|\"group\":|\"pages\":|self\.__next|webpack',line))
        index=bool(re.search(r'llms(?:-full)?\.txt|sitemap',urlsplit(url).path))
        for field,rules in SIGNALS.items():
            for value,pattern in rules.items():
                # Retain up to three distinct contexts, so a contrary statement isn't hidden by the first match.
                seen=set()
                for match in re.finditer(pattern,text,re.I):
                    start=max(text.rfind('\n',0,match.start()),text.rfind('. ',0,match.start()))+1
                    ends=[n for n in (text.find('\n',match.end()),text.find('. ',match.end())) if n>=0]
                    end=min(ends) if ends else len(text)
                    sentence=' '.join(text[max(start,match.start()-150):min(end,match.end()+200)].split())
                    if sentence in seen:continue
                    if len(sentence.split())<5:continue
                    seen.add(sentence)
                    scope=scope_for(url,sentence)
                    negative=bool(re.search(r'\b(?:no|not|never|unsupported|deprecated|disabled)\b',sentence,re.I))
                    affirmative=bool(re.search(r'\b(?:uses?|supports?|authenticate|authentication|authorization|requires?|create|generate|pass|header|provided|available|access|built|offers?|free|trial|sandbox|paid)\b',sentence,re.I))
                    if index:
                        status,reason='insufficient evidence','Documentation index is a discovery source, not an assertion.'
                    elif scope=='unknown' or len(sentence.split())<5 or not affirmative:
                        status,reason='insufficient evidence','No clear scoped assertion; inspect the source context.'
                    elif negative:
                        status,reason='conflicting','Negation or deprecation appears nearby; review before accepting this positive claim.'
                    else:
                        status,reason='supported','Exact source context contains a scoped affirmative statement; rule-supported, not independently verified.'
                    if field=='access':
                        status,reason='insufficient evidence','Plan and sandbox mentions do not establish API credential entitlement; manual review required.'
                    if field=='mcp':
                        status,reason='insufficient evidence','A protocol mention does not establish a vendor-maintained server; confirm ownership and direction.'
                    evidence.append(dict(field=field,value=value,scope=scope,url=url,excerpt=sentence,
                                         status=status,reason=reason,checked_at=doc.get('checked_at'),document_sha256=doc.get('sha256')))
                    if len(seen)>=3:break
    # Contradictory contexts override positive claims within the same field/value/scope.
    conflicts={(e['field'],e['value'],e['scope']) for e in evidence if e['status']=='conflicting'}
    for e in evidence:
        if (e['field'],e['value'],e['scope']) in conflicts and e['status']=='supported':
            e.update(status='conflicting',reason='Another retrieved context flags negation/deprecation for this scoped claim.')
    scoped={scope:{field:sorted({e['value'] for e in evidence if e['scope']==scope and e['field']==field and e['status']=='supported'}) for field in SIGNALS} for scope in SCOPES}
    return {'method':'Deterministic scope and textual-support checks; no model or independent reviewer',
            'scoped_fields':scoped,'evidence':evidence,
            'review_queue':[e for e in evidence if e['status']!='supported'],
            'counts':{status:sum(e['status']==status for e in evidence) for status in ('supported','conflicting','insufficient evidence')}}
