"""Behavior of the live node against a fake Fabric, a fake GitHub and a fake model: routing, reuse, refusals, learning."""

import json
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from eranos.model_client import BudgetExhausted, ModelCall, ModelUnavailable

from omninode_live import core, feed, grid as gridmod, run_checker, run_maker, run_tuner, spec as specmod
from omninode_live.core import ITEMS_STORE, RECORD_STORE, SPEC_KEY, Screen, TwoLedgers, ledgers


class FakeFabric:
    def __init__(self, key_id, shared=None):
        self.key_id, self.label, self.db = key_id, "test", shared if shared is not None else {}
        self.tasks = []

    def get(self, store, key):
        row = self.db.get((store, key))
        return (json.loads(json.dumps(row[0])), row[1]) if row else None

    def put(self, store, key, value, *, expected, tags):
        row = self.db.get((store, key))
        if row and expected != row[1]:
            raise RuntimeError("version conflict")
        version = (row[1] if row else 0) + 1
        self.db[(store, key)] = (json.loads(json.dumps(value)), version)
        return version

    def list(self, store, prefix="", limit=200):
        return [(k[1], json.loads(json.dumps(v[0])), v[1]) for k, v in sorted(self.db.items()) if k[0] == store and k[1].startswith(prefix)]

    def enqueue(self, **kw):
        self.tasks.append(kw)
        return kw["task_id"]


REPOS = [
    {"full_name": "a/skills-one", "description": "agent skills pack for docs", "license": {"spdx_id": "MIT"}, "stargazers_count": 90, "topics": ["agent-skills"], "pushed_at": "2026-10-30T00:00:00Z"},
    {"full_name": "b/format-tool", "description": "a fast deterministic code formatter", "license": {"spdx_id": "Apache-2.0"}, "stargazers_count": 80, "topics": ["code-formatter"], "pushed_at": "2026-10-30T00:00:00Z"},
    {"full_name": "c/closed", "description": "agent skills, closed licence", "license": None, "stargazers_count": 70, "topics": [], "pushed_at": "2026-10-30T00:00:00Z"},
    {"full_name": "d/bad-word", "description": "a synthetic data skill", "license": {"spdx_id": "MIT"}, "stargazers_count": 60, "topics": [], "pushed_at": "2026-10-30T00:00:00Z"},
]


def github(calls=None):
    def handle(request):
        if calls is not None:
            calls.append(request.url.path)
        if "/search/" in request.url.path:
            return httpx.Response(200, json={"items": REPOS})
        if request.url.path.endswith("/releases/latest"):
            return httpx.Response(200, json={"tag_name": "v1.0.0", "published_at": "2026-10-29T00:00:00Z"})
        if request.url.path.startswith("/repos/"):
            name = request.url.path.split("/repos/")[1]
            return httpx.Response(200, json=next(r for r in REPOS if r["full_name"] == name))
        return httpx.Response(404)

    g = feed.GitHub(transport=httpx.MockTransport(handle), sleep=lambda _s: None)
    return g


class FakeModel:
    def __init__(self, mid, log, *, bad=False):
        self.mid, self.log, self.bad = mid, log, bad

    def chat_json(self, system, user, *, meter, **_kw):
        self.log.append(self.mid)
        meter.add({"id": self.mid}, ModelCall(input_tokens=100, output_tokens=50, seconds=0.1, cost_usd=0.001))
        data = json.loads(user)
        if isinstance(data, dict):  # labeling
            labels = []
            for r in data["repositories"]:
                quote = r["description"][:20]
                labels.append({"key": r["key"], "category": "skill_pack" if "skill" in r["description"] else "deterministic_tool",
                               "determinism": "mixed", "use_cases": ["catalog"], "summary": "It does a useful documented job for agents.",
                               "evidence": ["not in the source" if self.bad else quote], "confidence_milli": 800})
            return {"labels": labels}
        return {"checks": [{"key": r["key"], "verdict": "approve", "reason": "matches"} for r in data]}


def run(fabric, log, *, run_id, bad=False, calls=None, gh=None):
    models = lambda m: FakeModel(m, log, bad=bad)  # noqa: E731
    return run_maker.execute(fabric, gh or github(calls), Screen(), models, "k_checker", run_id=run_id, task_id="t" + run_id, token=1)


def check(db, run_id, log):
    fabric = FakeFabric("k_checker", db)
    r, v = fabric.get(RECORD_STORE, core.RUN_PREFIX + run_id)
    spec, _ = fabric.get(RECORD_STORE, SPEC_KEY)
    g = gridmod.node_grid()
    node = run_checker.LiveFeedChecker(fabric=fabric, github=github(), screen=Screen(), models=lambda m: FakeModel(m, log), spec=spec, grid=g, cell=gridmod.cell_of(spec, g))
    res = node.execute({"maker_worker_key": r["maker_key_id"], "maker_output": r}, {"checker_worker_key": fabric.key_id})
    assert res.ok
    r["check"] = {"verdicts": {k: {x: w[x] for x in w if x != "value"} for k, w in res.output["verdicts"].items()},
                  "attempts": node.attempts, "reuse_checks": res.output["reuse_checks"]}
    r["status"] = "checked"
    fabric.put(RECORD_STORE, core.RUN_PREFIX + run_id, r, expected=v, tags=[])
    latest = fabric.get(RECORD_STORE, core.LATEST_KEY)
    fabric.put(RECORD_STORE, core.LATEST_KEY, {**latest[0], "status": "checked"}, expected=latest[1], tags=[])
    return res


def test_modes_route_each_item_and_word_list_keeps_the_name_out():
    fabric, log = FakeFabric("k_maker"), []
    record = run(fabric, log, run_id="r1")
    by = {i["key"]: i for i in record["items"]}
    assert by["repo-a--skills-one"]["status"] == "awaiting_check"
    assert by["repo-c--closed"]["status"] == "dropped_license"
    assert "d/bad-word" not in json.dumps(record) and not any("bad-word" in k for k in by)
    c = record["counts"]
    assert c["deterministic"]["dropped_word_list"] == 1 and c["deterministic"]["dropped_license"] == 1
    assert c["model"]["items_sent"] == 2 and c["hybrid"]["rule_accepted"] == 2 and c["reuse"]["answered_no_model"] == 0
    assert log, "the model really was called"


def test_second_run_reuses_checked_work_with_no_model_call():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1")
    check(fabric.db, "r1", log)
    log.clear()
    record = run(fabric, log, run_id="r2")
    assert log == [], "unchanged and approved: no model call"
    assert record["counts"]["reuse"]["answered_no_model"] == 2 and record["counts"]["tokens"] == {"input": 0, "output": 0}


def test_a_changed_item_goes_back_to_the_model():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1")
    check(fabric.db, "r1", log)
    log.clear()
    REPOS[0]["description"] = "agent skills pack for docs, now with search"
    REPOS[0]["pushed_at"] = "2026-11-01T00:00:00Z"
    try:
        record = run(fabric, log, run_id="r2")
    finally:
        REPOS[0]["description"], REPOS[0]["pushed_at"] = "agent skills pack for docs", "2026-10-30T00:00:00Z"
    assert record["counts"]["reuse"]["answered_no_model"] == 1 and record["counts"]["model"]["items_sent"] == 1 and len(log) == 1


def test_hybrid_rule_refuses_a_quote_that_is_not_in_the_source():
    fabric, log = FakeFabric("k_maker"), []
    record = run(fabric, log, run_id="r1", bad=True)
    assert record["counts"]["hybrid"]["rule_rejected"] == 2 and record["counts"]["hybrid"]["rule_accepted"] == 0
    assert all(v[0].get("labels") is None and v[0]["check"]["verdict"] == "none" for k, v in fabric.db.items() if k[0] == ITEMS_STORE), "a rejected label is not stored as a label"
    assert record["items"][0]["rule_failures"] == ["evidence_not_in_source"]


@pytest.mark.parametrize("label,failure", [
    ({"category": "made_up"}, "category_not_in_taxonomy"), ({"confidence_milli": 100}, "confidence_below_threshold"),
    ({"summary": "see https://example.com for all of the details here"}, "summary_has_link_or_address"),
    ({"summary": "A synthetic data helper that does a real job"}, "summary_word_list"), ({"category": "skill_pack"}, None),
])
def test_rule_cases(label, failure):
    item = {"description": "a formatter tool", "topics": ["fmt"], "full_name": "x/fmt"}
    s = specmod.seed_spec()["parameters"]["settings"]
    base = {"category": "deterministic_tool", "determinism": "deterministic", "use_cases": ["fmt"], "summary": "Formats code for people and agents alike.", "evidence": ["formatter"], "confidence_milli": 800}
    got = feed.validate_label({**base, **label}, item, s, Screen())
    if failure:
        assert failure in got
    else:
        assert "skill_pack_without_skill_in_source" in got


def test_same_key_cannot_check_its_own_work():
    fabric, log = FakeFabric("k_same"), []
    g = gridmod.node_grid()
    spec = specmod.seed_spec()
    node = run_checker.LiveFeedChecker(fabric=fabric, github=github(), screen=Screen(), models=lambda m: FakeModel(m, log), spec=spec, grid=g, cell=gridmod.cell_of(spec, g))
    res = node.execute({"maker_worker_key": "K_SAME", "maker_output": {"items": [], "run_id": "r"}}, {})
    assert not res.ok and res.diagnostics["error_code"] == "self_review_conflict" and log == []
    gh, ctx = github(), feed.RunContext(run_id="x", spec=spec, spec_version=1, fabric=fabric, github=github(), screen=Screen(), models=None)
    node = feed.build_pipeline(ctx, g, gridmod.cell_of(spec, g), maker_key_id="k_same", checker_key_id="k_same")
    res = node.execute({"run_id": "x"})
    assert not res.ok and res.diagnostics["error_code"] == "self_review_conflict" and gh.calls == 0


def test_checker_refuses_a_fine_tune_on_the_maker():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1")
    value, v = fabric.get(ITEMS_STORE, "repo-a--skills-one")
    fabric.put(ITEMS_STORE, "repo-a--skills-one", {**value, "fine_tune": "ft-1"}, expected=v, tags=[])
    res = check(fabric.db, "r1", log)
    assert res.output["verdicts"]["repo-a--skills-one"]["verdict"] == "reject"


def test_checker_uses_the_other_model_and_catches_a_license_change():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1")
    maker_models = set(log)
    log.clear()
    REPOS[1]["license"] = {"spdx_id": "GPL-3.0"}
    try:
        res = check(fabric.db, "r1", log)
    finally:
        REPOS[1]["license"] = {"spdx_id": "Apache-2.0"}
    assert res.output["verdicts"]["repo-b--format-tool"]["verdict"] == "reject"
    assert any("license_differs" in f for f in res.output["verdicts"]["repo-b--format-tool"]["findings"])
    assert res.output["verdicts"]["repo-a--skills-one"]["verdict"] == "approve"
    assert set(log) == {run_checker.OTHER[m] for m in maker_models} or len(maker_models) == 2


def test_tuner_changes_the_mix_and_the_next_run_uses_it():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1")
    check(fabric.db, "r1", log)
    done = run_tuner.step(fabric, time.time())
    spec, version = fabric.get(RECORD_STORE, SPEC_KEY)
    assert version == 2 and spec["parameters"]["model"]["tuner_version"] == 1
    change = spec["change_log"][-1]
    assert change["caused_by_run"] == "r1" and change["outcomes"] == 2 and change["from"] != change["to"]
    assert sum(change["to"].values()) == pytest.approx(1.0)
    stage = done["change"]["grid"]["stage"]
    assert stage in ("promoted", "verified", "evaluated")
    record = run(fabric, log, run_id="r2")
    assert record["spec_version"] == 2 and record["mix_used"] == change["to"] and record["tuner_version_used"] == 1


def test_grid_ledger_survives_being_stored():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1")
    check(fabric.db, "r1", log)
    run_tuner.step(fabric, time.time())
    state, _ = fabric.get(RECORD_STORE, core.GRID_KEY)
    g = gridmod.node_grid()
    ledger, costs = gridmod.load_ledger(g, state)
    assert ledger._records and costs.observations
    assert any(r.stage == "proposed" for r in ledger._records.values()), "the tuner's new set awaits dispatch"


def test_retrain_trigger_makes_one_task_and_starts_no_training():
    fabric = FakeFabric("k_maker")
    spec = specmod.seed_spec()
    spec["parameters"]["settings"]["retrain_min_examples"] = 1
    items = {"k": {"full_name": "a/b", "description": "d", "topics": [], "labels": {"category": "other"}, "maker_model": "m", "check": {"verdict": "approve"}}}
    first = run_tuner.retrain_trigger(fabric, [], items, spec)
    second = run_tuner.retrain_trigger(fabric, [], items, spec)
    assert first["state"] == "task_created" and second["state"] == "already_exported" and len(fabric.tasks) == 1
    assert "starts no training" in fabric.tasks[0]["brief"]["spend"]
    assert fabric.get(RECORD_STORE, first["dataset_record"])[0]["rows"][0]["verdict"] == "approve"


def test_daily_ceiling_refuses_before_any_call(tmp_path):
    two = ledgers(tmp_path / "shared.json", tmp_path / "node.json", ceiling=0.01)
    day = two.reserve(0.009)
    with pytest.raises(BudgetExhausted):
        two.reserve(0.009)
    two.settle(0.001, reserved=0.009, day=day)
    assert json.loads((tmp_path / "shared.json").read_text())["days"][day] == 0.001
    capped = ledgers(tmp_path / "s2.json", tmp_path / "n2.json", ceiling=500.0)
    assert capped.node.daily_usd == core.DAILY_CEILING_USD


def test_failed_model_attempt_is_recorded_and_says_nothing_about_the_model():
    class Down:
        def chat_json(self, *_a, **_k):
            raise ModelUnavailable("muse-spark-1.3 answered 500")

    fabric = FakeFabric("k_maker")
    record = run_maker.execute(fabric, github(), Screen(), lambda _m: Down(), "k_checker", run_id="r1", task_id="t", token=1)
    assert record["counts"]["model"]["attempts_failed"] >= 1 and record["attempts"][0]["outcome"] == "failed"
    record["check"] = {"verdicts": {}}
    assert run_tuner.outcomes_from_runs([record], specmod.seed_spec()["parameters"]["model"]["rewards"]) == []


def test_only_meta_models_without_fine_tunes():
    with pytest.raises(ValueError):
        core.meta_model("some-other-model", {"runtime": {}}, None)
    assert all(v["fine_tune"] is None for v in specmod.seed_spec()["parameters"]["model"]["variants"])


def test_github_no_credential_and_stops_when_allowance_is_low():
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"tag_name": "v1"}, headers={"x-ratelimit-remaining": "3"})

    g = feed.GitHub(transport=httpx.MockTransport(handle), sleep=lambda _s: None)
    g.latest_release("a/b")
    assert "authorization" not in seen[0].headers and not g.spare()


def test_execution_report_fits_the_fabric_contract():
    allowed = {"version", "harness", "model", "summaries", "contract", "usage", "blocks", "artifact_refs"}
    with_model = core.execution_report("maker", "w", "p", "s", [{"model": "muse-spark-1.3", "input_tokens": 1, "output_tokens": 2, "cost_usd": 0.1}])
    without = core.execution_report("tuner", "w", "p", "s", [])
    assert set(with_model) <= allowed and set(without) <= allowed
    assert set(with_model["summaries"]) == {"problem", "solution"} and without["model"] is None and with_model["usage"]["total_tokens"] == 3


def test_running_out_of_tokens_counts_only_with_the_nodes_settings_on_record():
    rewards = specmod.seed_spec()["parameters"]["model"]["rewards"]
    item = {"key": "k", "status": "label_failed", "maker_variant": "label-muse-spark", "trace": []}
    old = {"run_id": "r", "check": {"verdicts": {}}, "items": [item], "attempts": [{"step": "label", "item_keys": ["k"], "outcome": "failed", "error": "m used all 3000 tokens"}]}
    new = {"run_id": "r", "check": {"verdicts": {}}, "items": [item], "attempts": [{"step": "label", "item_keys": ["k"], "outcome": "failed", "error": "m used all 8000 tokens", "max_output_tokens": 8000}]}
    assert run_tuner.outcomes_from_runs([old], rewards) == []
    assert [o.success for o in run_tuner.outcomes_from_runs([new], rewards)] == [0.0]


def test_shim_submit_sends_an_array_and_reports_what_it_could_read_back(tmp_path):
    from omninode_live import shim as shimmod

    bodies, stored = [], set()

    def handle(request):
        if request.url.path == "/q/submit":
            body = json.loads(request.content)
            bodies.append(body)
            assert isinstance(body["task_objects"], list)
            stored.update(o["object_key"] for o in body["task_objects"] if o["object_key"] != "lost")
            return httpx.Response(200, json={"ok": True})
        key = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200 if key in stored else 404, json={})

    cred = tmp_path / "c.json"
    cred.write_text(json.dumps({"agent_id": "a", "worker_uuid": "w", "worker_token": "t"}))
    s = shimmod.Shim("a", cred, http=httpx.Client(base_url="https://x.invalid", transport=httpx.MockTransport(handle)))
    assert s.publish({"one": {"summary": "s"}}, "s", "i")["ok"] is True
    missing = s.publish({"one": {"summary": "s"}, "lost": {"summary": "s"}}, "s", "j")
    assert missing["ok"] is False and missing["readable"] == ["one"]
    assert shimmod.public_key("repo-a.b--c") == "feed_repo-a_b_c"


def test_a_failed_label_waits_before_it_is_paid_for_again_and_a_new_digest_does_not():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1", bad=True)
    log.clear()
    record = run(fabric, log, run_id="r2")
    assert log == [] and record["counts"]["deterministic"]["deferred"] == 2
    REPOS[1]["description"] = "a fast deterministic code formatter, version two"
    REPOS[1]["pushed_at"] = "2026-11-01T00:00:00Z"
    try:
        record = run(fabric, log, run_id="r3")
    finally:
        REPOS[1]["description"], REPOS[1]["pushed_at"] = "a fast deterministic code formatter", "2026-10-30T00:00:00Z"
    assert len(log) == 1 and record["counts"]["model"]["items_sent"] == 1


def test_github_down_keeps_the_item_pending_and_a_changed_source_is_refused():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1")
    r, _ = fabric.get(RECORD_STORE, core.RUN_PREFIX + "r1")
    spec, _ = fabric.get(RECORD_STORE, SPEC_KEY)
    g = gridmod.node_grid()
    down = feed.GitHub(transport=httpx.MockTransport(lambda _r: httpx.Response(502)), sleep=lambda _s: None)
    ck = FakeFabric("k_checker", fabric.db)
    node = run_checker.LiveFeedChecker(fabric=ck, github=down, screen=Screen(), models=lambda m: FakeModel(m, log), spec=spec, grid=g, cell=gridmod.cell_of(spec, g))
    res = node.execute({"maker_worker_key": "k_maker", "maker_output": r}, {"checker_worker_key": "k_checker"})
    assert {v["verdict"] for v in res.output["verdicts"].values()} == {"pending"}
    REPOS[0]["description"] = "something else now"
    try:
        node = run_checker.LiveFeedChecker(fabric=ck, github=github(), screen=Screen(), models=lambda m: FakeModel(m, log), spec=spec, grid=g, cell=gridmod.cell_of(spec, g))
        res = node.execute({"maker_worker_key": "k_maker", "maker_output": r}, {"checker_worker_key": "k_checker"})
    finally:
        REPOS[0]["description"] = "agent skills pack for docs"
    assert "source_text_changed" in res.output["verdicts"]["repo-a--skills-one"]["findings"]


def test_a_store_failure_after_labeling_keeps_the_paid_attempts_on_the_record():
    class Breaks(FakeFabric):
        def put(self, store, key, value, *, expected, tags):
            if store == ITEMS_STORE:
                raise RuntimeError("version conflict")
            return super().put(store, key, value, expected=expected, tags=tags)

    fabric, log = Breaks("k_maker"), []
    record = run(fabric, log, run_id="r1")
    assert record["ok"] is False and record["status"] == "failed" and record["attempts"] and record["attempts"][0]["input_tokens"] == 100


def test_the_grid_gates_batch_size_and_the_change_log_discloses_what_was_left_out():
    fabric, log = FakeFabric("k_maker"), []
    run(fabric, log, run_id="r1")
    check(fabric.db, "r1", log)
    done = run_tuner.step(fabric, time.time())
    change = done["change"]
    assert change["grid"]["stage"] == "promoted" and change["batch_size"] == {"from": 8, "to": 10, "gate": "the run's parameter set reached promoted"}
    assert "not a model comparison" in change["reading"] and change["excluded_from_outcomes"] == []
    old = {"run_id": "r", "attempts": [{"step": "label", "variant": "v", "item_keys": ["k"], "outcome": "failed", "error": "m used all 3000 tokens"}]}
    assert run_tuner.excluded_outcomes([old])[0]["items"] == 1


def test_a_draw_depends_on_the_run_and_the_mix_not_the_spec_version():
    fabric, log = FakeFabric("k_maker"), []
    a = run(fabric, log, run_id="same")
    value, v = fabric.get(RECORD_STORE, SPEC_KEY)
    fabric.put(RECORD_STORE, SPEC_KEY, value, expected=v, tags=[])
    fabric.db = {k: x for k, x in fabric.db.items() if k[0] != ITEMS_STORE and ".run." not in k[1]}
    b = run(fabric, log, run_id="same")
    assert a["draws"] == b["draws"]
