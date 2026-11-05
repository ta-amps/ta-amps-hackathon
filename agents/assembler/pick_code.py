import json,random,httpx,fp
T=json.load(open("records/tasks_raw.json")); tried={json.loads(l)["task_id"] for l in open("records/spin_up_runs.jsonl")}
batch=[t["task_id"] for t in json.load(open("records/batch1.json"))]+["verb_ngo_3e93e0be0e7c"]*0
rd=[t for t in T.values() if t.get("state")=="ready" and t["task_id"] not in tried and t["task_id"] not in batch and "run_code" in fp.needs(fp.text_of(t)) and "people_or_hardware" not in fp.needs(fp.text_of(t)) and fp.output_shape(fp.text_of(t))=="code_and_tests" and t["category"] in("ngo_public_good","general_verb","meta_generator","public_general")]
random.Random(5).shuffle(rd); print(len(rd))
h=httpx.Client(base_url="https://shim.teleionlabs.com",timeout=30,headers={"User-Agent":"teleion-assembler/1"}); out=[];seen=[]
if T["verb_ngo_3e93e0be0e7c"]["task_id"] not in tried: rd.insert(0,T["verb_ngo_3e93e0be0e7c"])
for t in rd:
    f=fp.fingerprint(t)
    if any(fp.score(f,s)>0.85 for s in seen): continue
    cur=h.get(f"/q/task/{t['task_id']}").json().get("task") or {}
    if cur.get("state")!="ready": continue
    cur.setdefault("category",t["category"]); out.append(cur); seen.append(f); print(t["task_id"],t["category"],str(t["title"])[:80])
    if len(out)>=5: break
json.dump(out,open("records/batch3.json","w"))
