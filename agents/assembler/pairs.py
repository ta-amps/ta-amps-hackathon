"""Sample real Task pairs for a held-out test of the profile score. Stratified by score; split by pair hash; labels come blind from label_pairs.py."""
import collections,hashlib,json,random,time
import fp
T=json.load(open("records/tasks_raw.json"))
tasks=[t for t in T.values() if not str(t.get("category","")).startswith(("e2e-canary","final-read")) and len(fp.text_of(t))>60]
rng=random.Random(20261104); rng.shuffle(tasks)
seen=collections.Counter(); keep=[]
for t in tasks:
    if seen[t["category"]]<500: keep.append(t); seen[t["category"]]+=1
t0=time.time(); fps={t["task_id"]:fp.fingerprint(t) for t in keep}; print("fingerprinted",len(fps),round(time.time()-t0,1),"s",flush=True)
json.dump(fps,open("records/fps_sample.json","w"))
ids=list(fps); strata=collections.defaultdict(list); seenp=set(); t0=time.time()
for _ in range(150000):
    a,c=rng.sample(ids,2); p=(min(a,c),max(a,c))
    if p in seenp: continue
    seenp.add(p); s=fp.score(fps[a],fps[c]); strata[int(s*10)/10].append(p+(s,))
    if time.time()-t0>40: break
by=collections.defaultdict(list)
for i in ids:
    for b in fps[i]["bands"]: by[b].append(i)
for b,v in by.items():
    if len(v)>1:
        for _ in range(4):
            a,c=rng.sample(v,2); p=(min(a,c),max(a,c))
            if p not in seenp:
                seenp.add(p); s=fp.score(fps[a],fps[c]); strata[int(s*10)/10].append(p+(s,))
print({k:len(v) for k,v in sorted(strata.items())},flush=True)
out=[]
for k,v in strata.items():
    rng.shuffle(v); out+=v[:50]
rng.shuffle(out)
rows=[{"a":a,"b":c,"score":s,"parts":fp.parts(fps[a],fps[c]),"exact":fps[a]["exact"]==fps[c]["exact"],"split":"dev" if int(hashlib.sha256((a+c).encode()).hexdigest(),16)%3==0 else "held",
       "ta":fp.text_of(T[a])[:900],"tb":fp.text_of(T[c])[:900]} for a,c,s in out]
json.dump(rows,open("records/pairs.json","w"))
print(len(rows),collections.Counter(r["split"] for r in rows),collections.Counter(r["exact"] for r in rows))
