// teleionlabs.com: static pages plus small edge jobs.
//   1. www.teleionlabs.com and preview hosts answer 301 (GET/HEAD) or 308 (other methods) to the apex, path and query kept.
//   2. /products and /tessera redirect 301/308 to /fabric/; /film and /video redirect 301/308 to /video/; legacy overview paths redirect 301/308 to agora.eranosforgood.org.
//   3. Every response carries the security headers: a CSP of 'self' only, HSTS without preload, nosniff.
//   4. GET /api/status reads the public health checks listed in /status.sources.json (built from
//      content/home.json), keeps only state and version, and caches the answer for 60 s.
// No storage, no cookies, no credentials. Only GET and HEAD are served, except the form on a link page (/l/<token>).

import { BANNED_PATTERNS, PRIVATE_SHA256 } from "./banned.generated.js";
import { maybeMediaRange } from "./media-range.js";
import { networkResponse } from "./network.js";
import { linkResponse } from "./link.js";
import { TEXT_CSS_HASH } from "./text.generated.js";

export const APEX = "teleionlabs.com";
const OVERVIEW_HOST = "agora.eranosforgood.org";
const STATUS_TTL_SECONDS = 60;
const isTextFile = (path) => path.endsWith(".txt");
// Retired pages: their job moved to the home film and the visitor's agent.
const RETIRED = new Set(["/start", "/story", "/network"]);
const OVERVIEW_PREFIXES = new Set([
  "judges", "how-it-works", "source", "library", "feeds", "scenarios",
  "models", "use-cases", "learning", "deploy", "studio", "accessibility",
  "decks", "storyboards", "evidence", "contribute", "hub-3d", "downloads",
]);
const PROBE_TIMEOUT_MS = 4000;
// Upstream hosts the status check may read. Anything else in the sources file is ignored.
const STATUS_HOSTS = new Set(["tessera.teleionlabs.com", "herma.teleionlabs.com", "eranosforgood.org"]);
// Service bindings, when configured, reach the other Workers directly instead of over the internet.
const STATUS_BINDINGS = { tessera: "TESSERA", shim: "HERMA", eranos: "ERANOS" };

export const SECURITY_HEADERS = {
  "Content-Security-Policy": [
    "default-src 'self'",
    "script-src 'self'",
    `style-src '${TEXT_CSS_HASH}'`,
    "img-src 'self'",
    "font-src 'self'",
    "media-src 'self'",
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
  const init = response.status === 206
    ? { status: response.status, statusText: response.statusText, headers: response.headers, encodeBody: "manual" }
    : response;
  const res = new Response(response.body, init);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.headers.set(k, v);
  for (const [k, v] of Object.entries(extra)) res.headers.set(k, v);
  return res;
}

function cacheControlFor(pathname) {
  if (pathname.startsWith("/fonts/") || pathname.startsWith("/media/")) return "public, max-age=31536000, immutable";
  if (pathname.startsWith("/assets/") || pathname === "/favicon.svg" || pathname === "/favicon.ico") return "public, max-age=3600";
  return "public, max-age=300";
}

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

export async function passesWordList(value, tokenMemo) {
  if (!wordListOk || typeof value !== "string") return false;
  if (BANNED.some((re) => re.test(value))) return false;
  for (const token of value.toLowerCase().match(/[\p{L}\p{N}]+/gu) || []) {
    let allowed = tokenMemo?.get(token);
    if (allowed === undefined) {
      allowed = !PRIVATE.has(await sha256Hex(token));
      tokenMemo?.set(token, allowed);
    }
    if (!allowed) return false;
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

  if (url.hostname !== APEX || url.protocol !== "https:" || url.port !== "") {
    const target = new URL(url.toString());
    target.protocol = "https:";
    target.hostname = APEX;
    target.port = "";
    target.hash = "";
    return withHeaders(new Response(null, { status: safe ? 301 : 308, headers: { Location: target.toString() } }));
  }

  // /products and /tessera redirect 301/308 to /fabric/ (Teleion Fabric public product naming).
  if (
    url.pathname === "/products" ||
    url.pathname.startsWith("/products/") ||
    url.pathname === "/tessera" ||
    url.pathname.startsWith("/tessera/")
  ) {
    const target = new URL(`https://${APEX}/fabric/`);
    target.search = url.search;
    return withHeaders(new Response(null, { status: safe ? 301 : 308, headers: { Location: target.toString() } }));
  }

  // /video (without slash) and legacy /film paths redirect 301/308 to the durable /video/ page.
  if (url.pathname === "/video" || url.pathname === "/film" || url.pathname.startsWith("/film/")) {
    const target = new URL(`https://${APEX}/video/`);
    target.search = url.search;
    return withHeaders(new Response(null, { status: safe ? 301 : 308, headers: { Location: target.toString() } }));
  }

  // Legacy overview paths move 301/308 to agora.eranosforgood.org (T9).
  const firstSeg = url.pathname.split("/").filter(Boolean)[0] || "";
  if (OVERVIEW_PREFIXES.has(firstSeg)) {
    const path = url.pathname.split("/").filter(Boolean).length === 1 && !url.pathname.endsWith("/")
      ? `${url.pathname}/`
      : url.pathname;
    const target = new URL(`https://${OVERVIEW_HOST}${path}`);
    target.search = url.search;
    return withHeaders(new Response(null, { status: safe ? 301 : 308, headers: { Location: target.toString() } }));
  }

  const link = url.pathname.match(/^\/l\/([^/]*)\/?$/);
  if (link && (safe || method === "POST")) {
    const res = await linkResponse(request, env, link[1]);
    return method === "HEAD" ? new Response(null, res) : res;
  }

  const bare = url.pathname.replace(/\/$/, "");
  if (RETIRED.has(bare)) {
    return withHeaders(new Response(null, { status: safe ? 301 : 308, headers: { Location: `https://${APEX}/` } }));
  }

  if (!safe) {
    return withHeaders(new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } }));
  }

  if (url.pathname === "/api/network") {
    return withHeaders(await networkResponse(request, env, ctx, passesWordList));
  }

  if (url.pathname === "/api/status") {
    const res = await statusResponse(request, env, ctx);
    const out = withHeaders(res);
    return method === "HEAD" ? new Response(null, out) : out;
  }

  const wantsText = !url.pathname.includes(".") && /^text\/(plain|markdown)/.test(request.headers.get("Accept") || "");
  const twin = wantsText ? (url.pathname === "/" ? "/index.txt" : `${url.pathname.replace(/\/$/, "")}.txt`) : null;
  const assetRequest = twin ? new Request(new URL(twin, url), request) : request;
  const servedPath = twin || url.pathname;
  const rawAsset = await env.ASSETS.fetch(assetRequest);
  const asset = await maybeMediaRange(request, rawAsset, ctx);
  const extra = {};
  const mediaOk = asset.status === 200 || asset.status === 206;
  if (mediaOk && (url.pathname.startsWith("/fonts/") || url.pathname.startsWith("/media/") || !asset.headers.has("Cache-Control"))) {
    extra["Cache-Control"] = cacheControlFor(url.pathname);
  }
  if (isTextFile(servedPath) && asset.status === 200) extra["Content-Type"] = "text/plain; charset=utf-8";
  extra.Vary = "Accept";
  if (url.pathname.startsWith("/records/") && url.pathname.endsWith(".json") && asset.status === 200) {
    extra["Content-Type"] = "application/json; charset=utf-8";
  }
  if (url.pathname.startsWith("/media/") && mediaOk) {
    if (url.pathname.endsWith(".mp4")) extra["Content-Type"] = "video/mp4";
    else if (url.pathname.endsWith(".vtt")) extra["Content-Type"] = "text/vtt; charset=utf-8";
  }
  if ((asset.headers.get("Content-Type") || "").startsWith("text/html")) {
    const cc = extra["Cache-Control"] || asset.headers.get("Cache-Control") || "public, max-age=0, must-revalidate";
    extra["Cache-Control"] = /no-transform/.test(cc) ? cc : `${cc}, no-transform`;
  }
  if ((servedPath === "/status.txt" || servedPath === "/status/") && asset.status === 200) {
    return withHeaders(await withLiveStatus(asset, request, env, ctx, servedPath), { ...extra, "Cache-Control": "no-store, no-transform" });
  }
  return withHeaders(asset, extra);
}

// The status page is plain text, so the Worker writes the live answers into it.
const STATE_WORDS = { up: "Answering", down: "Not answering" };
async function withLiveStatus(asset, request, env, ctx, path) {
  let services = [];
  try {
    services = (await (await statusResponse(request, env, ctx)).json()).services || [];
  } catch {
    services = [];
  }
  const state = (id) => STATE_WORDS[services.find((s) => s.id === id)?.state] || "No answer from the check";
  let body = await asset.text();
  body = path === "/status.txt"
    ? body.replace(/\[\[([a-z]+)\]\]/g, (_, id) => state(id))
    : body.replace(/(<span data-svc="([a-z]+)">)[^<]*/g, (_, open, id) => open + state(id));
  const headers = new Headers(asset.headers);
  headers.delete("Content-Length");
  headers.delete("ETag");
  return new Response(body, { status: 200, headers });
}
