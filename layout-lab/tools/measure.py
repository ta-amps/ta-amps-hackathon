#!/usr/bin/env python3
"""measure.py [ids]. Writes measures.json: weight center, empty region, text px, eye travel, fabric size, cover, caption checks, phone sizes."""
import sys, json, base64, io, math, functools, http.server, threading, os
from pathlib import Path
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
R = Path(__file__).resolve().parent.parent
SHELL = next(Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
BEATS = [1.7, 6.2, 9.7]; PAPER = np.array([245, 242, 234], float); SAFE_Y = 917
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
os.nice(10)
s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(R))); threading.Thread(target=s.serve_forever, daemon=True).start()
def pg_for(b, l, extra=""):
    pg = b.new_context(viewport={"width": 1920, "height": 1080}).new_page(); pg.goto(f"http://127.0.0.1:{s.server_port}/index.html?l={l}{extra}"); pg.evaluate("window.READY.then(()=>1)"); return pg
def grab(pg, t):
    d = base64.b64decode(pg.evaluate("t=>{renderAt(t);return document.getElementById('c').toDataURL('image/png').slice(22)}", t)); return np.asarray(Image.open(io.BytesIO(d)).convert("RGB"), float)
def weight(a):
    lum = np.abs(a - PAPER).sum(axis=2) / 3
    sat = a.max(axis=2) - a.min(axis=2)
    w = np.where(lum > 8, lum + 0.5 * sat, 0)
    h, wd = w.shape; tot = w.sum() or 1
    return float((w.sum(axis=0) * np.arange(wd)).sum() / tot / wd), float((w.sum(axis=1) * np.arange(h)).sum() / tot / h)
def empty_rect(mask):
    # largest all-empty rectangle on an 8 px grid; mask True = empty
    H, W = mask.shape; hist = np.zeros(W, int); best = (0, 0, 0)
    for y in range(H):
        hist = np.where(mask[y], hist + 1, 0); st = []
        for x in range(W + 1):
            v = hist[x] if x < W else 0; start = x
            while st and st[-1][1] >= v:
                sx, sv = st.pop(); ar = sv * (x - sx)
                if ar > best[0]: best = (ar, x - sx, sv)
                start = sx
            st.append((start, v))
    return best
ids = sys.argv[1].split(",")
out = json.loads((R / "measures.json").read_text()) if (R / "measures.json").exists() else {}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=str(SHELL), args=["--disable-gpu", "--font-render-hinting=none", "--disable-lcd-text"])
    for l in ids:
        pg = pg_for(b, l, "&cap=none"); pn = pg_for(b, l, "&cap=none&nopanels=1"); pb = pg_for(b, l)
        nb = pg.evaluate("NOBURN()"); info = pg.evaluate("layoutInfo()"); panels = pg.evaluate("PANELS()")
        cents = []; empties = []; cover = []; black = []
        for t in BEATS:
            a = grab(pg, t); n = grab(pn, t); fb = grab(pb, t)
            cents.append(weight(a))
            ne = np.abs(fb - PAPER).sum(axis=2) > 18
            mask = ne[:(1080 if nb else SAFE_Y):8, ::8] == False; ar, ew, eh = empty_rect(mask); empties.append((ar * 64 / (1920 * 1080) * 100, ew * 8, eh * 8))
            core = np.abs(n - PAPER).sum(axis=2) > 18; panel = np.abs(a - n).sum(axis=2) > 60
            cover.append(float((core & panel).sum() / max(1, core.sum()) * 100))
            black.append(float((a.sum(axis=2) < 120).mean() * 100))
        # travel: each choice line to the cubes it changes
        evs = pg.evaluate("LAB.LOG.map(e=>[e.t,e.k])"); dist = []
        for tt, k in evs:
            if k < 0 or tt < 2 or tt > 6.2: continue
            q = pg.evaluate("t=>probe(t)", tt + 0.03)
            if q.get("line") and q["line"]["k"] == k:
                p0, p1 = q["line"]["p0"], q["line"]["p1"]; mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2; z = q["zones"][str(k)]; dist.append(math.hypot(z[0] - mx, z[1] - my))
        q = pg.evaluate("t=>probe(t)", 9.7); wd = q["world"]
        # caption checks
        qp = pb.evaluate("t=>probe(t)", 9.7)
        pp = pg_for(b, l, "&cap=player"); qq = pp.evaluate("t=>probe(t)", 9.7); box = qq["box"]; 
        c0 = grab(pg, 9.7); inbox = np.abs(c0[int(box["y0"]):int(box["y1"]), int(box["x0"]):int(box["x1"])] - PAPER).sum(axis=2) > 18
        lowest = np.where((np.abs(c0 - PAPER).sum(axis=2) > 18).any(axis=1))[0]
        fs = [o.get("fs") * o.get("effk", 1) for o in panels if o.get("fs")]
        over = info["over"] + info["overFi"]
        out[l] = dict(name=info["name"], weight_x=round(np.mean([x[0] for x in cents]), 3), weight_y=round(np.mean([x[1] for x in cents]), 3), weight_x_choice=round(cents[1][0], 3),
            empty_pct=round(max(e[0] for e in empties), 1), empty_wh=max(empties)[1:], cover_pct=round(max(cover), 2), black_pct=round(np.mean(black), 1),
            text_px=round(min(fs), 1) if fs else None, eye_px=round(float(np.mean(dist))) if dist else None, eye_max=round(float(np.max(dist))) if dist else None,
            fabric_w=round((wd["fx1"] - wd["fx0"]) / 19.2, 1), fabric_h=round((wd["fy1"] - wd["fy0"]) / 10.8, 1), world_w=round((wd["x1"] - wd["x0"]) / 19.2, 1), world_h=round((wd["y1"] - wd["y0"]) / 10.8, 1),
            phone844=round(min(fs) * 844 / 1920, 1) if fs else None, phone390=round(min(fs) * 390 / 1920, 1) if fs else None, tile390=round(wd["tileW"] * 390 / 1920, 1), drop390=round(wd["modelDrop"] * 390 / 1920, 1),
            over=over, chars=pg.evaluate("CHARS()"), form=pg.evaluate("FORM()"), cap_box_y0=box["y0"], cap_box_hits=int(inbox.sum()), content_bottom=int(lowest.max()) if len(lowest) else 0, burn_w=round(qp.get("burnW") or 0), box_w=round(box["x1"] - box["x0"]), words=info["words"])
        print(l, json.dumps({k: v for k, v in out[l].items() if k not in ("words", "name")}, default=float), flush=True)
        (R / "measures.json").write_text(json.dumps(out, indent=1, default=float))
    b.close()
