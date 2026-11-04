#!/usr/bin/env python3
"""Every real-page view against pages/<k>.flags.json: no flagged text may enter the frame. check_views.py [style] [seed]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from render import R, server, page
from playwright.sync_api import sync_playwright
style = sys.argv[1] if len(sys.argv) > 1 else "iso"; seed = sys.argv[2] if len(sys.argv) > 2 else "0"; dq = sys.argv[3] if len(sys.argv) > 3 else ""
F = {p.name.split(".")[0]: json.loads(p.read_text()) for p in (R / "pages").glob("*.flags.json")}
srv = server(); bad = {}; seen = {}
with sync_playwright() as pw:
    b, pg, errs = page(pw, srv, style, f"&seed={seed}{dq}")
    pg.evaluate("window.__views = []")
    for i in range(1300, 1800):
        for v in pg.evaluate("(t) => { window.__views.length = 0; renderAt(t); return window.__views; }", i / 10):
            seen.setdefault(v["img"], [v["t"], v["t"]])[1] = v["t"]
            for f in F.get(v["img"], []):
                if f["x0"] < v["x1"] and f["x1"] > v["x0"] and f["y0"] < v["y1"] and f["y1"] > v["y0"]: bad.setdefault((v["img"], f["s"][:50]), v["t"])
    b.close()
print("pages shown:", {k: [round(x, 1) for x in r] for k, r in seen.items()}); print("flagged text in frame:", bad or "none", "errors:", errs); sys.exit(1 if bad else 0)
