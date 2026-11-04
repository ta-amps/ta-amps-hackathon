#!/usr/bin/env python3
"""Exploratory, not registered: where B and C differ by question kind, and how often B-cold's extra tries got past the limit."""
import json, collections as C
Q = {q["id"]: q for q in json.load(open("prereg/questions.json"))}
R = json.load(open("records/scored.json"))
for g in ("primary", "any"):
    for k in ("owner", "license", "language", "discovery"):
        line = []
        for arm in ("B", "B-direct", "C", "C-raw"):
            rs = [x for x in R if x["arm"] == arm and Q[x["id"]]["kind"] == k and (Q[x["id"]]["group"] == "primary" if g == "primary" else Q[x["id"]]["group"] in ("primary", "fresh", "low_star_unindexed", "not_on_feed"))]
            cor = sum(x["outcome"] == "correct" for x in rs); t = sum(x["tokens"] for x in rs)
            line.append(f"{arm} {cor}/{len(rs)} tok/run {t // max(1, len(rs))} tok/correct {t // max(1, cor)}")
        print(g, k, " | ".join(line))
for arm in ("B", "B-cold"):
    rs = [x for x in R if x["arm"] == arm and Q[x["id"]]["group"] in ("low_star_unindexed", "not_on_feed")]
    n = C.Counter(); 
    for x in rs:
        repos = [t for t in x["tools"] if t["name"] == "repos" or "/q/repos" in t["args"].get("url", "")]
        n[len(repos)] += 1
    print(arm, "lookups per run on unindexed items", sorted(n.items()))
ids = sorted({x["id"] for x in R if Q[x["id"]]["group"] in ("low_star_unindexed", "not_on_feed")})
print("item: B correct of 3 / B-cold correct of 3")
print([(i, sum(x["outcome"] == "correct" for x in R if x["id"] == i and x["arm"] == "B"), sum(x["outcome"] == "correct" for x in R if x["id"] == i and x["arm"] == "B-cold")) for i in ids])
