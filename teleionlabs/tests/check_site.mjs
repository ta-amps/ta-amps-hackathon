// Browser checks for the text site, against a running copy of the Worker (wrangler dev or a deploy).
//   node tests/check_site.mjs --base http://127.0.0.1:8799
// For each page, at desktop and phone width, under the light and the dark colour scheme:
//   light   body paper rgb(245, 242, 234), color-scheme "only light", no dark element over 5% of the viewport
//   layout  no sideways scroll; the first line is for agents; one footer row of links plus one line
//   text    no stylesheet file, no font file, no images in the page
//   console no console errors, page errors or CSP violations
//   film    on the home page: the canvas shows and draws, its scenes add up to 180 s, and controls work
//   scripts film code runs on / and /experience/ only, from this site; Three.js and the 3D world on /experience/ only
// Then axe per page and width: no serious or critical issue. Exit 1 on any failure.
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";

const require = createRequire(import.meta.url);
const PLAYWRIGHT = process.env.PLAYWRIGHT || "/home/username/meta_hacakthon/notes/claude-work-2026-10-31/herma/herma-src/node_modules/playwright";
const AXE = process.env.AXE || "/home/username/meta_hacakthon/eranos/web/node_modules/.pnpm/axe-core@4.14.0/node_modules/axe-core/axe.min.js";
const { chromium } = require(PLAYWRIGHT);
const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const BASE = opt("--base", "http://127.0.0.1:8799").replace(/\/$/, "");
const PAGES = ["/", "/experience/", "/fabric/", "/video/", "/benchmarks/", "/benchmarks/methodology/", "/free/", "/docs/", "/status/", "/security/", "/privacy/", "/terms/", "/company/"];
const FILMS = ["/", "/experience/"];
const VIEWPORTS = [{ width: 1280, height: 720 }, { width: 390, height: 844 }];
const PAPER = "rgb(245, 242, 234)";
const failures = [];
const fail = (where, what) => failures.push(`${where}: ${what}`);

const browser = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
const axeSource = await readFile(AXE, "utf8");
for (const viewport of VIEWPORTS) for (const colorScheme of ["light", "dark"]) {
  const ctx = await browser.newContext({ viewport, colorScheme });
  for (const path of PAGES) {
    const where = `${path} ${viewport.width} ${colorScheme}`;
    const page = await ctx.newPage();
    page.on("pageerror", (e) => fail(where, `page error ${e}`));
    page.on("console", (m) => { if (m.type() === "error" && !/api\/network|503/.test(m.text())) fail(where, `console ${m.text()}`); });
    const res = await page.goto(BASE + path, { waitUntil: "load" });
    if (!res.ok()) fail(where, `status ${res.status()}`);
    await page.waitForTimeout(300);
    const r = await page.evaluate(() => {
      const lum = (c) => { const m = c.match(/[\d.]+/g).map(Number); if (m.length > 3 && m[3] < 0.5) return 1; return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255; };
      const area = innerWidth * innerHeight;
      const dark = [...document.querySelectorAll("body, body *")].filter((e) => { const b = e.getBoundingClientRect(); return e.tagName !== "VIDEO" && b.width * b.height > area * 0.05 && lum(getComputedStyle(e).backgroundColor) < 0.25; }).map((e) => e.tagName);
      return {
        bg: getComputedStyle(document.documentElement).backgroundColor,
        scheme: getComputedStyle(document.documentElement).colorScheme,
        dark, sideways: document.documentElement.scrollWidth > innerWidth,
        first: document.body.firstElementChild.textContent,
        sheets: document.querySelectorAll('link[rel="stylesheet"]').length,
        imgs: document.images.length,
        fonts: performance.getEntriesByType("resource").filter((e) => /\.woff2?$/.test(e.name)).length,
        footerRows: document.querySelectorAll("footer p").length,
      };
    });
    if (r.bg !== PAPER) fail(where, `background ${r.bg}`);
    if (!/only/.test(r.scheme) || !/light/.test(r.scheme) || /dark/.test(r.scheme)) fail(where, `color-scheme ${r.scheme}`);
    if (r.dark.length) fail(where, `dark element ${r.dark.join(",")}`);
    if (r.sideways) fail(where, "sideways scroll");
    if (!r.first.startsWith("For AI agents:")) fail(where, "first line isn't for agents");
    if (r.sheets || r.fonts || r.imgs) fail(where, `not text only: ${JSON.stringify([r.sheets, r.fonts, r.imgs])}`);
    if (r.footerRows !== 2) fail(where, `footer has ${r.footerRows} lines`);
    const scripts = await page.evaluate(() => [...document.scripts].map((s) => s.src).filter(Boolean).concat(performance.getEntriesByType("resource").filter((e) => /\.m?js(\?|$)/.test(e.name)).map((e) => e.name)));
    for (const src of scripts) {
      if (new URL(src).origin !== new URL(BASE).origin) fail(where, `script from another site ${src}`);
      if (path !== "/experience/" && /film3d|three/.test(src)) fail(where, `3D code outside /experience/ ${src}`);
      if (!FILMS.includes(path) && /film/.test(src)) fail(where, `film code on a text page ${src}`);
    }
    if (FILMS.includes(path)) {
      const film = await page.evaluate(() => {
        const cv = document.getElementById("film");
        const px = cv.getContext("2d").getImageData(0, 0, cv.width, cv.height).data;
        let ink = 0; for (let i = 0; i < px.length; i += 400) if (px[i] < 120) ink++;
        return { hidden: cv.hidden, ink, secs: [...document.querySelectorAll("[data-seconds]")].reduce((a, s) => a + Number(s.dataset.seconds), 0) };
      });
      if (film.hidden) fail(where, "film hidden");
      const ctl = await page.evaluate(() => { const b = document.getElementById("film-controls").getBoundingClientRect(); return { bottom: b.bottom, vh: innerHeight }; });
      if (ctl.bottom > ctl.vh) fail(where, `controls end at ${Math.round(ctl.bottom)}, below the fold at ${ctl.vh}`);
      if (film.secs !== 180) fail(where, `film is ${film.secs} s`);
      const before = await page.textContent("#film-pos");
      await page.click('[data-film="next"]');
      await page.waitForTimeout(150);
      if (before === (await page.textContent("#film-pos"))) fail(where, "next did nothing");
      await page.waitForTimeout(1500);
      const ink = await page.evaluate(() => { const cv = document.getElementById("film"); const px = cv.getContext("2d").getImageData(0, 0, cv.width, cv.height).data; let n = 0; for (let i = 0; i < px.length; i += 400) if (px[i] < 120) n++; return n; });
      if (!ink) fail(where, "film draws nothing");
      // Paused, then jumped: the scene shows at rest, so its heading is fully drawn at once.
      await page.click('[data-film="pause"]');
      await page.click('[data-film="next"]');
      await page.waitForTimeout(150);
      const rested = await page.evaluate(() => { const cv = document.getElementById("film"); const px = cv.getContext("2d").getImageData(0, 0, cv.width, cv.height).data; let n = 0; for (let i = 0; i < px.length; i += 400) if (px[i] < 120) n++; return n; });
      if (!rested) fail(where, "a scene jumped to while paused is blank");
    }
    await page.close();
  }
  await ctx.close();
}
let axeRuns = 0;
for (const viewport of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport, bypassCSP: true });
  for (const path of PAGES) {
    const page = await ctx.newPage();
    await page.goto(BASE + path, { waitUntil: "load" });
    await page.addScriptTag({ content: axeSource });
    const out = await page.evaluate(async () => window.axe.run(document, { resultTypes: ["violations"] }));
    axeRuns++;
    for (const v of out.violations) if (["serious", "critical"].includes(v.impact)) fail(`${path} ${viewport.width} axe`, `${v.id}: ${v.nodes[0]?.target}`);
    await page.close();
  }
  await ctx.close();
}
await browser.close();
if (failures.length) { console.log(`FAIL ${failures.length}`); failures.forEach((f) => console.log(`  ${f}`)); process.exit(1); }
console.log(`PASS ${PAGES.length} pages, both widths, both colour schemes, ${axeRuns} axe runs`);
