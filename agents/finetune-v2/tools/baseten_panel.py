#!/usr/bin/env python3
"""The live non-fine-tuned route: Muse Spark Open on Baseten, same prompt, same settings as sizing/heldout_picks.py. Every answer recorded, unreadable ones too."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
H = Path(__file__).resolve().parents[1]; N = H.parents[1]; LEDGER = N / "coordination-2026-10-31/compute-ledger.jsonl"
sys.path[:0] = [str(N / "work-2026-11-02/warm-server-agent/src")]
from warm_agent.decider import partner_settings
import httpx
env = partner_settings()
rows = json.load(open(H / "records/dev-rows.json"))["rows"] + [r for r in json.load(open(H / "records/held-rows.json"))["rows"] if r["set"] in ("panel_held", "held_refs")]
out = H / "records/baseten-rows.jsonl"
def go(r):
    t = time.time(); rec = {"id": r["id"], "set": r["set"]}
    with httpx.Client(timeout=60, trust_env=False) as h:
        try:
            resp = h.post(env["BASETEN_BASE_URL"], headers={"Authorization": "Bearer " + env["BASETEN_API_KEY"]}, json={"model": env["BASETEN_MODEL_ID"], "temperature": 0.0, "max_tokens": 2000, "reasoning_effort": "low", "messages": r["messages"]})
            b = resp.json(); u = b.get("usage") or {}; c = u.get("prompt_tokens", 0) / 1e6 * .25 + u.get("completion_tokens", 0) / 1e6
            rec.update(status=resp.status_code, text=b["choices"][0]["message"].get("content"), usd=c, seconds=round(time.time() - t, 2))
        except Exception as e:
            rec.update(error=type(e).__name__, usd=0, seconds=round(time.time() - t, 2))
    return rec
with ThreadPoolExecutor(4) as ex, out.open("w") as f:
    for rec in ex.map(go, rows):
        f.write(json.dumps(rec) + "\n"); f.flush()
print(len(rows), "usd", round(sum(json.loads(l).get("usd", 0) for l in open(out)), 4))
