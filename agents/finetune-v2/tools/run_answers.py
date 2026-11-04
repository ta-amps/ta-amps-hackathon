#!/usr/bin/env python3
"""answers from a deployed adapter into records/answers-<set>-<adapter>.json. Usage: run_answers.py <adapter> <dev|held>. Detached call, saved on arrival; failures recorded."""
import json, os, sys, time
from pathlib import Path
import modal
H = Path(__file__).resolve().parents[1]; a, s = sys.argv[1], sys.argv[2]
rows = json.load(open(H / f"records/{s}-rows.json"))["rows"]
call = modal.Function.from_name("glimmer-pick-v2", "answer").spawn(a, rows)
print("call", call.object_id, flush=True); t = time.time()
for i in range(4):
    try:
        res = call.get(timeout=2900); break
    except Exception as e:
        print("retry", type(e).__name__, flush=True); time.sleep(20); res = None
if res is None:
    open(H / "records/answer-failures.jsonl", "a").write(json.dumps({"adapter": a, "set": s, "call": call.object_id}) + "\n"); sys.exit(1)
res["client_wall_s"] = round(time.time() - t, 1); (H / f"records/answers-{s}-{a}.json").write_text(json.dumps(res))
print(json.dumps({k: res[k] for k in res if k != "rows"}))
