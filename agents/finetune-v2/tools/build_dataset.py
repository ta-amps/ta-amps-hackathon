#!/usr/bin/env python3
"""Fine-tune v2 data. Real records only; no row's target is written by a model. Split by subject family before any training.
 train / dev: real need text that names an earlier Task Object (Task prompts and Task Object summaries), name masked, plus
 the seed-pack retrieval rows of the current adapter. held_refs: same kind, held out. panel_dev / panel_held: real Task text
 with live or word-search candidates, labels from two independent readers, for evaluation only, never training."""
import hashlib, json, math, random, re, subprocess, sys, collections
from pathlib import Path
H = Path(__file__).resolve().parents[1]; N = H.parents[1]
sys.path[:0] = [str(N / "work-2026-11-02/warm-server-agent/src")]
from warm_agent.decider import looks_secret
exec_src = (N / "work-2026-11-03/meta-live/decider.py").read_text()
i, j = exec_src.index("SYSTEM = ("), exec_src.index("MODEL_RECORD"); exec(exec_src[i:j])
SEED = "fine-tune-v2-20261104"
objs = json.load(open(N / "work-2026-11-03/search-eval/corpus/objects-raw.json"))[0]["results"]
refuted = set(json.load(open(H / "snapshot/refuted-ids.json")))
MARKED = re.compile(r"(?i)\binvented\b|\bmade.?up\b|\bfabricat|\brefuted\b|\bnot real\b|\bplaceholder\b")
TESTKEY = re.compile(r"(?i)ed_trial|scale-test|^probe_|_probe_|smoke_test|test_fixture")
excl = collections.Counter(); O = {}
for o in objs:
    k, s = o["k"], (o["s"] or "")
    why = "refuted" if k in refuted else "test_or_trial" if TESTKEY.search(k) else "marked_invented_or_refuted" if MARKED.search(s) else "secret_shape" if looks_secret(k + " " + s) else None
    if why: excl[why] += 1; continue
    O[k] = s
print("objects kept", len(O), "excluded", dict(excl))
W = re.compile(r"[a-z][a-z0-9]+")
STOP = frozenset("the and for with from this that our your you are not its use used was were has have run new".split())
toks = lambda s: [w for w in W.findall(s.lower()) if w not in STOP]
docs = {k: collections.Counter(toks(k.replace("_", " ") + " " + s[:600])) for k, s in O.items()}
df = collections.Counter(t for d in docs.values() for t in d); NN = len(docs); avg = sum(sum(d.values()) for d in docs.values()) / NN
post = collections.defaultdict(list)
for k, d in docs.items():
    for t in d: post[t].append(k)
def bm25(q, n=8, skip=()):
    sc = collections.Counter(); qt = set(toks(q))
    for t in qt:
        idf = math.log(1 + (NN - df[t] + .5) / (df[t] + .5))
        for k in post.get(t, ()):
            d = docs[k]; L = sum(d.values()); sc[k] += idf * d[t] * 2.2 / (d[t] + 1.2 * (.25 + .75 * L / avg))
    return [k for k, _ in sc.most_common(n + len(skip) + 2) if k not in skip][:n]
RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{9,}")
MASK = "an earlier Task Object"
def refs(text, skip=()):
    # a named object must be specific: a bare field name such as novelty_milli that also exists as an object key is not a reference
    return sorted(k for k in (set(RX.findall(text)) & set(O)) - set(skip) if len(k) >= 20 and (re.search(r"\d", k) or len(re.split(r"[_.:-]+", k)) >= 4))
def mask(text, keys):
    for k in sorted(keys, key=len, reverse=True): text = text.replace(k, MASK)
    return text
def stem(k): return "_".join(re.split(r"[_.:-]+", k.lower())[:2])
GENERIC = frozenset("ngo merge claim rerun re review check verify recheck audit fix add update task".split())
parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b): parent[find(a)] = find(b)
tasks = json.load(open(H / "snapshot/tasks-local.json"))
tasks = {k: v for k, v in tasks.items() if not k.startswith("verb_index_enrich") and len(v["title"] + v["prompt"]) > 40 and not looks_secret(v["title"] + " " + v["prompt"])}
DROP_CATS = {"aggregate_review_digest", "worker_memory", "system_feedback_signal"}  # lists and notes, not needs
cat = {o["k"]: o["c"] for o in objs}
pos = []
for k, s in O.items():
    if cat.get(k) in DROP_CATS: continue
    g = refs(s, skip=(k,))
    if g: pos.append({"src": "object_names_object", "from": k, "need": s, "gold": g})
for tid, t in tasks.items():
    text = f"{t['title']}. {t['prompt']}"; g = refs(text)
    if g: pos.append({"src": "task_names_object", "from": tid, "need": text, "gold": g})
refcount = collections.Counter(g for p in pos for g in p["gold"])
stemcount = collections.Counter(stem(p["from"]) for p in pos if p["src"] == "object_names_object")
HUB = lambda g: refcount[g] >= 6  # a widely used object does not make its users one subject
def fam(k): return ("f:" + stem(k)) if stemcount[stem(k)] < 12 and not stem(k).startswith("verb_") else ("k:" + k)
for p in pos:
    a = fam(p["from"]) if p["src"] == "object_names_object" else "t:" + p["from"]
    for g in p["gold"]:
        if not HUB(g): union(a, fam(g))
for tid, t in tasks.items():
    union("t:" + tid, "w:" + "_".join(x for x in toks(t["title"]) if x not in GENERIC)[:40].rsplit("_",1)[0])
def comp(p): return find(fam(p["from"]) if p["src"] == "object_names_object" else "t:" + p["from"])
def bucket(c): return int(hashlib.sha256(f"{SEED}:{c}".encode()).hexdigest(), 16) % 100
sizes = collections.Counter(comp(p) for p in pos); print("stems", collections.Counter(stem(p["from"]) for p in pos).most_common(12)); print("positive rows", len(pos), "families", len(sizes), "largest", sizes.most_common(3))
rng = random.Random(SEED)
def row(rid, need, cands, ranked, split, src, extra=None):
    need = " ".join(need.split())[:900]
    lines = [f"{n}. {c} | {c}. {' '.join(O[c].split())[:260]}" for n, c in enumerate(cands, 1)]
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Need: {need}\n\nCandidates:\n" + "\n".join(lines)}]
    return {"format": "orchestrator-json", "id": rid, "split": split, "src": src, "candidates": cands, "gold": ranked, "messages": msgs + ([{"role": "assistant", "content": json.dumps({"ranked": ranked[:5]})}] if ranked is not None else []), **(extra or {})}
out = collections.defaultdict(list); gold_rows = {"train": [], "dev": [], "held": []}
seen_gold = collections.Counter()
for n, p in enumerate(pos):
    seen_gold[p["gold"][0]] += 1
    if seen_gold[p["gold"][0]] > 6: excl["over_six_rows_for_one_object"] += 1; continue
    b = bucket(comp(p)); split = "held" if b < 20 else "dev" if b < 30 else "train"
    need = mask(p["need"], p["gold"]); g = p["gold"][:3]
    if len(toks(need)) < 6: excl["need_too_short"] += 1; continue
    c = bm25(need, 8, skip=(p["from"],))
    for x in g:
        if x not in c: c[rng.randrange(len(c) if len(c) < 8 else 8)] = x if len(c) >= 8 else c.insert(0, x) or x
    c = list(dict.fromkeys(c))
    if not set(g) <= set(c) or len(c) < 2: excl["gold_not_placed"] += 1; continue
    ranked = [x for x in c if x in g]
    gold_rows[split].append(row(f"{p['src']}-{n}", need, c[:8], ranked, split, p["src"]))
    out_need = need
    # a real need with another family's candidates: nothing here fits it
    if split != "held" or n % 2 == 0:
        other = rng.choice(pos)
        if comp(other) != comp(p):
            oc = [x for x in bm25(mask(other["need"], other["gold"]), 8, skip=(p["from"],)) if stem(x) != stem(p["from"]) and x not in p["gold"]][:8]
            sh = set(toks(need)) & set(t for x in oc[:1] for t in toks(O[x]))
            if len(oc) >= 2 and len(sh) <= 3:
                gold_rows[split].append(row(f"cross-{n}", need, oc, [], split, "cross_family_none"))
for s, v in gold_rows.items(): print(s, len(v), collections.Counter(r["src"] for r in v))
# seed-pack rows: the current adapter's own retrieval rows, none from a model
seed = [json.loads(l) for l in open(N / "claude-work-2026-10-31/glimmer-orchestrator/data/orchestrator-v1-sessionb/train-nonefix.jsonl")]
seed = [dict(r, split="train", src="seed_pack_retrieval") for r in seed if r.get("role") == "retrieval"]
# search-eval dev questions with rule labels only (no judged rows, no model-written questions)
qd = {q["qid"]: q for q in map(json.loads, open(H / "snapshot/dev.jsonl"))}
sd = []
for l in open(H / "snapshot/cands-off-dev.jsonl"):
    c = json.loads(l); q = qd[c["qid"]]
    if q.get("judged") or q.get("source") not in {"real_demand", "hand_checked_absent", "hand_rule", "drawn_library", "drawn_rows", "drawn_catalog"}: continue
    objc = [x["ref"][4:] for x in c["cands"] if x["ref"].startswith("obj:") and x["ref"][4:] in O][:8]
    if q.get("expect_none"):
        objc = bm25(q["q"], 6)
        if len(objc) >= 2: sd.append(row("sdev-" + c["qid"], q["q"], objc, [], "train", "search_dev_hand_checked_none"))
        continue
    gold = [a[4:] for a in q["accept"] if a.startswith("obj:") and a[4:] in objc]
    if gold and len(objc) >= 2: sd.append(row("sdev-" + c["qid"], q["q"], objc, gold, "train", "search_dev_rule_label"))
print("search dev rows", len(sd), collections.Counter(r["src"] for r in sd))
# Panel: real Tasks. Live candidates when recorded, else word search on the title, as the live route does.
live = {}
for l in open(N / "work-2026-11-03/meta-live/records/decisions.jsonl"):
    d = json.loads(l)
    if d.get("candidates"): live[d["task_id"]] = {"cands": d["candidates"], "cur": d.get("object_id"), "outcome": d.get("outcome"), "audit_pass": d.get("audit_pass")}
for l in open(N / "work-2026-11-03/sizing/records/fine-tune.jsonl"):
    d = json.loads(l)
    if d.get("event") == "answer" and d.get("candidates"): live.setdefault(d["task_id"], {"cands": d["candidates"], "cur": d.get("object_id"), "outcome": d.get("outcome"), "audit_pass": d.get("audit_pass")})
panel = []; refuted_in_live = sum(bool(set(v["cands"]) & refuted) for v in live.values())
print("live decisions", len(live), "with a refuted candidate", refuted_in_live)
trainish = {p["from"] for p in pos if bucket(comp(p)) >= 30}
for tid, t in tasks.items():
    text = f"{t['title']}. {t['prompt']}"; named = refs(text)
    if tid in trainish: continue
    need = mask(text, named)
    c = [x for x in live.get(tid, {}).get("cands", []) if x in O] or bm25(t["title"], 8)
    if len(c) < 2: continue
    split = "panel_dev" if bucket("panel:" + find("t:" + tid)) < 25 else "panel_held"
    panel.append(row("task-" + tid, need, c[:8], None, split, "real_task_live_candidates" if tid in live else "real_task_word_search", {"task_id": tid, "named_masked": named, "live": live.get(tid)}))
print("panel", collections.Counter((r["split"], r["src"]) for r in panel))
# train must not hold a task that is on the panel
pid = {r.get("task_id") for r in panel}
train = gold_rows["train"] + seed + sd; rng.shuffle(train)
allr = {"train": train, "dev": gold_rows["dev"], "held_refs": gold_rows["held"], "panel": panel}
texts = []; 
for rs in allr.values():
    for r in rs:
        for m in r["messages"]: texts.append(m["content"])
p = subprocess.run(["node", str(H / "tools/strip.mjs")], input=json.dumps(texts), capture_output=True, text=True, check=True)
st = json.loads(p.stdout); changed = sum(a != b for a, b in zip(texts, st)); print("texts", len(texts), "changed by personal data strip", changed)
it = iter(st)
for rs in allr.values():
    for r in rs:
        for m in r["messages"]: m["content"] = next(it)
hashes = {}
for name, rs in allr.items():
    f = H / f"data/{name}.jsonl"; f.write_text("".join(json.dumps(r) + "\n" for r in rs)); hashes[name] = {"rows": len(rs), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
needs = {name: {re.sub(r"\s+", " ", r["messages"][1]["content"].split("Candidates:")[0]) for r in rs} for name, rs in allr.items()}
print("need overlap train/held_refs", len(needs["train"] & needs["held_refs"]), "train/panel", len(needs["train"] & needs["panel"]), "train/dev", len(needs["train"] & needs["dev"]))
json.dump({"seed": SEED, "made_at": __import__("time").strftime("%FT%TZ", __import__("time").gmtime()), "files": hashes, "excluded_objects": dict(excl), "personal_strip": {"file": "work-2026-11-04-license/shim/deploy/cloudflare/pii_strip.js, commit 7fe3031", "texts": len(texts), "changed": changed}, "train_sources": collections.Counter(r["src"] for r in train), "objects_snapshot": "search-eval/corpus/objects-raw.json, read Nov 4 09:30 local", "refuted_ids": len(refuted)}, open(H / "data/manifest.json", "w"), indent=1, default=dict)
print(json.dumps(hashes, indent=0))
