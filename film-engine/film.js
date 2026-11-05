// Teleion Labs home film. One function, renderAt(t): same picture live and in the MP4. Canvas 2D, no library, every frame depends only on t.
// Style comes from ?style=iso|flat|kinetic|mix. Words and timing come from data.js, built from the presenter voice.
(() => {
  const PAPER = "#F5F2EA", CARD = "#FFFDF8", TONE = /[?&]world=1/.test(location.search) ? "#F5F2EA" : "#EFEBDF", LINE = "#E2DCCF", RULE = "#8A8476", INK = "#11161F", MUTED = "#565A5F", BLUE = "#24519B", RUST = "#A23E1C", PALE = "#DDE5F2", SAND = "#F3E2D8";
  const SANS = "Inter,'Liberation Sans',Arial,sans-serif", MONO = "ui-monospace,Menlo,Consolas,'Liberation Mono',monospace";
  const cv = document.getElementById("c"), c = cv.getContext("2d", { alpha: false });
  const MAINF = /[?&]main=1/.test(location.search), FEED9 = /[?&]feed=1/.test(location.search), MK9 = [[-0.044, -0.056], [5.662, 5.651], [11.381, 11.403], [13.618, 13.61], [14.502, 14.496], [16.287, 16.284], [17.979, 17.946], [18.396, 18.362], [23.44, 23.948], [23.727, 24.235], [25.356, 25.91], [28.258, 28.534], [29.233, 29.512], [29.921, 30.116], [31.568, 31.729], [34.885, 35.054], [36.818, 36.96], [45.818, 45.962], [47.089, 47.135], [48.409, 48.481], [50.695, 50.859], [51.572, 51.731], [57.582, 57.745], [59.484, 59.715], [62.014, 62.252], [63.294, 63.533], [67.301, 67.571], [69.29, 69.445], [69.567, 69.714], [71.195, 71.372], [73.113, 73.287], [77.121, 77.294], [78.313, 78.506], [83.316, 83.511], [86.079, 86.208], [86.352, 86.479], [88.886, 88.942], [90.463, 90.519], [93.483, 93.54], [96.19, 96.255], [96.467, 96.543], [98.982, 99.109], [99.854, 99.985], [103.89, 103.987]], MAP9 = (x) => { const k = MK9; if (x <= k[0][0]) return k[0][1]; for (let i = 0; i < k.length - 1; i++) if (x <= k[i + 1][0]) return k[i][1] + ((k[i + 1][1] - k[i][1]) * (x - k[i][0])) / (k[i + 1][0] - k[i][0] || 1); return k[k.length - 1][1]; }, WORLD = /[?&]world=1/.test(location.search), CARDM = /[?&]eranos=card/.test(location.search); let NOC9 = false, LIFTON = false; const qs = new URLSearchParams(location.search), STYLE = qs.get("style") || "iso", CAPS = qs.get("captions") !== "0";
  window.DUR = 180; 
  // Treatment: a seed picks layout, ground, object shapes and transitions. Seed 0 is the base design. The set is always two databases and an OmniNode.
  const SEED = parseInt(qs.get("seed") || "0", 10), CLIP = qs.get("clip") === "1";
  let _r = (SEED * 2654435761 + 12345) >>> 0; const rng = () => { _r = (_r + 0x6D2B79F5) >>> 0; let z = _r; z = Math.imul(z ^ (z >>> 15), z | 1); z ^= z + Math.imul(z ^ (z >>> 7), z | 61); return ((z ^ (z >>> 14)) >>> 0) / 4294967296; };
  const pick = (a) => a[Math.floor(rng() * a.length)];
  const V = SEED === 0 ? { mirror: false, ground: PAPER, db: "discs", node: 8, chip: "cube", u: 92, ts: 1, trans: null, pageFrom: "up", center: false, kalign: "left", kalpha: 0.24, ui: 0 } :
    { mirror: rng() < 0.5, ground: pick([PAPER, CARD, TONE]), db: pick(["discs", "slabs", "drum"]), node: pick([8, 6, 4]), chip: pick(["cube", "card", "tall"]), u: pick([92, 86, 96]), ts: pick([1, 1.1, 0.92]), trans: pick(["wipeL", "wipeU", "flood", "wipeD", "iris"]), pageFrom: pick(["up", "left", "right"]), center: rng() < 0.4, kalign: pick(["left", "center"]), kalpha: pick([0.14, 0.24, 0.34]), ui: Math.floor(rng() * 4) };
  const DIR = qs.get("dir") || "";
  if (qs.get("mirror") === "1") V.mirror = true;
  // Motion sets: how things move, not what they say.
  const MOTIONS = { m1: { name: "calm", k: 1, camK: 1, camT: 1.1 }, m2: { name: "snappy", k: 0.68, camK: 1, camT: 0.5, cut: true }, m3: { name: "conveyor", k: 1, linear: true, flow: true, camK: 0.92, camT: 1.3 }, m4: { name: "hopping", k: 0.95, hop: 0.34, camK: 1, camT: 0.9 }, m5: { name: "drop-in build", k: 0.9, build: "drop", camK: 1, camT: 0.9 }, m6: { name: "slot and rise", k: 0.9, build: "rise", camK: 1, camT: 1 }, m7: { name: "camera-led", k: 0.95, camK: 1.32, camT: 1.5 }, m8: { name: "wide and still", k: 0.85, camK: 0, camT: 0.6, cut: true } };
  const MO = MOTIONS[qs.get("motion") || "m1"] || MOTIONS.m1;
  const MX = V.mirror ? -1 : 1, TX = V.mirror ? 1010 : 90, PX = V.mirror ? 1240 : 70; let GROUND = V.ground;
  const CHAPTER = { title: "#F5F2EA", hook: "#FBEEE4", three: "#EAF0F8", statement: "#F4EFDD", parts: "#E7EDF7", split: "#F7EADF", omninode: "#EAF1E6", four: "#F6F0D8", live: "#EFEBDF", connect: "#E7EDF7" };
  const CHWORD = { parts: "Three parts", split: "Long-term", omninode: "OmniNodes", four: "What you get" };
  if (DIR) V.trans = { stack: "wipeU", cutaway: "iris", campus: "wipeL", parallax: "flood", chapters: "wipeD", closeup: "iris", sheets: "wipeU" }[DIR] || null;
  window.TREATMENT = V;
  const CUES = window.CUES, CAPTIONS = window.CAPTIONS;
  // Composition probe: every part and label is drawn through comp(), so tools/comp_check.py can measure it alone, or the frame without it.
  let COMPD = 0; const compIn = (fn) => { COMPD++; try { fn(); } finally { COMPD--; } };
  const comp = (id, kind, fn0) => { const fn = () => compIn(fn0); if (COMPD) { fn0(); return; } const C = window.__CMP; if (C) { C.seen[id] = kind; if (C.only !== undefined && C.only !== id) return; if (C.skip === id) return; if (C.tint === id) { const f0 = c.filter; c.filter = "brightness(0.55) sepia(1) saturate(30)"; fn(); c.filter = f0; return; } } fn(); };
  const clamp = (x) => Math.max(0, Math.min(1, x)), mix = (a, b, k) => a + (b - a) * k;
  // Closed forms of the playbook's curves.
  const soft = (x) => (x = clamp(x), (1 - Math.exp(-3.41 * x)) / (1 - Math.exp(-3.41)));
  const exit = (x) => Math.pow(clamp(x), 2.6);
  const inOut = (x) => { x = clamp(x); const a = x ** 1.42, b = (1 - x) ** 1.42; return a / (a + b || 1); };
  const pop = (x) => { x = clamp(x); const f = (t) => 1 - Math.exp(-2.67 * t) * (Math.cos(4.36 * t) + (2.67 / 4.36) * Math.sin(4.36 * t)); return f(x) / f(1); };
  const F = (n) => n / 30, seg = (t, a, d) => (t - a) / d;
  // When a word is spoken: M("parts","Second,") is the voice's own time, so a new voice moves the picture with it.
  const M = (scene, word, nth = 0) => { let n = 0; for (const w of (CUES[scene] || CUES.omninode).words) if (w[0] === word && n++ === nth) return w[1]; return (CUES[scene] || CUES.omninode).start; };
  const S = (k) => (CUES[k] || CUES.omninode).start, E = (k) => (CUES[k] || CUES.omninode).start + (CUES[k] || CUES.omninode).seconds;

  // ------------------------------------------------------------ images
  const IMG = {}; const load = (n) => new Promise((ok) => { const i = new Image(); i.onload = () => { IMG[n] = i; ok(); }; i.onerror = () => { console.error("image", n); ok(); }; i.src = `pages/${n}.jpg`; });
  const fonts = [["400", "inter-400"], ["600", "inter-600"], ["700", "inter-700"]].map(([w, f]) => new FontFace("Inter", `url(fonts/${f}.woff2)`, { weight: w }).load().then((x) => document.fonts.add(x)));
  window.READY = Promise.all([...fonts, ...["home", "ngo", "result", "process", "dash", "help", "library", "example"].map(load)]);

  // ------------------------------------------------------------ the set: true 30 degree isometric, or the same places drawn flat
  const COS = Math.cos(Math.PI / 6);
  let cam = { x: 770, y: 452, u: 104 }, FLAT = false;
  // The camera. iso is the true 30 degree view; the others are real orthographic cameras: yaw around the set, pitch looking down.
  const VIEWS = { iso: { iso: true }, "front-20": { yaw: 0, pitch: 20, front: true }, "front-35": { yaw: 0, pitch: 35, front: true }, "front-three-quarter": { yaw: 15, pitch: 25, front: true }, "high-three-quarter": { yaw: 30, pitch: 45 }, "front-orbit": { yaw: 0, pitch: 26, orbit: 9, front: true } };
  const VN = VIEWS[qs.get("view")] ? qs.get("view") : "iso", VW = VIEWS[VN], FRONT = !!VW.front, TOPH = !VW.iso;
  let VS = Math.SQRT1_2, VC = Math.SQRT1_2, KX = 1.2247, KY = 0.7071, KZ = 1;
  const setYaw = (deg) => { if (VW.iso) return; const a = (deg * Math.PI) / 180, b = (VW.pitch * Math.PI) / 180; VS = Math.sin(a); VC = Math.cos(a); KX = 1; KY = Math.sin(b); KZ = Math.cos(b); };
  setYaw(VW.yaw || 0);
  const P = (x, y, z = 0) => FLAT ? [cam.x + MX * (x - y) * COS * cam.u, cam.y + (x + y) * 0.5 * cam.u] : [cam.x + MX * (x * VC - y * VS) * KX * cam.u, cam.y + (x * VS + y * VC) * KY * cam.u - z * KZ * cam.u];
  const depth = (x, y) => x * VS + y * VC;
  const camAt = (x, y, u) => ({ x: V.mirror ? 1920 - x : x, y, u: u * (V.u / 92) });
  const path = (pts) => { c.beginPath(); pts.forEach((p, i) => (i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1]))); c.closePath(); };
  const poly = (pts, fill) => { path(pts); c.fillStyle = fill; c.fill(); };
  const shade = (a) => `rgba(17,22,31,${a})`, warm = (a) => `rgba(74,64,48,${a})`;
  const rr = (x, y, w, h, r) => { c.beginPath(); c.roundRect(x, y, w, h, r); };
  function softShadow(x, y, w, d, z = 0) { // one soft shadow: wide, faint layers falling toward +x
    if (FLAT || window.__CMP) return; const sx = x + 0.3 + z * 0.3, sy = y + 0.1 + z * 0.1;
    for (let i = 5; i >= 0; i--) { const e = 0.05 + i * 0.09; poly([P(sx - e, sy - e), P(sx + w + e, sy - e), P(sx + w + e, sy + d + e), P(sx - e, sy + d + e)], warm(0.04)); }
  }
  function discShadow(x, y, r) { if (FLAT || window.__CMP) return; const [a, b] = P(x + 0.18, y + 0.18, 0), rx = r * KX * cam.u, ry = r * KY * cam.u; for (let i = 4; i >= 0; i--) { c.beginPath(); c.ellipse(a, b, rx + i * 9, ry + i * 6, 0, 0, Math.PI * 2); c.fillStyle = warm(0.045); c.fill(); } }
  function box(x, y, z, w, d, h, top, edge = 0.22) {
    if (FLAT) { const [a, b] = P(x + w / 2, y + d / 2, 0), px = (w + d) * 0.5 * cam.u * 0.92; rr(a - px / 2, b - px / 2, px, px, Math.min(10, px * 0.2)); c.fillStyle = top; c.fill(); c.strokeStyle = shade(edge); c.lineWidth = 1.5; c.stroke(); return; }
    const front = [P(x, y + d, z + h), P(x + w, y + d, z + h), P(x + w, y + d, z), P(x, y + d, z)], right = [P(x + w, y, z + h), P(x + w, y + d, z + h), P(x + w, y + d, z), P(x + w, y, z)], lid = [P(x, y, z + h), P(x + w, y, z + h), P(x + w, y + d, z + h), P(x, y + d, z + h)];
    poly(front, top); poly(front, shade(0.07)); poly(right, top); poly(right, shade(0.15)); poly(lid, top);
    c.strokeStyle = shade(edge); c.lineWidth = 1.5; c.lineJoin = "round";
    for (const f of [front, right, lid]) { path(f); c.stroke(); }
  }
  // A database: stacked discs. r in floor units, growth g 0..1 raises the walls.
  function database(x, y, r, g, accent, level) {
    const hEach = 0.62, gap = 0.12, n = 3, [a, b0] = P(x, y, 0), rx = r * KX * cam.u, ry = r * KY * cam.u;
    if (FLAT) {
      const w = rx * 1.5, h = 3 * 66 * Math.max(0.05, g), bx = a - w / 2, by = b0 - h / 2 + 10;
      for (let i = 0; i < 3; i++) { const yy = by + (2 - i) * (h / 3); rr(bx, yy, w, h / 3 - 8, 12); c.fillStyle = CARD; c.fill(); c.strokeStyle = shade(0.22); c.lineWidth = 1.5; c.stroke(); c.fillStyle = accent; c.fillRect(bx + 18, yy + (h / 3 - 8) / 2 - 3, 60, 6); }
      return by - 8;
    }
    discShadow(x, y, r);
    if (V.db === "slabs") { const R = r * 0.86; for (let i = 0; i < 3; i++) { box(x - R, y - R, i * 0.72 * g, 2 * R, 2 * R, 0.6 * g, CARD); const L = P(x - R + 0.25, y + R, i * 0.72 * g + 0.34 * g), L2 = P(x + R - 0.25, y + R, i * 0.72 * g + 0.34 * g); c.strokeStyle = accent; c.lineWidth = 4; c.beginPath(); c.moveTo(L[0], L[1]); c.lineTo(L2[0], L2[1]); c.stroke(); } return 2.04 * g; }
    let z = 0, topZ = 0; const hEach2 = V.db === "drum" ? 2.04 : 0;
    for (let i = 0; i < (V.db === "drum" ? 1 : n); i++) {
      const h = (V.db === "drum" ? hEach2 : hEach) * g, b = P(x, y, z)[1], t = P(x, y, z + h)[1];
      const gr = c.createLinearGradient(a - rx, 0, a + rx, 0); gr.addColorStop(0, "#F4F0E6"); gr.addColorStop(0.45, "#FFFDF8"); gr.addColorStop(1, "#D8D2C4");
      c.beginPath(); c.ellipse(a, b, rx, ry, 0, 0, Math.PI); c.lineTo(a - rx, t); c.ellipse(a, t, rx, ry, 0, Math.PI, 0, true); c.closePath(); c.fillStyle = gr; c.fill(); c.strokeStyle = shade(0.22); c.lineWidth = 1.5; c.stroke();
      c.beginPath(); c.ellipse(a, b - h * 0.28 * cam.u, rx, ry, 0, 0.12 * Math.PI, 0.88 * Math.PI); c.strokeStyle = accent; c.lineWidth = 4; c.stroke();
      c.beginPath(); c.ellipse(a, t, rx, ry, 0, 0, Math.PI * 2); c.fillStyle = CARD; c.fill(); c.strokeStyle = shade(0.22); c.lineWidth = 1.5; c.stroke();
      z += h + gap * g; topZ = z - gap * g;
    }
    return topZ;
  }
  function octo(x, y, z, r, h, top, side) { // the OmniNode's body: a prism
    const NS = V.node, pts = (zz) => [...Array(NS)].map((_, i) => { const a = Math.PI / NS + (i * 2 * Math.PI) / NS; return P(x + Math.cos(a) * r, y + Math.sin(a) * r, zz); });
    if (FLAT) { const [a, b] = P(x, y), px = r * 1.6 * cam.u; rr(a - px / 2, b - px / 2, px, px, 26); c.fillStyle = top; c.fill(); c.strokeStyle = side; c.lineWidth = 4; c.stroke(); return; }
    const low = pts(z), up = pts(z + h);
    [...Array(NS).keys()].sort((p, q) => (low[p][1] + low[(p + 1) % NS][1]) - (low[q][1] + low[(q + 1) % NS][1])).forEach((i, k) => { const j = (i + 1) % NS, f = [low[i], low[j], up[j], up[i]]; poly(f, top); poly(f, shade(0.05 + 0.1 * Math.max(0, k / NS))); c.strokeStyle = shade(0.2); c.lineWidth = 1.5; path(f); c.stroke(); });
    poly(up, top); c.strokeStyle = side; c.lineWidth = 4; path(up); c.stroke();
  }
  function onPlane(x, y, z, fn) { // text and icons lying flat on a top surface
    const [ox, oy] = P(x, y, z); c.save();
    if (FLAT) c.translate(ox, oy); else c.transform(COS, 0.5, -COS, 0.5, ox, oy);
    fn(); c.restore();
  }
  const font = (w, s, f = SANS) => { c.font = `${w} ${s}px ${f}`; };
  function pill(s0, x0, y0, o0 = {}) { comp("pill:" + s0, "label", () => pill0(s0, x0, y0, o0)); }
  const GLASS = /^ev[cltouqwr]/.test(window.VOICE_KEY);
  function frost(x, y, w, h, r, k = 0.55) { if (MAINF) return; if (window.__CMP) { rr(x, y, w, h, r); c.fillStyle = CARD; c.fill(); return; } c.save(); rr(x, y, w, h, r); c.clip(); c.filter = "blur(14px) saturate(1.35)"; const m = 40, x0 = Math.max(0, x - m), y0 = Math.max(0, y - m), x1 = Math.min(1920, x + w + m), y1 = Math.min(1080, y + h + m); c.drawImage(cv, x0, y0, x1 - x0, y1 - y0, x0, y0, x1 - x0, y1 - y0); c.filter = "none"; c.fillStyle = `rgba(250,246,236,${k})`; c.fillRect(x, y, w, h); c.restore(); rr(x, y, w, h, r); c.strokeStyle = "rgba(255,255,255,.8)"; c.lineWidth = 1.5; c.stroke(); }
  let ONT = []; const normW = (q) => q.toLowerCase().replace(/[^a-z0-9 ]/g, " ").split(/\s+/).filter((w) => w.length > 1);
  const dupOf = (cap) => { const cw = normW(cap); if (!cw.length) return null; for (const q of ONT) { const w = new Set(normW(q)); let n = 0; for (const x of cw) if (w.has(x)) n++; if (n / cw.length >= 0.6) return q; } return null; };
  function pill0(s, x, y, o = {}) { if (o.a === undefined || o.a > 0.05) ONT.push(s); if (MAINF) { c.save(); if (o.a !== undefined) c.globalAlpha *= o.a; font(o.w || 600, o.size || 28); c.fillStyle = o.color || INK; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(s, x, y); c.restore(); return; } // screen-flat label; x,y is center
    const size = o.size || 28, w0 = (font(o.w || 600, size), c.measureText(s).width), w = w0 + size * 1.1, h = size * 1.72, a = o.a === undefined ? 1 : o.a;
    if (a <= 0) return; x = Math.max(62 + w / 2, Math.min(1858 - w / 2, x)); y = Math.max(62 + h / 2, y);
    c.save(); c.globalAlpha *= a; if (GLASS) { frost(x - w / 2, y - h / 2, w, h, h / 2); if (o.lw) { rr(x - w / 2, y - h / 2, w, h, h / 2); c.strokeStyle = o.stroke || shade(0.22); c.lineWidth = o.lw; c.stroke(); } } else { rr(x - w / 2, y - h / 2, w, h, h / 2); c.fillStyle = o.fill || CARD; c.fill(); c.strokeStyle = o.stroke || shade(0.22); c.lineWidth = o.lw || 1.5; c.stroke(); }
    c.fillStyle = o.color || INK; c.textAlign = "left"; c.textBaseline = "alphabetic"; c.fillText(s, x - w0 / 2, y + size * 0.36); c.restore();
  }
  // Text with wrapping. Returns the next baseline.
  function lines(s, w, size, weight) { font(weight, size); const out = []; let cur = ""; for (const word of s.split(" ")) { const t = cur ? cur + " " + word : word; if (c.measureText(t).width > w && cur) { out.push(cur); cur = word; } else cur = t; } if (cur) out.push(cur); return out; }
  function rise(s, x, y, size, weight, start, o = {}) { let r0; comp("text:" + s.slice(0, 24), "heading", () => { r0 = rise0(s, x, y, size, weight, start, o); }); return r0; }
  function rise0(s, x, y, size, weight, start, o = {}) { if (o.t === undefined || o.t >= start) ONT.push(s); // masked rise line by line, word by word
    const w = o.w || 1200, lh = size * (o.lh || 1.18), gap = o.center && GLASS ? 0 : o.gap === undefined ? 3 : o.gap, acc = o.accent || []; let yy = y, n = 0;
    c.textBaseline = "alphabetic"; c.textAlign = "left";
    for (const ln of lines(s, w, size, weight)) {
      font(weight, size); const lw = c.measureText(ln).width; let px = o.center ? x - lw / 2 : x;
      for (const word of ln.split(" ")) {
        const wd = c.measureText(word).width, k = soft(seg(o.t, start + F(n * gap), F(14)));
        if (k > 0) { c.save(); c.beginPath(); c.rect(px - 6, yy - size * 1.0, wd + 12, size * 1.28); c.clip(); c.fillStyle = acc.some((a) => word.replace(/[.,?!]/g, "") === a) ? RUST : o.color || INK; c.fillText(word, px, yy + (1 - k) * size * 1.15); c.restore(); }
        px += wd + c.measureText(" ").width; n++;
      }
      yy += lh;
    }
    return yy;
  }
  // ------------------------------------------------------------ places in the set (floor units). T and O are the two databases.
  const CAMPUS = DIR === "campus", TD = CAMPUS ? [-11, 0] : [-4.3, 0], NODE = [0, 0], AUD = CAMPUS ? [9.5, 0] : [4.1, 0], OD = CAMPUS ? [9.5, -10] : [4.1, -4.3], CORNER = CAMPUS ? [0, -10] : [0, -4.3], TOPZ = 2.05, NZ = 0.95;
  const RAILS = [[TD, NODE], [NODE, AUD], [AUD, OD], [OD, CORNER], [CORNER, NODE]];
  const SEC = CAMPUS ? { x0: -13.4, x1: 11.9, y0: -12.4, y1: 2.0 } : { x0: -6.3, x1: 6.0, y0: -6.3, y1: 1.2 }, AGENT = CAMPUS ? [-15.2, 0] : [-7.9, 0], META = CAMPUS ? [0, 3.2] : [0, 2.3];
  const V3 = (p, z = 0.12) => [p[0], p[1], z];
  // Choreography: every move and stock change is listed once, from the voice's own word times.
  const moves = [], stock = []; // move: {type,route,t0,t1}. stock: {t,T,O}
  const mv = (type, route, t0, dur) => moves.push({ type, route, t0, t1: t0 + dur });
  const dT = (t, n) => stock.push({ t, T: n, O: 0 }), dO = (t, n) => stock.push({ t, T: 0, O: n });
  const tTop = [TD[0], TD[1], TOPZ], oTop = [OD[0], OD[1], TOPZ], nIn = [0, 0, 0.25], aIn = [AUD[0], 0, 0.25], rT = V3(TD), rN = V3(NODE), rA = V3(AUD), rO = V3(OD), rC = V3(CORNER);
  const tToNode = [tTop, [TD[0], 0, 0.14], [-1, 0, 0.14], nIn], nodeToAud = [nIn, [1, 0, 0.14], [AUD[0] - 1, 0, 0.14], aIn], audToO = [aIn, [AUD[0], -1, 0.14], [OD[0], OD[1] + 1.3, 0.14], [OD[0], OD[1], 0.2], oTop], oToNode = [oTop, [OD[0], OD[1], 0.2], [1, CORNER[1], 0.14], [0, CORNER[1], 0.14], [0, -1.1, 0.14], nIn];
  function loop(at, o = {}) { // one Task through the set
    const w = o.work === undefined ? 1.1 : o.work; let t = at;
    mv("task", tToNode, t, 1.0); dT(t, -1);
    if (o.object !== false) mv("obj", oToNode, t + 0.1, 1.15);
    t += 1.2 + w;
    mv("task", nodeToAud, t, 0.75); t += 0.8; mv("obj", audToO, t + (o.audit === undefined ? 0.35 : o.audit), 0.85); dO(t + (o.audit === undefined ? 0.35 : o.audit) + 0.85, 1);
    return t + 1.2;
  }
  const B = {}; // named beats, filled below
  const tset = (t, n) => stock.push({ t, set: n, O: 0, T: 0 });
  function plan() { Object.assign(B, { first: 1e9, second: 1e9, third: 1e9, together: 1e9, pPick: 1e9, pSplit: 1e9, heldUntil: 0, powered: 1e9, sSep: 1e9, sSplits: 1e9, sPicks: 1e9, sWait: 1e9, done: [], oDet: 1e9, oModel: 1e9, oReuse: 1e9, oLearn: 1e9, oImprove: 1e9, feedAt: 1e9, fKnow: 1e9, fReuse: 1e9, fLong: 1e9, fBetter: 1e9, fCheaper: 1e9, fFewer: 1e9, reusable: 1e9, conv: 1e9, gives: 1e9, every: 1e9, direct: 1e9 }); }
  const stockAt = (t) => { let T = 0, O = 0; for (const e of stock) { if (e.t > t) break; if (e.set !== undefined) T = e.set; else T += e.T; O += e.O; } return { T: Math.max(0, T), O: Math.min(11, Math.max(0, O)) }; };
  const along = (route, k) => { const ls = []; let tot = 0; for (let i = 0; i < route.length - 1; i++) { const a = route[i], b = route[i + 1], l = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]); ls.push(l); tot += l; } let d = k * tot; for (let i = 0; i < ls.length; i++) { if (d <= ls[i] || i === ls.length - 1) { const f = ls[i] ? d / ls[i] : 0, a = route[i], b = route[i + 1]; return [mix(a[0], b[0], f), mix(a[1], b[1], f), mix(a[2], b[2], f)]; } d -= ls[i]; } return route[0]; };
  function chip(x, y, z, kind, s = 0.5) {
    const col = kind === "task" ? BLUE : RUST;
    if (FLAT) { const [a, b] = P(x, y), px = 36 * (s / 0.5); rr(a - px / 2, b - px / 2 - z * 14, px, px, 8); c.fillStyle = col; c.fill(); return; }
    const hh = V.chip === "card" ? 0.08 : V.chip === "tall" ? 0.46 : kind === "task" ? 0.2 : 0.3; box(x - s / 2, y - s / 2, z, s, s, hh, col, 0.3);
  }
  function rail(a, b, on, t, dir = 1) {
    const w = 0.34, dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy), ux = dx / l, uy = dy / l, nx = -uy * w, ny = ux * w;
    if (FLAT) { const [p, q] = [P(a[0], a[1]), P(b[0], b[1])]; c.strokeStyle = on ? PALE : LINE; c.lineWidth = 22; c.lineCap = "round"; c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(q[0], q[1]); c.stroke(); c.lineCap = "butt"; }
    else {
      poly([P(a[0] + nx, a[1] + ny, 0.06), P(b[0] + nx, b[1] + ny, 0.06), P(b[0] - nx, b[1] - ny, 0.06), P(a[0] - nx, a[1] - ny, 0.06)], on ? PALE : "#E8E2D4");
      c.strokeStyle = shade(0.16); c.lineWidth = 1.5; path([P(a[0] + nx, a[1] + ny, 0.06), P(b[0] + nx, b[1] + ny, 0.06), P(b[0] - nx, b[1] - ny, 0.06), P(a[0] - nx, a[1] - ny, 0.06)]); c.stroke();
    }
    // chevrons always creep along the rail, slowly, so the set is never frozen
    const step = 0.85, off = (t * (on ? 0.9 : 0.22)) % step;
    c.strokeStyle = on ? BLUE : RULE; c.lineWidth = 3; c.lineCap = "round"; c.globalAlpha *= on ? 0.75 : 0.45;
    for (let d = off + 0.6; d < l - 0.5; d += step) {
      const x = a[0] + ux * d, y = a[1] + uy * d, tip = P(x + ux * 0.14, y + uy * 0.14, 0.07), p1 = P(x - ux * 0.1 + nx * 0.5, y - uy * 0.1 + ny * 0.5, 0.07), p2 = P(x - ux * 0.1 - nx * 0.5, y - uy * 0.1 - ny * 0.5, 0.07);
      c.beginPath(); c.moveTo(p1[0], p1[1]); c.lineTo(tip[0], tip[1]); c.lineTo(p2[0], p2[1]); c.stroke();
    }
    c.lineCap = "butt"; c.globalAlpha /= on ? 0.75 : 0.45;
  }
  const faded = (a, fn) => { const g = c.globalAlpha; c.globalAlpha = g * a; fn(); c.globalAlpha = g; };
  const growth = (t, at) => soft(seg(t, at, F(16)));
  function modeAt(t) {
    if (t >= S("four")) return t >= B.fCheaper - 0.2 && t < S("live") ? { name: "Cheaper model", col: BLUE } : null;
    if (t < S("omninode")) return null;
    if (t >= B.oLearn) return { name: "Continuously learning", col: BLUE };
    if (t >= B.oReuse) return { name: "Reuse", col: RUST };
    if (t >= B.oModel) return { name: "Non-deterministic: Muse Spark", col: BLUE };
    if (t >= B.oDet) return { name: "Deterministic", col: INK };
    return null;
  }
  // Floor plate: the one ground for the technical act, with the rails on it.
  function section(t) { // Teleion Fabric is a bounded section that holds the nodes
    const a = soft(seg(t, S("parts"), F(14))), q = [P(SEC.x0, SEC.y0), P(SEC.x1, SEC.y0), P(SEC.x1, SEC.y1), P(SEC.x0, SEC.y1)];
    if (DIR === "parallax") { faded(a * 0.8, () => poly(q, CARD)); c.strokeStyle = BLUE; c.lineWidth = 4; c.lineJoin = "round"; faded(a, () => { path(q); c.stroke(); }); return; }
    faded(a, () => { poly(q, CARD); c.strokeStyle = BLUE; c.lineWidth = 4; c.lineJoin = "round"; path(q); c.stroke(); });
  }
  let QUIET = false;
  function drawSet(t) {
    FLAT = STYLE === "flat";
    const pS = S("parts"), tB = pS + 0.45, oB = pS + 0.7, nB = pS + 0.95, aB = B.sSep - 0.5;
    // Lit one at a time while the voice is on it. Everything else steps back.
    let focus = null;
    if (t >= B.first && t < B.second) focus = "T"; else if (t >= B.second && t < B.third) focus = "O"; else if (t >= B.third && t < B.together) focus = "N";
    const dim = (k) => (focus && focus !== k ? 0.26 : 1);
    comp("platform", "ground", () => section(t));
    if (CAMPUS) [[TD, "#E7EDF7"], [NODE, "#EEF1F8"], [OD, "#F7EADF"], [AUD, "#F7EADF"]].forEach(([q, col]) => { const a = soft(seg(t, pS + 0.2, F(14))); faded(a, () => { box(q[0] - 2.5, q[1] - 2.5, -0.02, 5, 5, 0.06, col, 0.14); }); });
    // Any agent connects from outside the section; Meta models power Fabric Intelligence from outside it.
    faded(dim("-") * soft(seg(t, pS + 1.2, F(12))), () => { rail(AGENT, [TD[0] - 1.65, 0], true, t); softShadow(AGENT[0] - 0.7, -0.7, 1.4, 1.4, 0); box(AGENT[0] - 0.7, -0.7, 0, 1.4, 1.4, 0.55, CARD); });
    if (t >= B.powered - 0.4) faded(soft(seg(t, B.powered - 0.4, F(12))), () => { rail(META, [0, 0.9], true, t); softShadow(META[0] - 0.55, META[1] - 0.55, 1.1, 1.1, 0); box(META[0] - 0.55, META[1] - 0.55, 0, 1.1, 1.1, 0.5, PALE); });
    const railShown = [true, t >= aB, t >= aB, t >= pS, t >= pS];
    RAILS.forEach(([a, b], i) => { if (!railShown[i]) return; const at = i === 0 || i > 2 ? pS + 0.9 : aB, k = soft(seg(t, at, F(14))); if (k <= 0) return; const end = [mix(a[0], b[0], k), mix(a[1], b[1], k)]; faded(i === 0 ? dim("T") : i > 2 ? dim("O") : 1, () => rail(a, end, moving(t, i), t)); });
    const st = stockAt(t);
    if (t >= tB) comp("Tasks db", "component", () => faded(dim("T"), () => { const g = growth(t, tB); database(TD[0], TD[1], 1.65, g, BLUE); drawStockT(t, st.T, g); }));
    if (t >= oB) comp("Objects db", "component", () => faded(dim("O"), () => { const g = growth(t, oB); database(OD[0], OD[1], 1.65, g, RUST); drawStockO(t, st.O, g); }));
    if (t >= nB) comp("OmniNode 0", "component", () => faded(dim("N"), () => drawNode(t, growth(t, nB), NODE[0], NODE[1], 1.25, BLUE, "OmniNode")));
    if (t >= aB) comp("Audit gate", "component", () => drawAudit(t, growth(t, aB)));
    for (const m of moves) if (t >= m.t0 && t < m.t1) { const k = inOut((t - m.t0) / (m.t1 - m.t0)), p = along(m.route, k); chip(p[0], p[1], p[2], m.type === "task" ? "task" : "obj"); }
    if (t >= B.pPick + 1.2 && t < B.heldUntil) chip(-1.5, 0, 0.14, "task");
    if (!QUIET) { drawLabels(t, dim, focus); if (t >= B.reusable && t < B.third && DIR !== "closeup") labelsObjects(t); if (t >= B.conv && t < B.gives) labelsIntel(t); drawLong(t); }
    FLAT = false;
  }
  function setBehind(t, t0, o = {}) { // the same set, still working, stepping back so the words can land
    const r = soft((t - t0) / 2.2), u = mix(92, o.u || 58, r), a = (o.a === undefined ? 0.55 : o.a), leave = o.leave === undefined ? 0 : soft(seg(t, o.leave, 0.7));
    cam = camAt(960 - 1.85 * u, mix(585, o.y || 720, r) + leave * 260, u / (V.u / 92));
    if (STYLE === "iso" && TERR) { if (!TR) terBuild(); terCam(TR.end); c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); const k9 = o.leave === undefined ? 0 : inOut((t - t0) / 1.1), dx9 = k9 * 1100; TNN = true; if (k9 < 1) { terPillar(TCX - PILLX - dx9 + (TERM ? 960 - TCX : 0), PH, 10, "Durable Tasks", "Tasks pillar", null, K5[3][0]); terPillar(TCX + PILLX + dx9 + (TERM ? 960 - TCX : 0), PH, 10, "Durable Task Objects", "Objects pillar", null, K5[2][0]); } TNN = false; return; }
    if (STYLE === "iso") { if (!FSET) fabricBuild(); const F0 = FSET.fit, k0 = mix(0.98, o.scale || 0.68, r); camFit(F0, t, k0); cam.y += mix(0, (o.cy || 170), r) + leave * 320; drawFabric(t, true); const veil = mix(0, 1 - a, r) * (1 - leave) + leave; c.save(); c.globalAlpha = veil; c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); c.restore(); return; }
    QUIET = true; faded(mix(1, a, r) * (1 - leave), () => drawSet(t)); QUIET = false;
  }
  function kineticBehind(t, img) { const im = IMG[img]; if (!im) return; const sc = 0.78, dy = ((t * 16) % 500); c.save(); c.globalAlpha = 0.18; c.drawImage(im, 0, -dy * sc, im.width * sc, im.height * sc); c.restore(); }
  const moving = (t, i) => moves.some((m) => t >= m.t0 && t < m.t1 && railMatch(m, i));
  const railMatch = (m, i) => (i === 0 ? m.route === tToNode || m.route[0] === tTop : i === 1 ? m.route === nodeToAud : i === 2 ? m.route === audToO : m.route === oToNode);
  function drawStockT(t, n, g) {
    if (g < 1) return; const pos = [[-0.62, -0.62], [0, -0.62], [0.62, -0.62], [-0.62, 0.05], [0, 0.05], [0.62, 0.05]];
    pos.slice(0, Math.min(6, n)).forEach((q, i) => chip(TD[0] + q[0], TD[1] + q[1], TOPZ, "task", 0.48));
  }
  function drawStockO(t, n, g) { // Task Objects stack up: version on version
    if (g < 1) return; const cols = [[-0.55, -0.45], [0.55, -0.45], [0, 0.55]];
    for (let i = 0; i < n; i++) { const q = cols[i % 3], lvl = Math.floor(i / 3); chip(OD[0] + q[0], OD[1] + q[1], TOPZ + lvl * 0.34, "obj", 0.52); }
  }
  function drawNode(t, g, x, y, r, col, name) {
    if (FLAT) { octo(x, y, 0, r, 1, CARD, col); return; }
    softShadow(x - r, y - r, 2 * r, 2 * r, 0);
    octo(x, y, 0.02, r, NZ * g, CARD, col);
    const busy = moves.some((m) => t >= m.t1 - 0.1 && t < m.t1 + 1.1 && m.route[m.route.length - 1] === nIn);
    if (g >= 1) { // the working ring turns only while the node works
      const k = busy ? (t * 2.4) % (Math.PI * 2) : (t * 0.25) % (Math.PI * 2), [a, b] = P(x, y, NZ), rx = r * 0.72 * KX * cam.u, ry = r * 0.72 * KY * cam.u;
      c.lineWidth = 8; c.strokeStyle = LINE; c.beginPath(); c.ellipse(a, b, rx, ry, 0, 0, Math.PI * 2); c.stroke();
      c.strokeStyle = col; c.beginPath(); c.ellipse(a, b, rx, ry, 0, k, k + (busy ? 1.9 : 0.9)); c.stroke();
    }
  }
  function drawAudit(t, g) {
    const on = t >= B.sSep + 0.6;
    if (FLAT) { octo(AUD[0], AUD[1], 0, 1.0, 1, on ? SAND : CARD, RUST); }
    else { softShadow(AUD[0] - 1, AUD[1] - 1, 2, 2, 0); octo(AUD[0], AUD[1], 0.02, 1.0, 0.8 * g, on ? SAND : CARD, RUST); }
    if (g >= 1) { const [a, b] = P(AUD[0], AUD[1], FLAT ? 0 : 0.82), k = soft(seg(t, B.sSep + 0.6, F(12))); c.strokeStyle = RUST; c.lineWidth = 8; c.lineCap = "round"; c.lineJoin = "round"; c.beginPath(); const p0 = [a - 32, b + 2], p1 = [a - 8, b + 24], p2 = [a + 38, b - 26]; c.moveTo(p0[0], p0[1]); if (k < 0.4) c.lineTo(mix(p0[0], p1[0], k / 0.4), mix(p0[1], p1[1], k / 0.4)); else { c.lineTo(p1[0], p1[1]); c.lineTo(mix(p1[0], p2[0], (k - 0.4) / 0.6), mix(p1[1], p2[1], (k - 0.4) / 0.6)); } if (k > 0) c.stroke(); c.lineCap = "butt"; }
  }
  function drawLabels(t, dim, focus) {
    const f = (at) => soft(seg(t, at, F(12))), pS = S("parts"), big = t < S("split") || DIR === "closeup" ? 38 : 30;
    const [tx, ty] = P(TD[0], TD[1], FLAT ? 1.9 : TOPZ + 1.6), [ox, oy] = P(OD[0], OD[1], FLAT ? 1.9 : TOPZ + 1.6), [nx, ny] = P(0, 0, FLAT ? 1.4 : 2.05);
    const lit = (k, col) => (focus === k ? { fill: col, color: CARD, stroke: col } : { color: col, stroke: col });
    const hideT = t >= S("split") && t < B.sSplits + 1.0 ? 0 : 1;
    pill("Teleion Fabric", V.mirror ? 1920 - 1070 : 1070, 76, { a: f(pS + 0.1) * hideT * (cam.u > 110 ? 0 : 1), size: 36, w: 700, color: BLUE, stroke: BLUE, lw: 3, fill: CARD });
    const [ax0, ay0] = P(AGENT[0], AGENT[1], FLAT ? 1 : 1.4); pill("Any agent", ax0, ay0, { a: f(pS + 1.2) * dim("-") * hideT, size: 28 });
    pill("Durable Tasks", tx, ty - (FLAT ? 80 : 0), { a: f(pS + 0.5) * dim("T") * hideT, size: big, w: 700, ...lit("T", BLUE) });
    pill("Durable Task Objects", ox, oy - (FLAT ? 80 : 0), { a: f(pS + 0.75) * dim("O") * hideT, size: big, w: 700, ...lit("O", RUST) });
    const m = modeAt(t); const nodeName = t < S("split") ? "Fabric Intelligence" : m ? m.name : "OmniNode";
    pill(nodeName, nx, ny, { a: f(pS + 1) * dim("N") * hideT, size: big, w: 700, ...(m ? { color: m.col, stroke: m.col } : lit("N", BLUE)) });
    if (t >= B.powered - 0.3) { const [mx0, my0] = P(META[0], META[1], FLAT ? 1 : 1.25); pill("Meta models", mx0, my0, { a: f(B.powered - 0.3), size: 28, w: 700, color: BLUE, stroke: BLUE, fill: PALE }); }
    if (t >= B.sSep - 0.3) pill("A separate OmniNode", P(AUD[0], AUD[1])[0] + 262 * MX, P(AUD[0], AUD[1])[1] + 66, { a: f(B.sSep - 0.3), color: RUST, stroke: RUST });
    if (t >= B.feedAt - 0.1 && t < B.fReuse - 0.1) { const [px, py] = P(TD[0], TD[1], 0.1), a = f(B.feedAt - 0.1) * (1 - soft(seg(t, B.fReuse - 0.3, F(6)))); pill("Feed maintenance Task", px + 40 * MX, py + 118, { a, size: 26, color: BLUE, stroke: BLUE, fill: PALE }); const [qx, qy] = P(OD[0], OD[1], 0.1); pill("Its results: new Task Objects", qx - 30 * MX, qy + 128, { a: f(B.feedAt + 1.5) * (1 - soft(seg(t, B.fReuse - 0.3, F(6)))), size: 26, color: RUST, stroke: RUST, fill: SAND }); }
    if (t >= B.oImprove - 0.3 && t < B.oDet + 0.1) { const k = Math.floor(clamp((t - B.oImprove) / Math.max(0.5, B.oDet - B.oImprove - 0.3)) * 2.999) + 1; pill(`Version ${k}`, nx + 170 * MX, ny + 62, { a: f(B.oImprove - 0.3), size: 26, color: BLUE, stroke: BLUE, fill: PALE }); }
    if (t >= B.oLearn && t < S("four")) pill("Version 4", nx + 200 * MX, ny + 62, { a: f(B.oLearn), size: 26, color: BLUE, stroke: BLUE, fill: PALE });
  }
  function labelsObjects(t) {
    const names = ["Reusable code", "Agent kit configs", "News", "GitHub repos"], [ox] = P(OD[0], OD[1]), yy = 132;
    names.forEach((n, i) => { const at = B.reusable + i * 0.85, x = V.mirror ? ox + 40 + (i % 2) * 290 : ox - 330 + (i % 2) * 280, y = yy + Math.floor(i / 2) * 58; pill(n, x, y + 0, { a: soft(seg(t, at, F(10))), size: 25, color: RUST, stroke: RUST, fill: SAND }); });
    if (t >= B.every) { const [x, y] = P(OD[0], OD[1], TOPZ + 0.4); ["v1", "v2", "v3"].forEach((v, i) => pill(v, x + 196 * MX, y + 18 + i * 48 - 40, { a: soft(seg(t, B.every + i * 0.2, F(10))), size: 25, color: RUST, stroke: RUST })); }
  }
  function labelsIntel(t) {
    const names = ["Conversation", "Shimming", "Decisioning", "Search and retrieval"], [nx] = P(0, 0); let x = V.mirror ? nx - 860 : nx - 160;
    names.forEach((n, i) => { const at = B.conv + i * 0.55; font(600, 25); const w = c.measureText(n).width + 28; pill(n, x + w / 2 + 40, 140, { a: soft(seg(t, at, F(10))), size: 25, color: BLUE, stroke: BLUE, fill: PALE }); x += w + 18; });
  }
  function drawLong(t) {
    const s0 = S("split"), s1 = E("split"); if (t < s0 || t >= s1) return;
    const sp = B.sSplits, into = B.sSplits + 1.0;
    if (t < into + 0.2) {
      // One clean picture first: the job is far longer than one session. The set steps back.
      const veil = Math.min(soft(seg(t, s0, F(9))), 1 - soft(seg(t, into - 0.1, F(9))));
      c.save(); c.globalAlpha = 0.94 * veil; c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 880); c.restore();
      const X = 150, W = 1620, Y = 330, H = 120, k = soft(seg(t, s0 + 0.1, F(18))), parts = soft(seg(t, sp, 0.5)), fly = soft(seg(t, into - 0.35, 0.5));
      c.save(); c.globalAlpha = veil;
      if (parts <= 0) { rr(X, Y, W * k, H, 14); c.fillStyle = BLUE; c.fill(); if (k > 0.6) { font(700, 52); c.fillStyle = CARD; c.textAlign = "center"; c.fillText("One long job", X + W / 2, Y + 78); c.textAlign = "left"; } }
      else for (let i = 0; i < 6; i++) { const gap = 26 * parts, w = (W - gap * 5) / 6, x = X + i * (w + gap); rr(x, Y, w, H, 14); c.fillStyle = BLUE; c.fill(); font(700, 52); c.fillStyle = CARD; c.textAlign = "center"; c.fillText(String(i + 1), x + w / 2, Y + 78); c.textAlign = "left"; }
      const sess = soft(seg(t, B.sJob + 1.2, F(12))) * (1 - parts);
      if (sess > 0) { c.globalAlpha = veil * sess; c.strokeStyle = RUST; c.lineWidth = 5; c.beginPath(); c.moveTo(X, Y + H + 28); c.lineTo(X, Y + H + 56); c.lineTo(X + 340, Y + H + 56); c.lineTo(X + 340, Y + H + 28); c.stroke(); font(700, 38); c.fillStyle = RUST; c.fillText("One agent session", X, Y + H + 112); c.globalAlpha = veil; }
      if (parts > 0) { font(700, 38); c.fillStyle = BLUE; c.fillText("Small Tasks", X, Y + H + 76); }
      c.restore(); return;
    }
    // Then the same six Tasks, done one by one, while the set works.
    const a = soft(seg(t, into, F(10))), w = 86, h = 58, gap = 14, total = 6 * w + 5 * gap, x0 = V.mirror ? 60 : 1860 - total, y0 = 50;
    c.save(); c.globalAlpha = a; rr(x0 - 16, y0 - 12, total + 32, h + 24, 16); c.fillStyle = GROUND; c.fill();
    for (let i = 0; i < 6; i++) {
      const x = x0 + i * (w + gap), dn = t >= B.done[i], pop0 = soft(seg(t, B.done[i], F(8))), waits = i === 3 && t >= B.sWait - 0.3 && !dn;
      rr(x, y0, w, h, 12); c.fillStyle = dn ? BLUE : CARD; c.fill(); c.strokeStyle = waits ? RUST : dn ? BLUE : INK; c.lineWidth = waits ? 4 : 2; if (waits) c.setLineDash([8, 6]); c.stroke(); c.setLineDash([]);
      if (dn) { c.strokeStyle = CARD; c.lineWidth = 6; c.lineCap = "round"; c.beginPath(); c.moveTo(x + w / 2 - 16, y0 + h / 2 + 1); c.lineTo(x + w / 2 - 4, y0 + h / 2 + 13 * pop0); c.lineTo(x + w / 2 + 18 * pop0, y0 + h / 2 - 12 * pop0); c.stroke(); c.lineCap = "butt"; }
      else { font(700, 30); c.fillStyle = waits ? RUST : INK; c.textAlign = "center"; c.fillText(String(i + 1), x + w / 2, y0 + 41); c.textAlign = "left"; }
    }
    c.restore();
    if (t >= B.sWait - 0.3 && t < B.done[3]) {}
  }
  // ------------------------------------------------------------ words beside the set
  function panels() {
    return [[S("parts"), VT.p[0], ""], [MK.parts[1], VT.p[1], ""], [MK.parts[2], VT.p[2], ""], [S("omninode"), VT.h, ""]];
  }
  const PXF = () => (V.mirror ? 760 : 70);
  let PANELS = null;
  function drawPanel(t) { comp("heading", "heading", () => drawPanel0(t)); }
  function drawPanel0(t) {
    let i = -1; for (let k = 0; k < PANELS.length; k++) if (t >= PANELS[k][0]) i = k;
    if (i < 0) return; const [at, h, sub] = PANELS[i], prev = PANELS[i - 1], same = prev && prev[1] === h, x = PX;
    const end = PANELS[i + 1] ? PANELS[i + 1][0] : E("omninode"), next = PANELS[i + 1], leave = next && next[1] === h ? 0 : soft(seg(t, end - F(5), F(5)));
    c.save(); c.globalAlpha = 1 - leave;
    if (TOPH) { const sz = 56 * V.ts; if (same) { font(700, sz); c.fillStyle = INK; c.fillText(h, PXF(), 118); } else rise(h, PXF(), 118, sz, 700, at, { t, w: 1100, lh: 1.1 }); c.restore(); return; }
    const size = (h.length > 26 ? 44 : 52) * V.ts, hl = lines(h, 430, size, 700), subl = sub ? lines(sub, 530, 31, 400) : [], total = hl.length * size * 1.16 + (sub ? 22 + subl.length * 41 : 0), y0 = 880 - total + size * 0.8;
    const yy = same ? (() => { font(700, size); hl.forEach((ln, n) => { c.fillStyle = INK; c.textAlign = "left"; c.fillText(ln, x, y0 + n * size * 1.16); }); return y0 + hl.length * size * 1.16; })() : rise(h, x, y0, size, 700, at, { t, w: 430, lh: 1.16 });
    if (sub) { const k = soft(seg(t, same ? at : at + 0.22, F(12))); subl.forEach((ln, n) => { c.save(); c.beginPath(); c.rect(x - 4, yy - 12 + n * 41, 660, 42); c.clip(); font(400, 31); c.fillStyle = MUTED; c.fillText(ln, x, yy + 22 + n * 41 + (1 - k) * 34); c.restore(); }); }
    c.restore();
  }
  const tagAnim = () => { if (/^ev[cltouqwr]/.test(window.VOICE_KEY)) return; font(600, 24); c.fillStyle = RULE; c.textAlign = V.mirror ? "left" : "right"; c.fillText("Animation", V.mirror ? 60 : 1860, 900); c.textAlign = "left"; };
  // ------------------------------------------------------------ the opening: one clean composition per beat
  function sceneTitle(t) {
    if (TOPEN) { terIdle(t, 18 * soft((t - 0.4) / 1.5), 0, S("parts") + 0.95); const y0 = rise("Supercharge your agentic operations.", 960, 130, 58, 700, 0.15, { t, center: true, w: 1600, gap: 6 }); const q0 = soft(seg(t, 2.4, F(14))); c.save(); c.globalAlpha = q0; pill("Teleion Fabric, by Teleion Labs.", 960, 800, { size: 34, w: 600, color: INK, stroke: LINE, fill: CARD }); c.restore(); tagAnim(); return; }
    c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080);
    if (DIR === "stack" || DIR === "cutaway") { cam = camAt(DIR === "stack" ? 1400 : 1400, DIR === "stack" ? 620 : 500, DIR === "stack" ? 44 : 50); if (DIR === "stack") drawStackFloors(t, true); else drawCutaway(t, true); }
    else if (DIR === "campus") { cam = camAt(1330, 560, 29); QUIET = true; drawSet(S("parts") + 3); QUIET = false; }
    cam = DIR === "closeup" ? camAt(1500, 760, 300) : camAt(1395, 560, 120); const g = growth(t, 0.05);
    if (DIR === "stack" || DIR === "cutaway" || DIR === "campus") { const y0 = rise("Supercharge your agentic operations.", TX, 420, 88 * V.ts, 700, 0.15, { t, w: 780, gap: 6 }); const q0 = soft(seg(t, 2.4, F(14))); font(400, 36); c.fillStyle = MUTED; c.save(); c.beginPath(); c.rect(TX - 10, y0 - 10, 860, 60); c.clip(); c.fillText("Teleion Fabric, by Teleion Labs.", TX, y0 + 36 + (1 - q0) * 40); c.restore(); tagAnim(); return; }
    blob(0, 0, 2.05, 1.2, 1.4); octo3(0, 0, 0.01, 1.7, 0.3 * g, CARD); octo3(0, 0, 0.3 * g + 0.01, 1.25, 0.7 * g, CARD);
    const [a, b] = P(0, 0, 1.02 * g), rx = 0.92 * KX * cam.u, ry = 0.92 * KY * cam.u, k = (t * 0.7) % (Math.PI * 2);
    if (g > 0.95) { c.beginPath(); c.ellipse(a, b, rx, ry, 0, 0, Math.PI * 2); c.fillStyle = "#F2EEE3"; c.fill(); c.lineWidth = 11; c.strokeStyle = LINE; c.stroke(); c.strokeStyle = BLUE; c.beginPath(); c.ellipse(a, b, rx, ry, 0, k, k + 1.5); c.stroke(); glyph(null, a, b, cam.u * 0.42, BLUE); }
    [0, 1, 2, 3].forEach((i) => { const q = ((t * 0.22 + i * 0.25) % 1), ang = i * Math.PI / 2 + 0.4; const d = mix(4.3, 1.8, q), xx = Math.cos(ang) * d, yy = Math.sin(ang) * d; faded(Math.sin(q * Math.PI), () => chip(xx, yy, 0.12, i % 2 ? "obj" : "task", 0.42)); });
    const y = rise("Supercharge your agentic operations.", TX, 420, 88 * V.ts, 700, 0.15, { t, w: 800, gap: 6 });
    const q = soft(seg(t, 2.4, F(14))); font(400, 36); c.fillStyle = MUTED; c.save(); c.beginPath(); c.rect(TX - 10, y - 10, 860, 60); c.clip(); c.fillText("Teleion Fabric, by Teleion Labs.", TX, y + 36 + (1 - q) * 40); c.restore();
    const lb = 1 - soft(seg(t, S("hook") - F(7), F(7))); tagAnim();
  }
  function sceneHook(t) {
    if (TOPEN && VK !== "frustrations") { const s = S("hook"), but = M("hook", "But"), off = soft((t - but) / 0.8); terIdle(t, (VK === "evo" || VK === "evq" || VK === "evr") ? 70 * (0.5 - 0.5 * Math.cos(Math.min(t, M("hook", "AI")) * 1.4)) + 12 : 18 + off * 28, (VK === "evo" || VK === "evq" || VK === "evr") ? 0 : off, S("parts") + 0.95); if ((VK === "evo" || VK === "evq" || VK === "evr")) { const off2 = soft((t - M("hook", "AI")) / 0.5); } rise("AI is smart.", 960, 140, 88, 700, M("hook", "AI") - 0.03, { t, center: true, gap: 4 }); rise("The way we use it is frustratingly dumb.", 960, MAINF ? 940 : 825, 52, 600, ((VK === "evo" || VK === "evq" || VK === "evr") ? M("hook", "The", 1) : but) - 0.02, { t, center: true, w: 1300, gap: 4, accent: ["dumb"] }); tagAnim(); return; }
    c.fillStyle = CARD; c.fillRect(0, 0, 1920, 1080); const s = S("hook"), but = VK === "frustrations" ? s + 2.5 : M("hook", "But"), l = t - s;
    cam = camAt(960, 700, 84); const off = soft((t - but) / 0.8);
    blob(0, 0, 2.05, 1.2, 1.4); octo3(0, 0, 0.01, 1.7, 0.3, CARD); octo3(0, 0, 0.31, 1.25, 0.7, CARD);
    const [a, b] = P(0, 0, 1.02), rx = 0.92 * KX * cam.u, ry = 0.92 * KY * cam.u, k = (t * mix(2, 0.2, off)) % (Math.PI * 2);
    c.lineWidth = 9; c.strokeStyle = LINE; c.beginPath(); c.ellipse(a, b, rx, ry, 0, 0, Math.PI * 2); c.stroke(); c.strokeStyle = off > 0.5 ? RUST : BLUE; c.beginPath(); c.ellipse(a, b, rx, ry, 0, k, k + 1.4); c.stroke();
    // Tasks circle in good order, then lose their way the moment the voice turns.
    for (let i = 0; i < 8; i++) { const an = i * Math.PI / 4 + t * 0.7, d = 2.6, ox = Math.cos(an) * d, oy = Math.sin(an) * d, sx = Math.sin(t * (1.1 + i * 0.31) + i * 2.1) * (2.4 + (i % 3)), sy = Math.cos(t * (0.9 + i * 0.27) + i) * (1.6 + (i % 2)); chip(mix(ox, sx, off), mix(oy, sy, off), 0.14, i % 3 ? "task" : "obj", 0.46); }
    if (VK === "frustrations") rise("Three frustratingly stupid ways we use AI today", 960, 260, 76, 700, s + 0.25, { t, center: true, w: 1500, gap: 3, accent: ["stupid"] });
    else { rise("AI is smart.", 960, 220, 118, 700, M("hook", "AI") - 0.03, { t, center: true, gap: 4 });
    rise("The way we use it is frustratingly dumb.", 960, 340, 62, 600, but - 0.02, { t, center: true, w: 1500, gap: 4, accent: ["dumb"] }); }
    tagAnim();
  }
  function stripes(t, col) { const o = (t * 18) % 120; c.save(); c.globalAlpha = 0.5; c.lineWidth = 2; c.strokeStyle = col; for (let x = -1200; x < 1920 + 1100; x += 120) { c.beginPath(); c.moveTo(x + o, 0); c.lineTo(x + o + 620 * 1.2, 1080 * 0.95 * 1.2); c.stroke(); } c.restore(); }
  function cube9(x, y, s9, h, col) { isoBox(x, y, s9 * 0.96, h, col); }
  function lump9(cx, cy, nx, ny, col, hf, S9 = 20) { for (let a = 0; a < ny; a++) for (let b = 0; b < nx; b++) { const h = hf(a, b); if (h <= 0) continue; cube9(cx + (b - a + (ny - nx) / 2) * S9, cy + (a + b - (nx + ny - 2) / 2) * (S9 / 2), S9, h, col); } }
  function floor9() { const S9 = 24, N = 36; for (let n = -N; n <= N; n++) for (let a = Math.max(-N, n - N); a <= Math.min(N, n + N); a++) { const b = n - a, dx = (b - a) * S9, dy = (a + b) * (S9 / 2); if (Math.abs(dy) > ZY + (MAINF ? 8 : 40) || Math.abs(dx) / (ZX + (MAINF ? 24 : 60)) + Math.abs(dy) / (2 * (ZY + (MAINF ? 8 : 40))) > 1) continue; isoBox(TCX + dx, TCY + dy, S9 * 0.96, 5, "#F1E8D6"); } }
  function world9(t) { if (!TR) terBuild(); c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); terCam(t); DK = 0; NOC9 = true; TNN = false; drawTerrainSet(S("parts") + 0.95); NOC9 = false; comp("floor", "ground", floor9); }
  const hw9 = () => 2 * (PILLX - PILLR) - 40;
  function world3(t) { world9(t); const s = S("three"), t3 = M("three", "rewrites") - 0.1, t4 = M("three", "trouble") - 0.25, Z = ZX * 0.9, BL = K5[3][0], RU = K5[2][0], TE = K5[1][0]; const head = (x, at, ac) => comp("heading", "heading", () => rise(x, TCX, 120, 58, 700, at, { t, center: true, w: hw9(), gap: 3, accent: [ac] }));
    if (t < t3) { const l = t - s; head("It doesn't know what's new.", s - 0.05, "new"); comp("skyline", "component", () => { const flow = [0, 1, 2, 3, 4].map((i) => ((l * 0.32 + i * 0.2) % 1)); flow.filter((q) => q < 0.5).forEach((q) => { const x = mix(-Z, Z, q), y = mix(-ZY * 0.55, ZY * 0.75, q); lump9(TCX + x, TCY + y, 2, 2, RU, () => 26); }); lump9(TCX, TCY, 7, 7, BL, (a, b) => 44 + 16 * ((a * 3 + b * 5) % 3)); flow.filter((q) => q >= 0.5).forEach((q) => { const x = mix(-Z, Z, q), y = mix(-ZY * 0.55, ZY * 0.75, q); lump9(TCX + x, TCY + y, 2, 2, RU, () => 26); }); }); pill("Your agent", TCX, TCY + ZY + 56, { size: 28, w: 700, color: INK, stroke: LINE, fill: CARD }); pill("New release", TCX + PILLX, TCY + 170, { size: 26, w: 700, color: RUST, stroke: RUST, fill: CARD, a: soft(l / 0.4) }); }
    else if (t < t4) { const l = t - t3; head("It rewrites code that already exists.", t3, "rewrites"); comp("skyline", "component", () => { [0, 1, 2, 3, 4].forEach((i) => { const k = pop(seg(l, 0.1 + i * 0.5, F(14))); if (k > 0) lump9(TCX + (i - 2) * ZX * 0.42, TCY + (i - 2) * ZY * 0.05, 4, 4, RU, (a, b) => k * (34 + 12 * ((a + b * 2) % 2))); }); }); const n = Math.min(5, Math.floor((l - 0.1) / 0.5) + 1); pill(`Same code, written ${n} ${n === 1 ? "time" : "times"}`, TCX, TCY + ZY + 56, { size: 30, w: 700, color: RUST, stroke: RUST, fill: CARD }); }
    else { const l = t - t4, S9 = 24, N = 11, reach = soft(l / 1.4) * 6.5; head("And it has trouble with long-horizon tasks.", t4, "trouble"); comp("skyline", "component", () => { for (let i = 0; i < N; i++) { const x = TCX + (i - 5) * S9 * 1.6, y = TCY + (i - 5) * S9 * 0.8; isoBox(x, y, S9 * 0.72, i < reach ? 10 : 6, i < reach ? TE : "#E4DAC6"); } const q = Math.min(reach, 6.5) + (l > 1.4 ? 0.18 * Math.sin((l - 1.4) * 3) : 0); isoBox(TCX + (q - 5) * S9 * 1.6, TCY + (q - 5) * S9 * 0.8 - 8 + (l > 1.4 ? 5 * Math.sin((l - 1.4) * 5) : 0), S9 * 0.8, 34, BL); }); pill("Too long for one session", TCX, TCY + ZY + 56, { size: 28, w: 700, color: RUST, stroke: RUST, fill: CARD, a: soft((l - 1.3) / 0.3) }); } }
  function worldStmt(t) { world9(t); const s = S("statement"), l = t - s, hasA = CUES.statement.words.some((q) => q[0] === "A"), m2 = hasA ? M("statement", "A") : s + CUES.statement.seconds * 0.55, br = soft((t - m2 + 0.6) / 0.9), g = soft(l / 0.9); comp("heading", "heading", () => { rise("Bigger models alone won't fix this.", TCX, 110, 54, 700, s + 0.05, { t, center: true, w: hw9(), gap: 3 }); if (hasA) rise("A multi-faceted solution is required.", TCX, 172, 38, 600, m2, { t, center: true, w: hw9(), gap: 3, accent: ["multi-faceted"] }); }); comp("skyline", "component", () => { const P5 = [[-0.55, -0.42, 4], [0.55, -0.42, 0], [-0.62, 0.42, 1], [0.62, 0.42, 3], [0, 0.72, 2]]; P5.forEach((q) => { if (br > 0) lump9(TCX + q[0] * ZX, TCY + q[1] * ZY, 5, 5, K5[q[2]] ? K5[q[2]][0] : "#7A5BA8", (a, b) => br * (46 + 22 * hsh(a * 7 + b * 13 + q[2] * 31))); }); if (br < 1) lump9(TCX, TCY, 7, 7, "#D8D2C3", (a, b) => (1 - br) * g * (150 + 6 * Math.sin(t * 2 + a + b)), 24); }); if (br < 0.5) pill("A bigger model", TCX, TCY + ZY + 56, { size: 30, w: 700, color: INK, stroke: LINE, fill: CARD, a: soft((l - 0.3) / 0.3) * (1 - br * 2) }); }
  const META9 = { work: ["Real run, sped up · Nov 3", ["label muse-spark-1.3: 4 items", "muse-spark-1.3 answered in 18.87 s, 2418 output tokens", "label muse-wonder-1.0: 1 item", "muse-wonder-1.0 answered in 4.02 s, 610 output tokens"]], policy: ["Real decider record, small live trial · Nov 4 UTC", ["decider: 3 real Tasks so far, all chose muse-spark-1.3", "where: the always-on agent, each real build Task it claims"]], fine: ["Real decider record, small live trial · Nov 4 UTC", ["Muse Glimmer 30B + our adapter: 65 real Tasks, 3 batches", "about 8% of ready Tasks; 1 pick has reached a live worker", "route: Muse Glimmer 30B, on-demand GPU", "route: Muse Spark and Muse Wonder, Meta API"]] };
  function sceneMeta(t) { world9(t); const W = CUES.meta.words, s = S("meta"), e = E("meta"), wd = (x) => { const q = W.find((v) => v[0] === x); return q ? q[1] : s; }, b2 = wd("A") - 0.2, bF = W.find((v, i) => v[0] === "A" && W[i + 1] && W[i + 1][0] === "fine-tuned")[1] - 0.2, beat = t < b2 ? "work" : t < bF ? "policy" : "fine", st = beat === "work" ? s : beat === "policy" ? b2 : bF, en = beat === "work" ? b2 : beat === "policy" ? bF : e - 0.4, R = META9[beat], at = R[1].map((q, i) => st + 0.3 + (i * (en - st - 0.3)) / R[1].length), on = at.filter((v) => t >= v).length, SX = TCX - ZX * 0.42, WX = TCX + ZX * 0.42, BL = K5[3][0], LB = "#7E9BD1", TE = K5[1][0], RU = K5[2][0], LY = TCY + 0.05 * ZY, gr = soft((t - st) / 0.7), wav = (a, b) => 7 * Math.sin(t * 2.2 + a * 0.8 + b * 0.8);
    pill("Teleion Fabric", TCX, 62, { size: 34, w: 700, color: INK });
    pill(beat === "policy" ? "A Meta-based decider" : beat === "fine" ? "A fine-tuned Meta model" : "Meta's Muse models", TCX, 150, { size: 34, w: 700, color: INK });
    comp("skyline", "component", () => { if (true) { const hS = 110, hW = 110; if (beat === "fine") lump9(TCX, TCY - ZY * 0.5, 4, 4, K5[0][0], (a, b) => gr * (46 + wav(a, b))); lump9(SX, TCY + 10, 8, 8, BL, (a, b) => gr * (hS * (0.86 + 0.14 * hsh(a * 7 + b * 13)) + wav(a, b))); lump9(WX, TCY + 10, 8, 8, LB, (a, b) => gr * (hW * (0.86 + 0.14 * hsh(a * 7 + b * 13)) + wav(a, b))); const P9 = 3.6, f = ((t - s) % P9) / P9, seg9 = f * 3, n9 = Math.floor(seg9), g9 = inOut(seg9 - n9), XP = [TCX - PILLX + PILLR, SX, WX, TCX + PILLX - PILLR], YP = [LY, TCY - hS * gr - 20, TCY - hW * gr - 20, LY]; isoBox(mix(XP[n9], XP[n9 + 1], g9), mix(YP[n9], YP[n9 + 1], g9) - Math.sin(g9 * Math.PI) * 50, 17, 17, RU); } else { const X3 = [TCX - ZX * 0.55, TCX, TCX + ZX * 0.55], C3 = [TE, RU, BL]; X3.forEach((x, i) => { const k = pop(clamp((t - at[i]) / 0.6)); if (k > 0) lump9(x, TCY + 10, 6, 6, C3[i], (a, b) => k * (70 + wav(a, b))); }); const j = Math.min(on, 3) - 1; if (j >= 0) { const g = clamp((t - at[j]) / 0.8), x0 = j === 0 ? TCX - PILLX + PILLR : X3[j - 1], y0 = j === 0 ? LY : TCY - 80; isoBox(mix(x0, X3[j], inOut(g)), mix(y0, TCY - 80, inOut(g)) - Math.sin(g * Math.PI) * 50, 17, 17, K5[4][0]); } } });
    pill("Muse Spark", SX, TCY + 205, { size: 30, w: 700, color: INK }); pill("Muse Wonder", WX, TCY + 205, { size: 30, w: 700, color: INK });
    const x = 336, y = 852, w = 1248, h = 200, PAD = 24, BAR = 40, fs = 30, lh = 44; comp("terminal", "label", () => { c.save(); if (!window.__CMP) { c.shadowColor = "rgba(40,34,24,.26)"; c.shadowBlur = 22; c.shadowOffsetY = 8; } rr(x, y, w, h, 12); c.fillStyle = "#0B0D10"; c.fill(); c.restore(); c.save(); rr(x, y, w, h, 12); c.clip(); c.fillStyle = "#1B1F25"; c.fillRect(x, y, w, BAR); ["#FF5F57", "#FEBC2E", "#28C840"].forEach((k, n) => { c.beginPath(); c.arc(x + PAD + n * 20, y + 20, 6, 0, Math.PI * 2); c.fillStyle = k; c.fill(); }); font(600, 21); c.fillStyle = "#D8D6CF"; c.textAlign = "center"; c.fillText(R[0], x + w / 2, y + 27); c.textAlign = "left"; c.font = `400 ${fs}px ${TMONO}`; const vis = R[1].map((q, i) => [q, i]).filter((q) => q[1] < on).slice(-3); vis.forEach((q, n) => { const yy = y + BAR + 14 + n * lh + lh * 0.74; if (n === vis.length - 1) { c.fillStyle = "rgba(255,255,255,.09)"; c.fillRect(x + 12, y + BAR + 14 + n * lh, w - 24, lh); } c.fillStyle = TCOL(q[0]); c.fillText(q[0].slice(0, Math.max(1, Math.floor((t - at[q[1]]) * 60))), x + PAD, yy); }); c.restore(); }); (window.__termChk = window.__termChk || {}).main = { x, y, w, h, over: 0 }; }
  function sceneThree(t) { if (WORLD && TERR) return world3(t); if ((VK === "evo" || VK === "evq" || VK === "evr")) { terIdle(t, 22, 0.4, S("parts") + 0.95); const m9 = MK.three; [["It doesn't know what's new.", m9[0], m9[1]], ["It rewrites code that already exists.", m9[1], m9[2]], ["It has trouble with long-horizon tasks.", m9[2], M("three", "Bigger")], ["Bigger models alone won't fix this.", M("three", "Bigger"), E("three")]].forEach((q) => { if (t >= q[1] - 0.05 && t < q[2]) rise(q[0], 960, 815, 52, 600, q[1], { t, center: true, w: 1500, gap: 3 }); }); return; }
    const s = S("three"), t2 = s, t3 = M("three", "rewrites") - 0.1, t4 = M("three", "trouble") - 0.25;
    c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080);
    if (t < t2 - 0.1) {
      cam = camAt(960, 640, 90);
      [0, 1, 2].forEach((i) => { const at = s + 0.3 + i * 0.3, g = soft(seg(t, at, F(14))), x = -3.2 + i * 3.2, y = 0; if (g <= 0) return; softShadow(x - 0.9, y - 0.9, 1.8, 1.8, 0); box(x - 0.9, y - 0.9, 0, 1.8, 1.8, 1.2 * g, i === 2 ? SAND : CARD); const [px, py] = P(x, y, 1.2 * g); font(700, 40); c.save(); c.globalAlpha = g; c.fillStyle = RUST; c.textAlign = "center"; c.fillText(String(i + 1), px, py + 14); c.textAlign = "left"; c.restore(); });
      rise("Three things keep getting in the way.", 960, 250, 72, 700, s + 0.25, { t, center: true, w: 1500, gap: 4 }); tagAnim(); return;
    }
    cam = camAt(1300, 520, 96);
    if (t < t3) {
      const l = t - t2;
      // It doesn't know what's new: new releases pass; the agent's knowledge stays old.
      rise("It doesn't know what's new.", TX, 470, 72 * V.ts, 700, t2 - 0.05, { t, w: 700, gap: 3, accent: ["new"] });
      rail([-5, 1.8], [3.8, 1.8], true, t);
      [0, 1, 2, 3].forEach((i) => { const x = -5 + ((l * 1.5 + i * 2.2) % 8.8); chip(x, 1.8, 0.14, "obj", 0.62); });
      softShadow(-1.4, -2, 2.8, 2.8, 0); box(-1.4, -2, 0, 2.8, 2.8, 0.9, CARD);
      pill("Your agent", P(0, -0.6, 2.2)[0], P(0, -0.6, 2.2)[1], { size: 30 }); pill("Knows last year", P(0, -0.6, 2.2)[0] + 240 * MX, P(0, -0.6, 1.2)[1] - 56, { size: 26, a: soft(seg(l, 0.7, 0.3)), color: RUST, stroke: RUST, fill: SAND }); pill("New release", V.mirror ? 780 : 1140, 840, { size: 26, color: RUST, stroke: RUST, fill: SAND });
    } else if (t < t4) {
      const l = t - t3;
      // It rewrites code that already exists: the same component made again and again.
      rise("It rewrites code that already exists.", TX, 470, 72 * V.ts, 700, t3, { t, w: 700, gap: 3, accent: ["rewrites"] });
      [0, 1, 2, 3, 4].forEach((i) => { const at = 0.1 + i * 0.5, k = pop(seg(l, at, F(14))); if (k <= 0) return; const x = -3.4 + i * 1.5, y = 0; softShadow(x - 0.6, y - 0.6, 1.2, 1.2, 0); box(x - 0.6, y - 0.6, (1 - k) * 2, 1.2, 1.2, 0.5, i === 4 ? SAND : CARD, i === 4 ? 0.5 : 0.22); });
      const n = Math.min(5, Math.floor((l - 0.1) / 0.5) + 1); pill(`Same code, written ${n} ${n === 1 ? "time" : "times"}`, V.mirror ? 620 : 1300, 820, { size: 30, color: RUST, stroke: RUST, fill: SAND });
    } else {
      const l = t - t4;
      // It loses the thread on long-horizon tasks: a long track that stops short.
      rise("And it has trouble with long-horizon tasks.", TX, 470, 72 * V.ts, 700, t4, { t, w: 700, gap: 3, accent: ["trouble"] });
      const end = mix(-5, 1.2, soft(l / 1.3));
      rail([-5, 0], [end, 0], true, t); faded(0.5, () => rail([2.6, 0], [5.4, 0], false, t));
      chip(mix(-5, 1.2, inOut(l / 1.3)), 0, 0.14 - Math.max(0, l - 1.3) * Math.max(0, l - 1.3) * 3.2 * (l < 2.5 ? 1 : 0), "task", 0.7);
      pill("Too long for one session", P(1.2, 0)[0] + 80 * MX, P(1.2, 0)[1] - 110, { size: 28, a: soft(seg(l, 1.3, 0.3)), color: RUST, stroke: RUST, fill: SAND });
    }
    tagAnim();
  }
  function sceneStatement(t) { if (WORLD && TERR) return worldStmt(t);
    const s = S("statement"), l = t - s, m2 = M("statement", "A");
    c.fillStyle = TONE; c.fillRect(0, 0, 1920, 1080); stripes(t, "#E5DFD0"); if (TOPEN) { const z9 = 1 + 0.06 * clamp(l / CUES.statement.seconds); c.translate(1400, 560); c.scale(z9, z9); c.translate(-1400, -560); }
    cam = camAt(1400, 600, 100);
    const big = soft(l / 0.9) * 1, h = mix(0.4, 4.2, big); softShadow(-1.3, -1.3, 2.6, 2.6, 0); box(-1.3, -1.3, 0, 2.6, 2.6, h, CARD);
    pill("A bigger model", P(0, 0, h)[0], P(0, 0, h)[1] - 62, { size: 30, a: soft(seg(l, 0.3, 0.3)) });
    rise("Bigger models alone won't fix this.", TX, 400, 76 * V.ts, 700, s + 0.2, { t, w: 820, gap: 3 });
    rise("A multi-faceted solution is required.", TX, 620, 54 * V.ts, 600, m2, { t, w: 780, gap: 3, accent: ["multi-faceted"] });
    tagAnim();
  }
  // ------------------------------------------------------------ real pages. o: {img,a,b,label}
  function page(o, t, t0, t1) {
    const w = 1800, h = 800, x0p = 60, ytarget = 56, enter = soft(seg(t, t0, F(13))), leave = exit(seg(t, t1 - F(7), F(7))), hz = V.pageFrom === "left" ? -1 : V.pageFrom === "right" ? 1 : 0, y = WORLD ? ytarget : ytarget + (hz ? 0 : (1 - enter) * 1000 - leave * 1000), xo = WORLD ? 0 : hz * ((1 - enter) * 2000 - leave * 2000);
    const x = x0p + xo, k = clamp((t - t0) / (t1 - t0)), s = mix(o.a.s, o.b.s, inOut(k)), ix = mix(o.a.x, o.b.x, inOut(k)), iy = mix(o.a.y, o.b.y, inOut(k));
    if (window.__views) window.__views.push({ img: o.img, x0: ix, y0: iy, x1: ix + w / s, y1: iy + h / s, t });
    c.save(); c.shadowColor = "rgba(74,64,48,.28)"; c.shadowBlur = 34; c.shadowOffsetY = 12; rr(x, y, w, h, 18); c.fillStyle = CARD; c.fill(); c.restore();
    c.save(); rr(x, y, w, h, 18); c.clip(); const im = IMG[o.img]; if (im) c.drawImage(im, x - ix * s, y - iy * s, im.width * s, im.height * s); c.restore();
    c.strokeStyle = shade(0.2); c.lineWidth = 1.5; rr(x, y, w, h, 18); c.stroke();
    if (o.label && !GLASS) { font(600, 26); const lw = c.measureText(o.label).width + 34; rr(x + w - lw, y + h + 14, lw, 44, 22); c.fillStyle = CARD; c.fill(); c.strokeStyle = o.warn ? RUST : BLUE; c.lineWidth = 2; c.stroke(); c.fillStyle = o.warn ? RUST : BLUE; c.textAlign = "left"; c.fillText(o.label, x + w - lw + 17, y + h + 45); }
  }
  const LIVE_LB = "Live page, Nov 3", ER_LB = "eranosforgood.org, live page", EX_LB = "Example on the live site";
  let LIVEP = null, ERP = null;
  function sceneLive(t) {
    c.fillStyle = TONE; c.fillRect(0, 0, 1920, 1080);
    const s = S("live"), a = CUES.live.words.some((q) => q[0] === "These") ? M("live", "These") : s + 2.2; if (WORLD && TERR) { if (!TR) terBuild(); terIdle(t, 10, 0, TR.end - 0.01); const e9 = E("live"), up = soft((t - (a - 0.2)) / 0.8), dn = soft((t - (e9 - 0.5)) / 0.5); if (t < a - 0.2) rise("This is running right now.", TCX, 130, 64, 700, s + 0.2, { t, center: true, w: 1100, gap: 3 }); if (up > 0) { c.save(); c.globalAlpha = Math.min(1, up * 3) * (1 - dn * dn); lift9(mix(1 - up, 1, dn) * (CARDM ? 0.92 : 1) + (CARDM ? 0.08 : 0), () => page({ img: "dash", a: { x: 0, y: 520, s: 0.71 }, b: { x: 0, y: 860, s: 0.71 }, label: LIVE_LB }, t, a - 0.2, e9 + 0.1)); c.restore(); } return; }
    if (t < a - 0.2) { if (STYLE === "kinetic") kineticBehind(t, "result"); else setBehind(t, s, { scale: 0.72, cy: 170, a: 0.8 }); rise("This is running right now.", 960, 150, 88, 700, s + 0.2, { t, center: true, w: 1500, gap: 3 }); return; }
    const m = TERR ? a - 1 : a + 3.6; if (t < m) page({ img: "home", a: { x: 0, y: 760, s: 0.7 }, b: { x: 0, y: 840, s: 0.703 }, label: LIVE_LB }, t, a - 0.2, m + 0.2); else page({ img: "dash", a: { x: 0, y: 520, s: 0.71 }, b: { x: 0, y: 860, s: 0.71 }, label: LIVE_LB }, t, m - 0.2, E("live") + 0.1);
  }

  // ================================================================== Eranos from one real browser take on the live site (takes/e_live-1547, real pointer, real clicks, nothing sent).
  // Each shot maps film time to take time, so a real click lands on its spoken word. Emphasis is a ring, a soft wash and a slow zoom; the pointer is only ever the one in the take.
  const TAKEON = /^ev[cltouqwr]/.test(window.VOICE_KEY) && qs.get("take") !== "0", TDIR = MAINF ? "takes/e_main3/" : "takes/e_full/", TL_LIVE = "Live eranosforgood.org, real browser, recorded Nov 3", TL_EXQ = "Example request, live eranosforgood.org, recorded Nov 3", TL_EXR = "Example result, live eranosforgood.org, recorded Nov 3";
  const TFS = {}; let TFP = null, RC = null; const TIMG = new Map(), TD3 = "takes/e_type/";
  const tkLoad = () => TFP || (TFP = Promise.all([fetch(TDIR + "rects.json").then((r) => r.json()).then((d) => { RC = d; })].concat([TDIR, TD3].map((dir) => fetch(dir + "frames.json").then((r) => r.json()).then((d) => { const z = d.frames[0][0]; TFS[dir] = { t: d.frames.map((q) => q[0] - z), f: d.frames.map((q) => dir + q[1]) }; })))));
  const tkFile = (q, x) => { const F = TFS[q.d || TDIR]; let a = 0, b = F.t.length - 1; while (a < b) { const m = (a + b + 1) >> 1; if (F.t[m] <= x) a = m; else b = m - 1; } return F.f[a]; };
  const tkImg = (fn) => { let e = TIMG.get(fn); if (e) return e; const im = new Image(); e = { im, ok: false, p: null }; e.p = new Promise((res) => { im.onload = () => { e.ok = true; res(); }; im.onerror = () => res(); }); im.src = fn; TIMG.set(fn, e); if (TIMG.size > 90) { const k = TIMG.keys().next().value; TIMG.delete(k); } return e; };
  const W2 = (w) => M("eranos", w), W3 = (w, n) => M("eranos", w, n), FW = (w) => M("finish", w);
  let SHOTS = null;
  function shotsBuild() { const e0 = S("eranos"), w0 = M("eranos", "Eranos."), press = W2("press"), door1 = M("eranos", "help,"), tell = W2("tell"), ask = W2("ask"), info = W2("information,"), or0 = W2("Or"), reus = W2("reusable"), proc = W2("process,"), their = W2("Their"), step = W2("step"), net = W2("network"), who = W2("Who"), anyone = W2("Anyone"), press2 = W3("press", 1), h2 = W3("help,", 1), conn = W2("connect"), keep = W2("keep"), tak = W2("takes"), then0 = W2("Then"), audits = W2("audits"), every0 = W2("Every"), src0 = W2("source."), pers = W2("person"), and0 = M("eranos", "finished") - 0.6, adapt = W2("adapt"), spare = W3("Spare", 1), fs = S("finish"), open = FW("Open"), follow = FW("follow"), then1 = FW("Then"), ad1 = FW("Adapt"), grp = CUES.finish && CUES.finish.words.some((q) => q[0] === "group,") ? FW("group,") : FW("group."), fe = S("connect");
    const fe2 = CUES.answer ? S("answer") : fe;
    SHOTS = [
      { s: w0 + 1, e: press - 1.2, k: [[0, 0.3], [1, 4.2]], a: [260, 120, 1400], b: [285, 130, 1340], l: TL_LIVE },
      { s: press - 1.2, e: door1 + 0.25, k: [[press - 1.2, 11.4], [door1, 13.62], [door1 + 0.25, 13.75]], a: [285, 130, 1340], b: [285, 185, 1030], l: TL_LIVE, r: [{ n: ["door1"], p: 6, s: press - 0.1, e: door1 + 0.25 }] },
      { s: door1 + 0.25, e: tell + 0.3, k: [[door1 + 0.25, 14.6], [tell + 0.3, 16.2]], a: [320, 40, 1290], b: [320, 50, 1250], l: TL_LIVE },
      { s: tell + 0.3, e: ask - 0.1, k: [[tell + 0.3, 18.4], [ask - 0.1, 22.4]], a: [320, 507, 1290], b: [320, 520, 1260], l: TL_LIVE },
      { s: ask - 0.1, e: or0 - 0.1, k: [[ask - 0.1, 23.75], [info + 0.1, 25.36], [or0 - 0.1, 28.2]], a: [320, 340, 1300], b: [320, 370, 1260], l: TL_LIVE, r: [{ n: ["info"], p: 5, s: info - 0.1, e: or0 - 0.1 }] },
      { s: or0 - 0.1, e: their - 0.1, k: [[or0 - 0.1, 29.3], [proc, 31.57], [their - 0.1, 34.8]], a: [320, 370, 1260], b: [320, 390, 1200], l: TL_LIVE, r: [{ n: ["process"], p: 5, s: reus - 0.1, e: their - 0.1 }] },
      { s: their - 0.1, e: net - 0.2, k: [[their - 0.1, 36.9], [net - 0.2, 41]], a: [300, 30, 1340], b: [300, 60, 1300], l: TL_EXQ, r: [{ n: ["steps", "auditrow"], p: 6, s: step - 0.3, e: net - 0.2 }] },
      { s: net - 0.2, e: who - 0.1, k: [[net - 0.2, 41], [who - 0.1, 45.7]], a: [290, 470, 1340], b: [290, 480, 1340], l: TL_EXQ, r: [{ n: ["log"], p: 3, s: net + 0.2, e: who - 0.1 }] },
      { s: who - 0.1, e: h2 + 0.25, k: [[who - 0.1, 47.2], [anyone + 0.9, 48.4], [h2, 50.7], [h2 + 0.25, 50.85]], a: [260, 120, 1400], b: [285, 185, 1030], l: TL_LIVE, r: [{ n: ["door2"], p: 6, s: press2 - 0.3, e: h2 + 0.25 }] },
      { s: h2 + 0.25, e: keep - 0.15, k: [[h2 + 0.25, 51.6], [keep - 0.15, 54]], a: [328, 390, 1260], b: [328, 395, 1260], l: TL_LIVE, r: [{ n: ["connect"], p: 5, s: conn, e: keep - 0.15 }] },
      { s: keep - 0.15, e: tak - 0.15, k: [[keep - 0.15, 54.1], [tak - 0.15, 57.5]], a: [320, 110, 1240], b: [320, 110, 1200], l: TL_LIVE, r: [{ n: ["keys"], p: 3, s: keep, e: tak - 0.15 }] },
      { s: tak - 0.15, e: then0 - 0.1, k: [[tak - 0.15, 5.7], [then0 - 0.1, 9.5]], a: [290, 300, 1340], b: [290, 320, 1340], l: TL_LIVE, r: [{ n: ["strip"], p: 3, s: tak + 0.1, e: then0 - 0.1 }] },
      { s: then0 - 0.1, e: every0 - 0.1, k: [[then0 - 0.1, 37], [every0 - 0.1, 41]], a: [300, 120, 1320], b: [300, 160, 1300], l: TL_EXQ, r: [{ n: ["auditrow"], p: 6, s: audits - 0.2, e: every0 - 0.1 }] },
      { s: every0 - 0.1, e: pers - 0.1, k: [[every0 - 0.1, 63.3], [pers - 0.1, 67.2]], a: [280, 288, 1000], b: [280, 288, 960], l: TL_EXR, r: [{ n: ["sources"], p: 6, s: every0 + 0.5, e: pers - 0.1 }] },
      { s: pers - 0.1, e: and0, k: [[pers - 0.1, 41], [and0, 45.7]], a: [290, 280, 1340], b: [290, 320, 1340], l: TL_EXQ, r: [{ n: ["decide"], p: 4, s: pers + 0.5, e: and0 }] },
      { s: and0, e: spare - 0.1, k: [[and0, 69.6], [adapt - 1.4, 73.1], [spare - 0.1, 77]], a: [300, 90, 1300], b: [300, 397, 1300], l: TL_LIVE, r: [{ n: ["adapt"], p: 5, s: adapt + 0.25, e: spare - 0.1 }] },
      { s: spare - 0.1, e: fs, k: [[spare - 0.1, 78.4], [fs, 83.3]], a: [260, 120, 1400], b: [285, 130, 1340], l: TL_LIVE },
      { s: fs, e: open + 0.15, k: [[fs, 86.1], [open + 0.05, 88.89], [open + 0.15, 89]], a: [300, 90, 1300], b: [300, 397, 1300], l: TL_LIVE, r: [{ n: ["open"], p: 5, s: open - 1, e: open + 0.15 }] },
      { s: open + 0.15, e: follow - 0.05, k: [[open + 0.15, 90.5], [follow - 0.05, 93.4]], a: [280, 100, 1100], b: [280, 130, 1040], l: TL_EXR },
      { s: follow - 0.05, e: then1 - 0.1, k: [[follow - 0.05, 63.3], [then1 - 0.1, 67.2]], a: [280, 288, 1000], b: [280, 288, 960], l: TL_EXR, r: [{ n: ["sources"], p: 6, s: follow + 0.3, e: then1 - 0.1 }] },
      { s: then1 - 0.1, e: grp + 0.25, k: [[then1 - 0.1, 96.25], [grp, 98.98], [grp + 0.25, 99.1]], a: [300, 397, 1300], b: [300, 397, 1300], l: TL_LIVE, r: [{ n: ["adapt"], p: 5, s: ad1 - 0.2, e: grp + 0.25 }] },
      { s: grp + 0.25, e: fe2 + 0.1, k: [[grp + 0.25, 99.9], [fe2 + 0.1, 103.8]], a: [320, 30, 1290], b: [320, 60, 1220], l: TL_LIVE },
    ];
    if (/^ev[ltouqwr]/.test(VK)) { const has = (w) => CUES.eranos.words.some((q) => q[0] === w), W9 = (...ws) => { for (const w of ws) if (has(w)) return W2(w); return e0; }, pr1 = W9("press", "presses"), d1 = M("eranos", "help,"), tl = W9("tell", "tells"), as0 = W9("ask"), or9 = W9("or", "Or"), rs9 = W9("reusable"), pc9 = W9("process,", "process", "process."), nt9 = W9("network"), an9 = W9("Anyone"), pr2 = VK === "evlb" ? W3("press", 0) : W3("press", 1), h9 = W3("help,", 1), th9 = W9("Then"), au9 = W9("audits"), pe9 = W9("person"), an0 = (() => { const L = CUES.eranos.words.filter((q) => q[0] === "every"); return L.length ? L[L.length - 1][1] : e0; })(), se9 = has("See") ? W2("See") : (e0 + fs) / 2, LV = TL_LIVE, XQ = TL_EXQ, XR = TL_EXR, I1 = [260, 120, 1400], I2 = [285, 130, 1340], D2 = [285, 185, 1030], base = SHOTS.slice(-5);
      SHOTS = [{ s: w0 + 1, e: pr1 - 1.2, k: [[w0 + 1, 0.3], [pr1 - 1.2, 4.2]], a: I1, b: I2, l: LV }, { s: pr1 - 1.2, e: d1 + 0.25, k: [[pr1 - 1.2, 11.4], [d1, 13.62], [d1 + 0.25, 13.75]], a: I2, b: D2, l: LV, r: [{ n: ["door1"], p: 6, s: pr1 - 0.1, e: d1 + 0.25 }] }, { s: d1 + 0.25, e: tl + 0.3, k: [[d1 + 0.25, 14.6], [tl + 0.3, 16.2]], a: [320, 40, 1290], b: [320, 50, 1250], l: LV }, /^ev[to]/.test(VK) ? { d: TD3, s: tl + 0.3, e: as0 - 0.1, k: [[tl + 0.3, 2], [as0 - 0.1, Math.min(7.2, 2 + (as0 - tl - 0.4) * 1.5)]], a: [320, 507, 1290], b: [320, 520, 1260], l: LV } : { s: tl + 0.3, e: as0 - 0.1, k: [[tl + 0.3, 18.4], [as0 - 0.1, 22.4]], a: [320, 507, 1290], b: [320, 520, 1260], l: LV }, { s: as0 - 0.1, e: or9 - 0.1, k: [[as0 - 0.1, 23.75], [as0 + 0.6, 25.36], [or9 - 0.1, 28.2]], a: [320, 300, 1300], b: [320, 310, 1260], l: LV, r: [{ n: ["info"], p: 5, s: as0 + 0.3, e: or9 - 0.1 }] }, { s: or9 - 0.1, e: nt9 - 0.1, k: [[or9 - 0.1, 29.3], [pc9, 31.57], [nt9 - 0.1, 41]], a: [320, 310, 1260], b: [320, 310, 1200], l: LV, r: [{ n: ["process"], p: 5, s: rs9 - 0.1, e: Math.min(nt9 - 0.1, pc9 + 3) }] }, { s: nt9 - 0.1, e: an9 - 0.1, k: [[nt9 - 0.1, 37], [an9 - 0.1, 45.7]], a: [290, 462, 1340], b: [320, 500, 1270], l: XQ, r: [{ n: ["log"], p: 3, s: nt9 + 0.2, e: an9 - 0.1 }] }, { s: an9 - 0.1, e: h9 + 0.25, k: [[an9 - 0.1, 47.2], [pr2 - 0.8, 48.4], [h9, 50.7], [h9 + 0.25, 50.85]], a: I1, b: D2, l: LV, r: [{ n: ["door2"], p: 6, s: pr2 - 0.3, e: h9 + 0.25 }] }, ...(() => { const kp = W9("keep"), hasT = has("takes"), tk9 = hasT ? W2("takes") : th9; return [{ s: h9 + 0.25, e: kp - 0.15, k: [[h9 + 0.25, 51.6], [kp - 0.15, 54]], a: [328, 390, 1260], b: [328, 395, 1260], l: LV, r: [{ n: ["connect"], p: 5, s: conn, e: kp - 0.15 }] }, { s: kp - 0.15, e: tk9 - 0.15, k: [[kp - 0.15, 54.1], [tk9 - 0.15, 57.5]], a: [320, 110, 1240], b: [320, 110, 1200], l: LV, r: [{ n: ["keys"], p: 3, s: kp, e: tk9 - 0.15 }] }].concat(hasT ? [{ s: tk9 - 0.15, e: th9 - 0.1, k: [[tk9 - 0.15, 5.7], [th9 - 0.1, 9.5]], a: [290, 300, 1340], b: [290, 320, 1340], l: LV, r: [{ n: ["strip"], p: 3, s: tk9 + 0.1, e: th9 - 0.1 }] }] : []); })(), ...(() => { const ev9 = W9("Every"); return [{ s: th9 - 0.1, e: ev9 - 0.1, k: [[th9 - 0.1, 37], [ev9 - 0.1, 41]], a: [300, 120, 1320], b: [300, 160, 1300], l: XQ, r: [{ n: ["auditrow"], p: 6, s: au9 - 0.2, e: ev9 - 0.1 }] }, { s: ev9 - 0.1, e: pe9 - 0.1, k: [[ev9 - 0.1, 63.3], [pe9 - 0.1, 67.2]], a: [280, 288, 1000], b: [280, 288, 960], l: XR, r: [{ n: ["sources"], p: 6, s: ev9 + 0.5, e: pe9 - 0.1 }] }]; })(), { s: pe9 - 0.1, e: an0 - 0.3, k: [[pe9 - 0.1, 41], [an0 - 0.3, 45.7]], a: [290, 280, 1340], b: [290, 320, 1340], l: XQ, r: [{ n: ["decide"], p: 4, s: pe9 + 0.5, e: an0 - 0.3 }] }, { s: an0 - 0.3, e: fs, k: [[an0 - 0.3, 69.6], [se9, 73.1], [fs, 77]], a: [300, 90, 1300], b: [300, 397, 1300], l: LV }].concat(base); const o0 = Math.min(fs, open - 1.6); SHOTS[SHOTS.length - 6].e = o0; const f1 = SHOTS[SHOTS.length - 5]; f1.s = o0; f1.k[0][0] = o0; }
    if (/^ev[wr]/.test(VK)) { const i9 = SHOTS.findIndex((q) => q.r && q.r[0].n[0] === "process"), th = W2("Their"), q0 = SHOTS[i9], e9 = q0.e; q0.e = th - 0.1; q0.k = [[q0.s, 29.3], [W2("reusable") + 0.5, 31.57], [th - 0.1, 34.7]]; q0.r[0].e = th - 0.1; SHOTS.splice(i9 + 1, 0, { s: th - 0.1, e: e9, k: [[th - 0.1, 36.9], [e9, 41]], a: [300, 30, 1340], b: [300, 60, 1300], l: TL_EXQ, r: [{ n: ["steps", "auditrow"], p: 6, s: th + 0.3, e: e9 }] }); }
    for (const q of SHOTS) if (q.k[0][0] === 0) q.k = [[q.s, q.k[0][1]], [q.e, q.k[1][1]]]; if (WORLD && CUES.answer) SHOTS[SHOTS.length - 1].e = S("answer") + 0.85;
    if (MAINF && /^evw[cde]/.test(VK)) { const nm = (w) => w.replace(/[.,?!:]$/, "").toLowerCase(), WA = [...CUES.eranos.words, ...CUES.finish.words], SW = (w, a = 0) => { const q = WA.find((v) => nm(v[0]) === w.toLowerCase() && v[1] >= a); return q ? q[1] : a; }, EW = (w, a = 0) => { const q = WA.find((v) => nm(v[0]) === w.toLowerCase() && v[1] >= a); return q ? q[2] : a; }, I1 = [260, 120, 1400], I2 = [285, 130, 1340], L = 0.15, w00 = M("eranos", "Eranos."), pres = SW("presses"), hE = EW("help", pres), tI = Math.max(hE + 2.2, SW("cited", hE) - 1), tOr = SW("or", tI), tAg = SW("Agents"), tOne = SW("one", tAg), tAny = SW("Anyone"), pr2 = SW("press", tAny), hE2 = EW("help", pr2), tThen = SW("Then", hE2), tPt = SW("point", tThen) - 0.45, tTeam = SW("team", tPt) - 0.3, tLib = SW("solution", tTeam) - 0.45, tSee = SW("See"), op = SW("Open"), oE = EW("one", op), tPr = SW("press", oE), grp = SW("group", tPr), grpE = EW("group", tPr), ad9 = SW("Adapt", oE), ZE = S("answer") + 0.85, a0 = w00 + 1, a1 = tI - L, b1 = tOr - L, b3 = tAg - L, b4 = tOne - L, b5 = tAny - L, b6 = tThen - L, b7 = tPt - L, b8 = tTeam - L, b9 = tLib - L, c0 = tSee - L, c1 = op - 1.3, c2 = tPr - L;
      SHOTS = [
        { s: a0, e: hE, k: [[a0, 10.9], [pres - 0.2, 11.4], [hE - 0.12, 13.62], [hE, 13.75]], a: I1, b: I2, l: TL_LIVE, r: [{ n: ["door1"], p: 6, s: pres - 0.1, e: hE }] },
        { s: hE, e: a1, k: [[hE, 18.4], [Math.min(a1, hE + 5), 22.9], [a1, 22.95]], a: [320, 507, 1290], b: [320, 520, 1260], l: TL_LIVE },
        { s: a1, e: b1, k: [[a1, 23.75], [a1 + 0.7, 25.36], [b1, 28.2]], a: [320, 300, 1300], b: [320, 310, 1260], l: TL_LIVE, r: [{ n: ["info"], p: 5, s: a1 + 0.3, e: b1 }] },
        { s: b1, e: b3, k: [[b1, 29.3], [SW("reusable") + 0.3, 31.57], [b3, 34.7]], a: [320, 310, 1260], b: [320, 310, 1200], l: TL_LIVE, r: [{ n: ["process"], p: 5, s: b1 + 0.2, e: b3 }] },
        { s: b3, e: b4, k: [[b3, 5.7], [b4, 9.5]], a: [290, 300, 1340], b: [290, 320, 1340], l: TL_LIVE, r: [{ n: ["strip"], p: 3, s: b3 + 0.2, e: b4 }] },
        { s: b4, e: b5, k: [[b4, 38.5], [b5, 41]], a: [300, 40, 1320], b: [300, 70, 1280], l: TL_EXQ, r: [{ n: ["steps", "auditrow"], p: 6, s: b4 + 0.2, e: b5 }] },
        { s: b5, e: hE2, k: [[b5, 47.2], [pr2 - 0.8, 48.4], [hE2 - 0.12, 50.7], [hE2, 50.85]], a: I1, b: I2, l: TL_LIVE, r: [{ n: ["door2"], p: 6, s: pr2 - 0.3, e: hE2 }] },
        { s: hE2, e: b6, k: [[hE2, 51.6], [b6, 54]], a: [300, 350, 1340], b: [300, 400, 1240], l: TL_LIVE, r: [{ n: ["connect"], p: 5, s: hE2 + 0.3, e: b6 }] },
        { s: b6, e: b7, k: [[b6, 37], [b7, 41]], a: [300, 120, 1320], b: [300, 160, 1300], l: TL_EXQ, r: [{ n: ["auditrow"], p: 6, s: SW("audits", tThen) - 0.2, e: b7 }] },
        { s: b7, e: b8, k: [[b7, 63.3], [b8, 67.2]], a: [280, 288, 1000], b: [280, 288, 960], l: TL_EXR, r: [{ n: ["sources"], p: 6, s: b7 + 0.4, e: b8 }] },
        { s: b8, e: b9, k: [[b8, 41], [b9, 45.7]], a: [290, 280, 1340], b: [290, 320, 1340], l: TL_EXQ, r: [{ n: ["decide"], p: 4, s: b8 + 0.4, e: b9 }] },
        { s: b9, e: c0, k: [[b9, 69.6], [b9 + 1.2, 73.1], [c0, 77]], a: [300, 90, 1300], b: [300, 397, 1300], l: TL_LIVE },
        { s: c0, e: oE, k: [[c0, 86.15], [c1, 86.4], [oE - 0.12, 88.89], [oE, 89]], a: [300, 397, 1300], b: [300, 397, 1300], l: TL_LIVE, r: [{ n: ["open"], p: 5, s: op - 0.9, e: oE }] },
        { s: oE, e: c2, k: [[oE, 90.5], [c2, 93.4]], a: [280, 100, 1100], b: [280, 130, 1040], l: TL_EXR },
        { s: c2, e: ZE, k: [[c2, 96.3], [grp, 98.98], [grpE, 99.1], [ZE, 99.1]], a: [300, 397, 1300], b: [320, 410, 1240], l: TL_LIVE, r: [{ n: ["adapt"], p: 5, s: ad9 - 0.2, e: grpE + 0.9 }] },
      ];
    } else if (MAINF && /^evwb/.test(VK)) { const WA = [...CUES.eranos.words, ...CUES.finish.words], SW = (w, a = 0) => { const q = WA.find((v) => v[0] === w && v[1] >= a); return q ? q[1] : a; }, EW = (w, a = 0) => { const q = WA.find((v) => v[0] === w && v[1] >= a); return q ? q[2] : a; }, I1 = [260, 120, 1400], I2 = [285, 130, 1340], w00 = M("eranos", "Eranos."), pres = SW("presses"), hE = EW("help,"), tIt = SW("It", hE), tOr = SW("or", tIt), tTh = SW("Their"), tAg = SW("and", tTh), tOne = SW("one", tAg), tAny = SW("Anyone"), pr2 = SW("press", tAny), hE2 = EW("help,", tAny), tThen = SW("Then", hE2), tAnd3 = SW("and", EW("result,", tThen)), tA = SW("A", tAnd3), tAnd4 = SW("and", tA), tSee = SW("See"), op = SW("Open"), oE = EW("one,", op), grp = SW("group."), grpE = EW("group."), ad9 = SW("Adapt", oE), ZE = S("answer") + 0.85, L = 0.15, TL9 = (n) => n; const a0 = w00 + 1, a1 = tIt - L, b1 = tOr - L, b2 = tTh - L, b3 = tAg - L, b4 = tOne - L, b5 = tAny - L, b6 = tThen - L, b7 = tAnd3 - L, b8 = tA - L, b9 = tAnd4 - L, c0 = tSee - L, c1 = op - 1.3;
      SHOTS = [
        { s: a0, e: hE, k: [[a0, 10.9], [pres - 0.2, 11.4], [hE - 0.12, 13.62], [hE, 13.75]], a: I1, b: I2, l: TL_LIVE, r: [{ n: ["door1"], p: 6, s: pres - 0.1, e: hE }] },
        { s: hE, e: a1, k: [[hE, 18.4], [a1, 22.9]], a: [320, 507, 1290], b: [320, 520, 1260], l: TL_LIVE },
        { s: a1, e: b1, k: [[a1, 23.75], [a1 + 0.7, 25.36], [b1, 28.2]], a: [320, 300, 1300], b: [320, 310, 1260], l: TL_LIVE, r: [{ n: ["info"], p: 5, s: a1 + 0.3, e: b1 }] },
        { s: b1, e: b2, k: [[b1, 29.3], [SW("reusable") + 0.3, 31.57], [b2, 34.7]], a: [320, 310, 1260], b: [320, 310, 1200], l: TL_LIVE, r: [{ n: ["process"], p: 5, s: b1 + 0.2, e: b2 }] },
        { s: b2, e: b3, k: [[b2, 36.9], [b3, 38.5]], a: [300, 30, 1340], b: [300, 60, 1300], l: TL_EXQ },
        { s: b3, e: b4, k: [[b3, 5.7], [b4, 9.5]], a: [290, 300, 1340], b: [290, 320, 1340], l: TL_LIVE, r: [{ n: ["strip"], p: 3, s: b3 + 0.2, e: b4 }] },
        { s: b4, e: b5, k: [[b4, 38.5], [b5, 41]], a: [300, 40, 1320], b: [300, 70, 1280], l: TL_EXQ, r: [{ n: ["steps", "auditrow"], p: 6, s: b4 + 0.2, e: b5 }] },
        { s: b5, e: hE2, k: [[b5, 47.2], [pr2 - 0.8, 48.4], [hE2 - 0.12, 50.7], [hE2, 50.85]], a: I1, b: I2, l: TL_LIVE, r: [{ n: ["door2"], p: 6, s: pr2 - 0.3, e: hE2 }] },
        { s: hE2, e: b6, k: [[hE2, 51.6], [b6, 54]], a: [300, 350, 1340], b: [300, 400, 1240], l: TL_LIVE, r: [{ n: ["connect"], p: 5, s: hE2 + 0.3, e: b6 }] },
        { s: b6, e: b7, k: [[b6, 37], [b7, 41]], a: [300, 120, 1320], b: [300, 160, 1300], l: TL_EXQ, r: [{ n: ["auditrow"], p: 6, s: SW("audits", tThen) - 0.2, e: b7 }] },
        { s: b7, e: b8, k: [[b7, 63.3], [b8, 67.2]], a: [280, 288, 1000], b: [280, 288, 960], l: TL_EXR, r: [{ n: ["sources"], p: 6, s: b7 + 0.4, e: b8 }] },
        { s: b8, e: b9, k: [[b8, 41], [b9, 45.7]], a: [290, 280, 1340], b: [290, 320, 1340], l: TL_EXQ, r: [{ n: ["decide"], p: 4, s: b8 + 0.4, e: b9 }] },
        { s: b9, e: c0, k: [[b9, 69.6], [b9 + 1.2, 73.1], [c0, 77]], a: [300, 90, 1300], b: [300, 397, 1300], l: TL_LIVE },
        { s: c0, e: oE, k: [[c0, 86.15], [c1, 86.4], [oE - 0.12, 88.89], [oE, 89]], a: [300, 330, 1400], b: [300, 397, 1300], l: TL_LIVE, r: [{ n: ["open"], p: 5, s: op - 0.9, e: oE }] },
        { s: oE, e: ZE, k: [[oE, 96.3], [grp, 98.98], [grpE, 99.1], [ZE, 99.1]], a: [300, 397, 1300], b: [320, 410, 1240], l: TL_LIVE, r: [{ n: ["adapt"], p: 5, s: ad9 - 0.2, e: grpE + 0.9 }] },
      ];
    } else if (MAINF) { const WD = CUES.eranos.words, FD = CUES.finish.words, wEnd = (L, w, after = 0) => { const q = L.find((v) => v[0] === w && v[1] >= after); return q ? q[2] : after; }, byR = (n) => SHOTS.findIndex((q) => q.r && q.r[0].n[0] === n), hold = (i, e9) => { const q = SHOTS[i], k = q.k, n = k.length, nx = SHOTS[i + 1]; k[n - 2][0] = e9 - 0.12; k[n - 1][0] = e9; q.e = e9; q.r[0].e = e9; nx.s = e9; nx.k[0][0] = e9; }; const iS = byR("steps"), iL = byR("log"); if (iS >= 0 && iL >= 0) { const qS = SHOTS[iS], qL = SHOTS[iL]; qS.e = qL.e; qS.k = [[qS.s, qS.k[0][1]], [qS.e, 41]]; qS.r[0].s = qL.r[0].s; qS.r[0].e = qL.e; SHOTS.splice(iL, 1); } const iD1 = byR("door1"); if (iD1 >= 0) { SHOTS[iD1].b = [285, 130, 1340]; hold(iD1, wEnd(WD, "help,")); } const iD2 = byR("door2"); if (iD2 >= 0) SHOTS[iD2].b = [285, 130, 1340]; if (iD2 >= 0) hold(iD2, wEnd(WD, "help,", SHOTS[iD2].r[0].s)); const iB = SHOTS.findIndex((q) => q.a && q.a[1] === 507); if (iB > 0) { const qB = SHOTS[iB], q9 = SHOTS[iB - 1]; qB.s = q9.s; qB.k[0][0] = q9.s; SHOTS.splice(iB - 1, 1); } const tF = FD.find((v) => v[0] === "Then")[1], grpE = FD[FD.length - 1][2], iA = SHOTS.findIndex((q, i) => i > SHOTS.length - 4 && q.r && q.r[0].n[0] === "adapt"); if (iA > 0) { const qA = SHOTS[iA], qZ = SHOTS[SHOTS.length - 1], kp = qA.k; const clickS = kp[1][1]; qA.e = qZ.e; qA.k = [[kp[0][0], kp[0][1]], [FD[FD.length - 2][1], clickS], [grpE, clickS + 0.12], [qZ.e, clickS + 0.12]]; qA.r[0].e = grpE + 0.9; qA.b = [320, 410, 1240]; SHOTS.splice(SHOTS.length - 1, 1); } const iR = SHOTS.findIndex((q, i) => i > 0 && SHOTS[i - 1].r && SHOTS[i - 1].r[0].n[0] === "open"), oF = FD.find((v) => v[0] === "one,")[2], rF = FD.find((v) => v[0] === "follow")[1]; const iO = SHOTS.findIndex((q) => q.r && q.r[0].n[0] === "open"); if (iO > 0) { SHOTS[iO].a = SHOTS[iO - 1].b.slice(); SHOTS[iO].b = SHOTS[iO - 1].b.slice(); hold(iO, wEnd(FD, "one,")); const qR = SHOTS[iO + 1], qSrc = SHOTS[iO + 2]; if (qSrc && qSrc.r && qSrc.r[0].n[0] === "sources") { const mid = FD.find((v) => v[0] === "follow")[1] - 0.1; qR.e = mid; qR.k[qR.k.length - 1][0] = mid; qSrc.s = mid; qSrc.k[0][0] = mid; qSrc.r[0].s = mid + 0.3; } } }
  }
  const shotsAt = (t) => { if (!TFS[TDIR]) return []; if (!SHOTS) shotsBuild(); const out = []; for (let i = 0; i < SHOTS.length; i++) { const q = SHOTS[i]; if (t >= q.s && t < q.e + 0.24) out.push(q); } return out; };
  const shotSrc = (q, t) => { const v9 = shotSrc0(q, t); return MAINF ? MAP9(v9) : v9; }; const shotSrc0 = (q, t) => { const k = q.k; if (t <= k[0][0]) return k[0][1]; for (let i = 0; i < k.length - 1; i++) if (t <= k[i + 1][0]) return mix(k[i][1], k[i + 1][1], (t - k[i][0]) / (k[i + 1][0] - k[i][0] || 1)); return k[k.length - 1][1]; };
  window.__prep = async (t) => { if (!TAKEON || t < S("eranos") + 2 || t >= S("connect") + 0.5) return; await tkLoad(); await Promise.all(shotsAt(t).map((q) => tkImg(tkFile(q, shotSrc(q, t))).p)); };
  window.__ringList = async () => { await tkLoad(); shotsAt(S("eranos") + 5); return SHOTS.flatMap((q) => (q.r || []).map((r) => ({ n: r.n.join("+"), s: Math.max(r.s, q.s) + 0.3, m: (Math.max(r.s, q.s) + Math.min(r.e, q.e)) / 2, e: Math.min(r.e, q.e) - 0.06 }))); };
  const NOCAP = /[?&]captions=0/.test(location.search);
  function drawShot(q, t, al, pa = al) { if (!TFS[TDIR]) { tkLoad(); return; } const fn = tkFile(q, shotSrc(q, t)), e = tkImg(fn), im = e.ok ? e.im : q.last; if (e.ok) q.last = e.im; if (!im) return; const x = 60, y = NOCAP ? 18 : 56, w = 1800, h = NOCAP ? 964 : 800, K = inOut((t - q.s) / (q.e - q.s)), cx = mix(q.a[0], q.b[0], K), cw = mix(q.a[2], q.b[2], K), ch = cw * h / w, srcT = shotSrc(q, t), lim9 = NOCAP && srcT > (MAINF ? MAP9(51.4) : 51.4) && srcT < (MAINF ? MAP9(57.8) : 57.8) ? 992 : 1080, cy = Math.min(mix(q.a[1], q.b[1], K), lim9 - ch), sc = w / cw;
    comp("page", "panel", () => { c.save(); c.globalAlpha = pa; c.shadowColor = "rgba(74,64,48,.28)"; c.shadowBlur = 34; c.shadowOffsetY = 12; rr(x, y, w, h, 18); c.fillStyle = CARD; c.fill(); c.restore(); c.save(); c.globalAlpha = al; rr(x, y, w, h, 18); c.clip(); c.drawImage(im, cx, cy, cw, ch, x, y, w, h);
      for (const r of q.r || []) { const a = soft((t - r.s) / 0.3) * (1 - soft((t - r.e + 0.2) / 0.2)); if (a <= 0.01) continue; const src9 = shotSrc(q, t), bs9 = r.n.map((n) => { let v = null; for (const e of RC[n] || []) { if (e[0] <= src9) v = e[1]; else break; } return v; }); if (bs9.some((v) => !v)) continue; const bx0 = Math.min(...bs9.map((v) => v[0])), by0 = Math.min(...bs9.map((v) => v[1])), bx1 = Math.max(...bs9.map((v) => v[0] + v[2])), by1 = Math.max(...bs9.map((v) => v[1] + v[3])), P0 = (r.p || 6) * sc, rx = x + (bx0 - cx) * sc - P0, ry = y + (by0 - cy) * sc - P0, rw = (bx1 - bx0) * sc + 2 * P0, rh = (by1 - by0) * sc + 2 * P0; if (rx < x + 4 || ry < y + 4 || rx + rw > x + w - 4 || ry + rh > y + h - 4) { (window.__ringOut = window.__ringOut || {})[r.n.join("+") + "@" + q.s.toFixed(1)] = 1; continue; } (window.__ringNow = window.__ringNow || []).push({ n: r.n.join("+"), t, box: LIFTON ? (() => { const m9 = c.getTransform(), P9 = [[rx, ry], [rx + rw, ry], [rx, ry + rh], [rx + rw, ry + rh]].map((q) => [m9.a * q[0] + m9.c * q[1] + m9.e, m9.b * q[0] + m9.d * q[1] + m9.f]), X9 = P9.map((q) => q[0]), Y9 = P9.map((q) => q[1]); return [Math.min(...X9), Math.min(...Y9), Math.max(...X9) - Math.min(...X9), Math.max(...Y9) - Math.min(...Y9)]; })() : [rx, ry, rw, rh] }); const pu = 0.5 + 0.5 * Math.sin((t - r.s) * 4.2); c.save(); c.globalAlpha = al * a * 0.42; c.fillStyle = "#F5F2EA"; c.beginPath(); c.rect(x, y, w, h); c.roundRect(rx, ry, rw, rh, 16); c.fill("evenodd"); c.restore(); c.save(); c.globalAlpha = al * a; c.strokeStyle = "rgba(36,81,155,.2)"; c.lineWidth = 10 + 6 * pu; rr(rx, ry, rw, rh, 16); c.stroke(); c.strokeStyle = "#24519B"; c.lineWidth = 3.5; rr(rx, ry, rw, rh, 16); c.stroke(); c.restore(); }
      c.restore(); });
    if (false) comp("page chip", "label", () => { const warn = q.l !== TL_LIVE; font(600, 26); const lw = c.measureText(q.l).width + 34; c.save(); rr(x + w - lw, y + h + 14, lw, 44, 22); c.fillStyle = CARD; c.fill(); c.strokeStyle = warn ? RUST : BLUE; c.lineWidth = 2; c.stroke(); c.fillStyle = warn ? RUST : BLUE; c.fillText(q.l, x + w - lw + 17, y + h + 45); c.restore(); }); }
  function lift9(k, fn, cy = 520) { const s0 = CARDM ? 0.9 : 1; if (k <= 0.001 && !CARDM) return fn(); c.save(); c.translate(960, cy); c.transform(s0 * mix(1, 0.62, k), s0 * mix(0, 0.31, k), s0 * mix(0, -0.62, k), s0 * mix(1, 0.31, k), 0, 0); c.translate(-960, -cy); LIFTON = true; fn(); LIFTON = false; c.restore(); }
  function takeScene(t) { if (WORLD) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); if (CARDM) stripes(t, LINE); const L9 = shotsAt(t); if (!L9.length) return; const q9 = L9[L9.length - 1], e0 = SHOTS[0].s, base = CARDM ? 0.08 : 0; let k9 = base; if (t < e0 + 0.9) k9 = mix(1, base, soft((t - e0) / 0.9)); else if (CARDM && q9 !== SHOTS[0]) k9 = base + 0.26 * (1 - soft((t - q9.s) / 0.7)); const al9 = soft((t - e0) / 0.3); lift9(k9, () => { const q0 = L9.length > 1 && t >= L9[1].s ? L9[1] : L9[0]; if (MAINF) drawShot(q0, t, q0 === SHOTS[0] ? al9 : 1, al9); else { drawShot(L9[0], t, al9); if (L9.length > 1 && t >= L9[1].s) drawShot(L9[1], t, soft((t - L9[1].s) / 0.22)); } }); return; } c.fillStyle = CARD; c.fillRect(0, 0, 1920, 1080); const L = shotsAt(t); if (!L.length) return; if (L.length === 1 || t < L[1].s) { drawShot(L[0], t, 1); return; } drawShot(L[0], t, 1); drawShot(L[1], t, soft((t - L[1].s) / 0.22)); }
  function sceneEranos(t) {
    const s = S("eranos"), w0 = M("eranos", "Eranos."), W_ = (w, n) => M("eranos", w, n), press = W_("press"), tell = W_("tell"), ask = W_("ask"), or0 = W_("Or"), their = W_("Their"), net = W_("network"), who = W_("Who"), anyone = W_("Anyone"), conn = W_("connect"), then0 = W_("Then"), every0 = W_("Every"), person = W_("person"), libr = (CUES.eranos.words.some((w) => w[0] === "finished") ? W_("finished") - 0.45 : W_("every")), see = W_("See");
    c.fillStyle = WORLD ? GROUND : CARD; c.fillRect(0, 0, 1920, 1080);
    if (t < w0 + 1.0) {
      if (TERR) { const z8 = 1 + 0.035 * clamp((t - s) / 8); c.save(); c.translate(960, 300); c.scale(z8, z8); c.translate(-960, -300); }
      if (TERR && CALM) { if (!TR) terBuild(); c.fillStyle = GROUND; c.fillRect(-200, -200, 2320, 1480); terCam(t); DK = 0; const k9 = soft(seg(t, MAINF ? w0 - 0.3 : w0 - 0.7, F(16))); c.save(); c.translate(960 - TCX * 0.8, 650 - TCY * 0.8 + k9 * 720); c.scale(0.8, 0.8); drawTerrainSet(t); c.restore(); } else if (STYLE === "kinetic") kineticBehind(t, "ngo"); else setBehind(t, s, { u: 58, y: 720, a: 0.72, leave: w0 - 0.5 });
      if (STYLE !== "kinetic" && t < w0 - 0.5) tagAnim();
      rise((VK === "evo" || VK === "evq" || VK === "evr") ? "So what do you do with spare tokens?" : /^evw[b-e]/.test(VK) ? "Teleion Fabric can run almost anything," : "Teleion Fabric can run almost anything.", 960, 170, 66, 600, s + 0.25, { t, center: true, w: 1600, gap: 3 });
      rise(/^evw[b-e]/.test(VK) ? "and we decided to put it to work, with" : "We're most proud to showcase our first public good example:", 960, 262, 44, 400, /^evw[b-e]/.test(VK) ? M("eranos", "and") : M("eranos", "We're"), { t, center: true, w: 1600, gap: 2, color: MUTED });
      const k = soft(seg(t, w0 - 0.05, F(12))); c.save(); c.beginPath(); c.rect(0, 360, 1920, 300); c.clip(); font(700, 200); c.fillStyle = BLUE; c.textAlign = "center"; c.fillText("Eranos", 960, 590 + (1 - k) * 250); c.textAlign = "left"; c.restore(); if (TERR) c.restore();
      return;
    }
    c.fillStyle = TONE; c.fillRect(0, 0, 1920, 1080);
    if (TAKEON) { takeScene(t); if (CUES.eranos.words.some((q) => q[0] === "See") && t >= see - 0.1 && t < see + 3.6) if (MAINF) pill("See it at eranosforgood.org", 960, 1030, { size: 36, w: 700, color: BLUE }); else pill("See it working at eranosforgood.org", 960, NOCAP ? 1030 : 905, { a: soft((t - see) / 0.3) * (1 - clamp((t - see - 3.3) / 0.3)), size: 56, w: 700, color: BLUE, stroke: BLUE, lw: 3, fill: CARD }); return; }
    const seq = [[w0 + 1.0, press, { img: "home", a: { x: 0, y: 0, s: 0.94 }, b: { x: 0, y: 0, s: 0.95 }, label: ER_LB }],
      [press, tell, { img: "home", a: { x: 0, y: 60, s: 0.94 }, b: { x: 0, y: 100, s: 0.95 }, label: ER_LB }],
      [tell, ask, { img: "ngo", a: { x: 0, y: 0, s: 0.71 }, b: { x: 0, y: 80, s: 0.74 }, label: ER_LB }],
      [ask, or0, { img: "ngo", a: { x: 0, y: 400, s: 0.71 }, b: { x: 0, y: 520, s: 0.74 }, label: ER_LB }],
      [or0, their, { img: "process", a: { x: 0, y: 0, s: 0.71 }, b: { x: 0, y: 760, s: 0.74 }, label: EX_LB, warn: true }],
      [their, net, { img: "example", a: { x: 0, y: 0, s: 0.71 }, b: { x: 0, y: 380, s: 0.74 }, label: EX_LB, warn: true }],
      [net, who, { img: "dash", a: { x: 0, y: 520, s: 0.71 }, b: { x: 0, y: 900, s: 0.74 }, label: "Live page, Nov 3" }],
      [who, anyone, { img: "home", a: { x: 0, y: 40, s: 0.94 }, b: { x: 0, y: 70, s: 0.95 }, label: ER_LB }],
      [anyone, then0, { img: "help", a: { x: 90, y: 640, s: 1.28 }, b: { x: 90, y: 700, s: 1.3 }, label: ER_LB }],
      [then0, every0, { img: "result", a: { x: 0, y: 0, s: 0.71 }, b: { x: 0, y: 30, s: 0.74 }, label: EX_LB, warn: true }],
      [every0, person, { img: "result", a: { x: 0, y: 300, s: 0.71 }, b: { x: 0, y: 860, s: 0.74 }, label: EX_LB, warn: true }],
      [person, libr, { img: "result", a: { x: 0, y: 0, s: 0.71 }, b: { x: 0, y: 40, s: 0.74 }, label: EX_LB, warn: true }],
      [see, E("eranos") - see < 12 ? see : see + (E("eranos") - see) / 7, { img: "home", a: { x: 0, y: 0, s: 0.94 }, b: { x: 0, y: 30, s: 0.95 }, label: ER_LB }],
      [libr, see, { img: "library", a: { x: 0, y: 0, s: 0.71 }, b: { x: 0, y: 760, s: 0.74 }, label: ER_LB }],
      ...(() => { const e0 = E("eranos"), hold = e0 - see; if (hold < 12) return []; const st = hold / 7, at = (i) => see + i * st; return [[at(1), at(2), { img: "ngo", a: { x: 0, y: 0, s: 0.71 }, b: { x: 0, y: 120, s: 0.71 }, label: ER_LB }], [at(2), at(3), { img: "example", a: { x: 0, y: 0, s: 0.71 }, b: { x: 0, y: 300, s: 0.71 }, label: EX_LB, warn: true }], [at(3), at(4), { img: "result", a: { x: 0, y: 300, s: 0.71 }, b: { x: 0, y: 760, s: 0.71 }, label: EX_LB, warn: true }], [at(4), at(5), { img: "library", a: { x: 0, y: 200, s: 0.71 }, b: { x: 0, y: 700, s: 0.71 }, label: ER_LB }], [at(5), at(6), { img: "dash", a: { x: 0, y: 520, s: 0.71 }, b: { x: 0, y: 860, s: 0.71 }, label: "Live page, Nov 3" }]]; })(),
      [E("eranos") - see < 12 ? see : see + ((E("eranos") - see) / 7) * 6, E("eranos"), { img: "home", a: { x: 0, y: 0, s: 0.94 }, b: { x: 0, y: 60, s: 0.95 }, label: ER_LB }]];
    if (TERR) { for (let i = 0; i < seq.length - 1; i++) { if (seq[i][2].img === seq[i + 1][2].img && seq[i + 1][0] <= seq[i][1] + 0.01) { seq[i] = [seq[i][0], seq[i + 1][1], { ...seq[i][2], b: seq[i + 1][2].b }]; seq.splice(i + 1, 1); i--; } } if (!TAKEON && t >= see - 0.1 && t < see + 3.6) { const a9 = soft((t - see) / 0.3) * (1 - clamp((t - see - 3.3) / 0.3)); pill("eranosforgood.org", 960, 900, { a: a9, size: 56, w: 700, color: BLUE, stroke: BLUE, lw: 3, fill: CARD }); } }
    if (DIR === "sheets" || DIR === "cutaway" || DIR === "parallax") {
      const uniq = []; seq.forEach((q, i) => { if (!uniq.some((u) => u[2].img === q[2].img)) uniq.push([q[0], q[1], q[2], uniq.length]); });
      uniq.forEach(([a, b, o, i]) => { { const im = IMG[o.img], sf = SHEETSAFE[o.img]; if (im && sf && t > w0 + 0.9) sheet({ ...o, a: { x: sf.x, y: sf.y, s: 1800 / sf.w }, b: { x: sf.x, y: sf.y, s: 1800 / sf.w }, label: null }, t, 1e9, 2e9, i); } });
      seq.forEach(([a, b, o], i) => { const a0 = i === 0 ? a + 1.1 : a + 0.15; if (t >= a0 && t < b - 0.1) sheet(o, t, a0, b - 0.1, i); });
    } else for (const [a, b, o] of seq) if (t >= a - 0.1 && t < b + 0.25) page(o, t, a - 0.1, b + 0.25);
  }
  function sceneFinish(t) { if (TAKEON) { takeScene(t); return; } c.fillStyle = CARD; c.fillRect(0, 0, 1920, 1080); const s = S("finish"), e0 = E("finish"), th = M("finish", "Then"); if (t < th) page({ img: "result", a: { x: 0, y: 300, s: 0.71 }, b: { x: 0, y: 700, s: 0.71 }, label: EX_LB, warn: true }, t, s - 0.1, th + 0.1); else page({ img: "library", a: { x: 0, y: 380, s: 0.74 }, b: { x: 0, y: 520, s: 0.74 }, label: ER_LB }, t, th - 0.1, e0 + 0.2); }
  function sceneAnswer(t) { const s = S("answer"), f = soft((t - s) / 2); terIdle(t, 10 + 30 * f, 0, TR ? TR.end - 0.01 : S("omninode") + CUES.omninode.seconds - 0.2); if (WORLD && TAKEON && t < s + 0.6) { const L9 = shotsAt(t), g9 = soft((t - s) / 0.6); if (L9.length) lift9(mix(CARDM ? 0.08 : 0, 1, g9), () => drawShot(L9[L9.length - 1], t, 1 - soft((t - s - 0.3) / 0.3))); } rise("AI is smart.", 960, 128, 76, 700, MAINF ? s + 0.55 : s + 0.05, { t, center: true, w: 1400, gap: 3 }); if (MAINF) { const k9 = soft((t - s - 0.6) / 0.5); c.save(); c.globalAlpha = k9; pill("Tell your agent to read teleionlabs.com/llms.txt, over HTTPS or MCP", 960, 1000, { size: 32, w: 600, color: BLUE, stroke: BLUE, fill: CARD }); c.restore(); } rise("Now the way we use it can be smart too.", 960, MAINF ? 912 : 815, 52, 600, M("answer", "Now") - 0.02, { t, center: true, w: 1500, gap: 3 }); }
  function sceneConnect(t) {
    if (TOPEN) { const s = S("connect"); terIdle(t, 40 + (EPIC ? 12 * soft((t - s) / 2.2) : 0), 0, TR ? TR.end - 0.01 : S("omninode") + CUES.omninode.seconds - 0.2); rise("Connect your agents today.", 960, 130, 76, 700, s + 0.05, { t, center: true, w: 1500, gap: 3 }); const k = MAINF ? 1 : soft(seg(t, s + 0.5, F(12))); c.save(); c.globalAlpha = k; pill("Tell your agent to read teleionlabs.com/llms.txt, over HTTPS or MCP", 960, MAINF ? 1000 : 815, { size: 34, w: 600, color: BLUE, stroke: BLUE, fill: CARD }); c.restore(); tagAnim(); return; }
    c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); const s = S("connect"), l = t - s;
    cam = camAt(1430, 480, 110);
    [[-3.2, 0], [0, -3.2], [-2.3, -2.3]].forEach((p) => { rail([p[0], p[1]], [0, 0], true, t); });
    blob(0, 0, 2.05, 1.2, 1.4); octo3(0, 0, 0.01, 1.7, 0.3, CARD); octo3(0, 0, 0.31, 1.25, 0.7, CARD);
    [[-3.2, 0, 0.14], [0, -3.2, 0.14], [-2.3, -2.3, 0.14]].forEach((p, i) => { const q = (l * 0.55 + i * 0.33) % 1; chip(mix(p[0], 0, q), mix(p[1], 0, q), 0.14, "task", 0.42); });
    rise("Connect your agents today.", TX, 430, 92 * V.ts, 700, s + 0.05, { t, w: 800, gap: 3 });
    const k = soft(seg(t, s + 0.8, F(12))); c.save(); c.globalAlpha = k; font(400, 38); c.fillStyle = MUTED; c.fillText("Tell your agent to read", TX, 610); font(700, 42); c.fillStyle = BLUE; c.fillText("teleionlabs.com/llms.txt", TX, 668); font(400, 30); c.fillStyle = MUTED; c.fillText("Over HTTPS or MCP.", TX, 726); c.restore();
    tagAnim();
  }

  // ================================================================== the set, rebuilt on one grid
  // A real platform with thickness, three named bays and an audit gate in line. One light (upper left, behind), one soft shadow, three face tones.
  // Dimming uses solid desaturated colors, never transparency. Names lie on the floor. Tasks and objects sit in numbered slots.
  const FACE = { top: 0, left: 0.08, right: 0.17 };
  // A layout is data: where the parts stand, the channels between them, where names lie, how the camera frames it.
  const LAYOUTS = {
    wide: { T: [-4.4, 3.3], N: [-0.55, -0.55], O: [3.3, -4.4], A: [3.4, -0.55, "x"], X0: -6.4, X1: 6.4, Y0: -6.6, Y1: 7.1, AGENT: [-8.2, 3.3], META: [-4.2, -7.0], u: 60, fx: 960, fy: 450, center: [-0.05, 0.25],
      lanes: { tn: [[-4.4, 1.75], [-4.4, -0.55], [-2.25, -0.55]], na: [[1.15, -0.55], [2.6, -0.55]], ao: [[4.2, -0.55], [5.5, -0.55], [5.5, -4.4], [4.85, -4.4]], on: [[1.75, -4.4], [-0.55, -4.4], [-0.55, -2.25]], ag: [[-7.9, 3.3], [-5.95, 3.3]], me: [[-4.2, -6.3], [-4.2, -1.75], [-1.75, -1.75]] },
      names: { T: [-6.0, 5.75, 58], N: [-2.2, 1.75, 60], O: [1.55, -2.1, 40], A: [2.5, 1.05, 46], F: [-0.2, 4.1, 72] }, bays: { T: [-6.15, 1.5, 3.9, 5.2], N: [-2.45, -2.45, 3.9, 5.4], O: [1.5, -6.2, 3.9, 5.0] } },
    row: { T: [-5.6, 0], N: [0, 0], O: [6.5, 0], A: [3.25, 0, "x"], X0: -8.1, X1: 8.9, Y0: -2.7, Y1: 4.9, AGENT: [-10.2, 0], META: [0, -4.8], u: 60, fx: 1040, fy: 470, center: [0.4, 1.1],
      lanes: { tn: [[-3.9, 0], [-1.72, 0]], na: [[1.72, 0], [2.45, 0]], ao: [[4.05, 0], [4.8, 0]], on: [[6.5, 1.7], [6.5, 2.1], [0, 2.1], [0, 1.72]], ag: [[-9.5, 0], [-7.3, 0]], me: [[0, -4.1], [0, -1.72]] },
      names: { T: [-7.3, 2.75, 62], N: [-2.1, 2.75, 62], O: [5.0, 2.75, 54], A: [2.25, 2.95, 44], F: [-7.6, 4.55, 66] }, bays: { T: [-7.7, -2.3, 4.3, 5.75], N: [-2.5, -2.3, 4.5, 5.75], O: [4.65, -2.3, 3.95, 5.75] } },
  };
  Object.assign(LAYOUTS, {
    triangle: { T: [-3.4, 3.6], N: [-3.4, -3.4], O: [3.6, -3.4], A: [0.6, -1.9, "x"], X0: -5.8, X1: 6.6, Y0: -5.8, Y1: 6.9, AGENT: [-7.9, 3.6], META: [-3.4, -8.0], u: 58, fx: 960, fy: 462, center: [0.35, 0.45],
      lanes: { tn: [[-3.4, 2.0], [-3.4, -1.65]], na: [[-1.75, -1.9], [-0.15, -1.9]], ao: [[1.35, -1.9], [3.6, -1.9], [3.6, -1.8]], on: [[2.0, -3.4], [-1.65, -3.4]], ag: [[-7.2, 3.6], [-5.0, 3.6]], me: [[-3.4, -7.3], [-3.4, -5.1]] },
      names: { T: [-5.0, 5.9, 54], N: [-2.9, -0.65, 50], O: [1.7, -0.9, 44], A: [-0.4, 0.5, 34], F: [1.0, 6.5, 62] }, bays: { T: [-5.3, 1.9, 3.8, 4.9], N: [-5.5, -5.5, 4.2, 5.8], O: [1.8, -5.3, 3.8, 5.2] } },
    raised: { T: [-4.4, 3.3], N: [-0.55, -0.55], O: [3.3, -4.4], A: [2.9, -0.55, "x"], Nz: 1.0, X0: -6.4, X1: 6.4, Y0: -6.6, Y1: 7.1, AGENT: [-8.6, 3.3], META: [-4.2, -8.5], u: 58, fx: 960, fy: 470, center: [-0.05, 0.25],
      lanes: { tn: [[-4.4, 1.75], [-4.4, -0.55], [-2.9, -0.55]], na: [[1.8, -0.55], [2.15, -0.55]], ao: [[3.65, -0.55], [5.5, -0.55], [5.5, -4.4], [4.85, -4.4]], on: [[1.75, -4.4], [-0.55, -4.4], [-0.55, -2.9]], ag: [[-7.9, 3.3], [-5.95, 3.3]], me: [[-4.2, -7.8], [-4.2, -2.1], [-2.5, -2.1]] },
      names: { T: [-6.0, 5.75, 58], N: [-2.4, 2.4, 60], O: [2.75, -2.15, 42], A: [2.0, 1.0, 38], F: [0.8, 6.75, 66] }, bays: { T: [-6.15, 1.5, 3.9, 5.2], N: [-3.0, -3.0, 4.9, 6.0], O: [1.5, -6.2, 3.9, 5.0] } },
    vee: { T: [-5.2, 0], N: [0, 0], O: [0, -5.2], A: [0, -2.65, "y"], X0: -7.6, X1: 5.2, Y0: -7.6, Y1: 4.4, AGENT: [-9.8, 0], META: [-7.0, -9.4], u: 62, fx: 1010, fy: 590, center: [-1.1, -1.6],
      lanes: { tn: [[-3.6, 0], [-1.72, 0]], na: [[0, -1.72], [0, -1.9]], ao: [[0, -3.4], [0, -3.6]], on: [[-1.6, -5.2], [-2.6, -5.2], [-2.6, -1.0], [-1.45, -1.0]], ag: [[-9.1, 0], [-6.8, 0]], me: [[-7.0, -8.7], [-7.0, -6.6], [-3.6, -6.6], [-3.6, -2.2], [-1.3, -2.2]] },
      names: { T: [-6.8, 2.2, 56], N: [-1.7, 2.2, 56], O: [1.9, -5.3, 44], A: [0.95, -2.6, 36], F: [0.2, 3.95, 56] }, bays: { T: [-7.0, -1.8, 3.8, 5.8], N: [-2.0, -1.85, 4.0, 5.9], O: [-1.9, -7.2, 3.9, 3.4] } },
    ring: { T: [-4.6, 0], N: [0, -4.6], O: [4.6, 0], A: [4.6, -3.0, "y"], X0: -6.8, X1: 6.8, Y0: -6.8, Y1: 5.9, AGENT: [-8.9, 0], META: [0, -8.8], u: 62, fx: 960, fy: 470, center: [0, -0.4],
      lanes: { tn: [[-4.6, -1.6], [-4.6, -4.6], [-1.72, -4.6]], na: [[1.72, -4.6], [4.6, -4.6], [4.6, -3.8]], ao: [[4.6, -2.2], [4.6, -1.6]], on: [[3.0, 0], [0, 0], [0, -2.9]], ag: [[-8.2, 0], [-6.2, 0]], me: [[0, -8.1], [0, -6.3]] },
      names: { T: [-6.3, 2.1, 52], N: [-3.5, -2.35, 42], O: [3.0, 2.1, 46], A: [1.9, -3.1, 32], F: [-2.6, 5.45, 62] }, bays: { T: [-6.4, -1.9, 3.7, 4.9], N: [-1.95, -6.5, 3.9, 5.0], O: [2.7, -1.75, 3.9, 4.8] } },
  });
  const namesFront = (T, N, A, O, y, sz) => ({ T: [T, y, sz], N: [N, y, sz], A: [A, y, sz * 0.8], O: [O, y, sz], F: [0, 0, 40] });
  Object.assign(LAYOUTS, {
    frow: { T: [-5.6, 0], N: [0, 0], O: [6.9, 0], A: [3.6, 0, "x"], AGENT: [-9.6, 0], META: [0, -5.2],
      lanes: { tn: [[-4.0, 0], [-1.72, 0]], na: [[1.72, 0], [2.75, 0]], ao: [[4.45, 0], [5.3, 0]], on: [[6.9, 1.6], [6.9, 2.4], [0, 2.4], [0, 1.72]], ag: [[-8.9, 0], [-7.2, 0]], me: [[0, -4.5], [0, -1.72]] }, names: namesFront(-5.6, 0, 3.6, 6.9, 3.1, 56), bays: { T: [-7.5, -2, 3.8, 4.3], N: [-2.1, -2, 4.2, 4.3], O: [5.0, -2, 3.8, 4.3] } },
    fstage: { T: [-6.1, 0], N: [0, 0], O: [7.0, 0], A: [3.85, 0, "x"], Nz: 0.8, AGENT: [-10, 0], META: [0, -5.6],
      lanes: { tn: [[-4.5, 0], [-2.45, 0]], na: [[2.45, 0], [3.0, 0]], ao: [[4.7, 0], [5.4, 0]], on: [[7.0, 1.6], [7.0, 3.0], [0, 3.0], [0, 2.4]], ag: [[-9.3, 0], [-7.7, 0]], me: [[0, -4.9], [0, -2.4]] }, names: namesFront(-6.1, 0, 3.85, 7.0, 3.6, 56), bays: { T: [-8, -2, 3.8, 4.6], N: [-2.6, -2.6, 5.2, 5.4], O: [5.1, -2, 3.8, 4.6] } },
  });
  const LNAME = !VW.iso ? (qs.get("layout") === "fstage" ? "fstage" : "frow") : qs.get("layout") || "wide", L0 = LAYOUTS[LNAME] || LAYOUTS.wide, DBV = qs.get("db") || "", NODES = Math.max(1, Math.min(3, parseInt(qs.get("nodes") || "1", 10))), STEPPED = qs.get("platform") === "stepped";
  const G = { Nz: 0, ...L0, R: DBV === "tall" ? 1.2 : DBV === "low" ? 1.95 : 1.6, DBH: DBV === "tall" ? 3.0 : DBV === "low" ? 1.05 : 1.9 };
  if (V.mirror) { FACE.left = 0.17; FACE.right = 0.08; }
  if (!VW.iso) { const kz = Math.cos((VW.pitch * Math.PI) / 180), ky = Math.sin((VW.pitch * Math.PI) / 180), my = -((G.Nz + 1.6) * kz) / ky - 1.5; G.META = [0, Math.min(my, -3.6)]; G.lanes = { ...G.lanes, me: [[0, G.META[1] + 0.75], G.lanes.me[1]] }; }
  const SL = G.R / 1.6;
  // Extra OmniNodes stand side by side in Fabric Intelligence's bay; each Task goes to one of them.
  const NLIST = (() => { const [x, y] = G.N; if (NODES === 1) return [[x, y, 1]]; const f0 = FRONT || VN === "high-three-quarter" ? [1, 0] : [0.7071, -0.7071], off = (NODES === 2 ? [-1.1, 1.1] : [-1.75, 0, 1.75]).map((d) => [d * f0[0] * (FRONT ? 1 : 1.4), d * f0[1] * 1.4]); return off.map((o) => [x + o[0], y + o[1], NODES === 2 ? 0.72 : 0.6]); })();
  const hex2 = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const mixHex = (a, b, k) => { const p = hex2(a), q = hex2(b); return `rgb(${Math.round(mix(p[0], q[0], k))},${Math.round(mix(p[1], q[1], k))},${Math.round(mix(p[2], q[2], k))})`; };
  let DK = 0; const D = (h) => (DK ? mixHex(h, "#EAE6DB", DK) : h);
  const faceCol = (h, f) => mixHex(h.startsWith("#") ? h : "#FFFFFF", "#3A3E45", FACE[f]);
  const col3 = (h, f) => (DK ? mixHex(faceCol(h, f).startsWith("rgb") ? rgbHex(faceCol(h, f)) : h, "#EAE6DB", DK) : faceCol(h, f));
  const rgbHex = (r) => { const m = r.match(/\d+/g).map(Number); return "#" + m.map((v) => v.toString(16).padStart(2, "0")).join(""); };
  const edge = () => `rgba(17,22,31,${0.2 * (1 - DK * 0.75)})`;
  function blob(x, y, rw, rd, h = 1) { // one soft shadow for everything: falls along +x, softer with height
    if (window.__CMP) return;
    const q = P(x + 0.32 * h, y + 0.1 * h, 0), w = rw * cam.u, d = rd * cam.u, a = 0.05 * (1 - DK * 0.7);
    for (let i = 5; i >= 0; i--) { c.beginPath(); c.ellipse(q[0], q[1], w + i * cam.u * 0.07, d + i * cam.u * 0.045, 0, 0, Math.PI * 2); c.fillStyle = warm(a); c.fill(); }
  }
  function block(x, y, z, w, d, h, top) { // three face tones; the side facing the camera depends on its yaw
    const fr = [P(x, y + d, z + h), P(x + w, y + d, z + h), P(x + w, y + d, z), P(x, y + d, z)], sx = VS >= 0 ? x + w : x, ri = [P(sx, y, z + h), P(sx, y + d, z + h), P(sx, y + d, z), P(sx, y, z)], li = [P(x, y, z + h), P(x + w, y, z + h), P(x + w, y + d, z + h), P(x, y + d, z + h)];
    poly(fr, col3(top, "left")); if (Math.abs(VS) > 0.01) poly(ri, col3(top, "right")); poly(li, D(top));
    c.strokeStyle = edge(); c.lineWidth = 1.4; c.lineJoin = "round"; for (const f of Math.abs(VS) > 0.01 ? [fr, ri, li] : [fr, li]) { path(f); c.stroke(); }
  }
  function floorText(x, y, lines0, size, col, weight = 700) {
    if (!VW.iso) { const a = P(x, y, 0.02), b = P(x + 1, y, 0.02), l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, ux = (b[0] - a[0]) / l, uy = (b[1] - a[1]) / l, k = (cam.u / 100) * 1.0, sg = ux < 0 ? -1 : 1; c.save(); c.transform(sg * ux * k, sg * uy * k, 0, k * (FRONT ? 0.9 : 0.8), a[0], a[1]); font(weight, size); c.fillStyle = col; c.textAlign = "center"; lines0.forEach((q, i) => c.fillText(q, 0, i * size * 1.08)); c.textAlign = "left"; c.restore(); return; }
    if (!V.mirror) { onPlaneU(x, y, 0.02, () => { font(weight, size); c.fillStyle = col; lines0.forEach((l, i) => c.fillText(l, 0, i * size * 1.1)); }); return; }
    font(weight, size); const wd = Math.max(...lines0.map((l) => c.measureText(l).width)) / 100, q = P(x + wd, y, 0.02), k = cam.u / 100; c.save(); c.transform(COS * k, -0.5 * k, COS * k, 0.5 * k, q[0], q[1]); c.fillStyle = col; lines0.forEach((l, i) => c.fillText(l, 0, i * size * 1.1)); c.restore(); }
  function onPlaneU(x, y, z, fn) { const q = P(x, y, z), k = cam.u / 100; c.save(); c.transform(COS * k, 0.5 * k, -COS * k, 0.5 * k, q[0], q[1]); fn(); c.restore(); }
  function cyl(x, y, z, r, h, top, side) { // r in units; side colors run left mid to right dark
    const a = P(x, y, z), b = P(x, y, z + h), rx = r * KX * cam.u, ry = r * KY * cam.u, g = c.createLinearGradient(a[0] - rx, 0, a[0] + rx, 0), s0 = side || top;
    g.addColorStop(0, col3(s0, "left")); g.addColorStop(0.55, col3(s0, "left")); g.addColorStop(1, col3(s0, "right"));
    c.beginPath(); c.ellipse(a[0], a[1], rx, ry, 0, 0, Math.PI); c.lineTo(b[0] - rx, b[1]); c.ellipse(b[0], b[1], rx, ry, 0, Math.PI, 0, true); c.closePath(); c.fillStyle = g; c.fill(); c.strokeStyle = edge(); c.lineWidth = 1.4; c.stroke();
    c.beginPath(); c.ellipse(b[0], b[1], rx, ry, 0, 0, Math.PI * 2); c.fillStyle = D(top); c.fill(); c.stroke();
    return b;
  }
  const isoRect = (x, y, w, d, z = 0.01) => [P(x, y, z), P(x + w, y, z), P(x + w, y + d, z), P(x, y + d, z)];
  // The platform fits the parts: an octagon around everything on it, plus a small margin. No empty section.
  function hullOfParts() {
    const pts = []; const addC = (p, r) => { for (let i = 0; i < 16; i++) { const a = (i * Math.PI) / 8; pts.push([p[0] + Math.cos(a) * r, p[1] + Math.sin(a) * r]); } };
    addC(G.T, G.R + 0.15); addC(G.O, G.R + 0.15); NLIST.forEach((n) => addC(n, 1.75 * n[2])); addC(G.A, 1.1);
    for (const k of ["tn", "na", "ao", "on"]) CH[k].forEach((q) => addC(q, 0.45));
    const nameBox = (n, ls, w0) => { const sz = n[2] / 100, wd = (w0 * n[2]) / 56 / 100; if (VW.iso) { pts.push([n[0], n[1] - sz], [n[0] + wd, n[1] - sz], [n[0], n[1] + sz * (ls - 0.8)], [n[0] + wd, n[1] + sz * (ls - 0.8)]); } else { const ky = 1 / (KY || 1); pts.push([n[0] - wd / 2, n[1] - sz * 0.6], [n[0] + wd / 2, n[1] - sz * 0.6], [n[0] - wd / 2, n[1] + sz * ls * ky * 0.8], [n[0] + wd / 2, n[1] + sz * ls * ky * 0.8]); } };
    const NM = G.names; nameBox(NM.T, 2, 240); nameBox(NM.N, 2, 340); nameBox(NM.A, 2, 300); nameBox(NM.O, 2, 370); if (VW.iso) nameBox(NM.F, 1, 500);
    const m = 0.45; let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, a0 = 1e9, a1 = -1e9, b0 = 1e9, b1 = -1e9; for (const [x, y] of pts) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); a0 = Math.min(a0, x + y); a1 = Math.max(a1, x + y); b0 = Math.min(b0, x - y); b1 = Math.max(b1, x - y); }
    x0 -= m; x1 += m; y0 -= m; y1 += m; a0 -= m * 1.4; a1 += m * 1.4; b0 -= m * 1.4; b1 += m * 1.4;
    const clip = (poly0, f) => { const out = []; for (let i = 0; i < poly0.length; i++) { const p = poly0[i], q = poly0[(i + 1) % poly0.length], fp = f(p), fq = f(q); if (fp >= 0) out.push(p); if (fp * fq < 0) { const k = fp / (fp - fq); out.push([p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k]); } } return out; };
    let hp = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]; hp = clip(hp, (p) => p[0] + p[1] - a0); hp = clip(hp, (p) => a1 - p[0] - p[1]); hp = clip(hp, (p) => p[0] - p[1] - b0); hp = clip(hp, (p) => b1 - p[0] + p[1]);
    return { hp, x0, x1, y0, y1 };
  }
  let HULL = null, FAB = false;
  const scalePoly = (q, k) => { const cx = q.reduce((a, p) => a + p[0], 0) / q.length, cy = q.reduce((a, p) => a + p[1], 0) / q.length; return q.map((p) => [cx + (p[0] - cx) * k, cy + (p[1] - cy) * k]); };
  function slabPoly(q, zTop, Z, top, sideL, sideR, line) {
    for (let i = 0; i < q.length; i++) { const a = q[i], b = q[(i + 1) % q.length], nx = b[1] - a[1], ny = -(b[0] - a[0]), nY = nx * VS + ny * VC, nX = nx * VC - ny * VS; if (nY <= 0.001) continue; const f = [P(a[0], a[1], zTop), P(b[0], b[1], zTop), P(b[0], b[1], zTop - Z), P(a[0], a[1], zTop - Z)]; poly(f, nX * MX > 0.2 * Math.hypot(nx, ny) ? sideR : sideL); c.strokeStyle = shade(0.14); c.lineWidth = 1.3; path(f); c.stroke(); }
    const tp = q.map((p) => P(p[0], p[1], zTop)); poly(tp, top); if (line) { c.strokeStyle = line; c.lineWidth = 3; c.lineJoin = "round"; path(tp); c.stroke(); } return tp;
  }
  function slabFloor(t, a) {
    if (!HULL) HULL = hullOfParts(); const q = HULL.hp, Z = FRONT ? 0.72 : 0.55;
    if (STEPPED) slabPoly(scalePoly(q, 1.1), -Z, 0.42, "#F1EDE2", "#E2DCCF", "#D2CBBB", null);
    if (!window.__CMP) for (let i = 4; i >= 0; i--) poly(scalePoly(q, 1 + i * 0.012).map((p) => P(p[0] + 0.35, p[1] + 0.15, -Z - (STEPPED ? 0.42 : 0))), warm(0.045 * a));
    const tp = slabPoly(q, 0, Z, CARD, "#E6E1D4", "#D6D0C1", BLUE);
    c.save(); path(tp); c.clip(); c.strokeStyle = "rgba(226,220,207,.75)"; c.lineWidth = 1.2; const { x0, x1, y0, y1 } = HULL; for (let x = Math.ceil(x0 / 2) * 2; x < x1; x += 2) { const p0 = P(x, y0), p1 = P(x, y1); c.beginPath(); c.moveTo(p0[0], p0[1]); c.lineTo(p1[0], p1[1]); c.stroke(); } for (let y = Math.ceil(y0 / 2) * 2; y < y1; y += 2) { const p0 = P(x0, y), p1 = P(x1, y); c.beginPath(); c.moveTo(p0[0], p0[1]); c.lineTo(p1[0], p1[1]); c.stroke(); } c.restore();
    if (TOPH && !FAB) { const a0 = P((x0 + x1) / 2, y1, -Z * 0.28); font(700, Math.round(cam.u * 0.42)); c.fillStyle = BLUE; c.textAlign = "center"; c.fillText("Teleion Fabric", a0[0], a0[1] + cam.u * 0.13); c.textAlign = "left"; }
  }
  function bay(k, lit) { const b = G.bays[k], col = k === "O" ? RUST : BLUE, q = isoRect(b[0], b[1], b[2], b[3], 0.015); poly(q, lit ? (k === "O" ? SAND : PALE) : "#F6F3EA"); c.strokeStyle = lit ? col : "rgba(138,132,118,.45)"; c.lineWidth = lit ? 2.5 : 1.3; path(q); c.stroke(); }
  // Channels: crisp recessed slots that end exactly at the rim of what they connect.
  function channel(pts, on, col) { const w = 0.27, seg0 = (a, b) => { const dx = Math.sign(b[0] - a[0]), dy = Math.sign(b[1] - a[1]), nx = -dy * w, ny = dx * w; const q = [P(a[0] + nx - dx * w * 0, a[1] + ny, 0.02), P(b[0] + nx, b[1] + ny, 0.02), P(b[0] - nx, b[1] - ny, 0.02), P(a[0] - nx, a[1] - ny, 0.02)]; poly(q, on ? mixHex(col, "#FFFFFF", 0.72) : "#E9E4D8"); c.strokeStyle = on ? col : "rgba(138,132,118,.7)"; c.lineWidth = 1.6; [[q[0], q[1]], [q[2], q[3]]].forEach(([m, n]) => { c.beginPath(); c.moveTo(m[0], m[1]); c.lineTo(n[0], n[1]); c.stroke(); }); };
    for (let i = 0; i < pts.length - 1; i++) seg0(pts[i], pts[i + 1]); for (let i = 1; i < pts.length - 1; i++) { const q = pts[i]; poly(isoRect(q[0] - w, q[1] - w, 2 * w, 2 * w, 0.02), on ? mixHex(col, "#FFFFFF", 0.72) : "#E9E4D8"); } }
  const CH = G.lanes;
  // Routes follow the channels. Tasks lift out of a slot, ride the channel, hop in and land.
  const LZ = 0.1, topT = G.DBH + 0.02, topN = 1.32, xyz = (p, z = LZ) => [p[0], p[1], z];
  const hopIn = (from, c0, ztop) => [[from[0], from[1], LZ], [mix(from[0], c0[0], 0.45), mix(from[1], c0[1], 0.45), ztop + 0.5], [c0[0], c0[1], ztop + 0.42], [c0[0], c0[1], ztop]];
  const hopOut = (c0, to, ztop) => [[c0[0], c0[1], ztop], [c0[0], c0[1], ztop + 0.5], [mix(c0[0], to[0], 0.55), mix(c0[1], to[1], 0.55), ztop + 0.5], [to[0], to[1], LZ]];
  const chain = (...a) => a.flat();
  const G_A = [G.A[0], G.A[1]], topNmain = 0, tn0 = CH.tn[0], tnE = CH.tn[CH.tn.length - 1], naS = CH.na[0], aoS = CH.ao[0], aoE = CH.ao[CH.ao.length - 1], onS = CH.on[0], onE = CH.on[CH.on.length - 1];
  const topFor = (n) => G.Nz + 0.3 + (0.72 + 0.3) * n[2]; // top of a node of this scale
  const R3For = (n) => ({ tn: chain(hopOut(G.T, tn0, topT), CH.tn.slice(1).map((q) => xyz(q)), hopIn(tnE, n, topFor(n)).slice(1)),
    tpre: chain(hopOut(G.T, tn0, topT), CH.tn.slice(1).map((q) => xyz(q))),
    thold: chain([xyz(tnE)], hopIn(tnE, n, topFor(n)).slice(1)),
    na: chain(hopOut(n, naS, topFor(n)), CH.na.slice(1).map((q) => xyz(q)), [xyz(G_A)]),
    ao: chain([xyz(G_A)], CH.ao.map((q) => xyz(q)), hopIn(aoE, G.O, topT).slice(1)),
    on: chain(hopOut(G.O, onS, topT), CH.on.slice(1).map((q) => xyz(q)), hopIn(onE, n, topFor(n)).slice(1)),
    drop: [[G.O[0], G.O[1], 4.2], [G.O[0], G.O[1], topT]] });
  const R3S = NLIST.map(R3For);
  const key3 = (m) => { const k = routeKey(m); if (k) return k; const r = m.route; if (r[0] === tTop && r.length === 3) return "tpre"; if (r[0][0] === -1.5) return "thold"; return null; };
  const SLOTS = [[-0.72, -0.78], [0, -0.78], [0.72, -0.78], [-0.72, 0.1], [0, 0.1], [0.72, 0.1]].map((q) => [q[0] * SL, q[1] * SL]);
  function slotPad(cx, cy, i, z) { const q = SLOTS[i], s = 0.56; poly(isoRect(cx + q[0] - s / 2, cy + q[1] - s / 2, s, s, z), DK ? "rgba(17,22,31,.025)" : "rgba(17,22,31,.06)"); }
  // birth times, so anything new lands softly instead of appearing
  let BIRTHS = null;
  function births() { let T = 0, O = 0; const tb = [], ob = []; for (const e of stock) { if (e.set !== undefined) { tb.length = 0; for (let i = 0; i < e.set; i++) tb.push(e.t + i * 0.07); T = e.set; } else if (e.T > 0) { tb.push(e.t); } else if (e.T < 0) { for (let n = 0; n < -e.T; n++) tb.push(null); } if (e.O > 0) ob.push(e.t); } BIRTHS = { ob }; }
  const buildK = (t, at) => (MO.build ? (MO.build === "drop" ? pop(seg(t, at, F(16))) : inOut(seg(t, at, F(20)))) : 1);
  function dbBody(cx, cy, col) {
    blob(cx, cy, G.R + 0.35, (G.R + 0.35) * 0.58, 2);
    for (let i = 0; i < 3; i++) { cyl(cx, cy, i * (G.DBH / 3), G.R, G.DBH / 3 - 0.05, CARD, CARD); const a = P(cx, cy, i * (G.DBH / 3) + 0.2), rx = G.R * KX * cam.u, ry = G.R * KY * cam.u; c.beginPath(); c.ellipse(a[0], a[1], rx, ry, 0, 0.14 * Math.PI, 0.86 * Math.PI); c.strokeStyle = D(col); c.lineWidth = 3.5; c.stroke(); }
    const top = P(cx, cy, G.DBH), rim = G.R * 0.88; c.beginPath(); c.ellipse(top[0], top[1], rim * KX * cam.u, rim * KY * cam.u, 0, 0, Math.PI * 2); c.strokeStyle = D(LINE); c.lineWidth = 2; c.stroke(); return top;
  }
  function drawT(t) {
    const { T: st } = stockAt(t), [cx, cy] = G.T, top = dbBody(cx, cy, BLUE), z = G.DBH;
    const open = moves.reduce((m, q) => { const k = key3(q); return (k === "tn" || k === "tpre") && t > q.t0 - 0.2 && t < q.t0 + 0.45 ? Math.max(m, Math.sin(Math.PI * clamp((t - q.t0 + 0.2) / 0.65))) : m; }, 0);
    for (let i = 0; i < 6; i++) slotPad(cx, cy, i, z + 0.01);
    if (open > 0) { c.beginPath(); c.ellipse(top[0], top[1], 0.42 * KX * cam.u * open, 0.42 * KY * cam.u * open, 0, 0, Math.PI * 2); c.fillStyle = D("#C9C3B3"); c.fill(); }
    for (let i = 0; i < Math.min(6, st); i++) { const q = SLOTS[i]; block(cx + q[0] - 0.24, cy + q[1] - 0.24, z + 0.02, 0.48, 0.48, 0.2, BLUE); }
  }
  function drawO(t) {
    const { O: st } = stockAt(t), [cx, cy] = G.O, z = G.DBH; dbBody(cx, cy, RUST);
    for (let i = 0; i < 6; i++) slotPad(cx, cy, i, z + 0.01);
    const n = Math.min(12, st);
    for (let i = 0; i < n; i++) { const q = SLOTS[i % 6], lvl = i >= 6 ? 1 : 0, b = BIRTHS.ob[Math.max(0, Math.min(BIRTHS.ob.length - 1, st - n + i))], d = b === undefined ? 1 : pop(seg(t, b, F(14))); block(cx + q[0] - 0.24, cy + q[1] - 0.24, z + 0.02 + lvl * 0.28 + (1 - d) * 0.8, 0.48, 0.48, 0.26, RUST); }
  }
  const nodeOf = (m) => m.ni === undefined ? (m.ni = Math.floor(m.t0 * 3.7 + 0.5) % NODES) : m.ni;
  function nodeWork(t, ni) { // ring fills while the node works
    let k = 0; for (const m of moves) { const q = key3(m); if ((q === "tn" || q === "thold") && nodeOf(m) === ni && t >= m.t1 - 0.05 && t < m.t1 + 1.25) k = Math.max(k, clamp((t - m.t1 + 0.05) / 1.15)); } return k;
  }
  function glyph(kind, x, y, r, col) { c.strokeStyle = col; c.fillStyle = col; c.lineWidth = Math.max(2.5, r * 0.16); c.lineCap = "round"; c.lineJoin = "round";
    if (kind === "rule") { for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(x - r, y - r * 0.5 + i * r * 0.5); c.lineTo(x + r, y - r * 0.5 + i * r * 0.5); c.stroke(); } }
    else if (kind === "model") { c.beginPath(); for (let i = 0; i < 8; i++) { const a = (i * Math.PI) / 4, m = i % 2 ? r * 0.36 : r; const px = x + Math.cos(a) * m, py = y + Math.sin(a) * m * 0.62; i ? c.lineTo(px, py) : c.moveTo(px, py); } c.closePath(); c.fill(); }
    else if (kind === "reuse") { c.beginPath(); c.ellipse(x, y, r, r * 0.6, 0, 0.3, Math.PI * 1.7); c.stroke(); c.beginPath(); c.moveTo(x + r * 0.95, y - r * 0.5); c.lineTo(x + r * 0.95, y - r * 0.05); c.lineTo(x + r * 0.45, y - r * 0.25); c.closePath(); c.fill(); }
    else if (kind === "learn") { [0, 1, 2].forEach((i) => { const h = r * (0.5 + i * 0.4); c.fillRect(x - r + i * r * 0.78, y + r * 0.55 - h, r * 0.5, h); }); }
    else { c.beginPath(); c.ellipse(x, y, r * 0.55, r * 0.33, 0, 0, Math.PI * 2); c.fill(); }
    c.lineCap = "butt"; }
  function drawN(t, n, ni) { // three tiers: plinth, body, lens with a progress ring and a working glyph
    const [x, y, sc] = n, Z = G.Nz;
    if (Z && ni === 0) { blob(x + 0.2, y + 0.2, 3.0, 1.8, 1.6); block(G.N[0] - 2.3, G.N[1] - 2.3, 0, 4.6, 4.6, Z, "#F4F0E6"); }
    if (!Z) blob(x, y, 2.05 * sc, 1.2 * sc, 1.4); octo3(x, y, Z + 0.01, 1.7 * sc, 0.3, CARD); octo3(x, y, Z + 0.31, 1.25 * sc, 0.72 * sc, CARD);
    const k = n[4] !== undefined ? n[4] : nodeWork(t, ni), m = modeAt(t), top = P(x, y, topFor(n)), rx = 0.92 * sc * KX * cam.u, ry = 0.92 * sc * KY * cam.u;
    c.beginPath(); c.ellipse(top[0], top[1], rx, ry, 0, 0, Math.PI * 2); c.fillStyle = D("#F2EEE3"); c.fill(); c.lineWidth = Math.max(5, cam.u * 0.1 * sc); c.strokeStyle = D(LINE); c.stroke();
    const start = -Math.PI / 2 + ((t * 0.12) % 6.283) * (k > 0 ? 0 : 1); c.beginPath(); c.ellipse(top[0], top[1], rx, ry, 0, start, start + (k > 0 ? k * 6.283 : 0.5)); c.strokeStyle = D(BLUE); c.stroke();
    const g = n[3] !== undefined ? n[3] : !m ? null : /Reuse/.test(m.name) ? "reuse" : /Muse|Non|Cheaper/.test(m.name) ? "model" : /Determ/.test(m.name) ? "rule" : "learn"; c.save(); c.translate(top[0], top[1]); c.scale(1, Math.max(0.55, KY / 0.7071)); glyph(g, 0, 0, cam.u * 0.42 * sc, D(g === "reuse" ? RUST : BLUE)); c.restore();
  }
  function octo3(x, y, z, r, h, top) { const NS = 8, pts = (zz) => [...Array(NS)].map((_, i) => { const a = Math.PI / NS + (i * 2 * Math.PI) / NS; return P(x + Math.cos(a) * r, y + Math.sin(a) * r, zz); }), low = pts(z), up = pts(z + h);
    [...Array(NS).keys()].sort((p, q) => (low[p][1] + low[(p + 1) % NS][1]) - (low[q][1] + low[(q + 1) % NS][1])).forEach((i) => { const j = (i + 1) % NS, nx = low[j][0] + low[i][0] - 2 * P(x, y, z)[0], f = [low[i], low[j], up[j], up[i]]; poly(f, nx < -cam.u * 0.3 ? col3(top, "left") : nx > cam.u * 0.3 ? col3(top, "right") : mixHex(rgbHex2(col3(top, "left")), rgbHex2(col3(top, "right")), 0.5)); c.strokeStyle = edge(); c.lineWidth = 1.2; path(f); c.stroke(); });
    poly(up, D(top)); c.strokeStyle = edge(); c.lineWidth = 1.4; path(up); c.stroke(); }
  const rgbHex2 = (v) => (v[0] === "#" ? v : rgbHex(v));
  function drawA(t, passing) { // the audit is a gate: Tasks pass through it, a check draws itself on the lintel
    if (FRONT) { const [x, y] = G.A; if (passing === "back") { block(x - 0.8, y - 0.8, 0, 1.6, 1.6, 0.34, "#F7EADF"); return; }
      const on = approvals(t), q = P(x, y - 0.55, 1.15), r = cam.u * 0.6; block(x - 0.1, y - 0.6, 0.34, 0.2, 0.12, 0.4, CARD); c.beginPath(); c.arc(q[0], q[1], r, 0, Math.PI * 2); c.fillStyle = D(on.k > 0 ? RUST : "#FFFDF8"); c.fill(); c.strokeStyle = D(RUST); c.lineWidth = 3; c.stroke();
      const k = on.k > 0 ? on.k : 1, p0 = [q[0] - r * 0.5, q[1]], p1 = [q[0] - r * 0.1, q[1] + r * 0.38], p2 = [q[0] + r * 0.55, q[1] - r * 0.4]; c.strokeStyle = on.k > 0 ? "#FFFDF8" : D("#E3C9B8"); c.lineWidth = r * 0.2; c.lineCap = "round"; c.beginPath(); c.moveTo(p0[0], p0[1]); if (k < 0.4) c.lineTo(mix(p0[0], p1[0], k / 0.4), mix(p0[1], p1[1], k / 0.4)); else { c.lineTo(p1[0], p1[1]); c.lineTo(mix(p1[0], p2[0], (k - 0.4) / 0.6), mix(p1[1], p2[1], (k - 0.4) / 0.6)); } c.stroke(); c.lineCap = "butt"; return; }
    const [x, y, ax] = G.A, along0 = ax === "x", post = (d) => (along0 ? block(x - 0.2, y + d - 0.2, 0.01, 0.4, 0.4, 1.35, CARD) : block(x + d - 0.2, y - 0.2, 0.01, 0.4, 0.4, 1.35, CARD));
    if (passing === "back") { const q = along0 ? isoRect(x - 0.75, y - 1.05, 1.5, 2.1, 0.015) : isoRect(x - 1.05, y - 0.75, 2.1, 1.5, 0.015); poly(q, D("#F7EADF")); c.strokeStyle = D(RUST); c.lineWidth = 1.6; path(q); c.stroke(); post(-0.85); return; }
    blob(x, y, 0.85, 0.5, 1); post(0.85); if (along0) block(x - 0.28, y - 1.08, 1.35, 0.56, 2.16, 0.3, "#F7EADF"); else block(x - 1.08, y - 0.28, 1.35, 2.16, 0.56, 0.3, "#F7EADF");
    const on = approvals(t), q = P(x, y, 1.65), r = cam.u * 0.3; c.beginPath(); c.ellipse(q[0], q[1], r, r * 0.58, 0, 0, Math.PI * 2); c.fillStyle = D(on.k > 0 ? RUST : "#FFFDF8"); c.fill(); c.strokeStyle = D(RUST); c.lineWidth = 2; c.stroke();
    if (on.k > 0) { const k = on.k, p0 = [q[0] - r * 0.5, q[1]], p1 = [q[0] - r * 0.1, q[1] + r * 0.3], p2 = [q[0] + r * 0.55, q[1] - r * 0.32]; c.strokeStyle = "#FFFDF8"; c.lineWidth = Math.max(3, r * 0.2); c.lineCap = "round"; c.beginPath(); c.moveTo(p0[0], p0[1]); if (k < 0.4) c.lineTo(mix(p0[0], p1[0], k / 0.4), mix(p0[1], p1[1], k / 0.4)); else { c.lineTo(p1[0], p1[1]); c.lineTo(mix(p1[0], p2[0], (k - 0.4) / 0.6), mix(p1[1], p2[1], (k - 0.4) / 0.6)); } c.stroke(); c.lineCap = "butt"; }
  }
  const approvals = (t) => { let k = 0; for (const m of moves) if (key3(m) === "na" && t >= m.t1 - 0.3 && t < m.t1 + 1.5) k = Math.max(k, clamp((t - m.t1 + 0.3) / 0.45)); return { k }; };
  function drawAgent() { const [x, y] = G.AGENT; blob(x, y, 0.9, 0.55, 0.7); block(x - 0.7, y - 0.7, 0, 1.4, 1.4, 0.6, CARD); }
  function drawMeta() { const [x, y] = G.META; blob(x, y, 0.95, 0.55, 0.8); block(x - 0.75, y - 0.75, 0, 1.5, 1.5, 0.7, "#DDE5F2"); }
  function moverList(t) { const out = []; for (const m of moves) { if (t < m.t0) continue; const dur = (m.t1 - m.t0) * MO.k; if (t >= m.t0 + dur) continue; const key = key3(m), r = R3S[nodeOf(m)][key]; if (!r) continue; const f = (t - m.t0) / dur, e = key === "drop" ? pop(f) : MO.linear ? f : inOut(f), q = along3(r, e), col = m.type === "task" ? BLUE : RUST, hz = MO.hop && q[2] < 0.2 ? Math.abs(Math.sin(e * Math.PI * 14)) * MO.hop : 0; out.push({ d: depth(q[0], q[1]) + q[2] * 0.9, fn: () => block(q[0] - 0.24, q[1] - 0.24, q[2] + hz, 0.48, 0.48, m.type === "task" ? 0.2 : 0.26, col) }); }
    if (MO.flow) { // a steady stream on the belts between Tasks
      const belt = (pts, col, sp, n) => { const r = pts.map((q) => xyz(q)); for (let i = 0; i < n; i++) { const q = along3(r, ((t * sp + i / n) % 1)); out.push({ d: depth(q[0], q[1]), fn: () => block(q[0] - 0.16, q[1] - 0.16, LZ, 0.32, 0.32, 0.12, col) }); } };
      if (t > S("parts") + 2) { belt(CH.tn, BLUE, 0.3, 2); belt(CH.on, RUST, 0.11, 3); } }
    return out; }
  const along3 = (r, k) => along(r, k);
  // Fixed places for everything that isn't on the floor: progress row, then one callout row beneath it.
  function callouts(t) {
    const row = (items, y0r, tone) => { const y = TOPH ? y0r + 6 : y0r; let x = V.mirror ? 900 : 60; if (TOPH && !V.mirror) { font(600, 26); let w0 = 0; for (const it of items) w0 += c.measureText(it[0]).width + 44; x = Math.max(780, 1860 - w0); } font(600, 26); const order = items; if (V.mirror) { let w0 = 0; for (const it of order) w0 += c.measureText(it[0]).width + 44; x = 1860 - w0; } for (const [txt, at] of order) { const w = c.measureText(txt).width + 30; if (t >= at) pill(txt, x + w / 2, y, { a: soft(seg(t, at, F(9))), size: 26, ...tone }); x += w + 14; font(600, 26); } };
    const rust = { color: RUST, stroke: RUST, fill: SAND }, blue = { color: BLUE, stroke: BLUE, fill: PALE };
    if (t >= B.reusable && t < B.third) row([["Reusable code", B.reusable], ["Agent kit configs", B.reusable + 0.85], ["News", B.reusable + 1.7], ["GitHub repos", B.reusable + 2.55]], 76, rust);
    if (t >= B.every && t < B.third) row([["Every version kept, with its source", B.every]], 132, rust);
    if (t >= B.conv && t < B.gives) row([["Conversation", B.conv], ["Shimming", B.conv + 0.5], ["Decisioning", B.conv + 1], ["Search and retrieval", B.conv + 1.5]], 76, blue);
    if (t >= B.gives && t < B.together) row([["Cheap, valuable direction", B.gives], ["Or a direct response", B.direct]], 76, blue);
    if (t >= B.sWait - 0.3 && t < B.done[3]) row([["Task 4 waits for 2 and 3", B.sWait - 0.3]], 132, rust);
    if (t >= B.oModel && t < B.oReuse) row([["The most appropriate model: Muse Spark", B.oModel]], 76, blue);
    if (t >= B.oImprove - 0.2 && t < B.oDet) row([[`OmniNode version ${Math.floor(clamp((t - B.oImprove) / Math.max(0.5, B.oDet - B.oImprove - 0.3)) * 2.999) + 1}`, B.oImprove - 0.2]], 76, blue);
    if (t >= B.oLearn && t < S("four")) row([["OmniNode version 4", B.oLearn]], 76, blue);
    if (t >= B.feedAt - 0.1 && t < B.fReuse - 0.1) row([["Feed maintenance Task", B.feedAt - 0.1], ["Its results become Task Objects", B.feedAt + 1.5]], 76, rust);
    if (t >= B.fCheaper - 0.2 && t < S("live")) row([["Cheaper models", B.fCheaper - 0.2], ["Deterministic engines", B.fCheaper + 0.7], ["Tools", B.fCheaper + 1.5]], 76, blue);
  }
  const onFrame = (q, m = 70) => q[0] > m && q[0] < 1920 - m && q[1] > 60 && q[1] < 890;
  function outsidePills(t, f) {
    const q = P(G.AGENT[0], G.AGENT[1], 0.6); q[1] -= 34 + cam.u * 0.72 * KY; if (onFrame(q, 110)) pill("Any agent", q[0], q[1], { a: soft(seg(t, S("parts") + 1.0, F(10))), size: 28, w: 700, color: f ? MUTED : INK });
    if (t >= B.powered - 0.3) { const m = P(G.META[0], G.META[1], 0.7); m[1] -= 34 + cam.u * 0.78 * KY; if (onFrame(m, 110)) pill("Meta models", m[0], m[1], { a: soft(seg(t, B.powered - 0.3, F(10))), size: 28, w: 700, color: BLUE, stroke: BLUE, fill: PALE }); }
  }
  function built(t, at, p, fn) { if (!MO.build || t >= at + 0.9) { fn(); return; } const k = buildK(t, at); if (k <= 0) return; const q = P(p[0], p[1], 0); c.save(); if (MO.build === "drop") c.translate(0, (k - 1) * 340); else { c.translate(q[0], q[1]); c.scale(1, Math.max(0.02, k)); c.translate(-q[0], -q[1]); } fn(); c.restore(); }
  function drawSet3(t) {
    const pS = S("parts"), f = QUIET ? null : focusOf(t), dimv = (k) => (f && f !== k ? 0.72 : 0), g = soft(seg(t, pS, F(16))), NM = G.names, off = "#A9A79F";
    comp("platform", "ground", () => slabFloor(t, g));
    if (t < pS + 0.1) return;
    ["T", "N", "O"].forEach((k) => bay(k, f === k));
    const lane = (k, on, col) => channel(CH[k], on, col), mvOn = (key) => moves.some((m) => t >= m.t0 && t < m.t1 && key3(m) === key);
    DK = 0;
    lane("ag", true, RULE); lane("tn", mvOn("tn") || mvOn("tpre") || mvOn("thold"), BLUE); lane("na", mvOn("na"), RUST); lane("ao", mvOn("ao"), RUST); lane("on", mvOn("on"), RUST);
    if (t >= B.powered - 0.3) lane("me", true, BLUE);
    if (!FRONT) comp("name:Fabric", "name", () => floorText(NM.F[0], NM.F[1], ["Teleion Fabric"], NM.F[2], BLUE));
    comp("name:T", "name", () => floorText(NM.T[0], NM.T[1], ["Durable", "Tasks"], NM.T[2], f === "T" || !f ? BLUE : off));
    comp("name:N", "name", () => floorText(NM.N[0], NM.N[1], ["Fabric", "Intelligence"], NM.N[2], f === "N" || !f ? BLUE : off));
    comp("name:A", "name", () => floorText(NM.A[0], NM.A[1], ["Audit and", "approve"], NM.A[2], f ? off : RUST));
    comp("name:O", "name", () => floorText(NM.O[0], NM.O[1], ["Durable Task", "Objects"], NM.O[2], f === "O" || !f ? RUST : off));
    // back to front: everything sorted by depth on the one grid
    const list = [{ d: depth(G.AGENT[0], G.AGENT[1]), fn: () => comp("agent", "component", () => { DK = f ? 0.72 : 0; drawAgent(); }) }, { d: depth(G.T[0], G.T[1]), fn: () => comp("Tasks db", "component", () => built(t, B.first - 0.15, G.T, () => { DK = dimv("T"); drawT(t); })) }, ...NLIST.map((n, i) => ({ d: depth(n[0], n[1]), fn: () => comp("OmniNode " + i, "component", () => built(t, B.third - 0.15 + i * 0.12, n, () => { DK = dimv("N"); drawN(t, n, i); })) })), { d: depth(G.O[0], G.O[1]), fn: () => comp("Objects db", "component", () => built(t, B.second - 0.15, G.O, () => { DK = dimv("O"); drawO(t); })) },
      { d: depth(G.A[0], G.A[1]) - 0.3, fn: () => comp("Audit gate", "component", () => { DK = f ? 0.72 : 0; drawA(t, "back"); }) }, { d: depth(G.A[0], G.A[1]) + 0.3, fn: () => comp("Audit gate", "component", () => { DK = f ? 0.72 : 0; drawA(t, "front"); }) }];
    if (t >= B.powered - 0.3) list.push({ d: depth(G.META[0], G.META[1]), fn: () => comp("Meta models", "component", () => { DK = dimv("N"); drawMeta(); }) });
    moverList(t).forEach((m) => list.push({ d: m.d, fn: () => { DK = 0; m.fn(); } }));
    list.sort((a, b) => a.d - b.d).forEach((e) => e.fn()); DK = 0;
    if (!QUIET) { outsidePills(t, f); callouts(t); drawLong(t); }
  }
  // Auto-framing: size and center the whole set in the area the heading leaves free, for this layout and this camera.
  let FIT = null;
  function computeFit() {
    if (!HULL) HULL = hullOfParts(); const keep = cam, yaws = VW.orbit ? [-VW.orbit, 0, VW.orbit] : [VW.yaw || 0]; let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9; cam = { x: 0, y: 0, u: 1 };
    const add = (q) => { x0 = Math.min(x0, q[0]); x1 = Math.max(x1, q[0]); y0 = Math.min(y0, q[1]); y1 = Math.max(y1, q[1]); };
    for (const yw of yaws) { setYaw(yw); HULL.hp.forEach((p) => { add(P(p[0], p[1], 0)); add(P(p[0], p[1], -0.8)); }); [G.T, G.O].forEach((p) => { add(P(p[0] - G.R, p[1], G.DBH + 0.6)); add(P(p[0] + G.R, p[1], G.DBH + 0.6)); }); NLIST.forEach((n) => add(P(n[0], n[1], topFor(n) + 0.8))); add(P(G.AGENT[0] - 0.9, G.AGENT[1] - 0.9, 0)); add(P(G.AGENT[0] + 0.9, G.AGENT[1] + 0.9, 0)); add(P(G.AGENT[0] - 0.9, G.AGENT[1], 1.9)); add(P(G.META[0] - 0.9, G.META[1] - 0.9, 0)); add(P(G.META[0] + 0.9, G.META[1] + 0.9, 0)); add(P(G.META[0], G.META[1], 2)); }
    setYaw(VW.yaw || 0); cam = keep;
    const RG = TOPH ? { x0: 70, x1: 1850, y0: 150, y1: 915 } : { x0: 70, x1: 1850, y0: 56, y1: 912 }, u = Math.min((RG.x1 - RG.x0) / (x1 - x0), (RG.y1 - RG.y0) / (y1 - y0));
    FIT = { u, cx: (RG.x0 + RG.x1) / 2 - ((x0 + x1) / 2) * u, cy: (RG.y0 + RG.y1) / 2 - ((y0 + y1) / 2) * u, box: [x0, y0, x1, y1], RG };
  }
  function iso3Cam(t) {
    if (!FIT) computeFit();
    if (VW.orbit) setYaw(Math.sin(((t - S("parts")) / 106) * Math.PI * 2) * VW.orbit);
    // No crop: holds stay inside the frame. Life comes from a gentle breath of scale toward the subject and a small drift.
    const f = focusOf(t), tgt = f === "T" ? G.T : f === "O" ? G.O : f === "N" ? G.N : null, kv = MO.camK ? 0.03 * MO.camK : 0, s0 = 0.97;
    const keysOn = (x) => inOut(x); let w = 0; if (tgt) { const at = f === "T" ? B.first : f === "O" ? B.second : B.third; w = keysOn((t - at) / (MO.camT || 1)); }
    const u = FIT.u * (s0 + kv * w), dx = Math.sin(t * 0.17) * 6 * (MO.camK ? 1 : 0.5), dy = Math.sin(t * 0.21) * 3;
    const gx = (x) => FIT.cx + (x - FIT.cx) * (u / FIT.u); const cx0 = (FIT.RG.x0 + FIT.RG.x1) / 2, cy0 = (FIT.RG.y0 + FIT.RG.y1) / 2;
    cam = { x: cx0 + (FIT.cx - cx0) * (u / FIT.u) + dx, y: cy0 + (FIT.cy - cy0) * (u / FIT.u) + dy, u };
  }
  function sceneIso3(t) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); iso3Cam(t); drawSet3(t); drawPanel(t); tagAnim(); }

  // ================================================================== the main film's picture
  // A fabric of OmniNodes in one bounded section. It re-forms, showing what radically flexible means. Each formation is plain data.
  const VK = window.VOICE_KEY || "flexible";
  const VWORDS = { flexible: { p: ["A super flexible fabric of OmniNodes", "Radically flexible", "Meta models help them keep improving"], h: "They keep getting better", tr: [["Knowledge of", "new events"], ["Reuse of", "working code"], ["Handling", "long-term tasks"]] }, frustrations: { p: ["A super flexible fabric of OmniNodes", "Radically flexible", "Meta models help them keep improving"], h: "They keep getting better", tr: [["Knowledge of", "new events"], ["Reuse of", "working code"], ["Handling", "long-term tasks"]] }, shortest: { p: ["A radically flexible fabric", "Of OmniNodes", "Meta models help them keep improving"], h: "They get better", tr: [["Knowledge of", "new events"], ["Reuse of", "working code"], ["Long-term", "tasks"]] }, efficiency: { p: ["Every agent, more efficient", "A fabric of OmniNodes", "It changes shape for any kind of work"], h: "What agents get", tr: [["They learn about", "new events"], ["They stop rewriting", "working code"], ["Long-term", "tasks get done"]] }, evolving: { p: ["", "", ""], h: "", tr: [["Knowledge of", "new events"], ["Reuse of", "working code"], ["Handling", "long-term tasks"]] }, grid: { p: ["OmniNodes that optimize themselves", "Permutations and parameters", "Guided by models and logic"], h: "The goal is simple", tr: [["Better knowledge", "of new events"], ["More reuse of", "working code"], ["Long-term tasks", "that finish"]] } };
  const VT = VWORDS[VK] || VWORDS.flexible, MK = window.MARKS || {};
  const NF = 12, ROLES = ["rule", "model", "reuse", "learn"];
  const yGap = () => (VW.iso ? 3.35 : Math.max(3.2, 1.32 / KY + 0.55));
  const FORMS = {
    grid: () => { const a = []; for (let r = 0; r < 3; r++) for (let q = 0; q < 4; q++) a.push([(q - 1.5) * 3.2, (r - 1) * yGap()]); return a; },
    hive: () => { const a = []; const rows = [3, 4, 5], g = yGap() * 0.92; rows.forEach((n, r) => { for (let q = 0; q < n; q++) a.push([(q - (n - 1) / 2) * 3.0, (r - 1) * g]); }); return a; },
    ring: () => { const a = [], ry = Math.max(4.6, yGap() * 1.5); for (let i = 0; i < 10; i++) { const an = (i / 10) * Math.PI * 2; a.push([Math.cos(an) * 6.4, Math.sin(an) * ry]); } a.push([-1.6, 0], [1.6, 0]); return a; },
    clusters: () => { const a = [], g = yGap(); [-6.2, 0, 6.2].forEach((cx) => { [[-1.35, -g / 2], [1.35, -g / 2], [-1.35, g / 2], [1.35, g / 2]].forEach((o) => a.push([cx + o[0], o[1]])); }); return a; },
    wide: () => { const a = [], g = yGap() * 1.15; for (let r = 0; r < 2; r++) for (let q = 0; q < 6; q++) a.push([(q - 2.5) * 3.0, (r - 0.5) * g]); return a; },
  };
  const FORDER = { grid: ["grid", "clusters", "ring", "hive"], hive: ["hive", "ring", "clusters", "grid"], ring: ["ring", "grid", "clusters", "wide"], clusters: ["clusters", "wide", "ring", "grid"], wide: ["wide", "hive", "clusters", "ring"] };
  const FLAY = FORDER[qs.get("layout")] ? qs.get("layout") : "grid";
  const DSTACK = DIR === "stack", DCAMP = DIR === "campus", DCUT = DIR === "cutaway", DCLOSE = DIR === "closeup", DPAR = DIR === "parallax";
  const STK = { H: 2.75, gapX: 6.6, zMax: 1.5 };
  const stackLocal = (i) => { const f = i % 3, n = Math.floor(i / 3), o = [[-1.25, -1.25], [1.25, -1.25], [-1.25, 1.25], [1.25, 1.25]][n % 4]; return [(f - 1) * STK.gapX + o[0], o[1], f]; };
  let FSET = null;
  function fabricBuild() {
    const XS = VN === "high-three-quarter" ? 1.3 : 1; let forms = FORDER[FLAY].map((k) => FORMS[k]().map((q) => [q[0] * XS, q[1]]));
    if (DSTACK) forms = [0, 1, 2, 3].map(() => [...Array(NF).keys()].map((i) => stackLocal(i).slice(0, 2)));
    if (DCAMP) { const b = FORMS.clusters(); forms = [0, 1, 2, 3].map((r) => b.map((_, i) => b[(i + r * 5) % NF])); }
    const pts = []; forms.forEach((f) => f.forEach((q) => { for (let i = 0; i < 12; i++) { const a = (i * Math.PI) / 6; pts.push([q[0] + Math.cos(a) * 1.15, q[1] + Math.sin(a) * 1.15]); } }));
    let ymax = -1e9, xmin = 1e9, ymin = 1e9; pts.forEach((q) => { ymax = Math.max(ymax, q[1]); xmin = Math.min(xmin, q[0]); ymin = Math.min(ymin, q[1]); });
    const nameAt = [xmin + 0.1, ymax + 1.0]; if (VW.iso) { pts.push([nameAt[0], nameAt[1] + 0.2], [nameAt[0] + 6.6, nameAt[1] + 0.2]); }
    const hp = octaHull(pts, 0.45), xs = hp.map((q) => q[0]), ysv = hp.map((q) => q[1]), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ysv), y1 = Math.max(...ysv);
    const agent = [x0 - 1.9, (y0 + y1) / 2 * 0.2], meta = [(x0 + x1) / 2, y0 - (VW.iso ? 1.9 : Math.max(2.0, (1.1 * KZ) / KY + 0.7))];
    const tops = []; forms.forEach((f) => f.forEach((q) => tops.push([q[0], q[1], 1.0])));
    const fit = fitFor(hp, [...tops, [agent[0] - 0.8, agent[1] - 0.8, 0], [agent[0] + 0.8, agent[1] + 0.8, 0], [agent[0], agent[1], 2.6], [meta[0] - 0.8, meta[1] - 0.8, 0], [meta[0] + 0.8, meta[1] + 0.8, 0], [meta[0], meta[1], 2.8]]);
    if (DSTACK) { tops.push([-STK.gapX - STK.H, 0, 2 * STK.zMax + 1.4]); }
    FSET = { forms, hp, x0, x1, y0, y1, agent, meta, nameAt, fit: DSTACK || DCUT ? fitFor(hp, [...tops, [x0, y0, DCUT ? 2.8 : 0], [x1, y0, DCUT ? 2.8 : 0], [agent[0] - 0.8, agent[1] - 0.8, 0], [agent[0], agent[1], 2.6], [meta[0] - 0.8, meta[1] - 0.8, 0], [meta[0] + 0.8, meta[1] + 0.8, 0], [meta[0], meta[1], 2.8], DSTACK ? [-STK.gapX, 0, 2 * STK.zMax + 1.6] : [x0, y0, 0]]) : fit };
  }
  function octaHull(pts, m) { let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, a0 = 1e9, a1 = -1e9, b0 = 1e9, b1 = -1e9; for (const [x, y] of pts) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); a0 = Math.min(a0, x + y); a1 = Math.max(a1, x + y); b0 = Math.min(b0, x - y); b1 = Math.max(b1, x - y); }
    x0 -= m; x1 += m; y0 -= m; y1 += m; a0 -= m * 1.4; a1 += m * 1.4; b0 -= m * 1.4; b1 += m * 1.4; const clip = (P0, f) => { const out = []; for (let i = 0; i < P0.length; i++) { const p = P0[i], q = P0[(i + 1) % P0.length], fp = f(p), fq = f(q); if (fp >= 0) out.push(p); if (fp * fq < 0) { const k = fp / (fp - fq); out.push([p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k]); } } return out; };
    let hp = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]; hp = clip(hp, (p) => p[0] + p[1] - a0); hp = clip(hp, (p) => a1 - p[0] - p[1]); hp = clip(hp, (p) => p[0] - p[1] - b0); hp = clip(hp, (p) => b1 - p[0] + p[1]); return hp; }
  function fitFor(hp, tops) { const keep = cam, yaws = VW.orbit ? [-VW.orbit, 0, VW.orbit] : [VW.yaw || 0]; let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9; cam = { x: 0, y: 0, u: 1 }; const add = (q) => { x0 = Math.min(x0, q[0]); x1 = Math.max(x1, q[0]); y0 = Math.min(y0, q[1]); y1 = Math.max(y1, q[1]); };
    for (const yw of yaws) { setYaw(yw); hp.forEach((p) => { add(P(p[0], p[1], 0)); add(P(p[0], p[1], -0.75)); }); tops.forEach((q) => add(P(q[0], q[1], q[2]))); } setYaw(VW.yaw || 0); cam = keep;
    const RG = TOPH ? { x0: 70, x1: 1850, y0: 150, y1: 835 } : { x0: 200, x1: 1850, y0: 60, y1: 870 }, u = Math.min((RG.x1 - RG.x0) / (x1 - x0), (RG.y1 - RG.y0) / (y1 - y0));
    return { u, cx: (RG.x0 + RG.x1) / 2 - ((x0 + x1) / 2) * u, cy: (RG.y0 + RG.y1) / 2 - ((y0 + y1) / 2) * u, RG }; }
  const camFit = (F0, t, k = 0.98) => { const cx0 = (F0.RG.x0 + F0.RG.x1) / 2, cy0 = (F0.RG.y0 + F0.RG.y1) / 2; if (VW.orbit) setYaw(Math.sin(((t - S("parts")) / 41) * Math.PI * 2) * VW.orbit); cam = { x: cx0 + (F0.cx - cx0) * k + Math.sin(t * 0.17) * 5, y: cy0 + (F0.cy - cy0) * k + Math.sin(t * 0.21) * 3, u: F0.u * k }; };
  const morphTimes = () => { const a = MK.parts[1] + 0.15, e = Math.max(MK.parts[2] - 0.1, a + 0.6), g = (e - a) / 3; return [a, a + g, a + 2 * g]; };
  const MDUR = () => Math.min(MO.camT && MO.k < 0.8 ? 0.5 : MO.linear ? 1.05 : 0.85, Math.max(0.35, (MK.parts[2] - MK.parts[1]) / 3 - 0.15));
  window.__compSkipF = (t) => { if (TERR) return false; if (VK === "grid") return t < S("parts") + 1.2; if (t < S("parts") + 2.4) return true; if (DCLOSE && t < MK.parts[1] + 1.5) return true; if (DSTACK && t < MK.parts[1] + 1.6 && t > MK.parts[1] - 0.2) return true; for (const a of morphTimes()) if (t >= a - 0.05 && t < a + MDUR() + 0.45) return true; return false; };
  const stackOpen = (t) => inOut((t - MK.parts[1] - 0.1) / 1.3);
  function fabricNodes(t) {
    const at0 = S("parts"), mts = morphTimes(), dur = MDUR(), { forms } = FSET, out = [];
    for (let i = 0; i < NF; i++) {
      const stag = (i % 5) * 0.035; let idx = 0; mts.forEach((a, j) => { if (t >= a + stag) idx = j + 1; }); const prev = forms[Math.max(0, idx - 1)][i], cur = forms[idx][i], at = idx ? mts[idx - 1] + stag : at0, f = clamp((t - at) / dur);
      let k = MO.linear ? f : MO.k < 0.8 ? soft(f) : inOut(f), z = 0; const moving = idx > 0 && f < 1;
      if (moving && MO.hop) z = Math.sin(Math.PI * f) * 1.4; if (moving && MO.build === "drop") { z = Math.sin(Math.PI * f) * 2.2; }
      let x = mix(prev[0], cur[0], k), y = mix(prev[1], cur[1], k), scale = 0.62;
      if (moving && MO.build === "rise") { x = f < 0.5 ? prev[0] : cur[0]; y = f < 0.5 ? prev[1] : cur[1]; z = -Math.sin(Math.PI * f) * 0.0; }
      const a0 = at0 + 0.35 + i * 0.09, g = MO.build === "drop" ? pop((t - a0) / 0.5) : soft((t - a0) / 0.45); const rise = MO.build === "rise" && moving ? Math.abs(1 - 2 * f) : 1;
      const role = ROLES[(i + idx * (1 + (i % 3))) % 4], fillAt = MK.parts[2] + 0.3 + i * 0.13, fill = t >= fillAt - 0.01 ? clamp((t - fillAt) / 0.9) : undefined;
      let zf = 0; if (DSTACK) { const f0 = i % 3; zf = (2 - f0) * STK.zMax * stackOpen(t); }
      out.push({ x, y, z: z + zf + (1 - g) * 2.4, g, rise, n: [x, y, scale, t < mts[0] ? null : role, fill], i });
    }
    return out;
  }
  function drawFabric(t, quiet) {
    if (!FSET) fabricBuild(); const FS = FSET, pS = S("parts"); FAB = true;
    comp("platform", "ground", () => { const a = soft((t - pS) / 0.4), Z = FRONT ? 0.72 : 0.55; if (!window.__CMP) for (let i = 4; i >= 0; i--) poly(scalePoly(FS.hp, 1 + i * 0.012).map((p) => P(p[0] + 0.35, p[1] + 0.15, -Z)), warm(0.045 * a)); const tp = slabPoly(FS.hp, 0, Z, CARD, "#E6E1D4", "#D6D0C1", BLUE); c.save(); path(tp); c.clip(); c.strokeStyle = "rgba(226,220,207,.75)"; c.lineWidth = 1.2; for (let x = Math.ceil(FS.x0 / 2) * 2; x < FS.x1; x += 2) { const p0 = P(x, FS.y0), p1 = P(x, FS.y1); c.beginPath(); c.moveTo(p0[0], p0[1]); c.lineTo(p1[0], p1[1]); c.stroke(); } for (let y = Math.ceil(FS.y0 / 2) * 2; y < FS.y1; y += 2) { const p0 = P(FS.x0, y), p1 = P(FS.x1, y); c.beginPath(); c.moveTo(p0[0], p0[1]); c.lineTo(p1[0], p1[1]); c.stroke(); } c.restore(); if (TOPH) { const a1 = P((FS.x0 + FS.x1) / 2, FS.y1, -Z * 0.28); font(700, Math.round(cam.u * 0.42)); c.fillStyle = BLUE; c.textAlign = "center"; c.fillText("Teleion Fabric", a1[0], a1[1] + cam.u * 0.13); c.textAlign = "left"; } });
    if (VW.iso) comp("name:Fabric", "name", () => floorText(FS.nameAt[0], FS.nameAt[1], ["Teleion Fabric"], 86, BLUE));
    if (DCUT) comp("walls", "ground", () => { const wall = (a, b, h) => { const q = [P(a[0], a[1], 0), P(b[0], b[1], 0), P(b[0], b[1], h), P(a[0], a[1], h)]; poly(q, "#F2EEE3"); c.strokeStyle = shade(0.16); c.lineWidth = 1.5; path(q); c.stroke(); }; const hp = FS.hp; let top = 0; hp.forEach((q, i) => { const b = hp[(i + 1) % hp.length], nx = b[1] - q[1], ny = -(b[0] - q[0]); if (nx * VS + ny * VC < -0.001) wall(q, b, 2.0); }); });
    if (DCAMP) { const b0 = FORMS.clusters(); [-6.2, 0, 6.2].forEach((cx, k0) => { comp("island " + k0, "ground", () => { const g0 = yGap(), R0 = 2.65, q = [[cx - R0, -g0 / 2 - 1.5], [cx + R0, -g0 / 2 - 1.5], [cx + R0, g0 / 2 + 1.5], [cx - R0, g0 / 2 + 1.5]]; slabPoly(q, 0.02, 0.0, k0 === 1 ? "#EEF1F8" : "#F7F3E9", "#E6E1D4", "#D6D0C1", RULE); }); }); channel([[-3.5, 0], [-2.7, 0]], true, BLUE); channel([[2.7, 0], [3.5, 0]], true, BLUE); }
    if (DSTACK) [0, 1, 2].forEach((f0) => { const fx = (f0 - 1) * STK.gapX, z0 = (2 - f0) * STK.zMax * stackOpen(t); comp("floor " + f0, "ground", () => { if (z0 > 0.02 && !window.__CMP) { DK = 0.7; blob(fx, 0, 3.0, 1.75, z0); DK = 0; } const R0 = STK.H, q = [[fx - R0, -R0], [fx + R0, -R0], [fx + R0, R0], [fx - R0, R0]]; slabPoly(q, z0, 0.16, "#FBF8F1", "#E6E1D4", "#D6D0C1", RULE); }); });
    const metaOn = t >= MK.parts[2] - 0.4 || quiet || TOPH, [ax, ay] = FS.agent, [mx, my] = FS.meta;
    channel([[ax + 0.8, ay], [FS.x0 + 0.5, ay]], true, RULE); comp("agent", "component", () => { blob(ax, ay, 0.9, 0.55, 0.7); block(ax - 0.7, ay - 0.7, 0, 1.4, 1.4, 0.6, CARD); });
    const list = [];
    if (metaOn) { channel([[mx, my + 0.8], [mx, FS.y0 + 0.5]], true, BLUE); list.push({ d: depth(mx, my), fn: () => comp("Meta models", "component", () => { blob(mx, my, 0.95, 0.55, 0.8); block(mx - 0.75, my - 0.75, 0, 1.5, 1.5, 0.7, "#DDE5F2"); }) }); }
    fabricNodes(quiet ? Math.max(t, E("parts")) : t).forEach((q) => { if (DCLOSE && !quiet && t < MK.parts[1] && q.i !== 5) return; list.push({ d: depth(q.x, q.y) + q.z * 0.3, fn: () => comp("OmniNode " + q.i, "component", () => { if (q.g <= 0) return; c.save(); if (q.z) c.translate(0, -q.z * KZ * cam.u); if (q.rise < 1) { const f0 = P(q.x, q.y, 0); c.translate(f0[0], f0[1]); c.scale(1, Math.max(0.04, q.rise)); c.translate(-f0[0], -f0[1]); } DK = 0; drawN(t, q.n, q.i); c.restore(); }) }); });
    // Tasks arrive from any agent; improvements come from Meta models. Small and steady.
    const flow = (from, to, ph, per, col, z0 = 0.1) => { const f = ((t + ph) % per) / 1.1; if (f < 1) { const q = [mix(from[0], to[0], inOut(f)), mix(from[1], to[1], inOut(f)), z0 + Math.sin(f * Math.PI) * 0.3]; list.push({ d: depth(q[0], q[1]) + 0.2, fn: () => block(q[0] - 0.2, q[1] - 0.2, q[2], 0.4, 0.4, 0.18, col) }); } };
    flow([ax + 0.8, ay], [FS.x0 + 0.6, ay], 0, 2.1, BLUE); if (metaOn) flow([mx, my + 0.9], [mx, FS.y0 + 0.6], 0.7, 1.7, "#7F9CC9");
    list.sort((a, b) => a.d - b.d).forEach((e) => e.fn()); DK = 0; FAB = false;
    if (!quiet) { const qa = P(ax, ay, 0.6); qa[1] -= 34 + cam.u * 0.72 * KY; pill("Any agent", qa[0], qa[1], { size: 28, w: 700 }); if (metaOn) { const m0 = P(mx, my, 0.7); m0[1] -= 34 + cam.u * 0.78 * KY; pill("Meta models", m0[0], m0[1], { size: 28, w: 700, color: BLUE, stroke: BLUE, fill: PALE }); } }
  }
  const FOOT = "Detailed videos on each component: OmniNode, Shimming, Fabric Intelligence, in the tabs above.";
  const footnote = () => comp("footnote", "label", () => { font(400, 25); c.fillStyle = MUTED; c.textAlign = "left"; c.fillText(FOOT, V.mirror ? 760 : 70, 906); });
  function sceneFabric(t) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); if (!FSET) fabricBuild(); camFit(FSET.fit, t);
    if (DCLOSE) { const a = MK.parts[1], k = 1 - soft((t - a) / 1.2), n0 = FSET.forms[0][5] || [0, 0], u0 = FSET.fit.u * 0.98; if (k > 0) { const uz = mix(u0, u0 * 3.4, k), q0 = (() => { const sv = cam; cam = { x: 0, y: 0, u: 1 }; const r = P(n0[0], n0[1], 0.6); cam = sv; return r; })(), cF = cam; cam = { x: mix(cF.x, 1040 - q0[0] * uz, k), y: mix(cF.y, 560 - q0[1] * uz, k), u: uz }; } }
    if (DPAR) { const sv = cam, d = Math.sin(t * 0.17); cam = { x: 960 + d * 9, y: 480, u: 44 }; comp("far blocks", "ground", () => { for (let i = 0; i < 7; i++) { const x = -14 + ((i * 7) % 26), y = 8 + ((i * 11) % 6); DK = 0.55; block(x, y - 6, 0, 2.6, 2.6, 0.5 + (i % 3) * 0.5, "#EFEAE0"); DK = 0; } }); cam = sv; const pn = t < S("omninode") ? { img: "dash", x: 60, y: 520, w: 1300, h: 620 } : { img: "ngo", x: 60, y: 100, w: 1300, h: 620 }; comp("real page", "ground", () => isoSheet(pn, 1190 + d * 12, 372, 0.5, 1)); }
    drawFabric(t, false); if (DPAR) pill("Real page", 1760, 62 + 26, { size: 24, color: MUTED }); drawPanel(t); tagAnim(); footnote(); }
  // Three improvement tracks, lighting as the voice names them. Rising steps show direction only; the numbers come next, measured.
  let TSET = null;
  const TRACKS = [{ x: -6.3, name: ["Knowledge of", "new events"], word: "knowledge", col: BLUE, key: "knowledge" }, { x: 0, name: ["Reuse of", "working code"], word: "reuse", col: RUST }, { x: 6.3, name: ["Handling", "long-term tasks"], word: "handling", col: BLUE }];
  function tracksBuild() { const pts = []; const depthY = VW.iso ? 6 * 0.95 : 1.2, front = VW.iso ? 3.3 : 1.0 + 1.5 / KY; TRACKS.forEach((q) => { pts.push([q.x - 2.5, -depthY], [q.x + 2.5, -depthY], [q.x - 2.5, front], [q.x + 2.5, front]); }); const hp = octaHull(pts, 0.25), fit = fitFor(hp, TRACKS.map((q) => [q.x + (VW.iso ? 0 : 2), -depthY, 3.2])); TSET = { hp, fit }; }
  function sceneTracks(t) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); if (!TSET) tracksBuild(); camFit(TSET.fit, t); const s0 = S("omninode");
    comp("platform", "ground", () => { const Z = FRONT ? 0.72 : 0.55; if (!window.__CMP) for (let i = 4; i >= 0; i--) poly(scalePoly(TSET.hp, 1 + i * 0.012).map((p) => P(p[0] + 0.35, p[1] + 0.15, -Z)), warm(0.045)); slabPoly(TSET.hp, 0, Z, CARD, "#E6E1D4", "#D6D0C1", BLUE); });
    const ks = MK.omninode.length >= 3 ? MK.omninode.slice(-3) : [S("omninode") + 1, S("omninode") + 2, S("omninode") + 3];
    TRACKS.forEach((q, ti) => { const lit = t >= ks[ti] - 0.1, on = soft((t - ks[ti] + 0.1) / 0.5); comp("name:" + q.name[1], "name", () => { const yy = VW.iso ? 1.55 : 0.9 + 0.62 / KY; floorText(VW.iso ? q.x - 2.1 : q.x, yy, VT.tr[ti], VW.iso ? 44 : 46, lit ? q.col : "#A9A79F"); }); });
    const items = []; TRACKS.forEach((q, ti) => { const lit = t >= ks[ti] - 0.1; for (let i = 0; i < 6; i++) { const start = ks[ti] + i * 0.11, k = lit ? pop((t - start) / 0.4) : 0, y = VW.iso ? -i * 0.95 : 0, xs = VW.iso ? q.x - 1.5 : q.x - 2.25 + i * 0.75, w = VW.iso ? 3.0 : 0.75, dp = VW.iso ? 0.9 : 1.8, h = 0.6 + i * 0.46, col = lit && k > 0.05 ? q.col : "#E9E4D8"; items.push({ d: depth(xs, y) + i * 0.001, fn: () => comp("Track " + ti, "component", () => { block(xs, y - dp / 2, 0.01, w, dp, h, col === q.col ? mixHexS(q.col, i) : col); }) }); } });
    items.sort((a, b) => a.d - b.d).forEach((e) => e.fn()); drawPanel(t); tagAnim(); footnote(); }
  const mixHexS = (col, i) => rgbHex(mixHex(col, "#FFFFFF", 0.72 - i * 0.13));
  // The benchmarks, big, with their conditions. Exact words from plain-benchmarks/results/RESULTS.txt.
  const BENCH = [{ big: "0 → 26 of 30", txt: "correct answers about new GitHub projects listed in our feeds", at: () => M("four", /^ev(c2|w[b-e])/.test(VK) ? "Correct" : "correct"), col: BLUE }, { big: "16% fewer", txt: "lines of code written", at: () => M("four", /^evw[c-e]/.test(VK) ? "It" : "Lines"), col: RUST }, { big: "7 instead of 10", txt: "model calls per job after a forced crash (5 paired jobs)", at: () => M("four", /^evw[b-e]/.test(VK) ? "After" : "after"), col: BLUE }].concat(CUES.tokens ? [{ big: "9,094 → 1,872", txt: "tokens, six recorded runs of one repeated job, Nov 3 (one run used no model at all)", at: () => S("tokens") + 0.3, col: RUST }] : []);
  const SMALL = "";
  const BISO = new URLSearchParams(location.search).get("bench") !== "cards";
  function isoBox(x, y, s9, h, col) { const [r, g, b] = hex2(col), sh = (f) => `rgb(${r * f | 0},${g * f | 0},${b * f | 0})`, w = s9, d = s9 / 2, face = (pts, k) => { c.beginPath(); pts.forEach((q, n) => (n ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]))); c.closePath(); c.fillStyle = k; c.fill(); }; face([[x - w, y], [x, y + d], [x, y + d - h], [x - w, y - h]], sh(0.8)); face([[x + w, y], [x, y + d], [x, y + d - h], [x + w, y - h]], sh(0.64)); face([[x, y - d - h], [x + w, y - h], [x, y + d - h], [x - w, y - h]], sh(1)); }
  function benchGroup(i, cx, cy, t, at, col) { const TILE = "#E9E2D0", GONE = "#D4CDBB"; if (i === 0) { const S9 = 40, R = 5, C = 6, n = Math.round(26 * clamp((t - at - 0.2) / 1.6)); let k = 0; for (let a = 0; a < R; a++) for (let b = 0; b < C; b++) { const x = cx + (b - a + (R - C) / 2) * S9, y = cy + (a + b - (R + C - 2) / 2) * S9 / 2 + 24, on = k < n; k++; if (on) isoBox(x, y, S9 * 0.92, 46, col); else isoBox(x, y, S9 * 0.92, 7, TILE); } } else if (i === 1) { const k = soft((t - at - 0.4) / 1.4), Hm = 230, v = mix(675, 570, k), S9 = 92, tow = (x, h, kc) => { const N = Math.round(h / 34); isoBox(x, cy + 118, S9, 8, TILE); for (let j = 0; j < N; j++) isoBox(x, cy + 112 - j * (h / N), S9 * 0.9, (h / N) - 3, kc); }; tow(cx - 125, Hm, GONE); tow(cx + 125, (Hm * v) / 675, col); } else if (i === 3) { const S9 = 40, n = Math.min(6, 1 + Math.floor(Math.max(0, t - at - 0.2) / 0.5)); LRUNS.forEach((v, j) => { const x = cx + (j - 2.5) * S9 * 1.25, y = cy + 120 - (j - 2.5) * S9 * 0.1; isoBox(x, y, S9 * 0.56, 8, TILE); if (j < n && v > 0) isoBox(x, y - 6, S9 * 0.56, (250 * v) / 9094, col); }); } else { const S9 = 54, R = 2, C = 5, drop = soft((t - at - 0.5) / 0.9); let k = 0; for (let a = 0; a < R; a++) for (let b = 0; b < C; b++) { const x = cx + (b - a + (R - C) / 2) * S9, y = cy + (a + b - (R + C - 2) / 2) * S9 / 2 + 30, gone = k >= 7; k++; isoBox(x, y, S9 * 0.9, gone ? mix(92, 8, drop) : 92, gone && drop > 0.5 ? GONE : col); } } }
  function benchIso(t) { const FB9 = BENCH.length > 3, s0 = S("four"), W = FB9 ? 430 : 570, GAP = 20, fb9 = FB9 ? 46 : 58, ft9 = FB9 ? 27 : 31, lh9 = FB9 ? 36 : 41, ka = BENCH.map((b, i) => soft((t - (i === 0 ? s0 + 0.5 : b.at() - 0.35)) / 0.6)), nS = ka.reduce((a, q) => a + q, 0), X0 = 960 - (nS * W + Math.max(0, nS - 1) * GAP) / 2; comp("heading", "heading", () => rise("And we measure it.", 960, 104, 58, 700, s0 + 0.1, { t, w: 1400, gap: 3, center: true })); BENCH.forEach((b, i) => { const k = ka[i]; if (k <= 0) return; let xc = X0; for (let j = 0; j < i; j++) xc += ka[j] * (W + GAP); const cx = xc + W / 2, at = i === 0 ? s0 + 0.5 : b.at() - 0.35; comp("card " + i, "panel", () => { c.save(); c.globalAlpha = Math.min(1, k * 1.5); ONT.push(b.big + " " + b.txt); c.textAlign = "center"; font(700, fb9); c.fillStyle = b.col; c.fillText(b.big, cx, 205); if (FB9) { c.save(); c.translate(cx, 420); c.scale(0.74, 0.74); c.translate(-cx, -420); } benchGroup(i, cx, 420, t, at, b.col); if (FB9) c.restore(); font(600, ft9); c.fillStyle = INK; lines(b.txt, W - 30, ft9, 600).forEach((l, n) => c.fillText(l, cx, 632 + n * lh9)); c.textAlign = "left"; c.restore(); }); }); const q = soft((t - (s0 + 1.2)) / 0.6); comp("small print", "label", () => { c.save(); c.globalAlpha = q; c.textAlign = "center"; font(400, 30); c.fillStyle = INK; lines(SMALL, 1700, 30, 400).forEach((l, n) => c.fillText(l, 960, 800 + n * 40)); if (FB9 && ka[3] > 0) c.fillText("Six runs: not a controlled test; settings changed after run 1.", 960, 880); c.textAlign = "left"; c.restore(); }); }
  function sceneBench(t) { if (BISO) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); stripes(t, LINE); const s9 = S("four"), z9 = 1 + 0.05 * clamp((t - s9) / (CUES.four.seconds + (CUES.tokens ? CUES.tokens.seconds : 0) + (CUES.plain ? CUES.plain.seconds : 0))) + 0.008 * Math.sin((t - s9) * 1.1); c.save(); c.translate(960, 430); c.scale(z9, z9); c.translate(-960, -430); benchIso(t); c.restore(); return; } c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); stripes(t, LINE); const s0 = S("four"), pz = 1 + 0.05 * clamp((t - s0) / (CUES.four.seconds + (CUES.tokens ? CUES.tokens.seconds : 0) + (CUES.plain ? CUES.plain.seconds : 0))) + 0.008 * Math.sin((t - s0) * 1.1); c.save(); c.translate(960, 430); c.scale(pz, pz); c.translate(-960, -430);
    comp("heading", "heading", () => rise("And we measure it.", TERR ? 960 : 70, 118, 62, 700, s0 + 0.1, { t, w: 1400, gap: 3, center: !!TERR }));
    const FB = BENCH.length > 3, GAP = FB ? 24 : 30, Y0 = 215, H = TERR ? 470 : 430, ka = BENCH.map((b, i) => soft((t - (i === 0 ? s0 + 0.5 : b.at() - 0.35)) / 0.6)), nS = ka.reduce((a, q) => a + q, 0), Wd = Math.min(mix(mix(1100, 860, ka[1]), 575, ka[2]), FB ? mix(1e9, 412, ka[3]) : 1e9, (1740 - GAP * Math.max(0, nS - 1)) / Math.max(1, nS)), X0 = 960 - (nS * Wd + Math.max(0, nS - 1) * GAP) / 2;
    BENCH.forEach((b, i) => { const W = Wd, k = ka[i], plate = k; if (plate <= 0) return; let xc = X0; for (let j = 0; j < i; j++) xc += ka[j] * (Wd + GAP); const x = xc, y = Y0 + (1 - plate) * 18; comp("card " + i, "panel", () => { c.save(); c.beginPath(); c.rect(x - 40, 0, (W + 80) * k, 1080); c.clip(); rr(x, y, W, H, 18); c.fillStyle = "#FBF8F1"; c.fill(); c.strokeStyle = LINE; c.lineWidth = 2; c.stroke(); if (k <= 0) { c.restore(); return; } c.globalAlpha = Math.min(1, k * 2); c.shadowColor = "rgba(74,64,48,.22)"; c.shadowBlur = 26; c.shadowOffsetY = 10; rr(x, y, W, H, 18); c.fillStyle = CARD; c.fill(); c.shadowBlur = 0; c.shadowOffsetY = 0; c.strokeStyle = b.col; c.lineWidth = 3; rr(x, y, W, H, 18); c.stroke(); const fb = W < 500 ? 46 : 66, ft = W < 500 ? 31 : 44; ONT.push(b.big + " " + b.txt); font(700, fb); c.fillStyle = b.col; const ls0 = lines(b.big, W - 50, fb, 700); font(700, fb); ls0.forEach((l, n) => c.fillText(l, x + 30, y + 80 + n * (fb + 10))); const yy = y + 80 + ls0.length * (fb + 10) + 18; const ls = lines(b.txt, W - 64, ft, 400); font(400, ft); c.fillStyle = INK; ls.forEach((l, n) => c.fillText(l, x + 32, yy + n * (ft + 11))); if (TERR) { const fa = soft((t - (i === 0 ? s0 + 0.5 : b.at() - 0.35) - 0.4) / 1.3), gx = x + 32, gy = y + H - 76, gw = W - 64; if (i === 3) { const R9 = [9094, 7348, 6127, 0, 3511, 1872], bw = gw / 6; R9.forEach((v, j) => { const hh = Math.max(3, (v / 9094) * 74 * clamp(fa * 6 - j)); rr(gx + j * bw, gy + 44 - hh, bw - 8, hh, 3); c.fillStyle = b.col; c.fill(); }); } else if (i === 0) { const n0 = 30, cw = gw / n0; for (let j = 0; j < n0; j++) { rr(gx + j * cw, gy, cw - 3, 40, 3); c.fillStyle = j < Math.round(26 * fa) ? b.col : "#E6E1D4"; c.fill(); } } else if (i === 1) { rr(gx, gy, gw, 16, 4); c.fillStyle = "#E6E1D4"; c.fill(); rr(gx, gy + 24, gw * mix(1, 570 / 675, fa), 16, 4); c.fillStyle = b.col; c.fill(); } else if (i === 2) { const cw = gw / 10; for (let j = 0; j < 10; j++) { const gone = j >= 7, dy0 = gone ? fa * 30 : 0; c.save(); c.globalAlpha *= gone ? 1 - fa * 0.8 : 1; rr(gx + j * cw, gy + dy0, cw - 6, 40, 4); c.fillStyle = b.col; c.fill(); c.restore(); } } } c.restore(); }); });
    const q = soft((t - (s0 + 1.2)) / 0.6); comp("small print", "label", () => { c.save(); c.globalAlpha = q; const ls = lines(SMALL, 1780, 33, 400); font(400, 33); c.fillStyle = INK; ls.forEach((l, n) => c.fillText(l, 70, (TERR ? 740 : 710) + n * 44)); c.restore(); });
    c.restore();
  }

  // The grid voice. A block of OmniNodes sits in a very large floor grid: every cell is a combination of settings. Regions of the grid rise as they score well,
  // models and logic narrow the search, and the best result flows back into the fabric. Direction only: heights are an illustration, not measurements.
  const GRN = 33; let GSET = null;
  function gridBuild() {
    const NR = VW.iso || VN === "high-three-quarter" ? GRN : 15, cell = 1, ys = VW.iso ? 1 : Math.max(1, Math.min(1.5, 0.5 / KY)), hx = GRN / 2 * cell, hy = NR / 2 * ys, pts = [[-hx, -hy], [hx, -hy], [-hx, hy], [hx, hy]];
    // Three regions of good results, placed where they cannot stand in front of the block of nodes.
    const peaks = [{ x: 8.5, y: -3 * ys * (NR / 15), a: 1.0, r: 4.2 }, { x: -9.5, y: -3.5 * ys * (NR / 15), a: 0.62, r: 3.8 }, { x: 0.5, y: -5.5 * ys * (NR / 15), a: 0.45, r: 3.4 }];
    const best = { x: peaks[0].x, y: peaks[0].y }; const hp = octaHull(pts, 0.25), fit = fitFor(hp, [[peaks[0].x, peaks[0].y, 3.2], [0, 0, 2.2], [-hx, -hy, 1], [hx, -hy, 1.4]]);
    GSET = { NR, ys, hx, hy, peaks, best, hp, fit, cells: [] }; for (let j = 0; j < NR; j++) for (let k = 0; k < GRN; k++) { const x = k - GRN / 2 + 0.5, y = (j - NR / 2 + 0.5) * ys; let sc = 0; for (const q of peaks) sc = Math.max(sc, q.a * Math.exp(-(((x - q.x) ** 2 + ((y - q.y) / Math.max(ys, 1)) ** 2) / (q.r * q.r)))); GSET.cells.push({ x, y, sc, jit: Math.abs(Math.sin(k * 12.9898 + j * 78.233) * 43758.5453) % 1, near: Math.hypot(x, y) }); }
  }
  function drawGrid(t) { if (!GSET) gridBuild(); const Q = GSET, pS = S("parts"), a0 = MK.parts[1], a1 = MK.parts[2], E0 = E("parts"), Z = FRONT ? 0.72 : 0.55; FAB = true;
    // Floor first: the block of nodes stands in a platform first, then the grid opens around it.
    const open = soft((t - pS - 0.4) / 1.6), plateR = 3.9, narrow = soft((t - a1) / Math.max(0.8, (E0 - a1) * 0.45)), found = soft((t - a1 - (E0 - a1) * 0.5) / 0.6), wave = (t - a0 + 0.4) * 10;
    comp("platform", "ground", () => { if (!window.__CMP) for (let i = 4; i >= 0; i--) poly(scalePoly(Q.hp, 1 + i * 0.012).map((p) => P(p[0] + 0.35, p[1] + 0.15, -Z)), warm(0.045)); slabPoly(Q.hp, 0, Z, "#F4F0E5", "#E6E1D4", "#D6D0C1", BLUE); });
    comp("grid", "ground", () => { for (const q of Q.cells) { const dv = q.near; if (dv < plateR + 0.3 || dv > 2 + open * 40) continue; const seen = wave > dv * 0.9 + q.jit * 2, k0 = seen ? clamp((wave - dv * 0.9 - q.jit * 2) / 5) : 0, keep = q.sc > 0.3 ? 1 - narrow * (q.x > 0 ? 0 : 0.7) : 1 - narrow * 0.9, sc = q.sc * k0 * keep, hg = sc * 2.6 + 0.05, x0 = q.x - 0.46, y0 = q.y - 0.46 * Q.ys, d = 0.92 * Q.ys; const col = seen && sc > 0.04 ? rgbHex(mixHex("#E6ECF6", BLUE, Math.min(1, sc * 1.05))) : "#EFEBDF"; if (hg > 0.12) block(x0, y0, 0.01, 0.92, d, hg, col); else { poly(isoRect(x0, y0, 0.92, d, 0.02), seen && q.sc > 0.05 && k0 > 0 ? mixHex("#F6F3EA", "#CBD8EC", Math.min(1, q.sc + 0.2)) : "#EFEBDF"); } } });
    // The best settings: one block turns rust, rises, and its result returns to the fabric.
    if (found > 0) comp("best settings", "component", () => { const b = Q.best; block(b.x - 0.5, b.y - 0.5 * Q.ys, 2.6, 1, Q.ys, 0.2 + found * 0.8, RUST); });
    // The fabric: nine OmniNodes on their own plate at the center.
    const plate = [[-plateR, -plateR], [plateR, -plateR], [plateR, plateR], [-plateR, plateR]].map((q) => [q[0], q[1] * Math.min(Q.ys, 1.25)]);
    comp("fabric plate", "ground", () => { slabPoly(plate, 0.14, 0.14, CARD, "#E6E1D4", "#D6D0C1", BLUE); });
    const nodes = []; const yg = Math.min(Q.ys, 1.25) * 2.45; for (let j = -1; j <= 1; j++) for (let k = -1; k <= 1; k++) nodes.push([k * 2.45, j * yg]);
    nodes.sort((a, b) => depth(a[0], a[1]) - depth(b[0], b[1])).forEach((q, i) => { const fillAt = a1 + (E0 - a1) * 0.6 + i * 0.05, fill = t >= fillAt ? clamp((t - fillAt) / 0.7) : (wave > 0 ? ((t * 0.5 + i * 0.11) % 1) : undefined); comp("OmniNode " + i, "component", () => { DK = 0; c.save(); c.translate(0, -0.14 * KZ * cam.u); drawN(t, [q[0], q[1], 0.56, wave > 0 ? ROLES[(i * 3 + Math.floor(Math.max(0, t - a0) * 0.8)) % 4] : null, fill], i); c.restore(); }); });
    // The best result flows back: a line of small blocks from the peak to the fabric.
    if (found > 0.3) for (let i = 0; i < 4; i++) { const f = ((t * 0.55 + i * 0.25) % 1), b = Q.best, q = [mix(b.x, 0, f), mix(b.y, 0, f), mix(3.4, 1.4, f) + Math.sin(f * Math.PI) * 0.8]; block(q[0] - 0.17, q[1] - 0.17, q[2], 0.34, 0.34, 0.18, RUST); }
    if (VW.iso) comp("name:Fabric", "name", () => { const v = P(-plateR + 0.25, plateR * Math.min(Q.ys, 1.25) - 0.15, 0.3), k = cam.u / 100; c.save(); c.transform(COS * k, 0.5 * k, -COS * k, 0.5 * k, v[0], v[1]); font(700, 60); c.fillStyle = BLUE; c.fillText("Teleion Fabric", 0, 0); c.restore(); });
    if (TOPH) comp("name:Fabric", "name", () => { const v = P(0, plate[2][1], -0.04); font(700, Math.round(cam.u * 0.72)); c.fillStyle = BLUE; c.textAlign = "center"; c.fillText("Teleion Fabric", v[0], v[1] + cam.u * 0.92); c.textAlign = "left"; });
    FAB = false; }
  function sceneGrid(t) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); if (!GSET) gridBuild(); camFit(GSET.fit, t); drawGrid(t); const a1 = MK.parts[2], E0 = E("parts"), at = a1 + (E0 - a1) * 0.5; if (t >= at) pill("Best settings, back into the fabric", V.mirror ? 480 : 1500, TOPH ? 96 : 76, { a: soft((t - at) / 0.4), size: 30, w: 700, color: RUST, stroke: RUST, fill: SAND }); drawPanel(t); font(600, 24); c.fillStyle = RULE; c.textAlign = V.mirror ? "left" : "right"; c.fillText("Illustration", V.mirror ? 60 : 1860, 900); c.textAlign = "left"; footnote(); }

  // ================================================================== the cube fabric (owner, Nov 3)
  // Two large database queues and, between them, one platform holding a grid of cubes. Each cube is one kind of thing and keeps its kind. For each Task the cubes
  // slide, rise and swap into a shape and a color mix that suit it. Results make the second database grow. An illustration: no scores, no meters.
  const CK = { settings: ["#C8963E", "Settings"], reuse: ["#A23E1C", "Reuse"], weights: ["#7A5C9E", "Weights"], nodes: ["#24519B", "Nodes"], exec: ["#2E8B7F", "Execution tasks"] }, CKN = Object.keys(CK);
  const CN = Math.max(6, Math.min(14, parseInt(qs.get("cubes") || "8", 10))); let CB = null;
  const PACE = parseFloat(qs.get("pace") || "1");
  function cubeBuild() {
    const n = CN, slots = [], ISOV = VW.iso || VN === "high-three-quarter", ys = TOPH && !ISOV ? Math.max(1, Math.min(1.6, 0.46 / KY)) : 1;
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) { const x = i - (n - 1) / 2, y = (j - (n - 1) / 2) * ys, m = (n - 1) / 2 || 1, u = ISOV ? ((i - j) / (2 * m)) : (i - m) / m, v = ISOV ? ((i + j - 2 * m) / (2 * m)) : (j - m) / m; slots.push({ x, y, u, v, i, j }); }
    const half = n / 2 + 0.55, hy = half * ys, gap = 4.6 + (ISOV ? 0 : 0.2), far = ISOV ? (half + 2.8 + gap * 0 + 2) : half + 3.9, T = ISOV ? [-far * 0.72, far * 0.72] : [-far, 0], O = ISOV ? [far * 0.72, -far * 0.72] : [far, 0], R = 2.75, H0 = 3.2, entry = ISOV ? [-half, half * ys] : [-half, 0], exit = ISOV ? [half, -half * ys] : [half, 0];
    // kinds in fixed share; each cube keeps its kind
    const kinds = []; const share = [0.16, 0.26, 0.14, 0.2, 0.24]; let acc = 0; CKN.forEach((k, q) => { const c0 = q === CKN.length - 1 ? n * n - kinds.length : Math.round(share[q] * n * n); for (let i = 0; i < c0; i++) kinds.push(k); });
    const hsh0 = (a) => Math.abs(Math.sin(a * 91.17 + 3.3) * 43758.5453) % 1, cubes = kinds.map((k, id) => ({ id, k, r: hsh0(id) }));
    const a = MK.parts[1], b = MK.parts[2], st = S("parts"), os = S("omninode"), oe = E("omninode"), om = MK.omninode;
    const TASKS = [
      { type: "repeat", at: Math.max(st + 2.6, a - 0.4), end: 0, want: ["reuse"], sh: (s) => Math.abs(s.v) < 0.17 },
      { type: "judgment", at: a + 2.6, end: 0, want: ["weights", "nodes"], sh: (s) => (Math.abs(s.u) < 0.55 && Math.abs(s.v) < 0.55) || Math.abs(s.v) < 0.12 },
      { type: "long", at: Math.max(b - 0.2, a + 5.9), end: 0, want: ["exec", "nodes"], sh: (s) => Math.abs(s.v) < 0.1 + 0.85 * ((s.u + 1) / 2) },
      { type: "knowledge", at: Math.min(os + 1.2, om[0] - 0.3), end: 0, want: ["settings", "nodes"], sh: (s) => Math.abs(s.v) < 0.42 && s.i % 2 === 0 || Math.abs(s.v) < 0.12 },
      { type: "repeat", at: om[1] - 0.1, end: 0, want: ["reuse"], sh: (s) => Math.abs(s.v) < 0.17 },
      { type: "long", at: om[2] - 0.15, end: 0, want: ["exec", "weights"], sh: (s) => Math.abs(s.v) < 0.1 + 0.85 * ((s.u + 1) / 2) },
    ];
    TASKS.forEach((q, i) => { q.end = i + 1 < TASKS.length ? TASKS[i + 1].at - 0.05 : oe - 0.1; });
    // Arrangements: the shape's cells take the wanted kinds; the rest settle, tidier with each Task.
    const place = (task, tidy) => { const cells = slots.map((s, k) => ({ s, k })), shape = task ? cells.filter((q) => task.sh(q.s)).sort((p, q) => p.s.u - q.s.u) : [], rest = cells.filter((q) => !task || !task.sh(q.s)).sort((p, q) => (tidy > 0.5 ? (p.s.j - q.s.j) || (p.s.i - q.s.i) : hsh0(p.k + 7) - hsh0(q.k + 7))); const pool = cubes.slice().sort((p, q) => { const rp = task ? (task.want.indexOf(p.k) < 0 ? 9 : task.want.indexOf(p.k)) : 0, rq = task ? (task.want.indexOf(q.k) < 0 ? 9 : task.want.indexOf(q.k)) : 0; return rp - rq || p.r - q.r; }); const pos = new Array(cubes.length), lit = new Array(cubes.length).fill(false); let c0 = 0; shape.forEach((q) => { const cb = pool[c0++]; pos[cb.id] = q.k; lit[cb.id] = !!task && task.want.includes(cb.k); });
      const others = pool.slice(c0).sort((p, q) => (tidy > 0.5 ? CKN.indexOf(p.k) - CKN.indexOf(q.k) || p.r - q.r : p.r - q.r)); rest.forEach((q, i) => { pos[others[i].id] = q.k; }); return { pos, lit, shapeOrder: shape.map((q) => q.k) }; };
    const stages = [place(null, 0), ...TASKS.map((q, i) => place(q, i / (TASKS.length - 1))), place(null, 1)];
    const lane = (a0, b0) => [a0, b0]; const hull = (() => { const q = [[-half, -hy], [half, -hy], [half, hy], [-half, hy]]; return q; })();
    const tops = [[T[0] - R, T[1], H0 + 1], [T[0] + R, T[1], H0 + 1], [O[0] - R, O[1], H0 + 3], [O[0] + R, O[1], H0 + 3], [T[0], T[1] + R, 0], [O[0], O[1] + R, 0], [T[0] - R, T[1] + R, 0], [O[0] + R, O[1] + R, 0], [0, 0, 2.4]];
    const fit = fitFor(hull, tops); CB = { n, slots, T, O, R, H0, half, hy, ys, cubes, TASKS, stages, hull, entry, exit, fit, ISOV };
  }
  const stageAt = (t) => { let i = 0; CB.TASKS.forEach((q, k) => { if (t >= q.at) i = k + 1; }); if (t >= E("omninode") - 0.4) i = CB.TASKS.length + 1; return i; };
  function bigDB(p, H, col, chips, chipCol) { const [cx, cy] = p, R = CB.R, K3 = 3; blob(cx, cy, R + 0.4, (R + 0.4) * 0.58, 2.2); const h1 = H / K3; for (let i = 0; i < K3; i++) { cyl(cx, cy, i * h1, R, h1 - 0.06, CARD, CARD); const a = P(cx, cy, i * h1 + h1 * 0.34), rx = R * KX * cam.u, ry = R * KY * cam.u; c.beginPath(); c.ellipse(a[0], a[1], rx, ry, 0, 0.12 * Math.PI, 0.88 * Math.PI); c.strokeStyle = D(col); c.lineWidth = 4; c.stroke(); } const top = P(cx, cy, H), rim = R * 0.88; c.beginPath(); c.ellipse(top[0], top[1], rim * KX * cam.u, rim * KY * cam.u, 0, 0, Math.PI * 2); c.strokeStyle = D(LINE); c.lineWidth = 2.5; c.stroke();
    const s0 = 0.74; for (let q = 0; q < chips; q++) { const ix = q % 3, iy = Math.floor(q / 3) % 3, lv = Math.floor(q / 9); block(cx + (ix - 1) * 1.08 - s0 / 2, cy + (iy - 1) * 1.0 - s0 / 2, H + 0.02 + lv * 0.34, s0, s0, 0.3, chipCol); } }
  function drawCubes(t, quiet) {
    if (!CB) cubeBuild(); const B0 = CB, pS = S("parts"), g = soft((t - pS) / 0.5), idx = stageAt(t), cur = B0.stages[idx], prv = B0.stages[Math.max(0, idx - 1)], at = idx === 0 ? pS : idx > B0.TASKS.length ? E("omninode") - 0.4 : B0.TASKS[idx - 1].at, tasks = B0.TASKS, done = tasks.filter((q) => t >= q.end - 0.2).length, resAt = (q) => q.end - 0.25;
    const Z = FRONT ? 0.72 : 0.55;
    if (!window.__CMP) for (let i = 4; i >= 0; i--) poly(scalePoly(B0.hull, 1 + i * 0.012).map((q) => P(q[0] + 0.35, q[1] + 0.15, -Z)), warm(0.045 * g));
    comp("platform", "ground", () => { slabPoly(B0.hull, 0, Z, CARD, "#E6E1D4", "#D6D0C1", BLUE); });
    // bridges into and out of the platform: crisp channels that end at the rims
    const band = (a0, b0, on, col) => { const dx = b0[0] - a0[0], dy = b0[1] - a0[1], l = Math.hypot(dx, dy) || 1, w = 0.42, nx = -dy / l * w, ny = dx / l * w, q = [P(a0[0] + nx, a0[1] + ny, 0.02), P(b0[0] + nx, b0[1] + ny, 0.02), P(b0[0] - nx, b0[1] - ny, 0.02), P(a0[0] - nx, a0[1] - ny, 0.02)]; poly(q, on ? mixHex(col, "#FFFFFF", 0.72) : "#E9E4D8"); c.strokeStyle = on ? col : "rgba(138,132,118,.7)"; c.lineWidth = 2; [[q[0], q[1]], [q[2], q[3]]].forEach(([m, n0]) => { c.beginPath(); c.moveTo(m[0], m[1]); c.lineTo(n0[0], n0[1]); c.stroke(); }); };
    const tOut = [B0.T[0] + (B0.ISOV ? 0.707 : 1) * (B0.R - 0.1), B0.T[1] - (B0.ISOV ? 0.707 : 0) * (B0.R - 0.1)], oIn = [B0.O[0] - (B0.ISOV ? 0.707 : 1) * (B0.R - 0.1), B0.O[1] + (B0.ISOV ? 0.707 : 0) * (B0.R - 0.1)];
    band(tOut, B0.entry, idx > 0 && idx <= tasks.length, BLUE); band(B0.exit, oIn, idx > 0 && idx <= tasks.length, RUST);
    // the two queues
    const items = []; const stock = Math.max(1, 9 - tasks.filter((q) => t >= q.at).length), results = done, HO = B0.H0 * 0.72 + results * 0.34 + (results ? pop(seg(t, tasks[results - 1].end - 0.2, 0.5)) - 1 : 0) * 0.34;
    items.push({ d: depth(B0.T[0], B0.T[1]), fn: () => comp("Tasks db", "component", () => { DK = 0; bigDB(B0.T, B0.H0, BLUE, stock, "#2A3038"); }) });
    items.push({ d: depth(B0.O[0], B0.O[1]), fn: () => comp("Objects db", "component", () => { DK = 0; bigDB(B0.O, HO, RUST, Math.min(9, 2 + results), RUST); }) });
    // the cubes
    const stag = (id) => (B0.cubes[id].r * 0.32 + (B0.slots[cur.pos[id]].u + 1) * 0.12) / PACE, dur = 0.72 / PACE; const cubeZone = [];
    const tidy = clamp((t - pS) / (E("omninode") - pS));
    for (const cb of B0.cubes) { const p0 = B0.slots[prv.pos[cb.id]], p1 = B0.slots[cur.pos[cb.id]], k = idx === 0 ? 1 : inOut((t - at - stag(cb.id)) / dur), x = mix(p0.x, p1.x, k), y = mix(p0.y, p1.y, k), moved = p0 !== p1 && k > 0 && k < 1, arc = moved ? Math.sin(Math.PI * k) * (MO.hop ? 1.6 : 0.9) : 0, litN = cur.lit[cb.id], litP = prv.lit[cb.id], lk = litN === litP ? (litN ? 1 : 0) : (litN ? k : 1 - k), hBase = 0.42 + (cb.r - 0.5) * 0.25 * (1 - tidy), h = hBase + lk * (0.75 + 0.5 * ((p1.u + 1) / 2)), col = rgbHex(mixHex(CK[cb.k][0], "#EDE8DB", (1 - lk) * 0.66)); cubeZone.push({ d: depth(x, y) + arc * 0.25, fn: () => { DK = 0; const s0 = 0.86; if (g > 0.05) block(x - s0 / 2, y - (s0 / 2) * B0.ys, 0.02 + arc + (1 - g) * 2, s0, s0 * B0.ys, h, col); } }); }
    comp("fabric", "component", () => { cubeZone.sort((a0, b0) => a0.d - b0.d).forEach((e) => e.fn()); });
    // the Task itself: from the first queue, over its shape, into the second
    const mvT = []; tasks.forEach((q, i) => { if (t < q.at + 0.25 || t >= q.end - 0.2) return; const st0 = B0.stages[i + 1], order = st0.shapeOrder, path = [[B0.T[0], B0.T[1], B0.H0 + 0.1], [B0.T[0], B0.T[1], B0.H0 + 0.9], [B0.entry[0], B0.entry[1], 1.9]]; const n0 = Math.max(1, Math.floor(order.length / 5)); for (let w = 0; w < order.length; w += n0) { const s = B0.slots[order[w]]; if (Math.abs(s.v) < 0.3) path.push([s.x, s.y, 2.0]); } path.push([B0.exit[0], B0.exit[1], 1.9], [B0.O[0], B0.O[1], HO + 1.0], [B0.O[0], B0.O[1], HO + 0.1]); const tr = clamp((t - q.at - 0.25) / (q.end - 0.2 - q.at - 0.25)), z3 = along(path, inOut(tr)); mvT.push({ d: depth(z3[0], z3[1]) + 6, fn: () => block(z3[0] - 0.33, z3[1] - 0.33, z3[2], 0.66, 0.66, 0.34, q.type === "x" ? RUST : "#2A3038") }); });
    items.push({ d: 0, fn: () => {} }); [...items].sort((a0, b0) => a0.d - b0.d).forEach((e) => e.fn()); mvT.forEach((e) => e.fn());
    DK = 0;
    if (!quiet) {
      const tag = (p, nm, col) => comp("name:" + nm, "name", () => { const q = P(p[0], p[1], 0), yy = q[1] + B0.R * KY * cam.u + 42; font(700, Math.round(Math.max(38, cam.u * 0.72))); c.fillStyle = col; c.textAlign = "center"; c.fillText(nm, q[0], yy); c.textAlign = "left"; });
      tag(B0.T, "Durable Tasks", BLUE); tag(B0.O, "Durable Task Objects", RUST);
      comp("name:Teleion Fabric", "name", () => { if (TOPH) { const a1 = P(0, B0.hy, -Z * 0.3); font(700, Math.round(Math.min(60, cam.u * 0.75))); c.fillStyle = BLUE; c.textAlign = "center"; c.fillText("Teleion Fabric", a1[0], a1[1] + cam.u * 0.14); c.textAlign = "left"; } else { const v = P(-B0.half + 0.3, B0.hy - 0.08, 0.02), k = cam.u / 100; c.save(); c.transform(COS * k, 0.5 * k, -COS * k, 0.5 * k, v[0], v[1]); font(700, 58); c.fillStyle = BLUE; c.fillText("Teleion Fabric", 0, 0); c.restore(); } });
    }
  }
  function cubeLegend() { comp("legend", "label", () => { let x = V.mirror ? 900 : 70; const y = 866; font(600, 27); CKN.forEach((k) => { rr(x, y - 22, 26, 26, 5); c.fillStyle = CK[k][0]; c.fill(); font(600, 27); c.fillStyle = INK; c.fillText(CK[k][1], x + 36, y); x += 36 + c.measureText(CK[k][1]).width + 32; }); }); }
  function sceneCubes(t) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); if (!CB) cubeBuild(); camFit(CB.fit, t, 0.985); drawCubes(t, false); cubeLegend(); font(600, 24); c.fillStyle = RULE; c.textAlign = V.mirror ? "left" : "right"; c.fillText("Illustration", V.mirror ? 60 : 1860, 866); c.textAlign = "left"; footnote(); }

  // ================================================================== the terrain fabric (owner, Nov 3): a very large floor grid, edge to edge, with the two databases as two tall pillars rising out of it.
  // Five kinds of cube. Each Task leaves the first pillar and the whole terrain reorganizes into that Task's own skyline. Blocks travel both ways on lanes to both pillars. An illustration: no scores.
  const K5 = [["#E0B64E", "Settings"], ["#2E8B7F", "Deterministic code"], ["#A23E1C", /[?&]main=1/.test(location.search) ? "Code and knowledge reuse" : "Code reuse"], ["#24519B", "Models"], ["#7A5C9E", "Harness"]], K5C = K5.map((q) => hex2(q[0])).concat([hex2("#5F7A8C"), hex2("#B5657A")]);
  const TERR = VK === "evolving" || /^ev[cltouqwr]/.test(VK) || qs.get("terrain") === "1", TMOVE = qs.get("move") || "", TSWEEP = qs.get("sweep") === "1", TTALL = parseFloat(qs.get("tall") || "1"), TGRAIN = Math.max(10, Math.min(80, parseInt(qs.get("grain") || (qs.get("emb") !== "terminal" ? "37" : ({ paper: "56", s50: "50", s40: "46", b80: "37", b70: "40" })[qs.get("tv") || "paper"] || "42"), 10)));
  window.TERR_ON = TERR; const EPIC = qs.get("epic") === "1", CALM = qs.get("calm") === "1", EMB = qs.get("emb") || "", TERM = EMB === "terminal", TV = qs.get("tv") || "paper", S50 = TERM && TV === "s50", S40 = TERM && TV === "s40", SIDE = TERM && (TV === "paper" || S50 || S40), B80 = TERM && TV === "b80", B70 = TERM && TV === "b70", BOT = B80 || B70, CTR = TERM && (TV === "center" || TV === "models"), TBIG = TERM && TV === "zoom", TCX = S50 ? 1440 : S40 ? 1340 : SIDE ? 1370 : 960, TCY = B80 && MAINF ? 502 : B80 ? 430 : !TERM || SIDE ? 470 : 376, PILLX = MAINF ? +(qs.get("px") || 740) : S50 ? 400 : S40 ? 455 : SIDE ? 360 : B80 ? 716 : EPIC ? 640 : !TERM ? 716 : 640, PILLR = MAINF ? +(qs.get("pr") || 104) : S50 ? 76 : S40 ? 84 : SIDE ? 72 : B80 ? 118 : B70 ? 100 : !TERM ? 118 : 92, PH = S50 || S40 ? 300 : SIDE ? 270 : B80 ? 330 : !TERM ? 330 : 260, ZX = MAINF ? 422 : S50 ? 235 : S40 ? 270 : SIDE ? 195 : B80 ? 372 : !TERM ? 372 : 290, ZY = MAINF ? 306 : S50 || S40 ? 250 : SIDE ? 215 : B80 ? 270 : !TERM ? 270 : 198, LANEG = TERM ? 15 : VW.iso ? 21 : 13; let TR = null;
  // cam=persp: a true perspective camera on the center line. pitch 90 looks straight down. Everything mirrors left to right. Used only with these query values.
  const PR = qs.get("cam") === "persp", PIT0 = parseFloat(qs.get("pitch") || "35"), PDIST = parseFloat(qs.get("dist") || "4600"), PMOVE = qs.get("cmove") || ""; const PC = { c: 0, s: 1, D: PDIST, F: PDIST, CY: 470, Yc: 0, Zc: 0, key: "" };
  const prj = (X, Y, Z = 0) => { const zv = PC.D - (Y * PC.c + Z * PC.s), k = PC.F / Math.max(120, zv), k0 = PC.F / Math.max(120, PC.D - Y * PC.c), w = clamp((0.97 - PC.s) / 0.06), ka = k + (k0 - k) * w; return [960 + X * ka, PC.CY + (Y * PC.s - Z * PC.c) * ka, ka]; };
  function pcamAt(t) { const f = clamp((t - S("parts")) / (S("omninode") + CUES.omninode.seconds - S("parts"))), pit = PMOVE === "rise" ? mix(PIT0, 86, inOut(f)) : PIT0, a = (pit * Math.PI) / 180; PC.c = Math.cos(a); PC.s = Math.sin(a); let sc = (PIT0 < 15 ? 0.92 : 0.98) * mix(1, 0.92, pit / 90 < 0.5 ? 0 : (pit / 90 - 0.5) * 2); if (PMOVE === "push") sc *= 1 + 0.05 * Math.sin(f * Math.PI); if (PMOVE === "pull") sc *= 1.05 - 0.05 * f; PC.D = PDIST; PC.F = PDIST * sc; PC.CY = 470 + ((90 - pit) / 90) * (PIT0 < 15 ? 240 : 66); PC.Yc = PC.D * PC.c; PC.Zc = PC.D * PC.s; }
  function pQuad(a, b, c0, d0, col) { c.fillStyle = col; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.lineTo(c0[0], c0[1]); c.lineTo(d0[0], d0[1]); c.closePath(); c.fill(); }
  function pBox(X, Y, Z, w, d, h, r, g, b) { const x0 = X, x1 = X + w, y0 = Y, y1 = Y + d, z1 = Z + h, sh = (f) => `rgb(${r * f | 0},${g * f | 0},${b * f | 0})`; if (h > 1.5) { if (PC.Yc > y1) pQuad(prj(x0, y1, Z), prj(x1, y1, Z), prj(x1, y1, z1), prj(x0, y1, z1), sh(0.84)); else if (PC.Yc < y0) pQuad(prj(x0, y0, Z), prj(x1, y0, Z), prj(x1, y0, z1), prj(x0, y0, z1), sh(0.84)); if (x1 < 0) pQuad(prj(x1, y0, Z), prj(x1, y1, Z), prj(x1, y1, z1), prj(x1, y0, z1), sh(0.7)); else if (x0 > 0) pQuad(prj(x0, y0, Z), prj(x0, y1, Z), prj(x0, y1, z1), prj(x0, y0, z1), sh(0.7)); } pQuad(prj(x0, y0, z1), prj(x1, y0, z1), prj(x1, y1, z1), prj(x0, y1, z1), sh(1)); if (h > 7) { c.strokeStyle = "rgba(255,255,255,.4)"; c.lineWidth = 1; c.stroke(); } }
  const hsh = (a) => Math.abs(Math.sin(a * 127.1 + 311.7) * 43758.5453) % 1;
  const bl = (u, v, cx, cy, rx, ry) => Math.max(0, 1 - ((u - cx) / rx) ** 2 - ((v - cy) / ry) ** 2);
  const stp = (p, n) => (p > 0 ? Math.ceil(p * n) / n : 0);
  const NEED = Array.from({ length: 13 }, (_, i) => [(hsh(i + 2) - 0.5) * 1.6, 0.1 + (hsh(i + 40) - 0.5) * 1.35, 90 + hsh(i + 80) * 170, i % 4 === 3 ? 3 : 0]);
  // Each Task's fingerprint, as a function of position in the center zone (u, v run -1 to 1). Returns [height in px, kind, depth of color 0 to 1], or null.
  const SKY = {
    repeat: (u, v) => { const m = Math.abs(u); if (Math.abs(v) < 0.075 && m < 1) return [66, 2, 0.95]; if (bl(m, v, 0.46, 0.5, 0.18, 0.2) > 0) return [34, 1, 0.75]; const p = bl(u, v, 0, 0.06, 0.8, 0.82); return p > 0 ? [8 + stp(p, 2) * 22, 2, 0.3 + stp(p, 2) * 0.3] : null; },
    judgment: (u, v) => { const p = bl(u, v, 0, 0.14, 0.46, 0.6); if (p > 0) { const q = stp(p, 6); return [q ** 1.3 * 170, 3, 0.4 + q * 0.6]; } const r = bl(u, v, 0, 0.14, 0.92, 0.95); return r > 0 ? [10 + stp(r, 2) * 28, 0, 0.3 + stp(r, 2) * 0.35] : null; },
    many: (u, v) => { const m = Math.abs(u), vv = v - 0.1, r = Math.hypot(m, vv); if (r > 1) return null; const ring = Math.floor(r * 5), th = Math.atan2(vv, m + 0.001), arm = Math.round(th / 0.62), onArm = Math.abs(th - arm * 0.62) < 0.2; if (!onArm) return [8, 1, 0.3]; return [16 + (4 - Math.min(4, ring)) * 18, Math.abs(arm) % 2 ? 4 : 1, 0.55 + (4 - Math.min(4, ring)) * 0.1]; },
    crater: (u, v) => { const m = Math.abs(u), r = Math.hypot(u, v - 0.1), a = Math.atan2(v - 0.1, m), d = Math.abs(r - 0.68); if (d < 0.2) { const q = stp(1 - d / 0.2, 3), sec = Math.floor(((a + Math.PI / 2) / Math.PI) * 4) % 2; return [(24 + q * 92) * (1 - 0.5 * clamp((v + 0.1) / 0.8)), sec ? 3 : 4, 0.45 + q * 0.5]; } return r < 0.46 ? [20, 2, 0.5] : null; },
    needles: (u, v) => { const m = Math.abs(u); for (const [cx, cy, k0] of [[0, -0.52, 3], [0.62, -0.2, 0], [0.34, 0.26, 0], [0.74, 0.5, 3], [0, 0.72, 0]]) { const p = bl(m, v, cx, cy, 0.26, 0.28); if (p > 0) { const q = stp(p, 3); return [14 + q * 62, k0, 0.5 + q * 0.5]; } } const r = bl(u, v, 0, 0.1, 0.96, 0.96); return r > 0 ? [7, 0, 0.3] : null; },
    terrace: (u, v) => { const p = bl(u, v, 0, 0.1, 1, 0.86); if (p <= 0) return null; if (bl(u, v, 0, 0.02, 0.13, 0.2) > 0) return [125, 3, 1]; const q = Math.min(5, Math.floor(p * 6)) / 5; return [14 + q * 110, Math.floor(q * 5) % 2 ? 1 : 4, 0.4 + q * 0.6]; },
  };
  // emb=terminal: one stored OmniNode run, read from its public record (qa/omni_run.json); every value comes from that record, sped up. Certain lines trigger the fabric. The audit there used a separate key.
  const AGENT9 = [{"kind": "say", "text": "agent: Starting your queue run, checking for ready NGO work", "st9": "", "mv9": ""}, {"kind": "cmd", "text": "$ GET /q/tasks?state=ready&tier=ngo_priority&limit=10", "st9": "", "mv9": ""}, {"kind": "ok", "text": "200: 59 ready Tasks match", "st9": "s2", "mv9": "TF"}, {"kind": "say", "text": "agent: one looks doable, gathering its context", "st9": "", "mv9": ""}, {"kind": "cmd", "text": "$ GET /q/search?q=softstart+quiz+largeprint+printproof+checklist", "st9": "s6", "mv9": "OF"}, {"kind": "cmd", "text": "$ GET /q/object/softstart_quiz_largeprint_printproof_checklist…", "st9": "", "mv9": ""}, {"kind": "say", "text": "agent: now I'll claim this fix task", "st9": "", "mv9": ""}, {"kind": "cmd", "text": "$ GET /q/claim/prompt-check-f1?task_id=…ca22c17da", "st9": "s3", "mv9": "TF"}, {"kind": "ok", "text": "TITLE: Fix check B1 in softstart quiz largeprint printproof", "st9": "", "mv9": ""}, {"kind": "call", "text": "muse-spark-1.3: Fix drafted, submitting the corrected checklist", "st9": "s4", "mv9": ""}, {"kind": "cmd", "text": "$ POST /q/submit", "st9": "s5", "mv9": ""}, {"kind": "ok", "text": "agent: Fixed B1 cap-height error: changed 6.3mm to about 4.5mm", "st9": "s7", "mv9": ""}, {"kind": "state", "text": "object keys: b1_fixed_checklist_prompt-check-f1_20261104_v1", "st9": "", "mv9": "FO"}];
  const TLOG = MAINF && !FEED9 ? AGENT9 : [{"kind": "cmd", "text": "$ GET shim.teleionlabs.com/q/object/"}, {"kind": "cmd", "text": "    omninode_feed_run_20261103t011822z"}, {"kind": "job", "text": "node omninode.feed-maintenance, spec v4"}, {"kind": "call", "text": "omninode-feed-maker claimed omninode_feed_20261103T011822Z"}, {"kind": "call", "text": "GitHub search: 14 calls, public API, no model"}, {"kind": "ok", "text": "items seen by code: 24"}, {"kind": "out", "text": "  dropped by license rule: 7"}, {"kind": "state", "text": "reuse check: 10 answered, no model call"}, {"kind": "out", "text": "  morluto/rea  reused from version 3"}, {"kind": "out", "text": "  DietrichGebert/ponytail  reused from version 3"}, {"kind": "out", "text": "  paperclipai/paperclip  reused from version 3"}, {"kind": "call", "text": "label muse-spark-1.3: 4 items"}, {"kind": "ok", "text": "muse-spark-1.3 answered in 18.87 s, 2418 output tokens"}, {"kind": "call", "text": "label muse-wonder-1.0: 1 item"}, {"kind": "ok", "text": "muse-wonder-1.0 answered in 4.02 s, 610 output tokens"}, {"kind": "ok", "text": "rule check accepted 3, sent back 2"}, {"kind": "note", "text": "audit by omninode-feed-checker, a separate worker"}, {"kind": "call", "text": "audit muse-wonder-1.0: 2 items"}, {"kind": "ok", "text": "muse-wonder-1.0 answered in 5.92 s, 545 output tokens"}, {"kind": "call", "text": "audit muse-spark-1.3: 1 item"}, {"kind": "ok", "text": "muse-spark-1.3 answered in 12.63 s, 712 output tokens"}, {"kind": "state", "text": "published 3 Task Objects, status 200"}, {"kind": "out", "text": "  feed_repo-amelnagdy_delegate-skills"}, {"kind": "out", "text": "  feed_repo-rubocop_rubocop"}, {"kind": "out", "text": "  feed_repo-scenario-labs_skills"}, {"kind": "state", "text": "status: checked, 53.88 s in all"}];
  const TLEX = [{"t": 0.0, "kind": "cmd", "text": "$ python3 agent.py policy_read", "rec": "policy"}, {"t": 1.8, "kind": "call", "text": "GET eranosforgood.org worker policy", "rec": "policy"}, {"t": 2.2, "kind": "ok", "text": "200: goal: Requests delivered well, fast and cheap.", "rec": "policy"}, {"t": 2.2, "kind": "state", "text": "last tuned 16 minutes ago, from 15 recorded outcomes", "rec": "policy"}, {"t": 3.2, "kind": "out", "text": "check: Muse Spark 1.3 67% · Muse Wonder 1.0 33%", "rec": "policy"}, {"t": 3.2, "kind": "out", "text": "make: Muse Spark 1.3 78% · Muse Wonder 1.0 22%", "rec": "policy"}];
  const TLEV = (x, i) => { if (MAINF && !FEED9) { if (!x.st9 && !x.mv9) return null; const mv = x.mv9 ? [x.mv9[0], x.mv9[1]] : null, r9 = {}; if (x.st9) r9.st = x.st9; if (mv) { r9.mv = mv; if (mv[0] === "T") r9.ringT = 1; if (mv[1] === "O") r9.ringO = 1; } return r9; } const s0 = x.text; if (x.rec === "lease") { if (/agent A claims/.test(s0)) return { st: "s12", mv: ["T", "F"], ringT: 1 }; if (/agent B claims/.test(s0)) return { st: "s13", mv: ["T", "F"], ringT: 1 }; if (/reports once/.test(s0)) return { st: "s14", mv: ["F", "O"], ringO: 1 }; return null; } if (x.rec === "policy") return /^out make/.test(s0) ? { st: "s15" } : null; if (/^node /.test(s0)) return { st: "s0" }; if (/ claimed /.test(s0)) return { st: "s0", mv: ["T", "F"], ringT: 1 }; if (/^GitHub search/.test(s0)) return { st: "s1" }; if (/^items seen/.test(s0)) return { st: "s2" }; if (/^reuse check/.test(s0)) return { st: "s6", mv: ["O", "F"] }; if (/^label muse-spark/.test(s0)) return { st: "s3" }; if (/^muse-spark.*answered/.test(s0) && i < 17) return { st: "s4" }; if (/^label muse-wonder/.test(s0)) return { st: "s4b" }; if (/^rule check/.test(s0)) return { st: "s5" }; if (/^audit by/.test(s0)) return { st: "s7" }; if (/^audit muse-wonder/.test(s0)) return { st: "s8" }; if (/^audit muse-spark/.test(s0)) return { st: "s9" }; if (/^published/.test(s0)) return { st: "s10", mv: ["F", "O"], ringO: 1 }; if (/^status:/.test(s0)) return { st: "s11", mv: ["F", "T"], ringT: 1 }; return null; };
  const TLH = { s0: [0, 0, 0, 0], s1: [60, 0, 0, 0], s2: [110, 0, 0, 0], s6: [70, 0, 110, 0], s3: [60, 90, 90, 0], s4: [50, 200, 70, 0], s4b: [50, 150, 70, 0], s5: [100, 50, 60, 0], s7: [40, 30, 50, 90], s8: [30, 120, 40, 100], s9: [30, 180, 40, 110], s10: [24, 40, 40, 70], s11: [16, 16, 24, 16], s12: [20, 40, 0, 150], s13: [40, 60, 0, 190], s14: [24, 24, 40, 60], s15: [20, 210, 20, 30] };
  const TLW = Object.fromEntries(Object.entries(TLH).map(([k, v]) => { const m = [[v[1], 3], [v[0], 1], [v[2], 2], [v[3], 4]].filter((q) => q[0] > 0).sort((p, q) => q[0] - p[0]).map((q) => q[1]); return [k, m.length ? m : [1]]; }));
  const TLF = (key) => (u, v) => { const [hD, hM, hR, hH] = TLH[key], m = Math.abs(u); if (bl(u, v, 0, 0.02, 0.98, 0.98) <= 0) return null; const pm = bl(u, v, 0, 0.02, 0.4, 0.44); if (pm > 0 && hM) { const w = stp(pm, 5); return [12 + w * hM, 3, 0.45 + w * 0.55]; } const pd = bl(m, v, 0.68, 0.02, 0.28, 0.42); if (pd > 0 && hD) { const w = stp(pd, 3); return [8 + w * hD, 1, 0.45 + w * 0.55]; } const pr = bl(u, v, 0, 0.7, 0.46, 0.26); if (pr > 0 && hR) { const w = stp(pr, 3); return [8 + w * hR, 2, 0.45 + w * 0.55]; } const ph = bl(u, v, 0, -0.68, 0.46, 0.24); if (ph > 0 && hH) { const w = stp(ph, 3); return [8 + w * hH, 4, 0.45 + w * 0.55]; } return [5, 0, 0.14]; };
  const LREC = [{"id": "20261103T004617Z", "tok": 9094, "reuse": 0, "sent": 8, "spark": 50, "wonder": 50}, {"id": "20261103T005049Z", "tok": 7348, "reuse": 3, "sent": 8, "spark": 45, "wonder": 55}, {"id": "20261103T011822Z", "tok": 6127, "reuse": 10, "sent": 5, "spark": 85, "wonder": 15}, {"id": "20261103T052057Z", "tok": 0, "reuse": 13, "sent": 0, "spark": 71, "wonder": 29}, {"id": "20261103T091737Z", "tok": 3511, "reuse": 13, "sent": 2, "spark": 71, "wonder": 29}, {"id": "20261103T131829Z", "tok": 1872, "reuse": 13, "sent": 1, "spark": 66, "wonder": 34}], LRUNS = [9094, 7348, 6127, 0, 3511, 1872], L7 = [["Harness", 4], ["Models", 3], ["Skills", 0], ["Tools", 5], ["Hooks", 6], ["Deterministic code", 1], ["Code reuse", 2]];
  const PCELL = 44 * (37 / TGRAIN), TSIZE = qs.get("size") === "1", PATCH = Math.max(1, Math.round((TGRAIN / 37) * 1.0));
  const patch = (q, cx, cy, n) => { if (PR) return Math.max(Math.abs(q.dx - cx), Math.abs(q.dy - cy) / 0.726) / PCELL <= n + 0.5; const a0 = (q.dx - cx) / (2 * 0.866 * TR0.U), b0 = (q.dy - cy) / TR0.U; const x = a0 + b0, y = b0 - a0; return Math.max(Math.abs(x), Math.abs(y)) <= n + 0.01; };
  let TR0 = { U: 30 }, TXE = ZX + 6, TNN = false, TRIP = null; const TOPEN = qs.get("open") !== "0" && TERR && /^ev[cltouqwr]/.test(VK) && (qs.get("emb") !== "terminal" || !["paper", "s50", "s40"].includes(qs.get("tv") || "paper"));
  function terIdle(t, amp, chaos, tf) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); if (!TR) terBuild(); terCam(PR ? TR.end : t); TRIP = { amp, chaos, t }; DK = 0; TNN = false; drawTerrainSet(tf); TRIP = null; }
  const SIZED = {
    repeat: (u, v, q) => { if (patch(q, 0, 0, PATCH)) return [52, 2, 1]; if (patch(q, 0, PR ? 150 : 96, PATCH)) return [30, 3, 0.9]; return null; },
    repeat2: (u, v, q) => { if (patch(q, -ZX + 70, 0, PATCH)) return [52, 2, 1]; return null; },
    judgment: (u, v) => { const p = bl(u, v, 0, 0.14, 0.42, 0.56); if (p > 0) { const w = stp(p, 6); return [w ** 1.3 * 170, 3, 0.4 + w * 0.6]; } const r = bl(u, v, 0, 0.14, 0.62, 0.72); return r > 0 ? [10 + stp(r, 2) * 26, 0, 0.3 + stp(r, 2) * 0.35] : null; },
  };
  const dang = (a, b) => { let d = a - b; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI; return Math.abs(d); };
  const CIRC = { // one round fabric, centered between the pillars; every shape mirrors left to right.
    repeat: (u, v, q) => { const th = Math.atan2(q.dy / 0.66, Math.abs(q.dx)); return Math.abs(th) < 0.2 && q.rn > 0.2 ? [46, 2, 1] : q.rn < 0.22 ? [30, 1, 0.9] : null; },
    judgment: (u, v, q) => { if (q.rn < 0.55) { const w = stp(1 - q.rn / 0.55, 5); return [20 + w * 225, 3, 0.5 + w * 0.5]; } return q.rn < 0.8 ? [14, 0, 0.55] : null; },
    many: (u, v, q) => { const th = Math.atan2(q.dy / 0.66, Math.abs(q.dx)), k = Math.round(th / (Math.PI / 6)); if (Math.abs(th - k * Math.PI / 6) > 0.11 / Math.max(q.rn, 0.3) * 0.5 || q.rn < 0.15) return null; return [(40 + q.rn * 90) * (1 - 0.4 * clamp(v)), Math.abs(k) % 2 ? 4 : 1, 0.9]; },
    crater: (u, v, q) => (Math.abs(q.rn - 0.7) < 0.17 ? [(26 + 80 * (1 - Math.abs(q.rn - 0.7) / 0.17)) * (1 - 0.5 * clamp(v)), Math.floor(q.rn * 40) % 2 ? 3 : 4, 0.85] : q.rn < 0.4 ? [20, 2, 0.5] : null),
    needles: (u, v, q) => { const h0 = hsh(Math.floor(Math.abs(q.dx) / 70) * 11 + Math.floor(q.dy / 44) * 29); return h0 > 0.74 ? [(50 + h0 * 120) * (1 - 0.4 * clamp(v)), h0 > 0.92 ? 3 : 0, 0.9] : h0 < 0.3 ? [8, 0, 0.3] : null; },
    terrace: (u, v, q) => { const w = Math.ceil((1 - q.rn) * 6) / 6; return [(16 + w * 175) * (1 - 0.3 * clamp(v)), Math.ceil((1 - q.rn) * 6) % 2 ? 4 : 1, 0.55 + w * 0.45]; },
  };
  const roomFn = (type, want, seed) => (u, v, q) => { const a = q.rx, b = q.ry, sum = a + b + 1, dif = Math.abs(a - b), on = type === "repeat" ? a === 0 && b === 0 : type === "judgment" ? dif === 1 && sum === 0 : type === "many" ? (sum + dif) % 2 === 1 : type === "crater" ? Math.max(Math.abs(a + 0.5), Math.abs(b + 0.5)) === 1.5 : type === "needles" ? a === b : true; if (!on) return null; const r0 = hsh(sum * 7 + dif * 13 + seed), k = want[Math.abs(sum * 3 + dif * 5 + seed) % want.length]; return [(type === "repeat" ? 44 : 34 + r0 * 150) * (1 - 0.45 * clamp((v + 0.1) / 0.9)), k, 0.85 + r0 * 0.15]; };
  const layerFn = (type, want) => (u, v, q) => { if (bl(u, v, 0, 0.1, 0.98, 0.9) <= 0) return null; const k = ((Math.abs(q.x - Math.round(q.y)) + 2 * Math.abs(q.x + Math.round(q.y))) % 5 + 5) % 5, idx = want.indexOf(k), on = !!SKY[type](u, v), order = [...want, ...[0, 1, 2, 3, 4].filter((n) => !want.includes(n))], lv = order.indexOf(k), z0 = 16 + (4 - lv) * 40; return idx >= 0 && on ? [24, k, 1, z0] : [14, k, 0.22, z0 * 0.72]; };
  const TSPEC = [["repeat", "Task: label a known GitHub project", 30.4, [2, 3]], ["judgment", "Task: tenant deposit laws, what changed", 33.4, [3, 0]], ["many", "Task: sort handwritten case notes", 36.3, [1, 4]], ["crater", "Task: a plain-language renter FAQ", 39.9, [3, 4, 2]], ["needles", "Task: new GitHub projects in our feeds", 42.9, [0, 3]], [TSIZE ? "repeat2" : "repeat", "The same Task again: stored code, less model", 44.7, [2, 1]], ["terrace", "Task: long-term feed maintenance", 46.5, [4, 1, 3]]];
  const CLUST = [[-0.56, -0.44], [0.56, -0.44], [-0.56, 0.5], [0.56, 0.5], [0, 0.03]];
  function terBuild() {
    const ISO = VW.iso || VN === "high-three-quarter", U = (ISO ? 1920 / (TGRAIN * 2 * 0.866) : 1920 / TGRAIN) * (V.u / 92 || 1) / (V.u / 92 || 1), ys = ISO ? 1 : 0.42 / KY, keep = cam; cam = { x: TCX, y: TCY, u: U };
    TR0 = { U }; const cells = [], span = S("omninode") + CUES.omninode.seconds - S("parts"), TM = (v) => S("parts") + ((v - 26) / 23) * span;
    const N = Math.ceil(Math.max(2100 / (KX * U), 1300 / (KY * U))) + 2;
    if (PR) { pcamAt(TM(26)); const M0 = Math.ceil(1700 / PCELL); for (let j = -M0 * 2; j <= M0; j++) for (let i = -M0; i <= M0; i++) { const X = (i + 0.5) * PCELL - PCELL / 2, Y = j * PCELL - PCELL / 2; cells.push({ x: i, y: j, X, Y, d: Y, id: i * 7 + j * 13 + (i < 0 ? 0 : 0), dx: X + PCELL / 2, dy: (Y + PCELL / 2) * 0.726, u: (X + PCELL / 2) / ZX, v: (Y + PCELL / 2) / 372 }); } }
    else for (let j = -N; j <= N; j++) for (let i = -N; i <= N; i++) { const x = i, y = j * ys, q = P(x, y); if (q[0] < -70 || q[0] > 1990 || q[1] < -50 || q[1] > 1180) continue; cells.push({ x, y, d: depth(x, y), id: i * 7 + j * 13, dx: q[0] - TCX, dy: q[1] - TCY, u: (q[0] - TCX) / ZX, v: (q[1] - TCY) / ZY }); }
    cells.sort((a, b) => a.d - b.d); const CC = cells.length; cells.forEach((q, i) => { q.hs = hsh(q.id); q.zone = Math.abs(q.dx) <= ZX && Math.abs(q.dy) <= ZY; if (EMB === "circle") { const rn = Math.hypot(q.dx / 490, q.dy / 262); q.dy2 = q.dy; q.rn = rn; q.hide = rn > 1; q.zone = !q.hide; } if (EMB === "rooms") { const M = Math.max(4, Math.round(7 * (TGRAIN / 37))); q.chan = ((q.x % M) + M) % M === 0 || ((q.y % M) + M) % M === 0; q.rx = Math.floor(q.x / M); q.ry = Math.floor(q.y / M); } if (EMB === "wall") q.zone = false; if (PR) { const dl = Math.hypot(Math.abs(q.dx) - PILLX, q.dy / 0.726); q.pm = dl < PILLR + 34 || (Math.abs(q.dy / 0.726) < 62 && Math.abs(q.dx) > ZX && Math.abs(q.dx) < PILLX); q.hs = hsh(Math.abs(q.id)); } q.mask = (PR && q.pm) || q.chan || (!PR && Math.abs(q.dy) < LANEG * 2.2 && Math.abs(q.dx) > (EMB === "circle" ? 480 : ZX) && Math.abs(q.dx) < PILLX) || (!PR && ((Math.abs(q.dx) - PILLX) / (PILLR + 24)) ** 2 + (q.dy / ((PILLR + 24) * KY / KX)) ** 2 < 1); });
    const r0Z = []; const blobs = (seed, want, nb) => Array.from({ length: nb }, (_, i) => { const a = hsh(seed * 9 + i), b = hsh(seed * 5 + i + 33), big = 120 + hsh(seed + i * 3) * 190; return { x: (a - 0.5) * 2050, y: (b - 0.5) * 1240 + 70, r: big, k: want[i % want.length] }; });
    const mk = (fn, seed, want, tidy, nb = 8) => { const Zz = new Float32Array(CC), H = new Float32Array(CC), R = new Uint8Array(CC), G = new Uint8Array(CC), B = new Uint8Array(CC), Kk = new Int8Array(CC).fill(-1), bs = want && nb && !CALM ? blobs(seed, want, nb) : []; for (let i = 0; i < CC; i++) { const q = cells[i]; let h = 0, k = -1, l = 0; if (!q.mask) { let r0 = q.zone && fn ? fn(q.u, q.v, q) : null; if (!r0 && fn && fn.whole) r0 = fn.whole(q); if (r0) { if (r0[3] !== undefined) r0Z[0] = r0[3]; const city = TTALL > 1 && r0[0] > 26 ? 0.28 + 1.12 * hsh(Math.floor(q.x / 2) * 31 + Math.floor(q.y / (2 * ys)) * 17 + seed) : 1; h = Math.min(r0[0] * (r0[0] > 26 ? TTALL * city : 1), Math.max(8, TCY + q.dy - (EPIC && !TERM ? 240 : B80 ? (MAINF ? 190 : 160) : TERM && !SIDE ? 182 : 215))); k = r0[1]; l = r0[2];  } else for (const b of bs) { const d = Math.hypot(Math.abs(q.dx) - Math.abs(b.x), (q.dy - b.y) * 1.2) / b.r; if (d < 1) { h = d < 0.55 ? 11 : 4; k = b.k; l = d < 0.55 ? 0.2 : 0.09; break; } } } if (r0Z[0] !== undefined) { Zz[i] = r0Z[0]; r0Z.length = 0; } if (h > 26) l = Math.max(l, 0.74); H[i] = h; Kk[i] = k; let c0 = q.chan ? [251, 248, 241] : k < 0 ? (CALM ? (TERR && bl(q.u, q.v, 0, 0.05, 1.04, 1.04) > 0 ? [248, 245, 237] : [240, 236, 226]) : [236, 231, 218]) : l < 0.05 ? [240, 236, 226].map((v, n) => v * 0.95 + K5C[k][n] * 0.05) : K5C[k].map((v) => v + (255 - v) * (1 - Math.min(EPIC ? Math.max(l, Math.min(1, l * 1.25)) : l, EPIC ? 0.97 : 0.84)) * (EPIC ? 0.8 : 0.86)); R[i] = c0[0]; G[i] = c0[1]; B[i] = c0[2]; } return { H, R, G, B, K: Kk, Z: Zz }; };
    // Five clusters land first, one kind at a time.
    const CL = EMB === "grow" ? CLUST.map((q) => [q[0] * 0.42, q[1] * 0.42]) : CLUST, CLR = EMB === "grow" ? 0.45 : 1; TR0.CL = CL; const RKS = [0.36, 0.36, 0.36, 0.36, 0.36, 0.36, 0.36, 0.58, 0.8, 0.9, 0.98, 1, 2.8], rks = []; const iT = (MAINF ? [0.3, 1.5, 2.7, 3.9, 5.1] : TERM ? [0.5, 0.95, 1.4, 1.85, 2.3] : [1.0, 1.65, 2.3, 2.95, 3.6]).map((v) => TM(26 + v)), stages = [mk(null, 1, null, 0)], ats = [S("parts")], names = [null], wants = [null], types = [null], org = [0];
    for (let n = 0; n < 5; n++) { const lim = n + 1; stages.push(mk((u, v) => { for (let k = 0; k < lim; k++) { const q = CL[k], p = bl(u, v, q[0], q[1], 0.27 * CLR, 0.36 * CLR); if (p > 0) { const w = stp(p, 3); return [18 + w * 72, k, 0.45 + w * 0.5]; } } return null; }, 2, null, 0)); ats.push(iT[n]); names.push(null); wants.push(null); types.push("intro"); org.push(1); }
    if (TERM && !MAINF && /^ev[touqwr]/.test(VK)) { if (!TLOG.some((q) => q.rec)) TLOG.push(...TLEX); }
    let TL = null; if (TERM) { const w0 = TLOG.map((x, i) => (x.kind === "out" ? 0.6 : /^(label|audit) muse/.test(x.text) ? 2.2 : 1)), tot = w0.reduce((a, b) => a + b, 0), a0 = MAINF ? S("parts") + CUES.parts.seconds - 0.6 : TM(29.2), a1 = TM(48.4), WO = CUES.learn && CUES.learn.words.find((q) => q[0] === "Over"), EX0 = TLOG.findIndex((q) => q.rec); let acc = 0; const NM = EX0 < 0 ? TLOG.length : EX0, totM = w0.slice(0, NM).reduce((a, b) => a + b, 0), aEnd = FEED9 ? M("learn", "Over") : MAINF ? S("learn") - 1.3 : WO ? WO[1] : (EX0 >= 0 ? S("omninode") + CUES.omninode.seconds * 0.5 : a1), lease9 = TLOG.map((q, i) => (q.rec === "lease" ? i : -1)).filter((i) => i >= 0), pol9 = TLOG.map((q, i) => (q.rec === "policy" ? i : -1)).filter((i) => i >= 0), at = TLOG.map((x, i) => { if (i === 0) return S("parts") + 0.3; if (x.rec === "lease") { const k = lease9.indexOf(i); return mix(WO ? aEnd : aEnd, CUES.models ? S("models") - 0.1 : a1, k / lease9.length); } if (x.rec === "policy") { const k = pol9.indexOf(i); return mix(S("models") + 0.1, S("models") + CUES.models.seconds - 0.2, k / pol9.length); } const r = a0 + (acc / totM) * (aEnd - a0 - (CUES.meta ? CUES.meta.seconds : 0)); acc += w0[i]; return CUES.meta && r >= S("meta") ? r + CUES.meta.seconds : r; }); const moves = [], ringsT = [], ringsO = []; TLOG.forEach((x, i) => { const e = TLEV(x, i); if (!e) return; if (e.mv && !e.st && MAINF) e.st = names[names.length - 1]; if (e.st && e.st !== (stages.length > 6 ? names[names.length - 1] : "")) { stages.push(mk(TLF(e.st), 5, TLW[e.st], 1, 0)); ats.push(at[i] + (BOT ? 0.5 : 0)); names.push(e.st); wants.push(TLW[e.st]); types.push(e.st); org.push(0); } if (e.mv) moves.push({ at: at[i] + (BOT ? 0.5 : 0), mv: e.mv, want: TLW[e.st] }); if (e.ringT) ringsT.push(at[i]); if (e.ringO) ringsO.push(at[i]); }); TL = { at, moves, ringsT, ringsO }; }
    const cache = {}; if (!TERM) TSPEC.forEach((q, i) => { const tidy = i / (TSPEC.length - 1), key = q[0]; const fn0 = TSIZE ? (SIZED[q[0]] || SKY[q[0]]) : SKY[q[0]]; if (TSIZE && q[0] === "terrace") fn0.whole = (c0) => { const w0 = Math.floor(((Math.abs(c0.dx) + Math.abs(c0.dy) * 1.3) / 1400) * 7), j0 = hsh(Math.floor(Math.abs(c0.dx) / 90) * 7 + Math.floor(c0.dy / 50) * 13); return CALM ? null : [6 + Math.floor(j0 * 3) * 5, w0 % 2 ? 1 : 4, 0.3]; }; const fnE = EMB === "circle" ? CIRC[q[0].replace("repeat2", "repeat")] : EMB === "rooms" ? roomFn(q[0], q[3], 3 + i) : EMB === "layers" ? layerFn(q[0], q[3]) : EMB === "grow" ? ((u, v, c0) => { const rk = Math.min(1, RKS[6 + i]); return SKY[q[0]](u / rk, v / rk, c0); }) : fn0; stages.push(!EMB && cache[key] && q[0] === "repeat" ? cache[key] : (cache[key] = mk(EMB === "wall" ? null : fnE, 11 + i * 7, q[3], tidy, TSIZE ? ({ repeat: 0, repeat2: 0, judgment: 2, many: 4, crater: 3, needles: 3, terrace: 0 })[q[0]] : 8))); ats.push(TM(q[2])); names.push(q[1]); wants.push(q[3]); types.push(q[0]); org.push(0); });
    if (CUES.learn) { const wW = CUES.learn.words.find((q) => q[0] === "Watch"), L0 = wW ? wW[1] : S("learn") + 0.2, Ld = wW ? (S("four") - 0.8 - L0) / 6 : (CUES.learn.seconds - (CUES.learn.seconds > 24 ? 6 : 1)) / 6; const W8 = CUES.learn.words, W8i = (a, b) => { const n = W8.findIndex((q, i) => q[0] === a && W8[i + 1] && (!b || W8[i + 1][0] === b)); return n >= 0 ? W8[n][1] : null; }, EV9 = /^ev[wr]/.test(VK), s09 = stages.length, RT9 = !EV9 ? null : wW ? [W8i("Nine"), W8i("Seven"), W8i("Six"), W8i("Then"), (W8i("Then") + W8i("It")) / 2, W8i("It")] : (MAINF ? [0, 1, 2, 3, 4, 5].map((n) => (FEED9 ? W8i("In", "our") - 1.1 : L0) + ((W8i("One", "run") - (FEED9 ? W8i("In", "our") - 1.1 : L0)) * n) / 6) : [L0, ...[0, 1, 2, 3, 4].map((n) => W8i("fell") + ((W8i("under") + 0.5 - W8i("fell")) * n) / 4)]); LRUNS.forEach((v, i) => { const f = v / 9094, H1 = [70, 60, 74, 40, 48, 40][i], H2 = [40, 74, 40, 30, 52, 36][i], H3 = [74, 40, 62, 26, 46, 34][i], H4 = [50, 62, 36, 22, 30, 24][i], Dc = [14, 30, 46, 110, 84, 104][i], Re = 10 + LREC[i].reuse * 8, B = [[-0.6, -0.45, 4, H1], [0.6, -0.45, 0, H2], [-0.76, 0.28, 5, H3], [0.76, 0.28, 6, H4], [-0.3, 0.62, 1, Dc], [0.3, 0.62, 2, Re]]; stages.push(mk((u, w) => { if (v > 0) { const m0 = bl(u, w, 0, -0.08, 0.14 + 0.2 * f, 0.2 + 0.26 * f); if (m0 > 0) { const q = stp(m0, 4); return [12 + q * 160 * f, 3, 0.5 + q * 0.5]; } } for (const b of B) { const p0 = bl(u, w, b[0], b[1], 0.2 + b[3] / 500, 0.26 + b[3] / 500); if (p0 > 0) { const q = stp(p0, 3); return [8 + q * b[3], b[2], 0.55 + q * 0.45]; } } return null; }, 31 + i, null, 1, 0)); ats.push(RT9 ? RT9[i] : L0 + i * Ld); names.push(`Same job, run ${i + 1} of 6: ${v.toLocaleString("en-US")} tokens` + (v ? "" : ", no model")); wants.push(v ? [3, 1, 2] : [1, 2]); types.push("learn"); org.push(0); }); if (RT9) [[W8i("One", "run"), 3], [W8i("In", "run"), 0], [W8i("By", "run"), 5]].forEach((q) => { if (q[0] === null) return; const j = s09 + q[1]; stages.push(stages[j]); ats.push(q[0]); names.push(names[j]); wants.push(wants[j]); types.push("learn"); org.push(0); }); }
    const end = S("omninode") + CUES.omninode.seconds - 0.1;
    let WL = null; if (EMB === "wall") { const C0 = Math.round(26 * (TGRAIN / 37)) || 26, R0 = Math.round(C0 * 0.46), PX = 780 / C0, s0 = PX / (KX * Math.abs(VC) * U), cz = PX / (KZ * U), a0 = (() => { const a1 = (0) / (KX * U), b1 = (590 - TCY) / (KY * U); return [a1 * VC + b1 * VS, -a1 * VS + b1 * VC]; })(), cells2 = []; for (let j = 0; j < R0; j++) for (let i = 0; i < C0; i++) cells2.push({ i, j, x: a0[0] + (i - C0 / 2) * s0, y: a0[1], z: j * cz, u: ((i + 0.5) / C0) * 2 - 1, v: 1 - ((j + 0.5) / R0) * 2, dx: (i - C0 / 2) * PX }); const mkW = (fn) => { const D0 = new Float32Array(cells2.length), R1 = new Uint8Array(cells2.length), G1 = new Uint8Array(cells2.length), B1 = new Uint8Array(cells2.length); cells2.forEach((q, n) => { const r0 = fn ? fn(q.u, q.v, q) : null; const c0 = r0 ? K5C[r0[1]].map((v) => v + (255 - v) * (1 - Math.max(0.74, r0[2])) * 0.86) : [240, 235, 224]; D0[n] = r0 ? 10 + Math.min(r0[0], 300) * 0.5 : 4; R1[n] = c0[0]; G1[n] = c0[1]; B1[n] = c0[2]; }); return { D: D0, R: R1, G: G1, B: B1 }; }; const stW = [mkW(null)]; for (let n = 0; n < 5; n++) { const lim = n + 1; stW.push(mkW((u, v) => { for (let k = 0; k < lim; k++) { const q = CLUST[k], p = bl(u, v, q[0], q[1], 0.3, 0.42); if (p > 0) { const w = stp(p, 3); return [40 + w * 150, k, 0.74 + w * 0.26]; } } return null; })); } TSPEC.forEach((q) => stW.push(mkW(SKY[q[0]]))); WL = { cells2, stW, s0, cz }; }
    const lS = (() => { font(600, 34); let x = 92; return K5.map((q) => { const a = x; x += 46 + c.measureText(q[1]).width + 30; return a; }); })();
    const pxS = 1 / (KX * U * (Math.abs(VC) + Math.abs(VS))), pxZ = 1 / (KZ * U); const W = (sx, sy) => { const a = (sx - TCX) / (KX * U), b = (sy - TCY) / (KY * U); return [a * VC + b * VS, -a * VS + b * VC]; };
    TR = { U, ys, cells, CC, stages, ats, names, wants, types, org, iT, end, lS, pxS, pxZ, W, firstTask: ats[6], WL, RKS, TL, ex: null, ey: null, tmap: TM }; cam = keep;
  }
  const pOrder = (Q) => { const key = Math.round(PC.Yc / 40); if (Q.ordKey === key) return Q.ord; Q.ordKey = key; const a = Q.cells.map((q, i) => i); a.sort((p, r) => { const A = Q.cells[p], B = Q.cells[r]; return (Math.hypot(B.X, B.Y - PC.Yc) - Math.hypot(A.X, A.Y - PC.Yc)); }); Q.ord = a; return a; };
  function terCam(t) { if (PR) pcamAt(t); if (EPIC) { const f = clamp((t - S("parts")) / (TR.end - S("parts"))), kE = 1 + 0.08 * (0.5 - 0.5 * Math.cos(f * Math.PI * 4)); if (PR) { PC.F *= 1 + 0.07 * (0.5 - 0.5 * Math.cos(f * Math.PI * 4)); } else { cam = { x: TCX, y: TCY - (kE - 1) * 260, u: TR.U * kE }; return; } } let k = 1, ox = 0, oy = Math.sin(t * 0.21) * 3; if (TMOVE === "calm") { const f = clamp((t - S("parts")) / (TR.end - S("parts"))); k = 1 + 0.035 * inOut(f); } cam = { x: TCX + ox, y: TCY + oy, u: TR.U * k }; }
  const terStage = (t) => { let i = 0; for (let k = 1; k < TR.ats.length; k++) if (t >= TR.ats[k]) i = k; return i; };
  const litK = (a, b, f) => Math.round(a + (b - a) * f);
  function terDrawCells(t) {
    const Q = TR, i0 = terStage(t), S1 = Q.stages[i0], S0 = Q.stages[Math.max(0, i0 - 1)], at = Q.ats[i0], nx = i0 + 1 < Q.ats.length ? Q.ats[i0 + 1] : Q.end, spanT = nx - at, intro = Q.org[i0] === 1, snap = TMOVE === "snappy", calm = TMOVE === "calm", dur0 = (intro ? 0.42 : snap ? 0.16 : calm ? 1.2 : 0.95) / PACE, del0 = (intro ? 0 : snap ? 0.14 : calm ? 1.0 : 0.62) / PACE, sc = i0 === 0 ? 1 : Math.min(1, (spanT * 0.72) / (dur0 + del0)), dur = dur0 * sc, del = del0 * sc;
    const a0 = P(0, 0), ex = P(1, 0), ey = P(0, Q.ys), eXx = ex[0] - a0[0], eXy = ex[1] - a0[1], eYx = ey[0] - a0[0], eYy = ey[1] - a0[1], wF = 0.95, wR = 0.82, kpx = cam.u / Q.U, pS = S("parts"), openR = 200 + soft((t - pS) / 0.9) * 2400;
    const rk1 = Q.RKS[Math.min(i0, Q.RKS.length - 1)] * 446, rk0 = Q.RKS[Math.max(0, Math.min(i0 - 1, Q.RKS.length - 1))] * 446, TGR = i0 < 1 ? rk1 : mix(rk0, rk1, soft((t - at) / Math.max(0.5, Math.min(1.6, spanT * 0.7)))); TXE = EMB === "circle" ? 486 : EMB === "grow" ? clamp(Math.min(1, rk1 / 446) * ZX + 26, 60, ZX + 6) : ZX + 6;
    const skyl = [], rightSide = Math.abs(VS) > 0.01;
    const face = (ax, ay, bx, by, hh, r, g, b, f, ax2) => { c.fillStyle = `rgb(${r * f | 0},${g * f | 0},${b * f | 0})`; c.beginPath(); c.moveTo(ax, ay); c.lineTo(bx, by); c.lineTo(bx, by - hh); c.lineTo(ax, ay - hh); c.closePath(); c.fill(); };
    const draw = (q, h, r, g, b, lift = 0) => { if (PR) { const w0 = (h > 3 ? 0.72 : 0.95) * PCELL, m0 = (PCELL - w0) / 2; if (h <= 1.2 && !lift) { const a = prj(q.X + m0, q.Y + m0), b1 = prj(q.X + m0 + w0, q.Y + m0 + w0); if (b1[1] < -30 || a[1] > 1110) return; } pBox(q.X + m0, q.Y + m0, lift, w0, w0, h * 0.72, r, g, b); return; } const w = h * kpx > 7 || lift > 0 ? wR : wF, m = (1 - w) / 2, bx = a0[0] + q.x * eXx + (q.y / Q.ys) * eYx + m * (eXx + eYx), by = a0[1] + q.x * eXy + (q.y / Q.ys) * eYy + m * (eXy + eYy) - lift * kpx, hh = h * kpx, p1x = bx + w * eXx, p1y = by + w * eXy, p2x = bx + w * (eXx + eYx), p2y = by + w * (eXy + eYy), p3x = bx + w * eYx, p3y = by + w * eYy; if (hh > 1.2) { face(p3x, p3y, p2x, p2y, hh, r, g, b, 0.84); if (rightSide) face(p1x, p1y, p2x, p2y, hh, r, g, b, 0.68); } c.fillStyle = `rgb(${r},${g},${b})`; c.beginPath(); c.moveTo(bx, by - hh); c.lineTo(p1x, p1y - hh); c.lineTo(p2x, p2y - hh); c.lineTo(p3x, p3y - hh); c.closePath(); c.fill(); if (hh > 7) { c.strokeStyle = "rgba(255,255,255,.4)"; c.lineWidth = 1; c.stroke(); } };
    const st = new Array(Q.CC);
    for (let i = 0; i < Q.CC; i++) { const q = Q.cells[i]; if (NOC9 || q.hide || Math.hypot(q.dx, q.dy) > openR || (EMB === "grow" && Math.hypot(q.dx, q.dy * 1.4) > TGR)) { st[i] = null; continue; } const dly = intro ? 0 : snap ? (Math.floor(q.hs * 5) / 5) * del : (Math.abs(q.dx) / 960) * del * 1.6, f0 = i0 === 0 ? 1 : clamp((t - at - dly) / dur), f = i0 === 0 ? 1 : (snap ? inOut(f0) : pop(f0)), h0 = S0.H[i], h1 = S1.H[i]; const swap = S0.K[i] !== S1.K[i] && S0.K[i] >= 0 && S1.K[i] >= 0, f2 = swap ? clamp(f0 * 2 - 1) : f; let h = swap ? (f0 < 0.5 ? h0 * (1 - inOut(f0 * 2)) : h1 * (snap ? inOut(f2) : pop(f2))) : Math.max(0, h0 + (h1 - h0) * f), fc = swap ? (f0 < 0.5 ? 0 : 1) : clamp(f), r = litK(S0.R[i], S1.R[i], fc), g = litK(S0.G[i], S1.G[i], fc), b = litK(S0.B[i], S1.B[i], fc); if (TSWEEP && !intro && i0 > 0 && !q.mask) { const w0 = (t - at - dly) / (dur * 0.9), f1 = Math.exp(-((w0 - 0.25) ** 2) / 0.05) ; h += f1 * (q.zone ? 30 : 10); r = litK(r, 150, f1 * 0.45); g = litK(g, 175, f1 * 0.45); b = litK(b, 220, f1 * 0.45); } if (EPIC && !TRIP && !q.mask && i0 > 5 && Q.wants[i0]) { const rr9 = Math.hypot(q.dx, q.dy / 0.62) / 1050, w9 = (t - at) / 1.5, f9 = Math.exp(-((w9 - rr9) ** 2) / 0.014); if (f9 > 0.01) { h += f9 * Math.min(46, Math.max(10, 46 - Math.max(0, q.dy) * 0.08)); const lc9 = K5C[Q.wants[i0][0]]; r = litK(r, lc9[0], f9 * 0.6); g = litK(g, lc9[1], f9 * 0.6); b = litK(b, lc9[2], f9 * 0.6); } } if (EPIC && TRIP && !q.mask && TRIP.t >= S("answer") + 0.5) { const ph = ((TRIP.t - S("answer") - 0.5) % 2.2) / 1.5, id9 = Math.floor((TRIP.t - S("answer") - 0.5) / 2.2) % 5, rr9 = Math.hypot(q.dx, q.dy / 0.62) / 1050, f9 = Math.exp(-((ph - rr9) ** 2) / 0.014); if (f9 > 0.01) { h += f9 * Math.min(46, Math.max(10, 46 - Math.max(0, q.dy) * 0.08)); const lc9 = K5C[id9]; r = litK(r, lc9[0], f9 * 0.6); g = litK(g, lc9[1], f9 * 0.6); b = litK(b, lc9[2], f9 * 0.6); } } if (TRIP && q.zone && !q.mask) { const w9 = TRIP.amp * (0.5 + 0.5 * Math.sin(Math.hypot(q.dx, q.dy) / 70 - TRIP.t * 2.4 + (TRIP.chaos ? q.hs * 9 * TRIP.chaos : 0))); h = Math.min(h + w9, Math.max(6, TCY + q.dy - 215)); if (S1.K[i] < 0 && h > 3 && TRIP.t < S("parts")) { const kk = K5C[Math.floor(q.hs * 5) % 5]; r = litK(r, kk[0], 0.3); g = litK(g, kk[1], 0.3); b = litK(b, kk[2], 0.3); } } const z0 = S0.Z[i], z1 = S1.Z[i]; st[i] = [h, r, g, b, z0 + (z1 - z0) * clamp(f)]; }
    comp("floor", "ground", () => { if (SIDE) { const xc9 = S50 ? 940 : S40 ? 780 : 820; c.save(); c.beginPath(); c.rect(xc9, 0, 1920 - xc9, 1080); c.clip(); } for (let n0 = 0; n0 < Q.CC; n0++) { const i = PR ? pOrder(Q)[n0] : n0; const v = st[i]; if (!v) continue; const q = Q.cells[i]; if (CALM && TERR && !q.chan && S1.K[i] < 0 && S0.K[i] < 0) { if (q.out9 === undefined) q.out9 = bl(q.u, q.v, 0, 0.05, 1.04, 1.04) <= 0; if (q.out9) continue; } if (q.zone && v[0] > 3) { if (v[4] > 0) draw(q, 0, 236, 231, 218); continue; } draw(q, v[0], v[1], v[2], v[3]); } if (SIDE) c.restore(); });
    if (Q.WL) { const W0 = Q.WL, A = W0.stW[i0], B = W0.stW[Math.max(0, i0 - 1)]; return () => comp("skyline", "component", () => { W0.cells2.forEach((q, n) => { const dly = intro ? 0 : (Math.abs(q.dx) / 960) * del * 1.6, f0 = i0 === 0 ? 1 : clamp((t - at - dly) / dur), f = f0 === 1 ? 1 : pop(f0), fc = f0 > 0.5 ? 1 : 0, d = (B.D[n] + (A.D[n] - B.D[n]) * f) / (KY * cam.u) * (KY > 0.3 ? 1 : 1); DK = 0; block(q.x, q.y, q.z, W0.s0 * 0.97, Math.max(0.02, d), W0.cz * 0.97, rgbHex(`rgb(${litK(B.R[n], A.R[n], fc)},${litK(B.G[n], A.G[n], fc)},${litK(B.B[n], A.B[n], fc)})`)); }); }); }
    return () => comp("skyline", "component", () => { for (let n0 = 0; n0 < Q.CC; n0++) { const i = PR ? pOrder(Q)[n0] : n0; const v = st[i]; if (!v) continue; const q = Q.cells[i]; if (!(q.zone && v[0] > 3)) continue; if (q.out9 && S1.K[i] < 0 && S0.K[i] < 0) continue; draw(q, v[0], v[1], v[2], v[3], v[4]); } });
  }
  function scrBlock(sx, sy, px, hpx, col) { if (PR) { const d0 = sy - TCY, far = Math.abs(d0) > 30, rg = hex2(col.startsWith("#") ? col : "#FFFDF8"); pBox(sx - TCX - px / 2, (far ? 0 : d0 * 1.7) - px / 2, far ? -d0 * 0.8 : 0, px, px, hpx, rg[0], rg[1], rg[2]); return; } const Q = TR, s = px * Q.pxS * (Q.U / cam.u), w0 = Q.W(sx, sy); block(w0[0] - s / 2, w0[1] - s / 2, 0, s, s, hpx * Q.pxZ, col); }
  function terLanes(t, lead) { const Q = TR, i0 = terStage(t), on = MAINF ? t >= Q.firstTask && t < S("four") : Q.org[i0] === 0 && i0 >= 6 && t < Q.end, n = 4, y0 = MAINF ? TCY + 0.05 * ZY : TCY, LX = PILLX - PILLR * 1, XE = MAINF ? ZX + 22 : TXE;
    const lane = (x0, x1, y, dir, active, col) => { if (PR) { const yy = (y - TCY) * 1.7, hw = LANEG * 1.15; c.fillStyle = active ? "#FFFDF8" : "#F6F3EA"; const A = prj(TCX - TCX + x0, yy - hw), B = prj(x1, yy - hw), C0 = prj(x1, yy + hw), D0 = prj(x0, yy + hw); pQuad(A, B, C0, D0, active ? "#FFFDF8" : "#F6F3EA"); return; } const a = Q.W(TCX + x0, y - LANEG * 0.72), b = Q.W(TCX + x1, y - LANEG * 0.72), d = Q.W(TCX + x1, y + LANEG * 0.72), e = Q.W(TCX + x0, y + LANEG * 0.72); poly([P(a[0], a[1], 0.02), P(b[0], b[1], 0.02), P(d[0], d[1], 0.02), P(e[0], e[1], 0.02)], active ? "#FFFDF8" : "#F6F3EA"); if (MAINF) { c.strokeStyle = "rgba(17,22,31,.2)"; c.lineWidth = 1.5; path([P(a[0], a[1], 0.02), P(b[0], b[1], 0.02)]); c.stroke(); path([P(e[0], e[1], 0.02), P(d[0], d[1], 0.02)]); c.stroke(); } c.strokeStyle = MAINF ? "rgba(17,22,31,.26)" : "rgba(17,22,31,.11)"; c.lineWidth = 2; c.lineJoin = "round"; const pa = Math.sign(x1 - x0) * dir, hw = LANEG * 0.42, gap = 40, off = (dir > 0 ? 1 : -1) * ((t * 34) % gap); for (let v = Math.min(x0, x1) + 26 + (off + gap) % gap; v < Math.max(x0, x1) - 26; v += gap) { const m0 = TCX + v + cam.x - TCX; c.beginPath(); c.moveTo(m0 - pa * 6, y + cam.y - TCY - hw); c.lineTo(m0 + pa * 6, y + cam.y - TCY); c.lineTo(m0 - pa * 6, y + cam.y - TCY + hw); c.stroke(); } };
    if (t < Q.firstTask - 0.7) return; comp("lanes", "ground", () => { for (const sg of [-1, 1]) { const x0 = sg * LX, x1 = sg * XE; lane(x0, x1, y0 - LANEG, Math.sign(x1 - x0), on); lane(x0, x1, y0 + LANEG, -Math.sign(x1 - x0), on); } });
    const speed = 0.62 * Math.max(0.7, PACE); if (!(on || (CUES.models && t >= S("models") && t < S("models") + CUES.models.seconds)) || (TERM && !MAINF)) return; const items = [];
    for (const sg of [-1, 1]) for (const lanen of [0, 1]) { const y = lanen === 0 ? y0 - LANEG : y0 + LANEG, inw = lanen === 1 ? sg < 0 : sg > 0, inward = sg < 0 ? lanen === 0 : lanen === 1; for (let i = 0; i < n; i++) { const f = ((t * speed + i / n + (sg > 0 ? 0.17 : 0) + lanen * 0.31) % 1), d = inward ? f : 1 - f, x = sg * (LX + (XE - LX) * d), sz = Math.min(1, Math.min(f, 1 - f) * 7), col = inward ? "#6B7280" : K5[lead][0]; items.push({ x, y, sz, col }); } }
    if (EMB === "rooms") { const M = Math.max(4, Math.round(7 * (TGRAIN / 37))); for (let i = 0; i < 6; i++) { const f = (t * 0.28 + i / 6) % 1, sp = (f - 0.5) * 2 * M * 2.2 * (i % 2 ? -1 : 1), a1 = i % 3 === 0 ? [sp + 0.5, 0.5] : i % 3 === 1 ? [0.5, sp + 0.5] : [sp + 0.5, M + 0.5]; items.push({ world: a1, col: i % 2 ? K5[lead][0] : "#6B7280", y: 0, x: 0, sz: 1 }); } } comp("lane traffic", "traffic", () => { items.sort((a, b) => a.y - b.y).forEach((e) => { if (e.world) { const s1 = 26 * Q.pxS; block(e.world[0] - s1 / 2, e.world[1] - s1 / 2, 0.02, s1, s1, 12 * Q.pxZ, e.col); } else if (e.sz > 0.55) scrBlock(TCX + e.x, e.y, 33 * e.sz, 15 * e.sz, e.col); }); }); }
  const TFILL = true;
  function pillarBody(cx, yB, yT, rx, ry, rings, NR, lit, litCol, side) { const SP = (yB - yT) / NR, ell = (y, a0, a1, ccw) => c.ellipse(cx, y, rx, ry, 0, a0, a1, ccw), lvl = Math.min(NR, rings), yL = yB - lvl * SP; if (yB - yT > 3) { c.beginPath(); ell(yB, 0, Math.PI); c.lineTo(cx - rx, yT); ell(yT, Math.PI, 0, true); c.closePath(); const g = c.createLinearGradient(cx - rx, 0, cx + rx, 0), lt = "#F7F4EC", dk = "#E8E3D7"; g.addColorStop(side < 0 ? 0 : 1, lt); g.addColorStop(side < 0 ? 1 : 0, dk); c.fillStyle = g; c.fill(); c.strokeStyle = edge(); c.lineWidth = 1.4; c.stroke();
      c.beginPath(); ell(yB, 0, Math.PI); c.lineTo(cx - rx, yL); ell(yL, Math.PI, 0, true); c.closePath(); const f = c.createLinearGradient(cx - rx, 0, cx + rx, 0), l2 = "#EFE3C9", d2 = "#DFD2B6"; f.addColorStop(side < 0 ? 0 : 1, l2); f.addColorStop(side < 0 ? 1 : 0, d2); c.fillStyle = f; c.fill();
      for (let i = 0; i < NR - 1; i++) { const y = yB - (i + 1) * SP; if (i + 1 > lvl + 0.01) { c.beginPath(); ell(y, 0.06 * Math.PI, 0.94 * Math.PI); c.strokeStyle = "rgba(17,22,31,.13)"; c.lineWidth = 2; c.stroke(); continue; } const pu = lit ? lit(i) : 0; c.beginPath(); ell(y, 0.06 * Math.PI, 0.94 * Math.PI); c.strokeStyle = pu > 0.02 ? mixHex("#6E7078", litCol, pu) : "rgba(17,22,31,.6)"; c.lineWidth = 4 + pu * 7; c.stroke(); }
      if (lvl < NR - 0.01) { c.beginPath(); ell(yL, 0, Math.PI); c.strokeStyle = "#11161F"; c.lineWidth = 4; c.stroke(); } }
    c.beginPath(); ell(yT, 0, Math.PI * 2); c.fillStyle = CARD; c.fill(); c.strokeStyle = LINE; c.lineWidth = 2.5; c.stroke();
    if (ry / rx > 0.65) for (let i = 0; i < NR; i++) { const on = i + 1 <= lvl + 0.01, kr = 0.96 - (i / NR) * 0.8, pu = on && lit ? lit(i) : 0; c.beginPath(); c.ellipse(cx, yT, rx * kr, ry * kr, 0, 0, Math.PI * 2); c.strokeStyle = pu > 0.02 ? mixHex("#6E7078", litCol, pu) : on ? "rgba(17,22,31,.4)" : "rgba(17,22,31,.1)"; c.lineWidth = 2 + pu * 4; c.stroke(); } }
  function pPillar(sx, Hpx, rings, name, key, lit, litCol) { const X = sx - TCX, R = PILLR; comp(key, "component", () => { const b0 = prj(X, 0, 0), t0 = prj(X, 0, Hpx), rx = R * b0[2], ry = rx * Math.max(0.05, PC.s); pillarBody(b0[0], b0[1], t0[1], rx, ry, rings, 10, lit, litCol, X < 0 ? -1 : 1); }); const f0 = prj(X, R, 0); if (!TNN) pill(name, f0[0], f0[1] + 44, { size: 30, w: 700, color: INK, stroke: LINE, fill: CARD }); }
  function terPillar(sx, Hpx, rings, name, key, lit, litCol) { if (PR) return pPillar(sx, Hpx, rings, name, key, lit, litCol); const Q = TR, w = Q.W(sx, MAINF ? TCY + 0.05 * ZY : TCY), R = (PILLR / (KX * Q.U)), H = Hpx * Q.pxZ, SP = 31 * Q.pxZ; comp(key, "component", () => { DK = 0; blob(w[0], w[1], R + 0.3, (R + 0.3) * 0.58, 2); if (TFILL) { const b0 = P(w[0], w[1], 0), t0 = P(w[0], w[1], H); pillarBody(b0[0], b0[1], t0[1], R * KX * cam.u, R * KY * cam.u, rings, 10, lit, litCol, sx < TCX ? -1 : 1); return; } cyl(w[0], w[1], 0, R, H, CARD, CARD); const rx = R * KX * cam.u, ry = R * KY * cam.u; for (let i = 0; i < Math.ceil(rings); i++) { const z = (i + 0.7) * SP; if (z > H - SP * 0.4) break; const a = P(w[0], w[1], z), v = i + 1 > rings ? rings - i : 1, pu = lit ? lit(i) : 0; c.beginPath(); c.ellipse(a[0], a[1], rx, ry, 0, 0.06 * Math.PI, 0.94 * Math.PI); c.globalAlpha = v; c.strokeStyle = pu > 0.02 ? mixHex("#6E7078", litCol, pu) : "rgba(17,22,31,.55)"; c.lineWidth = 3 + pu * 5; c.stroke(); c.globalAlpha = 1; } const top = P(w[0], w[1], H), rim = R * 0.88; c.beginPath(); c.ellipse(top[0], top[1], rim * KX * cam.u, rim * KY * cam.u, 0, 0, Math.PI * 2); c.strokeStyle = LINE; c.lineWidth = 2.5; c.stroke(); }); if (!TNN && (S50 || S40)) { const nm = name === "Durable Tasks" ? ["Durable", "Tasks"] : ["Durable Task", "Objects"]; nm.forEach((l, n) => pill(l, sx, TCY + PILLR * KY / KX + 36 + n * 40, { size: 25, w: 700, color: INK, stroke: LINE, fill: CARD })); } else if (!TNN) pill(name, EPIC ? cam.x + (sx - TCX) * cam.u / Q.U : sx, EPIC ? cam.y + (PILLR * KY / KX + 44) * cam.u / Q.U : TCY + PILLR * KY / KX + (TERM ? 32 : 44), { size: TERM ? 23 : 32, w: 700, color: INK, stroke: LINE, fill: CARD }); }
  // Experiment (shelves=1): what the two pillars hold, shown as a tall shelf on the front of each.
  const SHELF = qs.get("shelves") === "1", SH_T = ["Feed maintenance", "Research", "Write code", "Long-term job"], SH_O = [["Code component", 0], ["Agent kit", 1], ["News", 2], ["GitHub repo", 3], ["Code component", 0]];
  function shelfIcon(x, y, ty) { c.fillStyle = INK; c.strokeStyle = INK; c.lineWidth = 2.5; if (ty === 0) { c.beginPath(); c.moveTo(x, y - 12); c.lineTo(x + 12, y - 6); c.lineTo(x + 12, y + 7); c.lineTo(x, y + 13); c.lineTo(x - 12, y + 7); c.lineTo(x - 12, y - 6); c.closePath(); c.fill(); } else if (ty === 1) { rr(x - 12, y - 6, 24, 18, 3); c.fill(); rr(x - 6, y - 12, 12, 8, 2); c.stroke(); } else if (ty === 2) { rr(x - 10, y - 12, 20, 25, 2); c.stroke(); for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(x - 5, y - 5 + i * 6); c.lineTo(x + 5, y - 5 + i * 6); c.stroke(); } } else { c.beginPath(); c.moveTo(x - 6, y - 10); c.lineTo(x - 6, y + 10); c.moveTo(x - 6, y - 2); c.quadraticCurveTo(x + 6, y - 2, x + 7, y - 9); c.stroke(); [[x - 6, y - 11], [x - 6, y + 11], [x + 7, y - 10]].forEach((q) => { c.beginPath(); c.arc(q[0], q[1], 4, 0, Math.PI * 2); c.fill(); }); } }
  function terShelf(sx, Hpx, rowsAll, isObj, hi) { const top = P(TR.W(sx, TCY)[0], TR.W(sx, TCY)[1], Hpx), base = P(TR.W(sx, TCY)[0], TR.W(sx, TCY)[1], 0), rh = 62, n = Math.min(rowsAll.length, Math.floor((base[1] - top[1] - 22) / rh)), w = isObj ? 276 : 252, x = top[0] - w / 2; for (let i = 0; i < n; i++) { const y = base[1] + 18 - (i + 1) * rh; rr(x, y, w, rh - 8, 8); c.fillStyle = CARD; c.fill(); c.strokeStyle = !isObj && i === hi ? INK : LINE; c.lineWidth = !isObj && i === hi ? 3 : 1.5; c.stroke(); const r = rowsAll[i]; font(600, 25); c.fillStyle = INK; if (isObj) { shelfIcon(x + 24, y + (rh - 8) / 2, r[1]); c.fillText(r[0], x + 46, y + 36); } else { c.textAlign = "center"; c.fillText(r, x + w / 2, y + 36); c.textAlign = "left"; } } }
  function colLegend(items, want) { comp("legend", "label", () => { const y0 = MAINF ? 650 : B80 ? 610 : 530, fx9 = MAINF && want !== null, rows = fx9 ? [items.filter((q) => q[1] < 3), items.filter((q) => q[1] >= 3)] : [items.filter((q, i) => i < Math.ceil(items.length / 2)), items.filter((q, i) => i >= Math.ceil(items.length / 2))]; rows.forEach((col, side) => { if (!col.length) return; font(600, 28); const W = 60 + Math.max(...col.map((q) => c.measureText(q[0]).width)), cx0 = CTR ? (side ? 1880 - W / 2 - 10 : 40 + W / 2 + 10) : TCX + (side ? 1 : -1) * PILLX; frost(cx0 - W / 2 - 10, y0, W + 20, col.length * 40 + 16, 10); col.forEach((q, n) => { const dim = want && !want.includes(q[1]) ? 0.6 : 1, x = cx0 - W / 2 + 4, y = y0 + 14 + n * 40; c.save(); c.globalAlpha = dim; rr(x, y, 26, 26, 5); c.fillStyle = q[1] < 5 ? K5[q[1]][0] : q[1] === 5 ? "#5F7A8C" : "#B5657A"; c.fill(); c.fillStyle = INK; font(600, 28); c.fillText(q[0], x + 36, y + 22); c.restore(); }); }); }); }
  function learnLegend(t) { if (BOT || CTR) return colLegend(L7, null); comp("legend", "label", () => { font(600, 28); let W = 40; L7.forEach((q) => { W += 40 + c.measureText(q[0]).width + 26; }); const x0 = 960 - W / 2; frost(x0, 836, W, 60, 12); let x = x0 + 22; L7.forEach((q) => { const col = q[1] < 5 ? K5[q[1]][0] : (q[1] === 5 ? "#5F7A8C" : "#B5657A"); rr(x, 850, 30, 30, 5); c.fillStyle = col; c.fill(); c.fillStyle = INK; font(600, 28); c.fillText(q[0], x + 40, 876); x += 40 + c.measureText(q[0]).width + 26; }); }); }
  function terLegend(t, want) { const Q = TR; if (CUES.learn && t >= S("learn") && t < S("four")) return learnLegend(t); if (BOT || CTR) return colLegend(K5.map((q, k) => [q[1], k]).filter((q) => t >= Q.iT[q[1]] - 0.05), want); comp("legend", "label", () => { const W = Math.max(1380, Q.lS[4] - 92 + 46 + 150 + 44), x0 = 960 - W / 2; frost(x0, 836, W, 90, 12); font(600, 30); K5.forEach((q, k) => { const on = t >= Q.iT[k] - 0.05; if (!on) return; const x = x0 + (Q.lS[k] - 92) + 22, y = 876, dim = want && !want.includes(k) ? 0.6 : 1; c.save(); c.globalAlpha = dim; rr(x, y - 28, 34, 34, 6); c.fillStyle = q[0]; c.fill(); c.fillStyle = INK; font(600, 34); c.fillText(q[1], x + 46, y); c.restore(); }); c.fillStyle = MUTED; c.textAlign = "center"; font(400, 25); font(500, 28); c.fillText(/^ev[cltouqwr]/.test(VK) ? "Detailed videos: teleionlabs.com/video-gallery" : FOOT, 960, 914); c.textAlign = "left"; }); }
  function drawTerrainSet(t) { const Q = TR, i0 = terStage(t); const sky = terDrawCells(t); const want = Q.wants[i0], lead = want ? want[0] : 2; terLanes(t, lead);
    const ends = Q.ats.slice(6).map((a, i) => (i + 7 < Q.ats.length ? Q.ats[i + 7] : Q.end)), done = ends.filter((e) => t >= e - 0.1).length, rise = soft((t - S("parts") - 0.15) / 0.8), lastE = done ? ends[done - 1] - 0.1 : 0, ringsO = 3 + (done ? done - 1 + clamp((t - lastE) / 0.4) : 0), lc = K5[lead][0], HO = PH * rise;
    const NR = 10; let tL = null, oL = null; if (i0 >= 6 || (i0 + 1 < Q.ats.length && t >= Q.ats[i0 + 1] - 0.6 && i0 === 5)) { const nk = i0 >= 6 && t < Q.ats[i0] + 0.3 ? i0 : i0 + 1 < Q.ats.length && t >= Q.ats[i0 + 1] - 0.6 ? i0 + 1 : -1; if (nk > 0) { const a = Q.ats[nk]; tL = (i) => Math.exp(-(((t - (a - 0.55 + ((NR - 1 - i) / NR) * 0.8)) / 0.13) ** 2)); } } if (done || i0 >= 6) { const eN = ends.find((e) => t >= e - 0.75 && t < e + 0.1); if (eN) oL = (i) => Math.exp(-(((t - (eN - 0.65 + (i / NR) * 0.65)) / 0.13) ** 2)); }
    const wantNext = Q.wants[Math.min(Q.wants.length - 1, Math.max(6, i0 + (tL && t < Q.ats[Math.min(Q.ats.length - 1, i0 + 1)] - 0.3 && i0 + 1 < Q.ats.length && t >= Q.ats[i0 + 1] - 0.6 ? 1 : 0)))], lcT = K5[wantNext[0]][0];
    if (TERM) { const pl = (a, up, i) => Math.exp(-(((t - (a + ((up ? i : NR - 1 - i) / NR) * 0.6)) / 0.12) ** 2)); tL = (i) => Math.max(0, ...Q.TL.ringsT.map((a) => pl(a, false, i))); oL = (i) => Math.max(0, ...Q.TL.ringsO.map((a) => pl(a, true, i))); }
    const ringsO2 = TERM ? 3 + Q.TL.ringsO.reduce((n, a) => n + clamp((t - a - 0.4) / 0.4), 0) * 2 : ringsO;
    if (EPIC && !window.__CMP) { const kk = cam.u / Q.U, g9 = c.createRadialGradient(cam.x, cam.y + 50 * kk, 40, cam.x, cam.y + 50 * kk, (ZX + 120) * kk); g9.addColorStop(0, "rgba(74,64,48,.20)"); g9.addColorStop(1, "rgba(74,64,48,0)"); c.save(); c.translate(cam.x, cam.y + 50 * kk); c.scale(1, 0.6); c.translate(-cam.x, -cam.y - 50 * kk); c.fillStyle = g9; c.fillRect(0, -800, 1920, 3000); c.restore(); }
    terPillar(TCX - PILLX, HO, NR, "Durable Tasks", "Tasks pillar", tL, TERM ? K5[3][0] : lcT); terPillar(TCX + PILLX, HO, ringsO2, "Durable Task Objects", "Objects pillar", oL, TERM ? K5[2][0] : lc); if (SHELF && rise > 0.95) { comp("Tasks shelf", "panel", () => terShelf(TCX - PILLX, PH, SH_T, false, Q.ats.slice(6).filter((a) => t >= a - 0.6).length ? (Q.ats.slice(6).filter((a) => t >= a - 0.6).length - 1) % 4 : -1)); comp("Objects shelf", "panel", () => terShelf(TCX + PILLX, PH, SH_O.slice(0, 2 + done), true, -1)); } sky(); return { i0, want, HO }; }
  function terTask(t, HO) { const Q = TR, LE = TCX - PILLX + PILLR + 34, RE = TCX + PILLX - PILLR - 34; for (let k = 6; k < Q.ats.length; k++) { const a = Q.ats[k], e = k + 1 < Q.ats.length ? Q.ats[k + 1] : Q.end, t0 = a - 0.4, t1 = e - 0.05, t2 = t1 - Math.min(0.5, (t1 - t0) * 0.2); if (t < t0 || t >= t1) continue; let q, sc = 1; if (t < a) { const f = inOut((t - t0) / (a - t0)); q = [mix(LE, TCX - TXE, f), TCY]; sc = clamp(f * 4); } else if (t < t2) { const f = inOut((t - a) / (t2 - a)); q = [mix(TCX - TXE, TCX + TXE, f), TCY - Math.sin(f * Math.PI) * 215]; } else { const f = inOut((t - t2) / (t1 - t2)); q = [mix(TCX + TXE, RE, f), TCY]; sc = clamp((1 - f) * 4); } if (sc < 0.3) continue; if (!window.__CMP && !PR) { c.beginPath(); c.ellipse(q[0], q[1] + 26, 46 * sc, 22 * sc, 0, 0, Math.PI * 2); c.fillStyle = "rgba(74,64,48,.20)"; c.fill(); } scrBlock(q[0], q[1] + 4, 76 * sc, 34 * sc, CARD); scrBlock(q[0], q[1], 60 * sc, 28 * sc, K5[Q.wants[k][0]][0]); } }
  function terMoves(t) { const Q = TR, pos = { T: TCX - PILLX + PILLR + 14, O: TCX + PILLX - PILLR - 14 }; for (const m0 of Q.TL.moves) { const f0 = (t - m0.at) / 0.95; if (f0 < 0 || f0 > 1) continue; const f = inOut(f0), [a, b] = m0.mv, inw = (from) => (from === "T" ? TCX - TXE : TCX + TXE), x0 = a === "F" ? inw(b) : pos[a], x1 = b === "F" ? inw(a) : pos[b], y = TCY + (x1 > x0 ? -LANEG : LANEG), sc = Math.min(1, Math.min(f0, 1 - f0) * 6), col = K5[m0.want[0]][0]; if (sc < 0.35) continue; scrBlock(mix(x0, x1, f), y + 3, 46 * sc, 22 * sc, CARD); scrBlock(mix(x0, x1, f), y, 34 * sc, 16 * sc, col); } }
  const lineCol = (q) => (/^\s/.test(q) ? "#4A4F58" : /^(label|audit) muse|^muse-/.test(q) ? K5[3][0] : /^reuse/.test(q) ? K5[2][0] : /^(GitHub|items seen|rule check)/.test(q) ? "#1F7A6F" : /^audit by/.test(q) ? K5[4][0] : INK);
  const TMONO = '"DejaVu Sans Mono", "Liberation Mono", monospace', TSYM = (q) => (/ claimed /.test(q) ? "↓ " : /^reuse check/.test(q) ? "↓ " : /^published/.test(q) ? "↑ " : /^status:/.test(q) ? "✓ " : ""), TOBJ = (x) => /^reuse check|reused from|^published|^\s*feed_repo/.test(x.text), TMOD = (x) => /^(label|audit) muse|^muse-/.test(x.text);
  const TCOL = (q) => (/^agent:/.test(q) ? "#CDB4F5" : /^object keys/.test(q) ? "#F2A98A" : /^200|^TITLE/.test(q) ? "#86DDCB" : /^\s/.test(q) ? "#A9AFB8" : /^(label|audit) muse|^muse-/.test(q) ? "#8DB8FF" : /^reuse/.test(q) ? "#F2A98A" : /^(GitHub|items seen|rule check)/.test(q) ? "#86DDCB" : /^audit by/.test(q) ? "#CDB4F5" : "#F2F0EA");
  const W9f = () => M("learn", "Over");
  const PIL9 = (t, q) => (FEED9 && CUES.learn && t >= S("learn") && t < W9f() && !/GitHub search|items seen|reuse check|^label muse/.test(q.text)) || !MAINF && CUES.pillars && t >= S("pillars") && t < S("learn") && !/claimed|audit by|published|sent back/.test(q.text) || (VK === "evr" && CUES.learn && t >= S("learn") && t < M("learn", "Over") && !/GitHub search|items seen|reuse check|^label muse/.test(q.text));
  const rows9 = (t, pred) => { let r = ""; TLOG.forEach((q, i) => { if (t >= TR.TL.at[i] && (!pred || pred(q)) && !PIL9(t, q)) r = q.rec || ""; }); return r; };
  function termBox(t, o) { const Q = TR, { x, y, w, h, fs, lh, title, pred, short } = o, PAD = 24, BAR = 40, chk = (window.__termChk = window.__termChk || {}); comp("terminal" + (o.id || ""), "label", () => { c.save(); if (!window.__CMP) { c.shadowColor = "rgba(40,34,24,.26)"; c.shadowBlur = BOT ? 22 : 8; c.shadowOffsetY = BOT ? 8 : 3; } rr(x, y, w, h, 12); c.fillStyle = "#0B0D10"; c.fill(); c.restore(); c.save(); rr(x, y, w, h, 12); c.clip(); c.fillStyle = "#1B1F25"; c.fillRect(x, y, w, BAR); ["#FF5F57", "#FEBC2E", "#28C840"].forEach((k, n) => { c.beginPath(); c.arc(x + PAD + n * 20, y + BAR / 2, 6, 0, Math.PI * 2); c.fillStyle = k; c.fill(); }); font(600, 21); c.fillStyle = "#D8D6CF"; c.textAlign = "center"; const last9 = rows9(t, pred), ttl = last9 === "policy" ? "Real policy record · Nov 2" : title; c.fillText(ttl, x + w / 2, y + 27); c.textAlign = "left"; c.font = `400 ${fs}px ${TMONO}`; const rows = []; TLOG.forEach((q, i) => { if (t < Q.TL.at[i] || (pred && !pred(q)) || PIL9(t, q)) return; let tx = MAINF && !FEED9 ? q.text : q.text.replace(/^\$ GET .*/, "$ GET stored run record").replace(/^\s+omninode_feed_run.*/, "    " + q.text.trim()); if (short) tx = tx.replace(" answered in ", ": ").replace(" output tokens", " tokens").replace(/omninode-feed-maker claimed .*/, "omninode-feed-maker claimed the Task").replace(", public API, no model", ", no model").replace(/audit by .*/, "audit: a separate worker").replace("  reused from version", " reused, v").replace("200: goal: Requests delivered well, fast and cheap.", "goal: delivered well, fast and cheap").replace(/last tuned .*from (\d+) recorded outcomes/, "tuned from $1 recorded outcomes").replace(" · Muse Wonder 1.0", ", Wonder 1.0").replace("Muse Spark 1.3", "Spark 1.3"); const full = TSYM(q.text) + tx; rows.push({ s: o.noType ? full : full.slice(0, Math.max(1, Math.floor((t - Q.TL.at[i]) * 80))), full, i, base: q.text }); }); const maxL = Math.floor((h - BAR - 2 * 14) / lh), vis = rows.slice(-maxL); let over = 0; vis.forEach((q, n) => { const yy = y + BAR + 14 + n * lh + lh * 0.74; if (n === vis.length - 1) { c.fillStyle = "rgba(255,255,255,.09)"; c.fillRect(x + 12, y + BAR + 14 + n * lh, w - 24, lh); } c.font = `${q.base[0] === "$" ? 700 : 400} ${fs}px ${TMONO}`; if (c.measureText(q.full).width > w - 2 * PAD) over++; c.fillStyle = TCOL(q.base); c.fillText(q.s, x + PAD, yy); }); c.restore(); chk[o.id || "main"] = { x, y, w, h, over }; }); }
  function learnTerm(t) { const Q = TR, i0 = Q.names.findIndex((n) => /run 1 of 6/.test(n)), rows = LREC.map((r, i) => [Q.ats[i0 + i], MAINF ? `run ${i + 1}: ${r.tok.toLocaleString("en-US").padStart(5)} tokens · reused ${String(r.reuse).padStart(2)} · sent to a model ${r.sent}` : BOT ? `run ${i + 1}: ${r.tok.toLocaleString("en-US").padStart(5)} tokens · reused ${String(r.reuse).padStart(2)} · model ${r.sent}` + (r.sent ? ` · mix ${r.spark}/${r.wonder}` : ", no model") : SIDE ? `run ${i + 1}: ${r.tok.toLocaleString("en-US").padStart(5)} tokens, reused ${String(r.reuse).padStart(2)}, model ${r.sent}` : `run ${i + 1}: ${r.tok.toLocaleString("en-US").padStart(5)} tokens · reused ${String(r.reuse).padStart(2)} · sent to a model ${r.sent}` + (r.sent ? ` · model mix ${r.spark}/${r.wonder}` : ", no model call")]).filter((q) => t >= q[0]); const N9 = MAINF ? 3 : B80 ? 4 : B70 || SIDE ? 6 : 5, cur9 = (Q.names[terStage(t)] || "").match(/run (\d)/), vis9 = rows.length <= N9 ? rows : MAINF ? (() => { const L = rows.length - 1, cu = cur9 ? +cur9[1] - 1 : L, ids = [0, Math.min(cu, L), L]; if (new Set(ids).size < 3) ids[1] = Math.max(1, L - 1); return [...new Set(ids)].sort((a, b) => a - b).map((i) => rows[i]); })() : [rows[0]].concat(rows.slice(1 - N9)); const LR = S50 ? [40, 40, 880, 780, 28, 38] : S40 ? [40, 40, 720, 780, 26, 36] : B80 && MAINF ? [336, 852, 1248, 200, 30, 44] : B80 ? [384, 846, 1152, 212, 28, 37] : B70 ? [384, 738, 1152, 320, 30, 42] : CTR ? [384, 640, 1152, 248, 26, 36] : [270, 580, 1380, 246, 26, 36]; comp("terminal", "label", () => { const [x, y, w, h, fs, lh] = LR, PAD = 24, BAR = 40; c.save(); rr(x, y, w, h, 12); c.fillStyle = "#0B0D10"; c.fill(); rr(x, y, w, h, 12); c.clip(); c.fillStyle = "#1B1F25"; c.fillRect(x, y, w, BAR); ["#FF5F57", "#FEBC2E", "#28C840"].forEach((k, n) => { c.beginPath(); c.arc(x + 24 + n * 20, y + 20, 6, 0, Math.PI * 2); c.fillStyle = k; c.fill(); }); font(600, 21); c.fillStyle = "#D8D6CF"; c.textAlign = "center"; c.fillText(SIDE ? "Six stored runs, not a controlled test · Nov 3" : "One repeated job, six stored runs, not a controlled test · Nov 3", x + w / 2, y + 27); c.textAlign = "left"; c.font = `400 ${fs}px ${TMONO}`; vis9.forEach((q, n) => { if (cur9 && q[1].startsWith(`run ${cur9[1]}:`)) { c.fillStyle = "#23282F"; c.fillRect(x + 12, y + BAR + 14 + n * lh - 2, w - 24, lh); } c.fillStyle = /no model/.test(q[1]) ? "#86DDCB" : "#F2F0EA"; c.fillText(q[1], x + PAD, y + BAR + 14 + n * lh + lh * 0.74); }); c.restore(); }); (window.__termChk = window.__termChk || {}).main = { x: LR[0], y: LR[1], w: LR[2], h: LR[3], over: 0 }; }
  function terPanels(t) { const Q = TR, T1 = "Real run, sped up · Nov 3";
    if (TV === "s50") return termBox(t, { x: 40, y: 40, w: 880, h: 780, fs: 28, lh: 38, title: T1, short: true });
    if (TV === "s40") return termBox(t, { x: 40, y: 40, w: 720, h: 780, fs: 26, lh: 36, title: T1, short: true });
    if (B80 && MAINF) return termBox(t, { x: 336, y: 852, w: 1248, h: 200, fs: 30, lh: 44, title: FEED9 ? T1 : "Real agent run, Muse Spark 1.3, sped up · Nov 4 UTC", pred: FEED9 ? (q) => !/^\s/.test(q.text) : undefined }); if (B80) return termBox(t, { x: 384, y: 846, w: 1152, h: 212, fs: 28, lh: 37, title: T1, pred: (q) => !/^\s/.test(q.text) });
    if (B70) return termBox(t, { x: 384, y: 738, w: 1152, h: 320, fs: 30, lh: 42, title: T1 });
    if (TV === "paper") return termBox(t, { x: 40, y: 40, w: 760, h: 780, fs: 21, lh: 29, title: T1 });
    if (TV === "center") return termBox(t, { x: 384, y: 640, w: 1152, h: 248, fs: 26, lh: 36, title: T1, short: true });
    if (TV === "both") { termBox(t, { id: " left", x: 30, y: 540, w: 690, h: 286, fs: 24, lh: 34, title: "Task queue · real run, sped up · Nov 3", pred: (q) => !TOBJ(q), short: true }); return termBox(t, { id: " right", x: 1200, y: 540, w: 690, h: 286, fs: 24, lh: 34, title: "Task Objects · real run, sped up · Nov 3", pred: TOBJ, short: true }); }
    if (TV === "models") return termBox(t, { x: 384, y: 640, w: 1152, h: 248, fs: 26, lh: 36, title: T1, pred: TMOD, short: true });
    if (TV === "zoom") { if (t < Q.TL.at[1]) return; const G = Q.TL.at.filter((a, i) => /^node |^GitHub|^reuse check|^label muse-spark|^audit by|^published/.test(TLOG[i].text)); let g0 = G[0]; G.forEach((a) => { if (t >= a) g0 = a; }); const sl = 1 - soft((t - g0) / 0.35), z = 1 + 0.03 * clamp((t - g0) / 2); c.save(); c.translate(960, 720 + sl * 340); c.scale(z, z); c.translate(-960, -720); termBox(t, { x: 270, y: 620, w: 1380, h: 196, fs: 30, lh: 42, title: T1 }); c.restore(); } }
  function hop9(t) { const Q = TR, T9 = { s1: [-0.68, 0.02, 1], s2: [-0.68, 0.02, 1], s6: [0, 0.62, 2], s3: [0, 0, 3], s4: [0, 0, 3], s5: [0.68, 0.02, 1], s7: [0, -0.5, 4] }; comp("hop", "traffic", () => TLOG.forEach((x, i) => { const g = T9[x.st9]; if (!g) return; const f0 = t - Q.TL.at[i]; if (f0 < 0 || f0 > 0.95) return; for (let n = 0; n < 3; n++) { const f = clamp((f0 - n * 0.1) / 0.65); if (f <= 0 || f >= 1) continue; const e = inOut(f), x0 = 336 + 24 + Math.min(x.text.length * 18, 900) - n * 30, y0 = 900, x1 = TCX + g[0] * ZX + (n - 1) * 26, y1 = TCY + g[1] * ZY; isoBox(mix(x0, x1, e), mix(y0, y1, e) - Math.sin(f * Math.PI) * 70, 15, 15, K5[g[2]] ? K5[g[2]][0] : "#7A5BA8"); } })); }
  function sceneTerrain(t) { c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080); if (!TR) terBuild(); terCam(t); DK = 0; if (CUES.models && t >= S("models") && t < (CUES.learn ? TR.ats[TR.names.findIndex((n) => /run 1 of 6/.test(n))] : S("models") + CUES.models.seconds)) TRIP = { amp: 16 * soft((t - S("models")) / 0.5), chaos: 0, t }; else if (TERM && /^ev[touqwr]/.test(VK) && t >= TR.firstTask) TRIP = { amp: 8, chaos: 0, t }; const { i0, want, HO } = drawTerrainSet(t), Q = TR; TRIP = null; const inL = CUES.learn && t >= S("learn") && t < S("four"); if (TERM && MAINF && !FEED9 && !inL) hop9(t); if (TERM) { terMoves(t); if (inL && t >= TR.ats[TR.names.findIndex((n) => /run 1 of 6/.test(n))]) learnTerm(t); else terPanels(t); } else terTask(t, HO);
    pill("Teleion Fabric", TCX, 62, { size: TERM ? 34 : 42, w: 700, color: INK, stroke: LINE, fill: CARD });
    const nw9 = MAINF && Q.iT ? K5.filter((q, k) => t >= Q.iT[k] - 0.05 && t < Q.iT[k] + 1.7).pop() : null; if (nw9) { pill(nw9[1], TCX, 150, { size: 42, w: 700, color: INK, stroke: nw9[0], lw: 4, fill: CARD }); font(700, 42); const w9 = c.measureText(nw9[1]).width; isoBox(TCX - w9 / 2 - 34, 158, 14, 16, nw9[0]); } else if (TERM && CUES.learn && t >= S("learn") && t < S("four") && /run \d/.test(Q.names[i0] || "")) pill(Q.names[i0], TCX, 150, { size: 26, w: 700, color: INK, stroke: K5[3][0], lw: 3, fill: CARD }); else if (TERM && t >= Q.TL.at[1]) pill(MAINF && !FEED9 ? "One Task: fix a checklist" : "A feed Task", TCX, SIDE ? 160 : 150, { size: 26, w: 700, color: INK, stroke: K5[1][0], lw: 3, fill: CARD }); else if (!TERM && Q.names[i0]) { const a = soft((t - Q.ats[i0] - 0.12) / 0.28); if (a < 1 && i0 > 6 && Q.names[i0 - 1]) pill(Q.names[i0 - 1], TCX, 170, { a: 1 - a, size: 32, w: 700, color: INK, stroke: K5[Q.wants[i0 - 1][0]][0], lw: 3, fill: CARD }); pill(Q.names[i0], TCX, 170, { a, size: 32, w: 700, color: INK, stroke: K5[want[0]][0], lw: 3, fill: CARD }); }
    terLegend(t, i0 > 6 && t < Q.ats[i0] + 0.35 ? Q.wants[i0 - 1] : want);
    // The kinds are named as they land, then each name settles into the legend.
    if (!TERM && t >= Q.firstTask + 0.3 && (t < Q.end || (CUES.models && t < S("models") + CUES.models.seconds) || (CUES.learn && t < S("four")))) { pill(CUES.learn && t >= S("learn") && t < S("four") ? "Six recorded runs of one repeated job, Nov 3" : "One OmniNode, shaped for this Task", TCX, 802, { size: 30, w: 600, color: INK, stroke: LINE, fill: CARD }); }
  }
  function sceneTech(t) {
    c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080);
    if (DIR === "stack") { cam = camAt(1230, 590, 56); drawStackFloors(t, false); drawLong(t); drawPanel(t); tagAnim(); return; }
    if (DIR === "cutaway") { cam = camAt(1130, 545, 66); drawCutaway(t, false); drawLong(t); drawPanel(t); tagAnim(); return; }
    if (DIR === "parallax") { drawParallaxBack(t); cam = camAt(900 + Math.sin(t * 0.17) * 16, 610, 76); drawSet(t); drawParallaxFront(t); drawPanel(t); tagAnim(); return; }
    if (DIR === "closeup") { camPath(t, closeKeys(), 1250, 660); drawSet(t); c.save(); c.globalAlpha = Math.min(0.92, Math.max(0, (cam.u - 95) / 50)); rr(40, 640, 660, 270, 16); c.fillStyle = GROUND; c.fill(); c.restore(); drawPanel(t); tagAnim(); return; }
    if (DIR === "campus") { camPath(t, campusKeys(), 1180, 600); drawSet(t); drawPanel(t); tagAnim(); return; }
    if (DIR === "chapters") { const k = sceneAt(t); const w = CHWORD[k]; if (w) { const a = soft(seg(t, S(k), F(16))); font(700, 104); c.save(); c.globalAlpha = 0.85 * a; c.fillStyle = "#FFFDF8"; c.textAlign = "right"; c.fillText(w, 1880 + (1 - a) * 200 - (t - S(k)) * 2, 880); c.restore(); } cam = camAt(860, 585, 92); drawSet(t); drawPanel(t); tagAnim(); return; }
    if (STYLE === "iso") { sceneIso3(t); return; }
    cam = camAt(860, 585, 92); drawSet(t); drawPanel(t); tagAnim();
  }
  // Camera moves are parallel pans and pull-backs between named subjects; it holds still between them.
  function camPath(t, keys, fx, fy, dur = 0.95) {
    let i = 0; for (let k = 0; k < keys.length; k++) if (t >= keys[k][0]) i = k;
    const q = keys[i], prev = keys[Math.max(0, i - 1)], k = inOut((t - q[0]) / dur), u = mix(prev[3], q[3], k), x = mix(prev[1], q[1], k), y = mix(prev[2], q[2], k), z = mix(prev[4] || 0, q[4] || 0, k);
    cam = { x: fx - MX * (x - y) * COS * u, y: fy - (x + y) * 0.5 * u + z * u, u };
  }
  const WHOLE = [0, -2.2, 92 * 0.9], pkey = (at, p, u, z) => [at, p[0], p[1], u, z || 0];
  function closeKeys() { return [pkey(0, [0, 0], 92), pkey(S("parts"), [-0.2, -2.0], 88), pkey(B.first, TD, 245, 1.4), pkey(B.second, OD, 245, 1.4), pkey(B.third, NODE, 320, 0.7), pkey(B.together, [-0.2, -2.0], 88), pkey(S("split"), [-0.2, -2.0], 88), pkey(B.sPicks, NODE, 150, 0.5), pkey(B.sSep, AUD, 210, 0.5), pkey(S("omninode"), NODE, 320, 0.7), pkey(B.oLearn, NODE, 170, 0.5), pkey(S("four"), [-0.2, -2.0], 88), pkey(B.fKnow, TD, 180, 1.2), pkey(B.fReuse, OD, 180, 1.2), pkey(B.fLong, [-0.2, -2.0], 88), pkey(B.fBetter, NODE, 220, 0.6), pkey(B.fFewer, [-0.2, -2.0], 88)]; }
  function campusKeys() { const W = [-1.5, -5], wu = 39; return [pkey(0, W, wu), pkey(S("parts"), W, wu), pkey(B.first, TD, 96, 1.2), pkey(B.second, OD, 96, 1.2), pkey(B.third, NODE, 96, 0.7), pkey(B.together, W, wu), pkey(S("split"), W, wu), pkey(B.sSplits + 0.9, TD, 92, 1), pkey(B.sPicks + 0.7, NODE, 92, 0.6), pkey(B.sSep, AUD, 92, 0.6), pkey(S("omninode"), NODE, 110, 0.6), pkey(S("four"), W, wu), pkey(B.fKnow, TD, 92, 1), pkey(B.fReuse, OD, 92, 1), pkey(B.fLong, W, wu), pkey(B.fBetter, NODE, 92, 0.6), pkey(B.fFewer, W, wu)]; }
  // Moves, re-routed for directions that lay the parts out differently.
  const routeKey = (m) => (m.route === tToNode ? "tn" : m.route === nodeToAud ? "na" : m.route === audToO ? "ao" : m.route === oToNode ? "on" : m.route[0][2] === 5.2 ? "drop" : null);
  function movers(t, R, z0 = -9, z1 = 99) { for (const m of moves) if (t >= m.t0 && t < m.t1) { const r = R[routeKey(m)]; if (!r) continue; const q = along(r, inOut((t - m.t0) / (m.t1 - m.t0))); if (q[2] >= z0 && q[2] < z1) chip(q[0], q[1], q[2], m.type === "task" ? "task" : "obj", 0.5); } }
  const focusOf = (t) => (t >= B.first && t < B.second ? "T" : t >= B.second && t < B.third ? "O" : t >= B.third && t < B.together ? "N" : null);
  const nodeLabel = (t) => { const m = modeAt(t); return t < S("split") ? { name: "Fabric Intelligence", col: BLUE } : m || { name: "OmniNode", col: BLUE }; };
  const litPill = (s, x, y, a, col, on, size = 34) => pill(s, x, y, { a, size, w: 700, ...(on ? { fill: col, color: CARD, stroke: col } : { color: col, stroke: col }) });
  // 1. Exploded stack: three floors of one bounded section. Tasks travel down between them.
  function drawStackFloors(t, hero) {
    const pS = S("parts"), open = hero ? inOut(t / 2.2) : Math.max(inOut(seg(t, pS + 0.3, 1.3)), t >= S("split") ? 1 : 0), g = mix(0.42, 2.75, open), zO = 0, zN = g + 0.16, zT = 2 * g + 0.32, H = 2.9, st8 = mix(0, 1.25, open), ow = (dx) => [dx, -dx];
    const f = hero ? null : focusOf(t), dim = (k) => (f && f !== k ? 0.28 : 1), st = hero ? { T: 6, O: 5 } : stockAt(t), a0 = hero ? soft(t / 0.4) : soft(seg(t, pS, F(14)));
    const line3 = (x, y) => { const p0 = P(x, y, -0.2), p1 = P(x, y, zT + 1.1); c.beginPath(); c.moveTo(p0[0], p0[1]); c.lineTo(p1[0], p1[1]); c.stroke(); };
    const R0 = H + 0.5 + st8, rim = (z) => { path([P(-R0, -R0, z), P(R0, -R0, z), P(R0, R0, z), P(-R0, R0, z)]); c.stroke(); };
    faded(a0, () => { c.strokeStyle = BLUE; c.lineWidth = 3; rim(-0.2); line3(-R0, -R0); line3(R0, -R0); line3(-R0, R0); });
    const O0 = [st8, -st8], T0 = [-st8, st8];
    const R = { tn: [[T0[0] - 1.2, T0[1], zT + 0.16], [T0[0] + 1.8, T0[1], zT + 0.16], [1.5, 0, zN + 0.16], [0, 0, zN + 0.9]], na: [[0, 0, zN + 0.2], [1.8, 0, zN + 0.2], [1.8, 1.4, zN + 0.2]], ao: [[1.8, 1.4, zN + 0.2], [1.8, -1.2, zN + 0.2], [O0[0] + 0.3, O0[1] + 1.2, zO + 0.2]], on: [[O0[0] - 1.2, O0[1] - 0.4, zO + 0.2], [-1.3, -0.4, zN + 0.2], [0, -0.3, zN + 0.2]], drop: [[O0[0] - 1.2, O0[1] - 0.4, zO + 3], [O0[0] - 1.2, O0[1] - 0.4, zO + 0.2]] };
    const floor = (z, col, o) => { softShadow(o[0] - H, o[1] - H, 2 * H, 2 * H, z + 0.01); box(o[0] - H, o[1] - H, z, 2 * H, 2 * H, 0.16, col); };
    faded(a0 * dim("O"), () => { floor(zO, f === "O" ? SAND : CARD, O0); const cols = [[-1.6, -1.6], [-0.2, -1.6], [1.2, -1.6], [-1.6, -0.1], [-0.2, -0.1], [1.2, -0.1], [-1.6, 1.4], [-0.2, 1.4]]; for (let i = 0; i < Math.min(st.O, 8); i++) box(O0[0] + cols[i][0] - 0.35, O0[1] + cols[i][1] - 0.35, zO + 0.16, 0.7, 0.7, 0.4, RUST, 0.3); });
    if (!hero) faded(1, () => movers(t, R, -1, zN));
    faded(a0 * dim("N"), () => { floor(zN, f === "N" ? PALE : CARD, [0, 0]); octo(0, 0, zN + 0.16, 1.1, 0.75, CARD, BLUE); if (hero || t >= B.sSep - 0.5) octo(1.8, 1.4, zN + 0.16, 0.7, 0.5, t >= B.sSep + 0.6 ? SAND : CARD, RUST); const [a, b] = P(0, 0, zN + 0.91), k = (t * 1.6) % 6.28; c.lineWidth = 7; c.strokeStyle = LINE; c.beginPath(); c.ellipse(a, b, 0.72 * KX * cam.u, 0.72 * KY * cam.u, 0, 0, 6.3); c.stroke(); c.strokeStyle = BLUE; c.beginPath(); c.ellipse(a, b, 0.72 * KX * cam.u, 0.72 * KY * cam.u, 0, k, k + 1.3); c.stroke(); });
    if (!hero) movers(t, R, zN, zT);
    faded(a0 * dim("T"), () => { floor(zT, f === "T" ? PALE : CARD, T0); const pos = [[-1.8, -1.4], [-0.6, -1.4], [0.6, -1.4], [1.8, -1.4], [-1.8, 0.6], [-0.6, 0.6]]; for (let i = 0; i < Math.min(st.T, 6); i++) box(T0[0] + pos[i][0] - 0.38, T0[1] + pos[i][1] - 0.38, zT + 0.16, 0.76, 0.76, 0.26, BLUE, 0.3); });
    if (!hero) movers(t, R, zT, 99);
    faded(a0, () => { c.strokeStyle = BLUE; c.lineWidth = 3; rim(zT + 1.1); line3(R0, R0); });
    if (hero) return;
    const lb = (z) => P(R0, R0, z)[1] - 8, xr = P(R0, -R0, 0)[0] + 10, hide = t >= S("split") && t < B.sSplits + 1 ? 0 : 1, m = nodeLabel(t), xl = 1920 - 300;
    pill("Teleion Fabric", P(-R0, R0, zT + 1.1)[0] + 40, P(-R0, R0, zT + 1.1)[1] - 34, { a: a0 * hide, size: 36, w: 700, color: BLUE, stroke: BLUE, lw: 3 });
    const lab = (o, z) => { const q = P(o[0] + H, o[1] - H, z); return [q[0] + 22 * MX, q[1] - 26]; };
    { const q = P(T0[0], T0[1], zT + 0.9); litPill("Durable Tasks", q[0], q[1], a0 * dim("T") * hide, BLUE, f === "T"); }
    { const q = lab([0, 0], zN); litPill(m.name, q[0] + 60 * MX, q[1], a0 * dim("N") * hide, m.col, f === "N", m.name.length > 22 ? 26 : 34); }
    { const q = P(O0[0] + H, O0[1], zO + 0.16); litPill("Durable Task Objects", q[0] + 30 * MX, q[1] + 64, a0 * dim("O") * hide, RUST, f === "O", 32); }
    if (t >= B.powered - 0.3) pill("Meta models power this floor", lab([0, 0], zN)[0] + 60 * MX, lab([0, 0], zN)[1] + 56, { a: soft(seg(t, B.powered - 0.3, F(12))) * dim("N"), size: 26, color: BLUE, stroke: BLUE, fill: PALE });
    pill("Any agent connects here", P(T0[0] - H, T0[1] + H, zT)[0] - 30 * MX, P(T0[0] - H, T0[1] + H, zT)[1] + 48, { a: soft(seg(t, pS + 1.2, F(12))) * hide * dim("-"), size: 26 });
    if (t >= B.sSep - 0.3 && t < B.sSep + 3) pill("A separate OmniNode", P(1.8, 1.4, zN)[0] + 40 * MX, P(1.8, 1.4, zN)[1] + 66, { a: soft(seg(t, B.sSep - 0.3, F(10))), size: 26, color: RUST, stroke: RUST, fill: SAND });
    if (t >= B.feedAt && t < B.fReuse - 0.1) pill("Feed maintenance Task", P(T0[0], T0[1], zT)[0], P(T0[0], T0[1], zT + 1.6)[1], { a: soft(seg(t, B.feedAt, F(8))), size: 26, color: BLUE, stroke: BLUE, fill: PALE });
  }
  // 2. Cutaway: the section lifts its roof like a building. Three rooms, names on the walls.
  function drawCutaway(t, hero) {
    const pS = S("parts"), X = 7.4, Y = 3, HW = 3, open = hero ? inOut(seg(t, 1, 1.6)) : Math.max(inOut(seg(t, pS + 0.2, 1.3)), 0), f = hero ? null : focusOf(t), st = hero ? { T: 6, O: 5 } : stockAt(t), dim = (k) => (f && f !== k ? 0.3 : 1), a0 = hero ? soft(t / 0.4) : soft(seg(t, pS, F(12)));
    const wallA = (x0, x1, y, h, fill) => { const q = [P(x0, y, 0), P(x1, y, 0), P(x1, y, h), P(x0, y, h)]; poly(q, fill); poly(q, shade(0.03)); c.strokeStyle = shade(0.2); c.lineWidth = 1.5; path(q); c.stroke(); };
    const wallB = (x, y0, y1, h, fill) => { const q = [P(x, y0, 0), P(x, y1, 0), P(x, y1, h), P(x, y0, h)]; poly(q, fill); poly(q, shade(0.08)); c.strokeStyle = shade(0.2); c.lineWidth = 1.5; path(q); c.stroke(); };
    const onWall = (x, y, z, fn) => { const [ox, oy] = P(x, y, z); c.save(); c.transform(COS * cam.u / 100, 0.5 * cam.u / 100, 0, cam.u / 100, ox, oy); fn(); c.restore(); };
    faded(a0, () => {
      box(-X - 0.25, -Y - 0.25, -0.2, 2 * X + 0.5, 2 * Y + 0.5, 0.2, CARD); const fl = [P(-X, -Y, 0.01), P(X, -Y, 0.01), P(X, Y, 0.01), P(-X, Y, 0.01)]; c.strokeStyle = BLUE; c.lineWidth = 4; path(fl); c.stroke();
      [[-X, -2.46, "T", PALE], [-2.46, 2.46, "N", "#EEF1F8"], [2.46, X, "O", SAND]].forEach(([a, b, k, col]) => { if (f === k) poly([P(a, -Y, 0.01), P(b, -Y, 0.01), P(b, Y, 0.01), P(a, Y, 0.01)], col); });
      wallB(-X, -Y, Y, HW, "#F7F4EC"); wallA(-X, X, -Y, HW, "#F9F6EE"); wallB(-2.46, -Y, -0.7, HW * 0.75, "#F7F4EC"); wallB(2.46, -Y, -0.7, HW * 0.75, "#F7F4EC");
      [[-X + 0.45, ["Durable", "Tasks"], BLUE, "T"], [-2.0, ["Fabric", "Intelligence"], BLUE, "N"], [2.95, ["Durable Task", "Objects"], RUST, "O"]].forEach(([x, nm, col, k]) => { faded(dim(k), () => onWall(x, -Y, HW - 0.7, () => { font(700, 50); c.fillStyle = col; c.fillText(nm[0], 0, 0); c.fillText(nm[1], 0, 56); })); });
    });
    const R = { tn: [[-4.7, 0, 2.05], [-4.7, 0, 0.14], [0, 0, 0.14], [0, 0, 0.3]], na: [[0, 0, 0.14], [0, 2.1, 0.14]], ao: [[0, 2.1, 0.14], [4.7, 2.1, 0.14], [4.7, 0, 0.14], [4.7, 0, 2.05]], on: [[4.7, 0, 2.05], [4.7, -1.6, 0.14], [0, -1.6, 0.14], [0, 0, 0.3]], drop: [[4.7, 0, 5.2], [4.7, 0, 2.05]] };
    faded(a0 * dim("T"), () => { database(-4.7, 0, 1.45, 1, BLUE); for (let i = 0; i < Math.min(6, st.T); i++) chip(-4.7 + (i % 3 - 1) * 0.6, (Math.floor(i / 3) - 0.5) * 0.7, 2.05, "task", 0.46); });
    faded(a0 * dim("N"), () => { discShadow(0, 0, 1.1); octo(0, 0, 0.02, 1.1, 0.85, CARD, BLUE); const [a, b] = P(0, 0, 0.87), k = (t * 1.6) % 6.28; c.lineWidth = 7; c.strokeStyle = LINE; c.beginPath(); c.ellipse(a, b, 0.78 * cam.u, 0.46 * cam.u, 0, 0, 6.3); c.stroke(); c.strokeStyle = BLUE; c.beginPath(); c.ellipse(a, b, 0.78 * cam.u, 0.46 * cam.u, 0, k, k + 1.3); c.stroke(); });
    if (hero || t >= B.sSep - 0.5) faded(a0, () => { discShadow(0, 2.1, 0.75); octo(0, 2.1, 0.02, 0.75, 0.6, t >= B.sSep + 0.6 ? SAND : CARD, RUST); });
    faded(a0 * dim("O"), () => { database(4.7, 0, 1.45, 1, RUST); for (let i = 0; i < Math.min(9, st.O); i++) chip(4.7 + (i % 3 - 1) * 0.65, -0.3 + (i % 2) * 0.6, 2.05 + Math.floor(i / 3) * 0.3, "obj", 0.48); });
    if (!hero) movers(t, R);
    if (open < 1) { faded((1 - open) * a0, () => { box(-X - 0.25, -Y - 0.25, HW + open * 4, 2 * X + 0.5, 2 * Y + 0.5, 0.2, CARD); wallA(-X, X, Y, HW, "#F9F6EE"); wallB(X, -Y, Y, HW, "#F7F4EC"); }); }
    if (hero) return;
    const hide = t >= S("split") && t < B.sSplits + 1 ? 0 : 1;
    pill("Teleion Fabric", P(X, -Y, HW)[0] + 20 * MX, P(X, -Y, HW)[1] - 50, { a: a0 * hide, size: 36, w: 700, color: BLUE, stroke: BLUE, lw: 3 });
    pill("Any agent", P(-X - 1.6, 0, 0.7)[0], P(-X - 1.6, 0, 0.7)[1], { a: soft(seg(t, pS + 1.2, F(12))) * hide * dim("-"), size: 28 });
    if (t >= B.powered - 0.3) pill("Meta models", P(0, 0, 3.05)[0], P(0, 0, 2.2)[1] - 30, { a: soft(seg(t, B.powered - 0.3, F(12))) * dim("N"), size: 28, w: 700, color: BLUE, stroke: BLUE, fill: PALE });
    if (t >= S("split")) { const m = nodeLabel(t); pill(m.name, P(0, 0, 1.3)[0], P(0, 0, 1.3)[1], { a: hide, size: 28, w: 700, color: m.col, stroke: m.col }); }
    if (t >= B.sSep - 0.3) pill("A separate OmniNode", P(0, 2.1, 0)[0] - 150, P(0, 2.1, 0)[1] + 72, { a: soft(seg(t, B.sSep - 0.3, F(10))), size: 26, color: RUST, stroke: RUST, fill: SAND });
    if (t >= B.feedAt && t < B.fReuse - 0.1) pill("Feed maintenance Task", P(-4.7, 0, 3.2)[0], P(-4.7, 0, 3.2)[1], { a: soft(seg(t, B.feedAt, F(8))), size: 26, color: BLUE, stroke: BLUE, fill: PALE });
  }
  // 4. Depth: soft blocks far away, real UI on isometric panels behind the set, large soft Tasks passing in front.
  function isoSheet(o, ox, oy, sc, a) { // a real page on a wall plane
    const im = IMG[o.img]; if (!im) return; if (window.__views) window.__views.push({ img: o.img, x0: o.x, y0: o.y, x1: o.x + o.w, y1: o.y + o.h, t: -1 });
    c.save(); c.globalAlpha *= a; c.transform(COS * sc, -0.5 * sc, 0, sc, ox, oy); c.shadowColor = "rgba(74,64,48,.3)"; c.shadowBlur = 24; c.fillStyle = CARD; c.fillRect(0, 0, o.w, o.h); c.shadowBlur = 0; c.beginPath(); c.rect(0, 0, o.w, o.h); c.clip(); c.drawImage(im, o.x, o.y, o.w, o.h, 0, 0, o.w, o.h); c.restore();
  }
  function drawParallaxBack(t) {
    const d = Math.sin(t * 0.17); cam = camAt(960 + d * 9, 540, 58);
    faded(0.55, () => { for (let i = 0; i < 9; i++) { const x = -14 + ((i * 7) % 26), y = -13 + ((i * 11) % 22); softShadow(x, y, 2.4, 2.4, 0); box(x, y, 0, 2.4, 2.4, 0.5 + (i % 3) * 0.7, "#EFEAE0", 0.1); } });
    const panel = t < S("split") ? { img: "dash", x: 60, y: 520, w: 2000, h: 760 } : t < S("omninode") ? { img: "example", x: 0, y: 0, w: 2000, h: 760 } : t < S("four") ? { img: "dash", x: 60, y: 720, w: 2000, h: 760 } : { img: "ngo", x: 60, y: 100, w: 2000, h: 760 };
    panel.w = 1300; isoSheet(panel, 1190 + d * 12, 372, 0.5, 1);
    pill("Real page", 1810 + d * 12, 66, { size: 24, color: MUTED });
  }
  let SPR = null;
  function sprites() { // large soft Tasks, blurred once at load
    const mk = (col) => { const o = document.createElement("canvas"); o.width = 340; o.height = 300; const g = o.getContext("2d"); g.filter = "blur(8px)"; const W = 120, H = 60, cx = 170, cy = 120; g.fillStyle = col; g.beginPath(); g.moveTo(cx, cy - H); g.lineTo(cx + W, cy); g.lineTo(cx, cy + H); g.lineTo(cx - W, cy); g.fill(); g.fillStyle = col; g.globalAlpha = 0.86; g.beginPath(); g.moveTo(cx - W, cy); g.lineTo(cx, cy + H); g.lineTo(cx, cy + H + 50); g.lineTo(cx - W, cy + 50); g.fill(); g.globalAlpha = 0.72; g.beginPath(); g.moveTo(cx + W, cy); g.lineTo(cx, cy + H); g.lineTo(cx, cy + H + 50); g.lineTo(cx + W, cy + 50); g.fill(); return o; };
    SPR = { task: mk(BLUE), obj: mk(RUST) };
  }
  function drawParallaxFront(t) {
    if (!SPR) sprites();
    [[0.019, 0.1, "task", -60], [0.014, 0.6, "obj", 820]].forEach(([sp, ph, kind, yy]) => { const k = (t * sp + ph) % 1, sx = (V.mirror ? -340 : 760) + k * 1500; c.save(); c.globalAlpha = 0.5; c.drawImage(SPR[kind], sx, yy); c.restore(); });
  }
  // 7. Real pages as sheets that fan out in isometric, then settle flat when the voice reaches them.
  const SHEETSAFE = { home: { x: 0, y: 0, w: 1960, h: 870 }, ngo: { x: 100, y: 0, w: 2200, h: 978 }, result: { x: 0, y: 0, w: 2200, h: 978 }, help: { x: 40, y: 600, w: 2200, h: 978 }, process: { x: 0, y: 0, w: 2200, h: 978 }, example: { x: 0, y: 0, w: 2200, h: 978 }, library: { x: 40, y: 0, w: 2200, h: 978 }, dash: { x: 60, y: 520, w: 2200, h: 978 } };
  function sheet(o, t, t0, t1, slot) {
    const up = inOut((t - t0) / 0.65), down = inOut((t - (t1 - 0.35)) / 0.35), k = up * (1 - down), v = clamp((t - t0) / (t1 - t0)), s = mix(o.a.s, o.b.s, inOut(v)), ix = mix(o.a.x, o.b.x, inOut(v)), iy = mix(o.a.y, o.b.y, inOut(v)), im = IMG[o.img]; if (!im) return;
    if (window.__views) window.__views.push({ img: o.img, x0: ix, y0: iy, x1: ix + 1800 / s, y1: iy + 800 / s, t });
    const sc = 0.5, ax = COS * sc, bx = 0.5 * sc, cx = -COS * sc, dx = 0.5 * sc, ex = 1120 + slot * 52 - 300, fx = 70 + slot * 62;
    c.save(); c.transform(mix(ax, 1, k), mix(bx, 0, k), mix(cx, 0, k), mix(dx, 1, k), mix(ex, 60, k), mix(fx, 56, k));
    c.shadowColor = "rgba(74,64,48,.3)"; c.shadowBlur = 26; c.shadowOffsetY = 10; c.fillStyle = CARD; c.fillRect(0, 0, 1800, 800); c.shadowBlur = 0; c.shadowOffsetY = 0; c.beginPath(); c.rect(0, 0, 1800, 800); c.clip(); c.drawImage(im, -ix * s, -iy * s, im.width * s, im.height * s);
    c.restore();
    if (o.label && k > 0.9) { font(600, 26); const lw = c.measureText(o.label).width + 34; rr(1860 - lw - 22, 792, lw, 44, 22); c.fillStyle = CARD; c.fill(); c.strokeStyle = o.warn ? RUST : BLUE; c.lineWidth = 2; c.stroke(); c.fillStyle = o.warn ? RUST : BLUE; c.fillText(o.label, 1860 - lw - 22 + 17, 823); }
  }

  // ------------------------------------------------------------ kinetic type over real UI
  const UIS = ["ngo", "result", "process"], UIROT = (k, i) => UIS[(UIS.indexOf(k) + i) % UIS.length]; const UIBG = { title: "ngo", hook: "result", three: "process", statement: "ngo", parts: "result", split: "process", omninode: "ngo", four: "result", connect: "ngo" };
  const SENTS = {}; // sentences per scene, built at load
  function kinetic(t, k) {
    const s = CUES[k], im = IMG[UIROT(UIBG[k], V.ui)], l = (t - s.start) / s.seconds;
    c.fillStyle = GROUND; c.fillRect(0, 0, 1920, 1080);
    if (im) { const sc = 0.78, dy = mix(0, Math.max(0, im.height - 1400) * 0.9, l); c.save(); c.globalAlpha = V.kalpha; c.drawImage(im, 0, -dy * sc, im.width * sc, im.height * sc); c.restore(); }
    let cur = SENTS[k].find((q, i) => t < (SENTS[k][i + 1] ? SENTS[k][i + 1][0][1] : 1e9) - 0.05) || SENTS[k][SENTS[k].length - 1];
    if (t < cur[0][1] - 0.2) return;
    const big = cur.map((w) => w[0]).join(" "), size = big.length < 34 ? 104 : big.length < 62 ? 84 : big.length < 110 ? 66 : 54, n = lines(big, 1620, size, 700).length, lh = size * 1.14;
    let y = 480 - ((n - 1) * lh) / 2, x = 150, i = 0; const keys = ["dumb.", "new.", "exists.", "trouble", "Durable", "OmniNodes,", "OmniNodes.", "Eranos.", "reuse", "better.", "fewer", "audits", "approves"];
    for (const ln of lines(big, 1620, size, 700)) {
      font(700, size); x = V.kalign === "center" ? 960 - c.measureText(ln).width / 2 : 150;
      for (const word of ln.split(" ")) {
        const wt = cur[i] ? cur[i][1] : t, a = soft(seg(t, wt - 0.08, F(10))), wd = c.measureText(word).width;
        if (a > 0) { c.save(); c.beginPath(); c.rect(x - 6, y - size, wd + 14, size * 1.3); c.clip(); c.fillStyle = keys.includes(word) ? RUST : INK; c.fillText(word, x, y + (1 - a) * size * 1.15); c.restore(); }
        x += wd + c.measureText(" ").width; i++;
      }
      y += lh;
    }
  }
  // ------------------------------------------------------------ captions, the hackathon line, transitions
  function caption(t) { comp("caption", "caption", () => caption0(t)); }
  function caption0(t) {
    if (!CAPS) return; let cur = null; for (const q of CAPTIONS) if (t >= q[1] && t < q[2]) { cur = q; break; } if (!cur) return; if (GLASS && dupOf(cur[0])) { window.__capSkip = cur[0]; return; }
    let ls = lines(cur[0], 1560, 36, 600); font(600, 36); if (ls.length === 2) { const ws = cur[0].split(" "); let best = null; for (let i = 1; i < ws.length; i++) { const a = ws.slice(0, i).join(" "), b = ws.slice(i).join(" "), wa = c.measureText(a).width, wb = c.measureText(b).width, sc0 = Math.abs(wa - wb) - (/[,:]$/.test(ws[i - 1]) ? 240 : 0); if (wa < 1560 && wb < 1560 && (!best || sc0 < best[0])) best = [sc0, [a, b]]; } if (best) ls = best[1]; } const w = Math.max(...ls.map((l) => c.measureText(l).width)), n = ls.length, h = 18 + n * 46, y0 = 1036 - h;
    if (GLASS) { frost(960 - w / 2 - 22, y0, w + 44, h, 12, 0.62); font(600, 36); } else { rr(960 - w / 2 - 22, y0, w + 44, h, 12); c.fillStyle = "rgba(255,253,248,.94)"; c.fill(); } c.fillStyle = INK; c.textAlign = "center"; ls.forEach((l, i) => c.fillText(l, 960, y0 + 40 + i * 46)); c.textAlign = "left";
  }
  function hackathon() {}
  // Scene B shown through a shape that opens. kinds: wipe (masked, soft leading rail), flood (circle from a point).
  function reveal(kind, k, fnB, o = {}) {
    c.save(); c.beginPath();
    if (kind === "flood") { const R = Math.hypot(1920, 1080) * 1.05 * k; c.arc(o.x || 960, o.y || 540, R, 0, Math.PI * 2); }
    else if (kind === "wipeL") { const x = mix(1920 + 260, -260, k); c.moveTo(x + 260, 0); c.lineTo(1920 + 600, 0); c.lineTo(1920 + 600, 1080); c.lineTo(x - 260, 1080); }
    else if (kind === "wipeU") { const y = mix(1080, 0, k); c.rect(0, y, 1920, 1080 - y); }
    else if (kind === "wipeD") { c.rect(0, 0, 1920, 1080 * k); }
    else if (kind === "iris") { c.rect(960 * (1 - k), 540 * (1 - k), 1920 * k, 1080 * k); }
    else c.rect(0, 0, 1920 * k, 1080);
    c.clip(); fnB(); c.restore();
    if (kind === "wipeL") { const x = mix(1920 + 260, -260, k); c.strokeStyle = BLUE; c.lineWidth = 6; c.beginPath(); c.moveTo(x + 260, 0); c.lineTo(x - 260, 1080); c.stroke(); }
    if (kind === "wipeU") { const y = mix(1080, 0, k); c.fillStyle = BLUE; c.fillRect(0, y - 3, 1920, 6); }
    if (kind === "flood") { const R = Math.hypot(1920, 1080) * 1.05 * k; c.strokeStyle = BLUE; c.lineWidth = 6; c.beginPath(); c.arc(o.x || 960, o.y || 540, R, 0, Math.PI * 2); c.stroke(); }
  }
  const CHFLAT = () => DIR === "chapters";
  const useKinetic = (k) => STYLE === "kinetic" || (STYLE === "mix" && ["title", "hook", "three", "statement", "connect"].includes(k));
  const drawers = { meta: sceneMeta, title: sceneTitle, hook: sceneHook, three: sceneThree, statement: sceneStatement, parts: TERR ? sceneTerrain : VK === "grid" ? sceneGrid : sceneFabric, omninode: TERR ? sceneTerrain : sceneTracks, four: sceneBench, models: (t) => sceneTerrain(t), learn: (t) => sceneTerrain(t), pillars: (t) => sceneTerrain(t), plain: (t) => sceneBench(t), tokens: (t) => sceneBench(t), answer: (t) => sceneAnswer(t), live: sceneLive, eranos: sceneEranos, finish: sceneFinish, connect: sceneConnect };
  const ORDER = ["title", "hook", "three", "statement", "parts", "meta", "omninode", "models", "pillars", "learn", "four", "plain", "tokens", "live", "eranos", "finish", "answer", "connect"].filter((k) => CUES[k]); ORDER.sort((a, b) => S(a) - S(b));
  const scene = (k, t) => { if (useKinetic(k) && k !== "live" && k !== "eranos") kinetic(t, k); else drawers[k](t); };
  // Between acts only; inside the set the camera never moves.
  const TRANS = { meta: ["fade", 0.45], hook: ["wipeL", 0.45], three: ["wipeU", 0.4], statement: ["wipeL", 0.45], parts: ["flood", 0.55, { x: 960, y: 540 }], omninode: TERR ? null : ["wipeL", 0.5], models: null, learn: null, pillars: null, plain: null, tokens: null, answer: null, four: ["wipeU", 0.5], live: ["wipeL", 0.5], eranos: ["flood", 0.65, { x: 960, y: 620 }], connect: ["wipeU", 0.45] };
  function sceneAt(t) { let k = "title"; for (const q of ORDER) if (t >= S(q)) k = q; return k; }
  window.__beats = async () => { await tkLoad(); shotsAt(S("eranos") + 5); if (!TR) terBuild(); const out = [], Q = TR, wc = (x) => x.split(/\s+/).length; SHOTS.forEach((q, i) => out.push({ kind: "shot", label: (q.r && q.r[0].n.join("+")) || "shot " + i, s: q.s, e: q.e, words: 0 })); if (Q.TL) TLOG.forEach((x, i) => { const nx = Q.TL.at[i + 1]; out.push({ kind: "terminal line", label: x.text.slice(0, 40), s: Q.TL.at[i], e: nx === undefined ? (FEED9 ? Q.ats[Q.names.findIndex((n) => /run 1 of 6/.test(n))] : S("learn")) : nx, words: 0 }); }); const r0 = Q.names.findIndex((n) => /run 1 of 6/.test(n)); for (let i = r0; i >= 0 && i < Q.ats.length; i++) out.push({ kind: "run row", label: Q.names[i], s: Q.ats[i], e: i + 1 < Q.ats.length ? Q.ats[i + 1] : S("four"), words: wc(Q.names[i]) }); if (CUES.three && WORLD) { const a = S("three"), b = M("three", "rewrites") - 0.1, d = M("three", "trouble") - 0.25, e = E("three"); out.push({ kind: "text", label: "It doesn't know what's new.", s: a, e: b, words: 5 }, { kind: "text", label: "It rewrites code that already exists.", s: b, e: d, words: 6 }, { kind: "text", label: "And it has trouble with long-horizon tasks.", s: d, e, words: 7 }); } if (CUES.statement) out.push({ kind: "text", label: "Bigger models alone won't fix this.", s: S("statement"), e: E("statement"), words: CUES.statement.words.length }); BENCH.forEach((b, i) => { out.push({ kind: "number card", label: b.big, s: i === 0 ? S("four") + 0.5 : b.at() - 0.35, e: E("four"), words: wc(b.big + " " + b.txt) }); }); if (MAINF) out.push({ kind: "text", label: "Tell your agent to read", s: S("answer") + 0.6, e: E("connect"), words: 11 }); if (CUES.live) out.push({ kind: "text", label: "This is running right now.", s: S("live"), e: (CUES.live.words.some((q) => q[0] === "These") ? M("live", "These") : S("live") + 2.2) - 0.2, words: 5 }); return { total: E("connect"), last: CUES.connect.words[CUES.connect.words.length - 1][2], beats: out.map((q) => ({ ...q, s: +q.s.toFixed(2), e: +q.e.toFixed(2), d: +(q.e - q.s).toFixed(2) })) }; };
  if (CUES.meta) { TRANS.models = ["fade", 0.45]; TRANS.omninode = ["fade", 0.45]; }
  window.renderAt = (t) => { ONT = [];
    t = Math.max(0, Math.min(window.DUR - 1 / 60, t));
    if (DIR === "chapters") GROUND = CHAPTER[sceneAt(t)] || GROUND;
    c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.textAlign = "left"; c.textBaseline = "alphabetic"; c.setLineDash([]);
    const k = sceneAt(t), tr = MO.cut && ["omninode", "four"].includes(k) ? null : TRANS[k], i = ORDER.indexOf(k);
    if (WORLD && tr && t < S(k) + 0.45 && i > 0) { if (!window.__DS) { window.__DS = document.createElement("canvas"); window.__DS.width = cv.width; window.__DS.height = cv.height; } const g9 = window.__DS.getContext("2d"); scene(ORDER[i - 1], S(k) - 1 / 30); c.globalAlpha = 1; g9.setTransform(1, 0, 0, 1, 0, 0); g9.drawImage(cv, 0, 0); const f9 = (t - S(k)) / 0.45; if (MAINF) { if (f9 >= 0.5) scene(k, t); c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1 - Math.abs(f9 * 2 - 1); c.fillStyle = GROUND; c.fillRect(0, 0, cv.width, cv.height); c.restore(); c.globalAlpha = 1; } else { scene(k, t); c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1 - inOut(f9); c.drawImage(window.__DS, 0, 0); c.restore(); c.globalAlpha = 1; } } else if (tr && t < S(k) + tr[1] && i > 0) { if (CLIP) { c.fillStyle = PAPER; c.fillRect(0, 0, 1920, 1080); } else scene(ORDER[i - 1], S(k) - 1 / 30); c.globalAlpha = 1; reveal(V.trans || tr[0], inOut((t - S(k)) / tr[1]), () => scene(k, t), tr[2]); }
    else scene(k, t);
    c.globalAlpha = 1; hackathon(t); caption(t);
  };
  // Composition measure at one moment: draws the frame whole, each part alone, and the frame without each part, then compares pixels.
  window.__compSkip = (t) => t >= S("split") && t < B.sSplits + 1.3;
  window.__compSample = (t) => {
    const W = 480, H = 270, sm = document.createElement("canvas"); sm.width = W; sm.height = H; const g = sm.getContext("2d", { willReadFrequently: true });
    const grab = () => { g.drawImage(cv, 0, 0, W, H); return g.getImageData(0, 0, W, H).data; };
    const diff = (a, b) => { const m = new Uint8Array(W * H); for (let i = 0, j = 0; j < m.length; i += 4, j++) if (Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]) > 8) m[j] = 1; return m; };
    const C = (window.__CMP = { seen: {} }); renderAt(t); const full = grab().slice(), seen = { ...C.seen };
    C.only = "__none__"; renderAt(t); const none = grab().slice();
    const parts = [];
    for (const [id, kind] of Object.entries(seen)) {
      C.only = id; C.skip = undefined; renderAt(t); const mask = diff(grab(), none);
      C.only = undefined; C.skip = undefined; C.tint = id; renderAt(t); const vis = diff(grab(), full); C.tint = undefined;
      let area = 0, shown = 0, x0 = W, x1 = -1, y0 = H, y1 = -1, sx = 0, sy = 0; for (let j = 0; j < mask.length; j++) if (mask[j]) { area++; if (vis[j]) shown++; const x = j % W, y = (j / W) | 0; sx += x; sy += y; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
      if (area) parts.push({ id, kind, area, shown, box: [x0, y0, x1, y1], cx: sx / area, cy: sy / area, mask });
    }
    window.__CMP = null; window.__termChk = {}; window.__capSkip = null; renderAt(t); const ontNow = ONT.slice(), capNow = (typeof CAPTIONS !== "undefined" && CAPS) ? (CAPTIONS.find((q) => t >= q[1] && t < q[2]) || [null])[0] : null;
    const out = { t, term: window.__termChk, dup: capNow && window.__capSkip !== capNow && dupOf(capNow) ? capNow : null, parts: parts.map(({ mask, ...r }) => r), over: [] }, labs = parts.filter((q) => q.kind === "label" || q.kind === "heading" || q.kind === "name" || q.kind === "caption"), solid = parts.filter((q) => q.kind === "component" || q.kind === "panel" || q.kind === "label" || q.kind === "heading" || q.kind === "caption");
    for (const L of labs) for (const X of solid) { if (L === X) continue; let n = 0; for (let j = 0; j < L.mask.length; j++) if (L.mask[j] && X.mask[j]) n++; if (n / L.area > 0.04) out.over.push([L.id, X.id, +(n / L.area).toFixed(3)]); }
    out.trafficFabric = 0; for (const T of parts.filter((q) => q.kind === "traffic")) { const ov = (X) => { let n = 0; for (let j = 0; j < T.mask.length; j++) if (T.mask[j] && X.mask[j]) n++; return n / (T.area || 1); }; for (const X of labs) { const k = ov(X); if (k > 0.04) out.over.push([T.id, X.id, +k.toFixed(3)]); } for (const X of parts) if (X.id === "skyline") out.trafficFabric = Math.max(out.trafficFabric, +ov(X).toFixed(3)); }
    const GW = 48, GH = 27, occ = new Uint8Array(GW * GH), thick = parts.filter((q) => q.kind !== "ground" && q.kind !== "caption"); for (const q of thick) for (let j = 0; j < q.mask.length; j++) if (q.mask[j]) occ[(((j / W) | 0) * GH / H | 0) * GW + ((j % W) * GW / W | 0)] = 1;
    out.occ = Array.from(occ).join(""); return out;
  };
  // ------------------------------------------------------------ setup and live playback
  plan(); PANELS = panels(); births();
  for (const k of ORDER) { const out = []; let cur = []; for (const w of CUES[k].words) { cur.push(w); if (/[.?!]$/.test(w[0]) || (/[:]$/.test(w[0]))) { out.push(cur); cur = []; } } if (cur.length) out.push(cur); SENTS[k] = out; }
  window.OVERLAP_OK = [];
  const audio = document.getElementById("a");
  if (qs.get("still") === null && audio) {
    // Live playback in a browser. The audio is the clock; if it cannot play, a plain clock takes over so the film still runs, silently. Before the first play it shows a real frame and a Play button.
    let silent = false, playing = false, clockT = 0, last = null, started = false, stallA = -1, stallT = null;
    const now_t = () => (silent ? clockT : audio.currentTime || 0);
    const chrome = (t) => { const on = !playing, W = 1920, y = 1068; c.fillStyle = "rgba(17,22,31,.14)"; c.fillRect(0, y, W, 6); c.fillStyle = "#24519B"; c.fillRect(0, y, (W * Math.min(t, 180)) / 180, 6); if (!on) return; c.save();  c.beginPath(); c.arc(960, 800, 74, 0, Math.PI * 2); c.fillStyle = "#11161F"; c.fill(); c.beginPath(); c.moveTo(936, 760); c.lineTo(936, 840); c.lineTo(1004, 800); c.closePath(); c.fillStyle = "#FFFDF8"; c.fill(); font(700, 40); c.fillStyle = "#11161F"; c.textAlign = "center"; c.fillText(started ? "Paused. Click to go on." : "Click to play. 3 minutes, with sound.", 960, 925); c.textAlign = "left"; c.restore(); };
    const tick = (now) => { if (window.__render) return; if (playing && !silent) { const at = audio.currentTime || 0; if (at !== stallA) { stallA = at; stallT = now; } else if (stallT !== null && now - stallT > 1200) { try { audio.pause(); } catch (e) {} goSilent(); } else if (stallT === null) stallT = now; } if (silent && playing && last !== null) clockT += (now - last) / 1000; last = now; const t = now_t(); renderAt(!started ? Math.max(t, 5) : t); chrome(t); if (t >= 180) playing = false; requestAnimationFrame(tick); };
    window.READY.then(() => { requestAnimationFrame(tick); });
    const goSilent = () => { silent = true; clockT = audio.currentTime || 0; playing = true; };
    audio.addEventListener("error", () => { if (playing) goSilent(); });
    const toggle = () => { started = true; if (silent) { playing = !playing; return; } if (audio.paused) { playing = true; const r = audio.play(); if (r && r.catch) r.catch(goSilent); } else { audio.pause(); playing = false; } };
    cv.addEventListener("click", toggle); document.addEventListener("keydown", (e) => { if (e.code === "Space") { e.preventDefault(); toggle(); } if (e.code === "ArrowRight" || e.code === "ArrowLeft") { const d = e.code === "ArrowRight" ? 10 : -10; if (silent) clockT = Math.max(0, clockT + d); else audio.currentTime = Math.max(0, audio.currentTime + d); } });
  }
})();
