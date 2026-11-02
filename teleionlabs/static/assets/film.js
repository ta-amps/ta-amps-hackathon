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
  const head = (v, y, size) => text(v.s.h, { x: v.W / 2, y: v.H * (y || 0.16), size: (size || 40) * v.u, weight: 700, align: "center", maxW: v.W * 0.88, shown: typed(v, 0, 42) });
  function caption(v, list, times, y) {
    let cur = 0; times.forEach((t, i) => { if (v.t >= t) cur = i; });
    if (list[cur]) text(list[cur], { x: v.W / 2, y, size: 24 * v.u, align: "center", maxW: v.W * 0.84, alpha: fade(v, times[cur], 0.3), color: SOFT });
  }
  function box(x, y, w, h, stroke, fill) {
    c.fillStyle = fill || CARD; c.strokeStyle = stroke || INK; c.lineWidth = Math.max(1, 2 * (w > 0 ? 1 : 1));
    c.fillRect(x, y, w, h); c.strokeRect(x, y, w, h);
  }
  function seg(x1, y1, x2, y2, k, col) {
    c.strokeStyle = col || INK; c.lineWidth = 2; c.beginPath(); c.moveTo(x1, y1); k = clamp(k);
    c.lineTo(x1 + (x2 - x1) * k, y1 + (y2 - y1) * k); c.stroke();
  }

  // 2.5D: a light isometric world of tiles, drawn from three shades of one colour.
  const iso = (v, ox, oy, s) => ({
    p: (x, y, z = 0) => [ox + (x - y) * s, oy + (x + y) * s * 0.5 - z * s],
    s,
  });
  function poly(pts, fill, stroke) {
    c.beginPath(); pts.forEach(([x, y], i) => (i ? c.lineTo(x, y) : c.moveTo(x, y))); c.closePath();
    if (fill) { c.fillStyle = fill; c.fill(); }
    if (stroke) { c.strokeStyle = stroke; c.lineWidth = 1; c.stroke(); }
  }
  function cube(w, x, y, z, sx, sy, h, top, left, right, edge) {
    const P = w.p;
    poly([P(x, y + sy, z), P(x + sx, y + sy, z), P(x + sx, y + sy, z + h), P(x, y + sy, z + h)], left, edge);
    poly([P(x + sx, y, z), P(x + sx, y + sy, z), P(x + sx, y + sy, z + h), P(x + sx, y, z + h)], right, edge);
    poly([P(x, y, z + h), P(x + sx, y, z + h), P(x + sx, y + sy, z + h), P(x, y + sy, z + h)], top, edge);
  }
  const BLUES = ["#3A69B8", "#24519B", "#1A3D78"], INKS = ["#3B424C", "#22272F", "#11161F"], PAPERS = ["#FFFDF8", "#E9E3D5", "#D8D1C1"], RUSTS = ["#C4562F", "#A23E1C", "#7E2F14"];
  const block = (w, x, y, z, sx, sy, h, pal) => cube(w, x, y, z, sx, sy, h, pal[0], pal[1], pal[2], null);
  function floor(v, w, n, a) {
    c.globalAlpha *= a;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const wave = Math.sin(F.now / 900 + (i + j) * 0.5) * 0.015;
      cube(w, i + 0.04, j + 0.04, 0, 0.92, 0.92, 0.06 + wave, "#FFFDF8", "#E2DCCF", "#D8D1C1", null);
    }
    c.globalAlpha = 1;
  }

  const draw = {
    parts(v) {
      const { W, H, u } = v, n = v.s.steps.length, start = 1.2, each = (v.s.secs - start - 0.8) / n;
      head(v, 0.11, 36);
      const narrow = W < 700, s = (narrow ? 30 : 46) * u * (narrow ? 1.6 : 1), drift = Math.sin(F.now / 2600) * 10 * u;
      const w = iso(v, W / 2 + drift, H * 0.34, s), G = 8;
      floor(v, w, G, fade(v, 0, 0.8));
      const on = (i) => v.t >= start + i * each, rise = (i) => ease((v.t - start - i * each) / 0.8), z0 = 0.08;
      // Durable Tasks: a Task travels the row; the first worker stops; the next one takes over.
      if (on(0)) {
        const k = ease((v.t - start) / 0.6);
        c.globalAlpha = k;
        for (let i = 0; i < G; i++) cube(w, i + 0.12, 3.12, z0, 0.76, 0.76, 0.04, "#DCE5F3", "#C5D3EA", "#B4C5E2", null);
        const lap = ((v.t - start) % 4) / 4, x = lap * (G - 1);
        const fail = lap > 0.38 && lap < 0.5;
        block(w, x + 0.25, 3.25, z0 + 0.05, 0.5, 0.5, 0.5, fail ? RUSTS : BLUES);
        c.globalAlpha = 1;
      }
      // Durable Task Objects: stacks that grow, one block per kept version.
      if (on(1)) {
        const heights = [3, 5, 2, 4], k = rise(1);
        heights.forEach((m, i) => {
          const shown = Math.ceil(m * k * Math.min(1, (v.t - start - each + 1) / 2));
          for (let z = 0; z < shown; z++) block(w, 1 + i * 1.6, 5.3, z0 + z * 0.34, 0.8, 0.8, 0.3, z === shown - 1 ? BLUES : PAPERS);
        });
      }
      // The shim: a thin layer that lifts between the agent and its model.
      if (on(2)) {
        const k = rise(2), z = 2.3 * k;
        c.globalAlpha = 0.55 * k;
        poly([w.p(0.6, 0.4, z), w.p(4.4, 0.4, z), w.p(4.4, 2.6, z), w.p(0.6, 2.6, z)], "#DCE5F3", BLUE);
        c.globalAlpha = 1;
        block(w, 1.2, 1, z0, 0.9, 0.9, 1.1, INKS);
        const pulse = (F.now / 900) % 1;
        const [ax, ay] = w.p(1.65, 1.45, z0 + 1.1), [bx, by] = w.p(3.3, 1.45, 3.1 * k);
        seg(ax, ay, bx, by, 1, BLUE);
        c.fillStyle = BLUE; c.beginPath(); c.arc(ax + (bx - ax) * pulse, ay + (by - ay) * pulse, 4 * u, 0, Math.PI * 2); c.fill();
      }
      // The custom-trained model: the piece that turns slowly above the layer.
      if (on(3)) {
        const k = rise(3), bob = Math.sin(F.now / 700) * 0.06;
        block(w, 2.9, 1, 2.9 + bob, 0.9 * k, 0.9 * k, 0.9 * k, BLUES);
      }
      const cur = Math.min(n - 1, Math.floor(Math.max(0, v.t - start) / each));
      const tag = (i, gx, gy, gz) => {
        if (!on(i)) return;
        const [x, y] = w.p(gx, gy, gz), name = chars(v.s.steps[i]).map((q) => q.ch).join("").split(":")[0];
        text(name, { x: Math.max(8, Math.min(W - 8 - name.length * 8.6 * u, x)), y, size: 15 * u, weight: i === cur ? 700 : 400, maxW: W, color: i === cur ? BLUE : SOFT, alpha: rise(i) });
      };
      tag(0, 8.3, 3.2, 0.2); tag(1, -1.4, 7.4, 0); tag(2, 4.7, 0.2, 2.3); tag(3, 3.9, 0.6, 3.5);
      if (v.t >= start) caption(v, v.s.steps, v.s.steps.map((_, i) => start + i * each), H * 0.88);
      return cur;
    },
    title(v) {
      const y = text(v.s.h, { x: v.W / 2, y: v.H * 0.44, size: 60 * v.u, weight: 700, align: "center", maxW: v.W * 0.86, shown: typed(v, 0.2, 26) });
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
        const st = 0.6 + i * 3.6;
        if (v.t < st) return;
        text("0" + (i + 1), { x, y, size: 22 * u, color: RUST, weight: 700, maxW: 80 * u });
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
    link(v) {
      const { W, H, u } = v, y = H * 0.44, ax = W * 0.17, lx = W * 0.5, yx = W * 0.83, bw = 170 * u, bh = 76 * u, pw = 300 * u, ph = 64 * u;
      head(v, 0.15, 36);
      seg(ax + bw / 2, y, lx - pw / 2, y, (v.t - 1.2) / 1);
      seg(lx + pw / 2, y, yx - bw / 2, y, (v.t - 3) / 1.2);
      const used = v.t > 7;
      const node = (x, label) => { box(x - bw / 2, y - bh / 2, bw, bh); text(label, { x, y: y + 8 * u, size: 22 * u, align: "center", maxW: bw }); };
      node(ax, words.live_agent); node(yx, words.live_you);
      if (v.t > 2.2) {
        c.globalAlpha *= ease((v.t - 2.2) / 0.5);
        box(lx - pw / 2, y - ph / 2, pw, ph, used ? RULE : BLUE, used ? PAPER : CARD);
        text("teleionlabs.com/l/…", { x: lx, y: y - 4 * u, size: 19 * u, align: "center", maxW: pw, color: used ? MUTED : BLUE });
        const left = Math.max(0, 600 - (Math.min(v.t, 7) - 2.2) * 38), mm = Math.floor(left / 60), ss = Math.floor(left % 60);
        text(`${mm < 10 ? "0" : ""}${mm}:${ss < 10 ? "0" : ""}${ss}`, { x: lx, y: y + 20 * u, size: 15 * u, align: "center", maxW: pw, color: MUTED });
        c.globalAlpha = 1;
      }
      if (v.t > 5) {
        const bx = yx - 70 * u, by = y + bh / 2 + 18 * u;
        c.fillStyle = used ? BLUE : INK; c.fillRect(bx, by, 140 * u, 48 * u);
        text(used ? words.live_done : words.live_ok, { x: yx, y: by + 31 * u, size: 19 * u, align: "center", maxW: 140 * u, color: PAPER });
      }
      if (v.t > 8) {
        const ry = y + bh / 2 + 110 * u, k = ease((v.t - 8) / 1.6);
        c.strokeStyle = BLUE; c.lineWidth = 2; c.beginPath(); c.moveTo(yx, y + bh / 2 + 66 * u); c.lineTo(yx, ry); c.lineTo(yx + (ax - yx) * k, ry);
        if (k >= 1) c.lineTo(ax, y + bh / 2); c.stroke();
      }
      caption(v, v.s.steps, [0, 2.2, 4.6, 8], H * 0.84);
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
    omninode(v) {
      const { W, H, u } = v, cx = W / 2, cy = H * 0.5, n = v.s.steps.length, R = Math.min(W * 0.3, H * 0.27), start = 1.6, each = (v.s.secs - start - 1) / Math.max(1, n);
      head(v, 0.13, 38);
      const cur = Math.min(n - 1, Math.floor(Math.max(0, v.t - start) / each));
      const label = (st) => chars(st).map((q) => q.ch).join("");
      for (let i = 0; i < n; i++) {
        const a = -Math.PI / 2 + (i / n) * Math.PI * 2, y = cy + Math.sin(a) * R;
        const on = v.t >= start + i * each, hot = on && i === cur, name = label(v.s.steps[i]).split(":")[0];
        const half = ((name.length * 0.62 * 20 + 28) * u) / 2 + 8, x = Math.max(half, Math.min(W - half, cx + Math.cos(a) * R * 1.55));
        if (on) seg(cx, cy, x, y, (v.t - (start + i * each)) / 0.5, hot ? BLUE : RULE);
        const w = (name.length * 0.62 * 20 + 28) * u, h2 = 44 * u;
        c.globalAlpha = on ? 1 : 0.35;
        box(x - w / 2, y - h2 / 2, w, h2, hot ? BLUE : RULE, hot ? BLUE : CARD);
        text(name, { x, y: y + 7 * u, size: 20 * u, align: "center", maxW: w + 8, color: hot ? PAPER : INK });
        c.globalAlpha = 1;
      }
      const nw = 150 * u, nh = 72 * u, pulse = 1 + 0.03 * Math.sin(F.now / 300);
      box(cx - (nw * pulse) / 2, cy - (nh * pulse) / 2, nw * pulse, nh * pulse, INK, CARD);
      text("OmniNode", { x: cx, y: cy + 8 * u, size: 22 * u, weight: 700, align: "center", maxW: nw });
      if (v.t >= start) caption(v, v.s.steps, v.s.steps.map((_, i) => start + i * each), H * 0.86);
      else text(v.s.ps[0], { x: W / 2, y: H * 0.86, size: 22 * u, align: "center", maxW: W * 0.8, alpha: fade(v, 0.3), color: SOFT });
    },
    queue(v) {
      const { W, H } = v, narrow = W < 700, u = v.u, s = (narrow ? 26 : 44) * u * (narrow ? 1.5 : 1);
      head(v);
      const w = iso(v, W / 2 + Math.sin(F.now / 2600) * 10 * u, H * 0.3, s), G = 8;
      floor(v, w, G, fade(v, 0, 0.8));
      const row = 3.5, stops = [0.5, 2.8, 5, 7];
      const keys = [[0, 0], [1.4, 0], [2.8, 1], [4.2, 1.45], [5, 1.45], [6, 0], [6.6, 0], [7.6, 1], [9.2, 2], [10.6, 3], [99, 3]];
      let p = 3;
      for (let i = 0; i < keys.length - 1; i++) if (v.t >= keys[i][0] && v.t < keys[i + 1][0]) { p = keys[i][1] + (keys[i + 1][1] - keys[i][1]) * ease((v.t - keys[i][0]) / (keys[i + 1][0] - keys[i][0])); break; }
      const lit = v.t > 10.6, bad = v.t >= 4.2 && v.t < 6;
      for (let i = 0; i < G; i++) cube(w, i + 0.12, row - 0.38, 0.08, 0.76, 0.76, 0.03, "#DCE5F3", "#C5D3EA", "#B4C5E2", null);
      stops.forEach((x, i) => block(w, x - 0.2, row - 1.3, 0.08, 0.5, 0.5, i === 3 ? 1 : 0.7, i === 3 && lit ? BLUES : INKS));
      const at = p <= 1 ? stops[0] + (stops[1] - stops[0]) * p : p <= 2 ? stops[1] + (stops[2] - stops[1]) * (p - 1) : stops[2] + (stops[3] - stops[2]) * (p - 2);
      block(w, at - 0.2, row - 0.2, 0.12, 0.42, 0.42, 0.42, bad ? RUSTS : lit ? BLUES : INKS);
      caption(v, v.s.steps, [0, 1.4, 4.2, 6.6, 9.2], H * 0.86);
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
      const { W, H } = v, narrow = W < 700, u = v.u, s = (narrow ? 26 : 44) * u * (narrow ? 1.5 : 1);
      head(v);
      const w = iso(v, W / 2, H * 0.3, s), G = 8;
      floor(v, w, G, fade(v, 0, 0.8));
      [[1, 0], [3.5, 0.55], [6, 0.85]].forEach(([x, saved], i) => {
        const st = 0.8 + i * 1.6, k = ease((v.t - st) / 1), H0 = 3;
        const reused = H0 * saved * k, fresh = H0 * (1 - saved) * ease((v.t - st - 0.8) / 1);
        if (reused > 0.02) block(w, x, 3, 0.08, 1, 1, reused, BLUES);
        if (fresh > 0.02) block(w, x, 3, 0.08 + reused, 1, 1, fresh, INKS);
      });
      text(v.s.ps[0], { x: W / 2, y: H * 0.86, size: 24 * u, align: "center", maxW: W * 0.78, alpha: fade(v, 5), color: SOFT });
    },
    bars(v) {
      const { W, H, u } = v, x = W * 0.16, w = W * 0.68;
      head(v);
      v.s.steps.forEach((s, i) => {
        const a = chars(s).map((q) => q.ch).join(""), d = a.lastIndexOf(":"), pct = parseFloat(a.slice(d + 1)), y = H * 0.27 + i * 92 * u, k = ease((v.t - 1 - i * 1.2) / 1.6);
        text(a.slice(0, d), { x, y, size: 22 * u, maxW: w * 0.7 });
        text(`${(pct * k).toFixed(1)}%`, { x: x + w - 110 * u, y, size: 30 * u, weight: 700, maxW: 140 * u, color: i ? MUTED : BLUE });
        c.fillStyle = LINE; c.fillRect(x, y + 14 * u, w, 22 * u);
        c.fillStyle = i ? MUTED : BLUE; c.fillRect(x, y + 14 * u, w * (pct / 100) * k, 22 * u);
      });
      text(v.s.ps[0], { x: W / 2, y: H * 0.84, size: 22 * u, align: "center", maxW: W * 0.74, alpha: fade(v, 5), color: SOFT });
    },
    live(v) {
      const { W, H, u } = v, n = live.net;
      head(v, 0.12, 38);
      const mw = Math.min(W * 0.62, H * 1.2), mh = mw * 0.435, mx = W * 0.04, my = H * 0.2, sc = mw / 1000;
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
        const y = text(r.title, { x: W * 0.06, y: H * 0.72, size: 22 * u, maxW: W * 0.88, shown: typed(v, 3 + i * 3.2, 70) });
        text(meta, { x: W * 0.06, y: y + 2 * u, size: 18 * u, maxW: W * 0.88, color: MUTED });
      }
      text(v.s.ps[0], { x: W / 2, y: H * 0.93, size: 17 * u, align: "center", maxW: W * 0.86, color: MUTED, alpha: fade(v, 1) });
    },
    eranos(v) {
      const { W, H, u } = v;
      const y = text(v.s.h, { x: W / 2, y: H * 0.34, size: 38 * u, weight: 700, align: "center", maxW: W * 0.82, shown: typed(v, 0.1, 40) });
      const y2 = text(v.s.ps[0], { x: W / 2, y: y + 24 * u, size: 25 * u, align: "center", maxW: W * 0.68, alpha: fade(v, 3), color: SOFT });
      text(v.s.ps[1], { x: W / 2, y: y2 + 30 * u, size: 26 * u, align: "center", maxW: W * 0.8, alpha: fade(v, 6), color: BLUE });
    },
    connect(v) {
      const y = text(v.s.h, { x: v.W / 2, y: v.H * 0.44, size: 72 * v.u, weight: 700, align: "center", maxW: v.W * 0.9, shown: typed(v, 0.1, 24) });
      text(v.s.ps[0], { x: v.W / 2, y: y + 30 * v.u, size: 26 * v.u, align: "center", maxW: v.W * 0.86, shown: typed(v, 1.4, 38), caret: true });
    },
  };

  function frame(now) {
    F.now = now;
    const dt = F.last ? Math.min(0.1, (now - F.last) / 1000) : 0;
    F.last = now;
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
      const s = scenes[idx], rest = reduced && !F.playing, t = rest ? s.secs + 60 : F.t - s.start;
      c.globalAlpha = rest || idx === scenes.length - 1 ? 1 : clamp((s.secs - t) / 0.3);
      draw[s.kind]({ W, H, u: Math.max(0.42, Math.min(W / 1280, H / 720)), t, s });
      c.globalAlpha = 1; c.fillStyle = INK; c.fillRect(0, H - 2, W * (F.t / total), 2);
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
  btnToggle.addEventListener("click", () => { if (F.t >= total) F.t = 0; F.playing = !F.playing; label(); });
  label();
  requestAnimationFrame(frame);
})();
