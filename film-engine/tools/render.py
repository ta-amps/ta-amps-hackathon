#!/usr/bin/env python3
"""render.py <out.mp4> [--style iso] [--workers 4] [--from S --to S] [--audio f] [--still t,t,t --dir d]. Seek, draw, grab, pipe; chunks run in parallel."""
import argparse, base64, functools, http.server, json, subprocess, sys, tempfile, threading, time, multiprocessing as mp, os
from pathlib import Path
from playwright.sync_api import sync_playwright
R = Path(__file__).resolve().parent.parent
FF = str(Path.home() / ".local/share/aidr-tools/ffmpeg-7.0.2-amd64-static/ffmpeg")
SHELL = next(Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'"
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self): self.send_header("Content-Security-Policy", CSP); super().end_headers()
    def log_message(self, *a): pass
def server():
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=os.environ.get("ISO_STATIC", str(R)))); threading.Thread(target=s.serve_forever, daemon=True).start(); return s
def page(pw, srv, style, q=""):
    b = pw.chromium.launch(executable_path=str(SHELL), args=["--disable-gpu", "--font-render-hinting=none", "--disable-lcd-text", "--force-color-profile=srgb"])
    pg = b.new_context(viewport={"width": 1920, "height": 1080}).new_page(); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    import re as _re; _v = _re.search(r"[?&]voice=([a-z0-9]+)", q); pg.goto(f"http://127.0.0.1:{srv.server_port}/{'index-' + _v[1] + '.html' if _v else 'index-flexible.html'}?style={style}&still=1{q}"); pg.evaluate("window.READY.then(()=>1)")
    return b, pg, errs
GRAB = "async t=>{if(window.__prep)await window.__prep(t);renderAt(t);return document.getElementById('c').toDataURL('image/jpeg',0.97).slice(23)}"
def chunk(a):
    style, f0, f1, path, q = a; srv = server()
    ff = subprocess.Popen(["nice", "-n", "10", FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", "30", "-i", "-", "-vf", "scale=in_range=pc:in_color_matrix=bt601,format=gbrp,scale=out_range=tv:out_color_matrix=bt709:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-threads", "3", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", path], stdin=subprocess.PIPE)
    with sync_playwright() as pw:
        b, pg, errs = page(pw, srv, style, q)
        for f in range(f0, f1): ff.stdin.write(base64.b64decode(pg.evaluate(GRAB, f / 30)))
        b.close()
    ff.stdin.close(); ff.wait(); return path, errs
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("out", nargs="?"); ap.add_argument("--style", default="iso"); ap.add_argument("--workers", type=int, default=4); ap.add_argument("--from", dest="a", type=float, default=0); ap.add_argument("--to", dest="b", type=float, default=180); ap.add_argument("--audio"); ap.add_argument("--still"); ap.add_argument("--dir", default="qa/still"); ap.add_argument("--q", default=""); ap.add_argument("--kbps", type=int, default=800)
    A = ap.parse_args()
    if A.still:
        srv = server(); d = R / A.dir; d.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            b, pg, errs = page(pw, srv, A.style, A.q); t0 = time.time(); ts = [float(x) for x in A.still.split(",")]
            for t in ts: (d / f"{t:07.2f}.jpg").write_bytes(base64.b64decode(pg.evaluate(GRAB, t)))
            print(f"{(time.time() - t0) / len(ts) * 1000:.0f} ms/frame errors: {errs}"); b.close()
        sys.exit(0)
    n0, n1 = round(A.a * 30), round(A.b * 30); step = max(300, (n1 - n0) // (A.workers * 3) + 1); parts = []
    tmp = Path(tempfile.mkdtemp(prefix=f"iso-{A.style}-", dir=str(R / "qa")))
    for i, f in enumerate(range(n0, n1, step)): parts.append((A.style, f, min(n1, f + step), str(tmp / f"p{i:03d}.mkv"), A.q))
    t0 = time.time()
    with mp.Pool(A.workers) as pool:
        for path, errs in pool.imap_unordered(chunk, parts):
            print(Path(path).name, f"{time.time() - t0:.0f}s", errs[:2] if errs else "", flush=True)
    lst = tmp / "l.txt"; lst.write_text("".join(f"file '{p[3]}'\n" for p in parts))
    base = [FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst)]
    if A.audio: base += ["-i", A.audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-t", f"{A.b - A.a:.3f}"]
    def enc(crf):
        v = ["-c:v", "libx264", "-preset", "medium", "-threads", "6", "-crf", str(crf), "-maxrate", "1900k", "-bufsize", "3800k", "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-r", "30"]
        subprocess.run(["nice", "-n", "10", *base, *v, "-movflags", "+faststart", A.out], check=True); return Path(A.out).stat().st_size / 2**20
    crf = 24; mib = enc(crf)
    while mib > 20.5 and crf < 34:
        crf += 2; mib = enc(crf)
    print("crf", crf, flush=True)
    import shutil; shutil.rmtree(tmp); print("DONE", A.out, f"{Path(A.out).stat().st_size / 2**20:.1f} MiB {time.time() - t0:.0f}s", flush=True)
