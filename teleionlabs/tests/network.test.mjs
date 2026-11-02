// Practice case: an example, not a real person or case. All responses are local fixtures; no service is called.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { networkResponse, publicNetwork } from "../worker/network.js";

const okWords = async (text) => text !== "Disallowed model";
const request = (suffix = "", options = {}) => new Request("https://teleionlabs.com/api/network" + suffix, options);
function fixture(at = Date.now()) {
  const iso = new Date(at).toISOString();
  const row = { at: iso, kind: "nonprofit", kind_label: "Nonprofit Task", title: "Practice case: an example, not a real person or case.", place: "Anywhere", worker_kind: "dedicated", model: { name: "Example model", declared: false }, via: { type: "data_centre", code: "FRA", city: "Frankfurt", continent: "Europe" }, persona: "unpublished", object_key: "unpublished", worker_id: "unpublished" };
  return { generated_at: iso, totals: { workers: 4, data_centres: 1, continents: 1, claims: 6, nonprofit_claims: 3 },
    data_centres: [{ code: "FRA", city: "Frankfurt", continent: "Europe", continent_code: "EU", lat: 50, lon: 8, workers: 2, claims: 4, by_kind: { nonprofit: 2 }, last_claim_at: iso }],
    continents: [{ name: "Europe", code: "EU", workers: 2, claims: 2, by_kind: { shared: 2 } }], recent_claims: [row] };
}

test("the projection retains aggregates and drops identity, persona, keys and opted-out rows", async () => {
  const input = fixture();
  input.recent_claims.push({ ...input.recent_claims[0], show_on_map: false });
  const result = await publicNetwork(input, okWords);
  assert.equal(result.recent_claims.length, 1);
  assert.equal(result.recent_claims[0].worker_kind, "dedicated");
  assert.doesNotMatch(JSON.stringify(result), /unpublished|worker_id|object_key|persona/);
  assert.equal(result.totals.workers, 4, "totals can include connections that opt out of placement");
});

test("one-worker centers are never placed; claims fall back to the reported continent", async () => {
  const input = fixture(); input.data_centres[0].workers = 1;
  const result = await publicNetwork(input, okWords);
  assert.deepEqual(result.data_centres, []);
  assert.deepEqual(result.recent_claims[0].via, { type: "continent", continent: "Europe" });
  assert.equal(result.totals.data_centres, 0);
});

test("contributed display strings pass the supplied shared word gate, and ownership stays unknown", async () => {
  const input = fixture(); input.recent_claims[0].model.name = "Disallowed model"; input.recent_claims[0].worker_kind = "unverified";
  const result = await publicNetwork(input, okWords);
  assert.equal(result.recent_claims[0].model, null);
  assert.equal(result.recent_claims[0].worker_kind, "volunteer", "legacy wire enum means an unlabeled connection, not independently verified ownership");
});

test("old readings stay stale; missing or future time and malformed totals fail closed", async () => {
  const now = Date.now();
  assert.equal((await publicNetwork(fixture(now - 300_000), okWords, now)).freshness, "stale");
  for (const input of [{ ...fixture(), generated_at: null }, fixture(now + 120_000), { ...fixture(), totals: {} }]) {
    await assert.rejects(publicNetwork(input, okWords, now));
  }
  for (const key of ["continents", "recent_claims"]) {
    const input = fixture(); delete input[key];
    await assert.rejects(publicNetwork(input, okWords, now));
  }
});

test("the adapter uses only the fixed HERMA binding GET and forwards no client headers", async () => {
  let seen;
  const env = { HERMA: { fetch: async (req) => { seen = req; return Response.json({ ...fixture(), replay: { claims: [] } }); } } };
  const response = await networkResponse(request("?replay=1&kind=nonprofit", { headers: { cookie: "fixture", authorization: "fixture" } }), env, {}, okWords);
  assert.equal(response.status, 200);
  assert.equal(seen.url, "https://herma.teleionlabs.com/q/network?kind=nonprofit&replay=1");
  assert.equal(seen.method, "GET"); assert.equal(seen.headers.get("cookie"), null); assert.equal(seen.headers.get("authorization"), null);
  assert.equal(seen.redirect, "manual"); assert.equal(response.headers.get("Cache-Control"), "no-store");
});

test("mutations and unknown or duplicate query selectors never call the binding", async () => {
  let calls = 0;
  const env = { HERMA: { fetch: async () => { calls++; return Response.json(fixture()); } } };
  assert.equal((await networkResponse(request("", { method: "POST", body: "{}" }), env, {}, okWords)).status, 405);
  for (const suffix of ["?destination=https://fixture.invalid", "?kind=x", "?kind=own&kind=check", "?replay=2"]) {
    assert.equal((await networkResponse(request(suffix), env, {}, okWords)).status, 400);
  }
  assert.equal(calls, 0);
});

test("a requested replay must include its claims array rather than return an ordinary reading", async () => {
  const env = { HERMA: { fetch: async () => Response.json(fixture()) } };
  const response = await networkResponse(request("?replay=1"), env, {}, okWords);
  assert.equal(response.status, 503); assert.deepEqual(await response.json(), { available: false });
});

test("unavailable, malformed and oversized sources return unknown without any fabricated zero counts", async () => {
  for (const env of [{}, { HERMA: { fetch: async () => new Response("failure", { status: 503 }) } },
    { HERMA: { fetch: async () => new Response("invalid json") } },
    { HERMA: { fetch: async () => new Response("x".repeat(262145)) } },
    { HERMA: { fetch: async () => new Response("{}", { headers: { "Content-Length": "262145" } }) } }]) {
    const response = await networkResponse(request(), env, {}, okWords);
    assert.equal(response.status, 503); assert.deepEqual(await response.json(), { available: false });
    assert.equal(response.headers.get("Retry-After"), "60");
  }
});

test("a shared 60-second cache serves HEAD and GET without forwarding cookies or caching in the browser", async () => {
  const old = globalThis.caches, saved = new Map(), pending = [];
  globalThis.caches = { default: { match: async (key) => saved.get(key.url)?.clone(), put: async (key, response) => { assert.equal(response.headers.get("Cache-Control"), "public, max-age=60"); saved.set(key.url, response); } } };
  try {
    let calls = 0;
    const env = { HERMA: { fetch: async () => { calls++; return Response.json(fixture()); } } };
    await networkResponse(request(), env, { waitUntil: (work) => pending.push(work) }, okWords);
    await Promise.all(pending);
    const head = await networkResponse(request("", { method: "HEAD" }), env, {}, okWords);
    assert.equal(head.status, 200); assert.equal(await head.text(), "");
    const get = await networkResponse(request(), env, {}, okWords);
    assert.equal((await get.json()).available, true); assert.equal(get.headers.get("Cache-Control"), "no-store");
    assert.equal(calls, 1);
  } finally { if (old === undefined) delete globalThis.caches; else globalThis.caches = old; }
});

test("the reused browser normalizer requires a source timestamp and hides under-threshold map dots", async () => {
  const code = await readFile(new URL("../static/assets/network.js", import.meta.url), "utf8");
  const window = { matchMedia: () => ({ matches: true }) };
  vm.runInNewContext(code, { window, document: { querySelectorAll: () => [] } });
  assert.equal(window.TaNetwork.normalize({ ...fixture(), generated_at: null }), null);
  const data = fixture(); data.data_centres[0].workers = 1;
  assert.equal(window.TaNetwork.normalize(data).centers.length, 0);
});
