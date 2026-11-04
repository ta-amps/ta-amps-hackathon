#!/usr/bin/env python3
"""Collect a held-out answer call by id if given; otherwise spawn it anew and print the id at once. Usage: get_or_rerun.py <adapter> <set> [call_id]"""
import json, sys, time
from pathlib import Path
import modal
H = Path(__file__).resolve().parents[1]; a, s = sys.argv[1], sys.argv[2]
if len(sys.argv) > 3:
    call = modal.FunctionCall.from_id(sys.argv[3])
else:
    rows = json.load(open(H / f"records/{s}-rows.json"))["rows"]
    call = modal.Function.from_name("glimmer-pick-v2", "answer").spawn(a, rows)
open(H / "records/calls.log", "a").write(f"{time.strftime('%FT%TZ', time.gmtime())} {a} {s} {call.object_id}\n"); print("call", call.object_id, flush=True)
t = time.time(); res = None
for i in range(6):
    try:
        res = call.get(timeout=1200); break
    except Exception as e:
        print("retry", type(e).__name__, flush=True); time.sleep(15)
if res is None:
    open(H / "records/answer-failures.jsonl", "a").write(json.dumps({"adapter": a, "set": s, "call": call.object_id}) + "\n"); sys.exit(1)
res["client_wall_s"] = round(time.time() - t, 1); (H / f"records/answers-{s}-{a}.json").write_text(json.dumps(res))
print(json.dumps({k: res[k] for k in res if k != "rows"}))
