#!/usr/bin/env python3
"""Put a new main film on the home page and /video/. Usage: tools/swap_film.py <source.mp4> <new-name>, for example
tools/swap_film.py .../review/cube-main-3.mp4 main-film-20261104c. Captions come from the .vtt and .srt named cube-main
beside the source, or pass --captions <stem>. Stops if the film gate fails. Then run tools/publish.sh.
The new name must be new: /media/ is cached for a year. Earlier films stay in static/media, so a rollback is one line, main_film in content/site.json, then tools/publish.sh. Poster is taken at 70 s; --poster-at changes it."""
import os
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
NOTES = Path(os.environ["TELEION_NOTES"])
FF = Path.home() / ".local/share/aidr-tools/ffmpeg-7.0.2-amd64-static/ffmpeg"
QA = NOTES / "work-2026-11-02/claude-real-demo-film/film_qa.py"
INBOX = NOTES / "work-2026-11-03/gallery-inbox.jsonl"
SMALL = NOTES / "work-2026-11-03/mass/site-small"
MEDIA = HERE / "static/media"
# Where the /video/ transcript starts a new paragraph, when the script has these lines.
BREAKS = ["Teleion Fabric is a fabric", "And we measure it.", "Teleion Fabric can run almost anything", "Anyone with spare AI", "See it at eranosforgood.org"]
a = argparse.ArgumentParser(); a.add_argument("source", type=Path); a.add_argument("name"); a.add_argument("--captions", default="cube-main"); a.add_argument("--poster-at", type=int, default=70)
a = a.parse_args()
vtt, srt = a.source.with_name(a.captions + ".vtt"), a.source.with_name(a.captions + ".srt")
for f in (a.source, vtt, srt):
    if not f.is_file(): sys.exit(f"missing {f}")
if not re.fullmatch(r"main-film-[a-z0-9-]+", a.name): sys.exit("the name must look like main-film-20261104c")
site_file = HERE / "content/site.json"; site = site_file.read_text()
old = json.loads(site)["main_film"]
if old == a.name or (MEDIA / f"{a.name}.mp4").exists(): sys.exit(f"{a.name} is already used; /media/ is cached for a year, so pick a new name")
if subprocess.run(["git", "status", "--porcelain"], cwd=HERE, capture_output=True, text=True).stdout.strip(): sys.exit("commit or set aside other changes first")
print("film gate..."); q = subprocess.run([sys.executable, str(QA), str(a.source), str(srt)])
if q.returncode: sys.exit("STOP: the film gate failed; nothing changed")
mp4 = MEDIA / f"{a.name}.mp4"
subprocess.run([str(FF), "-nostdin", "-y", "-loglevel", "error", "-i", str(a.source), "-vf", "scale=1280:-2", "-c:v", "libx264", "-preset", "slow", "-crf", "29", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(mp4)], check=True)
if mp4.stat().st_size > 25 * 2**20: mp4.unlink(); sys.exit("STOP: the web copy is over 25 MiB; nothing changed")
shutil.copy(vtt, MEDIA / f"{a.name}.vtt")
subprocess.run([str(FF), "-nostdin", "-v", "error", "-y", "-ss", str(a.poster_at), "-i", str(mp4), "-frames:v", "1", "-q:v", "4", str(MEDIA / f"{a.name}.jpg")], check=True)
# The one line that names the film.
site_file.write_text(site.replace(f'"main_film": "{old}"', f'"main_film": "{a.name}"'))
# The transcript follows the captions.
text = " ".join(l.strip() for l in srt.read_text().splitlines() if l.strip() and "-->" not in l and not l.strip().isdigit())
paras, rest = [], text
for m in BREAKS:
    i = rest.find(m)
    if i > 0: paras.append(rest[:i].strip()); rest = rest[i:]
paras.append(rest.strip())
vf = HERE / "content/video.json"; v = json.loads(vf.read_text())
next(b for b in v["blocks"] if b["type"] == "video")["transcript"] = paras
vf.write_text(json.dumps(v, indent=1, ensure_ascii=False) + "\n")
# The gallery leads with it, from the same web copy so it uploads once.
gid = a.source.stem; gf = HERE / "tools/gallery.json"; g = json.loads(gf.read_text())
prev = g["picks"][0][0]
g["site_videos"] = [gid] + [x for x in g["site_videos"] if x not in (gid, prev)]
g["picks"][0][0] = gid
gf.write_text(json.dumps(g, indent=1, ensure_ascii=False))
dur = subprocess.run([str(FF), "-hide_banner", "-i", str(a.source)], capture_output=True, text=True).stderr
m = re.search(r"Duration: (\d+):(\d+):(\d+)", dur)
with INBOX.open("a") as f:
    f.write(json.dumps({"id": gid, "file": str(a.source), "title": "Main film", "note": f"{int(m[2])}:{m[3]} with voice, captions off at first. Passes the film check; audio not heard here. Terminal runs are sped up.", "style": "Isometric", "status": "Main", "audio": "Voice", "poster_at": a.poster_at}, ensure_ascii=False) + "\n")
shutil.copy(mp4, SMALL / f"{gid}.mp4")
subprocess.run(["git", "add", "content", "tools", f"static/media/{a.name}.mp4", f"static/media/{a.name}.vtt", f"static/media/{a.name}.jpg"], cwd=HERE, check=True)
subprocess.run(["git", "commit", "-qm", f"teleionlabs: main film is now {gid}, served as {a.name}"], cwd=HERE, check=True)
print(f"ready: {a.name} ({mp4.stat().st_size / 2**20:.1f} MiB), committed. Now run tools/publish.sh")
