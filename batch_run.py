"""Run the bounded pipeline on the assignment set and preserve per-app outcomes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
from datetime import datetime, timezone
from agent import run
ROOT=Path(__file__).resolve().parent

def main():
    seeds=json.loads((ROOT/'data/seeds.json').read_text())
    def task(pair):
        i,seed=pair
        result=run(seed['app'],seed['website'],ROOT/'output/batch'/str(i),max_pages=3)
        return {'id':i,**{k:result[k] for k in ('app','checked_at','pages_attempted','pages_read','elapsed_seconds','fields','prototype','production','blockers')},'verification_counts':result['verification']['counts'],'documents':result['documents']}
    rows=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(task,p):p for p in enumerate(seeds,1)}
        for future in as_completed(futures):
            i,seed=futures[future]
            try:rows.append(future.result())
            except Exception as exc:rows.append({'id':i,'app':seed['app'],'pages_read':0,'pages_attempted':0,'error':type(exc).__name__})
            if len(rows)%10==0: print(f'{len(rows)}/100 processed',flush=True)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'method':'Live seeded discovery, maximum 3 pages per app, 3 concurrent apps. Seed URLs are prior research inputs; no open-web search. Does not overwrite reviewed judgments.','apps':sorted(rows,key=lambda r:r['id'])}
    (ROOT/'data/batch-run.json').write_text(json.dumps(report,indent=2))
    print('Saved data/batch-run.json',flush=True)
if __name__=='__main__':main()
