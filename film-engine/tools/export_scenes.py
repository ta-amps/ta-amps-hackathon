#!/usr/bin/env python3
"""Per-scene silent clips, cut exactly at the voice's scene boundaries: out/scenes/<treatment>/<scene>.mp4.
export_scenes.py [--workers 6] iso flat kinetic mix iso-s1 flat-s2 ... A name is <style> or <style>-s<seed>."""
import base64, json, subprocess, sys, time, multiprocessing as mp
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from render import R, FF, server, page, GRAB
from playwright.sync_api import sync_playwright
T = json.loads((R.parent.parent / "work-2026-11-02/claude-real-demo-film/voice-presenter/george/timing.json").read_text())
OUT = R / "out/scenes"
def job(a):
    name, kind, nocap = a; base = name.split("-", 1)[1] if name[0] == "v" and name[1].isdigit() else name; style, _, sd = base.partition("-s"); dq = ""
    if style in ("stack", "cutaway", "campus", "parallax", "chapters", "closeup", "sheets"): dq = f"&dir={style}"; style = "iso"
    sc = T[kind]; f0, f1 = round(sc["start"] * 30), round((sc["start"] + sc["seconds"]) * 30)
    out = (R / "out/scenes-nocap" if nocap else OUT) / name / f"{kind}.mp4"; out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists(): return name, kind, 0, 0, []
    t0 = time.time(); srv = server(); tmp = out.with_suffix(".part.mp4")
    ff = subprocess.Popen(["nice", "-n", "10", FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", "30", "-i", "-", "-vf", "scale=in_range=pc:in_color_matrix=bt601,format=gbrp,scale=out_range=tv:out_color_matrix=bt709:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-threads", "3", "-g", "60", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", "-an", str(tmp)], stdin=subprocess.PIPE)
    with sync_playwright() as pw:
        b, pg, errs = page(pw, srv, style, f"&clip=1&seed={sd or 0}{dq}" + ("&captions=0" if nocap else ""))
        for f in range(f0, f1): ff.stdin.write(base64.b64decode(pg.evaluate(GRAB, f / 30)))
        b.close()
    ff.stdin.close(); ff.wait(); tmp.rename(out); srv.shutdown()
    return name, kind, f1 - f0, time.time() - t0, errs
if __name__ == "__main__":
    args = sys.argv[1:]; w = 6
    if "--workers" in args: i = args.index("--workers"); w = int(args[i + 1]); del args[i:i + 2]
    nocap = "--nocap" in args
    if nocap: args.remove("--nocap")
    jobs = [(n, k, nocap) for n in args for k in T]
    with mp.Pool(w) as pool:
        for name, kind, n, s, errs in pool.imap_unordered(job, jobs):
            print(name, kind, n, f"{s:.0f}s", errs[:1] if errs else "", flush=True)
    for n in args: print("DONE", n, len(list(((R / "out/scenes-nocap" if nocap else OUT) / n).glob("*.mp4"))), flush=True)
