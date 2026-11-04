#!/usr/bin/env python3
"""Answer files. dev-rows.json goes to every variant; held-rows.json runs once, on the chosen variant and the current adapter."""
import json
from pathlib import Path
H = Path(__file__).resolve().parents[1]; N = H.parents[1]
L = lambda p: [json.loads(x) for x in open(p)]
src = (N / "work-2026-11-03/meta-live/decider.py").read_text(); i, j = src.index("SYSTEM = ("), src.index("MODEL_RECORD"); exec(src[i:j])
panel = L(H / "data/panel.jsonl"); dev = L(H / "data/dev.jsonl"); refs = L(H / "data/held_refs.jsonl")
def slim(r, s): return {"id": r["id"], "set": s, "candidates": r.get("candidates"), "messages": r["messages"][:2]}
devrows = [slim(r, "dev") for r in dev] + [slim(r, "panel_dev") for r in panel if r["split"] == "panel_dev"]
held = [slim(r, "held_refs") for r in refs] + [slim(r, "panel_held") for r in panel if r["split"] == "panel_held"]
for r in L(N / "claude-work-2026-10-31/glimmer-orchestrator/data/orchestrator-v1/holdout-retrieval.jsonl"):
    held.append({"id": r["id"], "set": "orchestrator_holdout", "candidates": r["meta"]["candidate_ids"], "messages": r["messages"][:2]})
qs = {q["qid"]: q for q in L(H / "snapshot/heldout.jsonl")}
for c in L(H / "snapshot/cands-off-heldout.jsonl"):
    if len(c["cands"]) < 2 or c["match"] != "words": continue
    lines = [f"{n}. {x['ref']} | {x['title']}. {x['about']}" for n, x in enumerate(c["cands"], 1)]
    held.append({"id": "s-" + c["qid"], "set": "search_held", "candidates": [x["ref"] for x in c["cands"]], "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Need: {qs[c['qid']]['q']}\n\nCandidates:\n" + "\n".join(lines)}]})
(H / "records/dev-rows.json").write_text(json.dumps({"rows": devrows})); (H / "records/held-rows.json").write_text(json.dumps({"rows": held}))
import collections; print(collections.Counter(r["set"] for r in devrows), collections.Counter(r["set"] for r in held))
