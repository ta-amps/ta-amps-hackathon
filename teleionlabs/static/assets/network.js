// Adapted from the existing Agora network surface. The network map (/network/) and optional strips: where workers connect and which Tasks they
// claim, from the same-origin GET /api/network adapter for Herma's public GET /q/network (the contract in notes/coordination-2026-10-31/claude-design-network-map.v1.json).
// It reads that one address at most once a minute while the page is visible, draws each data center the answer names at
// its latitude and longitude on the dot-matrix land (Equal Earth, constants in the page's geography), pulses a ring
// twice for each new claim (never with reduced motion), and keeps the feed, the table and the totals in step. Every
// word comes from the page's Task Object (the .nw-words block). Replay plays the last hour from the record in about
// ten seconds; Pause stops updates, pulses and the callout. Without this script the page keeps its text and a link.
// It keeps nothing in the browser and has no inline code and no eval: it runs under script-src 'self'.
(function () {
  "use strict";

  const reduceMotion = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  const KINDS = ["nonprofit", "shared", "check", "own"];
  const MAX_PULSES = 8;

  function readJson(root, cls) {
    const node = root.querySelector("script." + cls);
    if (!node) return null;
    try { return JSON.parse(node.textContent); } catch (e) { return null; }
  }

  // A noun's sentence with its places filled. "{n:one:many}" picks a word by the count (1 Task, 2 Tasks).
  function fill(template, values) {
    return String(template == null ? "" : template).replace(/\{(\w+)(?::([^:{}]*):([^:{}]*))?\}/g, (all, key, one, many) => {
      if (values[key] == null) return all;
      if (one !== undefined) return Number(values[key]) === 1 ? one : many;
      return String(values[key]);
    });
  }

  function make(tag, cls, words) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (words != null) node.textContent = words;
    return node;
  }

  const num = (v) => (typeof v === "number" && isFinite(v) && v >= 0 ? Math.floor(v) : 0);
  const str = (v) => (typeof v === "string" && v.trim() ? v : null);
  const time = (v) => { const t = Date.parse(v); return isFinite(t) ? t : null; };

  // Equal Earth, as the page's geography gives it (the same numbers tools/build_geo.py used for the land): a data center's
  // latitude and longitude as a position in the map's box, in percent of its width and height.
  const A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, M = Math.sqrt(3) / 2;
  function project(lon, lat, P) {
    const clamped = Math.max(P.lat_min, Math.min(P.lat_max, lat));
    const lam = (lon * Math.PI) / 180, phi = (clamped * Math.PI) / 180;
    const theta = Math.asin(M * Math.sin(phi));
    const t2 = theta * theta, t6 = t2 * t2 * t2;
    const x = (lam * Math.cos(theta)) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)));
    const y = theta * (A1 + A2 * t2 + t6 * (A3 + A4 * t2));
    return { left: ((x + P.x_max) * P.scale / P.width) * 100, top: ((P.y_top - y) * P.scale / P.height) * 100 };
  }

  // The answer, checked: only fields of the contract, only values of the right kind.
  function normalize(d) {
    if (!d || typeof d !== "object" || !d.totals || !Array.isArray(d.data_centres) || !Array.isArray(d.continents) || !Array.isArray(d.recent_claims) || time(d.generated_at) === null) return null;
    const kinds = (o) => { const out = {}; KINDS.forEach((k) => { out[k] = num(o && o[k]); }); return out; };
    const row = (r) => {
      const at = time(r && r.at);
      if (at === null || KINDS.indexOf(r.kind) < 0) return null;
      const via = r.via && typeof r.via === "object" ? r.via : {};
      return {
        at, kind: r.kind, kind_label: str(r.kind_label), title: str(r.title), place: str(r.place), worker_kind: r.worker_kind === "dedicated" ? "dedicated" : "volunteer",
        model: r.model && str(r.model.name) ? { name: r.model.name, declared: r.model.declared === true } : null, object_key: str(r.object_key),
        via: via.type === "data_centre" && str(via.code) ? { code: via.code, city: str(via.city), continent: str(via.continent) } : { code: null, city: null, continent: str(via.continent) },
      };
    };
    const rows = (list) => (Array.isArray(list) ? list : []).map(row).filter(Boolean);
    return {
      generated: time(d.generated_at), recentMinutes: num(d.recent_minutes) || 10,
      totals: { workers: num(d.totals.workers), centers: num(d.totals.data_centres), continents: num(d.totals.continents), claims: num(d.totals.claims), nonprofit: num(d.totals.nonprofit_claims) },
      centers: d.data_centres.filter((c) => c && str(c.code) && num(c.workers) >= 2 && typeof c.lat === "number" && typeof c.lon === "number" && isFinite(c.lat) && isFinite(c.lon)).map((c) => ({
        code: c.code, city: str(c.city) || c.code, continent: str(c.continent) || "", continent_code: str(c.continent_code), lat: c.lat, lon: c.lon, workers: num(c.workers), claims: num(c.claims), by_kind: kinds(c.by_kind), last: time(c.last_claim_at),
      })),
      continents: (Array.isArray(d.continents) ? d.continents : []).filter((c) => c && str(c.code)).map((c) => ({ code: c.code, name: str(c.name) || c.code, workers: num(c.workers), claims: num(c.claims), by_kind: kinds(c.by_kind) })),
      recent: rows(d.recent_claims),
      replay: d.replay && Array.isArray(d.replay.claims) ? rows(d.replay.claims) : null,
    };
  }

  function Network(root, options) {
    this.root = root;
    this.mode = root.getAttribute("data-mode") === "strip" ? "strip" : "page";
    this.site = root.getAttribute("data-site") || "eranos";
    this.words = options.words || readJson(root, "nw-words");
    this.geo = options.geo || readJson(root, "nw-geo");
    this.source = options.source || root.getAttribute("data-source");
    this.kind = "all";
    this.data = null;
    this.skew = 0;
    this.failed = false;
    this.seen = null; // the time of the newest claim already pulsed
    this.paused = false;
    this.table = false;
    this.replaying = null;
    this.replayPending = false;
    this.replayGeneration = 0;
    this.loadGeneration = 0;
    this.timer = 0;
    this.nodes = { dots: new Map(), pills: new Map() };
    this.openCode = null;
    this.totalsAt = 0;
    this.find = (name) => root.querySelector("[data-" + name + "]");
    this.layer = this.find("layer");
    this.pulses = this.find("pulses");
  }

  const MISSES_BEFORE_BACKOFF = 3, BACKOFF_MS = 5 * 60 * 1000;  // review, Nov 2: failed reads back off
  const MAX_WAIT_MS = 60 * 60 * 1000;  // no automatic read waits longer than an hour
  const DEFAULT_WAIT_MS = 60 * 1000;  // a delay that is not a number waits a minute (review nit, Nov 2)

  Network.prototype.now = function () { return Date.now() - this.skew; };

  Network.prototype.start = function () {
    if (!this.words || !this.geo || !this.source || !this.layer) return;
    const self = this;
    // At most one read a minute (review B2, Nov 2): the noun's refresh_seconds, never under 60.
    this.refresh = Math.max(60, num(this.words.refresh_seconds) || 60) * 1000;
    this.lastRead = 0;
    if (this.mode === "page") {
      const wanted = new URLSearchParams(location.search).get("kind");
      if (KINDS.indexOf(wanted) >= 0) this.kind = wanted;
      this.controls();
    }
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        clearTimeout(self.timer); self.timer = 0; self.cancelRead();
        if (self.replayPending || self.replaying) self.stopReplay(true);
        return;
      }
      if (self.timer || self.paused || self.replaying || self.replayPending) return;
      // Back on the tab: read now only when the last read is a minute old or more; otherwise wait out the minute.
      const since = Date.now() - self.lastRead;
      if (since >= self.refresh) self.load(); else self.schedule(self.refresh - since);
    });
    window.setInterval(() => self.tick(), 15000);
    let resized = 0;
    window.addEventListener("resize", () => {
      window.clearTimeout(resized);
      resized = window.setTimeout(() => { const d = self.replaying ? self.replaying.shell : self.data; if (d) self.places(d); }, 150);
    });
    this.load();
  };

  // --- controls ------------------------------------------------------------------------------------------------------

  Network.prototype.controls = function () {
    const self = this, w = this.words.controls;
    const act = (name) => this.root.querySelector('[data-act="' + name + '"]');
    const bind = (name, on, labels) => {
      const b = act(name);
      if (!b) return;
      b.hidden = false;
      b.addEventListener("click", () => {
        const pressed = b.getAttribute("aria-pressed") !== "true";
        b.setAttribute("aria-pressed", pressed ? "true" : "false");
        b.querySelector("span").textContent = pressed ? labels[1] : labels[0];
        on(pressed);
      });
    };
    bind("replay", (on) => (on ? self.startReplay() : self.stopReplay()), [w.replay, w.replay_stop]);
    bind("pause", (on) => self.setPaused(on), [w.pause, w.resume]);
    bind("table", (on) => self.setTable(on), [w.table, w.map]);
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && self.openCode) self.closeCard(true); });
  };

  Network.prototype.setPaused = function (on) {
    this.paused = on;
    if (on) this.cancelRead();
    if (on && (this.replayPending || this.replaying)) this.stopReplay(true);
    clearTimeout(this.timer);
    this.timer = 0;
    if (on) { this.clearPulses(); this.render(false); } else if (!this.replaying) this.load();
    else this.render(false);
  };

  Network.prototype.setTable = function (on) {
    this.table = on;
    const map = this.find("view-map"), tables = this.find("view-table");
    if (map) map.hidden = on;
    if (tables) tables.hidden = !on;
    if (on) this.closeCard(false);
    this.render(false);
  };

  Network.prototype.setKind = function (kind) {
    if (kind === this.kind) return;
    this.kind = kind;
    try {
      const url = new URL(location.href);
      if (kind === "all") url.searchParams.delete("kind"); else url.searchParams.set("kind", kind);
      history.replaceState(null, "", url);
    } catch (e) { /* a page without history keeps the choice in the page only */ }
    this.seen = null;
    if (this.replaying || this.replayPending) { this.stopReplay(true); } else if (!this.paused) this.load(); else this.render(false);
  };

  // --- reading the answer -------------------------------------------------------------------------------------------

  Network.prototype.schedule = function (ms) {
    const self = this;
    // A delay that is not a number waits a minute, never an immediate read; none waits over an hour, so a timer's
    // delay stays far below the browser's limit.
    ms = typeof ms === "number" && !Number.isNaN(ms) ? Math.min(Math.max(0, ms), MAX_WAIT_MS) : DEFAULT_WAIT_MS;
    clearTimeout(this.timer);
    this.timer = document.hidden || this.paused || this.replaying || this.replayPending ? 0 : window.setTimeout(() => { self.timer = 0; self.load(); }, ms);
  };

  Network.prototype.status = function (message, link) {
    const node = this.find("status");
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
    if (!message) return;
    node.appendChild(document.createTextNode(message));
    if (link) {
      node.appendChild(document.createTextNode(" "));
      const a = make("a", null, link.text);
      a.href = link.href;
      node.appendChild(a);
    }
  };

  Network.prototype.address = function (replay) {
    const params = [];
    if (this.kind !== "all" && this.mode === "page") params.push("kind=" + encodeURIComponent(this.kind));
    if (replay) params.push("replay=1");
    return this.source + (params.length ? (this.source.indexOf("?") < 0 ? "?" : "&") + params.join("&") : "");
  };

  Network.prototype.fetchData = function (replay) {
    const self = this;
    const controller = window.AbortController ? new AbortController() : null;
    if (replay) this.replayController = controller; else this.loadController = controller;
    const stop = controller ? window.setTimeout(() => controller.abort(), 15000) : 0;
    return window.fetch(this.address(replay), { credentials: "omit", headers: { accept: "application/json" }, signal: controller ? controller.signal : undefined })
      .then((response) => {
        const retry = response.headers.get("retry-after");
        if (response.status === 429 || (response.status === 503 && retry)) {
          // Retry-After in seconds or as an HTTP date; never sooner than a minute.
          let seconds = Number(retry);
          if (!Number.isFinite(seconds)) { const at = Date.parse(retry || ""); seconds = Number.isFinite(at) ? Math.ceil((at - Date.now()) / 1000) : 0; }
          // Never under a minute or over an hour: a browser fires a timer over about 24.8 days at once, so an
          // unbounded Retry-After would poll in a tight loop (the review of c09566d measured 930 reads in 4 s).
          const wait = Math.min(Math.max(60, seconds || 0), 3600);
          const error = new Error("busy");
          error.wait = wait;
          throw error;
        }
        if (!response.ok) { const error = new Error("status " + response.status); error.status = response.status; throw error; }
        const age = Number(response.headers.get("age")) || 0;
        return response.json().then((json) => ({ json, age }));
      }).finally(() => {
        window.clearTimeout(stop);
        if (replay && self.replayController === controller) self.replayController = null;
        if (!replay && self.loadController === controller) self.loadController = null;
      });
  };

  Network.prototype.cancelRead = function () {
    this.loadGeneration++;
    if (this.loadController) this.loadController.abort();
    this.loadController = null;
  };

  Network.prototype.load = function () {
    if (document.hidden || this.paused || this.replaying || this.replayPending) return;
    this.cancelRead();
    const generation = this.loadGeneration;
    clearTimeout(this.timer); this.timer = 0;
    const self = this, asked = this.kind;
    this.lastRead = Date.now();
    this.fetchData(false).then((got) => {
      if (generation !== self.loadGeneration || asked !== self.kind || self.paused || document.hidden || self.replaying || self.replayPending) return;
      const data = normalize(got.json);
      if (!data) throw new Error("not an answer");
      self.skew = 0; // Source age never turns an old reading into a live one.
      self.failed = false;
      const fresh = self.data === null;
      self.data = data;
      self.status("");
      self.root.removeAttribute("data-failed");
      self.misses = 0;  // the first success ends any back-off
      self.render(!fresh);
      self.schedule(self.refresh);
    }).catch((error) => {
      if (generation !== self.loadGeneration || asked !== self.kind || self.paused || document.hidden || self.replaying || self.replayPending) return;
      self.failed = true;
      self.root.setAttribute("data-failed", "");
      self.clearPulses();
      if (self.data) self.render(false); else {
        self.root.setAttribute("data-state", "unknown");
        self.renderEmpty();
        const big = self.find("totals-big");
        if (big) big.textContent = self.words.freshness.unknown;
      }
      // Every failed read counts: any 4xx or 5xx, a network or CORS failure (an over-limit page without CORS reads as
      // one), a malformed answer. After 3 in a row the page reads on its own only every 5 minutes, until one read
      // succeeds; a click (a filter, Resume) still reads at once.
      self.misses = (self.misses || 0) + 1;
      const backoff = self.misses >= MISSES_BEFORE_BACKOFF ? BACKOFF_MS : 0;
      if (error && error.wait) {
        // The busy line says the real wait: the larger of the server's Retry-After and the back-off; a wait at the
        // one-hour cap reads "an hour" (review nit, Nov 2), and older words without that line keep the seconds.
        const delay = Math.min(Math.max(error.wait * 1000, backoff), MAX_WAIT_MS);
        self.status(delay >= MAX_WAIT_MS && self.words.busy_hour ? self.words.busy_hour
          : fill(self.words.busy, { seconds: Math.round(delay / 1000) }));
        self.schedule(delay);
        return;
      }
      self.root.setAttribute("data-failed", "");
      self.status(self.words.error.text, { text: self.words.error.link, href: self.words.herma.dashboard });
      self.schedule(Math.max(self.refresh, backoff));
    });
  };

  // --- words ---------------------------------------------------------------------------------------------------------

  Network.prototype.ago = function (at) {
    const seconds = Math.max(0, (this.now() - at) / 1000), a = this.words.ago;
    if (seconds < 10) return a.now;
    if (seconds < 60) return fill(a.seconds, { n: Math.floor(seconds) });
    if (seconds < 3600) return fill(a.minutes, { n: Math.floor(seconds / 60) });
    return fill(a.hours, { n: Math.floor(seconds / 3600) });
  };

  Network.prototype.kindLabel = function (r) { return r.kind_label || this.words.filter[r.kind] || r.kind; };

  Network.prototype.modelWords = function (r) {
    const f = this.words.feed;
    if (r.model) return r.model.declared ? fill(f.model_declared, { model: r.model.name }) : r.model.name;
    return r.worker_kind === "volunteer" ? f.model_none : f.model_not_used;
  };

  // The row as one line, by what the claim may be named by: its data center, its continent, or nothing.
  Network.prototype.rowTemplate = function (r, kind) {
    return r.via.code ? kind.row : r.via.continent ? kind.row_continent : kind.row_unplaced;
  };

  Network.prototype.rowValues = function (r) {
    return { kind: this.kindLabel(r), model: this.modelWords(r), city: r.via.city, continent: r.via.continent, ago: this.ago(r.at) };
  };

  Network.prototype.rowWords = function (r) {
    return fill(this.rowTemplate(r, this.words.feed), this.rowValues(r));
  };

  // Where a claim came through, for the table.
  Network.prototype.cameThrough = function (r) {
    const t = this.words.table;
    return fill(r.via.code ? t.came_center : r.via.continent ? t.came_continent : t.came_unplaced, { city: r.via.city, continent: r.via.continent });
  };

  // --- drawing -------------------------------------------------------------------------------------------------------

  Network.prototype.current = function () {
    return Boolean(this.data && !this.failed && Date.now() - this.data.generated <= 180000 && this.data.generated <= Date.now() + 60000);
  };

  Network.prototype.live = function () {
    const d = this.data;
    return Boolean(this.current() && d && d.recent.length && this.now() - d.recent[0].at < d.recentMinutes * 60000);
  };

  Network.prototype.render = function (polled) {
    const d = this.replaying ? this.replaying.shell : this.data;
    if (!d) return;
    const self = this;
    const card = this.find("feed-card");
    if (card) card.hidden = false;
    this.totals(d, false);
    this.places(d);
    if (this.mode === "strip") { this.strip(d, polled); return; }
    this.kinds(d);
    const rows = this.replaying ? this.replaying.shown : d.recent.filter((r) => self.kind === "all" || r.kind === self.kind);
    this.feed(d, rows);
    this.tables(d, rows);
    this.callout(d);
    this.cardRefresh(d);
    if (polled && !this.paused && !this.replaying && d.recent.length) this.pulseNew(d);
    else if (d.recent.length && this.seen === null) {
      this.seen = d.recent[0].at;
      if (this.live() && !this.paused) this.ring(d.recent[0]);
    }
    this.stateWords(d);
  };

  // Nothing real to show (the answer never came): no dots, no state chip, no claim.
  Network.prototype.renderEmpty = function () {
    this.places({ centers: [], continents: [], totals: { workers: 0 }, recent: [], recentMinutes: 10 });
    const svg = this.root.querySelector(".nw-world");
    if (svg) svg.setAttribute("aria-label", this.words.freshness.unknown);
    ["quiet", "empty", "feed-card"].forEach((name) => { const n = this.find(name); if (n) n.hidden = true; });
    const none = this.find("feed-empty");
    if (none) none.hidden = true;
  };

  Network.prototype.totals = function (d, force) {
    const big = this.find("totals-big"), sub = this.find("totals-sub"), w = this.words;
    if (this.mode === "strip") return;
    if (!big) return;
    // Spoken by a screen reader as a status, so it changes at most once a minute.
    if (!force && this.totalsAt && Date.now() - this.totalsAt < 60000) return;
    this.totalsAt = Date.now();
    big.textContent = fill(w.totals.big, { workers: d.totals.workers, data_centers: d.totals.centers });
    if (sub) sub.textContent = fill(w.totals.sub, { continents: d.totals.continents, claims: d.totals.claims, nonprofit_claims: d.totals.nonprofit });
  };

  // Data centers as buttons (the page) or dots (the strip), and continents as dashed pills, kept between answers so
  // focus stays where it is.
  Network.prototype.places = function (d) {
    const self = this, page = this.mode === "page", layer = this.layer, P = this.geo.projection;
    const width = layer.clientWidth || 800;
    const k = Math.max(0.55, Math.min(1, width / 800));
    const top = d.centers.slice().sort((a, b) => b.claims - a.claims).slice(0, page ? 8 : 0).map((c) => c.code);
    const seenCodes = new Set();
    d.centers.forEach((c) => {
      seenCodes.add(c.code);
      let node = self.nodes.dots.get(c.code);
      if (!node) {
        node = page ? make("button", "nw-dc") : make("span", "nw-dc");
        if (page) {
          node.type = "button";
          node.setAttribute("aria-expanded", "false");
          node.addEventListener("click", () => self.openCard(c.code, node));
        }
        node.appendChild(make("span", "nw-dot"));
        if (page) node.appendChild(make("span", "nw-label"));
        layer.appendChild(node);
        self.nodes.dots.set(c.code, node);
      }
      node.dataset.code = c.code;
      const at = project(c.lon, c.lat, P);
      node.style.left = at.left.toFixed(2) + "%";
      node.style.top = at.top.toFixed(2) + "%";
      node.style.setProperty("--d", Math.max(7, Math.round(Math.min(30, 10 + 4 * Math.sqrt(c.workers)) * k)) + "px");
      node.classList.toggle("is-hollow", self.kind !== "all" && c.by_kind[self.kind] === 0);
      node.classList.toggle("is-left", at.left > 80);
      if (page) {
        node.setAttribute("aria-label", fill(self.words.data_center.aria, { city: c.city, continent: c.continent }));
        const label = node.querySelector(".nw-label");
        label.textContent = top.indexOf(c.code) >= 0 ? c.city : "";
        label.hidden = top.indexOf(c.code) < 0;
      }
    });
    this.nodes.dots.forEach((node, code) => { if (!seenCodes.has(code)) { node.remove(); self.nodes.dots.delete(code); if (self.openCode === code) self.closeCard(false); } });
    const seenPills = new Set();
    d.continents.forEach((c) => {
      const anchor = self.geo.continents[c.code];
      if (!anchor) return;
      seenPills.add(c.code);
      let node = self.nodes.pills.get(c.code);
      if (!node) {
        node = make("span", "nw-pill");
        node.setAttribute("aria-hidden", "true");
        layer.appendChild(node);
        self.nodes.pills.set(c.code, node);
      }
      node.dataset.code = c.code;
      node.style.left = ((anchor[0] / self.geo.viewbox[2]) * 100).toFixed(2) + "%";
      node.style.top = ((anchor[1] / self.geo.viewbox[3]) * 100).toFixed(2) + "%";
      node.textContent = fill(c.workers === 1 ? self.words.continent_pill.one : self.words.continent_pill.many, { continent: c.name, workers: c.workers });
      node.classList.toggle("is-hollow", self.kind !== "all" && c.by_kind[self.kind] === 0);
    });
    this.nodes.pills.forEach((node, code) => { if (!seenPills.has(code)) { node.remove(); self.nodes.pills.delete(code); } });
    if (page) this.layoutPills();
    const empty = !d.centers.length && !d.continents.length && !d.totals.workers;
    const sentence = empty ? this.words.map_aria.empty : fill(this.words.map_aria.some, {
      centers: d.centers.length ? d.centers.map((c) => fill(this.words.map_aria.center, { city: c.city, workers: c.workers })).join(", ") : this.words.map_aria.centers_none,
      continents: d.continents.length ? d.continents.map((c) => c.name + " (" + c.workers + ")").join(", ") : this.words.map_aria.continents_none,
      claims: d.totals.claims,
    });
    const svg = this.root.querySelector(".nw-world");
    if (svg && page) svg.setAttribute("aria-label", sentence);
  };

  // A continent's pill sits at its fixed point; where it would overlap another pill, a data center or its label, or run past
  // the map's edge, it moves the least that keeps them apart and inside.
  Network.prototype.layoutPills = function () {
    const sw = this.layer.clientWidth, sh = this.layer.clientHeight;
    if (!sw || !sh) return;
    const base = this.layer.getBoundingClientRect();
    const rect = (node) => { const r = node.getBoundingClientRect(); return { l: r.left - base.left, t: r.top - base.top, r: r.right - base.left, b: r.bottom - base.top }; };
    // What a pill must keep clear of: every data center's dot and its label.
    const fixed = [];
    this.nodes.dots.forEach((node) => {
      const dot = node.querySelector(".nw-dot"), label = node.querySelector(".nw-label");
      if (dot) fixed.push(rect(dot));
      if (label && !label.hidden) fixed.push(rect(label));
    });
    const boxes = [];
    this.nodes.pills.forEach((node) => {
      boxes.push({ node, w: node.offsetWidth, h: node.offsetHeight, x: (parseFloat(node.style.left) / 100) * sw, y: (parseFloat(node.style.top) / 100) * sh });
    });
    boxes.sort((a, b) => a.y - b.y || a.x - b.x);
    const hits = (b, o) => b.x - b.w / 2 < o.r + 3 && b.x + b.w / 2 > o.l - 3 && b.y - b.h / 2 < o.b + 3 && b.y + b.h / 2 > o.t - 3;
    boxes.forEach((b, i) => {
      b.x = Math.max(b.w / 2 + 2, Math.min(b.x, sw - b.w / 2 - 2));
      b.y = Math.max(b.h / 2 + 2, Math.min(b.y, sh - b.h / 2 - 2));
      const others = fixed.concat(boxes.slice(0, i).map((a) => ({ l: a.x - a.w / 2, t: a.y - a.h / 2, r: a.x + a.w / 2, b: a.y + a.h / 2 })));
      for (let n = 0; n < 8; n++) {
        const hit = others.filter((o) => hits(b, o))[0];
        if (!hit) break;
        b.y = hit.b + b.h / 2 + 4;
      }
      b.y = Math.min(b.y, sh - b.h / 2 - 2);
    });
    boxes.forEach((b) => { b.node.style.left = b.x.toFixed(1) + "px"; b.node.style.top = b.y.toFixed(1) + "px"; });
  };

  Network.prototype.kinds = function (d) {
    const box = this.find("kinds");
    if (!box) return;
    const has = (k) => d.centers.some((c) => c.by_kind[k] > 0) || d.continents.some((c) => c.by_kind[k] > 0) || d.recent.some((r) => r.kind === k);
    const wanted = ["all"].concat(KINDS.filter((k) => k !== "own" || has("own")));
    const signature = wanted.join(",") + "|" + this.kind;
    if (box.getAttribute("data-signature") === signature) return;
    box.setAttribute("data-signature", signature);
    Array.prototype.slice.call(box.querySelectorAll("button")).forEach((b) => b.remove());
    box.hidden = false;
    const self = this;
    wanted.forEach((kind) => {
      const b = make("button", "nw-choice", self.words.filter[kind]);
      b.type = "button";
      b.setAttribute("aria-pressed", kind === self.kind ? "true" : "false");
      b.addEventListener("click", () => self.setKind(kind));
      box.appendChild(b);
    });
  };

  Network.prototype.stateWords = function (d) {
    const f = this.words.feed;
    const state = this.replaying ? "replay" : this.paused ? "paused" : !this.current() ? "stale" : this.live() ? "live" : "quiet";
    const freshness = this.find("freshness");
    if (freshness) freshness.textContent = fill(this.words.freshness[this.current() ? "current" : "stale"], { time: new Date(d.generated).toLocaleString() });
    const chip = this.find("state-chip");
    if (chip) { chip.hidden = false; chip.textContent = f.state[state]; chip.setAttribute("data-state", state); }
    const title = this.find("feed-title");
    if (title) title.textContent = ["quiet", "stale"].includes(state) ? f.title_quiet : f.title;
    const quiet = this.find("quiet");
    if (quiet) {
      const none = (d.centers.length || d.continents.length) && state === "quiet" && !this.replaying;
      quiet.hidden = !none || this.table;
      quiet.textContent = none ? this.words.quiet : "";
    }
    const empty = this.find("empty");
    if (empty) {
      const nobody = !d.centers.length && !d.continents.length && !d.totals.workers;
      empty.hidden = !nobody || this.table;
      empty.textContent = nobody ? this.words.empty : "";
    }
    this.root.setAttribute("data-state", state);
  };

  Network.prototype.feed = function (d, rows) {
    const self = this, list = this.find("feed"), none = this.find("feed-empty"), f = this.words.feed;
    if (!list) return;
    const before = this.feedTop;
    this.feedTop = rows.length ? rows[0].at : before;
    while (list.firstChild) list.removeChild(list.firstChild);
    rows.forEach((r) => {
      const item = make("li", "nw-item is-" + r.worker_kind);
      if (before !== undefined && r.at > before && !reduceMotion.matches && !self.paused) item.classList.add("is-new");
      item.appendChild(make("span", "nw-tile"));
      const body = make("div", "nw-item-body");
      // "{kind} claimed" in bold, then the rest up to {ago}, then the time, which keeps counting on.
      const lead = fill(self.rowTemplate(r, f).split("{ago}")[0], self.rowValues(r));
      const cut = lead.indexOf(" · ");
      const what = make("p", "nw-item-what");
      what.appendChild(make("b", null, cut < 0 ? lead : lead.slice(0, cut)));
      what.appendChild(document.createTextNode(cut < 0 ? "" : lead.slice(cut)));
      const when = make("time", null, self.ago(r.at));
      when.setAttribute("data-at", String(r.at));
      when.setAttribute("datetime", new Date(r.at).toISOString());
      what.appendChild(when);
      body.appendChild(what);
      if (r.title) {
        const line = make("p", "nw-item-title");
        if (r.object_key && self.words.herma.contribution) {
          const a = make("a", null, r.title);
          a.href = fill(self.words.herma.contribution, { object_key: encodeURIComponent(r.object_key) });
          line.appendChild(a);
        } else line.textContent = r.title;
        body.appendChild(line);
      }
      const chips = make("p", "nw-chips");
      chips.appendChild(make("span", "nw-chip", f.who[r.worker_kind]));
      chips.appendChild(make("span", "nw-chip", r.place ? fill(f.place, { place: r.place }) : f.place_none));
      body.appendChild(chips);
      item.appendChild(body);
      list.appendChild(item);
    });
    if (none) {
      none.hidden = rows.length > 0;
      none.textContent = rows.length ? "" : this.kind !== "all" ? this.words.filter.none : f.empty;
    }
  };

  Network.prototype.tables = function (d, rows) {
    const t = this.words.table, self = this;
    const centers = this.find("rows-centers"), claims = this.find("rows-claims");
    if (!centers || !claims) return;
    while (centers.firstChild) centers.removeChild(centers.firstChild);
    while (claims.firstChild) claims.removeChild(claims.firstChild);
    const cell = (tag, words, scope) => { const n = make(tag, null, words); if (scope) n.scope = scope; return n; };
    d.centers.forEach((c) => {
      const tr = make("tr");
      tr.appendChild(cell("th", c.city + " (" + c.code + ")", "row"));
      tr.appendChild(cell("td", c.continent));
      tr.appendChild(cell("td", String(c.workers)));
      tr.appendChild(cell("td", String(c.claims)));
      centers.appendChild(tr);
    });
    d.continents.forEach((c) => {
      const tr = make("tr");
      tr.appendChild(cell("th", t.continent_row, "row"));
      tr.appendChild(cell("td", c.name));
      tr.appendChild(cell("td", String(c.workers)));
      tr.appendChild(cell("td", String(c.claims)));
      centers.appendChild(tr);
    });
    const recent = rows.filter((r) => this.now() - r.at < d.recentMinutes * 60000 || this.replaying);
    recent.forEach((r) => {
      const tr = make("tr");
      tr.appendChild(cell("th", self.ago(r.at), "row"));
      tr.appendChild(cell("td", r.title || t.no_title));
      tr.appendChild(cell("td", self.kindLabel(r)));
      tr.appendChild(cell("td", self.modelWords(r)));
      tr.appendChild(cell("td", self.cameThrough(r)));
      claims.appendChild(tr);
    });
    if (!recent.length) {
      const tr = make("tr"), td = make("td", "nw-table-empty", t.claims_empty);
      td.colSpan = 5;
      tr.appendChild(td);
      claims.appendChild(tr);
    }
  };

  // --- the newest claim: a pill beside its data center, and rings ----------------------------------------------------

  Network.prototype.callout = function (d) {
    const old = this.find("callout");
    if (old) old.remove();
    if (this.paused || this.replaying || this.table || !this.live()) return;
    const r = d.recent.filter((x) => this.kind === "all" || x.kind === this.kind)[0];
    if (!r || !r.via.code) return;
    const dc = this.nodes.dots.get(r.via.code);
    if (!dc) return;
    const pill = make("span", "nw-callout", fill(this.words.callout, { kind: this.kindLabel(r), ago: this.ago(r.at) }));
    pill.setAttribute("data-callout", "");
    pill.setAttribute("aria-hidden", "true");
    pill.style.left = dc.style.left;
    pill.style.top = dc.style.top;
    if (parseFloat(dc.style.top) < 22) pill.classList.add("is-below");
    this.pulses.appendChild(pill);
  };

  Network.prototype.clearPulses = function () {
    Array.prototype.slice.call(this.pulses.querySelectorAll(".nw-ring")).forEach((n) => n.remove());
  };

  Network.prototype.ring = function (r) {
    if (reduceMotion.matches) return;
    let node = null;
    if (r.via.code) node = this.nodes.dots.get(r.via.code);
    else if (this.data) {
      const named = this.data.continents.filter((c) => c.name === r.via.continent)[0];
      node = named ? this.nodes.pills.get(named.code) : null;
    }
    if (!node) return;
    const ring = make("span", "nw-ring");
    ring.style.left = node.style.left;
    ring.style.top = node.style.top;
    window.setTimeout(() => { if (ring.parentNode) ring.parentNode.removeChild(ring); }, 5200);
    this.pulses.appendChild(ring);
  };

  // A ring twice (2.4 s each, so never longer than five seconds) for each claim newer than the last one pulsed.
  Network.prototype.pulseNew = function (d) {
    const self = this;
    const fresh = d.recent.filter((r) => this.seen !== null && r.at > this.seen && (this.kind === "all" || r.kind === this.kind));
    this.seen = Math.max(this.seen === null ? 0 : this.seen, d.recent[0].at);
    fresh.slice(0, MAX_PULSES).reverse().forEach((r, i) => window.setTimeout(() => { if (!self.paused && !self.replaying) self.ring(r); }, i * 350));
  };

  // The strip: the same dots without labels or buttons, one headline, the last claim, and a ring for the newest claim
  // when it loads or when a new one arrives.
  Network.prototype.strip = function (d, polled) {
    const s = this.words.strip[this.site] || this.words.strip.eranos;
    const headline = this.find("headline"), sub = this.find("sub"), last = this.find("last");
    if (headline) headline.textContent = fill(s.headline, { workers: d.totals.workers, continents: d.totals.continents });
    if (sub) sub.textContent = fill(s.sub, { nonprofit_claims: d.totals.nonprofit, workers: d.totals.workers });
    const r = d.recent[0];
    if (last) {
      if (!r) { last.hidden = false; last.textContent = s.quiet; } else {
        last.hidden = false;
        last.textContent = fill(r.via.code ? s.last : r.via.continent ? s.last_continent : s.last_unplaced, { kind: this.kindLabel(r), model: this.modelWords(r), city: r.via.city, continent: r.via.continent, ago: this.ago(r.at) });
      }
    }
    if (r && (this.seen === null || (polled && r.at > this.seen))) { if (this.seen === null || this.live()) this.ring(r); }
    if (r) this.seen = Math.max(this.seen === null ? 0 : this.seen, r.at);
  };

  // --- one data center's numbers -------------------------------------------------------------------------------------

  Network.prototype.openCard = function (code, button) {
    const d = this.data, c = d && d.centers.filter((x) => x.code === code)[0], card = this.find("card");
    if (!c || !card) return;
    this.closeCard(false);
    const w = this.words.data_center;
    while (card.firstChild) card.removeChild(card.firstChild);
    const head = make("h2", "nw-card-title", fill(w.card_title, { city: c.city }));  // under the page's h1
    head.tabIndex = -1;
    const close = make("button", "nw-card-close", "✕");
    close.type = "button";
    close.setAttribute("aria-label", w.close);
    const self = this;
    close.addEventListener("click", () => self.closeCard(true));
    card.appendChild(close);
    card.appendChild(head);
    card.appendChild(make("p", "nw-card-continent", c.continent));
    card.appendChild(make("p", "nw-card-counts", fill(w.card_counts, { workers: c.workers, claims: c.claims })));
    card.appendChild(make("p", "nw-card-note", w.card_note));
    card.hidden = false;
    // Beside the dot, on the side with room, and kept inside the map.
    const stage = card.parentNode, sw = stage.clientWidth, sh = stage.clientHeight;
    const x = (parseFloat(button.style.left) / 100) * sw, y = (parseFloat(button.style.top) / 100) * sh;
    const cw = card.offsetWidth, ch = card.offsetHeight, gap = 22;
    let left = x + gap;
    if (left + cw > sw) left = x - gap - cw;
    card.style.left = Math.max(0, Math.min(left, sw - cw)) + "px";
    card.style.top = Math.max(0, Math.min(y - ch / 2, sh - ch)) + "px";
    button.setAttribute("aria-expanded", "true");
    this.openCode = code;
    this.opener = button;
    head.focus();
  };

  Network.prototype.cardRefresh = function (d) {
    if (!this.openCode) return;
    const c = d.centers.filter((x) => x.code === this.openCode)[0], card = this.find("card");
    if (!c || !card) { this.closeCard(false); return; }
    const counts = card.querySelector(".nw-card-counts");
    if (counts) counts.textContent = fill(this.words.data_center.card_counts, { workers: c.workers, claims: c.claims });
  };

  Network.prototype.closeCard = function (giveFocusBack) {
    const card = this.find("card");
    if (card) card.hidden = true;
    if (this.opener) this.opener.setAttribute("aria-expanded", "false");
    if (giveFocusBack && this.opener) this.opener.focus();
    this.openCode = null;
    this.opener = null;
  };

  // --- replay ---------------------------------------------------------------------------------------------------------

  // The last hour from the record, played in about ten seconds: each claim arrives at its turn with its ring. With
  // reduced motion every row is there at once.
  Network.prototype.startReplay = function () {
    const self = this;
    this.cancelRead();
    const generation = ++this.replayGeneration;
    if (this.replayController) this.replayController.abort();
    this.replayPending = true;
    clearTimeout(this.timer);
    this.timer = 0;
    this.clearPulses();
    const band = this.find("band");
    this.fetchData(true).then((got) => {
      if (generation !== self.replayGeneration || !self.replayPending) return;
      self.replayPending = false;
      const data = normalize(got.json);
      if (!data || !data.replay) throw new Error("no replay");
      const claims = data.replay.filter((r) => self.kind === "all" || r.kind === self.kind);
      self.replaying = { shell: self.data || data, claims, shown: [], steps: [] };
      if (band) band.hidden = false;
      const first = claims.length ? claims[0].at : 0, span = claims.length ? Math.max(1, claims[claims.length - 1].at - first) : 1;
      const total = num(self.words.replay_seconds) * 1000 || 10000;
      const batch = Math.max(1, Math.ceil(claims.length / 50)); // at most about fifty steps, so it stays near ten seconds
      const play = (i) => {
        if (!self.replaying || self.replaying.claims !== claims) return;
        if (i >= claims.length) { self.render(false); return; }
        const group = claims.slice(i, i + batch), r = group[group.length - 1];
        self.replaying.shown = group.slice().reverse().concat(self.replaying.shown).slice(0, 40);
        self.render(false);
        self.ring(r);
        const next = claims[i + batch];
        const wait = reduceMotion.matches ? 0 : next ? Math.max(120, Math.round(((next.at - r.at) / span) * total)) : 0;
        self.replaying.steps.push(window.setTimeout(() => play(i + batch), Math.min(wait, 1200)));
      };
      if (reduceMotion.matches) {
        self.replaying.shown = claims.slice().reverse().slice(0, 40);
        self.render(false);
      } else play(0);
      self.render(false);
    }).catch(() => {
      if (generation !== self.replayGeneration) return;
      self.replayPending = false;
      self.replaying = null;
      if (band) band.hidden = true;
      const b = self.root.querySelector('[data-act="replay"]');
      if (b) { b.setAttribute("aria-pressed", "false"); b.querySelector("span").textContent = self.words.controls.replay; }
      self.status(self.words.replay_error);
      if (self.data) self.render(false);
      self.schedule(self.refresh);
    });
  };

  Network.prototype.stopReplay = function (keepPressed) {
    this.replayGeneration++;
    this.replayPending = false;
    if (this.replayController) this.replayController.abort();
    this.replayController = null;
    if (this.replaying) this.replaying.steps.forEach((t) => clearTimeout(t));
    this.replaying = null;
    const band = this.find("band");
    if (band) band.hidden = true;
    this.clearPulses();
    this.seen = null;
    if (!this.paused && !document.hidden) this.load(); else this.render(false);
    if (keepPressed) {
      const b = this.root.querySelector('[data-act="replay"]');
      if (b) { b.setAttribute("aria-pressed", "false"); b.querySelector("span").textContent = this.words.controls.replay; }
    }
  };

  // Every 15 seconds the "ago" words move on, without a read, and a quiet map turns quiet.
  Network.prototype.tick = function () {
    const self = this;
    if (!this.data || document.hidden || this.paused) return;
    Array.prototype.forEach.call(this.root.querySelectorAll("time[data-at]"), (node) => { node.textContent = self.ago(Number(node.getAttribute("data-at"))); });
    if (this.mode === "strip") { this.strip(this.data, false); return; }
    this.stateWords(this.data);
    if (!this.live()) { const c = this.find("callout"); if (c) c.remove(); }
  };

  function mount(root, options) {
    if (!root || root.taNetwork) return root && root.taNetwork;
    options = options || {};
    const network = new Network(root, options);
    root.taNetwork = network;
    const geoUrl = root.getAttribute("data-geo");
    if (network.geo || !geoUrl) { network.start(); return network; }
    window.fetch(geoUrl, { credentials: "omit" }).then((r) => r.json()).then((geo) => {
      network.geo = geo;
      const svg = root.querySelector(".nw-world");
      if (svg && geo.dots && !svg.querySelector(".nw-land")) {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("class", "nw-land");
        path.setAttribute("d", geo.dots);
        svg.setAttribute("viewBox", geo.viewbox.join(" "));
        svg.appendChild(path);
      }
      network.start();
    }).catch(() => { /* without the geography the strip keeps its link */ });
    return network;
  }

  window.TaNetwork = { mount, project, normalize };
  Array.prototype.forEach.call(document.querySelectorAll("[data-network]"), (root) => mount(root));
})();
