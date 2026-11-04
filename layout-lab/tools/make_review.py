#!/usr/bin/env python3
import json
from pathlib import Path
R=Path(__file__).resolve().parent.parent; m=json.loads((R/'measures.json').read_text())
V={
'B80W65':'PICK. Largest fabric of any layout with a readable centered log. Full log lines fit. Three lines is the real limit.',
'B80W55':'Fits only shortened lines (55 chars), and saves just 1.2 points of black. Not worth losing the full lines.',
'B80W75':'Same fabric, but the right part of the window is empty on most lines, with more black and more eye travel.',
'B75W65':'My own addition. Four lines for 2.6 points less fabric width. Use it if three lines feel rushed once the film is paced.',
'BARCAP':'Caption rule fallback: the burned line lives in the title bar, so no band is needed. Reads well but adds a bright line right above the log.',
'B70W65':'ALTERNATE 2. Five lines of context, and two lines stay clear of a player caption. Fabric is 12% smaller than B80W65.',
'B70W55':'As B70W65 with shortened lines. No real gain.','B70W75':'Most black of the window group (16.9%). Looks heavy.',
'B70W65WIN':'Windows-style bar. Measures the same as the Mac one. Mac dots read faster as "a terminal"; this one is a matter of taste.',
'B80':'Edge to edge, with a why column. Same fabric, but 16.7% black, 726 px travel and a heavy band. The owner was right to drop it.',
'B70':'Edge to edge: 25.4% black and the longest travel of the bottom group.',
'S50':'Tried as asked. Fabric is 20% narrower than B80W65, visual weight sits far left, and the eye crosses 1094 px per line. 40% of the panel width is unused.',
'S40':'Best side by side. Fabric grows 12% over 50/50 and text only drops 1 px. Weight still pulls left.',
'S30':'Largest side-by-side fabric, at 24 px and the most lopsided weight of the plain splits. Needs the shortest wording.',
'S60':'Fabric is too small: 29.4% wide. Rejected on the owner\'s first test.',
'F50':'Floating lifts the window off the edges and cuts black to 23%, but it is still a left-heavy frame.','F40':'Same: tidier than S40, same fabric, 18% black, weight x 0.321.','F30':'Tidy, 23 px, fabric as S30. Good if a side window is ever wanted.',
'FB':'Floating strip with the caption band kept. Clean, but the band costs a fifth of the fabric.','FT':'Log on top reads first and pulls weight to the top; the fabric feels pushed down. Covers 0.22%, from the window shadow.',
'O2N':'ALTERNATE 1. Most impressive: fabric 60.9% by 91.6%, almost nothing covered, weight centered. Text is the catch: 23 px log, 20 px choices, poor on phones.',
'O1':'One corner window. Clean cover, but weight x 0.344: one black box unbalances a symmetric picture.','O2':'O2N with the caption band. Choices text falls to 18 px, too small.','O3':'Shown as the failure: covers 17.11% of the core picture, including the Harness cubes.',
'B80C':'B80 with a reserved burned-caption band. Fabric 39.3% against 47.4%: that is the price of the band.','B70C':'Same at 70/30: fabric 34.4%, too small.',
'T20':'Reverse of B80C. Same size. The log sits far from the Harness cubes, and the top-heavy weight (y 0.23) fights the isometric floor.','T30':'Reverse of B70C. Same complaint, smaller fabric.',
'CON':'Best way to show the choices beside the log, and well balanced, but fabric is only 32.5% wide and black is 25%.','RACK':'Shortest travel of the flat layouts (479 px): each part has one row. Clear, but no longer feels like a typing terminal, and the fabric is small.','GUT':'Why column inside the log. Useful idea; fabric too small here. The idea could move into B70W75.',
'CARB':'Blocks hop from the line to its cubes. Physically links them, and is the best motion idea. Add this to the pick after a look at pace.','CAR':'Same idea across a 1009 px flight on a split. Long flights cross the frame and get busy.',
'P3':'Smallest fabric (26.8%). The third panel is clear, but this fails the owner\'s size test badly.','FLANK':'Symmetric and centered, but 38.6% black, 22 px text, and the right terminal stays half empty because most lines belong left.',
'SLAB':'Truly in the 3D world and striking, but text runs at 30 degrees at about 22 px, fabric is small, and it leaves the largest empty area (26%).','BOOK':'Beautiful V shape; unreadable at 17.9 px on a slant. A brief opening shot at most.',
'PLINTH':'Front camera flattens the fabric into the "chocolate bars" the owner rejected. The 47% cover figure is the screens on the plinth\'s own face, not the fabric.',
'PL2':'Fails: 5 lines do not fit, 16.5 px on a slant. Keeps the fabric large, but the faces are too short for a log.','BR':'Ratio follows the story. Fine motion, but panels resizing draw the eye away from the log, and weight stays left.','DOL':'Camera moves between them. Lively, but the terminal and full fabric are not both in frame at every moment, so it misses "at once". Good as a transition.',
}
order=[l for l in (R/'order.txt').read_text().split()]
rows='\n'.join(f"| {l} | {m[l]['fabric_w']} x {m[l]['fabric_h']} | {m[l]['world_w']} x {m[l]['world_h']} | {m[l]['text_px']} | {'/'.join(map(str,m[l]['chars'])) or '-'} | {m[l]['weight_x']}, {m[l]['weight_y']} | {m[l]['empty_pct']} | {m[l]['black_pct']} | {m[l]['eye_px']} | {m[l]['cover_pct']} | {m[l]['phone844']} / {m[l]['phone390']} | {m[l]['tile390']} | {m[l]['cap_box_hits']} | {V[l]} |" for l in order)
head=(R/'tools/review_head.md').read_text()
(R/'REVIEW.md').write_text(head+"\n## Every layout, measured\n\nFabric is the cube floor plus its tallest skyline, as a percent of frame width x height. With pillars adds the pillars and names. Text is the smallest log or choices size in px at 1080p, corrected for slant. Chars is how many fit on one line. Weight is the center of visual weight, x then y, with 0.5 as center, averaged over the three moments. Empty is the largest empty rectangle as a percent of frame. Eye is the mean px from a typed line to the cubes it changes, over the choice lines. Covers is the percent of core picture pixels hidden by panels, at the worst moment. Phone is text px at 844 and 390 wide. Tile is one cube tile's width at 390 wide. Box is non-paper px under a two-line player caption box (0 means clear).\n\n| ID | Fabric % | With pillars % | Text | Chars | Weight | Empty % | Black % | Eye | Covers % | Phone | Tile | Box | Honest review |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"+rows+"\n")
print(len(order))
