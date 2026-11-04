"""The pre-step: real table, fake Fabric, GitHub and model. It may narrow and force, never spend, approve or break a run."""

import json
from pathlib import Path

import httpx
import pytest
from eranos.model_client import BudgetExhausted, ModelCall

from omninode_live import core, feed, prestep, run_tuner, spec as specmod
from omninode_live.core import ITEMS_STORE, RECORD_STORE, Screen
from tests.test_behavior import FakeFabric, FakeModel, check

TABLE = Path(prestep.__file__).with_name("prestep_rules.json")


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("OMNINODE_PRESTEP_RULES", str(TABLE))


def traces():
    return prestep.read_traces()


def repo_github(repos, calls=None):
    def handle(request):
        if calls is not None:
            calls.append(request.url.path)
        if "/search/" in request.url.path:
            return httpx.Response(200, json={"items": repos})
        if request.url.path.endswith("/releases/latest"):
            return httpx.Response(200, json={"tag_name": "v2", "published_at": "2026-10-29T00:00:00Z"})
        name = request.url.path.split("/repos/")[1]
        return httpx.Response(200, json=next(r for r in repos if r["full_name"] == name))

    return feed.GitHub(transport=httpx.MockTransport(handle), sleep=lambda _s: None)


def repo(name, description, topics, stars=100):
    return {"full_name": name, "description": description, "license": {"spdx_id": "MIT"}, "stargazers_count": stars, "topics": topics, "pushed_at": "2026-11-01T00:00:00Z"}


FORCED = repo("a/fmt", "A fast formatter for Ruby code, written in plain Rust.", ["code-formatter", "ruby"])
TO_MODEL = repo("b/thing", "A helper that keeps notes for a small research team", ["notes"])
SKILLS = repo("c/agent-skills", "Skills for writing better documents with coding agents.", ["agent-skills", "docs"])


def universe(ids, pinned=()):
    return [{"id": i, "kind": "category", "text": t, "sent": True, "pinned": i in pinned} for i, t in ids.items()]


CFG = json.loads(TABLE.read_text())["shortlist"]


def test_shortlist_keeps_what_matches_and_always_keeps_pinned():
    d = prestep.shortlist("a linter and static-analysis parser for python", universe(
        {"tool": "linter static-analysis parser compiler", "agents": "agent framework orchestration", "train": "model training gpu", "other": "other"}, pinned=["other"]), CFG)
    assert not d["fell_open"] and "tool" in d["kept"] and "other" in d["kept"] and "train" in d["cut"]
    assert d["tokens_after_est"] < d["tokens_before_est"] and d["ms"] < 50


def test_shortlist_falls_open_with_no_signal_and_on_a_small_universe():
    u = universe({"tool": "linter parser", "agents": "agent framework", "train": "model training"})
    d = prestep.shortlist("zzz qqq", u, CFG)
    assert d["fell_open"] and d["reason"] == "low_confidence" and d["cut"] == [] and d["confidence"] < CFG["min_confidence"]
    d = prestep.shortlist("linter", universe({"tool": "linter", "x": "y"}), CFG)
    assert d["fell_open"] and d["reason"] == "small_universe" and d["cut"] == []


def test_signals_find_repo_names_paths_and_identifiers():
    sig = prestep.signals("Look at rubocop/rubocop and src/app/main.py using static-analysis and parseTree")
    assert "rubocop/rubocop" in sig["repo_names"] and sig["signature"]["has_repo_name"] and sig["signature"]["needs_github"]
    assert "static-analysis" in sig["identifiers"] and sig["signature"]["has_path"]


def test_forced_label_skips_the_model_but_not_the_rule_the_store_or_the_check(on):
    fabric, log = FakeFabric("k_maker"), []
    gh = repo_github([FORCED, TO_MODEL])
    models = lambda m: FakeModel(m, log)  # noqa: E731
    from omninode_live import run_maker
    record = run_maker.execute(fabric, gh, Screen(), models, "k_checker", run_id="r1", task_id="t", token=1)
    by = {i["key"]: i for i in record["items"]}
    forced = by["repo-a--fmt"]
    assert forced["maker_model"] == "deterministic_rule" and forced["maker_variant"] is None and forced["status"] == "awaiting_check"
    assert [t for t in forced["trace"] if t["outcome"] == "forced_function"] and [t for t in forced["trace"] if t["outcome"] == "accepted"]
    assert all("repo-a--fmt" not in a["item_keys"] for a in record["attempts"])
    assert record["counts"]["deterministic"]["forced_function"] == 1 and record["counts"]["reuse"]["labeled_awaiting_check"] == 0
    value = fabric.get(ITEMS_STORE, "repo-a--fmt")[0]
    assert "Rust" not in value["labels"]["summary"], "third-party words stay out of what goes public"
    assert value["check"]["verdict"] == "pending"
    assert record["prestep"]["forced_items"] == 1 and record["prestep"]["firings"]["code_tool_topics_label_by_code"] == 1


def test_checker_audits_a_forced_label_with_a_real_model_and_tuner_and_dataset_ignore_it(on, monkeypatch):
    fabric, log = FakeFabric("k_maker"), []
    from omninode_live import run_maker
    run_maker.execute(fabric, repo_github([FORCED]), Screen(), lambda m: FakeModel(m, log), "k_checker", run_id="r1", task_id="t", token=1)
    assert log == [], "no model made this label"
    monkeypatch.setattr("tests.test_behavior.github", lambda: repo_github([FORCED]))
    res = check(fabric.db, "r1", log)
    assert res.output["verdicts"]["repo-a--fmt"]["verdict"] == "approve" and res.output["verdicts"]["repo-a--fmt"]["audit_model"] == "muse-spark-1.3" and log == ["muse-spark-1.3"]
    run_record = fabric.get(RECORD_STORE, core.RUN_PREFIX + "r1")[0]
    assert run_tuner.outcomes_from_runs([{**run_record, "check": {"verdicts": {"repo-a--fmt": {"verdict": "approve"}}}}], specmod.seed_spec()["parameters"]["model"]["rewards"]) == []
    item = fabric.get(ITEMS_STORE, "repo-a--fmt")[0]
    item["check"]["verdict"] = "approve"
    spec = specmod.seed_spec()
    spec["parameters"]["settings"]["retrain_min_examples"] = 1
    assert run_tuner.retrain_trigger(fabric, [run_record], {"repo-a--fmt": item}, spec)["state"] == "not_enough_examples"


def test_a_checked_model_label_is_not_replaced_by_a_template(on):
    fabric, log = FakeFabric("k_maker"), []
    from omninode_live import run_maker
    run_maker.execute(fabric, repo_github([FORCED]), Screen(), lambda m: FakeModel(m, log), "k_checker", run_id="r1", task_id="t", token=1)
    value, version = fabric.get(ITEMS_STORE, "repo-a--fmt")
    fabric.put(ITEMS_STORE, "repo-a--fmt", {**value, "labels": {"summary": "x"}, "check": {"verdict": "approve"}}, expected=version, tags=[])
    changed = {**FORCED, "description": "A fast formatter for Ruby code, now also for Crystal.", "pushed_at": "2026-11-02T00:00:00Z"}
    record = run_maker.execute(fabric, repo_github([changed]), Screen(), lambda m: FakeModel(m, log), "k_checker", run_id="r2", task_id="t", token=1)
    assert record["items"][0].get("maker_model") != "deterministic_rule" and log


def test_a_label_the_rule_would_refuse_goes_to_the_model_instead(on):
    fabric, log = FakeFabric("k_maker"), []
    named = repo("next.ai/fmt", "A fast formatter for Ruby code, written in plain Rust.", ["code-formatter"])
    from omninode_live import run_maker
    record = run_maker.execute(fabric, repo_github([named]), Screen(), lambda m: FakeModel(m, log), "k_checker", run_id="r1", task_id="t", token=1)
    assert log and record["items"][0]["maker_model"] != "deterministic_rule"
    assert any(r["kind"] == "refused" and "summary_has_link_or_address" in r["why"] for r in traces())


def test_a_forced_path_refuses_text_that_looks_personal(on):
    fabric, log = FakeFabric("k_maker"), []
    who = repo("a/fmt", "A fast formatter for Ruby, write to someone@example.org for help", ["code-formatter"])
    from omninode_live import run_maker
    record = run_maker.execute(fabric, repo_github([who]), Screen(), lambda m: FakeModel(m, log), "k_checker", run_id="r1", task_id="t", token=1)
    assert record["items"][0].get("maker_model") != "deterministic_rule"
    assert any(r["kind"] == "refused" and r["why"] == "looks_personal" for r in traces())


def test_a_spent_ceiling_still_stops_model_calls(on):
    class Spent(FakeModel):
        def chat_json(self, *a, **k):
            raise BudgetExhausted("ceiling")

    fabric = FakeFabric("k_maker")
    from omninode_live import run_maker
    record = run_maker.execute(fabric, repo_github([TO_MODEL]), Screen(), lambda m: Spent(m, []), "k_checker", run_id="r1", task_id="t", token=1)
    assert record["attempts"][0]["outcome"] == "refused_by_ceiling" and record["items"][0]["status"] == "label_failed" and record["attempts"][0]["input_tokens"] == 0


def test_forced_tool_respects_the_allowance_and_refreshes_the_digest(on):
    pre = prestep.PreStep("r", spec=specmod.seed_spec())
    item = {"key": "k", "full_name": "a/b", "description": "notes for a small research team here", "topics": [], "status": "needs_label", "latest_release": None,
            "trace": [{"outcome": "unchanged_since_last_push"}], "content_digest": "old"}
    gh = repo_github([])
    gh.core_remaining = 1
    pre.before_batch([item], settings=specmod.seed_spec()["parameters"]["settings"], screen=Screen(), github=gh, validate=feed.validate_label, trace=feed.trace, digest=feed.content_digest)
    assert gh.calls == 0 and any(r["kind"] == "refused" and r["why"] == "github_allowance" for r in traces())
    gh.core_remaining = 100
    pre.before_batch([item], settings=specmod.seed_spec()["parameters"]["settings"], screen=Screen(), github=gh, validate=feed.validate_label, trace=feed.trace, digest=feed.content_digest)
    assert gh.calls == 1 and item["latest_release"]["tag"] == "v2" and item["content_digest"] != "old"


def test_cut_categories_reach_the_model_and_a_wanted_cut_is_recorded_then_pinned(on):
    seen = []

    class Wants(FakeModel):
        def chat_json(self, system, user, *, meter, **kw):
            data = json.loads(user)
            seen.append(data["categories"])
            meter.add({"id": self.mid}, ModelCall(input_tokens=100, output_tokens=50, seconds=0.1, cost_usd=0.001))
            return {"labels": [{"key": r["key"], "category": "model_tooling", "determinism": "mixed", "use_cases": [], "summary": "It helps a team keep notes on research work.",
                                "evidence": [r["description"][:20]], "confidence_milli": 800} for r in data["repositories"]]}

    linty = repo("d/skills-and-agents", "An agent framework harness with orchestration and workflow runtime sdk", ["agent-framework"])
    from omninode_live import run_maker
    for n in (1, 2, 3):
        fabric = FakeFabric("k_maker")
        run_maker.execute(fabric, repo_github([linty]), Screen(), lambda m: Wants(m, []), "k_checker", run_id=f"r{n}", task_id="t", token=1)
    assert "model_tooling" not in seen[0] and "other" in seen[0]
    calls = [r for r in traces() if r["kind"] == "call"]
    assert calls[0]["asked_for_anyway"] == ["category:model_tooling"] and "kept" in calls[0] and calls[0]["tokens_after_est"] <= calls[0]["tokens_before_est"]
    assert "model_tooling" in seen[2], "cut then wanted twice: it stays from then on"


def test_a_skill_loads_when_the_text_matches(on):
    systems = []

    class Sees(FakeModel):
        def chat_json(self, system, user, *, meter, **kw):
            systems.append(system)
            return super().chat_json(system, user, meter=meter, **kw)

    tool = repo("e/grype", "A scanner for security problems in container images", ["static-analysis"])
    from omninode_live import run_maker
    record = run_maker.execute(FakeFabric("k_maker"), repo_github([tool]), Screen(), lambda m: Sees(m, []), "k_checker", run_id="r1", task_id="t", token=1)
    assert "linter, formatter" in systems[0] and systems[0].startswith(specmod.LABEL_SYSTEM) and record["prestep"]["firings"]["code_tool_hint"] == 1


def test_step_back_between_turns_when_calls_make_no_progress_or_tokens_grow(on):
    pre = prestep.PreStep("r", spec=specmod.seed_spec())
    group = [{"key": "k", "full_name": "x/y", "description": "notes for a small research team here", "topics": []}]
    cats = specmod.seed_spec()["parameters"]["settings"]["categories"]
    assert pre.before_call(group, cats, "")["step_back"] is None
    for _ in range(2):
        pre.after_call(pre.before_call(group, cats, ""), group, {}, tokens=100, variant="v", outcome="unparsed")
    plan = pre.before_call(group, cats, "")
    assert plan["step_back"] and {"rule": "no_progress", "do": "step_back"} in plan["firings"]
    pre = prestep.PreStep("r2", spec=specmod.seed_spec())
    for t in (10, 20, 30):
        pre.after_call(pre.before_call(group, cats, ""), group, {"k": {"category": "other"}}, tokens=t, variant="v", outcome="answered")
    assert "tokens_growing" in [f["rule"] for f in pre.before_call(group, cats, "")["firings"]]


def test_same_item_failing_in_an_earlier_run_steps_back_and_the_note_reaches_the_model(on):
    prestep.append({"kind": "finish", "run_id": "old", "failed_keys": ["repo-b--thing"]})
    seen = []

    class Sees(FakeModel):
        def chat_json(self, system, user, *, meter, **kw):
            seen.append(json.loads(user))
            return super().chat_json(system, user, meter=meter, **kw)

    from omninode_live import run_maker
    record = run_maker.execute(FakeFabric("k_maker"), repo_github([TO_MODEL]), Screen(), lambda m: Sees(m, []), "k_checker", run_id="r1", task_id="t", token=1)
    assert seen[0]["step_back"] and record["prestep"]["firings"]["same_call_twice"] == 1


def test_a_forced_rule_the_audit_keeps_refusing_turns_itself_off(on):
    for n in range(3):
        prestep.append({"kind": "forced", "run_id": f"o{n}", "key": "k", "rule": "code_tool_topics_label_by_code", "do": "force_function"})
        prestep.record_check(f"o{n}", {"k": {"verdict": "reject"}})
    fabric, log = FakeFabric("k_maker"), []
    from omninode_live import run_maker
    record = run_maker.execute(fabric, repo_github([FORCED]), Screen(), lambda m: FakeModel(m, log), "k_checker", run_id="r1", task_id="t", token=1)
    assert log and record["items"][0]["maker_model"] != "deterministic_rule" and record["prestep"]["rules_off"] == ["code_tool_topics_label_by_code"]


def test_approved_labels_teach_the_scorer_words(on):
    prestep.append({"kind": "call", "run_id": "o", "answered": {"k": "model_tooling"}, "top_terms": ["quantize"]})
    prestep.record_check("o", {"k": {"verdict": "approve"}})
    pre = prestep.PreStep("r", spec=specmod.seed_spec())
    assert pre.memory["terms"]["model_tooling"] == ["quantize"]


@pytest.mark.parametrize("content", ["{not json", '{"enabled": true}', '{"enabled": true, "learning": {"traces_read": 1, "pin_after_misses": 1, "rule_off_after_rejects": 1, "rule_off_reject_share": 1, "learned_terms_per_resource": 1}, "rules": [{"do": "force_tool"}, {"id": "x", "do": "step_back", "when": {"unknown_condition": 1}}]}'])
def test_a_broken_table_behaves_exactly_as_today(tmp_path, monkeypatch, content):
    bad = tmp_path / "rules.json"
    bad.write_text(content)
    monkeypatch.setenv("OMNINODE_PRESTEP_RULES", str(bad))
    log, sent = [], []

    class Sees(FakeModel):
        def chat_json(self, system, user, *, meter, **kw):
            sent.append((system, json.loads(user)))
            return super().chat_json(system, user, meter=meter, **kw)

    from omninode_live import run_maker
    record = run_maker.execute(FakeFabric("k_maker"), repo_github([FORCED]), Screen(), lambda m: Sees(m, log), "k_checker", run_id="r1", task_id="t", token=1)
    assert record["ok"] and record["items"][0]["status"] == "awaiting_check" and record["items"][0]["maker_model"] != "deterministic_rule"
    assert sent[0][0] == specmod.LABEL_SYSTEM and sent[0][1]["categories"] == specmod.seed_spec()["parameters"]["settings"]["categories"] and "step_back" not in sent[0][1]


def test_an_unwritable_trace_does_not_stop_the_run(on, tmp_path, monkeypatch):
    monkeypatch.setenv("OMNINODE_PRESTEP_TRACES", str(tmp_path))  # a directory: every write fails
    from omninode_live import run_maker
    record = run_maker.execute(FakeFabric("k_maker"), repo_github([TO_MODEL]), Screen(), lambda m: FakeModel(m, []), "k_checker", run_id="r1", task_id="t", token=1)
    assert record["ok"]


def test_every_run_leaves_a_closing_line_even_with_no_model_work(on):
    from omninode_live import run_maker
    run_maker.execute(FakeFabric("k_maker"), repo_github([]), Screen(), lambda m: FakeModel(m, []), "k_checker", run_id="r1", task_id="t", token=1)
    rows = traces()
    assert rows[-1]["kind"] == "finish" and rows[-1]["enabled"] is True and prestep.report(rows)["runs"] == 1


def test_table_text_passes_the_shared_word_list():
    table, screen = json.loads(TABLE.read_text()), Screen()
    words = [*table["skills"].values(), table["step_back_text"], *[r.get("phrase", "") for r in table["rules"]], *[r["id"] for r in table["rules"]]]
    assert not [w for w in words if screen.visible_hit(w)]


def test_each_item_keeps_its_own_category_in_a_mixed_group(on):
    pre = prestep.PreStep("r", spec=specmod.seed_spec())
    cats = specmod.seed_spec()["parameters"]["settings"]["categories"]
    lint = {"key": "a", "full_name": "x/lint", "description": "linter formatter parser for code", "topics": ["linter"]}
    quant = {"key": "b", "full_name": "x/quant", "description": "model inference and training on gpu", "topics": ["llm"]}
    plan = pre.before_call([lint, lint, lint, quant], cats, "")
    assert "model_tooling" in plan["categories"] and "deterministic_tool" in plan["categories"]
    unsure = {"key": "c", "full_name": "x/zz", "description": "zzz qqq", "topics": []}
    assert pre.before_call([lint, unsure], cats, "")["categories"] == cats


def test_a_refused_template_gets_a_models_try_next_run(on):
    fabric, log = FakeFabric("k_maker"), []
    from omninode_live import run_maker
    run_maker.execute(fabric, repo_github([FORCED]), Screen(), lambda m: FakeModel(m, log), "k_checker", run_id="r1", task_id="t", token=1)
    value, version = fabric.get(ITEMS_STORE, "repo-a--fmt")
    fabric.put(ITEMS_STORE, "repo-a--fmt", {**value, "check": {"verdict": "reject"}}, expected=version, tags=[])
    record = run_maker.execute(fabric, repo_github([FORCED]), Screen(), lambda m: FakeModel(m, log), "k_checker", run_id="r2", task_id="t", token=1)
    assert log and record["items"][0]["maker_model"] != "deterministic_rule" and record["items"][0]["status"] == "awaiting_check"


def test_a_skill_that_is_not_text_changes_nothing(tmp_path, monkeypatch):
    table = json.loads(TABLE.read_text())
    table["skills"]["label_thin_description"] = 1
    bad = tmp_path / "rules.json"
    bad.write_text(json.dumps(table))
    monkeypatch.setenv("OMNINODE_PRESTEP_RULES", str(bad))
    from omninode_live import run_maker
    thin = repo("z/n", "short text", [])
    record = run_maker.execute(FakeFabric("k_maker"), repo_github([thin]), Screen(), lambda m: FakeModel(m, []), "k_checker", run_id="r1", task_id="t", token=1)
    assert record["ok"] and record["prestep"]["errors"] >= 1


def test_template_verdicts_do_not_move_the_grid(on):
    from omninode_live import grid as gridmod
    spec = specmod.seed_spec()
    g = gridmod.node_grid()
    ledger, costs = gridmod.load_ledger(g, None)
    run_record = {"run_id": "r", "spec_version": 1, "attempts": [], "ok": True, "seconds": 1, "counts": {"reuse": {"answered_no_model": 0}},
                  "items": [{"key": "k", "maker_model": "deterministic_rule", "maker_variant": None}], "check": {"verdicts": {"k": {"verdict": "approve"}}, "attempts": []}}
    result = run_tuner.walk_grid(ledger, costs, g, spec, run_record, None, [])
    assert result["approve_rate"] is None and result["stage"] != "promoted"


def test_a_check_in_a_later_run_still_reaches_the_rule_that_made_the_label(on):
    for n in range(3):
        prestep.append({"kind": "forced", "run_id": f"o{n}", "key": f"k{n}", "rule": "r1", "do": "force_function"})
        prestep.record_check(f"later{n}", {f"k{n}": {"verdict": "reject"}})
    assert prestep.PreStep("r", spec=specmod.seed_spec()).memory["rules_off"] == ["r1"]
