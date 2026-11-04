// The home film: draws the text of this page on a canvas, plus live numbers from /api/network. Every word comes from
// the article under it (edit the text, the film changes). No text here except what the page gives it in film-words.
(() => {
  const cv = document.getElementById("film");
  const art = document.getElementById("text");
  const bar = document.getElementById("film-controls");
  if (!cv || !art || !bar || !cv.getContext) return;
  const words = JSON.parse(document.getElementById("film-words").textContent);
  const c = cv.getContext("2d");
  cv.hidden = false;
  bar.hidden = false;
  const INK = "#11161F", MUTED = "#565A5F", SOFT = "#2F343A", BLUE = "#24519B", RUST = "#A23E1C", PAPER = "#F5F2EA", CARD = "#FFFDF8", RULE = "#8A8476", LINE = "#E2DCCF";
  const FONT = "ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const ease = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
  const colour = (n) => (n === "blue" ? BLUE : n === "rust" ? RUST : null);
  const runs = (el) => [...el.childNodes].map((n) => ({ t: (n.textContent || "").replace(/\s+/g, " "), c: n.getAttribute ? n.getAttribute("data-c") : null })).filter((r) => r.t);
  const scenes = [...art.querySelectorAll("[data-scene]")].map((s) => ({
    kind: s.dataset.scene, secs: Number(s.dataset.seconds) || 5, h: runs(s.querySelector("h2")),
    ps: [...s.querySelectorAll("p")].map(runs), steps: [...s.querySelectorAll("li")].map(runs),
  }));
  let at = 0;
  scenes.forEach((s) => { s.start = at; at += s.secs; });
  const total = at;
  const full = art.innerText.split("\n").map((l) => l.trim()).filter(Boolean);
  const F = { t: 0, last: 0, playing: !reduced, idx: -1, now: 0 };
  const [btnBack, btnToggle, btnNext] = ["back", "pause", "next"].map((k) => bar.querySelector(`[data-film="${k}"]`));
  const pos = document.getElementById("film-pos");

  // Live data: the same public aggregate the network API serves.
  const live = { net: null, map: null, failed: false };
  fetch("/api/network").then((r) => (r.ok ? r.json() : Promise.reject())).then((d) => { if (d && d.totals) live.net = d; else live.failed = true; }).catch(() => { live.failed = true; });
  fetch("/assets/network-geo.json").then((r) => r.json()).then((g) => {
    const pts = [];
    for (const m of g.dots.matchAll(/M([\d.]+) ([\d.]+)((?:h0m[\d.]+ 0)*)h0/g)) {
      let x = Number(m[1]); const y = Number(m[2]);
      pts.push([x, y]);
      for (const s of m[3].matchAll(/m([\d.]+) 0/g)) { x += Number(s[1]); pts.push([x, y]); }
    }
    live.map = { pts, P: g.projection };
  }).catch(() => {});
  const project = (lon, lat, P) => {
    const A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, M = Math.sqrt(3) / 2;
    const clampLat = Math.max(P.lat_min, Math.min(P.lat_max, lat)) * Math.PI / 180, lam = lon * Math.PI / 180;
    const th = Math.asin(M * Math.sin(clampLat)), t2 = th * th, t6 = t2 * t2 * t2;
    const x = (lam * Math.cos(th)) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)));
    const y = th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2));
    return [(x + P.x_max) * P.scale, (P.y_top - y) * P.scale];
  };

  function chars(r) {
    if (typeof r === "string") r = [{ t: r, c: null }];
    const a = [];
    r.forEach((x) => { for (const ch of x.t) a.push({ ch, c: x.c }); });
    while (a.length && a[0].ch === " ") a.shift();
    while (a.length && a[a.length - 1].ch === " ") a.pop();
    return a;
  }
  function wrap(a, cols) {
    const lines = []; let i = 0;
    while (i < a.length) {
      let e = Math.min(i + cols, a.length);
      if (e < a.length) { let k = e; while (k > i && a[k].ch !== " ") k--; if (k > i) e = k; }
      lines.push(a.slice(i, e)); i = e;
      while (i < a.length && a[i].ch === " ") i++;
    }
    return lines;
  }
  function text(r, o) {
    const size = o.size, lh = size * (o.lh || 1.3);
    c.font = `${o.weight || 400} ${size}px ${FONT}`;
    c.textBaseline = "alphabetic"; c.textAlign = "left";
    const cw = c.measureText("0").width, a = chars(r), lines = wrap(a, Math.max(8, Math.floor(o.maxW / cw)));
    let shown = o.shown === undefined ? Infinity : o.shown, y = o.y, caret = false;
    const typing = shown < a.length, base = c.globalAlpha;
    c.globalAlpha = base * (o.alpha === undefined ? 1 : o.alpha);
    for (const ln of lines) {
      const x0 = o.align === "center" ? o.x - (ln.length * cw) / 2 : o.x, n = Math.min(ln.length, Math.max(0, shown));
      for (let i = 0; i < n; i++) {
        if (ln[i].ch === " ") continue;
        c.fillStyle = colour(ln[i].c) || o.color || INK;
        c.fillText(ln[i].ch, x0 + i * cw, y);
      }
      if ((typing || o.caret) && !caret && shown <= ln.length && shown >= 0) {
        if (typing || Math.floor(F.now / 530) % 2 === 0) { c.fillStyle = INK; c.fillRect(x0 + n * cw + cw * 0.1, y - size * 0.8, Math.max(2, cw * 0.5), size * 0.96); }
        caret = true;
      }
      shown -= ln.length + 1; y += lh;
    }
    c.globalAlpha = base;
    return y;
  }
  const cap = (a) => { const t = a.map((q) => q.ch).join("").trim(); return t.charAt(0).toUpperCase() + t.slice(1); };
  const typed = (v, s, cps) => Math.floor(Math.max(0, v.t - s) * (cps || 34));
  const fade = (v, s, l) => clamp((v.t - s) / (l || 0.5));
  const head = (v, y, size) => text(v.s.h, { x: v.W / 2, y: v.H * (y || 0.16), size: Math.max(19, (size || 40) * v.u), weight: 700, align: "center", maxW: v.W * 0.88, shown: typed(v, 0, 42) });
  function caption(v, list, times, y, wide) {
    let cur = 0; times.forEach((t, i) => { if (v.t >= t) cur = i; });
    if (list[cur]) text(list[cur], { x: v.W / 2, y, size: Math.max(15, 24 * v.u), align: "center", maxW: v.W * (wide || 0.84), alpha: fade(v, times[cur], 0.3), color: SOFT });
  }
  function box(x, y, w, h, stroke, fill) {
    c.fillStyle = fill || CARD; c.strokeStyle = stroke || INK; c.lineWidth = Math.max(1, 2 * (w > 0 ? 1 : 1));
    c.fillRect(x, y, w, h); c.strokeRect(x, y, w, h);
  }
  function seg(x1, y1, x2, y2, k, col) {
    c.strokeStyle = col || INK; c.lineWidth = 2; c.beginPath(); c.moveTo(x1, y1); k = clamp(k);
    c.lineTo(x1 + (x2 - x1) * k, y1 + (y2 - y1) * k); c.stroke();
  }

  // Thin lines only: a few labeled nodes, and one dot moving between them. A column on a phone, a row otherwise.
  const line = (x1, y1, x2, y2, col) => { c.strokeStyle = col || RULE; c.lineWidth = 1; c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke(); };
  const nameOf = (st) => chars(st).map((q) => q.ch).join("").split(":")[0];
  const route = (pts, p) => { const i = Math.max(0, Math.min(pts.length - 2, Math.floor(p))), k = clamp(p - i); return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k]; };
  const dot = (x, y, col, u) => { c.fillStyle = col || BLUE; c.beginPath(); c.arc(x, y, Math.max(5, 8 * u), 0, Math.PI * 2); c.fill(); };
  function node(v, x, y, name, state, side) {
    const r = Math.max(4, 6 * v.u), hot = state === "hot";
    c.fillStyle = hot ? BLUE : PAPER; c.strokeStyle = hot ? BLUE : INK; c.lineWidth = 1;
    c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); c.stroke();
    const size = Math.max(14, 20 * v.u);
    if (side) text(name, { x: x + r + 14, y: y + size * 0.34, size, weight: hot ? 700 : 400, maxW: v.W - x - r - 22, color: hot ? BLUE : INK });
    else text(name, { x, y: y + r + size * 1.7, size, weight: hot ? 700 : 400, align: "center", maxW: Math.max(120, v.sp - 16), lh: 1.25, color: hot ? BLUE : INK });
  }
  function chain(v, names, cur, p, shown, bad) {
    const { W, H } = v, n = names.length, narrow = W < 700;
    v.sp = narrow ? 0 : (W * 0.64) / Math.max(1, n - 1);
    const pts = names.map((_, i) => (narrow ? [W * 0.16, H * 0.3 + (i * H * 0.36) / Math.max(1, n - 1)] : [W / 2 + (i - (n - 1) / 2) * v.sp, H * 0.44]));
    line(pts[0][0], pts[0][1], pts[n - 1][0], pts[n - 1][1]);
    names.forEach((name, i) => { if (i < shown) node(v, pts[i][0], pts[i][1], name, i === cur ? "hot" : "", narrow); });
    const [x, y] = route(pts, p);
    dot(x, y, bad ? RUST : BLUE, v.u);
  }
  // When each sentence starts in the voice, in seconds into its scene.
  const marks = (kind) => (words.labels.marks || {})[kind] || null;
  const lastMark = (list, t) => { let cur = 0; list.forEach((m, i) => { if (t >= m) cur = i; }); return cur; };
  const moved = (keys, t) => {
    for (let i = 0; i < keys.length - 1; i++) if (t >= keys[i][0] && t < keys[i + 1][0]) return keys[i][1] + (keys[i + 1][1] - keys[i][1]) * ease((t - keys[i][0]) / (keys[i + 1][0] - keys[i][0]));
    return keys[keys.length - 1][1];
  };

  const draw = {
    parts(v) {
      // The real shape of the system, not a line: who talks to whom. Each part lights its own connections.
      const { W, H, u } = v, n = v.s.steps.length, pm = marks("parts") || [], start = pm[0] ?? 1.2, each = (v.s.secs - start - 0.8) / n, t = v.t, narrow = W < 700;
      const stepAt = v.s.steps.map((_, i) => pm[i] ?? start + i * each), cur = lastMark(stepAt, t);
      head(v, 0.13, 36);
      const L = words.labels.map;
      const N = { agent: [0.09, 0.14], shim: [0.36, 0.14], model: [0.68, 0.0], store: [0.36, 0.72], feeds: [0.09, 0.72], queue: [0.68, 0.5], workers: [0.93, 0.5], tuned: [0.68, 1.0] };
      const P = (k) => [W * (0.04 + N[k][0] * 0.92), H * (0.27 + N[k][1] * 0.38)];
      const E = [["agent", "shim"], ["shim", "model"], ["store", "shim"], ["feeds", "store"], ["shim", "queue"], ["queue", "workers"], ["workers", "store"], ["workers", "shim"], ["tuned", "queue"]];
      const lit = [[4, 5], [3, 6], [0, 1, 2, 7, 8]][cur] || [];
      const hot = [["queue", "workers"], ["feeds", "store"], ["shim", "model", "tuned"]][cur] || [];
      const started = t >= start;
      E.forEach(([p, q], i) => {
        const [x1, y1] = P(p), [x2, y2] = P(q), on = started && lit.includes(i);
        line(x1, y1, x2, y2, on ? BLUE : "#BDB6A6");
        if (on) { const k = ((t * 0.6 + i * 0.37) % 1); dot(x1 + (x2 - x1) * k, y1 + (y2 - y1) * k, BLUE, u * 0.7); }
      });
      const size = narrow ? 11 : Math.max(13, 20 * u);
      Object.keys(N).forEach((k) => {
        const [x, y] = P(k), on = started && hot.includes(k), r = Math.max(4, 7 * u);
        c.fillStyle = on ? BLUE : PAPER; c.strokeStyle = on ? BLUE : INK; c.lineWidth = 1;
        c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); c.stroke();
        const below = N[k][1] > 0.3 ? 1 : -1;
        text(L[k], { x, y: y + below * (r + size * (below > 0 ? 1.3 : 0.7)), size, weight: on ? 700 : 400, align: "center", maxW: narrow ? W * 0.27 : W * 0.24, color: on ? BLUE : INK, lh: 1.15 });
      });
      if (started) caption(v, v.s.steps, stepAt, H * 0.82);
    },
    title(v) {
      const y = text(v.s.h, { x: v.W / 2, y: v.H * 0.44, size: 60 * v.u, weight: 700, align: "center", maxW: v.W * 0.86 });
      text(v.s.ps[0], { x: v.W / 2, y: y + 24 * v.u, size: 24 * v.u, align: "center", maxW: v.W * 0.7, alpha: fade(v, 2), color: MUTED });
    },
    hook(v) {
      const y = text(v.s.h, { x: v.W / 2, y: v.H * 0.38, size: 74 * v.u, weight: 700, align: "center", maxW: v.W * 0.9, shown: typed(v, 0.1, 20) });
      text(v.s.ps[0], { x: v.W / 2, y: y + 36 * v.u, size: 44 * v.u, weight: 700, align: "center", maxW: v.W * 0.84, shown: typed(v, 1.2, 36) });
    },
    three(v) {
      const x = v.W * 0.1, maxW = v.W * 0.8, u = v.u;
      text(v.s.h, { x, y: v.H * 0.2, size: 24 * u, maxW, alpha: fade(v, 0), color: MUTED });
      let y = v.H * 0.34;
      v.s.ps.slice(0, 3).forEach((p, i) => {
        const st = (marks("three") || [0.6, 4.2, 7.8])[i];
        if (v.t < st) return;
        // The number sits centered on the first line of its sentence.
        text("0" + (i + 1), { x, y: y - (42 - 22) * u * 0.36, size: 22 * u, color: RUST, weight: 700, maxW: 80 * u });
        y = text(p, { x: x + 72 * u, y, size: 42 * u, weight: 700, maxW: maxW - 72 * u, shown: typed(v, st, 26) }) + 44 * u;
      });
    },
    statement(v) {
      const y = text(v.s.h, { x: v.W / 2, y: v.H * 0.4, size: 48 * v.u, weight: 700, align: "center", maxW: v.W * 0.82, shown: typed(v, 0.1, 38) });
      text(v.s.ps[0], { x: v.W / 2, y: y + 24 * v.u, size: 26 * v.u, align: "center", maxW: v.W * 0.7, alpha: fade(v, v.s.secs * 0.45), color: SOFT });
    },
    fixes(v) {
      const u = v.u, x = v.W * 0.12;
      head(v);
      let y = v.H * 0.34;
      v.s.ps.forEach((p, i) => {
        const st = 1.2 + i * 5.4;
        if (v.t < st) return;
        const a = chars(p), dot = a.findIndex((ch) => ch.ch === ".") + 1;
        const lead = a.slice(0, dot).map((q) => q.ch).join(""), rest = a.slice(dot).map((q) => q.ch).join("").trim();
        text(lead, { x, y, size: 32 * u, weight: 700, maxW: v.W * 0.76, shown: typed(v, st, 30), color: BLUE });
        y = text(rest, { x, y: y + 40 * u, size: 22 * u, maxW: v.W * 0.76, alpha: fade(v, st + 1), color: SOFT }) + 34 * u;
      });
    },
    file(v) {
      const { W, H, u } = v;
      head(v, 0.16, 40);
      const x = W * 0.16, w = W * 0.68, top = H * 0.27, h = H * 0.38;
      box(x, top, w, h, RULE, CARD);
      let y = top + 48 * u;
      v.s.steps.forEach((s, i) => {
        const st = 1 + i * 1.9;
        if (v.t < st) return;
        const line = [{ t: "> ", c: "blue" }, ...s];
        y = text(line, { x: x + 28 * u, y, size: 21 * u, maxW: w - 56 * u, shown: typed(v, st, 44) }) + 18 * u;
      });
      text(v.s.ps[0], { x: W / 2, y: H * 0.77, size: 24 * u, align: "center", maxW: W * 0.76, alpha: fade(v, 7.5), color: SOFT });
    },
    page(v) {
      const { W, H, u } = v, col = W * 0.56, size = Math.max(9, 12.5 * u), lh = size * 1.55, maxW = W - col - 40 * u;
      c.font = `400 ${size}px ${FONT}`;
      const cw = c.measureText("0").width, lines = [];
      full.forEach((p) => wrap(chars(p), Math.floor(maxW / cw)).forEach((l) => lines.push(l.map((x) => x.ch).join(""))));
      const vis = Math.floor(H / lh), scroll = Math.max(0, lines.length - vis) * ease((v.t - 1) / (v.s.secs - 1.5)), hot = Math.floor(scroll + vis * 0.45);
      c.save(); c.beginPath(); c.rect(col - 10 * u, 0, W - col + 10 * u, H - 2); c.clip();
      lines.forEach((l, i) => {
        const y = (i - scroll + 1) * lh;
        if (y < -lh || y > H + lh) return;
        if (i === hot) { c.fillStyle = "rgba(36,81,155,0.14)"; c.fillRect(col - 8 * u, y - size * 1.05, maxW + 16 * u, lh); }
        text(l, { x: col, y, size, maxW: maxW + cw, alpha: fade(v, 0.5, 1), color: SOFT });
      });
      c.restore();
      const lx = W * 0.07, lw = col - lx - 48 * u;
      const y = text(v.s.h, { x: lx, y: H * 0.36, size: 44 * u, weight: 700, maxW: lw, shown: typed(v, 0.1, 34) });
      const y2 = text(v.s.ps[0], { x: lx, y: y + 22 * u, size: 23 * u, maxW: lw, alpha: fade(v, 2), color: SOFT });
      text(v.s.ps[1], { x: lx, y: y2 + 16 * u, size: 23 * u, maxW: lw, alpha: fade(v, 4), color: SOFT });
    },
    spaces(v) {
      const { W, H, u } = v, gap = 32 * u, bw = W * 0.38, top = H * 0.3, bh = H * 0.42;
      head(v);
      v.s.ps.forEach((p, i) => {
        const st = 1.4 + i * 3.2;
        if (v.t < st) return;
        const x = W / 2 + (i ? gap / 2 : -gap / 2 - bw);
        c.globalAlpha *= ease((v.t - st) / 0.6);
        box(x, top, bw, bh, i ? BLUE : INK, CARD);
        const a = chars(p), d = a.findIndex((q) => q.ch === ":");
        const y = text(a.slice(0, d).map((q) => q.ch).join(""), { x: x + 28 * u, y: top + 54 * u, size: 28 * u, weight: 700, maxW: bw - 56 * u, color: i ? BLUE : INK });
        text(cap(a.slice(d + 1)), { x: x + 28 * u, y: y + 18 * u, size: 22 * u, lh: 1.5, maxW: bw - 56 * u, color: SOFT });
        c.globalAlpha = 1;
      });
    },
    split(v) {
      // One long job becomes a graph of small Tasks. Tasks wait for what they depend on. Then a separate worker approves.
      const { W, H, u } = v, n = v.s.steps.length, each = (v.s.secs - 0.8) / n, t = v.t;
      head(v, 0.13, 36);
      const apart = ease((t - each) / 1.2), bw = W * 0.72, bx = W * 0.14, by = H * 0.42, r = Math.max(10, 16 * u);
      const G = [[0.06, 0.5], [0.34, 0.15], [0.34, 0.85], [0.64, 0.5], [0.94, 0.5]], D = [[0, 1], [0, 2], [1, 3], [2, 3], [3, 4]];
      const at = (i) => { const hx = bx + bw * G[i][0], hy = H * (0.27 + G[i][1] * 0.36); return [bx + bw * (i + 0.5) / 5 + (hx - (bx + bw * (i + 0.5) / 5)) * apart, by + (hy - by) * apart]; };
      if (apart < 1) { c.strokeStyle = RULE; c.lineWidth = 1; c.strokeRect(bx, by - r, bw, r * 2); }
      const finish = [2, 2.5, 2.9, 3.5, 4.2].map((x) => each * x), done = (i) => t > finish[i];
      if (apart >= 1) D.forEach(([p, q]) => { const [x1, y1] = at(p), [x2, y2] = at(q); line(x1, y1, x2, y2, done(p) ? BLUE : RULE); });
      for (let i = 0; i < 5; i++) {
        const [x, y] = at(i);
        c.fillStyle = done(i) ? BLUE : PAPER; c.strokeStyle = done(i) ? BLUE : INK; c.lineWidth = 1;
        c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); c.stroke();
        text(String(i + 1), { x, y: y + r * 0.42, size: Math.max(12, r), align: "center", maxW: r * 2, color: done(i) ? PAPER : INK });
      }
      caption(v, v.s.steps, marks("split") || v.s.steps.map((_, i) => i * each), H * 0.8);
    },
    four(v) {
      // Four outcomes, one at a time. Each paragraph is "Lead. Detail."
      const { W, H, u } = v, x = W * (W < 700 ? 0.06 : 0.12), maxW = W * (W < 700 ? 0.88 : 0.76), each = (v.s.secs - 1) / 4;
      head(v, 0.13, 36);
      let y = H * 0.25;
      v.s.ps.slice(0, 4).forEach((p, i) => {
        const st = (marks("four") || [])[i] ?? 0.8 + i * each;
        if (v.t < st) return;
        const a = chars(p), d = a.findIndex((q) => q.ch === ".") + 1;
        const lead = a.slice(0, d).map((q) => q.ch).join(""), rest = a.slice(d).map((q) => q.ch).join("").trim();
        y = text(lead, { x, y, size: Math.max(20, 32 * u), weight: 700, maxW, shown: typed(v, st, 34), color: BLUE });
        y = text(rest, { x, y: y + 2 * u, size: Math.max(14, 21 * u), maxW, alpha: fade(v, st + 0.7), color: SOFT }) + 24 * u;
      });
    },
    omninode(v) {
      const { W, H, u } = v, n = v.s.steps.length, start = (marks("omninode") || [3.4])[0], each = (v.s.secs - start - 0.8) / n, narrow = W < 700;
      head(v, 0.13, 36);
      const om = marks("omninode") || v.s.steps.map((_, i) => 3.4 + i * each), cur = lastMark(om, v.t);
      const hub = narrow ? [W * 0.1, H * 0.46] : [W / 2, H * 0.3];
      v.sp = narrow ? 0 : Math.min((W * 0.86) / n, 300 * u);
      const pts = v.s.steps.map((_, i) => (narrow ? [W * 0.3, H * 0.28 + (i * H * 0.36) / (n - 1)] : [W / 2 + (i - (n - 1) / 2) * v.sp, H * 0.56]));
      pts.forEach((p, i) => line(hub[0], hub[1], p[0], p[1], v.t >= start && i === cur ? BLUE : RULE));
      const size = Math.max(16, 24 * u);
      c.fillStyle = PAPER; c.strokeStyle = INK; c.lineWidth = 1;
      c.beginPath(); c.arc(hub[0], hub[1], Math.max(5, 8 * u), 0, Math.PI * 2); c.fill(); c.stroke();
      if (narrow) text("OmniNode", { x: hub[0] - Math.max(5, 8 * u), y: hub[1] - size, size, weight: 700, maxW: W * 0.4 });
      else text("OmniNode", { x: hub[0], y: hub[1] - size, size, weight: 700, align: "center", maxW: W * 0.5 });
      v.s.steps.forEach((st, i) => node(v, pts[i][0], pts[i][1], nameOf(st), v.t >= start && i === cur ? "hot" : "", narrow));
      if (v.t < start) { text(v.s.ps[0], { x: W / 2, y: H * 0.8, size: Math.max(15, 24 * u), align: "center", maxW: W * 0.84, alpha: fade(v, 0.3), color: SOFT }); return; }
      const k = ease(((v.t - start) % each) / Math.min(1.2, each));
      dot(hub[0] + (pts[cur][0] - hub[0]) * k, hub[1] + (pts[cur][1] - hub[1]) * k, BLUE, u);
      caption(v, v.s.steps, om, H * 0.8);
    },
    queue(v) {
      // Same story as the captions: claimed, stopped, back in the queue, picked up again, saved, checked.
      const r = v.s.secs / 15, at = (x) => x * r, t = v.t;
      head(v, 0.14, 36);
      const times = [0, 1.6, 4.6, 7.2, 10].map(at);
      const p = moved([[at(0), 0], [at(1.6), 0], [at(3), 1], [at(5.8), 1], [at(7.2), 0], [at(7.8), 0], [at(9), 1], [at(10), 2], [at(11.6), 3], [99, 3]], t);
      const bad = t >= at(4.6) && t < at(7.2);
      chain(v, words.labels.queue, Math.min(3, Math.round(p)), p, 4, bad);
      caption(v, v.s.steps, times, v.H * 0.8);
    },
    workers(v) {
      const { W, H, u } = v, n = 2, bw = W * 0.38, gap = 32 * u, top = H * 0.32;
      head(v, 0.16, 38);
      v.s.ps.forEach((p, i) => {
        const st = 1.2 + i * 3;
        if (v.t < st) return;
        const x = W / 2 + (i ? gap / 2 : -gap / 2 - bw), a = chars(p), d = a.findIndex((q) => q.ch === ":");
        const y = text(a.slice(0, d).map((q) => q.ch).join(""), { x, y: top + 20 * u, size: 28 * u, weight: 700, maxW: bw, color: i ? BLUE : INK, shown: typed(v, st, 40) });
        text(cap(a.slice(d + 1)), { x, y: y + 18 * u, size: 22 * u, lh: 1.5, maxW: bw, alpha: fade(v, st + 0.8), color: SOFT });
      });
      return n;
    },
    reuse(v) {
      head(v, 0.14, 36);
      const names = words.labels.reuse, p = moved([[1, 0], [3.2, 1], [5.4, 2], [99, 2]], v.t);
      chain(v, names, Math.round(p), p, names.length);
      text(v.s.ps[0], { x: v.W / 2, y: v.H * 0.8, size: Math.max(15, 24 * v.u), align: "center", maxW: v.W * 0.84, alpha: fade(v, 2), color: SOFT });
    },
    bars(v) {
      const { W, H, u } = v, narrow = W < 700, x = W * (narrow ? 0.08 : 0.16), w = W * (narrow ? 0.84 : 0.68), size = Math.max(13, 22 * u), big = Math.max(18, 30 * u);
      head(v);
      let y = H * 0.27;
      v.s.steps.forEach((s, i) => {
        const a = chars(s).map((q) => q.ch).join(""), d = a.lastIndexOf(":"), pct = parseFloat(a.slice(d + 1)), k = ease((v.t - 1 - i * 1.2) / 1.6), col = i % 2 ? MUTED : BLUE;
        const end = text(a.slice(0, d), { x, y, size, maxW: w - big * 4, lh: 1.25 }), row = end - size * 1.25;
        text(`${(pct * k).toFixed(1)}%`, { x: x + w - big * 3.6, y: row, size: big, weight: 700, maxW: big * 4, color: col });
        c.fillStyle = LINE; c.fillRect(x, row + 12, w, Math.max(6, 14 * u));
        c.fillStyle = col; c.fillRect(x, row + 12, w * (pct / 100) * k, Math.max(6, 14 * u));
        y = row + Math.max(58, 84 * u);
      });
      text(v.s.ps[0], { x: W / 2, y: H * 0.8, size: Math.max(14, 22 * u), align: "center", maxW: W * (narrow ? 0.9 : 0.74), alpha: fade(v, 5), color: SOFT });
    },
    live(v) {
      const { W, H, u } = v, n = live.net;
      head(v, 0.12, 38);
      const mw = Math.min(W * 0.62, (H * 0.46) / 0.435), mh = mw * 0.435, mx = W * 0.04, my = H * 0.19, sc = mw / 1000;
      if (live.map) {
        c.fillStyle = "#CFC8B8";
        const r = Math.max(0.8, 1.5 * sc);
        c.globalAlpha *= fade(v, 0.3, 1.2);
        for (const [x, y] of live.map.pts) c.fillRect(mx + x * sc - r, my + y * sc - r, r * 2, r * 2);
        c.globalAlpha = 1;
      }
      if (!n) {
        if (live.failed) text(words.live_none, { x: W / 2, y: H * 0.8, size: 22 * u, align: "center", maxW: W * 0.8, color: MUTED });
        return;
      }
      if (live.map) (n.data_centres || []).forEach((d, i) => {
        const [px, py] = project(d.lon, d.lat, live.map.P), x = mx + px * sc, y = my + py * sc, a = fade(v, 1 + i * 0.25, 0.4);
        const pulse = (F.now / 900 + i * 0.37) % 1;
        c.globalAlpha = a * (1 - pulse); c.strokeStyle = BLUE; c.lineWidth = 2;
        c.beginPath(); c.arc(x, y, (5 + 22 * pulse) * u, 0, Math.PI * 2); c.stroke();
        c.globalAlpha = a; c.fillStyle = BLUE;
        c.beginPath(); c.arc(x, y, Math.min(12, 3 + Math.sqrt(d.workers || 1)) * u, 0, Math.PI * 2); c.fill();
        c.globalAlpha = 1;
      });
      const t = n.totals || {}, sx = mx + mw + 28 * u, sw = W - sx - 24 * u;
      [[t.workers, words.live_workers], [t.data_centres, words.live_places], [t.claims, words.live_claims]].forEach(([val, label], i) => {
        const y = my + 44 * u + i * 104 * u, k = ease((v.t - 1.5 - i * 0.6) / 1.5);
        text(String(Math.round((val || 0) * k)), { x: sx, y, size: 52 * u, weight: 700, maxW: sw, color: BLUE });
        text(label, { x: sx, y: y + 30 * u, size: 18 * u, maxW: sw, color: SOFT });
      });
      const claims = (n.recent_claims || []).filter((r) => r.title);
      if (claims.length) {
        const i = Math.floor(Math.max(0, v.t - 3) / 3.2) % claims.length, r = claims[i], via = r.via && (r.via.city || r.via.continent);
        const meta = [r.model && r.model.name, via].filter(Boolean).join(" · ");
        const y = text(r.title, { x: W * 0.06, y: my + mh + 44 * u, size: 22 * u, maxW: W * 0.88, shown: typed(v, 3 + i * 3.2, 70) });
        text(meta, { x: W * 0.06, y: y + 2 * u, size: 18 * u, maxW: W * 0.88, color: MUTED });
      }
      text(v.s.ps[0], { x: W / 2, y: H * 0.93, size: Math.max(13, 17 * u), align: "center", maxW: W * 0.86, color: MUTED, alpha: fade(v, 1) });
    },
    eranos(v) {
      // The two-sided marketplace as its real shape: NGOs on one side, helpers on the other, a network of agents between, then a separate audit, then what the NGO gets.
      const { W, H, u } = v, narrow = W < 700, L = words.labels.eranos, em = marks("eranos") || [8.2, 11, 17, 21];
      const knots = [[0, 0], [em[0], 8.2], [em[1], 11], [em[2], 17], [em[3], 21]], warp = (x) => { for (let i = knots.length - 1; i >= 0; i--) if (x >= knots[i][0]) { const a = knots[i], b = knots[i + 1]; return b ? a[1] + ((x - a[0]) * (b[1] - a[1])) / (b[0] - a[0]) : a[1] + (x - a[0]); } return x; };
      const t = warp(v.t); v = { ...v, t };
      const into = ease((t - 7.4) / 1.6);
      const P = narrow
        ? { ngo: [W * 0.1, H * 0.2], help: [W * 0.58, H * 0.2], net: [W * 0.34, H * 0.36], audit: [W * 0.1, H * 0.52], info: [W * 0.1, H * 0.65], reuse: [W * 0.5, H * 0.65], own: [W * 0.1, H * 0.78] }
        : { ngo: [W * 0.1, H * 0.34], help: [W * 0.34, H * 0.2], net: [W * 0.34, H * 0.46], audit: [W * 0.58, H * 0.46], info: [W * 0.74, H * 0.3], reuse: [W * 0.74, H * 0.62], own: [W * 0.88, H * 0.46] };
      // The agents start spread across the frame behind the words, then gather into the network.
      const small = narrow ? 34 : 92 * u;
      const A = [[0, 0], [0.95, -0.35], [0.55, 0.75], [-0.6, 0.7], [-0.95, -0.2], [-0.4, -0.8], [0.4, -0.85]].map(([a, b]) => [
        W / 2 + a * W * 0.42 + (P.net[0] + a * small - W / 2 - a * W * 0.42) * into,
        H / 2 + b * H * 0.42 + (P.net[1] + b * small * 0.62 - H / 2 - b * H * 0.42) * into]);
      const E = [[0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [0, 6], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 1]];
      E.forEach(([a, b]) => line(A[a][0], A[a][1], A[b][0], A[b][1]));
      A.forEach(([x, y]) => { c.fillStyle = PAPER; c.strokeStyle = INK; c.lineWidth = 1; c.beginPath(); c.arc(x, y, Math.max(4, 6 * u), 0, Math.PI * 2); c.fill(); c.stroke(); });
      E.forEach(([a, b], i) => { if (i % 3) return; const k = ((t * 0.5 + i * 0.37) % 1); dot(A[a][0] + (A[b][0] - A[a][0]) * k, A[a][1] + (A[b][1] - A[a][1]) * k, BLUE, u * 0.6); });
      if (t < 8.2) {
        c.fillStyle = PAPER; c.globalAlpha *= 0.86; c.fillRect(W * 0.04, H * 0.22, W * 0.92, H * 0.5); c.globalAlpha = 1;
        text(v.s.h, { x: W / 2, y: H * (narrow ? 0.34 : 0.4), size: Math.max(19, 38 * u), weight: 700, align: "center", maxW: W * 0.82, shown: typed(v, 0.1, 40) });
        return;
      }
      text([{ t: "Eranos", c: null }], { x: W / 2, y: H * 0.1, size: Math.max(22, 36 * u), weight: 700, align: "center", maxW: W * 0.8, alpha: fade(v, 8.2) });
      const lit = (name, from, to) => (t >= from && (to === undefined || t < to) ? "hot" : "");
      v.sp = narrow ? 0 : W * 0.19;
      const wire = (a, b, from) => { if (t >= from) { c.globalAlpha = fade(v, from); line(P[a][0], P[a][1], P[b][0], P[b][1], BLUE); c.globalAlpha = 1; } };
      wire("ngo", "net", 8.2); wire("help", "net", 11); wire("net", "audit", 13); wire("audit", "info", 13); wire("audit", "reuse", 14); wire("info", "own", 15); wire("reuse", "own", 15);
      // Labels sit where no line runs through them.
      const place = (key, from, hot, pos) => {
        if (t < from) return;
        const [x, y] = P[key], size = Math.max(14, 20 * u), name = [{ t: L[key], c: null }], r = Math.max(4, 6 * u);
        c.globalAlpha = fade(v, from);
        if (narrow || pos === "side") node(v, x, y, name, hot, true);
        else if (pos === "below") node(v, x, y, name, hot, false);
        else {
          node(v, x, y, [], hot, true);
          text(name, { x: pos === "left" ? x - 96 * u : x, y: y - r - size * 0.7, size, weight: hot ? 700 : 400, align: "center", maxW: W * 0.26, alpha: fade(v, from), color: hot ? BLUE : INK });
        }
        c.globalAlpha = 1;
      };
      place("ngo", 8.2, lit("ngo", 8.2, 11), "above");
      place("help", 11, "", "side");
      place("audit", 13, lit("audit", 17, 21), "left");
      place("info", 13, lit("info", 13, 15), "above");
      place("reuse", 14, lit("reuse", 14, 15.5), "below");
      place("own", 15, lit("own", 15.5, 17), "side");
      if (!narrow) text([{ t: L.net, c: null }], { x: P.net[0], y: P.net[1] + small * 0.62 + 34 * u, size: Math.max(14, 20 * u), weight: t >= 11 && t < 13 ? 700 : 400, align: "center", maxW: W * 0.26, alpha: fade(v, 11), color: t >= 11 && t < 13 ? BLUE : INK });
      else text([{ t: L.net, c: null }], { x: P.net[0] + small + 18, y: P.net[1] + 6, size: 14, maxW: W * 0.5, alpha: fade(v, 11) });
      // Tasks keep arriving: one from the NGO to the network, then through the audit to both results and home.
      const flow = [[P.ngo, P.net, 8.2, 2.6], [P.help, P.net, 11, 2.6], [P.net, P.audit, 13, 2.2], [P.audit, P.info, 13, 2.4], [P.audit, P.reuse, 14, 2.4], [P.info, P.own, 15, 2.4], [P.reuse, P.own, 15.6, 2.4]];
      flow.forEach(([p, q, from, each]) => { if (t < from) return; const k = ease(((t - from) % each) / each); dot(p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k, BLUE, u); });
      const times = [8.2, 11, 17, 21], y = H * (narrow ? 0.86 : 0.82);
      caption(v, v.s.ps, times, y, 0.94);
    },
    connect(v) {
      const y = text(v.s.h, { x: v.W / 2, y: v.H * 0.44, size: 72 * v.u, weight: 700, align: "center", maxW: v.W * 0.9, shown: typed(v, 0.1, 24) });
      text(v.s.ps[0], { x: v.W / 2, y: y + 30 * v.u, size: 26 * v.u, align: "center", maxW: v.W * 0.86, shown: typed(v, 1.4, 38), caret: true });
    },
  };

  // The 3D world, only on the page that asks for it (/experience/), after first paint. Until it arrives, or if it can't run, the line drawings stay.
  let world = null, onScreen = true;
  if ("IntersectionObserver" in window) new IntersectionObserver((e) => { onScreen = e[e.length - 1].isIntersecting; }).observe(cv);
  const loadWorld = () => {
    if (!words.world || reduced || !document.createElement("canvas").getContext("webgl2")) return;
    import("/assets/film3d.js").then((m) => {
      scenes.forEach((s, i) => { s.prevWorld = i > 0 && m.isWorld(scenes[i - 1].kind); });
      world = m.create({ target: cv, scenes, words, api: { text, chars, wrap, typed, FONT } });
      cv.filmWorld = world;
    }).catch(() => { world = null; });
  };
  requestAnimationFrame(() => setTimeout(() => (window.requestIdleCallback ? requestIdleCallback(loadWorld, { timeout: 1500 }) : loadWorld()), 0));
  cv.addEventListener("film-seek", (e) => { F.t = Math.max(0, Math.min(total, e.detail)); F.playing = false; F.held = true; F.idx = -1; label(); });

  function frame(now) {
    F.now = now;
    const dt = F.last ? Math.min(0.1, (now - F.last) / 1000) : 0;
    F.last = now;
    if (!onScreen) { requestAnimationFrame(frame); return; }
    if (F.playing) {
      F.t += dt;
      if (F.t >= total) { F.t = total; F.playing = false; label(); }
    }
    let idx = scenes.length - 1;
    for (let i = 0; i < scenes.length; i++) if (F.t < scenes[i].start + scenes[i].secs) { idx = i; break; }
    if (idx !== F.idx) { F.idx = idx; label(); }
    const W = cv.clientWidth, H = cv.clientHeight;
    if (W && H) {
      const dpr = Math.min(devicePixelRatio || 1, 2), pw = Math.round(W * dpr), ph = Math.round(H * dpr);
      if (cv.width !== pw || cv.height !== ph) { cv.width = pw; cv.height = ph; }
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.globalAlpha = 1; c.fillStyle = PAPER; c.fillRect(0, 0, W, H);
      // Paused or jumped to while paused: the scene at rest, never a half-typed line or a bar on its way up.
      const s = scenes[idx], rest = !F.playing && !F.held, t = rest ? s.secs + 60 : F.t - s.start;
      const v = { W, H, u: Math.max(0.42, Math.min(W / 1280, H / 720)), t, s };
      if (world && world.has(s.kind)) {
        const nextScene = scenes[idx + 1], st = rest ? Math.max(F.t - s.start, Math.min(3, s.secs - 0.6)) : t;
        world.draw(c, { ...v, t: st }, s.start + st, !!nextScene && world.has(nextScene.kind));
      } else {
        c.globalAlpha = rest || idx === scenes.length - 1 ? 1 : clamp((s.secs - t) / 0.3);
        draw[s.kind](v);
      }
      c.globalAlpha = 1;
      // The hackathon line stays still on screen from 0:00 to 0:20, never typed. Same words as the page.
      if (F.t < 20 && scenes[0].ps[1]) {
        const small = W < 700, size = Math.max(13, 17 * v.u), by = H - (small ? 46 : 22);
        c.fillStyle = PAPER; c.fillRect(0, by - size * 1.2, W, H - by + size * 1.2);
        text(scenes[0].ps[1], { x: W / 2, y: by, size, align: "center", maxW: W * 0.92, color: MUTED });
      }
      c.fillStyle = INK; c.fillRect(0, H - 2, W * (F.t / total), 2);
    }
    requestAnimationFrame(frame);
  }
  function label() {
    btnToggle.textContent = F.t >= total ? words.replay : F.playing ? words.pause : words.play;
    pos.textContent = words.scene.replace("{n}", F.idx + 1).replace("{total}", scenes.length);
  }
  const go = (d) => { const i = Math.max(0, Math.min(scenes.length - 1, F.idx + d)); F.t = scenes[i].start; F.idx = -1; };
  btnBack.addEventListener("click", () => go(-1));
  btnNext.addEventListener("click", () => go(1));
  btnToggle.addEventListener("click", () => { if (F.t >= total) F.t = 0; F.playing = !F.playing; F.held = false; label(); });
  // Voice: browsers allow sound only after a click, so the visitor turns it on. The track follows the film's clock.
  const btnSound = bar.querySelector('[data-film="sound"]');
  let voice = null;
  const syncVoice = () => {
    if (!voice) return;
    if (F.playing) { if (Math.abs(voice.currentTime - F.t) > 0.35) voice.currentTime = F.t; if (voice.paused) voice.play().catch(() => {}); }
    else if (!voice.paused) voice.pause();
  };
  if (btnSound && btnSound.dataset.src) btnSound.addEventListener("click", () => {
    if (voice) { voice.pause(); voice = null; btnSound.textContent = words.sound_on; return; }
    voice = new Audio(btnSound.dataset.src); voice.preload = "auto";
    if (!F.playing && F.t < total) { F.playing = true; label(); }
    btnSound.textContent = words.sound_off; syncVoice();
  });
  setInterval(syncVoice, 500);
  label();
  requestAnimationFrame(frame);
})();
