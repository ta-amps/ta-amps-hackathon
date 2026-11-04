#!/usr/bin/env python3
"""Scores every run and writes records/results.json. Answers checked against GitHub. Item bootstrap, 10,000 resamples, seed 99."""
import json, random, re, sys, statistics as st
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import scorer as sc
ROOT = Path(__file__).resolve().parent.parent
Q = {q["id"]: q for q in json.load(open(ROOT / "prereg/questions.json"))}
rows = [json.loads(l) for l in open(ROOT / "records/runs.jsonl")]
def score_multi(q, final):
    t = sc.answer_text(final)
    names = []
    for m in re.findall(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", t):
        m = m.removesuffix(".git").rstrip(".")
        if m.lower() not in [n.lower() for n in names]: names.append(m)
    if not names: return ("unknown", "no names") if sc.is_unknown(t) else ("wrong", "no names")
    good = []
    tr = q["truth"]
    for n in names[:3]:
        v = sc.score({"group": "primary", "kind": "discovery", "truth": tr}, n)
        if v[0] == "correct": good.append(n)
    return ("correct", ",".join(good)) if len(good) == 3 else ("wrong", f"{len(good)} of 3 fit: " + ",".join(names[:3]))
for r in rows:
    q = Q[r["id"]]
    o, d = score_multi(q, r.get("final")) if q["kind"] == "multi" else sc.score(q, r.get("final"))
    r["outcome"], r["detail"] = o, d
    r["tokens"] = r["prompt_tokens"] + r["completion_tokens"]
json.dump(rows, open(ROOT / "records/scored.json", "w"), ensure_ascii=False)
GROUPS = {"primary": ["primary"], "on_page": None, "deep": None, "fresh": ["fresh"], "low_star_unindexed": ["low_star_unindexed"], "not_on_feed": ["not_on_feed"], "invented": ["invented"], "multi_discovery": ["multi_discovery"], "any_real_repo": ["primary", "fresh", "low_star_unindexed", "not_on_feed"]}
def ids(g):
    if g in ("on_page", "deep"): return [q["id"] for q in Q.values() if q.get("stratum") == g]
    return [q["id"] for q in Q.values() if q["group"] in GROUPS[g]]
by = defaultdict(list)
for r in rows: by[(r["arm"], r["id"])].append(r)
ARMS = sorted({r["arm"] for r in rows})
def item_stats(arm, i):
    rs = by.get((arm, i), [])
    return (sum(r["outcome"] == "correct" for r in rs), sum(r["tokens"] for r in rs), sum(r["seconds"] for r in rs), len(rs))
def boot(fn, items, n=10000, seed=99):
    rng = random.Random(seed); vals = []
    for _ in range(n):
        s = [rng.choice(items) for _ in items]; v = fn(s)
        if v is not None: vals.append(v)
    vals.sort()
    return (round(vals[int(.025 * len(vals))], 3), round(vals[int(.975 * len(vals)) - 1], 3)) if vals else None
out = {"arms": ARMS, "groups": {}}
def arm_summary(arm, items):
    S = [item_stats(arm, i) for i in items]; k, t, s, n = (sum(x[j] for x in S) for j in range(4))
    if not n: return None
    table = dict(zip(items, S))
    rs = [r for i in items for r in by.get((arm, i), [])]
    return {"runs": n, "items": len(items), "correct": k, "pct_correct": round(100 * k / n, 1),
            "pct_ci": [round(100 * x, 1) for x in boot(lambda it: (sum(table[i][0] for i in it) / max(1, sum(table[i][3] for i in it))), items)],
            "wrong": sum(r["outcome"] == "wrong" for r in rs), "unknown": sum(r["outcome"] == "unknown" for r in rs),
            "tokens_per_run": round(t / n), "total_tokens": t, "tokens_per_correct": round(t / k) if k else None,
            "tokens_per_correct_ci": boot(lambda it: (sum(table[i][1] for i in it) / sum(table[i][0] for i in it)) if sum(table[i][0] for i in it) else None, items),
            "seconds_per_run": round(s / n, 1), "model_calls_per_run": round(sum(r["calls"] for r in rs) / n, 2), "tool_calls_per_run": round(sum(len(r["tools"]) for r in rs) / n, 2),
            "tool_chars_per_run": round(sum(t2["result_chars"] for r in rs for t2 in r["tools"]) / n), "direct_share": round(sum(bool(r.get("direct")) for r in rs) / n, 3)}
def pair(a, b, items):
    A = {i: item_stats(a, i) for i in items}; B = {i: item_stats(b, i) for i in items}
    items2 = [i for i in items if A[i][3] and B[i][3]]
    if not items2: return None
    rate = lambda T, it: sum(T[i][0] for i in it) / sum(T[i][3] for i in it)
    tok = lambda T, it: sum(T[i][1] / T[i][3] for i in it)
    tpc = lambda T, it: (sum(T[i][1] for i in it) / sum(T[i][0] for i in it)) if sum(T[i][0] for i in it) else None
    def tpc_ratio(it):
        x, y = tpc(A, it), tpc(B, it)
        return x / y if x is not None and y else None
    mean = lambda T, i: T[i][0] / T[i][3]
    wins = sum(mean(A, i) > mean(B, i) for i in items2); losses = sum(mean(A, i) < mean(B, i) for i in items2)
    from math import comb
    n = wins + losses; p = min(1, 2 * sum(comb(n, k) for k in range(0, min(wins, losses) + 1)) / 2 ** n) if n else 1
    return {"items": len(items2), "total_token_ratio": round(tok(A, items2) / tok(B, items2), 3), "total_token_ratio_ci": boot(lambda it: tok(A, it) / tok(B, it), items2),
            "tokens_per_correct_ratio": round(tpc_ratio(items2), 3) if tpc_ratio(items2) else None, "tokens_per_correct_ratio_ci": boot(tpc_ratio, items2),
            "correct_points_difference": round(100 * (rate(A, items2) - rate(B, items2)), 1), "correct_points_ci": [round(100 * x, 1) for x in boot(lambda it: rate(A, it) - rate(B, it), items2)],
            "items_first_better": wins, "items_second_better": losses, "sign_test_p": round(p, 4),
            "seconds_ratio": round(sum(A[i][2] / A[i][3] for i in items2) / sum(B[i][2] / B[i][3] for i in items2), 3)}
for g in GROUPS:
    it = ids(g)
    if not it: continue
    out["groups"][g] = {"arms": {a: arm_summary(a, it) for a in ARMS}, "pairs": {f"{x} vs {y}": pair(x, y, it) for x, y in [("B", "C"), ("B", "C-raw"), ("B-cold", "C"), ("B-direct", "C"), ("B", "B-old"), ("B", "A")]}}
def miss_states(arm, it):
    c = defaultdict(int)
    for i in it:
        for r in by.get((arm, i), []):
            for t in r["tools"]:
                m = re.search(r'"miss":"([a-z_]+)"', t.get("reply_head", ""))
                if m: c[m.group(1)] += 1
    return dict(c)
out["read_through_misses_arm_B"] = {g: miss_states("B", ids(g)) for g in GROUPS if ids(g)}
out["read_through_misses_arm_B_direct"] = {g: miss_states("B-direct", ids(g)) for g in GROUPS if ids(g)}
out["failed_runs"] = sum(1 for r in rows if r.get("final") is None)
at = [json.loads(l) for l in open(ROOT / "records/attempts.jsonl")]
out["attempts"] = {"total": len(at), "non_200": sum(a["status"] != 200 for a in at), "missing_usage": sum(a["prompt_tokens"] is None for a in at), "finish_not_stop": sum(a["finish_reason"] not in ("stop", None) for a in at)}
sp = [json.loads(l) for l in open(ROOT / "records/spend.jsonl")]
out["spend_usd"] = round(sum(x.get("usd_est") or 0 for x in sp), 3)
json.dump(out, open(ROOT / "records/results.json", "w"), indent=1)
for g, d in out["groups"].items():
    print("==", g)
    for a, s in d["arms"].items():
        if s: print(f" {a:9} {s['correct']}/{s['runs']} {s['pct_correct']}% CI{s['pct_ci']} wrong {s['wrong']} unk {s['unknown']} tok/run {s['tokens_per_run']} total {s['total_tokens']} tok/correct {s['tokens_per_correct']} CI{s['tokens_per_correct_ci']} sec {s['seconds_per_run']} calls {s['model_calls_per_run']} tools {s['tool_calls_per_run']} chars {s['tool_chars_per_run']} direct {s['direct_share']}")
    for k, p in d["pairs"].items():
        if p: print(f"   {k}: tok ratio {p['total_token_ratio']} CI{p['total_token_ratio_ci']} tok/correct ratio {p['tokens_per_correct_ratio']} CI{p['tokens_per_correct_ratio_ci']} points {p['correct_points_difference']} CI{p['correct_points_ci']} better {p['items_first_better']}/{p['items_second_better']} p={p['sign_test_p']} sec ratio {p['seconds_ratio']}")
print({k: out[k] for k in ("failed_runs", "attempts", "spend_usd", "read_through_misses_arm_B", "read_through_misses_arm_B_direct")})
