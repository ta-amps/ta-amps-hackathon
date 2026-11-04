#!/usr/bin/env python3
"""board.py: one contact sheet, one row per layout: three moments, then player captions on. Labels carry the measurements."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
R = Path(__file__).resolve().parent.parent
m = json.loads((R / "measures.json").read_text())
ORDER = [l.strip() for l in (R / "order.txt").read_text().splitlines() if l.strip()]
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
f1 = ImageFont.truetype(FB, 26); f2 = ImageFont.truetype(F, 21); f3 = ImageFont.truetype(F, 20)
TW, TH = 600, 338; GAP = 12; LAB = 92; HDR = 58
cols = [("a-task-arrives", "Task arrives"), ("b-choices-land", "Choices land"), ("c-later-run", "A later run spends less"), ("player-captions", "Player captions on, over burned")]
ORDER = [l for l in ORDER if l in m]
W = 4 * TW + 5 * GAP; H = HDR + len(ORDER) * (TH + LAB + GAP) + GAP
im = Image.new("RGB", (W, H), (235, 231, 221)); d = ImageDraw.Draw(im)
for i, (_, n) in enumerate(cols): d.text((GAP + i * (TW + GAP) + 8, 16), n, fill=(17, 22, 31), font=f1)
y = HDR
for l in ORDER:
    q = m[l]; d.text((GAP, y + 4), f"{l}  {q['name']}", fill=(17, 22, 31), font=f1)
    d.text((GAP, y + 38), f"Fabric {q['fabric_w']}% wide, {q['fabric_h']}% tall; with pillars {q['world_w']}% by {q['world_h']}%.  Text {q['text_px']} px.  Eye travel {q['eye_px']} px.  Covers {q['cover_pct']}% of core.", fill=(40, 44, 52), font=f2)
    d.text((GAP, y + 64), f"Chars per line {q.get('chars')}.  Weight center x {q['weight_x']}, y {q['weight_y']}.  Largest empty {q['empty_pct']}%.  Lowest content y {q['content_bottom']}, player box top y {round(q['cap_box_y0'])}, box touches {q['cap_box_hits']} px.", fill=(40, 44, 52), font=f3)
    y2 = y + LAB
    for i, (n, _) in enumerate(cols):
        p = R / "stills" / f"{l}-{n}.png"
        if p.exists(): im.paste(Image.open(p).convert("RGB").resize((TW, TH), Image.LANCZOS), (GAP + i * (TW + GAP), y2))
    y += TH + LAB + GAP
im.save(R / "board.png", optimize=True); print(im.size, len(ORDER))
