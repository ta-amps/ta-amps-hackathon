#!/usr/bin/env python3
"""Test 2 rows: fresh real ready Tasks through the same reads decider.py makes. No model call here."""
import json, sys, time
from pathlib import Path
H = Path(__file__).resolve().parents[1]; N = H.parents[1]
sys.path[:0] = [str(N / "work-2026-11-02/warm-server-agent/src"), str(N / "work-2026-11-03/omninode-live"), str(N / "work-2026-11-03/meta-live")]
import httpx, decider as dec
from warm_agent.banned_words_guard import scrub_private_info
from warm_agent.decider import looks_secret
used = set()
for f in ("train", "dev", "held_refs", "panel"):
    for l in open(H / f"data/{f}.jsonl"):
        r = json.loads(l); used.add(r.get("task_id") or r["id"].split("-", 1)[-1])
tasks_local = set(json.load(open(H / "snapshot/tasks-local.json")))
http = httpx.Client(base_url=dec.SHIM, timeout=45, trust_env=False, headers={"User-Agent": "teleion-fabric-decider/1"})
total, tasks = dec.ready_tasks(http)
fresh = [t for t in tasks if t["task_id"] not in tasks_local and t["task_id"] not in used and not str(t["task_id"]).startswith("verb_index_enrich_")]
print("ready", total, "listed", len(tasks), "fresh non-index", len(fresh), flush=True)
fresh.sort(key=lambda t: t["task_id"])
import hashlib
fresh.sort(key=lambda t: hashlib.sha256(("test2:" + t["task_id"]).encode()).hexdigest())
rows = []
for t in fresh:
    if len(rows) >= 120: break
    title = str(t.get("title") or "")[:120]
    if looks_secret(title): continue
    r = http.post("/q/search", params={"record_demand": "0"}, json={"q": title, "limit": 30, "record_demand": False})
    cands = dec.candidates_from_search(r.json().get("results") or []) if r.status_code == 200 else []
    cands = [c for c in cands if c["id"] != t["task_id"] and not looks_secret(f"{c['id']} {c['title']} {c['summary']}")]
    if len(cands) < 2: continue
    rows.append({"id": "t2-" + t["task_id"], "set": "panel_held", "split": "panel_held", "task_id": t["task_id"], "candidates": [c["id"] for c in cands], "messages": dec.build_messages(t, cands, scrub_private_info)})
    time.sleep(.15)
(H / "records/test2-rows.json").write_text(json.dumps({"rows": rows}))
with open(H / "data/panel2.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r) + "\n")
print("rows", len(rows))
