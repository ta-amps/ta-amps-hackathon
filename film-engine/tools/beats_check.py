#!/usr/bin/env python3
"""Pace gate: beats_check.py "<query>". Fails on any shot under 2 s, any terminal line or run row under 0.95 s, on-screen text under 150 words a minute (at least 2 s), and on unused time at the end. Prints total length and the shortest 10 shots."""
import json, sys, http.server, threading, functools
from pathlib import Path
from playwright.sync_api import sync_playwright
R = Path(__file__).resolve().parent.parent; q = sys.argv[1]; voice = q.split("voice=")[1].split("&")[0]
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(R)); h.log_message = lambda *a: None
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(R), **k)
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome"); p = b.new_page(viewport={"width": 1920, "height": 1080}); p.goto(f"http://127.0.0.1:{srv.server_port}/index-{voice}.html?{q.lstrip('&')}"); p.wait_for_function("window.__beats"); d = p.evaluate("window.__beats()"); b.close()
fails = []
for x in d["beats"]:
    need = 2 if x["kind"] == "shot" else 0.95 if x["kind"] in ("terminal line", "run row") else max(2, x["words"] / 2.5)
    x["need"] = need
    if x["d"] + 1e-6 < need: fails.append(f'{x["kind"]} "{x["label"]}" {x["d"]} s at {x["s"]} (needs {need:.1f})')
tail = d["total"] - d["last"]
if tail > 0.6: fails.append(f"{tail:.2f} s unused after the last word")
if not 179 <= d["total"] <= 180: fails.append(f'total {d["total"]:.2f} s, target 179 to 180')
sh = sorted((x for x in d["beats"] if x["kind"] == "shot"), key=lambda x: x["d"])[:10]
print(json.dumps({"total": d["total"], "last_word": d["last"], "shortest_shots": [[x["label"], x["d"], x["s"]] for x in sh], "fail": fails}, indent=0))
sys.exit(1 if fails else 0)
