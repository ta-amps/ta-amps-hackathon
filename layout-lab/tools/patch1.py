import re
s=open('lab.js').read()
s=s.replace('const UNIT = { 0: 24, 1: 12, 2: 12, 3: 12, 4: 12 };','const UNIT = { 0: 18, 1: 9, 2: 9, 3: 9, 4: 9 };')
# two-line pillar names, sized to the pillar
s=s.replace('''const fsN = Math.max(20, Math.round(25 * Math.min(1.15, k))); c.font = `600 ${fsN}px ${SANS}`; c.textAlign = "center"; c.fillStyle = INK; const yNm = yP - H - rx * 0.42 - 14; ft2("Durable Tasks", W.cx - px, yNm); ft2("Durable Task Objects", W.cx + px, yNm); if (W.nameY) ft2("Teleion Fabric", W.cx, W.nameY); c.textAlign = "left";''',
'''const fsN = Math.max(20, Math.round(21 * Math.min(1.4, k))); c.font = `600 ${fsN}px ${SANS}`; c.textAlign = "center"; c.fillStyle = INK; const yNm = yP - H - rx * (W.mode === "front" ? Math.sin(W.pitch) : 0.42) - 12; ft2("Durable", W.cx - px, yNm - fsN * 1.16); ft2("Tasks", W.cx - px, yNm); ft2("Durable Task", W.cx + px, yNm - fsN * 1.16); ft2("Objects", W.cx + px, yNm); if (W.nameY) ft2("Teleion Fabric", W.cx, W.nameY); c.textAlign = "left";''')
s=s.replace('const top = Math.min(yNm - fsN, P(-N / 2, -N / 2, Math.max(vals[2], 0))[1]), bottom = d[1] + th; DZ.world = { x0: W.cx - px - rx, x1: W.cx + px + rx, y0: top, y1: bottom, fx0: W.cx - HALF, fx1: W.cx + HALF, fy0: P(-N / 2, -N / 2, 150)[1], fy1: bottom, fsN, rx };',
 'const maxV = Math.max(LAB.A[2].v, LAB.B[2].v) * UNIT[2], top = Math.min(yNm - fsN * 2.2, P(-N / 2, -N / 2, maxV)[1]), bottom = d[1] + th; DZ.world = { x0: W.cx - px - rx, x1: W.cx + px + rx, y0: top, y1: bottom, fx0: W.cx - HALF, fx1: W.cx + HALF, fy0: P(0, 0, 0)[1] - (W.cy - P(-N / 2, -N / 2, maxV)[1]), fy1: bottom, fsN, rx, k, tileW: (W.mode === "front" ? 5 * U * 1.25 : 5 * U * 0.866 * 2) * k, modelDrop: (LAB.A[3].v - LAB.B[3].v) * UNIT[3] * k };')
# automatic line form
s=s.replace('function formOf(e, form) { return form === "full" ? e.full : form === "tiny" ? e.tiny : e.short; }',
'''function formOf(e, form) { return form === "full" ? e.full : form === "tiny" ? e.tiny : e.short; }
const AUTOF = new Map(); function autoForm(o) { const key = [o.w, o.fs, o.side || "", o.gutter || "", o.pad ?? 26].join(); if (AUTOF.has(key)) return AUTOF.get(key); c.save(); const PAD = o.pad ?? 26, lim = (o.gutter || o.w) - PAD * (o.gutter ? 1 : 2); let got = "tiny"; for (const f of ["full", "short", "tiny"]) { let ok = true; LAB.LOG.forEach((e) => { if (o.side && e.side !== o.side) return; c.font = `${e.cmd ? 700 : 400} ${o.fs}px ${MONO}`; if (c.measureText(formOf(e, f)).width > lim) ok = false; }); if (ok) { got = f; break; } } c.restore(); AUTOF.set(key, got); return got; }''')
s=s.replace('const { x, y, w, h, fs, lh, form = "short", title = "Real run, sped up · Nov 3" } = o, PAD = o.pad ?? 26','const { x, y, w, h, fs, lh, title = "Real run, sped up · Nov 3" } = o, form = o.form || autoForm(o), PAD = o.pad ?? 26')
s=s.replace('LAB.LOG.forEach((e) => { if (o.side && e.side !== o.side) return; const lim = (o.gutter || o.w) - PAD * (o.gutter ? 1 : 2); if (c.measureText(formOf(e, o.form || "short")).width > lim) over++; });','const F0 = o.form || autoForm(o); LAB.LOG.forEach((e) => { if (o.side && e.side !== o.side) return; const lim = (o.gutter || o.w) - PAD * (o.gutter ? 1 : 2); c.font = `${e.cmd ? 700 : 400} ${o.fs}px ${MONO}`; if (c.measureText(formOf(e, F0)).width > lim) over++; });')
# floating window look
s=s.replace('if (!o.flat) { c.shadowColor = "rgba(40,34,24,.2)"; c.shadowBlur = 10; c.shadowOffsetY = 4; } rr(x, y, w, h, 12);','if (!o.flat) { c.shadowColor = o.float ? "rgba(40,34,24,.34)" : "rgba(40,34,24,.2)"; c.shadowBlur = o.float ? 34 : 10; c.shadowOffsetY = o.float ? 14 : 4; } rr(x, y, w, h, o.float ? 16 : 12);')
# corner legend
s=s.replace('function legend(t, o) { const { cx, y,','''function legendCol(t, o) { const { x, y, fs = 24, kinds, lh } = o; const LH = lh || fs * 2.6; kinds.forEach((k, n) => { const q = CHO(k, t), yy = y + n * LH; rr(x, yy - fs * 0.85, fs * 0.95, fs * 0.95, 5); c.fillStyle = q ? K5[k][0] : shade(K5[k][0], 1, 0.55); c.fill(); c.font = `600 ${fs}px ${SANS}`; c.fillStyle = q ? INK : "#7E7C74"; c.fillText(K5[k][1], x + fs * 1.3, yy); if (q) { c.font = `400 ${fs * 0.9}px ${SANS}`; c.fillStyle = shade(K5[k][0], 0.78); c.fillText(q.s, x + fs * 1.3, yy + fs * 1.1); } }); }
function legend(t, o) { const { cx, y,''')
# captions
a=s.index('function caption(t)'); b=s.index('// a terminal lying in the world')
s=s[:a]+'''const CAPMODE = qs.get("cap") || "burned", SAFE_Y = 917;
const capText = (t) => (t < 1.95 ? "A Task arrives." : t < RB ? "Fabric Intelligence picks the parts for this Task." : `Later that day, same Task: ${LAB.B[2].v} from stored work, ${LAB.tokB.toLocaleString("en-US")} tokens, not ${LAB.tokA.toLocaleString("en-US")}.`);
function caption(t) { if (CAPMODE === "none") return; const s = capText(t); if (CAPMODE !== "track") { c.font = `600 36px ${SANS}`; c.textAlign = "center"; c.fillStyle = INK; c.fillText(s, 960, 990); DZ.burnW = c.measureText(s).width; c.textAlign = "left"; } if (CAPMODE === "player" || CAPMODE === "track") playerBox(s); }
// a browser or YouTube player's caption box: each line about 5% of frame height, two lines, bottom center, dark box
function playerBox(s) { const fs = 42, lh = 54, words = s.split(" "); c.font = `400 ${fs}px Roboto,Arial,${SANS}`; const lines = [""]; words.forEach((w) => { const n = lines[lines.length - 1] + (lines[lines.length - 1] ? " " : "") + w; if (c.measureText(n).width > 980) lines.push(w); else lines[lines.length - 1] = n; }); const bw = Math.max(...lines.map((l) => c.measureText(l).width)) + 36, y1 = 1037; lines.forEach((l, i) => { const w = c.measureText(l).width + 36, y = y1 - (lines.length - i) * lh; c.fillStyle = "rgba(8,8,8,.78)"; c.fillRect(960 - w / 2, y, w, lh); c.fillStyle = "#FFFFFF"; c.textAlign = "center"; c.fillText(l, 960, y + lh * 0.74); c.textAlign = "left"; }); DZ.box = { x0: 960 - bw / 2, x1: 960 + bw / 2, y0: y1 - lines.length * lh, y1 }; }
'''+s[b:]
# fit + layouts
a=s.index('const DEF = {'); b=s.index('const CFG0 =')
s=s[:a]+r'''// fit the world (pillars on one axis, fabric centered between them) into a rectangle
const PX = 300, PY = -75, PH = 165, RX = 52;
function fit(x0, x1, y0, y1, o = {}) { const below = o.below ?? 40, px = o.px ?? PX, rx = o.rx ?? RX, py = o.py ?? PY, ph = o.ph ?? PH, topU = Math.max(165 + 16 * 9, -py + ph + rx * 0.42 + 46), botU = 165 + 10, k = Math.min((x1 - x0) / (2 * (px + rx)), (y1 - y0 - below) / (topU + botU), o.kmax || 9), cx = (x0 + x1) / 2, H0 = (topU + botU) * k + below, top = y0 + (y1 - y0 - H0) / 2, cy = top + topU * k; return { cx, cy, k, px, py, ph, rx, nameY: o.noName ? 0 : cy + botU * k + 34 }; }
const after = (w, d = 76) => w.nameY + d - 34;
const lgUnder = (w, o = {}) => ({ cx: w.cx, y: w.nameY + (o.d ?? 44), fs: o.fs ?? 22, lh: o.lh ?? 54, gap: o.gap ?? 34, rows: o.rows });
const ROW1 = [[1, 2, 0, 3, 4]];
const pillarless = 0;
const S_Y1 = 905; // everything except captions stays above this line
const LDEF = (name, d, fam) => ({ name, d, fam });
const DEF = {
  S50: LDEF("50/50 side by side", () => { const w = fit(972, 1896, 24, S_Y1, { below: 150 }); return { w, p: [{ t: "term", x: 24, y: 24, w: 924, h: S_Y1 - 24, fs: 28, lh: 40 }], lg: lgUnder(w) }; }, "side"),
  S40: LDEF("40/60 side by side (terminal 40, fabric 60)", () => { const w = fit(796, 1896, 24, S_Y1, { below: 150 }); return { w, p: [{ t: "term", x: 24, y: 24, w: 744, h: S_Y1 - 24, fs: 27, lh: 39 }], lg: lgUnder(w, { gap: 44 }) }; }, "side"),
  S30: LDEF("30/70 side by side (terminal 30, fabric 70)", () => { const w = fit(600, 1896, 24, S_Y1, { below: 110 }); return { w, p: [{ t: "term", x: 24, y: 24, w: 552, h: S_Y1 - 24, fs: 24, lh: 36, pad: 24 }], lg: lgUnder(w, { rows: ROW1, gap: 26, d: 42, fs: 20 }) }; }, "side"),
  S60: LDEF("60/40 side by side (terminal 60, fabric 40)", () => { const w = fit(1176, 1896, 24, S_Y1, { below: 150 }); return { w, p: [{ t: "term", x: 24, y: 24, w: 1128, h: S_Y1 - 24, fs: 30, lh: 42 }], lg: lgUnder(w, { fs: 20, gap: 22 }) }; }, "side"),
  B80: LDEF("80/20 fabric on top, terminal strip below", () => { const w = fit(300, 1620, 16, 716, { below: 40 }); return { w, p: [{ t: "term", x: 300, y: 730, w: 1320, h: 175, fs: 28, lh: 40, bar: 0, flat: 1 }], lgc: [{ x: 40, y: 500, kinds: [1, 2, 0], fs: 23 }, { x: 1640, y: 560, kinds: [3, 4], fs: 23 }] }; }, "stack"),
  B70: LDEF("70/30 fabric on top, terminal below", () => { const w = fit(300, 1620, 16, 630, { below: 36 }); return { w, p: [{ t: "term", x: 300, y: 640, w: 1320, h: 265, fs: 28, lh: 40, bar: 42 }], lgc: [{ x: 40, y: 450, kinds: [1, 2, 0], fs: 23 }, { x: 1640, y: 510, kinds: [3, 4], fs: 23 }] }; }, "stack"),
  T20: LDEF("20/80 terminal strip on top, fabric below", () => { const w = fit(300, 1620, 200, S_Y1, { below: 40 }); return { w, p: [{ t: "term", x: 300, y: 16, w: 1320, h: 175, fs: 28, lh: 40, bar: 0 }], lgc: [{ x: 40, y: 640, kinds: [1, 2, 0], fs: 23 }, { x: 1640, y: 700, kinds: [3, 4], fs: 23 }] }; }, "stack"),
  T30: LDEF("30/70 terminal on top, fabric below", () => { const w = fit(300, 1620, 288, S_Y1, { below: 36 }); return { w, p: [{ t: "term", x: 300, y: 16, w: 1320, h: 265, fs: 28, lh: 40, bar: 42 }], lgc: [{ x: 40, y: 660, kinds: [1, 2, 0], fs: 23 }, { x: 1640, y: 720, kinds: [3, 4], fs: 23 }] }; }, "stack"),
};
'''+s[b:]
# renderAt
s=s.replace('if (L.preW) L.preW(t); drawWorld(t, L.w); if (L.lg) legend(t, L.lg); for (const o of L.p) {','if (L.preW) L.preW(t); drawWorld(t, L.w); if (L.lg) legend(t, L.lg); if (L.lgc) L.lgc.forEach((q) => legendCol(t, q)); if (!qs.get("nopanels")) for (const o of L.p) {')
s=s.replace('window.probe = (t) => { window.renderAt(t); return { world: DZ.world,','window.probe = (t) => { window.renderAt(t); return { burnW: DZ.burnW, box: DZ.box, world: DZ.world,')
s=s.replace('window.LAYOUT_IDS','window.PANELS = () => DEF[LID].d(6.2).p; window.LAYOUT_IDS')
s=s.replace('const L = DEF[LID].d(9.7); const pf','window.renderAt(9.7); const L = DEF[LID].d(9.7); const pf')
open('lab.js','w').write(s)
