// The stream/header contract runs in workerd, not a Node FixedLengthStream mock.
// Reuse the workspace's installed Miniflare; MINIFLARE can select another installation.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { VIDEO_BYTES } from "../worker/media-range.js";

const require = createRequire(import.meta.url);
const installed = process.env.MINIFLARE || fileURLToPath(new URL("../../../../portal-worker/node_modules/miniflare", import.meta.url));
const { Miniflare, Log, LogLevel, convertV4MiniflareOptions } = require(installed);
const PATH = "/media/teleion-fabric-preview-20261102.mp4";
const helper = await readFile(new URL("../worker/media-range.js", import.meta.url), "utf8");
let mf;

before(async () => {
  const options = {
    log: new Log(LogLevel.NONE),
    workers: [{
      name: "media-range-test",
      compatibilityDate: "2026-04-01",
      modules: [
      { type: "ESModule", path: "fixture.js", contents: `
        import {maybeMediaRange, VIDEO_BYTES} from './media-range.js';
        const states = new Map();
        export default {async fetch(request, env, ctx) {
          const url = new URL(request.url);
          const id = url.searchParams.get('id') || 'default';
          if (url.pathname === '/fixture-state') return Response.json(states.get(id) || {});
          const mode = url.searchParams.get('mode') || '';
          const state = {read: 0, pulls: 0, cancelled: false};
          states.set(id, state);
          const limit = mode === 'short' ? 15 : VIDEO_BYTES;
          const stream = new ReadableStream({
            async pull(controller) {
              if (mode === 'slow') await new Promise(resolve => setTimeout(resolve, 2));
              if (state.read >= limit) { controller.close(); return; }
              const count = Math.min(mode === 'slow' ? 4096 : 70001, limit - state.read);
              const bytes = new Uint8Array(count);
              for (let i = 0; i < count; i++) bytes[i] = (state.read + i) % 251;
              state.read += count;
              state.pulls++;
              controller.enqueue(bytes);
            },
            cancel() { state.cancelled = true; }
          });
          const headers = new Headers({
            'Content-Type': mode === 'html' ? 'text/html' : 'video/mp4',
            'ETag': '"preview"', 'Cache-Control': 'public, max-age=300',
            'Content-Length': String(VIDEO_BYTES),
            'Content-Digest': 'full-body-value',
          });
          if (mode === 'no-length') headers.delete('Content-Length');
          if (mode === 'wrong-length') headers.set('Content-Length', '100');
          if (mode === 'encoded') headers.set('Content-Encoding', 'gzip');
          const status = Number(url.searchParams.get('status') || 200);
          const body = request.method === 'HEAD' || status === 304 ? null : stream;
          const asset = new Response(body, {status, headers, encodeBody: 'manual'});
          const result = await maybeMediaRange(request, asset, ctx);
          // Match the sites' existing final response-header wrapper.
          const wrapped = new Response(result.body, result);
          wrapped.headers.set('X-Test-Final-Wrapper', 'preserved');
          return wrapped;
        }};
      ` },
      { type: "ESModule", path: "media-range.js", contents: helper },
      { type: "ESModule", path: "media.generated.js", contents: await readFile(new URL("../worker/media.generated.js", import.meta.url), "utf8") },
      ],
    }],
  };
  mf = new Miniflare(convertV4MiniflareOptions ? convertV4MiniflareOptions(options) : options);
  await mf.ready;
});
after(async () => { await mf?.dispose(); });

async function request(range, {mode, status, method = "GET", ifRange, path = PATH, id = crypto.randomUUID()} = {}) {
  const url = new URL(`http://localhost${path}`);
  url.searchParams.set("id", id);
  if (mode) url.searchParams.set("mode", mode);
  if (status) url.searchParams.set("status", status);
  const headers = {};
  if (range !== null) headers.Range = range;
  if (ifRange) headers["If-Range"] = ifRange;
  return { response: await mf.dispatchFetch(url, {method, headers}), id };
}

async function bytes(response) { return new Uint8Array(await response.arrayBuffer()); }
function expected(start, count) { return Uint8Array.from({length: count}, (_, i) => (start + i) % 251); }

test("the allowlisted asset still has its recorded exact size", async () => {
  assert.equal((await stat(new URL(`../static${PATH}`, import.meta.url))).size, VIDEO_BYTES);
});

test("real runtime returns exact byte intervals, including stream chunk boundaries", async () => {
  for (const [range, start, end, mode] of [
    ["bytes=0-1023", 0, 1023],
    ["bytes=69990-70020", 69990, 70020],
    ["bytes=6600100-", 6600100, VIDEO_BYTES - 1],
    ["bytes=-128", VIDEO_BYTES - 128, VIDEO_BYTES - 1],
    ["bytes=6600190-9999999", 6600190, VIDEO_BYTES - 1],
    ["bytes=0-1023", 0, 1023, "no-length"],
  ]) {
    const {response} = await request(range, {mode});
    assert.equal(response.status, 206, range);
    assert.equal(response.headers.get("Content-Range"), `bytes ${start}-${end}/${VIDEO_BYTES}`);
    assert.equal(Number(response.headers.get("Content-Length")), end - start + 1);
    assert.equal(response.headers.get("Accept-Ranges"), "bytes");
    assert.equal(response.headers.get("ETag"), '"preview"');
    assert.equal(response.headers.get("Content-Digest"), null);
    assert.equal(response.headers.get("X-Test-Final-Wrapper"), "preserved");
    assert.deepEqual(await bytes(response), expected(start, end - start + 1));
  }
});

test("a suffix larger than the asset selects the whole representation as 206", async () => {
  const {response} = await request("bytes=-9999999");
  assert.equal(response.status, 206);
  assert.equal(response.headers.get("Content-Range"), `bytes 0-${VIDEO_BYTES - 1}/${VIDEO_BYTES}`);
  assert.deepEqual(await bytes(response), expected(0, VIDEO_BYTES));
});

test("unsatisfiable single ranges return empty 416 responses", async () => {
  for (const range of [`bytes=${VIDEO_BYTES}-`, "bytes=8-3", "bytes=-0"]) {
    const {response} = await request(range);
    assert.equal(response.status, 416, range);
    assert.equal(response.headers.get("Content-Range"), `bytes */${VIDEO_BYTES}`);
    assert.equal((await bytes(response)).length, 0);
  }
});

test("unsupported syntax and mismatched validators keep the full response", async () => {
  for (const [range, ifRange] of [
    [null], ["bytes=0-1,4-5"], ["items=0-1"], ["bytes=no"], ["bytes=-"],
    ["bytes=999999999999999999999999-"],
    ["bytes=0-1", '"different"'], ["bytes=0-1", 'W/"preview"'],
    ["bytes=0-1", "Mon, 02 Nov 2026 00:00:00 GMT"],
  ]) {
    const {response} = await request(range, {ifRange});
    assert.equal(response.status, 200, `${range} ${ifRange}`);
    assert.equal(response.headers.get("Content-Range"), null);
    await response.body.cancel();
  }
  const {response} = await request("bytes=2-4", {ifRange: '"preview"'});
  assert.equal(response.status, 206);
  assert.deepEqual(await bytes(response), expected(2, 3));
});

test("HEAD advertises the complete representation and ignores Range without a body", async () => {
  const {response} = await request("bytes=0-1", {method: "HEAD"});
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Accept-Ranges"), "bytes");
  assert.equal(response.headers.get("Content-Range"), null);
  assert.equal(Number(response.headers.get("Content-Length")), VIDEO_BYTES);
  assert.equal((await bytes(response)).length, 0);
});

test("native statuses and ineligible bodies bypass the fallback", async () => {
  for (const options of [
    {status: 206}, {status: 304}, {status: 416}, {status: 404},
    {mode: "wrong-length"}, {mode: "encoded"}, {mode: "html"}, {path: "/other.mp4"},
  ]) {
    const {response} = await request("bytes=0-1", options);
    assert.equal(response.status, options.status || 200, JSON.stringify(options));
    assert.equal(response.headers.get("Accept-Ranges"), null);
    if (response.body) await response.body.cancel();
  }
});

test("early upstream EOF fails the partial body instead of silently truncating it", async () => {
  let response;
  try {
    ({response} = await request("bytes=0-100", {mode: "short"}));
  } catch (error) {
    // workerd may abort before headers reach Miniflare's HTTP client.
    assert.equal(error.message, "fetch failed");
    return;
  }
  assert.equal(response.status, 206);
  await assert.rejects(() => response.arrayBuffer());
});

test("completed intervals and client cancellation stop the upstream reader", async () => {
  for (const cancelledByClient of [false, true]) {
    const {response, id} = await request(cancelledByClient ? "bytes=0-" : "bytes=0-10", {mode: "slow"});
    if (cancelledByClient) {
      const reader = response.body.getReader();
      await reader.read();
      await reader.cancel();
    } else await response.arrayBuffer();
    let state;
    for (let attempt = 0; attempt < 30; attempt++) {
      state = await (await mf.dispatchFetch(`http://localhost/fixture-state?id=${id}`)).json();
      if (state.cancelled) break;
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    assert.equal(state.cancelled, true, JSON.stringify(state));
    assert.ok(state.read < VIDEO_BYTES / 4, `upstream was drained: ${JSON.stringify(state)}`);
  }
});
