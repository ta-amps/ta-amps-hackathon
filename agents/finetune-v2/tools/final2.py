#!/usr/bin/env python3
"""Test 2: fresh live-shape Tasks. Registered gate in records/preregistration-2.json. Writes records/results-2.json."""
import json, collections
from pathlib import Path
src = (Path(__file__).parent / "score.py").read_text().split("if __name__")[0].replace("Path(__file__)", f"Path({str(Path(__file__).parent / 'score.py')!r})").replace('records/panel-judgments.jsonl', 'records/panel2-judgments.jsonl')
exec(src)
rows = json.load(open(H / "records/test2-rows.json"))["rows"]; thr = json.load(open(H / "records/plain-threshold.json"))["threshold"]
arms = {"always_none": {r["id"]: ("none", None) for r in rows}, "plain_code": {r["id"]: plain_answer(r, thr) for r in rows}}
secs = {}
for n, p in (("current_adapter", "records/answers-test2-none-fix.json"), ("new_adapter", "records/answers-test2-a.json"), ("baseten_open", "records/baseten2-rows.jsonl")):
    arms[n], secs[n] = load_answers(H / p, rows)
res, per = {}, {}
for n, a in arms.items():
    t, per[n] = table(rows, a); res[n] = t.get("panel_held", {})
    res[n]["outcomes"] = dict(collections.Counter(a.get(r["id"], ("invalid",))[0] for r in rows))
    if secs.get(n): res[n]["median_seconds"] = secs[n][len(secs[n]) // 2]
cmp = {f"new vs {o}": paired(per["new_adapter"], per[o]) for o in ("current_adapter", "baseten_open", "plain_code", "always_none")}
new, cur = res["new_adapter"], res["current_adapter"]
gate = {"lower_bound_above_zero_vs_current": cmp["new vs current_adapter"]["ci95"][0] > 0, "lower_bound_above_zero_vs_baseten": cmp["new vs baseten_open"]["ci95"][0] > 0,
        "plain_code_margin_10_points": cmp["new vs plain_code"]["ci95"][0] > -0.10, "false_picks_at_most_20pct": new.get("false_pick", 0) <= .2 * max(1, new.get("pick", 0)), "five_more_right_picks_than_current": new.get("right_pick", 0) >= cur.get("right_pick", 0) + 5}
cost = {n: {k: json.load(open(H / f"records/answers-test2-{n}.json")).get(k) for k in ("load_s", "wall_s", "usd_estimate", "adapter_sha256")} for n in ("none-fix", "a")}
b = L(H / "records/baseten2-rows.jsonl"); cost["baseten_usd"] = round(sum(x.get("usd", 0) for x in b), 4)
J = L(H / "records/panel2-judgments.jsonl"); cost["readers_usd"] = {j: round(sum(x["usd"] for x in J if x["judge"] == j), 3) for j in JJ}
out = {"rows": len(rows), "arms": res, "wilson": {n: wilson(res[n].get("correct", 0), res[n].get("n", 0)) for n in res}, "paired": cmp, "gate": gate, "gate_pass": all(gate.values()), "cost": cost}
(H / "records/results-2.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=0))
