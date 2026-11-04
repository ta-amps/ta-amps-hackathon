#!/bin/bash
# qa.sh <full.mp4>: motion checks, then the film gate with the home-film length, loudness, and contact sheets.
cd "$(dirname "$0")/.."; f="$1"; b=$(basename "$f" .mp4)
cp captions.srt "${f%.mp4}.srt"
python3 ../motion-tools/proof/check.py . "$f" 2>&1 | tail -8 | cut -c1-400 > qa/$b.check.txt; cat qa/$b.check.txt
python3 - "$f" <<'E'
import re,subprocess,sys,json
from pathlib import Path
FF=str(Path.home()/".local/share/aidr-tools/ffmpeg-7.0.2-amd64-static/ffmpeg"); f=sys.argv[1]
r=subprocess.run([FF,"-hide_banner","-nostats","-i",f,"-af","ebur128=peak=true:framelog=quiet","-f","null","-"],capture_output=True,text=True).stderr
print("LUFS",re.findall(r"I:\s+(-?[\d.]+) LUFS",r)[-1],"LRA",re.findall(r"LRA:\s+(-?[\d.]+) LU",r)[-1],"TP",re.findall(r"Peak:\s+(-?[\d.]+) dBFS",r)[-1])
i=subprocess.run([FF,"-hide_banner","-i",f],capture_output=True,text=True).stderr; print(re.search(r"Duration: [\d:.]+",i)[0],re.search(r"Video:.*",i)[0][:90],f"{Path(f).stat().st_size/2**20:.1f} MiB")
fz=subprocess.run([FF,"-hide_banner","-nostats","-i",f,"-vf","freezedetect=n=0.002:d=2.5","-an","-f","null","-"],capture_output=True,text=True).stderr
print("frozen",re.findall(r"freeze_start: ([\d.]+)",fz)[:6],re.findall(r"freeze_duration: ([\d.]+)",fz)[:6])
E
F=~/.local/share/aidr-tools/ffmpeg-7.0.2-amd64-static/ffmpeg; $F -y -hide_banner -loglevel error -i "$f" -vf "fps=1/6,scale=480:-1,tile=4x8" -frames:v 1 qa/$b-sheet.png
