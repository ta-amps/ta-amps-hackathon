// teleionlabs.com: static pages plus three small jobs.
//   1. www.teleionlabs.com answers 301 (GET/HEAD) or 308 (other methods) to the apex, path and query kept.
//   2. Every response carries the security headers: a CSP of 'self' only, HSTS without preload, nosniff.
//   3. GET /api/status reads the public health checks listed in /status.sources.json (built from
//      content/home.json), keeps only state and version, and caches the answer for 60 s.
// No storage, no cookies, no forms, no credentials. Only GET and HEAD are served.

import { BANNED_PATTERNS, PRIVATE_SHA256 } from "./banned.generated.js";
import { maybeMediaRange } from "./media-range.js";

export const APEX = "teleionlabs.com";
const STATUS_TTL_SECONDS = 60;
const TEXT_FILES = new Set(["/llms.txt", "/robots.txt", "/.well-known/security.txt"]);
const PROBE_TIMEOUT_MS = 4000;
// Upstream hosts the status check may read. Anything else in the sources file is ignored.
const STATUS_HOSTS = new Set(["tessera.teleionlabs.com", "herma.teleionlabs.com", "eranosforgood.org"]);
// Service bindings, when configured, reach the other Workers directly instead of over the internet.
const STATUS_BINDINGS = { tessera: "TESSERA", shim: "HERMA", eranos: "ERANOS" };

export const SECURITY_HEADERS = {
  "Content-Security-Policy": [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self'",
    "font-src 'self'",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
    "object-src 'none'",
  ].join("; "),
  "Strict-Transport-Security": "max-age=31536000",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Frame-Options": "DENY",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), browsing-topics=()",
  "Cross-Origin-Opener-Policy": "same-origin",
};

function withHeaders(response, extra = {}) {
  const res = new Response(response.body, response);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.headers.set(k, v);
  for (const [k, v] of Object.entries(extra)) res.headers.set(k, v);
  return res;
}

function aliasHeaders(url) {
  // workers.dev and preview hosts serve the same pages but never get indexed.
  if (url.hostname === APEX) return {};
  return {
    "X-Robots-Tag": "noindex",
    Link: `<https://${APEX}${url.pathname}>; rel="canonical"`,
  };
}

function cacheControlFor(pathname) {
  if (pathname.startsWith("/fonts/")) return "public, max-age=31536000, immutable";
  if (pathname.startsWith("/assets/") || pathname === "/favicon.svg") return "public, max-age=3600";
  return "public, max-age=300";
}

// Rule 16: every upstream string passes the shared banned-words list before it leaves this Worker:
// its patterns, and its private names, which exist only as SHA-256 hashes of lowercase word tokens.
// If any pattern fails to compile, or the list is empty, nothing upstream passes (fail closed).
const BANNED = [];
const PRIVATE = new Set(PRIVATE_SHA256);
let wordListOk = BANNED_PATTERNS.length > 0 && PRIVATE.size > 0;
for (const p of BANNED_PATTERNS) {
  try {
    BANNED.push(new RegExp(p, "i"));
  } catch {
    wordListOk = false;
  }
}

async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function passesWordList(value) {
  if (!wordListOk || typeof value !== "string") return false;
  if (BANNED.some((re) => re.test(value))) return false;
  for (const token of value.toLowerCase().match(/[\p{L}\p{N}]+/gu) || []) {
    if (PRIVATE.has(await sha256Hex(token))) return false;
  }
  return true;
}

let sourcesMemo = null;
async function loadSources(env) {
  if (sourcesMemo) return sourcesMemo;
  const res = await env.ASSETS.fetch(new Request(`https://${APEX}/status.sources.json`));
  if (!res.ok) throw new Error(`status sources: ${res.status}`);
  const list = await res.json();
  sourcesMemo = (Array.isArray(list) ? list : []).filter((s) => {
    try {
      const u = new URL(s.url);
      return typeof s.id === "string" && u.protocol === "https:" && STATUS_HOSTS.has(u.hostname);
    } catch {
      return false;
    }
  });
  return sourcesMemo;
}

function healthRequest(url) {
  return new Request(url, {
    headers: { Accept: "application/json", "User-Agent": "teleionlabs-status/1" },
    signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
  });
}

async function get(env, source) {
  const binding = env[STATUS_BINDINGS[source.id]];
  if (binding && typeof binding.fetch === "function") {
    try {
      const res = await binding.fetch(healthRequest(source.url));
      if (res.ok) return res;
    } catch {
      // Fall through to the public address.
    }
  }
  // No binding, or one that isn't connected (local dev): read the public address instead.
  return fetch(healthRequest(source.url));
}

async function probe(env, source) {
  try {
    const res = await get(env, source);
    if (!res.ok) return { id: source.id, state: "down" };
    const body = await res.json().catch(() => null);
    const out = { id: source.id, state: body && body.ok === true ? "up" : "down" };
    if (body && typeof body.version === "string" && /^[0-9A-Za-z.+-]{1,20}$/.test(body.version) && (await passesWordList(body.version))) {
      out.version = body.version;
    }
    return out;
  } catch {
    return { id: source.id, state: "down" };
  }
}

// The Worker keeps its own copy for STATUS_TTL_SECONDS in the Cache API; browsers get no-store, because the zone
// rewrites cacheable answers to hours (so "about a minute old" would stop being true in a browser).
function forClient(res) {
  const out = new Response(res.body, res);
  out.headers.set("Cache-Control", "no-store");
  return out;
}

export async function statusResponse(request, env, ctx, now = () => new Date()) {
  const cache = globalThis.caches && globalThis.caches.default;
  const key = new Request(`https://${APEX}/api/status`, { method: "GET" });
  if (cache) {
    const hit = await cache.match(key);
    if (hit) return forClient(hit);
  }
  const sources = await loadSources(env);
  const services = await Promise.all(sources.map((s) => probe(env, s)));
  const body = JSON.stringify({ checked_at: now().toISOString(), services });
  const type = { "Content-Type": "application/json; charset=utf-8" };
  if (cache && ctx && typeof ctx.waitUntil === "function") {
    ctx.waitUntil(cache.put(key, new Response(body, { headers: { ...type, "Cache-Control": `public, max-age=${STATUS_TTL_SECONDS}` } })));
  }
  return new Response(body, { headers: { ...type, "Cache-Control": "no-store" } });
}

export async function handle(request, env, ctx) {
  const url = new URL(request.url);
  const method = request.method.toUpperCase();
  const safe = method === "GET" || method === "HEAD";

  if (url.hostname === `www.${APEX}`) {
    const target = new URL(url.toString());
    target.protocol = "https:";
    target.hostname = APEX;
    target.port = "";
    target.hash = "";
    return withHeaders(new Response(null, { status: safe ? 301 : 308, headers: { Location: target.toString() } }));
  }

  if (!safe) {
    return withHeaders(new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } }), aliasHeaders(url));
  }

  if (url.pathname === "/api/status") {
    const res = await statusResponse(request, env, ctx);
    const out = withHeaders(res, aliasHeaders(url));
    return method === "HEAD" ? new Response(null, out) : out;
  }

  const asset = await maybeMediaRange(request, await env.ASSETS.fetch(request), ctx);
  const extra = aliasHeaders(url);
  if (asset.status === 200 && (url.pathname.startsWith("/fonts/") || !asset.headers.has("Cache-Control"))) {
    extra["Cache-Control"] = cacheControlFor(url.pathname);
  }
  if (TEXT_FILES.has(url.pathname) && asset.status === 200) extra["Content-Type"] = "text/plain; charset=utf-8";
  // no-transform on every HTML page: the zone would otherwise inject an analytics beacon, which the CSP blocks.
  if ((asset.headers.get("Content-Type") || "").startsWith("text/html")) {
    const cc = extra["Cache-Control"] || asset.headers.get("Cache-Control") || "public, max-age=0, must-revalidate";
    extra["Cache-Control"] = /no-transform/.test(cc) ? cc : `${cc}, no-transform`;
  }
  return withHeaders(asset, extra);
}
