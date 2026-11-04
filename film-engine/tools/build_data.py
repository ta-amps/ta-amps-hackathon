#!/usr/bin/env python3
"""Reads the presenter voice's timing and word alignment, plus home.json words, and writes data.js. Run again when a new timed voice lands."""
import json, re, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent
import os
V = R.parent.parent / "work-2026-11-02/claude-real-demo-film/voice-presenter" / os.environ.get("VOICE", "george-v4")
T = json.loads((V / "timing.json").read_text()); man = {l["id"]: l for l in json.loads((V / "voice-timestamps-manifest.json").read_text())["lines"]}
FIX = {"Eh-rah-nohs": "Eranos", "Tell-ay-on": "Teleion", "Omni-nodes": "OmniNodes", "Omni-node": "OmniNode"}
ALIGN = {}  # the manifest may list only the last synthesis, so find each scene's alignment by its text
for f in sorted(V.glob("*.align.json"), key=lambda q: q.stat().st_mtime):
    x = json.loads(f.read_text()); ALIGN[x.get("display_text", "")] = x
for l in json.loads((V / "voice-timestamps-manifest.json").read_text())["lines"]:
    if l.get("align_path") and Path(l["align_path"]).exists(): ALIGN[l["text"]] = json.loads(Path(l["align_path"]).read_text())
scenes = {}; cues = []
for k, s in T.items():
    a = ALIGN[s["text"]]; al = a["alignment"]; trim = float(a.get("start_trim_sec", 0))
    disp = s["text"].split(); ws = []; cur = ""; t0 = 0; t1 = 0
    for ch, x, y in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if ch.isspace():
            if cur: ws.append([cur, t0, t1]); cur = ""
        else:
            if not cur: t0 = x
            cur += ch; t1 = y
    if cur: ws.append([cur, t0, t1])
    if len(ws) == len(disp): ws = [[d, w[1], w[2]] for d, w in zip(disp, ws)]
    else: print("word count differs", k, len(ws), len(disp))
    base = s["start"] + s["voice_at"] - trim
    ws = [[w, round(base + a0, 3), round(base + a1, 3)] for w, a0, a1 in ws]
    scenes[k] = {"start": s["start"], "seconds": s["seconds"], "words": ws}
    # captions: whole sentences, or phrases of long sentences. Shown over up to two lines. Never a list fragment.
    cur = []; groups = []
    for w in ws:
        cur.append(w)
        if re.search(r"[.?!]$", w[0]): groups.append(cur); cur = []
    if cur: groups.append(cur)
    def split(g):
        text = " ".join(x[0] for x in g)
        if len(text) <= 100: return [g]
        # prefer a colon, then a word that opens a clause; a comma inside a list is the last resort
        best = None; mid = len(g) // 2; OPEN = ("each", "for", "so", "and", "or", "then", "It", "powered")
        for i, x in enumerate(g[:-1]):
            nxt = g[i + 1][0]
            rank = 0 if x[0].endswith(":") else 1 if nxt in OPEN else 2 if x[0].endswith(",") else None
            if rank is None: continue
            score = rank * 8 + abs(i - mid)
            if best is None or score < best[0]: best = (score, i)
        i = best[1] if best else mid
        return split(g[:i + 1]) + split(g[i + 1:])
    for g in groups:
        for q in split(g): cues.append([" ".join(x[0] for x in q), q[0][1], q[-1][2]])
for i, c in enumerate(cues):
    nxt = cues[i + 1][1] if i + 1 < len(cues) else c[2] + 2
    c[2] = round(min(max(c[2] + 0.25, c[1] + 1.0), nxt - 0.03), 3)
    c[0] = c[0].replace("Eranos for good dot org", "eranosforgood.org")
marks = json.loads((V / "marks.json").read_text())
KEY = {"george-v4": "flexible", "george-frustrations-first": "frustrations", "george-shortest-technical": "shortest", "george-efficiency-first": "efficiency", "george-grid-optimization": "grid", "george-evolving-fabric": "evolving", "george-evolving-fabric-cut": "evcut", "george-evolving-fabric-cut2": "evc2", "george-evolving-learn-a": "evla", "george-evolving-learn-b": "evlb", "george-evt": "evt", "george-evo": "evo", "george-evu": "evu", "george-evq": "evq", "george-evwb": "evwb", "george-evwc": "evwc", "george-evwd": "evwd", "george-evwe": "evwe", "george-evw": "evw", "george-evr": "evr"}.get(V.name, "flexible")
OUTD = R / "voices" / KEY; OUTD.mkdir(parents=True, exist_ok=True); (OUTD / "voice-music.mp3").write_bytes((V / "voice-music.mp3").read_bytes())
(R / f"index-{KEY}.html").write_text((R / "index.html").read_text().replace('src="audio/voice-music.mp3"', f'src="voices/{KEY}/voice-music.mp3"').replace('src="data.js"', f'src="voices/{KEY}/data.js"'))
(OUTD / "data.js").write_text("window.VOICE_KEY=" + json.dumps(KEY) + ";\n" + "window.CUES=" + json.dumps(scenes, separators=(",", ":")) + ";\nwindow.CAPTIONS=" + json.dumps(cues, separators=(",", ":")) + ";\nwindow.MARKS=" + json.dumps({k: [round(scenes[k]["start"] + x, 3) for x in v] for k, v in marks.items()}, separators=(",", ":")) + ";\n")
srt = "".join(f"{i+1}\n{int(c[1]//3600):02}:{int(c[1]%3600//60):02}:{int(c[1]%60):02},{int(c[1]*1000%1000):03} --> {int(c[2]//3600):02}:{int(c[2]%3600//60):02}:{int(c[2]%60):02},{int(c[2]*1000%1000):03}\n{c[0]}\n\n" for i, c in enumerate(cues))
(OUTD / "captions.srt").write_text(srt); print("scenes", len(scenes), "cues", len(cues)); print(scenes["parts"]["words"][:6]); print([c[0] for c in cues[:6]])
