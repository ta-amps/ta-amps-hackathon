import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def mods(tmp_path, monkeypatch):
    (tmp_path / "v").mkdir()
    (tmp_path / "v/v1.json").write_text((ROOT / "versions/v1.json").read_text())
    monkeypatch.setenv("SIZING_RECORDS", str(tmp_path / "r"))
    monkeypatch.setenv("SIZING_VERSIONS", str(tmp_path / "v"))
    import sizer, store, tuner
    importlib.reload(store)
    importlib.reload(tuner)
    return sizer, store, tuner


def rec(i, title, passed, needs=False, size="small", usd=0.005, tokens=900, kind="general_verb|cognitive"):
    return {"task_id": f"t{i}", "title": title, "kind": kind, "size": size, "audit_pass": passed, "audit_needs_people": needs, "usd": usd, "output_tokens": tokens, "finished_ok": passed, "arm": "sized",
            "decision": {"complexity_milli": 700, "prompt_chars": 300, "table_version": 1}}


def test_index_task_needs_no_model(mods):
    sizer, store, _ = mods
    d = sizer.size_task({"task_id": "verb_index_enrich_x", "category": "distributed_index_enrichment", "step_mode": "atomic_build_step"}, {}, store.table(1))
    assert d["size"] == "none" and d["handler"] == "client_index" and d["budget"]["usd"] == 0.0


def test_checks_never_go_to_the_maker(mods):
    sizer, store, _ = mods
    d = sizer.size_task({"task_id": "a", "category": "eval_and_rank", "step_mode": "atomic_verification_step"}, {}, store.table(1))
    assert d["handler"] == "not_for_a_maker"


def test_budget_scales_with_size_and_big_signal(mods):
    sizer, store, _ = mods
    t = store.table(1)
    small = sizer.size_task({"task_id": "a", "title": "Write a note", "category": "c", "step_mode": "atomic_cognitive_step", "complexity_milli": 500, "prompt": "x"}, {}, t)
    big = sizer.size_task({"task_id": "b", "title": "Write a note", "category": "c", "step_mode": "atomic_cognitive_step", "complexity_milli": 900, "prompt": "x"}, {}, t)
    assert small["model"] == sizer.SMALL and big["model"] == sizer.BIG
    assert big["budget"]["usd"] > small["budget"]["usd"]


def test_a_later_decision_changes_from_earlier_outcomes(mods):
    sizer, store, _ = mods
    t = store.table(1)
    task = {"task_id": "new", "title": "Handset trial of the menu tree", "category": "c", "step_mode": "atomic_cognitive_step", "complexity_milli": 500, "prompt": "x"}
    assert sizer.size_task(task, {"past": []}, t)["size"] == "small"
    past = [rec(1, "Handset trial of the menu tree again", False, True), rec(2, "Handset trial of menu tree", False, True)]
    d = sizer.size_task(task, {"past": past}, t)
    assert d["size"] == "none" and d["handler"] == "decline_needs_people"
    good = [rec(1, "Handset trial of the menu tree again", True), rec(2, "Handset trial of menu tree", True)]
    assert sizer.size_task(task, {"past": good}, t)["size"] == "small"


def test_tuner_adds_a_word_only_from_never_passing_tasks(mods):
    _, store, tuner = mods
    rows = [rec(i, f"Handset run number{i}", False, True) for i in range(3)] + [rec(i + 3, f"Write note about thing{i}", True) for i in range(8)]
    new, changes = tuner.propose(rows, store.table(1))
    assert "handset" in new["needs_people_terms"]
    assert "write" not in new["needs_people_terms"]
    assert changes


def test_held_out_refuses_a_table_that_declines_passing_work(mods):
    _, store, tuner = mods
    t = store.table(1)
    worse = json.loads(json.dumps(t))
    worse["needs_people_terms"].append("note")
    held = [rec(i, f"Write note {i}", True) for i in range(6)]
    assert tuner.replay(worse, held, t["reward"])["mean_reward"] < tuner.replay(t, held, t["reward"])["mean_reward"]


def test_canary_rolls_back_and_any_version_restores(mods):
    sizer, store, tuner = mods
    t = store.table(1)
    v = store.new_version({**t, "parent": 1})
    st = store.state()
    st["canary"] = {"version": v, "share_pct": 25, "since": "2000"}
    store.save_state(st)
    for i in range(6):
        store.append("outcomes.jsonl", {**rec(i, f"a{i}", False), "finished_ok": False, "usd": 0.05, "decision": {"table_version": v}})
        store.append("outcomes.jsonl", {**rec(i + 20, f"c{i}", False), "arm": "control", "decision": {"table_version": 1}})
        store.append("outcomes.jsonl", {**rec(i + 10, f"b{i}", True), "decision": {"table_version": 1}})
    assert tuner.step()["event"] == "rolled_back"
    assert store.state()["active"] == 1 and store.state()["canary"] is None
    tuner.restore(v)
    assert store.state()["active"] == v
    tuner.restore(1)
    assert store.state()["active"] == 1


def test_canary_share_is_small_and_stable(mods):
    _, store, _ = mods
    v = store.new_version({**store.table(1), "parent": 1})
    st = {"active": 1, "canary": {"version": v, "share_pct": 25, "since": "x"}, "history": []}
    roles = [store.choose_table(f"task{i}", st)[1] for i in range(1000)]
    assert 180 < roles.count("canary") < 320
    assert roles == [store.choose_table(f"task{i}", st)[1] for i in range(1000)]


def test_promotion_needs_enough_on_both_sides_then_a_drop_sends_it_back(mods):
    _, store, tuner = mods
    t = store.table(1)
    v = store.new_version({**t, "parent": 1})
    st = store.state()
    st["canary"] = {"version": v, "share_pct": 25, "since": "2000"}
    store.save_state(st)
    for i in range(6):
        store.append("outcomes.jsonl", {**rec(i, f"a{i}", True), "decision": {"table_version": v}})
    store.append("outcomes.jsonl", {**rec(50, "b", True), "decision": {"table_version": 1}})
    assert tuner.step()["event"] == "waiting_on_canary"
    for i in range(6):
        store.append("outcomes.jsonl", {**rec(60 + i, f"b{i}", True), "decision": {"table_version": 1}})
    assert tuner.step()["event"] == "promoted" and store.state()["active"] == v
    for i in range(6):
        store.append("outcomes.jsonl", {**rec(70 + i, f"d{i}", False), "finished_ok": False, "decision": {"table_version": v}})
    assert tuner.step()["event"] == "rolled_back_after_promotion" and store.state()["active"] == 1


def test_explored_rows_are_never_called_learning(mods):
    _, store, tuner = mods
    store.append("outcomes.jsonl", {**rec(1, "x", True), "arm": "explore_flip", "decision": {"rules_fired": ["similar_tasks_failed_small"], "table_version": 1, "explored_from": "small"}})
    assert tuner.learning_examples() == []


def test_public_names_are_replaced():
    import worker

    class G:
        def sanitize_visible_text(self, t):
            return t
    assert "Teleion Fabric" in worker.public(G(), "the Tessera queue", 100) and "Herma" not in worker.public(G(), "Herma shim", 100)


def test_a_task_waiting_on_an_unfinished_task_is_blocked_with_no_model(mods):
    sizer, store, _ = mods
    t = {"task_id": "a", "title": "Compare results", "prompt": "When verb_ngo_4a590e7c1b53 is done, compare.", "category": "c", "step_mode": "atomic_cognitive_step"}
    assert sizer.named_tasks(t) == ["verb_ngo_4a590e7c1b53"]
    assert sizer.size_task(t, {"named_task_states": {"verb_ngo_4a590e7c1b53": "ready"}}, store.table(1))["handler"] == "decline_blocked"
    assert sizer.size_task(t, {"named_task_states": {"verb_ngo_4a590e7c1b53": "done"}}, store.table(1))["size"] == "small"


def test_no_finished_task_ends_the_trial_without_promoting(mods):
    _, store, tuner = mods
    v = store.new_version({**store.table(1), "parent": 1})
    st = store.state()
    st["canary"] = {"version": v, "share_pct": 25, "since": "2000", "changes_key": "k"}
    store.save_state(st)
    for i in range(6):
        store.append("outcomes.jsonl", {"task_id": f"a{i}", "kind": "c|cognitive", "arm": "sized", "size": "none", "finished_ok": False, "usd": 0.0, "decision": {"table_version": v}})
        store.append("outcomes.jsonl", {**rec(i + 10, f"b{i}", False), "finished_ok": False, "decision": {"table_version": 1}})
    assert tuner.step()["event"] == "ended_no_evidence"
    assert store.state()["active"] == 1 and store.state()["canary"] is None and "k" in store.state()["refused_changes"]


def test_a_lost_race_is_not_counted(mods):
    _, store, tuner = mods
    assert tuner._judged([{"stopped": "claim_empty", "finished_ok": False}], store.table(1)["reward"]) == []
