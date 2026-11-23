"""Compare retained keyword candidates with scoped checks on the same saved sources."""
from pathlib import Path
import json
from verify import verify_documents
ROOT=Path(__file__).resolve().parent

def evaluate(rows):
    checks=[]
    for r in rows:
        before=sorted({e['value'] for e in r['baseline'] if e['field']=='auth'})
        after=verify_documents([r['document']])['scoped_fields']['api']['auth']
        expected=r['expected']
        checks.append({'id':r['id'],'app':r['app'],'url':r['url'],'expected':expected,'before':before,'after':after,
                       'before_ok':before==expected,'after_ok':after==expected,'fetch_status':r['document']['status'],
                       'document_sha256':r['document'].get('sha256'),
                       'missing_after':sorted(set(expected)-set(after)),'extra_after':sorted(set(after)-set(expected))})
    return {'method':'Ten previously reviewed auth sets, one frozen official document per app. Baseline and new rules see identical text. Development sample, not blind or independently labeled. Expected sets can require additional sources; missing methods measure a combination of retrieval coverage and extraction errors. Access and buildability are not scored.','checks':checks,'before_correct':sum(c['before_ok'] for c in checks),'after_correct':sum(c['after_ok'] for c in checks)}
if __name__=='__main__':
    source=ROOT/'output/verification-frozen.json'
    if not source.exists():raise SystemExit('Local frozen documents are not distributed. Inspect data/verification-evaluation.json for recorded results and hashes; rerun research to obtain fresh documents.')
    result=evaluate(json.loads(source.read_text()))
    (ROOT/'data/verification-evaluation.json').write_text(json.dumps(result,indent=2))
    print(f"Exact auth sets: {result['before_correct']}/10 before, {result['after_correct']}/10 after")
    for c in result['checks']:print(c['app'],c['before'],c['after'],c['expected'])
