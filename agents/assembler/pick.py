"""Pick real, different ready Tasks across kinds, from the open read, fresh."""
import collections,json,random,sys
import httpx,fp
T=json.load(open("records/tasks_raw.json"))
rng=random.Random(int(sys.argv[1]) if len(sys.argv)>1 else 7)
try: tried={json.loads(l)["task_id"] for l in open("records/spin_up_runs.jsonl")}
except FileNotFoundError: tried=set()
ready=[t for t in T.values() if t.get("state")=="ready" and not str(t["category"]).startswith(("e2e-","final-read")) and t["task_id"] not in tried]
rng.shuffle(ready)
want=json.loads(sys.argv[2]) if len(sys.argv)>2 else {"distributed_index_enrichment":1,"ngo_public_good":4,"report_upkeep":2,"eval_and_rank":2,"general_verb":2,"demo_and_video":1,"version_propagation_recheck":1,"feedback_verification_and_benchmark":1,"meta_generator":1,"worker_self_directed":1,"aggregate_work_review":1}
print(collections.Counter(t["category"] for t in ready).most_common(14))
h=httpx.Client(base_url="https://shim.teleionlabs.com",timeout=30,headers={"User-Agent":"teleion-assembler/1"})
out=[];seen=[]
for cat,n in want.items():
    got=0
    for t in ready:
        if got>=n: break
        if t["category"]!=cat: continue
        f=fp.fingerprint(t)
        if any(fp.score(f,s)>0.9 for s in seen): continue
        cur=h.get(f"/q/task/{t['task_id']}").json().get("task") or {}
        if cur.get("state")!="ready": continue
        cur.setdefault("category",t["category"]); out.append(cur); seen.append(f); got+=1
json.dump(out,open(sys.argv[3] if len(sys.argv)>3 else "records/batch1.json","w"))
for t in out: print(t["task_id"],t["category"],int(t.get("complexity_milli") or 0),str(t.get("title"))[:80],fp.needs(fp.text_of(t)))
