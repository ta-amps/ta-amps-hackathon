// Browser checks for every page, against a running copy of the Worker (wrangler dev or a deploy).
//   node tests/check_site.mjs --base http://127.0.0.1:8799 [--shots DIR]
// For each page, at 1280x613 (scale 1.5) and 390x844, under the light and the dark colour scheme:
//   light   no opaque element (background alpha > 0.5) larger than 5% of the viewport with luminance
//           below 0.25 (no exemptions); body paper rgb(245, 242, 234); color-scheme "only light"
//   layout  no sideways scroll; the agent banner above the header nav; one footer row of links
//   text    no text under 14 px (13 px for monospace)
//   console no console errors, page errors or CSP violations
//   banner  the shared <ta-agent-banner> rendered from its inline noun (data-ready)
//   bands   at 1280 wide, every .band is at most 1280x450, so each one can be filmed as it is
//   setup   on /start/: the browser writes the same default setup the build wrote, and every setting changes it
// Then axe (WCAG 2.2 A/AA and best practice) per page and width: no serious or critical issue.
// Exit 1 on any failure. Needs Playwright and axe-core; set PLAYWRIGHT and AXE to override paths.
import { createRequire } from "node:module";
import { readFile, mkdir } from "node:fs/promises";

const require = createRequire(import.meta.url);
const PLAYWRIGHT = process.env.PLAYWRIGHT || "/home/username/meta_hacakthon/notes/claude-work-2026-10-31/herma/herma-src/node_modules/playwright";
const AXE = process.env.AXE || "/home/username/meta_hacakthon/eranos/web/node_modules/.pnpm/axe-core@4.14.0/node_modules/axe-core/axe.min.js";
const { chromium } = require(PLAYWRIGHT);

const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const BASE = opt("--base", "http://127.0.0.1:8799").replace(/\/$/, "");
const SHOTS = opt("--shots", "");

const PAGES = [
  { path: "/", name: "home" },
  { path: "/start/", name: "start" },
  { path: "/fabric/", name: "fabric" },
  { path: "/video/", name: "video" },
  { path: "/benchmarks/", name: "benchmarks" },
  { path: "/benchmarks/methodology/", name: "methodology" },
  { path: "/free/", name: "free" },
  { path: "/docs/", name: "docs" },
  { path: "/status/", name: "status" },
  { path: "/security/", name: "security" },
  { path: "/privacy/", name: "privacy" },
  { path: "/terms/", name: "terms" },
  { path: "/company/", name: "company" },
  { path: "/this-page-does-not-exist/", name: "not-found", status: 404 },
];
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 613, deviceScaleFactor: 1.5 },
  { name: "phone", width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
];
const SCHEMES = ["light", "dark"];
const PAPER = "rgb(245, 242, 234)";

function inPage() {
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const vw = window.innerWidth, vh = window.innerHeight;
  const out = { dark: [], small: [], errors: [] };
  for (const el of document.querySelectorAll("body, body *")) {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const r = el.getBoundingClientRect();
    const bg = parse(cs.backgroundColor);
    if (bg && bg.a > 0.5 && r.width * r.height > 0.05 * vw * vh && lum(bg) < 0.25) {
      out.dark.push(`${el.tagName.toLowerCase()}.${el.className} ${Math.round(r.width)}x${Math.round(r.height)} ${cs.backgroundColor}`);
    }
    const ownText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (ownText && r.width > 0) {
      const size = parseFloat(cs.fontSize);
      const mono = /mono/i.test(cs.fontFamily.split(",")[0]);
      if (size < (mono ? 13 : 14) - 0.01) out.small.push(`${el.tagName.toLowerCase()}.${el.className} ${size}px "${el.textContent.trim().slice(0, 40)}"`);
    }
  }
  out.body = getComputedStyle(document.body).backgroundColor;
  out.html = getComputedStyle(document.documentElement).backgroundColor;
  out.scheme = getComputedStyle(document.documentElement).colorScheme;
  out.meta = document.querySelector('meta[name="color-scheme"]')?.content || null;
  out.overflow = document.documentElement.scrollWidth - window.innerWidth;
  const banner = document.querySelector(".agent-banner");
  const header = document.querySelector(".site-header");
  out.bannerFirst = !!(banner && header && (banner.compareDocumentPosition(header) & Node.DOCUMENT_POSITION_FOLLOWING) && banner.getBoundingClientRect().bottom <= header.getBoundingClientRect().top + 1);
  out.banners = document.querySelectorAll(".agent-banner").length;
  const footer = document.querySelector("footer");
  out.footerLists = footer ? footer.querySelectorAll("ul").length : 0;
  const links = footer ? [...footer.querySelectorAll(".site-footer__links a")] : [];
  const tops = new Set(links.map((a) => Math.round(a.getBoundingClientRect().top)));
  out.footerRows = tops.size;
  out.footerLines = footer ? footer.querySelectorAll("p").length : 0;
  out.h1 = document.querySelectorAll("h1").length;
  out.bannerReady = banner ? banner.dataset.ready === "true" : false;
  out.bands = [...document.querySelectorAll(".band")].map((b) => {
    const r = b.getBoundingClientRect();
    return { id: b.id, w: Math.round(r.width), h: Math.round(r.height) };
  });
  out.storage = (() => { try { return localStorage.length + sessionStorage.length; } catch { return -1; } })();
  out.cookies = document.cookie.length;
  out.title = document.title;
  out.ogSiteName = document.querySelector('meta[property="og:site_name"]')?.content || "";
  out.ogImage = document.querySelector('meta[property="og:image"]')?.content || "";
  out.headerImgAlt = document.querySelector(".site-header img")?.alt || "";
  out.footerBrand = document.querySelector("footer b")?.innerText || "";
  out.footerLineText = document.querySelector("footer p")?.innerText || "";
  out.imgsOk = [...document.images].every((i) => i.complete && i.naturalWidth > 0);
  return out;
}

async function checkBenchmarks(page, where) {
  const total = await page.$$eval("[data-bench-group]", (els) => els.length);
  if (total !== 5) fail(where, `benchmarks: expected 5 groups, got ${total}`);
  for (const tag of ["new", "reuse", "queue", "model", "checks"]) {
    await page.click(`[data-bench-filter="${tag}"]`);
    const pressed = await page.$eval(`[data-bench-filter="${tag}"]`, (el) => el.getAttribute("aria-pressed"));
    const visible = await page.$$eval("[data-bench-group]", (els) => els.filter((el) => !el.hidden).length);
    if (pressed !== "true") fail(where, `benchmarks: chip ${tag} aria-pressed=${pressed}`);
    if (visible !== 1) fail(where, `benchmarks: chip ${tag} showed ${visible} groups instead of 1`);
  }
  await page.click('[data-bench-filter="all"]');
  const restored = await page.$$eval("[data-bench-group]", (els) => els.filter((el) => !el.hidden).length);
  if (restored !== total) fail(where, `benchmarks: chip all showed ${restored} of ${total} groups`);
}

async function checkVideo(page, where) {
  const info = await page.evaluate(() => {
    const v = document.querySelector(".video-player video");
    const tr = document.querySelectorAll(".video-transcript p").length;
    const dl = document.querySelector('.video-body a[download][href$=".mp4"]');
    const track = v ? v.querySelector('track[kind="captions"][default]') : null;
    return {
      exists: !!v,
      controls: v ? v.controls : false,
      autoplay: v ? v.autoplay : true,
      poster: v ? v.getAttribute("poster") || "" : "",
      trackSrc: track ? track.getAttribute("src") || "" : "",
      transcriptRows: tr,
      downloadHref: dl ? dl.getAttribute("href") || "" : "",
    };
  });
  if (!info.exists || !info.controls) fail(where, "video: missing click-to-play <video controls>");
  if (info.autoplay) fail(where, "video: autoplay must be off");
  if (!info.poster.endsWith(".svg")) fail(where, `video: missing light SVG poster (${info.poster})`);
  if (!info.trackSrc.endsWith(".vtt")) fail(where, `video: missing default WebVTT captions (${info.trackSrc})`);
  if (info.transcriptRows < 4) fail(where, `video: expected >= 4 transcript rows, got ${info.transcriptRows}`);
  if (!info.downloadHref.endsWith(".mp4")) fail(where, `video: missing direct MP4 download link (${info.downloadHref})`);
}

// The setup writer: the default the browser shows equals the one the build wrote, and each setting changes it.
async function checkSetup(page, where) {
  const raw = await (await page.request.get(page.url())).text();
  const built = raw.match(/<code data-setup-output>([\s\S]*?)<\/code>/)[1]
    .replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
  const shown = () => page.$eval("[data-setup-output]", (el) => el.textContent);
  if ((await shown()) !== built) fail(where, "setup: the browser's default setup differs from the built one");
  await page.click("summary");
  const steps = [
    ["goal: add", () => page.check('input[name="goal"][value="add"]')],
    ["via: mcp", () => page.check('input[name="via"][value="mcp"]')],
    ["show: commands", () => page.check('input[name="show"][value="commands"]')],
    ["agent name", () => page.fill('input[name="agent"]', "field-agent")],
    ["queue", () => page.selectOption('select[name="queue"]', "demo.ping")],
    ["map off", () => page.uncheck('input[name="map"]')],
    ["show: values", () => page.check('input[name="show"][value="values"]')],
    ["show: agent", () => page.check('input[name="show"][value="agent"]')],
    ["via: http", () => page.check('input[name="via"][value="http"]')],
    ["goal: work", () => page.check('input[name="goal"][value="work"]')],
  ];
  for (const [name, act] of steps) {
    const before = await shown();
    await act();
    if ((await shown()) === before) fail(where, `setup: changing ${name} left the setup the same (a dead setting)`);
  }
  const last = await shown();
  for (const want of ['"show_on_map":false', "field-agent", "demo.ping"]) if (!last.includes(want)) fail(where, `setup: the written setup lacks ${want}`);
  await page.fill('input[name="agent"]', "x\"; rm -rf / #");
  if ((await shown()).includes('"; rm')) fail(where, "setup: an agent name with quotes reached the setup uncleaned");
  await page.click("summary");
}

const failures = [];
const fail = (where, msg) => failures.push(`${where}: ${msg}`);
let checks = 0;

const browser = await chromium.launch();
const axeSource = await readFile(AXE, "utf8");
if (SHOTS) await mkdir(SHOTS, { recursive: true });

for (const vp of VIEWPORTS) {
  for (const scheme of SCHEMES) {
    const context = await browser.newContext({ ...vp, viewport: { width: vp.width, height: vp.height }, colorScheme: scheme, reducedMotion: "reduce" });
    for (const pg of PAGES) {
      const where = `${pg.name} ${vp.name} ${scheme}`;
      const page = await context.newPage();
      const problems = [];
      page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
      page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
      const res = await page.goto(BASE + pg.path, { waitUntil: "networkidle" });
      const expected = pg.status || 200;
      if (!res || res.status() !== expected) fail(where, `status ${res && res.status()} (expected ${expected})`);
      // The 404 page logs the browser's own "failed to load resource" line for the page itself.
      for (const p of problems) if (!(pg.status === 404 && /404/.test(p))) fail(where, p);
      const r = await page.evaluate(inPage);
      checks++;
      for (const d of r.dark) fail(where, `dark element ${d}`);
      for (const s of r.small) fail(where, `small text ${s}`);
      if (r.body !== PAPER) fail(where, `body background ${r.body}`);
      if (r.html !== PAPER) fail(where, `html background ${r.html}`);
      // Chrome reports the computed value as "light only"; both spellings mean the same thing.
      if (!["only light", "light only"].includes(r.scheme)) fail(where, `color-scheme ${r.scheme}`);
      if (r.meta !== "only light") fail(where, `meta color-scheme ${r.meta}`);
      if (r.overflow > 0) fail(where, `sideways scroll ${r.overflow}px`);
      if (!r.bannerFirst || r.banners !== 1) fail(where, "the agent banner is not the one block above the header");
      // One row of links (footer.v1.json: it wraps only when the screen is too narrow, so phones may wrap).
      if (r.footerLists !== 1 || r.footerLines !== 1 || (vp.name === "desktop" && r.footerRows !== 1)) fail(where, `footer lists ${r.footerLists}, rows ${r.footerRows}, lines ${r.footerLines}`);
      if (r.h1 !== 1) fail(where, `${r.h1} h1 elements`);
      if (!r.bannerReady) fail(where, "the shared agent banner did not render from its noun");
      if (vp.name === "desktop") for (const b of r.bands) if (b.w > 1280 || b.h > 450) fail(where, `band #${b.id} is ${b.w}x${b.h}, over 1280x450`);
      if (!r.title.includes("Teleion Labs") || /agora|ta-amps/i.test(r.title)) fail(where, `title ${r.title}`);
      if (r.ogSiteName !== "Teleion Labs") fail(where, `og:site_name ${r.ogSiteName}`);
      if (r.ogImage !== "https://teleionlabs.com/assets/og-teleion-1200x630.png") fail(where, `og:image ${r.ogImage}`);
      if (r.headerImgAlt !== "Teleion Labs") fail(where, `header img alt ${r.headerImgAlt}`);
      if (r.footerBrand !== "Teleion Labs") fail(where, `footer brand ${r.footerBrand}`);
      if (r.footerLineText !== "Teleion Labs Incorporated. Free through December 31, 2026.") fail(where, `footer line ${r.footerLineText}`);
      if (!r.imgsOk) fail(where, "broken image on page");
      if (pg.name === "start" && scheme === "light") await checkSetup(page, where);
      if (pg.name === "benchmarks" && scheme === "light") await checkBenchmarks(page, where);
      if (pg.name === "video" && scheme === "light") await checkVideo(page, where);
      if (r.storage !== 0 || r.cookies !== 0) fail(where, "browser storage or cookies used");
      if (pg.name === "home" || pg.name === "status") {
        const states = await page.$$eval("[data-service]", (els) => els.map((e) => e.dataset.state));
        if (!states.length || states.some((s) => s !== "up")) fail(where, `live strip states ${states.join(",")}`);
      }
      if (SHOTS && scheme === "dark") {
        await page.screenshot({ path: `${SHOTS}/${pg.name}-${vp.name}.png`, fullPage: false });
        if (pg.name === "home") await page.screenshot({ path: `${SHOTS}/${pg.name}-${vp.name}-full.png`, fullPage: true });
      }
      await page.close();
    }
    await context.close();
  }
}

// axe, in a context that lets the axe script in (the site's CSP blocks injected scripts).
let axeRuns = 0;
for (const vp of VIEWPORTS) {
  const context = await browser.newContext({ ...vp, viewport: { width: vp.width, height: vp.height }, bypassCSP: true });
  for (const pg of PAGES) {
    const page = await context.newPage();
    await page.goto(BASE + pg.path, { waitUntil: "networkidle" });
    await page.addScriptTag({ content: axeSource });
    const result = await page.evaluate(async () => window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] },
      resultTypes: ["violations"],
    }));
    axeRuns++;
    for (const v of result.violations) {
      if (v.impact === "serious" || v.impact === "critical") fail(`${pg.name} ${vp.name} axe`, `${v.impact} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);
      else console.log(`note: ${pg.name} ${vp.name} axe ${v.impact} ${v.id} (${v.nodes.length})`);
    }
    await page.close();
  }
  await context.close();
}
await browser.close();

console.log(`pages ${PAGES.length}, page loads checked ${checks} (2 widths x 2 schemes), axe runs ${axeRuns}`);
if (failures.length) {
  console.log(`FAIL ${failures.length}`);
  for (const f of failures) console.log(`  ${f}`);
  process.exit(1);
}
console.log("PASS light, layout, text size, console, storage and axe (no serious or critical)");
