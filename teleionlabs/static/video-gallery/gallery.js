// The owner's review catalog: permanent numbers, newest first, labels, filters, favorites, notes and compare. Notes stay in this browser.
(async () => {
  const root = document.getElementById("gal"), plain = document.getElementById("plain");
  const { items, picks = [] } = await (await fetch("/video-gallery/items.json", { cache: "no-store" })).json();
  const KEY = "teleion-gallery-v1";
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } };
  const state = load(); state.fav ||= {}; state.score ||= {}; state.note ||= {};
  const lastSeen = state.seen || ""; const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch {} };
  const q = new URLSearchParams(location.search);
  const el = (tag, cls, txt) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt !== undefined) n.textContent = txt; return n; };
  const uniq = (k) => [...new Set(items.map((i) => i[k]).filter(Boolean))].sort();
  const bar = el("div", "bar");
  const search = el("input"); search.type = "search"; search.placeholder = "Search words or a number, like 12"; search.setAttribute("aria-label", "Search"); search.value = q.get("q") || "";
  const selects = {};
  const addSelect = (key, label) => {
    const s = el("select"); s.setAttribute("aria-label", label); s.append(new Option("All: " + label, ""));
    uniq(key).forEach((v) => s.append(new Option(v, v))); s.value = q.get(key) || ""; selects[key] = s; bar.append(s);
  };
  bar.append(search);
  addSelect("type", "kinds"); addSelect("style", "styles"); addSelect("status", "status"); addSelect("audio", "sound");
  const mine = el("select"); mine.setAttribute("aria-label", "My picks");
  [["", "All: my picks"], ["fav", "Favorites"], ["noted", "With notes"], ["new", "New since my last visit"]].forEach(([v, t]) => mine.append(new Option(t, v)));
  mine.value = q.get("mine") || "";
  const sort = el("select"); sort.setAttribute("aria-label", "Sort");
  [["new", "Most recent"], ["old", "Oldest"], ["num", "Number"], ["score", "My score"], ["long", "Longest"], ["short", "Shortest"]].forEach(([v, t]) => sort.append(new Option(t, v)));
  sort.value = q.get("sort") || "new";
  const dl = el("button", "", "Download my notes"); const count = el("span", "count");
  bar.append(mine, sort, dl, count);
  const cmp = el("div"); cmp.id = "cmp"; const grid = el("div", "grid");
  const start = el("section"); start.id = "start";
  const fillStart = () => {
  if (picks.length) {
    start.append(el("h2", "", "Start here: our best starting points"), el("p", "", "Picked by hand, so you don't have to look through everything. Tell us which parts you like, by number, and we'll tune from there."));
    const pg = el("div", "grid");
    picks.forEach((p, n) => { const i = items.find((x) => x.id === p.id); if (!i) return; const c = card(i); const why = el("p", "why", p.why); const label = el("div", "rank", `Pick ${n + 1}`); c.querySelector(".body").prepend(label, why); pg.append(c); });
    start.append(pg, el("h2", "", "Everything else"));
  }
  };
  root.append(start, bar, cmp, grid); root.hidden = false; if (plain) plain.hidden = true;
  const clock = (s) => (s ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}` : "");
  const when = (d) => new Date(d).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  let compare = (q.get("compare") || "").split(",").filter(Boolean).map(Number);
  function drawCompare() {
    cmp.replaceChildren();
    compare.map((n) => items.find((i) => i.num === n)).filter(Boolean).forEach((i) => {
      const box = el("div"); box.append(el("h3", "", `#${i.num} ${i.title}`));
      if (i.video) { const v = el("video"); v.src = i.video; v.controls = true; v.preload = "metadata"; if (i.poster) v.poster = i.poster; box.append(v); }
      else { const a = el("a", "", "This one plays on its own page"); a.href = i.open; box.append(a); }
      cmp.append(box);
    });
  }
  function card(i) {
    const c = el("article", "card"); c.id = `v${i.num}`; if (compare.includes(i.num)) c.classList.add("sel");
    const th = el("button", "thumb"); th.setAttribute("aria-label", `Play number ${i.num}`);
    if (i.poster) { const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = i.poster; th.append(im); } else th.append(el("span", "none", i.video ? "Play" : "Opens in the browser"));
    th.append(el("span", "num", "#" + i.num)); if (i.seconds) th.append(el("span", "len", clock(i.seconds))); if (lastSeen && i.added > lastSeen) th.append(el("span", "new", "New"));
    th.onclick = () => { if (!i.video) { location.href = i.open; return; } const v = el("video"); v.src = i.video; v.controls = true; v.autoplay = true; if (i.poster) v.poster = i.poster; th.replaceWith(v); };
    const b = el("div", "body"); b.append(el("h2", "", i.title), el("div", "when", "Added " + when(i.added)), el("p", "", i.note || ""));
    const tags = el("div", "tags");
    for (const k of ["type", "style", "status", "audio"]) if (i[k]) { const t = el("button", "tag " + i[k], i[k]); t.title = "Show only " + i[k]; t.onclick = () => { selects[k].value = i[k]; draw(); }; tags.append(t); }
    const acts = el("div", "acts");
    const fav = el("button", "", "Favorite"); fav.setAttribute("aria-pressed", !!state.fav[i.num]); fav.onclick = () => { state.fav[i.num] = !state.fav[i.num]; fav.setAttribute("aria-pressed", state.fav[i.num]); save(); };
    const score = el("select"); score.setAttribute("aria-label", "Score"); ["Score", "1", "2", "3", "4", "5"].forEach((v, n) => score.append(new Option(v, n || ""))); score.value = state.score[i.num] || ""; score.onchange = () => { state.score[i.num] = score.value; save(); };
    const cm = el("button", "", "Compare"); cm.setAttribute("aria-pressed", compare.includes(i.num)); cm.onclick = () => { compare = compare.includes(i.num) ? compare.filter((n) => n !== i.num) : [...compare, i.num].slice(-2); fillStart(); drawCompare(); draw(); if (compare.length) cmp.scrollIntoView({ block: "nearest" }); };
    const open = el("a", "", "Open"); open.href = i.open;
    acts.append(fav, score, cm, open);
    const note = el("textarea"); note.placeholder = "Notes"; note.setAttribute("aria-label", `Notes on number ${i.num}`); note.value = state.note[i.num] || ""; note.onchange = () => { state.note[i.num] = note.value; save(); };
    b.append(tags, acts, note); c.append(th, b); return c;
  }
  function draw() {
    const w = search.value.trim().toLowerCase();
    let list = items.filter((i) => {
      if (w && !(/^#?\d+$/.test(w) ? String(i.num) === w.replace("#", "") : `${i.title} ${i.note} ${i.type} ${i.style} ${i.status}`.toLowerCase().includes(w))) return false;
      for (const k in selects) if (selects[k].value && i[k] !== selects[k].value) return false;
      if (mine.value === "fav" && !state.fav[i.num]) return false;
      if (mine.value === "noted" && !state.note[i.num]) return false;
      if (mine.value === "new" && !(lastSeen && i.added > lastSeen)) return false;
      return true;
    });
    const by = { new: (a, b) => (b.added > a.added ? 1 : b.added < a.added ? -1 : b.num - a.num), old: (a, b) => (a.added > b.added ? 1 : -1), num: (a, b) => a.num - b.num, score: (a, b) => (state.score[b.num] || 0) - (state.score[a.num] || 0), long: (a, b) => (b.seconds || 0) - (a.seconds || 0), short: (a, b) => (a.seconds || 0) - (b.seconds || 0) };
    list = list.sort(by[sort.value]);
    grid.replaceChildren(...list.map(card)); count.textContent = `${list.length} of ${items.length}`;
    const p = new URLSearchParams(); if (search.value) p.set("q", search.value); for (const k in selects) if (selects[k].value) p.set(k, selects[k].value); if (mine.value) p.set("mine", mine.value); if (sort.value !== "new") p.set("sort", sort.value); if (compare.length) p.set("compare", compare.join(","));
    history.replaceState(null, "", location.pathname + (p.size ? "?" + p : "") + location.hash);
  }
  search.oninput = draw; Object.values(selects).forEach((s) => (s.onchange = draw)); mine.onchange = draw; sort.onchange = draw;
  dl.onclick = () => {
    const out = items.filter((i) => state.fav[i.num] || state.score[i.num] || state.note[i.num]).map((i) => ({ number: i.num, title: i.title, favorite: !!state.fav[i.num], score: state.score[i.num] || null, note: state.note[i.num] || "" }));
    const a = el("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], { type: "application/json" })); a.download = "video-gallery-notes.json"; a.click();
  };
  fillStart(); drawCompare(); draw();
  if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
  addEventListener("pagehide", () => { state.seen = items.reduce((m, i) => (i.added > m ? i.added : m), ""); save(); });
})();
