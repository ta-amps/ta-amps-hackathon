// Unit tests for the Worker (node --test). No network: fetch and the asset binding are stubbed.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { handle, passesWordList, SECURITY_HEADERS } from "../worker/lib.js";
import entry from "../worker/index.js";

const DIST = fileURLToPath(new URL("../dist/", import.meta.url));

function assets() {
  return {
    async fetch(req) {
      const url = new URL(typeof req === "string" ? req : req.url);
      let path = url.pathname;
      if (path.endsWith("/")) path += "index.html";
      const type = path.endsWith(".html") ? { "Content-Type": "text/html; charset=utf-8" } : {};
      try {
        const body = await readFile(DIST + path.slice(1));
        return new Response(body, { status: 200, headers: type });
      } catch {
        return new Response("not found", { status: 404, headers: { "Content-Type": "text/html; charset=utf-8" } });
      }
    },
  };
}

const ctx = { waitUntil() {} };

test("the entry module exports only the default handler", () => {
  assert.equal(typeof entry.fetch, "function");
});

test("www answers 301 to the apex for GET, keeping path and query", async () => {
  const res = await handle(new Request("https://www.teleionlabs.com/free/?a=1#x"), { ASSETS: assets() }, ctx);
  assert.equal(res.status, 301);
  assert.equal(res.headers.get("Location"), "https://teleionlabs.com/free/?a=1");
  assert.equal(res.headers.get("Strict-Transport-Security"), "max-age=31536000");
});

test("www answers 308 for other methods", async () => {
  const res = await handle(new Request("https://www.teleionlabs.com/api/x", { method: "POST", body: "{}" }), { ASSETS: assets() }, ctx);
  assert.equal(res.status, 308);
  assert.equal(res.headers.get("Location"), "https://teleionlabs.com/api/x");
});

test("only GET and HEAD are served on the apex", async () => {
  const res = await handle(new Request("https://teleionlabs.com/", { method: "POST", body: "x" }), { ASSETS: assets() }, ctx);
  assert.equal(res.status, 405);
  assert.equal(res.headers.get("Allow"), "GET, HEAD");
});

test("pages carry the security headers, a CSP of 'self' only, and no alias headers on the apex", async () => {
  const res = await handle(new Request("https://teleionlabs.com/"), { ASSETS: assets() }, ctx);
  assert.equal(res.status, 200);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) assert.equal(res.headers.get(k), v, k);
  const csp = res.headers.get("Content-Security-Policy");
  assert.match(csp, /default-src 'self'/);
  assert.match(csp, /frame-ancestors 'none'/);
  assert.doesNotMatch(csp, /https?:|\*|unsafe/);
  assert.doesNotMatch(res.headers.get("Strict-Transport-Security"), /preload|includeSubDomains/);
  assert.equal(res.headers.get("X-Robots-Tag"), null);
});

test("the workers.dev alias serves the same page with noindex and a canonical link", async () => {
  const res = await handle(new Request("https://teleionlabs.ta-amps.workers.dev/free/"), { ASSETS: assets() }, ctx);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("X-Robots-Tag"), "noindex");
  assert.equal(res.headers.get("Link"), '<https://teleionlabs.com/free/>; rel="canonical"');
});

test("/api/status reads only the listed health checks and keeps only state and version", async (t) => {
  const seen = [];
  t.mock.method(globalThis, "fetch", async (req) => {
    const url = typeof req === "string" ? req : req.url;
    seen.push(url);
    if (url.includes("tessera")) return Response.json({ ok: true, version: "0.2.0", queues: [{ name: "secret-ish" }] });
    if (url.includes("herma")) return Response.json({ ok: false });
    return new Response("boom", { status: 500 });
  });
  const res = await handle(new Request("https://teleionlabs.com/api/status"), { ASSETS: assets() }, ctx);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Cache-Control"), "no-store", "browsers never keep the status");
  const body = await res.json();
  assert.deepEqual(Object.keys(body).sort(), ["checked_at", "services"]);
  assert.deepEqual(body.services, [
    { id: "tessera", state: "up", version: "0.2.0" },
    { id: "shim", state: "down" },
    { id: "eranos", state: "down" },
  ]);
  assert.deepEqual(seen.sort(), [
    "https://eranosforgood.org/api/health",
    "https://herma.teleionlabs.com/healthz",
    "https://tessera.teleionlabs.com/v1/health",
  ]);
});

test("/api/status prefers a connected service binding and falls back when it fails", async (t) => {
  const publicCalls = [];
  t.mock.method(globalThis, "fetch", async (req) => {
    publicCalls.push(req.url);
    return Response.json({ ok: true, version: "9" });
  });
  const env = {
    ASSETS: assets(),
    TESSERA: { fetch: async () => Response.json({ ok: true, version: "0.2.0" }) },
    HERMA: { fetch: async () => new Response("not connected", { status: 503 }) },
    ERANOS: { fetch: async () => { throw new Error("no"); } },
  };
  const body = await (await handle(new Request("https://teleionlabs.com/api/status"), env, ctx)).json();
  assert.deepEqual(body.services.map((s) => s.state), ["up", "up", "up"]);
  assert.deepEqual(publicCalls.sort(), ["https://eranosforgood.org/api/health", "https://herma.teleionlabs.com/healthz"]);
});

test("a missing page answers with the 404 page's status", async () => {
  const res = await handle(new Request("https://teleionlabs.com/nope/"), { ASSETS: assets() }, ctx);
  assert.equal(res.status, 404);
});

test("agent-readable text files are served as plain text", async () => {
  for (const path of ["/llms.txt", "/robots.txt", "/.well-known/security.txt"]) {
    const res = await handle(new Request(`https://teleionlabs.com${path}`), { ASSETS: assets() }, ctx);
    assert.equal(res.status, 200, path);
    assert.equal(res.headers.get("Content-Type"), "text/plain; charset=utf-8", path);
  }
  const sec = await (await handle(new Request("https://teleionlabs.com/.well-known/security.txt"), { ASSETS: assets() }, ctx)).text();
  assert.match(sec, /^Contact: mailto:hello@teleionlabs\.com$/m);
  const expires = new Date(sec.match(/^Expires: (.+)$/m)[1]);
  assert.ok(expires - Date.now() < 365 * 86400 * 1000, "Expires is less than a year away (RFC 9116)");
});

test("upstream strings pass the shared banned-words list before they leave the Worker (rule 16)", async (t) => {
  assert.equal(await passesWordList("0.2.0"), true);
  assert.equal(await passesWordList("Teleion"), true, "Teleion, with an i, is allowed");
  assert.equal(await passesWordList("abcdef0123456789"), false, "a 12+ character hex string is refused");
  t.mock.method(globalThis, "fetch", async () => Response.json({ ok: true, version: "abcdef0123456789" }));
  const body = await (await handle(new Request("https://teleionlabs.com/api/status"), { ASSETS: assets() }, ctx)).json();
  assert.ok(body.services.every((s) => s.state === "up" && !("version" in s)), "the refused version is dropped, the state stays");
});

test("HTML pages carry no-transform, so the zone injects nothing the CSP would block", async () => {
  for (const path of ["/", "/free/", "/nope/"]) {
    const res = await handle(new Request(`https://teleionlabs.com${path}`), { ASSETS: assets() }, ctx);
    assert.match(res.headers.get("Cache-Control"), /no-transform/, path);
  }
  const css = await handle(new Request("https://teleionlabs.com/assets/site.css"), { ASSETS: assets() }, ctx);
  assert.doesNotMatch(css.headers.get("Cache-Control") || "", /no-transform/);
});

test("/api/status: the Worker keeps a 60 s copy at the edge; browsers get no-store, also on a cache hit", async (t) => {
  const store = new Map();
  const pending = [];
  globalThis.caches = { default: {
    async match(req) { const r = store.get(req.url); return r ? r.clone() : undefined; },
    async put(req, res) { store.set(req.url, res); },
  } };
  t.after(() => { delete globalThis.caches; });
  t.mock.method(globalThis, "fetch", async () => Response.json({ ok: true, version: "1" }));
  const waitCtx = { waitUntil(p) { pending.push(p); } };
  const first = await handle(new Request("https://teleionlabs.com/api/status"), { ASSETS: assets() }, waitCtx);
  await Promise.all(pending);
  assert.equal(first.headers.get("Cache-Control"), "no-store");
  assert.equal(store.get("https://teleionlabs.com/api/status").headers.get("Cache-Control"), "public, max-age=60");
  const second = await handle(new Request("https://teleionlabs.com/api/status"), { ASSETS: assets() }, waitCtx);
  assert.equal(second.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(await second.json(), await first.json());
});
