// Practice case: an example, not a real person or case. Local workerd with an in-memory service binding only.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const installed = process.env.MINIFLARE || fileURLToPath(new URL("../../../../portal-worker/node_modules/miniflare", import.meta.url));
const { Miniflare, Log, LogLevel, convertV4MiniflareOptions } = require(installed);
let mf;
before(async () => {
  const modules = await Promise.all(["network.js", "lib.js", "link.js", "text.generated.js", "banned.generated.js", "media-range.js", "media.generated.js"].map(async (name) => ({
    type: "ESModule", path: name, contents: await readFile(new URL(`../worker/${name}`, import.meta.url), "utf8"),
  })));
  const options = { log: new Log(LogLevel.NONE), workers: [{ name: "network-runtime-test", compatibilityDate: "2026-04-01", modules: [
    ...modules,
    { type: "ESModule", path: "fixture.js", contents: `
      import { networkResponse } from './network.js';
      import { passesWordList } from './lib.js';
      export default { async fetch(request, env, ctx) {
        const mode = new URL(request.url).searchParams.get('mode');
        const now = new Date().toISOString();
        const claims = Array.from({ length: 300 }, (_, i) => ({ at: now, kind: 'nonprofit', kind_label: 'Nonprofit Task',
          title: 'Practice case: an example, not a real person or case. Example inventory group ' + i,
          place: 'Anywhere', worker_kind: i % 2 ? 'volunteer' : 'dedicated', model: { name: 'Example model ' + i, declared: true },
          via: { type: 'data_centre', code: 'FRA', city: 'Frankfurt', continent: 'Europe' } }));
        const value = { generated_at: now, totals: { workers: 53, data_centres: 1, continents: 1, claims: 300, nonprofit_claims: 300 },
          data_centres: [{ code: 'FRA', city: 'Frankfurt', continent: 'Europe', continent_code: 'EU', lat: 50, lon: 8, workers: 53, claims: 300 }],
          continents: [], recent_claims: claims.slice(0, 20), replay: { claims } };
        let tokenMemo;
        const gate = (text, memo) => { tokenMemo = memo; return passesWordList(text, memo); };
        const local = { HERMA: { fetch: async () => {
          if (mode === 'slow') return new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('{')); } }));
          return Response.json(value);
        } } };
        const response = await networkResponse(new Request('https://teleionlabs.com/api/network?replay=1'), local, {}, gate);
        response.headers.set('X-Test-Token-Memo', String(tokenMemo?.size || 0));
        return response;
      } }
    ` },
  ] }] };
  // Miniflare's first ES module is the entry point.
  options.workers[0].modules.unshift(options.workers[0].modules.pop());
  mf = new Miniflare(convertV4MiniflareOptions ? convertV4MiniflareOptions(options) : options);
  await mf.ready;
});
after(async () => { await mf?.dispose(); });

test("real workerd preserves the largest upstream replay and uses the shared display gate", async (t) => {
  const started = performance.now();
  const response = await mf.dispatchFetch("http://localhost/");
  const body = await response.json();
  const elapsed = performance.now() - started;
  assert.equal(response.status, 200);
  assert.equal(body.recent_claims.length, 20); assert.equal(body.replay.claims.length, 300);
  assert.equal(body.recent_claims[0].model.name, "Example model 0");
  assert.equal(body.data_centres[0].workers, 53);
  t.diagnostic(JSON.stringify({ rows: 320, uniqueTokenMemo: Number(response.headers.get("X-Test-Token-Memo")), localRoundTripMs: Number(elapsed.toFixed(2)), note: "Local runtime wall-clock, not production CPU usage." }));
});

test("a stalled upstream body is cancelled at the bounded deadline and becomes unavailable", async () => {
  const started = performance.now();
  const response = await mf.dispatchFetch("http://localhost/?mode=slow");
  assert.equal(response.status, 503); assert.deepEqual(await response.json(), { available: false });
  const elapsed = performance.now() - started;
  assert.ok(elapsed >= 3500 && elapsed < 6500, `timeout took ${elapsed} ms`);
});
