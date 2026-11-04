import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decider as d

C = [{"id": "a", "title": "A", "summary": "x"}, {"id": "b", "title": "B", "summary": "y"}]

def test_parse():
    assert d.parse_answer('{"ranked": ["b","a"]}', C) == {"outcome": "route", "object_id": "b", "ranked": ["b", "a"]}
    assert d.parse_answer('{"ranked": []}', C)["outcome"] == "no_fit"
    assert d.parse_answer('{"ranked": ["zzz"]}', C)["outcome"] == "invalid"
    assert d.parse_answer('nonsense', C)["outcome"] == "invalid"
    assert d.parse_answer(None, C)["outcome"] == "invalid"
    assert d.parse_answer('{"ranked": "a"}', C)["outcome"] == "invalid"

def test_share_stable_and_small():
    ids = [f"t{i}" for i in range(4000)]
    share = sum(d.in_share(i) for i in ids) / 4000
    assert 0.12 < share < 0.18 and d.in_share("t7") == d.in_share("t7")

def test_rollback():
    good = [{"audit_pass": True}] * 12
    assert d.routes_stay_on(good)
    assert not d.routes_stay_on([{"audit_pass": True}] * 8 + [{"audit_pass": False}] * 4)
    assert d.routes_stay_on([{"audit_pass": False}] * 5)  # too few to judge
    assert d.routes_stay_on(good + [{"audit_pass": None}] * 20)  # a Spark outage is not the model's fault

def test_spend_counts_open_reservation():
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "s.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in [{"kind": "reserve", "id": "x", "usd": 1.0}, {"kind": "cost", "usd": 0.5}]))
        assert d.spent(p) == 1.5
        p.write_text("\n".join(json.dumps(r) for r in [{"kind": "reserve", "id": "x", "usd": 1.0}, {"kind": "settle", "id": "x", "usd": 0.2}]))
        assert d.spent(p) == 0.2

def test_candidates_only_objects():
    rs = [{"artifact_kind": "durable_task", "id": "t"}, {"artifact_kind": "task_object", "id": "o", "title": "T", "summary": "s  s"}]
    assert d.candidates_from_search(rs) == [{"id": "o", "title": "T", "summary": "s s"}]


def test_the_live_record_keeps_plain_code_apart_from_a_model(tmp_path, monkeypatch):
    log = tmp_path / "warm.jsonl"
    rows = [
        {"kind": "fabric_decision", "task_id": "a", "model": "muse-spark-1.3", "model_route": "plain_code_rule", "fallback": False, "attempts": [{"route": "plain_code_rule", "outcome": "answered", "cost_usd": 0}]},
        {"kind": "fabric_decision", "task_id": "b", "model": "muse-spark-1.3", "model_route": "plain_code_rule", "fallback": False, "attempts": [{"route": "plain_code_rule", "outcome": "answered", "cost_usd": 0}]},
        {"kind": "fabric_decision", "task_id": "c", "model": "muse-spark-1.3", "model_route": "meta_api_muse_spark", "fallback": False, "attempts": [{"route": "baseten_meta_open_model", "outcome": "bad_answer"}, {"route": "meta_api_muse_spark", "outcome": "answered", "cost_usd": 0.003}]},
        {"kind": "fabric_decision", "task_id": "d", "model": "muse-spark-1.3", "model_route": "rule_no_model", "fallback": True, "attempts": []},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setattr(d, "WARM_LOG", log)
    for name in ("DECISIONS", "RUNS", "SEARCHES"):
        monkeypatch.setattr(d, name, tmp_path / f"{name}.jsonl")
    live = d.tally()["live_route_list"]
    assert live["decisions"] == 4
    assert live["decided_by_plain_code_no_model"] == 3
    assert live["decided_by_a_meta_model"] == 1
    assert live["decided_by_route"] == {"plain_code_rule": 2, "meta_api_muse_spark": 1, "rule_no_model": 1}
    assert live["fell_back_after_every_route_failed"] == 1
    assert "decided_by_a_model" not in live and "models_chosen" not in live
    assert live["task_object_hint_reached_a_maker_by_route"] == {}
    assert live["routes_each_attempt_including_failures"]["baseten_meta_open_model"]["answered"] == 0


def test_a_pick_counts_as_fine_tuned_only_on_its_own_route_and_a_failed_read_is_kept_apart(tmp_path, monkeypatch):
    log = tmp_path / "warm.jsonl"
    rows = [
        {"kind": "fabric_decision_effect", "task_id": "a", "object_id": "x", "object_route": d.GLIMMER_ROUTE},
        {"kind": "fabric_decision_effect", "task_id": "b", "object_id": "y", "object_route": "baseten_meta_open_model"},
        {"kind": "fabric_decision_effect", "task_id": "c", "object_id": "z", "object_route": "baseten_meta_open_model"},
        {"kind": "fabric_decision_effect", "task_id": "e", "object_id": None, "object_route": None},
        {"kind": "fabric_tool_call", "task_id": "b", "ok": True, "chosen_by": "baseten_meta_open_model"},
        {"kind": "fabric_tool_call", "task_id": "c", "ok": False, "chosen_by": "baseten_meta_open_model"},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setattr(d, "WARM_LOG", log)
    for name in ("DECISIONS", "RUNS", "SEARCHES"):
        monkeypatch.setattr(d, name, tmp_path / f"{name}.jsonl")
    body = d.tally()
    assert body["fine_tuned_decider"]["fine_tuned_picks_given_to_a_live_maker"] == 1
    live = body["live_route_list"]
    assert live["task_object_hint_reached_a_maker_by_route"] == {d.GLIMMER_ROUTE: 1, "baseten_meta_open_model": 2}
    assert live["full_task_object_also_read_by_route"] == {"baseten_meta_open_model": 1}


def test_publish_refuses_without_its_own_record_key(monkeypatch, capsys):
    monkeypatch.delenv("DECIDER_RECORD_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "omninode_live.shim", None)  # importing it would fail: it must not get that far
    assert d.publish() == 2
    assert "DECIDER_RECORD_KEY" in capsys.readouterr().err
