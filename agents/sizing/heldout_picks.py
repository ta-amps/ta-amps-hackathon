"""The auto-replace test for the Task Object pick. Same held-out rows, no training data shared with the fine-tune's checker.
Plain code: BM25 over the candidate list, with a no-fit threshold set on the dev split only. Then the Meta open model on Baseten, the live default route, if asked."""
import json, math, re, sys, collections, time
import os
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = Path(os.environ.get("SIZING_HOLDOUT_DATA", "/nonexistent"))
W = re.compile(r"[a-z][a-z0-9]+")
STOP = frozenset("the and for with from this that our your you are not its use used takes gives need input side pin pins".split())
def toks(s): return [w for w in W.findall(s.lower()) if w not in STOP]
def parts(r):
    u = r["messages"][1]["content"]; need = u.split("Candidates:")[0]
    lines = [l for l in u.split("Candidates:")[1].splitlines() if re.match(r"\d+\. ", l)]
    return need, [(l.split(". ", 1)[1].split(" | ")[0], l.split(" | ", 1)[1] if " | " in l else l) for l in lines]
def score(r):
    need, cands = parts(r); docs = [(i, toks(t)) for i, t in cands]
    df = collections.Counter(t for _, d in docs for t in set(d)); N = len(docs) or 1; avg = sum(len(d) for _, d in docs) / N or 1
    q = set(toks(need)); out = []
    for i, d in docs:
        tf = collections.Counter(d)
        s = sum(math.log(1 + (N - df[t] + .5) / (df[t] + .5)) * tf[t] * 2.2 / (tf[t] + 1.2 * (.25 + .75 * len(d) / avg)) for t in q if t in tf)
        out.append((s / max(1, len(q)), i))
    out.sort(reverse=True); return out
def load(name): return [json.loads(l) for l in (DATA / name).read_text().splitlines()]
def is_none(r): return bool(r["meta"].get("none_case")) or not r["meta"].get("gold_id")
def evaluate(rows, thr):
    fit = hit = none = none_ok = false_none = 0; per = []
    for r in rows:
        s = score(r); pick = s[0][1] if s and s[0][0] >= thr else None
        if is_none(r): none += 1; none_ok += pick is None
        else: fit += 1; hit += pick == r["meta"]["gold_id"]; false_none += pick is None
        per.append({"id": r["id"], "pick": pick})
    return {"fit_rows": fit, "top_pick_hit": hit, "none_rows": none, "none_right": none_ok, "fit_called_none": false_none}, per
dev = [r for r in load("dev.jsonl") if r["meta"].get("role") == "retrieval"]
held = load("holdout-retrieval.jsonl")
print("dev retrieval rows", len(dev), "none", sum(is_none(r) for r in dev))
best = max((evaluate(dev, t / 100)[0]["top_pick_hit"] + evaluate(dev, t / 100)[0]["none_right"], -t, t / 100) for t in range(0, 300, 5))
thr = best[2]
res, per = evaluate(held, thr)
print(json.dumps({"threshold_from_dev": thr, "held_out": res, "no_threshold": evaluate(held, 0.0)[0]}, indent=1))
out = {"plain_bm25": {"threshold_from_dev": thr, **res}}
if "--baseten" in sys.argv:
    sys.path[:0] = [str(REPO / "agents/warm-server-agent/src"), str(REPO / "agents/live-decider")]
    import decider as dec
    from warm_agent.decider import partner_settings, reserve, settle
    from warm_agent.grid_config import load_warm_agent_grid
    import httpx
    env = partner_settings(); cfg = load_warm_agent_grid(None).section("decider_routes")
    fit = hit = none = none_ok = bad = 0; usd = 0.0; rows_out = []
    with httpx.Client(timeout=30, trust_env=False) as h:
        for r in held:
            cands = [{"id": c} for c in r["meta"]["candidate_ids"]]
            rid = reserve(HERE / "spend.jsonl", 0.02, 4.5, "held-out pick, Meta open model on Baseten")
            try:
                resp = h.post(env["BASETEN_BASE_URL"], headers={"Authorization": "Bearer " + env["BASETEN_API_KEY"]}, json={"model": env["BASETEN_MODEL_ID"], "temperature": 0.0, "max_tokens": 2000, "reasoning_effort": "low", "messages": r["messages"][:2]})
                body = resp.json(); u = body.get("usage") or {}
                c = u.get("prompt_tokens", 0) / 1e6 * .25 + u.get("completion_tokens", 0) / 1e6 * 1.0
                usd += c; settle(HERE / "spend.jsonl", rid, c, "held-out pick, Baseten, list-rate estimate")
                got = dec.parse_answer(body["choices"][0]["message"].get("content"), cands)
            except Exception as exc:
                settle(HERE / "spend.jsonl", rid, 0.02, "held-out pick, Baseten, failed, hold kept"); got = {"outcome": "invalid", "why": type(exc).__name__}
            rows_out.append({"id": r["id"], **got})
            if got["outcome"] == "invalid": bad += 1
            if is_none(r): none += 1; none_ok += got["outcome"] == "no_fit"
            else: fit += 1; hit += got.get("object_id") == r["meta"]["gold_id"]
    out["baseten_open_model"] = {"fit_rows": fit, "top_pick_hit": hit, "none_rows": none, "none_right": none_ok, "unreadable": bad, "usd_estimate": round(usd, 4), "model": env["BASETEN_MODEL_ID"]}
    (HERE / "records/heldout-baseten-rows.jsonl").write_text("\n".join(json.dumps(x) for x in rows_out))
    print(json.dumps(out["baseten_open_model"], indent=1))
(HERE / "records/heldout-picks.json").write_text(json.dumps(out, indent=1))
