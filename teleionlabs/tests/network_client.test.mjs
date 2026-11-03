// Practice case: an example, not a real person or case. Deferred browser reads run entirely in memory.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const code = await readFile(new URL("../static/assets/network.js", import.meta.url), "utf8");
const fixture = () => ({ generated_at: new Date().toISOString(), totals: { workers: 0, data_centres: 0, continents: 0, claims: 0, nonprofit_claims: 0 }, data_centres: [], continents: [], recent_claims: [], replay: { claims: [] } });
const settle = () => new Promise((resolve) => setImmediate(resolve));

function harness() {
  const band = { hidden: true }, timers = new Map(); let serial = 0;
  const window = { matchMedia: () => ({ matches: true }), AbortController,
    setTimeout: (fn, ms) => { const n = ++serial; timers.set(n, { fn, ms }); return n; },
    clearTimeout: (n) => { timers.delete(n); } };
  const document = { querySelectorAll: () => [], hidden: false };
  vm.runInNewContext(code, { window, document, AbortController, URLSearchParams, clearTimeout: window.clearTimeout, Date });
  const root = { getAttribute: () => null, querySelector: () => null, removeAttribute() {}, setAttribute() {} };
  const net = window.TaNetwork.mount(root, { words: { controls: { replay: "Replay" }, replay_error: "Replay unavailable", error: { text: "Unavailable", link: "Status" }, herma: { dashboard: "/status/" } }, geo: {}, source: "/api/network" });
  net.find = (name) => name === "band" ? band : null;
  net.clearPulses = () => {}; net.render = () => {}; net.status = () => {}; net.refresh = 60000;
  const ordinaryLoad = net.load.bind(net);
  let loads = 0; net.load = () => { loads++; };
  return { net, band, window, document, timers, ordinaryLoad, loads: () => loads };
}

test("Back to live invalidates a replay that resolves later", async () => {
  const h = harness(); let complete;
  h.net.fetchData = () => new Promise((resolve) => { complete = resolve; });
  h.net.startReplay(); h.net.stopReplay(); complete({ json: fixture() }); await settle();
  assert.equal(h.net.replaying, null); assert.equal(h.net.replayPending, false); assert.equal(h.band.hidden, true); assert.equal(h.loads(), 1);
});

test("pausing and changing a filter invalidate pending replay results", async () => {
  for (const action of ["pause", "filter"]) {
    const h = harness(); let complete;
    h.net.fetchData = () => new Promise((resolve) => { complete = resolve; });
    h.net.startReplay();
    if (action === "pause") h.net.setPaused(true); else h.net.setKind("nonprofit");
    complete({ json: fixture() }); await settle();
    assert.equal(h.net.replaying, null); assert.equal(h.band.hidden, true);
    assert.equal(h.loads(), action === "pause" ? 0 : 1);
  }
});

test("pausing an active replay clears its scheduled steps without another read", () => {
  const h = harness();
  const step = h.window.setTimeout(() => { throw new Error("a cancelled replay step ran"); }, 100);
  h.net.replaying = { shell: {}, steps: [step] }; h.band.hidden = false;
  h.net.setPaused(true);
  assert.equal(h.net.replaying, null); assert.equal(h.band.hidden, true); assert.equal(h.timers.size, 0); assert.equal(h.loads(), 0);
});

test("a replay failure resets its state and schedules the next ordinary read", async () => {
  const h = harness(); h.net.fetchData = () => Promise.reject(new Error("offline"));
  h.net.startReplay(); await settle();
  assert.equal(h.net.replaying, null); assert.equal(h.net.replayPending, false); assert.equal(h.band.hidden, true);
  assert.equal(h.timers.size, 1); const timer = [...h.timers.values()][0]; assert.equal(timer.ms, 60000);
  timer.fn(); assert.equal(h.loads(), 1);
});

test("the read deadline remains active after headers, aborts a stalled JSON body, and clears afterward", async () => {
  const h = harness(); let bodyStarted = false;
  h.window.fetch = async (_url, options) => ({ status: 200, ok: true, headers: new Headers(), json: () => {
    bodyStarted = true;
    return new Promise((_resolve, reject) => options.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true }));
  } });
  const read = h.net.fetchData(false); await settle();
  assert.equal(bodyStarted, true); assert.equal(h.timers.size, 1);
  const timer = [...h.timers.values()][0]; assert.equal(timer.ms, 15000); timer.fn();
  await assert.rejects(read, /aborted/); assert.equal(h.timers.size, 0);
});

test("cancelling a pending replay aborts its fetch and cannot revive its band", async () => {
  const h = harness(); let signal;
  h.window.fetch = (_url, options) => {
    signal = options.signal;
    return new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true }));
  };
  h.net.startReplay(); h.net.stopReplay(); await settle();
  assert.equal(signal.aborted, true); assert.equal(h.net.replaying, null); assert.equal(h.band.hidden, true); assert.equal(h.timers.size, 0);
});

test("pausing or hiding the page prevents an ordinary pending read from applying late data", async () => {
  for (const action of ["pause", "hide"]) {
    const h = harness(); let complete;
    h.net.fetchData = () => new Promise((resolve) => { complete = resolve; });
    h.ordinaryLoad();
    if (action === "pause") h.net.setPaused(true); else h.document.hidden = true;
    complete({ json: fixture(), age: 0 }); await settle();
    assert.equal(h.net.data, null); assert.equal(h.timers.size, 0);
  }
});

test("a slower earlier ordinary read cannot replace a newer reading", async () => {
  const h = harness(), pending = [];
  h.net.fetchData = () => new Promise((resolve) => { pending.push(resolve); });
  h.ordinaryLoad(); h.ordinaryLoad();
  const newer = fixture(); newer.totals.workers = 8;
  pending[1]({ json: newer, age: 0 }); await settle();
  const older = fixture(); older.totals.workers = 99;
  pending[0]({ json: older, age: 0 }); await settle();
  assert.equal(h.net.data.totals.workers, 8); assert.equal(h.timers.size, 1);
});
