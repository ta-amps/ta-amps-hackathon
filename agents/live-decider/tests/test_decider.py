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


def test_publish_refuses_without_its_own_record_key(monkeypatch, capsys):
    monkeypatch.delenv("DECIDER_RECORD_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "omninode_live.shim", None)  # importing it would fail: it must not get that far
    assert d.publish() == 2
    assert "DECIDER_RECORD_KEY" in capsys.readouterr().err
