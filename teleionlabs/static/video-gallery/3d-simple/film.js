// The simple 3D home film: reads the article under it for every sentence, draws them over the 3D set in world.js.
// Without WebGL, or with reduced motion, it shows still pictures of the same scenes and the same words.
(() => {
  const cv = document.getElementById("film"), art = document.getElementById("text"), bar = document.getElementById("film-controls");
  if (!cv || !art || !bar || !cv.getContext) return;
  const BASE = new URL(".", document.currentScript.src).href;
  const words = JSON.parse(document.getElementById("film-words").textContent);
  const LW = words.simple;
  const c = cv.getContext("2d");
  cv.hidden = false; bar.hidden = false;
  const INK = "#11161F", MUTED = "#565A5F", SOFT = "#2F343A", BLUE = "#24519B", RUST = "#A23E1C", PAPER = "#F5F2EA", CARD = "#FFFDF8", LINE = "#D8D1C1";
  const FONT = "ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace";
  const query = new URLSearchParams(location.search);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const DEBUG = query.has("debug"), NOWORDS = query.has("nowords"), FORCE_STILLS = query.has("stills");
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const land = (x) => { x = clamp(x); return 1 - Math.pow(1 - x, 3); };

  // Words: runs of text with their color, read from the article. Nothing is typed here.
  const runs = (el) => [...el.childNodes].map((n) => ({ t: (n.textContent || "").replace(/\s+/g, " "), c: n.getAttribute ? n.getAttribute("data-c") : null })).filter((r) => r.t);
  const scenes = [...art.querySelectorAll("[data-scene]")].map((s) => ({
    kind: s.dataset.scene, secs: Number(s.dataset.seconds) || 5, h: runs(s.querySelector("h2")),
    ps: [...s.querySelectorAll("p")].map(runs), steps: [...s.querySelectorAll("li")].map(runs),
  }));
  let at = 0; scenes.forEach((s) => { s.start = at; at += s.secs; });
  const total = at, by = Object.fromEntries(scenes.map((s) => [s.kind, s]));
  // Split runs into sentences, keeping colors.
  function sentences(rs) {
    const out = []; let cur = [];
    rs.forEach((r) => {
      const parts = r.t.split(/(?<=[.?!])\s+/);
      parts.forEach((p, i) => { if (p) cur.push({ t: p, c: r.c }); if (i < parts.length - 1) { out.push(cur); cur = []; } });
    });
    if (cur.length) out.push(cur);
    return out;
  }
  const plain = (rs) => rs.map((r) => r.t).join("");
  const S = by;
  const li2 = sentences(S.parts.steps[2]), om = sentences(S.omninode.ps[0]);
  // Times are the voice's own marks, in film seconds. "main" is large, "cap" is the reading line.
  const stage = [
    { from: 0, to: 6.85, main: S.title.h, cap: S.title.ps[0], capFrom: 2.83 },
    { from: 7.25, to: 11.85, main: S.hook.h, cap: S.hook.ps[0], capFrom: 8.42, holdColor: { "dumb.": 9.76 } },
    { from: 12.25, to: 14.4, main: S.three.h },
    { from: 14.48, to: 15.94, big: S.three.ps[0] }, { from: 16.01, to: 18.54, big: S.three.ps[1] }, { from: 18.61, to: 21.85, big: S.three.ps[2] },
    { from: 22.25, to: 27.85, main: S.statement.h, cap: S.statement.ps[0], capFrom: 24.4 },
    { from: 28.24, to: 31.06, main: S.parts.h },
    { from: 31.14, to: 38.86, read: S.parts.steps[0], bold: ":" }, { from: 38.94, to: 50.22, read: S.parts.steps[1], bold: ":" },
    { from: 50.3, to: 61.5, read: li2[0], bold: ":" }, { from: 61.57, to: 67.38, read: li2[1] }, { from: 67.45, to: 70.85, read: om[1] },
    { from: 71.25, to: 74.08, main: S.split.h },
    { from: 74.16, to: 78.02, read: S.split.steps[0] }, { from: 78.09, to: 80.24, read: S.split.steps[1] }, { from: 80.31, to: 84.52, read: S.split.steps[2] },
    { from: 84.59, to: 87.03, read: S.split.steps[3] }, { from: 87.1, to: 90.85, read: S.split.steps[4] },
    { from: 91.25, to: 94.58, main: S.omninode.h },
    { from: 94.64, to: 98.11, read: om[0] },
    { from: 98.18, to: 101.28, read: S.omninode.steps[0], bold: ":" }, { from: 101.35, to: 104.46, read: S.omninode.steps[1], bold: ":" },
    { from: 104.53, to: 108.15, read: S.omninode.steps[2], bold: ":" }, { from: 108.22, to: 112.85, read: S.omninode.steps[3], bold: ":" },
    { from: 113.25, to: 114.62, main: S.four.h },
    { from: 114.7, to: 116.2, read: S.four.ps[0], bold: "." }, { from: 116.28, to: 120.05, read: S.four.ps[1], bold: "." }, { from: 120.12, to: 121.98, read: S.four.ps[2], bold: "." }, { from: 122.05, to: 134.85, read: S.four.ps[3], bold: "." },
    { from: 135.25, to: 137.05, main: S.live.h },
    { from: 137.12, to: 146.25, live: true },
    { from: 147.24, to: 154.99, read: S.eranos.h, roomy: true },
    { from: 155.06, to: 157.58, big: S.eranos.ps[0] }, { from: 157.65, to: 163.77, read: S.eranos.ps[1] }, { from: 163.84, to: 166.57, read: S.eranos.ps[2] },
    { from: 166.64, to: 169.59, big: [{ t: LW.help, c: null }] }, { from: 169.66, to: 176.1, big: S.eranos.ps[3] },
    { from: 177.23, to: 180.5, main: S.connect.h, cap: S.connect.ps[0], capFrom: 177.9 },
  ];

  // Live data, the same public aggregate as the home film. Never a placeholder: if it fails, the words say so.
  const live = { net: null, failed: false };
  const usable = (d) => d && d.available !== false && d.totals && typeof d.totals.workers === "number";
  const failLive = query.has("nolive");
  (failLive ? Promise.reject() : fetch("/api/network").then((r) => (r.ok ? r.json() : Promise.reject())))
    .then((d) => { if (usable(d)) live.net = d; else live.failed = true; }).catch(() => { live.failed = true; });
  const cleanClaim = (r) => r.title && !/[_{}]|tessera|herma/i.test(r.title);

  const F = { t: 0, last: 0, playing: !reduced && !query.has("paused"), held: false, idx: -1, now: 0 };
  const [btnBack, btnToggle, btnNext] = ["back", "pause", "next"].map((k) => bar.querySelector(`[data-film="${k}"]`));
  const posEl = document.getElementById("film-pos");

  // Text helpers. Every drawn line is recorded when debugging, so overlaps can be tested.
  let boxes = [];
  function setFont(size, weight) { c.font = `${weight || 400} ${size}px ${FONT}`; }
  function wrapRuns(rs, maxW, size, weight, boldUntil) {
    const toks = [];
    let charPos = 0;
    rs.forEach((r) => r.t.split(/(\s+)/).forEach((w) => { if (w) { toks.push({ w, c: r.c, b: boldUntil !== null && charPos < boldUntil }); charPos += w.length; } }));
    const lines = []; let line = [], lw = 0;
    const m = (t, b) => { setFont(size, b ? 700 : weight); return c.measureText(t).width; };
    toks.forEach((t) => {
      const w = m(t.w, t.b);
      if (/^\s+$/.test(t.w)) { if (line.length) { line.push({ ...t, tw: w }); lw += w; } return; }
      if (lw + w > maxW && line.length) { while (line.length && /^\s+$/.test(line[line.length - 1].w)) { lw -= line[line.length - 1].tw; line.pop(); } lines.push({ toks: line, w: lw }); line = []; lw = 0; }
      line.push({ ...t, tw: w }); lw += w;
    });
    if (line.length) lines.push({ toks: line, w: lw });
    return lines;
  }
  function drawLines(lines, cx, y, size, weight, color, alpha, lh, tNow, holdColor) {
    const base = c.globalAlpha;
    c.textBaseline = "alphabetic"; c.textAlign = "left";
    lines.forEach((ln, i) => {
      let x = cx - ln.w / 2; const yy = y + i * lh;
      ln.toks.forEach((t) => {
        if (!/^\s+$/.test(t.w)) {
          setFont(size, t.b ? 700 : weight);
          let col = t.c === "blue" ? BLUE : t.c === "rust" ? RUST : color;
          if (holdColor && holdColor[t.w] !== undefined && tNow < holdColor[t.w]) col = color;
          c.fillStyle = col; c.globalAlpha = base * alpha; c.fillText(t.w, x, yy);
        }
        x += t.tw;
      });
      if (DEBUG) boxes.push({ s: ln.toks.map((q) => q.w).join(""), x: cx - ln.w / 2, y: yy - size, w: ln.w, h: size * 1.25, kind: "text" });
    });
    c.globalAlpha = base;
  }
  // Rise on arrival, quick fade on the way out. Never typed; words hold still while being read.
  const arrive = (t, from, to) => ({ a: clamp((t - from) / 0.22) * clamp((to - t) / 0.14), dy: (1 - land((t - from) / 0.4)) * 16 });

  function drawStage(v) {
    const { W, H, t, band } = v, tall = v.tall, cur = stage.find((b) => t >= b.from && t < b.to);
    if (!cur) return;
    const u = Math.min(W / 1280, H / 700), mainS = tall ? 24 : Math.max(26, 44 * u), capS = tall ? 16 : Math.max(17, 25 * u), readS = tall ? 15.5 : Math.max(16, 25 * u), bigS = tall ? 21 : Math.max(22, 36 * u);
    const maxW = Math.min(W - (tall ? 28 : 120), tall ? 999 : 1120), cx = W / 2;
    const first = t === 0 ? { a: 1, dy: 0 } : null;
    if (cur.live) return drawLive(v, cur, cx, maxW, readS);
    const bits = [];
    const add = (rs, size, weight, color, from, hold, boldCh) => {
      let boldUntil = null;
      if (boldCh) { const p = plain(rs), i = p.indexOf(boldCh); if (i >= 0) boldUntil = i + 1; }
      bits.push({ lines: wrapRuns(rs, maxW, size, weight, boldUntil), size, weight, color, from, hold, lh: size * 1.32 });
    };
    if (cur.main) add(cur.main, mainS, 700, INK, cur.from);
    if (cur.cap) add(cur.cap, capS, 400, SOFT, cur.capFrom);
    if (cur.big) add(cur.big, bigS, 700, INK, cur.from);
    if (cur.read) add(cur.read, cur.roomy ? Math.max(readS, tall ? 15.5 : 27 * u) : readS, cur.roomy ? 700 : 400, INK, cur.from, null, cur.bold);
    // The block is centered in the band and does not jump when a second line arrives.
    let hTot = 0; bits.forEach((b, i) => { hTot += b.lines.length * b.lh + (i ? 12 : 0); });
    let y = Math.max(8, (band - hTot) / 2) + (bits[0] ? bits[0].size * 0.95 : 0);
    bits.forEach((b, i) => {
      if (i) y += 12 - b.size * 0.3 + bits[i - 1].size * 0.0;
      const ar = t < 0.01 ? { a: 1, dy: 0 } : arrive(t, b.from, cur.to);
      if (t >= b.from) { c.save(); c.translate(0, ar.dy); drawLines(b.lines, cx, y, b.size, b.weight, b.color, ar.a, b.lh, t, cur.holdColor); c.restore(); }
      y += b.lines.length * b.lh;
    });
  }
  function drawLive(v, cur, cx, maxW, readS) {
    const { W, H, t, band, tall } = v, n = live.net, ar = arrive(t, cur.from, cur.to);
    c.save(); c.translate(0, ar.dy);
    if (!n) {
      const msg = live.failed ? words.live_none : "";
      const lines = wrapRuns([{ t: msg, c: null }], maxW, readS + 2, 400, null);
      drawLines(lines, cx, band * 0.5, readS + 2, 400, SOFT, ar.a, (readS + 2) * 1.3);
    } else {
      const tt = n.totals, items = [[tt.workers, words.live_workers], [tt.data_centres, words.live_places], [tt.claims, words.live_claims]];
      const cols = tall ? W / 3 : Math.min(300, W / 3), numS = tall ? 32 : Math.max(32, 52 * Math.min(W / 1280, H / 700)), labS = tall ? 12 : Math.max(14, 17 * Math.min(W / 1280, H / 700));
      items.forEach(([val, label], i) => {
        const x = cx + (i - 1) * cols, count = Math.round((val || 0) * land((t - cur.from - i * 0.2) / 1.2));
        drawLines(wrapRuns([{ t: String(count), c: null }], cols, numS, 700, null), x, band * (tall ? 0.28 : 0.36), numS, 700, BLUE, ar.a, numS);
        drawLines(wrapRuns([{ t: label, c: null }], cols - 8, labS, 400, null), x, band * (tall ? 0.28 : 0.36) + labS * 1.75, labS, 400, SOFT, ar.a, labS * 1.2);
      });
      const claims = (n.recent_claims || []).filter(cleanClaim);
      if (claims.length && t >= 138.73) {
        const i = Math.floor((t - 138.73) / 2.1) % claims.length, r = claims[i], via = r.via && (r.via.city || r.via.continent);
        const meta = [r.model && r.model.name, via].filter(Boolean).join(" · "), s = tall ? 12.5 : Math.max(13, 15 * Math.min(W / 1280, H / 700));
        setFont(s, 400);
        let title = r.title; const room = W - (tall ? 24 : 120);
        while (c.measureText(title + "…").width > room && title.length > 8) title = title.slice(0, -2);
        if (title !== r.title) title = title.trimEnd() + "…";
        const fade = clamp((((t - 138.73) % 2.1)) / 0.2);
        const yb = H - (tall ? 28 : 28);
        drawLines(wrapRuns([{ t: title, c: null }], room + 8, s, 400, null), cx, yb, s, 400, SOFT, ar.a * fade, s * 1.2);
        drawLines(wrapRuns([{ t: meta, c: null }], room, s, 400, null), cx, yb + s * 1.35, s, 400, MUTED, ar.a * fade, s * 1.2);
      }
      const p = sentences(S.live.ps[0]), line = p[1] || S.live.ps[0];
      if (!tall || true) drawLines(wrapRuns(line, maxW, tall ? 12.5 : Math.max(13, 16 * Math.min(W / 1280, H / 700)), 400, null), cx, band * (tall ? 0.74 : 0.86), tall ? 12.5 : Math.max(13, 16 * Math.min(W / 1280, H / 700)), 400, MUTED, ar.a, 16);
    }
    c.restore();
  }

  function pill(v, r, placed) {
    const small = v.tall, size = small ? 12.5 : Math.max(14, 17 * Math.min(v.W / 1280, v.H / 700));
    setFont(size, 700);
    const w1 = c.measureText(r.text).width; setFont(size * 0.9, 400);
    const w2 = r.sub ? c.measureText(r.sub).width : 0;
    const pad = size * 0.75, w = Math.max(w1, w2) + pad * 2, h = (r.sub ? size * 2.5 : size * 1.5) + pad * 0.5;
    let x = Math.max(8, Math.min(v.W - w - 8, r.x - w / 2)), y = r.y - h - 6;
    y = Math.max(v.band + 2, y);
    // Stay clear of anything already placed: move up, then down.
    for (let n = 0; n < 8; n++) {
      const hit = placed.find((q) => x < q.x + q.w + 4 && x + w > q.x - 4 && y < q.y + q.h + 3 && y + h > q.y - 3);
      if (!hit) break;
      const up = hit.y - h - 5;
      y = up >= v.band + 2 ? up : hit.y + hit.h + 5;
    }
    c.globalAlpha = r.alpha;
    c.fillStyle = CARD; c.strokeStyle = r.accent || LINE; c.lineWidth = 1.5;
    c.beginPath(); c.roundRect(x, y, w, h, 7); c.fill(); c.stroke();
    c.textAlign = "center"; c.textBaseline = "alphabetic";
    setFont(size, 700); c.fillStyle = r.accent || INK; c.fillText(r.text, x + w / 2, y + pad * 0.25 + size * 1.08);
    if (r.sub) { setFont(size * 0.9, 400); c.fillStyle = SOFT; c.fillText(r.sub, x + w / 2, y + pad * 0.25 + size * 2.25); }
    c.textAlign = "left"; c.globalAlpha = 1;
    const box = { x, y, w, h, s: r.text, kind: "pill" };
    placed.push(box); if (DEBUG) boxes.push(box);
  }
  function label(v, r, placed) {
    if (r.x < 0 || r.x > v.W || r.y > v.H - 34 || r.y < v.band * 0.6) return;
    if (r.kind === "digit") {
      setFont(v.tall ? 12 : Math.max(13, 17 * Math.min(v.W / 1280, v.H / 700)), 700); c.textAlign = "center"; c.textBaseline = "middle";
      c.globalAlpha = clamp(r.alpha); c.fillStyle = r.done ? CARD : INK; c.fillText(r.text, r.x, r.y); c.textBaseline = "alphabetic"; c.textAlign = "left"; c.globalAlpha = 1;
      return;
    }
    const u = Math.min(v.W / 1280, v.H / 700), small = v.tall;
    const base = small ? 13.5 : Math.max(16, 23 * u), size = base * (r.small ? (small ? 0.86 : 0.76) : 1) * (1 + (small ? 0.12 : 0.26) * clamp(r.focus || 0));
    const a = clamp(r.alpha) * (1 - 0.62 * clamp(r.dim || 0));
    setFont(size, 700); c.textAlign = "center"; c.textBaseline = "alphabetic";
    // On a phone a long name takes two lines, so two neighbors never touch.
    if (small && !r.left && r.place === "above" && c.measureText(r.text).width > v.W * (r.small ? 0.24 : 0.36)) {
      const lines = wrapRuns([{ t: r.text, c: null }], v.W * (r.small ? 0.24 : 0.38), size, 700, null), lh = size * 1.24;
      lines.forEach((ln, i) => { const txt = ln.toks.map((q) => q.w).join(""), yy = r.y - 6 - (lines.length - 1 - i) * lh; c.globalAlpha = a; c.fillStyle = INK; c.fillText(txt, r.x, yy); if (DEBUG) boxes.push({ s: txt, x: r.x - ln.w / 2, y: yy - size, w: ln.w, h: size * 1.2, kind: "label" }); placed.push({ x: r.x - ln.w / 2, y: yy - size, w: ln.w, h: size * 1.2 }); });
      if (r.on > 0) { const w0 = Math.max(...lines.map((l) => l.w)); c.globalAlpha = a * clamp(r.on); c.fillStyle = r.color || BLUE; c.fillRect(r.x - w0 / 2, r.y - 6 + size * 0.24, w0, 2); }
      c.textAlign = "left"; c.globalAlpha = 1;
      return;
    }
    const w = c.measureText(r.text).width;
    const x = r.left ? r.x + w / 2 : Math.max(w / 2 + 6, Math.min(v.W - w / 2 - 6, r.x));
    const y = r.place === "below" ? r.y + size + 3 : r.y - 6;
    c.globalAlpha = a; c.fillStyle = INK; c.fillText(r.text, x, y);
    if (r.on > 0) { c.globalAlpha = a * clamp(r.on); c.fillStyle = r.color || BLUE; c.fillRect(x - w / 2, y + size * 0.24, w, Math.max(2, size * 0.13)); }
    if (DEBUG) boxes.push({ s: r.text, x: x - w / 2, y: y - size, w, h: size * 1.3, kind: "label" });
    placed.push({ x: x - w / 2, y: y - size, w, h: size * 1.3 });
    if (r.sub) {
      const s2 = small ? 11.5 : Math.max(13, 15.5 * u); setFont(s2, 400);
      const lines = wrapRuns([{ t: r.sub, c: null }], v.W * (small ? 0.74 : 0.34), s2, 400, null);
      c.textAlign = "center"; c.fillStyle = SOFT; c.globalAlpha = a;
      lines.forEach((ln, i) => c.fillText(ln.toks.map((q) => q.w).join(""), x, y + size * 0.42 + s2 * (1.1 + i * 1.2)));
      const wmax = Math.max(...lines.map((l) => l.w));
      if (DEBUG) boxes.push({ s: r.sub, x: x - wmax / 2, y: y + size * 0.42, w: wmax, h: s2 * 1.25 * lines.length, kind: "label" });
      placed.push({ x: x - wmax / 2, y: y + size * 0.42, w: wmax, h: s2 * 1.25 * lines.length });
    }
    c.textAlign = "left"; c.globalAlpha = 1;
  }

  // Stills for no WebGL or reduced motion: real frames of this film, captured without words.
  const STILLS = [3, 10.5, 15.4, 17.8, 20.4, 23.8, 29.5, 36.8, 42, 49.8, 54.8, 65.2, 69, 75.8, 79.6, 81.5, 85.8, 89.6, 96, 100, 103, 106.8, 110.9, 116, 118.2, 121.5, 128, 144, 151, 156, 159, 162, 165, 168, 172, 179.2];
  const stillImgs = {};
  const useStills = () => !world;
  function drawStill(v) {
    const { W, H, t, tall } = v;
    let i = 0; STILLS.forEach((s, k) => { const end = k < STILLS.length - 1 ? (s + STILLS[k + 1]) / 2 : 999; if (t >= (k ? (STILLS[k - 1] + s) / 2 : 0) && t < end) i = k; });
    const key = `${tall ? "t" : "w"}${i}`;
    if (!stillImgs[key]) { const im = new Image(); im.src = `${BASE}stills/${tall ? "tall" : "wide"}-${String(i).padStart(2, "0")}.webp`; stillImgs[key] = im; }
    const im = stillImgs[key];
    c.fillStyle = PAPER; c.fillRect(0, 0, W, H);
    if (im.complete && im.naturalWidth) {
      const k = Math.max(W / im.naturalWidth, H / im.naturalHeight), iw = im.naturalWidth * k, ih = im.naturalHeight * k;
      c.drawImage(im, (W - iw) / 2, H - ih, iw, ih);
    }
  }

  let world = null, worldFailed = false, onScreen = true;
  if ("IntersectionObserver" in window) new IntersectionObserver((e) => { onScreen = e[e.length - 1].isIntersecting; }).observe(cv);
  const glOK = () => { try { return !!document.createElement("canvas").getContext("webgl2"); } catch (e) { return false; } };
  if (!reduced && !FORCE_STILLS && glOK()) {
    import(`${BASE}world.js`).then((m) => {
      world = m.create({ words, base: BASE, pages: LW.pages });
      cv.filmWorld = world;
    }).catch(() => { worldFailed = true; world = null; });
  }

  // Quality follows the machine: fewer pixels if frames run long.
  let pr = Math.min(devicePixelRatio || 1, 1.75), slow = 0, fast = 0;
  function frame(now) {
    F.now = now;
    const dt = F.last ? Math.min(0.1, (now - F.last) / 1000) : 0;
    F.last = now;
    if (!onScreen && !F.held) { requestAnimationFrame(frame); return; }
    if (F.playing) {
      // The voice leads while it is really moving. If it stalls, the film keeps going on its own clock.
      const vt = voice && !voice.paused && !voice.seeking ? voice.currentTime : -1;
      F.t += dt;
      if (vt >= 0 && vt !== F.vLast) {
        const err = vt - F.t; F.vLast = vt;
        if (Math.abs(err) < 3) F.t = Math.abs(err) > 0.4 ? vt : F.t + err * 0.15;
      }
      if (F.t >= total) { F.t = total; F.playing = false; label2(); }
    }
    if (!query.has("noadapt")) { if (dt > 0.042 && F.playing) { slow++; fast = 0; } else if (dt > 0 && dt < 0.02) { fast++; slow = 0; } if (slow > 45 && pr > 0.8) { pr = Math.max(0.8, pr * 0.82); slow = 0; } }
    let idx = scenes.length - 1;
    for (let i = 0; i < scenes.length; i++) if (F.t < scenes[i].start + scenes[i].secs) { idx = i; break; }
    if (idx !== F.idx) { F.idx = idx; label2(); }
    const W = cv.clientWidth, H = cv.clientHeight;
    if (W && H) {
      const dpr = Math.min(devicePixelRatio || 1, 2), pw = Math.round(W * dpr), ph = Math.round(H * dpr);
      if (cv.width !== pw || cv.height !== ph) { cv.width = pw; cv.height = ph; }
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.globalAlpha = 1; c.fillStyle = PAPER; c.fillRect(0, 0, W, H);
      const tall = W / H < 1.05, v = { W, H, t: F.t, tall, band: H * (tall ? 0.3 : 0.215) };
      boxes = [];
      const placed = [];
      if (world && world.alive) {
        const gl = world.draw(F.t, W, H, pr);
        if (gl) c.drawImage(gl, 0, 0, W, H);
        const recs = world.labels(F.t);
        recs.filter((r) => r.kind !== "pill").forEach((r) => label(v, r, placed));
        recs.filter((r) => r.kind === "pill").forEach((r) => pill(v, r, placed));
      } else drawStill(v);
      if (!NOWORDS) drawStage(v);
      c.fillStyle = INK; c.fillRect(0, H - 2, W * (F.t / total), 2);
      if (DEBUG) cv.filmDebug = { t: F.t, boxes, calls: world ? world.calls : 0, world: !!world, W, H, band: v.band, pr };
    }
    requestAnimationFrame(frame);
  }
  function label2() {
    btnToggle.textContent = F.t >= total ? words.replay : F.playing ? words.pause : words.play;
    posEl.textContent = words.scene.replace("{n}", F.idx + 1).replace("{total}", scenes.length);
  }
  cv.addEventListener("film-seek", (e) => { F.t = Math.max(0, Math.min(total, e.detail)); F.playing = false; F.held = true; F.idx = -1; label2(); syncVoice(true); });
  // Back and Next go by scene; without motion they go by line, so every line can be read at rest.
  const beats = stage.map((b) => b.capFrom !== undefined ? b.capFrom + 0.4 : b.from + 0.4);
  const go = (d) => {
    if (reduced || !world) {
      const cur = beats.findIndex((b) => b > F.t + 0.01), i = Math.max(0, Math.min(beats.length - 1, (cur < 0 ? beats.length : cur) - 1 + d));
      F.t = beats[i]; F.idx = -1;
    } else {
      const i = Math.max(0, Math.min(scenes.length - 1, F.idx + d)); F.t = scenes[i].start + (i ? 0.0 : 0); F.idx = -1;
    }
    syncVoice(true);
  };
  btnBack.addEventListener("click", () => go(-1));
  btnNext.addEventListener("click", () => go(1));
  btnToggle.addEventListener("click", () => { if (F.t >= total) F.t = 0; F.playing = !F.playing; F.held = false; label2(); syncVoice(true); });
  // Browsers allow sound only after a click. While the voice plays, its clock is the film's clock.
  const btnSound = bar.querySelector('[data-film="sound"]');
  let voice = null;
  function syncVoice(force) {
    if (!voice) return;
    if (F.playing) { if (force || (Math.abs(voice.currentTime - F.t) > 0.35 && voice.readyState > 2 && !voice.seeking && performance.now() - (F.vSeek || 0) > 2000)) { F.vSeek = performance.now(); voice.currentTime = F.t; } if (voice.paused) voice.play().catch(() => {}); }
    else if (!voice.paused) voice.pause();
  }
  if (btnSound && btnSound.dataset.src) btnSound.addEventListener("click", () => {
    if (voice) { voice.pause(); voice = null; btnSound.textContent = words.sound_on; return; }
    voice = new Audio(btnSound.dataset.src); voice.preload = "auto";
    if (!F.playing && F.t < total) { F.playing = true; F.held = false; label2(); }
    btnSound.textContent = words.sound_off; syncVoice(true);
    cv.filmVoice = voice;
  });
  setInterval(() => syncVoice(false), 500);
  cv.filmState = F;
  label2();
  requestAnimationFrame(frame);
})();
