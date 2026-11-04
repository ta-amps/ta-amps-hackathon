// A public copy can run its checks on a made-up sample list. A deploy never can.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));

test("the deploy's build command drops the sample setting", () => {
  const config = readFileSync(new URL("../wrangler.jsonc", import.meta.url), "utf8");
  const command = /"command":\s*"([^"]+)"/.exec(config)[1];
  assert.match(command, /env -u TELEION_SAMPLE_WORD_LIST[^&]*build\.py/);
  assert.match(command, /env -u TELEION_SAMPLE_WORD_LIST[^&]*check_words\.py/);
});

test("build.py fails closed with no real list and no sample setting", () => {
  const env = { ...process.env, BANNED_WORDS: "/nonexistent/word-list.json" };
  delete env.TELEION_SAMPLE_WORD_LIST;
  const run = spawnSync("python3", ["-c", "import build,sys\ntry:\n  build.shared_words()\nexcept build.BuildError:\n  sys.exit(7)"], { cwd: root, env });
  assert.equal(run.status, 7);
});

test("a named list that is missing is never replaced by the sample", () => {
  const env = { ...process.env, BANNED_WORDS: "/nonexistent/word-list.json", TELEION_SAMPLE_WORD_LIST: "1" };
  const run = spawnSync("python3", ["-c", "import build,sys\ntry:\n  build.shared_words()\nexcept build.BuildError:\n  sys.exit(7)"], { cwd: root, env });
  assert.equal(run.status, 7);
});
