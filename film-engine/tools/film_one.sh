#!/bin/bash
# film_one.sh <id> <query>: full cut, gate, clips, sheet. Uses ISO_STATIC if set.
cd "$(dirname "$0")/.."; n=$1; q=$2; f=$PWD/out/full/$n.mp4; w=${WORKERS:-4}
python3 tools/render.py $f --style iso --q "$q" --audio audio/voice-music.mp3 --workers $w > qa/$n.full.log 2>&1 || { echo "RESULT $n RENDER-FAIL"; exit 1; }
cp captions.srt "${f%.mp4}.srt"; python3 tools/film_gate.py $f > qa/$n.gate.json 2>&1; echo "RESULT $n gate $(cut -c1-300 qa/$n.gate.json)"
python3 tools/clips_from_full.py $f $n > /dev/null 2>&1
~/.local/share/aidr-tools/ffmpeg-7.0.2-amd64-static/ffmpeg -y -hide_banner -loglevel error -i $f -vf "fps=1/6,scale=384:-1,tile=5x6" -frames:v 1 qa/$n-sheet.png; echo "RESULT $n done $(du -m $f | cut -f1) MB"
