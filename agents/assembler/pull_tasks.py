"""Pull real Tasks from the shim's open read, with their full prompts, for fingerprint tests."""
import json,sys,time,httpx
h=httpx.Client(base_url="https://shim.teleionlabs.com",timeout=60,headers={"User-Agent":"teleion-assembler/1"})
out={}
for st in ("ready","done","completed","leased","failed"):
    off=0
    while off<4000:
        try: r=h.get("/q/tasks",params={"state":st,"limit":200,"offset":off,"finished":"true"})
        except Exception as e: print(st,off,e); break
        if r.status_code!=200: print(st,off,r.status_code,r.text[:200]); break
        d=r.json(); ts=d.get("tasks") or []
        for t in ts: out[t["task_id"]]=t
        print(st,off,len(ts),d.get("total_matching"),flush=True)
        off+=200
        if not ts or off>=int(d.get("total_matching") or 0): break
        time.sleep(0.3)
json.dump(out,open("records/tasks_raw.json","w"))
print(len(out))
import collections
print(collections.Counter(t.get("state") for t in out.values()).most_common())
print(collections.Counter(t.get("category") for t in out.values()).most_common(25))
print(json.dumps(next(iter(out.values())))[:1200])
