"""The decider's ordered route list: each failure moves on, nothing raises, and the record names the route."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from warm_agent.decider import BASETEN, GLIMMER, META, RULE, NotConfigured, decide, read_route
from warm_agent.grid_config import load_warm_agent_grid

CFG = {**load_warm_agent_grid(None).section("decider_routes"), "partner_timeout_seconds": 0.2, "meta_timeout_seconds": 0.2}
TASK = {"task_id": "t1", "title": "Do a thing", "prompt": "details", "verb_kind": "general_verb"}
GOOD = json.dumps({"model": "muse-wonder-1.0", "object_id": None, "why": "hard"})


def good(*_a, **_k):
    return {"content": GOOD, "cost_usd": 0.001}


def down(*_a, **_k):
    raise RuntimeError("down")


def slow(*_a, **_k):
    time.sleep(1)
    return good()


def run(tmp_path, **kw):
    base = {"cfg": CFG, "meta_complete": good, "search": lambda _q: [], "partner_call": good, "routes_path": tmp_path / "r.json", "spend_path": tmp_path / "s.jsonl"}
    return decide(TASK, **{**base, **kw})


def test_partner_first(tmp_path):
    d = run(tmp_path)
    assert (d["model_route"], d["model"], d["fallback"]) == (BASETEN, "muse-wonder-1.0", False)
    assert (tmp_path / "s.jsonl").exists()


def test_down_partner_moves_to_meta(tmp_path):
    d = run(tmp_path, partner_call=down)
    assert d["model_route"] == META and d["attempts"][0]["outcome"] == "failed"


def test_slow_partner_moves_on_quickly(tmp_path):
    t = time.monotonic()
    d = run(tmp_path, partner_call=slow)
    assert d["model_route"] == META and time.monotonic() - t < 0.9


def test_not_configured_is_recorded(tmp_path):
    def missing(*_a, **_k):
        raise NotConfigured

    d = run(tmp_path, partner_call=missing)
    assert d["attempts"][0]["outcome"] == "not_configured" and d["model_route"] == META


def test_all_down_uses_the_rule(tmp_path):
    d = run(tmp_path, partner_call=down, meta_complete=down)
    assert (d["model_route"], d["model"], d["fallback"], d["object_id"]) == (RULE, "muse-spark-1.3", True, None)


def test_bad_answers_are_rejected(tmp_path):
    bad = lambda *_a, **_k: {"content": json.dumps({"model": "something-else", "object_id": None}), "cost_usd": 0}  # noqa: E731
    wrong_id = lambda *_a, **_k: {"content": json.dumps({"model": "muse-spark-1.3", "object_id": "invented"}), "cost_usd": 0}  # noqa: E731
    d = run(tmp_path, partner_call=bad, meta_complete=wrong_id)
    assert d["model_route"] == RULE and [a["outcome"] for a in d["attempts"]] == ["bad_answer", "bad_answer"]


def test_listed_object_is_taken(tmp_path):
    ans = lambda *_a, **_k: {"content": json.dumps({"model": "muse-spark-1.3", "object_id": "o1"}), "cost_usd": 0}  # noqa: E731
    d = run(tmp_path, partner_call=ans, search=lambda _q: [{"id": "o1", "title": "T", "summary": "S"}])
    assert (d["object_id"], d["object_route"]) == ("o1", BASETEN)


def test_fine_tuned_route_supplies_the_object(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"active": True, "routes": {"t1": {"object_id": "o9", "title": "T", "summary": "S", "adapter_sha256": "abc"}}}))
    d = run(tmp_path)
    assert (d["object_id"], d["object_route"], d["adapter_sha256"]) == ("o9", GLIMMER, "abc") and d["model_route"] == BASETEN


def test_rolled_back_routes_are_ignored(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"active": False, "routes": {"t1": {"object_id": "o9"}}}))
    assert read_route("t1", p) is None
    p.write_text("not json")
    assert read_route("t1", p) is None


def test_rule_drops_a_fine_tuned_hint(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"active": True, "routes": {"t1": {"object_id": "o9"}}}))
    d = run(tmp_path, partner_call=down, meta_complete=down)
    assert d["object_id"] is None and d["model_route"] == RULE


def test_secret_shaped_task_reaches_no_route(tmp_path):
    seen = []
    for t in ({**TASK, "title": "use sk-abcdefghijklmnop now"}, {**TASK, "prompt": "key ghp_abcdefghijkl here"}):
        d = decide(t, cfg=CFG, meta_complete=lambda **k: seen.append(k) or good(), partner_call=lambda *a, **k: seen.append(a) or good(), search=lambda q: seen.append(q) or [], routes_path=tmp_path / "r.json", spend_path=tmp_path / "s.jsonl")
        assert d["model_route"] == RULE
    assert not seen


def test_missing_usage_keeps_the_hold():
    import httpx

    from warm_agent.decider import baseten_call

    t = httpx.MockTransport(lambda _r: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]}))
    r = baseten_call("s", "u", cfg=CFG, transport=t, settings={"BASETEN_API_KEY": "k", "BASETEN_BASE_URL": "https://example.invalid/v1", "BASETEN_MODEL_ID": "meta-models/x"})
    assert r["cost_usd"] == float(CFG["reserve_per_route_usd"])


def test_unusable_ledger_refuses_the_call(tmp_path):
    (tmp_path / "s.jsonl").mkdir()
    calls = []
    d = run(tmp_path, partner_call=lambda *a, **k: calls.append(1) or good(), meta_complete=lambda *a, **k: calls.append(1) or good())
    assert not calls and d["model_route"] == RULE


def test_slow_search_cannot_hold_the_claim(tmp_path):
    cfg = {**CFG, "search_timeout_seconds": 0.1}
    t = time.monotonic()
    d = run(tmp_path, cfg=cfg, search=lambda _q: time.sleep(1) or [])
    assert time.monotonic() - t < 0.8 and d["attempts"][0]["outcome"] == "failed" and d["model_route"] == BASETEN


def test_timed_out_call_stays_reserved_until_settled_late(tmp_path):
    from warm_agent.decider import _total

    run(tmp_path, partner_call=slow)
    assert _total((tmp_path / "s.jsonl").read_text()) >= float(CFG["reserve_per_route_usd"])
    time.sleep(1.1)
    assert '"answered after its time' in (tmp_path / "s.jsonl").read_text() or "answered after its time" in (tmp_path / "s.jsonl").read_text()


def test_budget_stop_uses_the_rule_and_keeps_a_route(tmp_path):
    (tmp_path / "s.jsonl").write_text(json.dumps({"kind": "cost", "usd": 9.5}) + "\n")
    calls = []
    d = run(tmp_path, partner_call=lambda *a, **k: calls.append(1) or good())
    assert d["model_route"] == RULE and not calls


def test_stalled_ledger_lock_refuses_quickly(tmp_path):
    import fcntl

    ledger = tmp_path / "s.jsonl"
    ledger.write_text("")
    holder = ledger.open("a")
    fcntl.flock(holder, fcntl.LOCK_EX)
    cfg = {**CFG, "ledger_lock_wait_seconds": 0.05}
    calls = []
    t = time.monotonic()
    d = run(tmp_path, cfg=cfg, partner_call=lambda *a, **k: calls.append(1) or good(), meta_complete=lambda *a, **k: calls.append(1) or good())
    assert time.monotonic() - t < 0.5 and not calls and d["model_route"] == RULE
    holder.close()


def test_model_may_echo_the_fine_tuned_object(tmp_path):
    (tmp_path / "r.json").write_text(json.dumps({"active": True, "routes": {"t1": {"object_id": "o9"}}}))
    ans = lambda *_a, **_k: {"content": json.dumps({"model": "muse-spark-1.3", "object_id": "o9"}), "cost_usd": 0}  # noqa: E731
    d = run(tmp_path, partner_call=ans)
    assert (d["object_id"], d["object_route"], d["model_route"]) == ("o9", GLIMMER, BASETEN)


def test_long_slugs_are_not_treated_as_secrets():
    from warm_agent.decider import looks_secret

    assert not looks_secret("Client-Side Distributed Index Enrichment for 'camelot_fuzz_rerun_after_clean_error_muse-worker-01_20261104_v1'")
    assert looks_secret("use ghp_abcdefghijkl now")


def test_malformed_billed_reply_keeps_the_hold(tmp_path):
    def broken(*_a, **_k):
        raise KeyError("choices")

    d = run(tmp_path, partner_call=broken)
    assert d["attempts"][0]["outcome"] == "failed" and '"usd": 0.02' in (tmp_path / "s.jsonl").read_text()


def test_absent_cost_keeps_the_hold(tmp_path):
    d = run(tmp_path, partner_call=lambda *a, **k: {"content": GOOD, "cost_usd": None})
    assert d["cost_usd"] == float(CFG["reserve_per_route_usd"])


def test_candidate_with_a_credential_shape_is_never_sent(tmp_path):
    sent = []
    bad = {"id": "o2", "title": "T", "summary": "key ghp_abcdefghijkl"}
    run(tmp_path, partner_call=lambda sys_, user, **k: sent.append(user) or good(), search=lambda _q: [bad, {"id": "o3", "title": "fine", "summary": "ok"}])
    assert "ghp_" not in sent[0] and "o3" in sent[0]


def test_the_hold_covers_the_worst_case_on_the_list_rates():
    from warm_agent.decider import worst_case_usd

    grid = load_warm_agent_grid(None)
    cfg = grid.section("decider_routes")
    spark = grid.section("budget_and_rates")["models"]["muse-spark-1.3"]["prices_usd_per_million"]
    hold = float(cfg["reserve_per_route_usd"])
    assert worst_case_usd(cfg, spark["input"], spark["output"], int(cfg["meta_max_output_tokens"])) <= hold
    assert worst_case_usd(cfg, float(cfg["partner_input_usd_per_million"]), float(cfg["partner_output_usd_per_million"]), int(cfg["partner_max_output_tokens"])) <= hold


def test_stalled_decide_cannot_hold_the_claim(monkeypatch):
    from warm_agent import decider

    def stalls(*_a, attempts=None, **_k):
        attempts.append({"route": "baseten_meta_open_model", "outcome": "timed_out"})
        time.sleep(2)

    monkeypatch.setattr(decider, "decide", stalls)
    cfg = {**CFG, "overall_deadline_seconds": 0.1, "partner_timeout_seconds": 0.1}
    t = time.monotonic()
    d = decider.bounded_decide(TASK, cfg=cfg, meta_complete=good, search=lambda _q: [])
    assert time.monotonic() - t < 1 and d["model_route"] == RULE and d["model"] == "muse-spark-1.3"
    assert d["attempts"][0]["outcome"] == "timed_out"  # earlier attempts stay on the record


def test_more_secret_shapes():
    from warm_agent.decider import looks_secret

    for text in ("xo" "xb-1234567890-1234567890-abcdefghijklmnopqrstuvwx", "AK" "IAABCDEFGHIJKLMNOP", "-----BE" "GIN PRIVATE KEY-----", "github_pat_abc123", "postgresql://app:n8V!q2Rs7@db.internal/app"):
        assert looks_secret(text), text


def test_a_hold_too_small_means_no_call(tmp_path):
    calls = []
    d = run(tmp_path, cfg={**CFG, "reserve_per_route_usd": 0.0001}, partner_call=lambda *a, **k: calls.append(1) or good(), meta_complete=lambda *a, **k: calls.append(1) or good())
    assert not calls and d["model_route"] == RULE and d["attempts"][0]["outcome"] == "refused_hold_too_small"


def test_next_routed_task(tmp_path):
    from warm_agent.decider import next_routed_task

    p = tmp_path / "r.json"
    assert next_routed_task(p, set()) is None
    p.write_text(json.dumps({"active": True, "routes": {"a": {}, "b": {}}}))
    assert next_routed_task(p, set()) == "a" and next_routed_task(p, {"a"}) == "b" and next_routed_task(p, {"a", "b"}) is None
    p.write_text(json.dumps({"active": False, "routes": {"a": {}}}))
    assert next_routed_task(p, set()) is None


def test_plain_rule_needs_no_model(tmp_path):
    calls = []
    t = {**TASK, "title": "Client-Side Distributed Index Enrichment for 'x'"}
    d = decide(t, cfg=CFG, meta_complete=lambda **k: calls.append(1) or good(), partner_call=lambda *a, **k: calls.append(1) or good(), search=lambda _q: [], routes_path=tmp_path / "r.json", spend_path=tmp_path / "s.jsonl")
    assert not calls and d["model_route"] == "plain_code_rule" and d["fallback"] is False and d["cost_usd"] == 0.0


def test_task_naming_an_object_forces_a_read_by_plain_code(tmp_path):
    t = {**TASK, "prompt": "Fetch GET https://shim.teleionlabs.com/q/object/seed_v1, then check it"}
    d = decide(t, cfg=CFG, meta_complete=good, partner_call=good, search=lambda _q: [], routes_path=tmp_path / "r.json", spend_path=tmp_path / "s.jsonl")
    assert d["tool"] == {"name": "read_task_object", "key": "seed_v1", "chosen_by": "plain_code_rule"}


def test_other_hosts_are_not_read(tmp_path):
    t = {**TASK, "prompt": "Fetch GET https://evil.example/q/object/seed_v1"}
    d = decide(t, cfg=CFG, meta_complete=good, partner_call=good, search=lambda _q: [], routes_path=tmp_path / "r.json", spend_path=tmp_path / "s.jsonl")
    assert "tool" not in d


def test_model_guided_read(tmp_path):
    ans = lambda *_a, **_k: {"content": json.dumps({"model": "muse-spark-1.3", "object_id": "o1", "read_object": True}), "cost_usd": 0}  # noqa: E731
    d = run(tmp_path, partner_call=ans, search=lambda _q: [{"id": "o1", "title": "T", "summary": "S"}])
    assert d["tool"] == {"name": "read_task_object", "key": "o1", "chosen_by": BASETEN}
