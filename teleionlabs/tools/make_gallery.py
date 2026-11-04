#!/usr/bin/env python3
"""Build the owner's review gallery at /video-gallery/. Run after one build (it borrows the built page's frame), then build again."""
import html, json, os, re, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
NOTES = Path(os.environ["TELEION_NOTES"])  # the local working notes; not part of this repository
W = NOTES / "work-2026-11-02"
def _home(v):
    if isinstance(v, str) and v.startswith("notes:"): return str(NOTES / v[6:])
    if isinstance(v, str) and v.startswith("~/"): return str(Path.home() / v[2:])
    if isinstance(v, list): return [_home(x) for x in v]
    if isinstance(v, dict): return {k: _home(x) for k, x in v.items()}
    return v
CFG = _home(json.loads((HERE / "tools/gallery.json").read_text()))
SITE_VIDEOS = CFG.get("site_videos") or []
FF = CFG["ffmpeg"]
OUT = HERE / "static/video-gallery"; MEDIA = HERE / "static/media"
shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)
for f in MEDIA.glob("gallery-*"):
    if not f.name.startswith("gallery-eranos-"): f.unlink()

if not CFG.get("site_videos"):
    # The 3D film with the real Eranos pages: its own copy, so the live home page is untouched.
    src = Path(CFG["film3d_dist"])
    d3 = OUT / "3d"; d3.mkdir()
    page = (src / "index.html").read_text()
    for n in ["film.js", "film3d.js", "three-0.187.0.min.js"] + [f"eranos-{p}.webp" for p in ["home", "ngo", "info", "process", "status", "library"]]:
        shutil.copy(src / "assets" / n, d3 / n)
        page = page.replace(f"/assets/{n}", f"/video-gallery/3d/{n}")
    js = (d3 / "film.js").read_text().replace('"/assets/film3d.js"', '"/video-gallery/3d/film3d.js"'); (d3 / "film.js").write_text(js)
    shutil.copy(src / "media/film-voice-20261103.mp3", MEDIA / "gallery-3d-voice.mp3")
    page = page.replace("/media/film-voice-20261103.mp3", "/media/gallery-3d-voice.mp3")
    (d3 / "index.html").write_text(page)

    # The Claude Design World film, with its own styles and fonts.
    wd = OUT / "world"; shutil.copytree(NOTES / "claude-design-2026-11-02/site/dist", wd, ignore=shutil.ignore_patterns("fonts") if False else None)
    for sub in ("human", "library", "status"): shutil.rmtree(wd / sub, ignore_errors=True)
    idx = wd / "index.html"; t = idx.read_text().replace('"/static/', '"/video-gallery/world/static/').replace("'/static/", "'/video-gallery/world/static/")
    # Only Meta model names show from live data here; everything else reads "a model". Links to pages not copied go to their real homes.
    t, n = re.subn(r"/l\+ama\|[^/]*/i\.test\(s\)", "!/muse/i.test(s)", t); assert n >= 1
    t = t.replace('href="/human/"', 'href="/"').replace('href="/library/"', 'href="https://eranosforgood.org/library"')
    idx.write_text(t)
    for css in (wd / "static/css").glob("*.css"):
        c = css.read_text().replace("/static/", "/video-gallery/world/static/"); css.write_text(c)

# The Claude Design review page, as that session built it.
cd = NOTES / "claude-design-2026-11-02/video-gallery"
if not SITE_VIDEOS: shutil.copytree(cd, OUT / "claude-design", ignore=shutil.ignore_patterns("build.py", "sync.sh", "template.html", "README.md", "scenes", "*.py"))
# The isometric film page (film "iso"), as a self-contained copy.
if not SITE_VIDEOS: shutil.copytree(NOTES / "work-2026-11-03/iso-film", OUT / "iso", ignore=shutil.ignore_patterns("out", "qa", "tools", "captions.srt", "_*.txt"))
from PIL import Image
Image.open(NOTES / "work-2026-11-03/gallery-extra/raytraced-sheet.png").convert("RGB").save(MEDIA / "gallery-blocks-stills.jpg", quality=85)
for src, dst in (("t5", "gallery-cube-stills"), ("vars", "gallery-cube-versions")):
    im = Image.open(NOTES / f"work-2026-11-03/iso-film/qa/{src}.png").convert("RGB"); im.thumbnail((2000, 2000)); im.save(MEDIA / f"{dst}.jpg", quality=85)
shutil.copytree(NOTES / "work-2026-11-03/film-3d-simple", OUT / "3d-simple")
# Finished work that agents hand in: one JSON object per line. Newest entry for an id wins. Over-size files are skipped and reported.
inbox = NOTES / "work-2026-11-03/gallery-inbox.jsonl"
seen = {v["id"]: v for v in CFG["videos"]}
if inbox.exists():
    for line in inbox.read_text().splitlines():
        if not line.strip(): continue
        x = json.loads(line)
        if x.get("remove"): seen.pop(x["id"], None); continue
        if not Path(x["file"]).exists(): print("missing", x["file"]); continue
        if Path(x["file"]).stat().st_size > 25 * 2**20: print("too large, skipped", x["file"]); continue
        seen[x["id"]] = {"group": "cuts", "type": "Full cut", "status": "Candidate", "audio": "Voice", "poster_at": 45, **x}
hold = [l.strip() for l in (NOTES / "work-2026-11-03/mass/hold.txt").read_text().splitlines() if l.strip() and not l.startswith("#")] if (NOTES / "work-2026-11-03/mass/hold.txt").exists() else []
CFG["videos"] = [v for v in seen.values() if not any(v["id"] == h or v["id"].startswith(h + "-") for h in hold)]
if SITE_VIDEOS: CFG["videos"] = [v for v in CFG["videos"] if v["id"] in SITE_VIDEOS]
# Music options, each mixed under the voice.
mg = NOTES / "work-2026-11-03/music-gen"; music = []
if (mg / "candidates.json").exists():
    d = json.loads((mg / "candidates.json").read_text()); d = d if isinstance(d, list) else d.get("candidates", [])
    for x in d:
        if CFG.get("site_videos") and x["id"] not in ("el-pads", "el-strings", "ace-felt"): continue
        src = mg / "out" / f"{x['id']}-mix.mp3"
        if not src.exists(): continue
        shutil.copy(src, MEDIA / f"gallery-music-{x['id']}.mp3")
        music.append({"id": "music-" + x["id"], "title": "Music: " + x.get("title", x["id"]), "note": "3:00 under the voice, for listening. Screened by measurements; nobody here has listened to it.", "type": "Music", "style": "Music", "status": "Candidate", "audio": "Voice", "seconds": 180, "video": f"/media/gallery-music-{x['id']}.mp3", "open": f"/media/gallery-music-{x['id']}.mp3"})
CFG["extra"] = [e for e in CFG.get("extra", []) if not e["id"].startswith("music-")] + music
# The film mixer: pick the best clip per scene.
if not SITE_VIDEOS: shutil.copytree(NOTES / "work-2026-11-03/scene-library", OUT / "mix", ignore=lambda d, names: [n for n in names if n in ("work", "tools", "gen", "sheets", "posters-src", "__pycache__") or ".tmp" in n or (Path(d, n).is_file() and Path(d, n).stat().st_size > 24 * 2**20) or (d.endswith("scene-library") and n not in ("player", "library.json", "captions.json", "audio.json", "audio", "clips", "recipes", "mixes", "posters", "review.json"))])
# Rendered videos and their first-look pictures.
rows = []
for v in CFG["videos"]:
    p = (W / v["file"]) if not v["file"].startswith("/") else Path(v["file"])
    if not p.exists(): print("missing", p); continue
    name = "gallery-" + v["id"]
    small = NOTES / "work-2026-11-03/mass/site-small" / f"{v['id']}.mp4"; small.parent.mkdir(exist_ok=True)
    if not small.exists() or small.stat().st_mtime < p.stat().st_mtime:
        subprocess.run(["nice", "-n", "5", FF, "-y", "-loglevel", "error", "-i", str(p), "-vf", "scale=1280:-2", "-c:v", "libx264", "-preset", "medium", "-crf", "33", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", str(small)], check=True)
    shutil.copy(small, MEDIA / f"{name}.mp4")
    subprocess.run([FF, "-v", "error", "-y", "-ss", str(v.get("poster_at", 40)), "-i", str(p), "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "5", str(MEDIA / f"{name}.jpg")], check=True)
    rows.append((v, f"/media/{name}.mp4", f"/media/{name}.jpg"))
e = html.escape
# Permanent numbers: an item keeps its number for good, and new items take the next one.
num_file = HERE / "tools/gallery-numbers.json"
numbers = json.loads(num_file.read_text()) if num_file.exists() else {}
def number(i):
    if i not in numbers: numbers[i] = max(numbers.values(), default=0) + 1
    return numbers[i]
def probe(p):
    r = subprocess.run([FF, "-hide_banner", "-i", str(p)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r)
    return round(int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])) if m else None
import datetime as dt
stamp = lambda p: dt.datetime.fromtimestamp(Path(p).stat().st_mtime, dt.timezone.utc).isoformat(timespec="minutes")
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
items = []
added = json.loads((HERE / "tools/gallery-added.json").read_text()) if (HERE / "tools/gallery-added.json").exists() else {}
for l in CFG["live"]:
    items.append({**{k: l.get(k) for k in ("id", "title", "note", "type", "style", "status", "audio", "seconds")}, "open": l["href"], "added": added.setdefault(l["id"], now)})
for v, m, j in rows:
    src = (W / v["file"]) if not v["file"].startswith("/") else Path(v["file"])
    items.append({"id": v["id"], "title": v["title"], "note": v["note"], "type": v["type"], "style": v["style"], "status": v["status"], "audio": v["audio"], "seconds": probe(src), "video": m, "poster": j, "open": m, "added": stamp(src)})
cdm = NOTES / "claude-design-2026-11-02/video-gallery"
for c in ([] if CFG.get("site_videos") else json.loads((cdm / "manifest.json").read_text())["items"]):
    base = "/video-gallery/claude-design/"
    world = "world" in c["look"].lower() or "3d" in c["look"].lower()
    items.append({"id": c["id"], "title": "Claude Design: " + c["title"], "note": c.get("desc", "") + " Some older wording; its Eranos pages are drawn copies.", "type": "Full cut", "style": "World" if world else "Flat", "status": "Candidate" if world else "Older", "audio": "No voice" if "none" in c.get("audio", "") else "Voice", "seconds": round(c["seconds"]), "video": base + c["file"], "poster": base + c["poster"], "open": base + c["file"], "added": stamp(cdm / c["file"])})
for x in CFG.get("extra", []):
    items.append({**x, "added": added.setdefault(x["id"], now)})
for it in items: it["num"] = number(it["id"])
items.sort(key=lambda x: (x["added"], x["num"]), reverse=True)
num_file.write_text(json.dumps(numbers, indent=0)); (HERE / "tools/gallery-added.json").write_text(json.dumps(added, indent=0))
ids = {i["id"] for i in items}
(OUT / "items.json").write_text(json.dumps({"updated": now, "items": items, "picks": [{"id": a, "why": b} for a, b in CFG.get("picks", []) if a in ids]}, ensure_ascii=False))
shutil.copy(HERE / "tools/gallery.js", OUT / "gallery.js"); shutil.copy(HERE / "tools/gallery.css", OUT / "gallery.css")
rowsh = "".join(f'<li><a href="{e(i["open"])}">#{i["num"]} {e(i["title"])}</a>. {e(i["type"])}, {e(i["style"])}, {e(i["status"])}. {e(i["note"])}</li>' for i in items)
body = f"""<h1>{e(CFG['title'])}</h1><p>{e(CFG['intro'])}</p><div id="gal" hidden></div><ol id="plain">{rowsh}</ol><script src="/video-gallery/gallery.js" defer></script>"""
frame = (HERE / "dist/free/index.html").read_text()
out = re.sub(r"<main\b[^>]*>.*?</main>", lambda m: f'<main id="main" class="wide">{body}</main>', frame, flags=re.S)
out = re.sub(r"<title>.*?</title>", f"<title>{e(CFG['title'])} · Teleion Labs</title>", out, flags=re.S)
out = re.sub(r'<meta name="description"[^>]*>', '<meta name="robots" content="noindex"><link rel="stylesheet" href="/video-gallery/gallery.css">', out)
(OUT / "index.html").write_text(out)
(HERE / "static/video-gallery.txt").write_text(f"{CFG['title']}\n\n{CFG['intro']}\n\n" + "\n".join(f"#{i['num']} {i['title']} ({i['type']}, {i['style']}, {i['status']}): https://teleionlabs.com{i['open']}" for i in items) + "\n")
print(len(items), "items,", len(rows), "videos copied", sum((MEDIA / Path(m).name).stat().st_size for _, m, _ in rows) // 2**20, "MiB")
