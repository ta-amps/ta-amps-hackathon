// Browser checks for every page, against a running copy of the Worker (wrangler dev or a deploy).
//   node tests/check_site.mjs --base http://127.0.0.1:8799 [--shots DIR]
// For each page, at 1280x613 (scale 1.5) and 390x844, under the light and the dark colour scheme:
//   light   no opaque element (background alpha > 0.5) larger than 5% of the viewport with luminance
//           below 0.25 (no exemptions); body paper rgb(245, 242, 234); color-scheme "only light"
//   layout  no sideways scroll; the agent banner above the header nav; one footer row of links
//   text    no text under 14 px (13 px for monospace)
//   console no console errors, page errors or CSP violations
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
  { path: "/tessera/", name: "tessera" },
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
  out.storage = (() => { try { return localStorage.length + sessionStorage.length; } catch { return -1; } })();
  out.cookies = document.cookie.length;
  return out;
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
