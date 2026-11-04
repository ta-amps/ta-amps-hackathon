#!/usr/bin/env python3
"""Held-out comparison and the pre-registered gate. Usage: final.py <variant>. Writes records/results.json."""
import json, sys, collections
from pathlib import Path
src = (Path(__file__).parent / "score.py").read_text().split("if __name__")[0].replace("Path(__file__)", f"Path({str(Path(__file__).parent / 'score.py')!r})")
exec(src)
v = sys.argv[1]; rows = json.load(open(H / "records/held-rows.json"))["rows"]; thr = json.load(open(H / "records/plain-threshold.json"))["threshold"]
ORCH_THR = 0.25
arms = {}
arms["always_none"] = {r["id"]: ("none", None) for r in rows}
arms["plain_code"] = {r["id"]: plain_answer(r, ORCH_THR if r["set"] == "orchestrator_holdout" else thr) for r in rows}
res = {}; per = {}; secs = {}
def add(name, path):
    a, s = load_answers(path, rows); arms[name] = a; secs[name] = s
add("current_adapter", H / "records/answers-held-none-fix.json"); add("new_adapter", H / f"records/answers-held-{v}.json"); add("baseten_open", H / "records/baseten-rows.jsonl")
for n, a in arms.items():
    res[n], per[n] = table(rows, a)
    res[n]["outcomes_panel"] = dict(collections.Counter(a.get(r["id"], ("invalid",))[0] for r in rows if r["set"] == "panel_held"))
    if n in secs and secs[n]: res[n]["median_seconds"] = secs[n][len(secs[n]) // 2]
sets = {"panel_held", "held_refs", "orchestrator_holdout"}
ids = {s: {r["id"] for r in rows if r["set"] == s} for s in sets}
cmp = {}
for s in sets:
    for other in ("current_adapter", "plain_code", "always_none", "baseten_open"):
        A = {i: per["new_adapter"][i] for i in per["new_adapter"] if i in ids[s]}; B = {i: per[other][i] for i in per[other] if i in ids[s]}
        if A and B and set(A) & set(B): cmp[f"{s}: new vs {other}"] = paired(A, B)
    A = {i: per["current_adapter"][i] for i in per["current_adapter"] if i in ids[s]}; B = {i: per["plain_code"][i] for i in per["plain_code"] if i in ids[s]}
    if A and B: cmp[f"{s}: current vs plain_code"] = paired(A, B)
P = {n: res[n].get("panel_held", {}) for n in arms}
acc = lambda n: P[n].get("correct", 0) / max(1, P[n].get("n", 0))
new, cur = P["new_adapter"], P["current_adapter"]
primary = cmp["panel_held: new vs current_adapter"]
orch_new, orch_cur = res["new_adapter"]["orchestrator_holdout"], res["current_adapter"]["orchestrator_holdout"]
gate = {
 "lower_bound_above_zero_vs_current": primary["ci95"][0] > 0,
 "at_least_plain_and_always_none": acc("new_adapter") >= acc("plain_code") and acc("new_adapter") >= acc("always_none"),
 "false_picks_at_most_20pct_of_picks": new.get("false_pick", 0) <= .2 * max(1, new.get("pick", 0)),
 "five_more_right_picks_than_current": new.get("right_pick", 0) >= cur.get("right_pick", 0) + 5,
 "orchestrator_not_5_points_below_current": orch_new.get("correct", 0) / orch_new.get("n", 1) >= orch_cur.get("correct", 0) / orch_cur.get("n", 1) - .05,
}
gate_pass = all(gate.values())
# search: scored with search-eval's own rule
R = N / "work-2026-11-03/search-eval"
qs = {q["qid"]: q for q in L(H / "snapshot/heldout.jsonl")}
objs = {o["k"]: ((o["k"] + " " + (o["s"] or "")).lower()) for o in json.load(open(R / "corpus/objects-raw.json"))[0]["results"]}
feed = collections.defaultdict(set)
for r_ in json.load(open(R / "corpus/repos-raw.json"))[0]["results"]: feed[r_["repo"]].add(r_["feed"])
judg = {}
for l_ in open(H / "snapshot/judgments.jsonl"):
    j = json.loads(l_); judg[(j["q"], j["id"])] = j["relevant"]
def hit(q, i):
    if q.get("judged"): return judg.get((q["q"], i))
    for a in q["accept"]:
        k, _, val = a.partition(":")
        if a.lower() == i.lower(): return True
        if k == "owner" and i.lower().startswith(f"repo:{val.lower()}/"): return True
        if k == "feed" and i.startswith("repo:") and val in feed.get(i[5:], ()): return True
        if k == "objprefix" and i.startswith("obj:") and i[4:].startswith(val): return True
        if k == "objterm" and i.startswith("obj:") and val.lower() in objs.get(i[4:], ""): return True
    return False
search = {}
srows = [r for r in rows if r["set"] == "search_held"]
for n in ("current_adapter", "new_adapter"):
    a = arms[n]; c = dict(n=0, default_right=0, model_right=0, model_right_fallback=0, moved_to_right=0, moved_to_wrong=0, said_none=0, none_row_said_none=0, none_rows=0)
    for r in srows:
        q = qs[r["id"][2:]]; o, p = a.get(r["id"], ("invalid", None)); top = r["candidates"][0]
        if q.get("expect_none"): c["none_rows"] += 1; c["none_row_said_none"] += o == "none"; continue
        judgedq = q.get("judged")
        if judgedq and judg.get((q["q"], top)) is None: continue
        c["n"] += 1; dr = bool(hit(q, top)); c["default_right"] += dr; c["said_none"] += o == "none"
        mr = o == "pick" and bool(hit(q, p)); c["model_right"] += mr; fb = bool(hit(q, p if o == "pick" else top)); c["model_right_fallback"] += fb
        c["moved_to_right"] += fb and not dr; c["moved_to_wrong"] += dr and not fb
    search[n] = c
g = lambda name: json.load(open(H / f"records/answers-held-{name}.json"))
cost = {n: {k: g(n).get(k) for k in ("load_s", "wall_s", "usd_estimate", "adapter_sha256")} for n in ("none-fix", v)}
base = {r["id"]: r for r in L(H / "records/baseten-rows.jsonl")}
pid = ids["panel_held"]; cost["baseten_open_panel_usd"] = round(sum(base[i].get("usd", 0) for i in pid if i in base), 4)
out = {"variant": v, "panel_gold": {k: P["plain_code"].get("gold_" + k, 0) for k in ("fit", "none", "disagree", "missing")}, "arms": res, "paired": cmp, "wilson_acc_panel": {n: wilson(P[n].get("correct", 0), P[n].get("n", 0)) for n in arms}, "search_held": search, "cost": cost, "gate": gate, "gate_pass": gate_pass}
(H / "records/results.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("panel_gold", "paired", "wilson_acc_panel", "search_held", "cost", "gate", "gate_pass")}, indent=1))
for n in arms: print(n, {s: {k: res[n].get(s, {}).get(k) for k in ("n", "correct", "pick", "right_pick", "false_pick", "missed", "invalid")} for s in sets}, res[n].get("median_seconds"), res[n].get("outcomes_panel"))
