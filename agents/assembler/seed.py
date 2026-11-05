"""Seed the assembly memory only from outcomes already on record: the sizing worker's read answers and index runs, and the OpenCode swarm's checker verdicts."""
import json
from pathlib import Path

import httpx

import fp

NOTES = Path(__import__("os").environ["TELEION_NOTES"])
T = json.load(open("records/tasks_raw.json"))
rows, miss = [], 0


def add(task_id, harness, model, outcome, source):
    global miss
    t = T.get(task_id)
    if not t:
        miss += 1
        return
    rows.append({"task_id": task_id, "fp": fp.fingerprint(t), "assembly": {"harness": harness, "model": model}, "outcome": outcome, "source": source})


for line in open(NOTES / "work-2026-11-03/sizing/records/outcomes.jsonl"):
    r = json.loads(line)
    if r.get("handler") == "client_index" and r.get("finished_ok"):
        add(r["task_id"], "deterministic_only", None, {"pass": True, "usd": 0.0, "needs_people": False}, "sizing")
    elif r.get("audit_pass") is not None:
        model = {"small": "muse-spark-1.3-contributor", "big": "muse-wonder-1.0"}.get(r.get("size"), "muse-spark-1.3-contributor")
        add(r["task_id"], "json_answer", model, {"pass": bool(r["audit_pass"]), "usd": float(r.get("usd") or 0), "needs_people": bool(r.get("needs_people_or_hardware") or r.get("audit_needs_people"))}, "sizing")

v = json.load(open(NOTES / "work-2026-11-03/agent-prompt/swarm/logs/verdicts.json"))
h = httpx.Client(base_url="https://shim.teleionlabs.com", timeout=30, headers={"User-Agent": "teleion-assembler/1"})
for key, x in v.items():
    if x["verdict"] not in ("CONFIRMED", "REFUTED"):
        continue
    try:
        task_id = h.get(f"/q/object/{key}").json().get("source_task_id")
    except Exception:
        task_id = None
    if not task_id:
        miss += 1
        continue
    add(task_id, "opencode", "muse-spark-1.3-contributor", {"pass": x["verdict"] == "CONFIRMED", "usd": 0.03, "needs_people": False}, "swarm")

with open("records/memory.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(len(rows), "seed rows; no Task text for", miss)
