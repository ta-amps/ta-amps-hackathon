#!/usr/bin/env python3
"""Composition gate. comp_check.py <id> "<query>" [--style iso] [--step 2.5] : prints JSON. Exit 1 on failure. Uses ISO_STATIC if set.
Fails: part covered >5%; label over a part, label or heading; anything cut by the frame edge; center of mass >8% off the safe area's center; an empty block >25% of the safe area."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from render import R, server, page
from playwright.sync_api import sync_playwright
AX = 479
LIM = dict(cover=0.05, over=0.04, mass=0.08, empty=0.25)
SAFE = (60 / 4, 60 / 4, 1860 / 4, 900 / 4)  # in the 480 x 270 measure
def biggest_rect(grid, W, H):
    # largest empty rectangle over a 0/1 grid
    best = 0; h = [0] * W; box = None
    for y in range(H):
        for x in range(W): h[x] = 0 if grid[y * W + x] else h[x] + 1
        st = []
        for x in range(W + 1):
            cur = h[x] if x < W else 0; start = x
            while st and st[-1][1] >= cur:
                s0, hh = st.pop(); a = hh * (x - s0)
                if a > best: best = a; box = (s0, y - hh + 1, x, y + 1)
                start = s0
            st.append((start, cur))
    return best, box
def judge(s):
    res = []; P = [p for p in s["parts"] if p["kind"] != "caption"]
    for p in s["parts"]:
        if p["kind"] == "component" and 1 - p["shown"] / p["area"] > LIM["cover"]: res.append(("blocked", p["id"], round(1 - p["shown"] / p["area"], 3)))
        if p["kind"] == "name" and 1 - p["shown"] / p["area"] > 0.12: res.append(("name-blocked", p["id"], round(1 - p["shown"] / p["area"], 3)))
        x0, y0, x1, y1 = p["box"]
        if p["kind"] not in ("caption", "ground", "traffic") and (x0 <= 0 or y0 <= 0 or x1 >= 479 or y1 >= 269): res.append(("cut", p["id"], p["box"]))
    for L, X, k in s["over"]:
        if not (L == "caption" and X == "caption"): res.append(("label-over", f"{L} / {X}", k))
    by = {p["id"]: p for p in s["parts"]}; T0, O0 = by.get("Tasks pillar"), by.get("Objects pillar")
    if T0 and O0:  # strict left-right symmetry (owner, Nov 3)
        if abs(T0["box"][0] + O0["box"][2] - AX) > 4 or abs(T0["box"][2] + O0["box"][0] - AX) > 4: res.append(("not-symmetric", "pillars x", float(abs(T0["box"][0] + O0["box"][2] - AX))))
        if abs(T0["box"][1] - O0["box"][1]) > 2 or abs(T0["box"][3] - O0["box"][3]) > 2: res.append(("not-symmetric", "pillars y", float(abs(T0["box"][1] - O0["box"][1]))))
        sk = by.get("skyline")
        if sk and sk["area"] > 0.05 * 480 * 270 and abs(sk["cx"] - AX / 2) > 24: res.append(("not-symmetric", "fabric off center", round(abs(sk["cx"] - AX / 2) / 480, 3)))
        lg = by.get("legend")
        if lg and abs(lg["box"][0] + lg["box"][2] - 479) > 6: res.append(("not-symmetric", "legend", 0.0))
    if s.get("dup"): res.append(("caption-duplicates-screen", s["dup"][:40], 1.0))
    TK = s.get("term") or {}
    for k, v in TK.items():
        if v.get("over"): res.append(("terminal-line-too-long", k, float(v["over"])))
    if "main=1" in " ".join(sys.argv) and "main" in TK:
        m = TK["main"]; fb = [by[k]["box"] for k in ("floor", "skyline") if by.get(k)]
        if abs(m["x"] * 2 + m["w"] - 1920) > 2: res.append(("terminal-off-axis", "main", 1.0))
        if fb:
            bot = max((b[1] + b[3]) * 4 for b in fb); above, below = m["y"] - bot, 1080 - m["y"] - m["h"]
            if above < 0: res.append(("terminal-covers-fabric", "main", round(-above / 1080, 3)))
            elif (by.get("floor") or {}).get("box", [0, 0, 0, 0])[2] > 180 and abs(above - below) > 28: res.append(("terminal-padding-uneven", f"{above} vs {below}", round(abs(above - below) / 1080, 3)))
    if AX == 479:
        if "main" in TK and abs(TK["main"]["x"] * 2 + TK["main"]["w"] - 1920) > 4: res.append(("terminal-off-axis", "main", 1.0))
        if " left" in TK and " right" in TK:
            l, r = TK[" left"], TK[" right"]
            if abs(l["x"] + r["x"] + r["w"] - 1920) > 4 or l["w"] != r["w"] or l["h"] != r["h"] or l["y"] != r["y"]: res.append(("terminals-not-mirrored", "both", 1.0))
    W0 = sum(p["area"] * (0.15 if p["kind"] in ("ground", "traffic") else 1) for p in P) or 1
    mx = sum(p["cx"] * p["area"] * (0.15 if p["kind"] in ("ground", "traffic") else 1) for p in P) / W0; my = sum(p["cy"] * p["area"] * (0.15 if p["kind"] in ("ground", "traffic") else 1) for p in P) / W0
    cx, cy = (SAFE[0] + SAFE[2]) / 2, (SAFE[1] + SAFE[3]) / 2; dx, dy = (mx - cx) / (SAFE[2] - SAFE[0]), (my - cy) / (SAFE[3] - SAFE[1])
    if max(abs(dx), abs(dy)) > LIM["mass"]: res.append(("off-center", f"{dx:+.2f},{dy:+.2f}", round(max(abs(dx), abs(dy)), 3)))
    GW, GH = 48, 27; occ = s["occ"]; x0, x1 = int(SAFE[0] * GW / 480), int(SAFE[2] * GW / 480) ; y0, y1 = int(SAFE[1] * GH / 270), int(SAFE[3] * GH / 270)
    W_, H_ = x1 - x0, y1 - y0; grid = [int(occ[(y + y0) * GW + x + x0]) for y in range(H_) for x in range(W_)]; b, box = biggest_rect(grid, W_, H_); frac = b / (W_ * H_)
    if frac > LIM["empty"]: res.append(("empty-block", box, round(frac, 3)))
    return res
def run(fid, q, style="iso", step=2.5, frm=None, to=None):
    global AX
    AX = 719 if "tv=s50" in q else 669 if "tv=s40" in q else 685 if "emb=terminal" in q and ("tv=" not in q or "tv=paper" in q) else 479
    tf = 0; srv = server(); fails = {}; worst = {}; n = 0
    with sync_playwright() as pw:
        b, pg, errs = page(pw, srv, style, q)
        cuts = pg.evaluate("Object.values(CUES).map(s=>s.start)")
        if frm is None: frm = 0.5; to = pg.evaluate("Object.values(CUES).reduce((m, s) => Math.max(m, s.start + s.seconds), 0)")
        t = frm
        while t < to:
            if any(abs(t - c0) < 0.75 for c0 in cuts): t += 0.5; continue
            if pg.evaluate("(t)=>(window.TERR_ON||t<CUES.omninode.start)?window.__compSkipF(t):false", t): t += step; continue
            s = pg.evaluate("async (t)=>{if(window.__prep)await window.__prep(t);return window.__compSample(t)}", t); n += 1; tf = max(tf, s.get("trafficFabric", 0))
            for r in judge(s):
                fails[r[0]] = fails.get(r[0], 0) + 1; k = r[0]
                if k not in worst or (isinstance(r[2], float) and r[2] > worst[k][2]): worst[k] = (round(t, 1), str(r[1]), r[2] if isinstance(r[2], float) else 0.0)
            t += step
        b.close()
    return {"id": fid, "samples": n, "fails": fails, "worst": worst, "pass": not fails, "traffic_over_fabric": tf, "traffic_checked_by_eye": tf > 0.04, "errors": errs[:2]}
def _one(args):
    return run(*args)
def run_many(fid, q, style, step, procs):
    import multiprocessing as mp
    srv = server()
    with sync_playwright() as pw:
        b, pg, errs = page(pw, srv, style, q); end = pg.evaluate("Object.values(CUES).reduce((m, s) => Math.max(m, s.start + s.seconds), 0)"); b.close()
    cuts = [0.5 + (end - 0.5) * i / procs for i in range(procs + 1)]
    with mp.get_context("spawn").Pool(procs) as P: R0 = P.map(_one, [(fid, q, style, step, cuts[i], cuts[i + 1]) for i in range(procs)])
    fails, worst = {}, {}
    for r in R0:
        for k, v in r["fails"].items(): fails[k] = fails.get(k, 0) + v
        for k, v in r["worst"].items():
            if k not in worst or v[2] > worst[k][2]: worst[k] = v
    return {"id": fid, "samples": sum(r["samples"] for r in R0), "fails": fails, "worst": worst, "pass": not fails, "traffic_over_fabric": max(r["traffic_over_fabric"] for r in R0), "traffic_checked_by_eye": any(r["traffic_checked_by_eye"] for r in R0), "errors": [e for r in R0 for e in r["errors"]][:2]}
if __name__ == "__main__":
    a = sys.argv[1:]; style = a[a.index("--style") + 1] if "--style" in a else "iso"; step = float(a[a.index("--step") + 1]) if "--step" in a else 1.0
    pr = int(a[a.index("--procs") + 1]) if "--procs" in a else 1; qq = a[1] if len(a) > 1 and not a[1].startswith("--") else ""; r = run_many(a[0], qq, style, step, pr) if pr > 1 else run(a[0], qq, style, step); print(json.dumps(r)); sys.exit(0 if r["pass"] else 1)
