#!/bin/bash
cd $TELEION_NOTES/work-2026-11-03/layout-lab
ALL=$(paste -sd, order.txt)
python3 tools/render.py stills $ALL | grep -v "over 0 0 \[\]" | cut -c1-100
python3 tools/measure.py $ALL >/dev/null 2>measure.err; tail -1 measure.err
for l in B80W65 B75W65 B70W65 O2N S50 S40 S30 B80 B70 BARCAP CARB CON F50 BR DOL; do python3 tools/render.py clip $l >/dev/null; done
python3 tools/board.py; python3 tools/make_review.py
D=../mass/local-site/terminal/layouts; cp board.png REVIEW.md $D/; cp stills/*.png $D/stills/; cp clips/*.mp4 $D/clips/
python3 - <<'PY'
import json
m=json.load(open('measures.json'))
for l in 'B80W65 B75W65 B70W65 O2N S50 S40 S30 F40 B80C O3'.split():
    q=m[l]; print(l,q['fabric_w'],q['fabric_h'],q['world_w'],q['world_h'],'wx',q['weight_x'],'wy',q['weight_y'],'txt',q['text_px'],'eye',q['eye_px'],'cov',q['cover_pct'],'blk',q['black_pct'],'ch',q['chars'],'emp',q['empty_pct'],'box',q['cap_box_hits'])
PY
echo FINISHED
