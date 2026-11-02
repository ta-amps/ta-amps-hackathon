// Read-only presentation adapter for Herma's existing public aggregate. No worker identities, credentials,
// work authority or client-selected destination cross this boundary. Counts remain Herma's observations.
const ORIGIN = "https://shim.teleionlabs.com/q/network";
const CACHE_ORIGIN = "https://teleionlabs.com/api/network";
const KINDS = new Set(["nonprofit", "shared", "check", "own"]);
const CONTINENTS = { AF: "Africa", AN: "Antarctica", AS: "Asia", EU: "Europe", NA: "North America", OC: "Oceania", SA: "South America" };
const MAX_BYTES = 256 * 1024;
const TIMEOUT_MS = 4000;
const TTL = 60;
const count = (value) => Number.isSafeInteger(value) && value >= 0 ? value : 0;
const date = (value) => typeof value === "string" && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : null;
const kinds = (value) => Object.fromEntries([...KINDS].map((key) => [key, count(value?.[key])]));
const continent = (value) => Object.values(CONTINENTS).includes(value) ? value : null;

async function boundedJson(response, signal) {
  const length = response.headers.get("Content-Length");
  if (length && (!/^\d+$/.test(length) || Number(length) > MAX_BYTES)) {
    await response.body?.cancel();
    throw new Error("size");
  }
  if (!response.body) throw new Error("body");
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  const abort = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener("abort", abort, { once: true });
  try {
    while (true) {
      if (signal.aborted) throw new Error("timeout");
      const { value, done } = await reader.read();
      if (signal.aborted) throw new Error("timeout");
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BYTES) { await reader.cancel(); throw new Error("size"); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } finally {
    signal.removeEventListener("abort", abort);
    reader.releaseLock();
  }
}

export async function publicNetwork(value, passesWordList, now = Date.now()) {
  const generated = date(value?.generated_at);
  if (!generated || Date.parse(generated) > now + 60_000 || !value?.totals || !Array.isArray(value.data_centres) ||
      !Array.isArray(value.continents) || !Array.isArray(value.recent_claims)) throw new Error("shape");
  for (const key of ["workers", "data_centres", "continents", "claims", "nonprofit_claims"]) {
    if (!Number.isSafeInteger(value.totals[key]) || value.totals[key] < 0) throw new Error("totals");
  }
  const memo = new Map();
  const tokenMemo = new Map();
  const words = async (value, max = 160) => {
    if (typeof value !== "string" || !value.trim() || value.length > max || /[\u0000-\u001f\u007f]/.test(value)) return null;
    if (!memo.has(value)) memo.set(value, await passesWordList(value, tokenMemo));
    return memo.get(value) ? value : null;
  };
  const centers = [];
  for (const center of value.data_centres.slice(0, 100)) {
    if (!center || !/^[A-Z]{3}$/.test(center.code) || count(center.workers) < 2 ||
        typeof center.lat !== "number" || !Number.isFinite(center.lat) || Math.abs(center.lat) > 90 ||
        typeof center.lon !== "number" || !Number.isFinite(center.lon) || Math.abs(center.lon) > 180) continue;
    const city = await words(center.city, 80);
    const area = continent(center.continent);
    if (!city || !area) continue;
    centers.push({ code: center.code, city, continent: area, continent_code: Object.keys(CONTINENTS).find((key) => CONTINENTS[key] === area),
      lat: center.lat, lon: center.lon, workers: count(center.workers), claims: count(center.claims), by_kind: kinds(center.by_kind), last_claim_at: date(center.last_claim_at) });
  }
  const centerMap = new Map(centers.map((center) => [center.code, center]));
  const continents = (Array.isArray(value.continents) ? value.continents : []).slice(0, 7)
    .filter((entry) => entry && Object.hasOwn(CONTINENTS, entry.code))
    .map((entry) => ({ code: entry.code, name: CONTINENTS[entry.code], workers: count(entry.workers), claims: count(entry.claims), by_kind: kinds(entry.by_kind) }));
  const rows = async (list, maximum) => {
    const result = [];
    for (const row of (Array.isArray(list) ? list : []).slice(0, maximum)) {
      const at = date(row?.at);
      if (!at || !KINDS.has(row.kind) || Date.parse(at) > Date.parse(generated) + 60_000 || row.show_on_map === false) continue;
      const center = row.via?.type === "data_centre" ? centerMap.get(row.via.code) : null;
      const area = continent(row.via?.continent);
      const modelName = await words(row.model?.name, 80);
      result.push({ at, kind: row.kind, kind_label: await words(row.kind_label, 80), title: await words(row.title, 240), place: await words(row.place, 80),
        worker_kind: row.worker_kind === "dedicated" ? "dedicated" : "volunteer",
        model: modelName ? { name: modelName, declared: row.model.declared === true } : null,
        via: center ? { type: "data_centre", code: center.code, city: center.city, continent: center.continent }
          : { type: "continent", continent: area } });
    }
    return result;
  };
  const result = { available: true, generated_at: generated, checked_at: new Date(now).toISOString(),
    freshness: now - Date.parse(generated) > 180_000 ? "stale" : "current", window_hours: 24, recent_minutes: 10,
    totals: { workers: count(value.totals.workers), data_centres: centers.length, continents: count(value.totals.continents), claims: count(value.totals.claims), nonprofit_claims: count(value.totals.nonprofit_claims) },
    data_centres: centers, continents, recent_claims: await rows(value.recent_claims, 100) };
  if (value.replay && Array.isArray(value.replay.claims)) result.replay = { claims: await rows(value.replay.claims, 300) };
  return result;
}

function answer(value, status = 200, retry = false) {
  return Response.json(value, { status, headers: { "Cache-Control": "no-store", ...(retry ? { "Retry-After": "60" } : {}) } });
}

export async function networkResponse(request, env, ctx, passesWordList) {
  if (!["GET", "HEAD"].includes(request.method)) return new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } });
  const url = new URL(request.url);
  const query = new URLSearchParams();
  for (const key of url.searchParams.keys()) {
    if (!["kind", "replay"].includes(key) || url.searchParams.getAll(key).length !== 1) return answer({ available: false }, 400);
  }
  const kind = url.searchParams.get("kind"), replay = url.searchParams.get("replay");
  if ((kind !== null && kind !== "all" && !KINDS.has(kind)) || (replay !== null && replay !== "1")) return answer({ available: false }, 400);
  if (kind && kind !== "all") query.set("kind", kind);
  if (replay === "1") query.set("replay", "1");
  const suffix = query.size ? `?${query}` : "";
  const key = new Request(CACHE_ORIGIN + suffix);
  const cache = globalThis.caches?.default;
  const client = (response) => {
    const out = new Response(request.method === "HEAD" ? null : response.body, response);
    out.headers.set("Cache-Control", "no-store");
    return out;
  };
  try {
    const hit = cache ? await cache.match(key) : null;
    if (hit) return client(hit);
  } catch { /* A failed cache read must not hide the source's current state. */ }
  if (!env.HERMA?.fetch || typeof passesWordList !== "function") return client(answer({ available: false }, 503, true));
  const controller = new AbortController();
  let timeout;
  const deadline = new Promise((_, reject) => { timeout = setTimeout(() => { controller.abort(); reject(new Error("timeout")); }, TIMEOUT_MS); });
  try {
    const work = (async () => {
      const response = await env.HERMA.fetch(new Request(ORIGIN + suffix, {
        method: "GET", headers: { Accept: "application/json" }, credentials: "omit", redirect: "manual", signal: controller.signal,
      }));
      if (controller.signal.aborted || !response.ok) { await response.body?.cancel(); throw new Error("upstream"); }
      const source = await boundedJson(response, controller.signal);
      if (replay === "1" && !Array.isArray(source?.replay?.claims)) throw new Error("replay");
      return publicNetwork(source, passesWordList);
    })();
    const value = await Promise.race([work, deadline]);
    const response = answer(value);
    if (cache && ctx?.waitUntil) {
      const stored = new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": `public, max-age=${TTL}` } });
      ctx.waitUntil(cache.put(key, stored).catch(() => {}));
    }
    return client(response);
  } catch { return client(answer({ available: false }, 503, true)); }
  finally { clearTimeout(timeout); }
}
