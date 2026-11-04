#!/usr/bin/env python3
import os
"""Score answers. Usage: score.py <rows.json> <answers name=path ...>. Panel gold from two readers; disagreements counted, not scored."""
import collections, json, math, random, re, sys
from pathlib import Path
H = Path(__file__).resolve().parents[1]; N = H.parents[1]
sys.path[:0] = [str(N / "work-2026-11-03/meta-live")]
L = lambda p: [json.loads(x) for x in open(p)]
def parse(text, cands):
    if not isinstance(text, str): return "invalid", None
    m = re.search(r"\{.*\}", text, re.S)
    try: ranked = json.loads(m.group(0) if m else text)["ranked"]
    except Exception: return "invalid", None
    if not isinstance(ranked, list): return "invalid", None
    if not ranked: return "none", None
    if not all(isinstance(x, str) and x in cands for x in ranked): return "invalid", None
    return "pick", ranked[0]
# gold -----------------------------------------------------------------------------------------------------------------
judged = collections.defaultdict(dict)
for j in L(H / "records/panel-judgments.jsonl"):
    if j.get("helps") is not None: judged[j["id"]][j["judge"]] = j["helps"]
JJ = ("muse-wonder-1.0", os.environ["PANEL_SECOND_READER"])
def panel_gold(rid):
    d = judged.get(rid, {})
    if len(d) < 2: return {"kind": "missing"}
    a, b = set(d[JJ[0]]), set(d[JJ[1]])
    if not a and not b: return {"kind": "none", "union": set()}
    if a & b: return {"kind": "fit", "ok": a & b, "union": a | b}
    return {"kind": "disagree", "union": a | b}
gref = {r["id"]: r["gold"] for r in L(H / "data/held_refs.jsonl")}; gref.update({r["id"]: r["gold"] for r in L(H / "data/dev.jsonl")})
orch = {r["id"]: r["meta"] for r in L(N / "claude-work-2026-10-31/glimmer-orchestrator/data/orchestrator-v1/holdout-retrieval.jsonl")}
def gold(row):
    s = row["set"]
    if s in ("panel_held", "panel_dev"): return panel_gold(row["id"])
    if s in ("held_refs", "dev"):
        g = gref[row["id"]]; return {"kind": "fit", "ok": set(g), "union": set(g)} if g else {"kind": "none", "union": set()}
    if s == "orchestrator_holdout":
        m = orch[row["id"]]; return {"kind": "fit", "ok": {m["gold_id"]}, "union": {m["gold_id"]}} if m.get("gold_id") and not m.get("none_case") else {"kind": "none", "union": set()}
    return {"kind": "search"}
# plain code -----------------------------------------------------------------------------------------------------------
W = re.compile(r"[a-z][a-z0-9]+"); STOP = frozenset("the and for with from this that our your you are not its use used takes gives need input side pin pins".split())
toks = lambda s: [w for w in W.findall(s.lower()) if w not in STOP]
def plain_scores(msg):
    u = msg[1]["content"]; need, rest = u.split("Candidates:", 1); lines = [l for l in rest.splitlines() if re.match(r"\d+\. ", l)]
    cs = [(l.split(". ", 1)[1].split(" | ")[0], l.split(" | ", 1)[1] if " | " in l else l) for l in lines]; docs = [(i, toks(t)) for i, t in cs]
    df = collections.Counter(t for _, d in docs for t in set(d)); n = len(docs) or 1; avg = sum(len(d) for _, d in docs) / n or 1; q = set(toks(need)); out = []
    for i, d in docs:
        tf = collections.Counter(d); s = sum(math.log(1 + (n - df[t] + .5) / (df[t] + .5)) * tf[t] * 2.2 / (tf[t] + 1.2 * (.25 + .75 * len(d) / avg)) for t in q if t in tf)
        out.append((s / max(1, len(q)), i))
    return sorted(out, reverse=True)
def plain_answer(row, thr):
    s = plain_scores(row["messages"]); return ("pick", s[0][1]) if s and s[0][0] >= thr else ("none", None)
def judge_row(g, o, p):
    """correct, false_pick, missed, right_pick"""
    k = g["kind"]
    if k == "fit":
        return {"correct": o == "pick" and p in g["ok"], "false_pick": o == "pick" and p not in g["union"], "missed": o != "pick", "right_pick": o == "pick" and p in g["ok"], "pick": o == "pick"}
    if k == "none":
        return {"correct": o == "none", "false_pick": o == "pick", "missed": False, "right_pick": False, "pick": o == "pick"}
    return None
def table(rows, ans):
    """ans: id -> (outcome, pick). Returns per-set counts and per-row correct."""
    res = collections.defaultdict(lambda: collections.Counter()); per = {}
    for r in rows:
        g = gold(r)
        res[r["set"]]["gold_" + g["kind"]] += 1
        if g["kind"] in ("missing", "disagree", "search"): continue
        o, p = ans.get(r["id"], ("invalid", None)); j = judge_row(g, o, p)
        c = res[r["set"]]; c["n"] += 1; c["invalid"] += o == "invalid"
        for k, v in j.items(): c[k] += bool(v)
        per[r["id"]] = bool(j["correct"])
    return {k: dict(v) for k, v in res.items()}, per
def load_answers(path, rows):
    cand = {r["id"]: r["candidates"] for r in rows}; d = {}; secs = []
    src = json.load(open(path))["rows"] if str(path).endswith(".json") else L(path)
    for a in src:
        if a["id"] in cand:
            d[a["id"]] = parse(a.get("text"), set(cand[a["id"]])); 
            if a.get("seconds"): secs.append(a["seconds"])
    return d, sorted(secs)
def paired(a, b, seed=11):
    ids = sorted(set(a) & set(b)); only_a = sum(a[i] and not b[i] for i in ids); only_b = sum(b[i] and not a[i] for i in ids); n = len(ids)
    rng = random.Random(seed); diffs = sorted(sum((a[i] - b[i]) for i in rng.choices(ids, k=n)) / n for _ in range(5000))
    m = only_a + only_b; p = min(1.0, 2 * sum(math.comb(m, k) for k in range(0, min(only_a, only_b) + 1)) / 2 ** m) if m else 1.0
    return {"n": n, "only_first_right": only_a, "only_second_right": only_b, "diff": round((only_a - only_b) / n, 4) if n else None, "ci95": [round(diffs[125], 4), round(diffs[4875], 4)], "mcnemar_p": round(p, 5)}
def wilson(k, n, z=1.96):
    if not n: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
if __name__ == "__main__":
    rows = json.load(open(sys.argv[1]))["rows"]; arms = dict(a.split("=", 1) for a in sys.argv[2:])
    thr = float(json.load(open(H / "records/plain-threshold.json"))["threshold"]) if (H / "records/plain-threshold.json").exists() else 0.25
    out = {"always_none": table(rows, {r["id"]: ("none", None) for r in rows})[0], f"plain_code_thr_{thr}": table(rows, {r["id"]: plain_answer(r, thr) for r in rows})[0]}
    pers = {}
    for name, p in arms.items():
        ans, secs = load_answers(p, rows); out[name], pers[name] = table(rows, ans); out[name]["seconds_median"] = secs[len(secs) // 2] if secs else None
    print(json.dumps(out, indent=1))
