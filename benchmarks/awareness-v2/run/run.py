#!/usr/bin/env python3
"""Runs the arms over the questions in a fixed random order. usage: run.py QUESTIONS OUT ATTEMPTS ARM:RUNS ... """
import json, random, sys, concurrent.futures as cf
from pathlib import Path
import common2 as c
qfile, out, attempts = sys.argv[1], c.REC / sys.argv[2], sys.argv[3]
c.set_attempts(attempts)
plan = [a.split(":") for a in sys.argv[4:]]
Q = json.load(open(qfile))
done = set()
if out.exists():
    for l in out.open():
        d = json.loads(l); done.add((d["id"], d["arm"], d["run"]))
work = [(q, a, r) for q in Q for a, n in plan for r in range(int(n)) if (q["id"], a, r) not in done]
random.Random(20261104).shuffle(work)
print("work", len(work), flush=True)
stop = []
def one(w):
    q, a, r = w
    if stop: return None
    try: res = c.run_one(q, a, r)
    except c.Stop as e:
        stop.append(str(e)); return {"id": q["id"], "arm": a, "run": r, "stopped": str(e)}
    return {"id": q["id"], "arm": a, "run": r, **res}
with cf.ThreadPoolExecutor(12) as ex:
    for i, res in enumerate(ex.map(one, work)):
        if res is None: continue
        if "stopped" in res:
            with (c.REC / "stopped.jsonl").open("a") as f: f.write(json.dumps(res) + "\n")
            print("STOP", res, flush=True); continue
        with out.open("a") as f: f.write(json.dumps(res, ensure_ascii=False) + "\n")
        if i % 20 == 0: print(i, res["id"], res["arm"], res["run"], str(res["final"])[:60].replace("\n", " "), res["prompt_tokens"] + res["completion_tokens"], "spent", round(c.spent(), 3), flush=True)
print("spent", round(c.spent(), 3))
