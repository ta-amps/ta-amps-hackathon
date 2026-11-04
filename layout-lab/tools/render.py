#!/usr/bin/env python3
"""render.py stills L01,L02 | render.py clip L01 [from] [to]. Runs niced. Stills at the same moments for every layout."""
import sys, base64, functools, http.server, threading, subprocess, os, json
from pathlib import Path
from playwright.sync_api import sync_playwright
R = Path(__file__).resolve().parent.parent
FF = str(Path.home() / ".local/share/aidr-tools/ffmpeg-7.0.2-amd64-static/ffmpeg")
SHELL = next(Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
BEATS = {"a-task-arrives": 1.7, "b-choices-land": 6.2, "c-later-run": 9.7}
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
def open_page(pw, l, extra=""):
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(R))); threading.Thread(target=s.serve_forever, daemon=True).start()
    b = pw.chromium.launch(executable_path=str(SHELL), args=["--disable-gpu", "--font-render-hinting=none", "--disable-lcd-text", "--force-color-profile=srgb"])
    pg = b.new_context(viewport={"width": 1920, "height": 1080}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{s.server_port}/index.html?l={l}{extra}"); pg.evaluate("window.READY.then(()=>1)"); return b, pg, errs
GRAB = "t=>{renderAt(t);return document.getElementById('c').toDataURL('image/png').slice(22)}"
GRABJ = "t=>{renderAt(t);return document.getElementById('c').toDataURL('image/jpeg',0.96).slice(23)}"
os.nice(10)
with sync_playwright() as pw:
    if sys.argv[1] == "stills":
        for l in sys.argv[2].split(","):
            b, pg, errs = open_page(pw, l)
            for n, t in BEATS.items(): (R / "stills" / f"{l}-{n}.png").write_bytes(base64.b64decode(pg.evaluate(GRAB, t)))
            info = pg.evaluate("layoutInfo()");
            b2, pg2, _ = open_page(pw, l, "&cap=player"); (R / "stills" / f"{l}-player-captions.png").write_bytes(base64.b64decode(pg2.evaluate(GRAB, BEATS["c-later-run"]))); b2.close()
            print(l, info["name"], "over", info["over"], info["overFi"], errs); (R / "stills" / f"{l}.json").write_text(json.dumps(info)); b.close()
    else:
        l = sys.argv[2]; a = float(sys.argv[3]) if len(sys.argv) > 3 else 0; z = float(sys.argv[4]) if len(sys.argv) > 4 else 10
        b, pg, errs = open_page(pw, l)
        ff = subprocess.Popen(["nice", "-n", "12", FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", "30", "-i", "-", "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "2", "-movflags", "+faststart", "-an", str(R / "clips" / f"{l}.mp4")], stdin=subprocess.PIPE)
        for f in range(int(a * 30), int(z * 30)): ff.stdin.write(base64.b64decode(pg.evaluate(GRABJ, f / 30)))
        ff.stdin.close(); ff.wait(); print("clip", l, errs); b.close()
