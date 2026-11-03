// Offline fixture tests for the onboarding worker example in content/start.json (#loop).
// Verifies all six scenarios from ANTIGRAVITY_REVIEW_02_ONBOARDING_AND_CLAIMS.md plus missing token.
// Makes zero network calls and uses no real credentials.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const START_JSON = fileURLToPath(new URL("../content/start.json", import.meta.url));

async function loadLoopSnippet() {
  const start = JSON.parse(await readFile(START_JSON, "utf8"));
  const loop = start.blocks.find((b) => b.id === "loop");
  assert.ok(loop && typeof loop.code === "string", "content/start.json must contain #loop code");
  return loop.code;
}

async function runScenario(code, scenario, token = "review-fixture") {
  const calls = [];
  const timers = new Map();
  let claims = 0;
  let seq = 0;
  const response = (status, body) => ({
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  });

  const fetch = async (url, opt = {}) => {
    const path = new URL(url).pathname;
    const body = opt.body ? JSON.parse(opt.body) : null;
    calls.push({ path, body, headers: opt.headers || {} });
    if (path === "/v1/tasks/claim") {
      claims++;
      if (scenario === "claim_unavailable") return response(503, { error: "unavailable" });
      return claims === 1
        ? response(200, { task_id: "fixture-task", fencing_token: 1, heartbeat_seconds: 30, brief: { title: "example" } })
        : response(204, null);
    }
    if (path === "/v1/tasks/heartbeat") {
      return response(scenario === "heartbeat_rejected" ? 409 : 200, { ok: scenario !== "heartbeat_rejected" });
    }
    if (path.startsWith("/v1/stores/")) {
      if (scenario === "save_network_error") throw new Error("fixture network failure");
      if (scenario === "heartbeat_rejected") {
        for (const cb of timers.values()) await cb();
      }
      return scenario === "save_conflict"
        ? response(409, { error: "version_conflict" })
        : response(200, { version: 1 });
    }
    if (path === "/v1/tasks/submit") {
      return response(
        scenario === "submit_rejected" || scenario === "heartbeat_rejected" ? 409 : 200,
        { ok: scenario !== "submit_rejected" && scenario !== "heartbeat_rejected" },
      );
    }
    throw new Error(`Unexpected mocked path ${path}`);
  };

  let error = null;
  try {
    await vm.runInNewContext(
      `(async () => {\n${code}\n})()`,
      {
        process: { env: token ? { TESSERA_TOKEN: token } : {} },
        fetch,
        setInterval: (cb) => {
          const id = ++seq;
          timers.set(id, cb);
          return id;
        },
        clearInterval: (id) => timers.delete(id),
      },
      { timeout: 1000 },
    );
  } catch (e) {
    error = e.message;
  }

  return {
    error,
    calls,
    submitCalls: calls.filter((c) => c.path === "/v1/tasks/submit"),
    claimCalls: claims,
    unclearedTimers: timers.size,
  };
}

test("onboarding worker example rejects missing TESSERA_TOKEN before making requests", async () => {
  const code = await loadLoopSnippet();
  const out = await runScenario(code, "happy", "");
  assert.match(out.error || "", /TESSERA_TOKEN/);
  assert.equal(out.calls.length, 0);
  assert.equal(out.unclearedTimers, 0);
});

test("1. happy path: claims, saves version 1, submits with idempotency key, stops cleanly on 204", async () => {
  const code = await loadLoopSnippet();
  const out = await runScenario(code, "happy");
  assert.equal(out.error, null);
  assert.equal(out.claimCalls, 2);
  assert.equal(out.submitCalls.length, 1);
  assert.deepEqual(out.submitCalls[0].body, {
    task_id: "fixture-task",
    fencing_token: 1,
    output: { record: "fixture-task", version: 1 },
  });
  assert.equal(out.submitCalls[0].headers["idempotency-key"], "fixture-task:1");
  assert.equal(out.unclearedTimers, 0);
});

test("2. save 409 conflict: stops dependent work, never submits without version, cleans up heartbeat", async () => {
  const code = await loadLoopSnippet();
  const out = await runScenario(code, "save_conflict");
  assert.match(out.error || "", /save 409/);
  assert.equal(out.submitCalls.length, 0);
  assert.equal(out.claimCalls, 1);
  assert.equal(out.unclearedTimers, 0);
});

test("3. submit 409 rejection: surfaces error instead of ignoring rejection and claiming again", async () => {
  const code = await loadLoopSnippet();
  const out = await runScenario(code, "submit_rejected");
  assert.match(out.error || "", /submit 409/);
  assert.equal(out.submitCalls.length, 1);
  assert.equal(out.claimCalls, 1);
  assert.equal(out.unclearedTimers, 0);
});

test("4. claim 503 unavailable: distinguishes error from 204 idle queue", async () => {
  const code = await loadLoopSnippet();
  const out = await runScenario(code, "claim_unavailable");
  assert.match(out.error || "", /claim 503/);
  assert.equal(out.submitCalls.length, 0);
  assert.equal(out.claimCalls, 1);
  assert.equal(out.unclearedTimers, 0);
});

test("5. save network throw: cleans up heartbeat timer in finally block", async () => {
  const code = await loadLoopSnippet();
  const out = await runScenario(code, "save_network_error");
  assert.match(out.error || "", /fixture network failure/);
  assert.equal(out.submitCalls.length, 0);
  assert.equal(out.unclearedTimers, 0);
});

test("6. heartbeat 409 during work: marks lease lost, aborts before submit, cleans up timer", async () => {
  const code = await loadLoopSnippet();
  const out = await runScenario(code, "heartbeat_rejected");
  assert.match(out.error || "", /lease lost/);
  assert.equal(out.submitCalls.length, 0);
  assert.equal(out.claimCalls, 1);
  assert.equal(out.unclearedTimers, 0);
});
