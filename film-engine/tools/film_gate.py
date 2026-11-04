#!/usr/bin/env python3
"""The film gate for the 180 s home film.
 - Duration: exactly 180 s (+0.1), for the home film. Submission cuts have their own gate.
 - No hackathon line anywhere (owner, Nov 3).
 - Numbers and Meta models: on real pages and labels, checked in the page text, not in captions.
 Added: on-screen words go through the shared list; loudness and true peak are reported. film_gate.py <mp4> [--seconds N]"""
import os
import json, re, subprocess, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent
FF = str(Path.home() / ".local/share/aidr-tools/ffmpeg-7.0.2-amd64-static/ffmpeg")
WORDS = Path(os.environ["TELEION_NOTES"]) / "coordination-2026-10-31/rules/banned-words.json"
mp4 = Path(sys.argv[1]); fails = []
def run(*a): return subprocess.run([FF, "-hide_banner", "-nostats", *a], capture_output=True, text=True).stderr
info = run("-i", str(mp4)); m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info); dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
want_s = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 180.0
if not want_s - 0.1 <= dur <= want_s + 0.1: fails.append(f"duration {dur:.2f} s")
size = mp4.stat().st_size / 2**20
if size > 21: fails.append(f"size {size:.1f} MiB over 21")
for k, msg in (("1920x1080", "not 1920x1080"), ("yuv420p", "not yuv420p"), ("bt709", "not bt709"), ("Audio:", "no audio")):
    if k not in info: fails.append(msg)
fr = run("-i", str(mp4), "-vf", "freezedetect=n=0.002:d=2.5", "-an", "-f", "null", "-"); sp = re.findall(r"freeze_start: ([\d.]+)", fr)
if sp: fails.append(f"frozen stretches at {[round(float(x)) for x in sp[:6]]}")
p = subprocess.run([FF, "-hide_banner", "-nostats", "-i", str(mp4), "-vf", "fps=1,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-an", "-f", "null", "-"], capture_output=True, text=True).stdout
dark = [i for i, y in enumerate(float(x) for x in re.findall(r"YAVG=([\d.]+)", p)) if y < 110]
if dark: fails.append(f"dark frames at {dark[:8]}")
d = json.loads(WORDS.read_text()); film = (R / "film.js").read_text(); caps = mp4.with_suffix(".srt").read_text() if mp4.with_suffix(".srt").exists() else (R / "voices/flexible/captions.srt").read_text()
strings = " ".join(re.findall(r'"([^"]{3,})"', film))
for where, txt in (("captions", re.sub(r"\d+:\d+:\d+[,.]\d+ --> .*|^\d+$", " ", caps, flags=re.M)), ("film text", strings)):
    for cat in ("always", "visible_text", "marketing_voice"):
        for pat in d[cat]["patterns"]:
            mm = re.search(pat, txt, re.I)
            if mm: fails.append(f"{where} hits word list ({cat}): {mm[0]!r}")
    if re.search(r"\b(tessera|herma|hybrid)\b", txt, re.I): fails.append(f"retired word in {where}")
    if re.search(r"\b(nouns?|verbs?|receipts?|live numbers|plain http)\b", txt, re.I): fails.append(f"forbidden phrase in {where}")
if re.search(r"hackathon", caps, re.I): fails.append("hackathon line is spoken or captioned")
home = (R / "pages/home.txt").read_text()
if not re.search(r"\d+ workers", home): fails.append("no worker number on the live page")
if "Muse Spark" not in home + (R / "pages/dash.txt").read_text(): fails.append("no Meta model on real pages")
l = run("-i", str(mp4), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-")
lufs, tp, lra = re.findall(r"I:\s+(-?[\d.]+) LUFS", l)[-1], re.findall(r"Peak:\s+(-?[\d.]+) dBFS", l)[-1], re.findall(r"LRA:\s+(-?[\d.]+) LU", l)[-1]
if float(tp) > -1.0: fails.append(f"true peak {tp}")
print(json.dumps({"file": mp4.name, "seconds": round(dur, 2), "mib": round(size, 1), "lufs": float(lufs), "tp": float(tp), "lra": float(lra), "fail": fails}))
sys.exit(1 if fails else 0)
