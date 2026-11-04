"""The compiler and ops: a spec drives everything, a spec that breaks a rule never runs, and the sidecar stays inside."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from omninode_live import grid as gridmod
from omninode_live import shapes


class FakeFabric:
    key_id = "k_maker"
    label = "t"

    def __init__(self, records: dict[str, dict[str, Any]] | None = None) -> None:
        self.records = records or {}
        self.puts: list[tuple[str, str]] = []

    def list(self, store: str, prefix: str = "", limit: int = 200) -> list[tuple[str, Any, int]]:
        return [(k, v, 1) for k, v in self.records.get(store, {}).items() if k.startswith(prefix)]

    def get(self, store: str, key: str) -> tuple[Any, int] | None:
        v = self.records.get(store, {}).get(key)
        return (v, 1) if v is not None else None

    def put(self, store: str, key: str, value: Any, *, expected: int | None, tags: list[str]) -> int:
        self.records.setdefault(store, {})[key] = value
        self.puts.append((store, key))
        return 2


class FakeScreen:
    def blocked(self, text: str) -> bool:
        return "forbidden" in text

    def visible_hit(self, text: str) -> bool:
        return "forbidden" in text or "banned" in text


class FakeMeter:
    pass


class FakeModel:
    def __init__(self, answer: Any) -> None:
        self.answer, self.calls = answer, 0

    def chat_json(self, system: str, user: str, *, meter: Any, **_: Any) -> Any:
        import json

        self.calls += 1
        rows = json.loads(user)["rows"]
        return self.answer(rows)


def base_spec(**more: Any) -> dict[str, Any]:
    spec = {
        "schema": shapes.SCHEMA, "id": "test-shape", "goal": "g", "reward": {"cost_scale_usd": 1, "time_scale_minutes": 60, "max_penalty": 0.5},
        "invariants": sorted(shapes.REQUIRED_INVARIANTS), "budget_usd_per_day": 1.0, "memory": {"store": "omninode.shape_items"},
        "parameters": {"model": {"tuner_version": 0, "variants": [{"id": "s", "step": "make", "status": "active", "model": "muse-spark-1.3", "fine_tune": None}], "mix": {"make": {"s": 1.0}}}},
        "composition": "read >> split >> ask >> store @ check",
        "steps": [
            {"id": "read", "op": "rows_from_records", "mode": "code", "args": {"store": "eranos.catalog", "fields": {"name": "$0.name", "n": "$0.n"}, "key_fields": ["name"]}},
            {"id": "split", "op": "classify", "mode": "code", "args": {"rules": [{"when": [{"field": "n", "op": "gte", "value": 5}], "set": {"status": "plain_done", "finding": "big"}},
                                                                                {"set": {"status": "needs_model"}}]}},
            {"id": "ask", "op": "model", "mode": "model", "args": {"only_status": ["needs_model"], "input_fields": ["name"], "out_fields": ["say"], "system": "s", "group_size": 2, "next_status": "plain_done"}},
            {"id": "store", "op": "store_items", "mode": "code", "args": {"only_status": ["plain_done"]}},
        ],
        "check": {"composition": "load >> verdict", "steps": [
            {"id": "load", "op": "load_run_rows", "mode": "code", "args": {}},
            {"id": "verdict", "op": "store_verdicts", "mode": "code", "args": {}},
        ]},
    }
    spec.update(more)
    return spec


def make_ctx(spec: dict[str, Any], fabric: Any, model: Any = None) -> shapes.ShapeContext:
    return shapes.ShapeContext(run_id="r1", spec=spec, spec_version=1, fabric=fabric, screen=FakeScreen(), models=lambda _m: model, now=1.8e9)


def run(spec: dict[str, Any], fabric: Any, model: Any = None) -> tuple[Any, shapes.ShapeContext]:
    grid = gridmod.node_grid()
    ctx = make_ctx(spec, fabric, model)
    node, _ = shapes.compile_shape(ctx, grid, dict(grid.default_verified_cell), maker_key_id="k_maker", checker_key_id="k_checker")
    return node.execute({"run_id": "r1"}), ctx


def test_a_spec_decides_plain_code_versus_model_and_nothing_else_does() -> None:
    fabric = FakeFabric({"eranos.catalog": {"a": {"name": "a", "n": 9}, "b": {"name": "b", "n": 1}}})
    model = FakeModel(lambda rows: {"answers": [{"key": r["key"], "say": "x"} for r in rows]})
    result, ctx = run(base_spec(), fabric, model)
    assert result.ok
    assert model.calls == 1 and ctx.attempts[0]["item_keys"] == ["b"]  # only the row plain code left open
    assert sorted(k for _s, k in fabric.puts) == ["test-shape.a", "test-shape.b"]


def test_two_specs_make_two_different_graphs_from_the_same_code() -> None:
    fabric = FakeFabric({"eranos.catalog": {"a": {"name": "a", "n": 9}}})
    grid = gridmod.node_grid()
    one, _ = shapes.compile_shape(make_ctx(base_spec(), fabric), grid, dict(grid.default_verified_cell), maker_key_id="m", checker_key_id="c")
    other = base_spec(composition="read >> split >> store @ check")
    other["steps"] = [s for s in other["steps"] if s["id"] != "ask"]
    two, _ = shapes.compile_shape(make_ctx(other, fabric), grid, dict(grid.default_verified_cell), maker_key_id="m", checker_key_id="c")
    assert one.algebraic_tree() != two.algebraic_tree()


@pytest.mark.parametrize(("change", "why"), [
    (lambda s: s.update(invariants=["only_this"]), "invariants missing"),
    (lambda s: s["steps"].append({"id": "x", "op": "shell", "mode": "code"}), "unknown op"),
    (lambda s: s["parameters"]["model"]["variants"][0].update(model="other-model"), "not allowed"),
    (lambda s: s.update(budget_usd_per_day=900), "budget"),
    (lambda s: s["memory"].update(store="eranos.instructions"), "memory store"),
    (lambda s: s.update(composition="read >> split >> ask >> store"), "must end @ check"),
    (lambda s: s.pop("check"), "independent check"),
    (lambda s: s["steps"][2].update(mode="code"), "says mode"),
    (lambda s: s["steps"][0].update(op="rows_from_http", args={"urls": ["https://example.com/x"]}), "not one of ours"),
    (lambda s: s.update(goal=""), "goal"),
    (lambda s: s["steps"][0]["args"].update(store="eranos.private_things"), "not one a shape may read"),
    (lambda s: s.update(sidecar={"inside": "read", "features": ["n"], "target_field": "x", "target_value": 1, "answer_when_skipped": {"x": 1}}), "inside one of this shape's model"),
])
def test_a_spec_that_breaks_a_rule_is_refused_before_it_runs(change: Any, why: str) -> None:
    spec = copy.deepcopy(base_spec())
    change(spec)
    grid = gridmod.node_grid()
    with pytest.raises(shapes.ShapeError, match=why):
        shapes.compile_shape(make_ctx(spec, FakeFabric()), grid, dict(grid.default_verified_cell), maker_key_id="m", checker_key_id="c")


def test_the_combinators_compile_and_a_waterfall_falls_through() -> None:
    assert shapes.parse("a >> (b // c) >> d @ check") == ("@", (">>", (">>", "a", ("//", "b", "c")), "d"), "check")
    with pytest.raises(shapes.ShapeError):
        shapes.parse("a >> (b")
    with pytest.raises(shapes.ShapeError):
        shapes.parse("a >> ; rm")

    class Http:
        def get(self, _url: str) -> Any:
            raise shapes.httpx.ConnectError("down")

    spec = base_spec(composition="(live // memory) >> split >> store @ check")
    spec["steps"] = [{"id": "live", "op": "rows_from_http", "mode": "code", "args": {"urls": ["https://shim.teleionlabs.com/q/repos"], "key_field": "repo"}},
                     {"id": "memory", "op": "rows_from_records", "mode": "code", "args": {"store": "eranos.catalog", "fields": {"name": "$0.name", "n": "$0.n"}, "key_fields": ["name"]}},
                     {"id": "split", "op": "classify", "mode": "code", "args": {"rules": [{"set": {"status": "plain_done"}}]}},
                     {"id": "store", "op": "store_items", "mode": "code", "args": {"only_status": ["plain_done"]}}]
    fabric = FakeFabric({"eranos.catalog": {"a": {"name": "a", "n": 1}}})
    grid = gridmod.node_grid()
    ctx = make_ctx(spec, fabric)
    ctx.http = Http()
    node, _ = shapes.compile_shape(ctx, grid, dict(grid.default_verified_cell), maker_key_id="m", checker_key_id="c")
    result = node.execute({"run_id": "r1"})
    assert result.ok and result.output["rows"][0]["key"] == "a"


def test_the_nesting_limit_holds_for_a_long_shape() -> None:
    grid = gridmod.node_grid()
    spec = base_spec(composition=" >> ".join(f"s{i}" for i in range(40)) + " @ check")
    spec["steps"] = [{"id": f"s{i}", "op": "sort", "mode": "code", "args": {"by": "n", "keep": 9}} for i in range(40)]
    node, _ = shapes.compile_shape(make_ctx(spec, FakeFabric()), grid, dict(grid.default_verified_cell), maker_key_id="m", checker_key_id="c")
    assert node.execute({"rows": []}).ok


def sidecar_spec(answer_for: dict[str, str] | None = None) -> dict[str, Any]:
    spec = base_spec(composition="read >> ask >> store @ check", sidecar={"inside": "ask", "features": ["close"], "target_field": "verdict", "target_value": "yes", "answer_when_skipped": {"verdict": "yes"},
                                                                         "min_samples": 4, "skip_above": 0.8, "audit_every": 3, "max_width": 0.5})
    spec["steps"] = [{"id": "read", "op": "rows_from_records", "mode": "code", "args": {"store": "eranos.catalog", "fields": {"name": "$0.name", "close": "$0.close"}, "key_fields": ["name"]}},
                     {"id": "ask", "op": "model", "mode": "model", "args": {"only_status": ["open"], "input_fields": ["name"], "out_fields": ["verdict"], "system": "s", "group_size": 1, "next_status": "plain_done"}},
                     {"id": "store", "op": "store_items", "mode": "code", "args": {"only_status": ["plain_done"]}}]
    return spec


def test_sidecar_sits_inside_the_step_and_spares_only_what_its_interval_earned_and_tests_its_skips() -> None:
    records = {f"r{i:02}": {"name": f"r{i:02}", "close": 1.0} for i in range(20)}
    model = FakeModel(lambda rows: {"answers": [{"key": r["key"], "verdict": "yes"} for r in rows]})
    grid = gridmod.node_grid()
    spec = sidecar_spec()
    ctx = make_ctx(spec, FakeFabric({"eranos.catalog": records}), model)
    node, nodes = shapes.compile_shape(ctx, grid, dict(grid.default_verified_cell), maker_key_id="m", checker_key_id="c")
    assert "sidecar" not in shapes.leaves_or_empty(spec)
    assert isinstance(nodes["ask"].sidecar, shapes.RowSidecar)  # part of the node, not a step of the graph
    result = node.execute({"run_id": "r1"})
    side = nodes["ask"].sidecar
    assert result.ok and side.skips > 0
    assert model.calls < 20  # some calls spared
    assert side.audits and all(a["agreed"] for a in side.audits)  # every Nth skip still goes to a model
    assert all(r["status"] == "awaiting_check" for r in result.output["rows"])  # spared rows still wait for the independent check


def test_sidecar_tells_different_content_apart_where_the_stock_features_cannot() -> None:
    grid = gridmod.node_grid()
    cell = dict(grid.default_verified_cell)
    side = shapes.RowSidecar({"features": ["close"], "min_samples": 4}, grid, cell, None)
    for _ in range(20):
        side.observe_rank1({"close": 1.0}, 1.0)
        side.observe_rank1({"close": 0.0}, 0.0)
    assert side.predict_score({"close": 1.0})["predicted_score"] > 0.9
    assert side.predict_score({"close": 0.0})["predicted_score"] < 0.1
    stock = shapes.SidecarOmniNode(grid=grid, cell=cell)
    same = stock._featurize({"records": [{"x": "good"}]})[0] == stock._featurize({"records": [{"x": "completely different"}]})[0]
    assert same.all()


def test_sidecar_state_survives_a_restart() -> None:
    grid = gridmod.node_grid()
    cell = dict(grid.default_verified_cell)
    one = shapes.RowSidecar({"features": ["close"], "min_samples": 2}, grid, cell, None)
    for _ in range(5):
        one.observe_rank1({"close": 1.0}, 1.0)
    two = shapes.RowSidecar({"features": ["close"], "min_samples": 2}, grid, cell, one.state())
    assert two.predict_score({"close": 1.0})["calibration_samples"] == one.predict_score({"close": 1.0})["calibration_samples"]


def test_memory_reuses_an_approved_answer_and_not_a_pending_one() -> None:
    spec = base_spec(composition="read >> remember >> split >> ask >> store @ check")
    spec["steps"].insert(1, {"id": "remember", "op": "memory_reuse", "mode": "reuse", "args": {"digest_fields": ["name", "n"]}})
    from omninode_live.core import digest

    d = digest({"name": "b", "n": 1, "rules_version": None})
    d2 = digest({"name": "c", "n": 1, "rules_version": None})
    fabric = FakeFabric({"eranos.catalog": {"b": {"name": "b", "n": 1}, "c": {"name": "c", "n": 1}},
                         "omninode.shape_items": {"test-shape.b": {"input_digest": d, "answer": {"say": "old"}, "check": {"verdict": "approve"}},
                                                  "test-shape.c": {"input_digest": d2, "answer": {"say": "old"}, "check": {"verdict": "pending"}}}})
    model = FakeModel(lambda rows: {"answers": [{"key": r["key"], "say": "new"} for r in rows]})
    result, ctx = run(spec, fabric, model)
    by = {r["key"]: r for r in result.output["rows"]}
    assert by["b"]["status"] == "reused" and by["b"]["answer"] == {"say": "old"}
    assert ctx.attempts[0]["item_keys"] == ["c"]


def test_rule_table_stops_a_made_up_quote_and_a_link() -> None:
    step_conf = {"id": "rule", "op": "rule_validate", "mode": "hybrid", "args": {"only_status": ["proposed"], "rules": [
        {"field": "verdict", "enum": ["yes", "no"]},
        {"field": "evidence", "min_len": 5, "quoted_from": ["source"]},
        {"field": "summary", "max_len": 50, "no_links": True, "word_list": True}]}}
    grid = gridmod.node_grid()
    node = shapes.RuleValidate(make_ctx(base_spec(), FakeFabric()), step_conf, grid, dict(grid.default_verified_cell))
    rows = [{"key": "good", "status": "proposed", "source": "The Sky is blue today, it said.", "_proposed": {"verdict": "yes", "evidence": "sky is blue today", "summary": "fine"}},
            {"key": "invented", "status": "proposed", "source": "The sky is blue", "_proposed": {"verdict": "yes", "evidence": "the sea is green and deep", "summary": "fine"}},
            {"key": "link", "status": "proposed", "source": "The sky is blue", "_proposed": {"verdict": "yes", "evidence": "the sky is blue", "summary": "see example.com"}},
            {"key": "word", "status": "proposed", "source": "The sky is blue", "_proposed": {"verdict": "maybe", "evidence": "the sky is blue", "summary": "banned word"}}]
    out = node.execute({"rows": rows}).output["rows"]
    assert [r["status"] for r in out] == ["rule_accepted", "rule_rejected", "rule_rejected", "rule_rejected"]
    assert out[1]["rule_failures"] == ["evidence_not_in_source"]
    assert "summary_has_link_or_address" in out[2]["rule_failures"]
    assert set(out[3]["rule_failures"]) == {"verdict_not_allowed", "summary_word_list"}


def test_compare_text_exact_coverage_numbers_and_window() -> None:
    found = shapes.compare_text("Filing is due in 15 days", "intro words. FILING is due in   15 days! other text")
    assert found["exact"] and found["same_numbers"] and "filing is due" in found["window"]
    moved = shapes.compare_text("Filing is due in 15 days", "filing is due in 30 days")
    assert not moved["exact"] and not moved["same_numbers"]


def test_a_checker_records_its_own_model_and_leaves_the_makers_alone() -> None:
    spec = base_spec()
    spec["check"] = {"composition": "load >> audit >> rule >> verdict", "steps": [
        {"id": "load", "op": "load_run_rows", "mode": "code", "args": {}},
        {"id": "audit", "op": "model", "mode": "model", "args": {"only_status": ["open"], "other_than_field": "maker_model", "input_fields": ["name"], "out_fields": ["verdict", "reason"], "system": "s"}},
        {"id": "rule", "op": "rule_validate", "mode": "hybrid", "args": {"only_status": ["proposed"], "answer_field": "audit", "rules": [{"field": "verdict", "enum": ["approve", "reject"]}]}},
        {"id": "verdict", "op": "store_verdicts", "mode": "code", "args": {}}]}
    store = "omninode.shape_items"
    fabric = FakeFabric({store: {"test-shape.a": {"key": "a", "name": "a", "maker_model": "muse-spark-1.3", "answer": {"say": "made"}}}})
    seen = []

    def models(m: str) -> Any:
        seen.append(m)
        return FakeModel(lambda rows: {"answers": [{"key": r["key"], "verdict": "reject", "reason": "no"} for r in rows]})

    grid = gridmod.node_grid()
    ctx = make_ctx(spec, fabric)
    ctx.models = models
    node = shapes.compile_check(ctx, grid, dict(grid.default_verified_cell))
    out = node.execute({"maker_worker_key": "k_maker", "maker_output": {"items": [{"key": "a", "status": "awaiting_check"}]}})
    row = out.output["rows"][0]
    assert seen == ["muse-wonder-1.0"] and row["verdict"] == "reject" and row["maker_model"] == "muse-spark-1.3"
    assert fabric.records[store]["test-shape.a"]["check"]["checker_key_id"] == "k_maker" and fabric.records[store]["test-shape.a"]["answer"] == {"say": "made"}
    assert fabric.records[store]["test-shape.a"]["status"] == "rejected"


def test_sidecar_takes_any_number_of_features() -> None:
    grid = gridmod.node_grid()
    cell = dict(grid.default_verified_cell)
    for n in (1, 3, 4, 5, 17):
        side = shapes.RowSidecar({"features": [f"f{i}" for i in range(n)], "min_samples": 2}, grid, cell, None)
        side.observe_rank1({"f0": 1.0}, 1.0)
        assert side.predict_score({"f0": 1.0})["predicted_score"] >= 0.0


def test_two_citations_in_one_place_stay_two_rows() -> None:
    grid = gridmod.node_grid()
    conf = {"id": "r", "op": "rows_from_records", "mode": "code", "args": {"store": "eranos.catalog", "explode": ["c"], "fields": {"a": "$key", "q": "$1.q"}, "key_fields": ["a"]}}
    node = shapes.RowsFromRecords(make_ctx(base_spec(), FakeFabric({"eranos.catalog": {"k": {"c": [{"q": 1}, {"q": 2}]}}})), conf, grid, dict(grid.default_verified_cell))
    rows = node.execute({}).output["rows"]
    assert [r["key"] for r in rows] == ["k", "k--2"] and [r["q"] for r in rows] == [1, 2]


def test_dry_read_finds_what_validate_cannot_and_writes_nothing() -> None:
    grid = gridmod.node_grid()
    fabric = FakeFabric({"eranos.catalog": {"k": {"kit": {"big": "object" * 50}, "ok": 1}}})
    spec = base_spec()
    spec["steps"][0]["args"].update(fields={"kit": "$0.kit", "nothing": "$0.nope", "name": "$key"}, key_fields=["kit"])
    errors = shapes.dry_read(spec, fabric, FakeScreen(), grid, dict(grid.default_verified_cell))
    assert any("not a short name" in e for e in errors) and any("nothing" in e for e in errors)
    assert fabric.puts == []


def test_a_shape_with_no_memory_step_can_run_twice() -> None:
    versions: dict[str, int] = {}

    class Strict(FakeFabric):
        def get(self, store: str, key: str) -> Any:
            return (self.records[store][key], versions[key]) if key in versions else super().get(store, key)

        def put(self, store: str, key: str, value: Any, *, expected: int | None, tags: list[str]) -> int:
            assert expected == versions.get(key), "version conflict"
            versions[key] = (expected or 0) + 1
            self.records.setdefault(store, {})[key] = value
            return versions[key]

    spec = base_spec(composition="read >> split >> store @ check")
    spec["steps"] = [s for s in spec["steps"] if s["id"] != "ask"]
    fabric = Strict({"eranos.catalog": {"a": {"name": "a", "n": 9}}})
    spec["steps"][0]["args"]["store"] = "eranos.catalog"
    assert run(spec, fabric)[0].ok and run(spec, fabric)[0].ok
    assert versions["test-shape.a"] == 2


def test_publish_sends_small_batches_and_catches_up_on_approved_rows_left_out() -> None:
    sent: list[int] = []

    class Shim:
        def publish(self, objects: dict[str, Any], summary: str, key: str) -> dict[str, Any]:
            sent.append(len(objects))
            return {"status": 200, "ok": True, "readable": sorted(objects), "redirected": []}

    grid = gridmod.node_grid()
    store = "omninode.shape_items"
    earlier = {f"test-shape.e{i}": {"key": f"e{i}", "answer": {"line": "x"}, "check": {"verdict": "approve"}} for i in range(14)}
    earlier["test-shape.done"] = {"key": "done", "answer": {"line": "x"}, "check": {"verdict": "approve"}, "public_object": "p"}
    earlier["test-shape.no"] = {"key": "no", "answer": {"line": "x"}, "check": {"verdict": "reject"}}
    fabric = FakeFabric({store: earlier})
    ctx = make_ctx(base_spec(), fabric)
    ctx.shim = Shim()
    conf = {"id": "p", "op": "publish_objects", "mode": "code", "args": {"prefix": "t_", "summary": "{line}", "batch": 10}}
    shapes.PublishObjects(ctx, conf, grid, dict(grid.default_verified_cell)).execute({"rows": []})
    assert sent == [10, 4] and len(ctx.published["readable"]) == 14
    assert fabric.records[store]["test-shape.e0"]["public_object"] == "t_e0"


def test_new_rules_make_new_answers() -> None:
    from omninode_live.core import digest

    spec = base_spec(composition="read >> remember >> split >> store @ check")
    spec["steps"] = [s for s in spec["steps"] if s["id"] != "ask"]
    spec["steps"].insert(1, {"id": "remember", "op": "memory_reuse", "mode": "reuse", "args": {"digest_fields": ["name"], "rules_version": 2}})
    old = digest({"name": "b", "rules_version": 1})
    fabric = FakeFabric({"eranos.catalog": {"b": {"name": "b", "n": 9}}, "omninode.shape_items": {"test-shape.b": {"input_digest": old, "check": {"verdict": "approve"}}}})
    spec["steps"][0]["args"]["store"] = "eranos.catalog"
    result, _ = run(spec, fabric)
    assert result.output["rows"][0]["status"] == "awaiting_check"
