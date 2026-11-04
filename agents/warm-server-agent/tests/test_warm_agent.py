"""Automated conformance and behavioral test suite for `warm-server-agent`."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from warm_agent.agent_loop import WarmServerAgent
from warm_agent.banned_words_guard import BannedWordsGuard, scrub_private_info
from warm_agent.canary_and_tuner import (
    LineageDescriptor,
    ModelCanaryRegistry,
    TunerLoop,
    verify_checker_independence,
)
from warm_agent.grid_config import GridLedger, load_warm_agent_grid
from warm_agent.meta_client import (
    ContributorTierDenied,
    ModelCallError,
    SharedSpendLedger,
    SpendCapExceeded,
    WarmMetaModelClient,
)

ALLOWED_NUMERIC_IDENTITIES = {0, 1, -1, 0.0, 1.0}
FORBIDDEN_INDUSTRY_TOKENS = (
    "real_estate",
    "realestate",
    "mortgage",
    "healthcare",
    "hospital",
    "patient",
    "fintech",
    "ecommerce",
    "hospitality",
    "parcel",
    "zoning",
    "insurance",
    "retail",
)


def test_zero_hardcoded_values_ast_gate() -> None:
    """ZeroHardcodedValuesAstGate: operational `src/warm_agent/*.py` must contain zero magic numbers."""
    violations: list[str] = []
    for py_path in sorted((SRC_DIR / "warm_agent").glob("*.py")):
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                val = node.value
                if val not in ALLOWED_NUMERIC_IDENTITIES:
                    violations.append(f"{py_path.name}:{node.lineno} literal={val!r}")
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
                    neg_val = -node.operand.value
                    if neg_val not in ALLOWED_NUMERIC_IDENTITIES:
                        violations.append(f"{py_path.name}:{node.lineno} unary_literal={neg_val!r}")
    assert violations == [], f"Magic numeric literals detected: {violations}"


def test_domain_agnostic_naming_gate() -> None:
    """DomainAgnosticNamingGate: filenames, schema IDs, and Python symbols must be 100% domain-agnostic."""
    violations: list[str] = []
    for folder in (ROOT_DIR / "config", SRC_DIR, ROOT_DIR / "tests"):
        for path in sorted(folder.rglob("*")):
            if "__pycache__" in path.parts:
                continue
            low_name = path.name.lower()
            for bad in FORBIDDEN_INDUSTRY_TOKENS:
                if bad in low_name:
                    violations.append(f"filename:{path.name}:{bad}")
            if path.suffix == ".json":
                spec = json.loads(path.read_text(encoding="utf-8"))
                schema_id = str(spec.get("schema_id") or "").lower()
                for bad in FORBIDDEN_INDUSTRY_TOKENS:
                    if bad in schema_id:
                        violations.append(f"schema_id:{schema_id}:{bad}")
            elif path.suffix == ".py" and path.parent != ROOT_DIR / "tests":
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        sym_low = node.name.lower()
                        for bad in FORBIDDEN_INDUSTRY_TOKENS:
                            if bad in sym_low:
                                violations.append(f"symbol:{path.name}:{node.name}:{bad}")
    assert violations == [], f"Industry-coupled names detected: {violations}"


def test_banned_words_and_private_scrubber_gate() -> None:
    """BannedWordsGuard dynamically loads rules/banned-words.json and keeps config/src clean."""
    grid = load_warm_agent_grid()
    guard = BannedWordsGuard(grid.section("endpoints_and_paths")["banned_words_path"])
    for path in sorted(list((ROOT_DIR / "config").glob("*.json")) + list((SRC_DIR / "warm_agent").glob("*.py"))):
        hits = guard.scan_text(path.read_text(encoding="utf-8"), include_visible_rules=False)
        assert hits == [], f"Banned word hit in {path.name}: {hits}"

    assert guard.scan_text("Teleion Labs runs Teleion Fabric.", include_visible_rules=True) == []
    scrubbed = scrub_private_info("Contact ops@example.org with Bearer tan_secret123 or 415-555-0199")
    assert "ops@example.org" not in scrubbed
    assert "tan_secret123" not in scrubbed
    assert "415-555-0199" not in scrubbed


def test_node_grid_lifecycle_regime_selection_and_boundary_auto_expansion() -> None:
    grid = load_warm_agent_grid()
    ledger = GridLedger()
    ledger.register("custom_cell")
    with pytest.raises(PermissionError):
        ledger.promote_verified("custom_cell")
    ledger.advance_through_verified("custom_cell")
    ledger.promote_verified("custom_cell")
    assert ledger.cell_states["custom_cell"] == "promoted"

    cell_default, _ = grid.resolve_regime_cell(ready_count=0, idle_cycles=0)
    assert cell_default == "interactive_warm_cell"
    backlog_threshold = int(grid.section("regimes")["high_backlog_ready_threshold"])
    cell_backlog, _ = grid.resolve_regime_cell(ready_count=backlog_threshold + 2, idle_cycles=0)
    assert cell_backlog == "high_backlog_cell"
    cell_idle, _ = grid.resolve_regime_cell(ready_count=0, idle_cycles=3)
    assert cell_idle == "low_activity_conservation_cell"

    gen_before = grid.generation
    high_before = grid.axes["default_max_output_tokens"].high
    assert high_before is not None
    expanded = grid.maybe_expand_boundary("default_max_output_tokens", high_before)
    assert expanded is True
    assert grid.generation == gen_before + 1
    assert (grid.axes["default_max_output_tokens"].high or 0) > high_before


def test_shared_spend_ledger_contributor_refusal_and_native_max_tokens(tmp_path: Path) -> None:
    grid = load_warm_agent_grid()
    key_file = tmp_path / "meta.env"
    key_file.write_text("META_API_KEY=test_meta_secret_do_not_log\n", encoding="utf-8")
    ledger = SharedSpendLedger(
        tmp_path / "meta-spend.json",
        daily_cap_usd=0.05,
        total_cap_usd=0.10,
        round_digits=6,
        file_mode=0o600,
        dir_mode=0o700,
    )
    attempts: list[dict[str, Any]] = []
    captured_payloads: list[dict[str, Any]] = []

    def _mock_meta(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured_payloads.append(body)
        if body.get("messages", [{}])[-1].get("content") == "TRIGGER_500":
            return httpx.Response(500, json={"error": "upstream_error"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{\"summary\":\"grounded answer\"}"}}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 100},
            },
        )

    client = WarmMetaModelClient(
        grid,
        key_file=key_file,
        ledger=ledger,
        attempt_recorder=attempts.append,
        transport=httpx.MockTransport(_mock_meta),
    )

    with pytest.raises(ContributorTierDenied):
        client.complete(
            model_id="muse-spark-1.3-contributor",
            system_prompt="sys",
            user_prompt="hi",
        )

    # Caller-provided native max_tokens (3200) must be preserved without arbitrary ceiling clamping
    res = client.complete(
        model_id="muse-spark-1.3",
        system_prompt="sys",
        user_prompt="hello",
        max_tokens=3200,
        json_object=True,
    )
    assert res["ok"] is True
    assert captured_payloads[0]["max_tokens"] == 3200
    assert ledger.read_snapshot()["calls"] == 1

    # Failed calls are recorded on the attempt log and release unused reservation
    with pytest.raises(ModelCallError):
        client.complete(
            model_id="muse-spark-1.3",
            system_prompt="sys",
            user_prompt="TRIGGER_500",
            max_tokens=256,
        )
    assert any(a["ok"] is False for a in attempts)
    assert all("test_meta_secret_do_not_log" not in json.dumps(a) for a in attempts)

    # Cap exhaustion refuses before sending HTTP
    with pytest.raises(SpendCapExceeded):
        client.complete(
            model_id="muse-wonder-1.0",
            system_prompt="sys",
            user_prompt="huge",
            max_tokens=4000,
        )
    client.close()


def test_canary_auto_promotion_gradual_rollout_and_drop_rollback(tmp_path: Path) -> None:
    grid = load_warm_agent_grid()
    registry = ModelCanaryRegistry(grid, state_path=tmp_path / "canary.json")
    cand = registry.candidates["muse_glimmer_30b_orchestrator_v1"]
    assert cand.status == "canary_active"
    assert cand.rollout_share == pytest.approx(0.15)

    # 4 passing live outcomes step rollout up to rung 2 (0.35), then 0.65, then 1.0 (promoted_default)
    for _ in range(12):
        registry.record_live_outcome("muse_glimmer_30b_orchestrator_v1", passed=True)
    assert cand.rollout_share == pytest.approx(1.0)
    assert cand.status == "promoted_default"

    # Sudden quality drop triggers immediate automatic rollback to 0.0
    dec = registry.candidates["wave3_pruned_decoder_decisioner_v1"]
    for _ in range(4):
        registry.record_live_outcome("wave3_pruned_decoder_decisioner_v1", passed=False)
    assert dec.status == "rolled_back"
    assert dec.rollout_share == pytest.approx(0.0)


def test_checker_strict_lineage_independence() -> None:
    """Different keys/UUIDs alone are NOT independent if fine-tune adapter or training data matches."""
    maker = LineageDescriptor(
        worker_uuid="w-maker-01",
        agent_id="maker-a",
        model_id="muse-spark-1.3",
        fine_tune_adapter_id="adapter-x",
        training_data_digest="corpus-nov2",
    )
    same_adapter_checker = LineageDescriptor(
        worker_uuid="w-checker-02",
        agent_id="checker-b",
        model_id="muse-spark-1.3",
        fine_tune_adapter_id="adapter-x",
        training_data_digest="different-corpus",
    )
    ok_adapter, reason_adapter = verify_checker_independence(maker, same_adapter_checker)
    assert ok_adapter is False
    assert reason_adapter == "shared_fine_tune_adapter"

    same_corpus_checker = LineageDescriptor(
        worker_uuid="w-checker-03",
        agent_id="checker-c",
        model_id="muse-wonder-1.0",
        fine_tune_adapter_id="adapter-y",
        training_data_digest="corpus-nov2",
    )
    ok_corpus, reason_corpus = verify_checker_independence(maker, same_corpus_checker)
    assert ok_corpus is False
    assert reason_corpus == "shared_training_data_corpus"

    truly_independent_checker = LineageDescriptor(
        worker_uuid="w-checker-04",
        agent_id="checker-d",
        model_id="muse-wonder-1.0",
        fine_tune_adapter_id=None,
        training_data_digest=None,
    )
    ok_indep, reason_indep = verify_checker_independence(maker, truly_independent_checker)
    assert ok_indep is True
    assert reason_indep == "ok"


def test_warm_server_agent_end_to_end_cycle_and_loopback(tmp_path: Path) -> None:
    grid = load_warm_agent_grid()
    key_file = tmp_path / "meta.env"
    key_file.write_text("META_API_KEY=mock_meta_key\n", encoding="utf-8")
    ledger = SharedSpendLedger(
        tmp_path / "meta-spend.json",
        daily_cap_usd=5.0,
        total_cap_usd=25.0,
        round_digits=6,
        file_mode=0o600,
        dir_mode=0o700,
    )

    submitted_payloads: list[dict[str, Any]] = []
    bridge_posts: list[dict[str, Any]] = []

    def _mock_meta(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        model = body["model"]
        if model == "muse-wonder-1.0":
            content = json.dumps(
                {"verdict": "CONFIRMED", "quality_milli": 910, "summary": "Verified external Task Object."}
            )
        else:
            content = json.dumps(
                {
                    "summary": "Grounded Task execution result.",
                    "findings": ["Lease valid", "Schema verified"],
                    "recommended_next_step": "Queue independent verification",
                }
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 60},
            },
        )

    def _mock_tessera(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/health":
            return httpx.Response(
                200,
                json={"ok": True, "queues": {"eq01": {"ready": 0}, "eq02": {"ready": 2}, "eq03": {"ready": 0}}},
            )
        return httpx.Response(404, json={"ok": False})

    def _mock_herma(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/health":
            return httpx.Response(200, json={"ok": True})
        if path == "/q/register":
            body = json.loads(request.content.decode("utf-8"))
            aid = body["agent_id"]
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "worker_token": f"tok_{aid}",
                    "worker_profile": {"agent_id": aid, "worker_uuid": f"uuid_{aid}"},
                },
            )
        if path == "/bridge/threads":
            return httpx.Response(200, json={"ok": True, "threads": ["warm-agent-hub"]})
        if path == "/bridge/warm-agent-hub/status":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "inbox": [
                        {
                            "id": 101,
                            "sender": "peer-volunteer-01",
                            "target_agent": "*",
                            "prompt_text": "How do I renew a Task lease before timeout?",
                            "simhash64_hex": "aa11bb22cc33dd44",
                        }
                    ],
                },
            )
        if path == "/bridge/warm-agent-hub/inbox" and request.method == "POST":
            bridge_posts.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json={"ok": True, "queued_count": 1})
        if path == "/q/feedback":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "feedback": [
                        {
                            "feedback_id": "fb_ext_01",
                            "agent_id": "external-worker-99",
                            "observation": "Leaderboard timed out when fetching default rows; need paginated query.",
                        }
                    ],
                },
            )
        if path == "/q/objects":
            return httpx.Response(200, json={"objects": [{"object_key": "warm_artifact_e2e", "eval_count": 0}]})
        if path == "/q/object/warm_artifact_e2e":
            return httpx.Response(
                200,
                json={
                    "object_key": "warm_artifact_e2e",
                    "worker_uuid": "uuid_teleion-warm-maker",
                    "producer_agent": "teleion-warm-maker",
                    "source_task_id": "task_build_01",
                    "payload": {
                        "summary": "Grounded",
                        "producer_lineage": {
                            "model_id": "muse-spark-1.3",
                            "training_data_digest": "manifest-ext-77",
                            "training_example_ids": ["ext-row-1", "ext-row-2"],
                        },
                    },
                },
            )
        if path == "/q/task/task_build_01":
            return httpx.Response(200, json={"task": {"title": "Summarize", "prompt": "Summarize the resources"}})
        if path == "/q/enqueue":
            return httpx.Response(200, json={"ok": True, "enqueued_followup_verbs": [{"task_id": "task_verify_01"}]})
        if path == "/q/claim":
            step_mode = request.url.params.get("step_mode")
            if step_mode == "atomic_build_step":
                return httpx.Response(
                    200,
                    json={
                        "ok": True,
                        "task": {
                            "task_id": "task_build_01",
                            "step_mode": "atomic_build_step",
                            "verb_kind": "draft_resource_summary",
                            "title": "Summarize verified municipal food resources",
                            "lease_epoch": 7,
                        },
                    },
                )
            if request.url.params.get("task_id") == "task_verify_01":
                return httpx.Response(200, json={"ok": True, "task": {"task_id": "task_verify_01", "lease_epoch": 3}})
        if path == "/q/submit" and request.method == "POST":
            body_json = json.loads(request.content.decode("utf-8"))
            submitted_payloads.append(body_json)
            raw_objs = body_json.get("task_objects")
            stored_objs = (
                [{"object_key": o["object_key"]} for o in raw_objs if isinstance(o, dict) and o.get("object_key")]
                if isinstance(raw_objs, list)
                else []
            )
            applied = [{"target_id": e["target_id"]} for e in body_json.get("evaluations") or []]
            return httpx.Response(200, json={"ok": True, "stored_task_objects": stored_objs, "applied_evaluations": applied})
        return httpx.Response(404, json={"ok": False})

    meta_client = WarmMetaModelClient(
        grid,
        key_file=key_file,
        ledger=ledger,
        transport=httpx.MockTransport(_mock_meta),
    )
    agent = WarmServerAgent(
        grid,
        meta_client=meta_client,
        herma_transport=httpx.MockTransport(_mock_herma),
        tessera_transport=httpx.MockTransport(_mock_tessera),
        state_dir_override=tmp_path / "state",
        credentials_dir_override=tmp_path / "creds",
        loopback_port_override=0,
    )
    meta_client.attempt_recorder = agent._record_model_attempt
    agent.checker_identity.update(
        {
            "training_data_digest": "manifest-checker-wonder",
            "training_example_ids": ["chk-row-101", "chk-row-102"],
        }
    )

    port = agent.start_loopback_server()
    try:
        report = agent.run_single_cycle()
        assert report["ok"] is True
        assert "builder" in report["health"]["woken_roles"]
        assert (tmp_path / "state" / "wake" / "builder").exists()
        assert report["bilateral_replies"] == 2
        assert report["maker_did_work"] is True
        assert report["checker_did_work"] is True
        assert len(submitted_payloads) == 2
        assert len(bridge_posts) == 2

        # Instant no-queue HTTP loopback test
        with httpx.Client(trust_env=False) as local_http:
            st = local_http.get(f"http://127.0.0.1:{port}/v1/warm/status")
            assert st.status_code == 200
            st_json = st.json()
            assert st_json["maker_checker_distinct"] is True

            instant = local_http.post(
                f"http://127.0.0.1:{port}/v1/warm/respond",
                json={"prompt": "Ping warm server responder", "peer_agent": "codex-probe", "use_model": True},
            )
            assert instant.status_code == 200
            inst_json = instant.json()
            assert inst_json["queued"] is False
            assert inst_json["ok"] is True
    finally:
        agent.stop()

    transcripts = (tmp_path / "state" / "warm-agent-transcripts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(transcripts) == 3


def test_canary_rollback_and_rung_state_persist_across_restart(tmp_path: Path) -> None:
    """Automatic rollback (`rolled_back`) and rollout rungs survive `ModelCanaryRegistry` restart."""
    grid = load_warm_agent_grid()
    canary_path = tmp_path / "canary-restart.json"
    reg1 = ModelCanaryRegistry(grid, state_path=canary_path)

    for _ in range(4):
        reg1.record_live_outcome("wave3_pruned_decoder_decisioner_v1", passed=False)
    for _ in range(4):
        reg1.record_live_outcome("muse_glimmer_30b_orchestrator_v1", passed=True)

    assert reg1.candidates["wave3_pruned_decoder_decisioner_v1"].status == "rolled_back"
    assert reg1.candidates["wave3_pruned_decoder_decisioner_v1"].rollout_share == pytest.approx(0.0)
    assert reg1.candidates["muse_glimmer_30b_orchestrator_v1"].rung_index == 1
    assert reg1.candidates["wave3_contriever_kkt_router_v1"].to_dict()["live_serving_active"] is False

    reg2 = ModelCanaryRegistry(grid, state_path=canary_path)
    assert reg2.candidates["wave3_pruned_decoder_decisioner_v1"].status == "rolled_back"
    assert reg2.candidates["wave3_pruned_decoder_decisioner_v1"].rollout_share == pytest.approx(0.0)
    assert reg2.candidates["muse_glimmer_30b_orchestrator_v1"].rung_index == 1


def test_row_set_overlap_and_provenance_attestation_independence() -> None:
    """Overlapping row sets fail independence even when whole-corpus digests differ."""
    maker = LineageDescriptor(
        worker_uuid="w-maker-row",
        agent_id="maker-row",
        model_id="muse-spark-1.3",
        fine_tune_adapter_id="adapter-m1",
        training_data_digest="manifest-digest-a",
        training_example_ids=("ex-001", "ex-002"),
    )
    checker_overlap = LineageDescriptor(
        worker_uuid="w-checker-row",
        agent_id="checker-row",
        model_id="muse-wonder-1.0",
        fine_tune_adapter_id="adapter-c1",
        training_data_digest="manifest-digest-b",
        training_example_ids=("ex-002", "ex-099"),
    )
    ok_overlap, reason_overlap = verify_checker_independence(maker, checker_overlap)
    assert ok_overlap is False
    assert reason_overlap == "overlapping_training_examples"

    checker_missing_prov = LineageDescriptor(
        worker_uuid="w-checker-unattested",
        agent_id="checker-unattested",
        model_id="muse-wonder-1.0",
    )
    ok_att, reason_att = verify_checker_independence(
        maker, checker_missing_prov, require_provenance_attestation=True
    )
    assert ok_att is False
    assert reason_att == "provenance_not_established"


def test_truthful_maker_lineage_and_rejected_or_malformed_outcomes(tmp_path: Path) -> None:
    """Maker never credits uninvoked adapters; HTTP 200 `{ok: false}` and malformed checker JSON fail cleanly."""
    grid = load_warm_agent_grid()
    key_file = tmp_path / "meta.env"
    key_file.write_text("META_API_KEY=mock_meta_key\n", encoding="utf-8")
    ledger = SharedSpendLedger(
        tmp_path / "meta-spend.json",
        daily_cap_usd=5.0,
        total_cap_usd=25.0,
        round_digits=6,
        file_mode=0o600,
        dir_mode=0o700,
    )
    checker_mode = {"mode": "malformed_json"}
    submit_mode = {"ok": False, "stored": False}
    submitted_bodies: list[dict[str, Any]] = []

    def _mock_meta(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body["model"] == "muse-wonder-1.0":
            content = "not-json-at-all" if checker_mode["mode"] == "malformed_json" else json.dumps(
                {"verdict": "CONFIRMED", "quality_milli": 900, "summary": "Valid review"}
            )
        else:
            content = json.dumps({"summary": "Drafted output", "findings": ["f1"], "recommended_next_step": "verify"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 40},
            },
        )

    claim_task: dict[str, Any] = {
        "task_id": "task_b1",
        "step_mode": "atomic_build_step",
        "verb_kind": "draft_summary",
        "title": "Test",
        "lease_epoch": 1,
    }

    def _mock_herma(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/q/register":
            aid = json.loads(request.content.decode("utf-8"))["agent_id"]
            return httpx.Response(
                200,
                json={"ok": True, "worker_token": f"tok_{aid}", "worker_profile": {"agent_id": aid, "worker_uuid": f"u_{aid}"}},
            )
        if request.url.path == "/q/claim":
            return httpx.Response(200, json={"ok": True, "task": dict(claim_task)})
        if request.url.path == "/q/submit":
            submitted_bodies.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json=dict(submit_mode))
        return httpx.Response(404, json={"ok": False})

    meta_client = WarmMetaModelClient(grid, key_file=key_file, ledger=ledger, transport=httpx.MockTransport(_mock_meta))
    agent = WarmServerAgent(
        grid,
        meta_client=meta_client,
        herma_transport=httpx.MockTransport(_mock_herma),
        tessera_transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"ok": True, "queues": {}})),
        state_dir_override=tmp_path / "state",
        credentials_dir_override=tmp_path / "creds",
        loopback_port_override=0,
    )

    # 1. Maker HTTP 200 with `{ok: False, stored: False}` must NOT count as success or credit Wave-3 canary
    maker_ok = agent.execute_maker_step()
    assert maker_ok is False
    assert agent.metrics["maker_submissions"] == 0
    assert agent.canary_registry.candidates["wave3_pruned_decoder_decisioner_v1"].recent_outcomes == []
    submitted_objs = submitted_bodies[-1]["task_objects"]
    assert isinstance(submitted_objs, list) and len(submitted_objs) == 1
    assert submitted_objs[0]["object_key"] == "warm_artifact_task_b1"
    prod_lin = submitted_objs[0]["payload"]["producer_lineage"]
    assert prod_lin["model_id"] == "muse-spark-1.3"
    assert prod_lin["fine_tune_adapter_id"] is None



def _checker_rig(tmp_path: Path, meta_content: str, *, maker_model: str = "muse-spark-1.3", claim_other_task: bool = False):
    grid = load_warm_agent_grid()
    key_file = tmp_path / "meta.env"
    key_file.write_text("META_API_KEY=mock_meta_key\n", encoding="utf-8")
    ledger = SharedSpendLedger(
        tmp_path / "meta-spend.json", daily_cap_usd=5.0, total_cap_usd=25.0, round_digits=6, file_mode=0o600, dir_mode=0o700
    )
    calls: dict[str, list[Any]] = {"meta": [], "claim": [], "enqueue": [], "submit": [], "release": []}

    def _meta(request: httpx.Request) -> httpx.Response:
        calls["meta"].append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": meta_content}}], "usage": {"prompt_tokens": 10, "completion_tokens": 10}},
        )

    def _herma(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/q/onboard" or path.endswith("/onboard"):
            return httpx.Response(200, json={"ok": True, "worker_uuid": f"u_{len(path)}", "worker_token": "tok"})
        if path == "/q/objects":
            return httpx.Response(
                200,
                json={
                    "objects": [
                        {"object_key": "warm_artifact_seen", "eval_count": 1},
                        {"object_key": "other_object", "eval_count": 0},
                        {"object_key": "warm_artifact_t1", "eval_count": 0},
                    ]
                },
            )
        if path == "/q/object/warm_artifact_t1":
            return httpx.Response(
                200,
                json={
                    "object_key": "warm_artifact_t1",
                    "worker_uuid": "u_maker_elsewhere",
                    "producer_agent": "teleion-warm-maker",
                    "source_task_id": "src1",
                    "payload": {"summary": "did it", "producer_lineage": {"model_id": maker_model}},
                },
            )
        if path == "/q/task/src1":
            return httpx.Response(200, json={"task": {"title": "Do it", "prompt": "Do the thing"}})
        if path == "/q/enqueue":
            calls["enqueue"].append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json={"ok": True, "enqueued_followup_verbs": [{"task_id": "chk1"}]})
        if path == "/q/claim":
            calls["claim"].append(dict(request.url.params))
            task_id = "other_task" if claim_other_task else "chk1"
            return httpx.Response(200, json={"task": {"task_id": task_id, "lease_epoch": 3}})
        if path == "/q/release":
            calls["release"].append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json={"ok": True})
        if path == "/q/submit":
            body = json.loads(request.content.decode("utf-8"))
            calls["submit"].append(body)
            return httpx.Response(
                200, json={"ok": True, "applied_evaluations": [{"target_id": body["evaluations"][0]["target_id"]}]}
            )
        return httpx.Response(200, json={"ok": True, "worker_uuid": "u_x", "worker_token": "tok"})

    agent = WarmServerAgent(
        grid,
        meta_client=WarmMetaModelClient(grid, key_file=key_file, ledger=ledger, transport=httpx.MockTransport(_meta)),
        herma_transport=httpx.MockTransport(_herma),
        tessera_transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"ok": True, "queues": {}})),
        state_dir_override=tmp_path / "state",
        credentials_dir_override=tmp_path / "creds",
        loopback_port_override=0,
    )
    agent.maker_identity = {"agent_id": "teleion-warm-maker", "worker_uuid": "u_maker", "worker_token": "m"}
    agent.checker_identity = {"agent_id": "teleion-warm-checker", "worker_uuid": "u_checker", "worker_token": "c"}
    return agent, calls


def test_checker_checks_the_named_target_and_refused_verdict_is_stored(tmp_path: Path) -> None:
    agent, calls = _checker_rig(tmp_path, json.dumps({"verdict": "NEEDS_REVISION", "quality_milli": 120, "summary": "not done"}))
    assert agent.execute_checker_step() is True
    assert calls["claim"][0]["task_id"] == "chk1"
    assert calls["enqueue"][0]["worker_uuid"] == "u_maker"  # the maker asks; the maker can't claim it
    assert "owner_worker_uuid" not in calls["enqueue"][0]["verbs"][0]  # the shim bars an owner from a verification Task
    evaluation = calls["submit"][0]["evaluations"][0]
    assert evaluation["target_id"] == "warm_artifact_t1"
    assert evaluation["verdict"] == "REFUTED"  # the shim stores this; NEEDS_REVISION would read UNREVIEWED
    assert calls["submit"][0]["worker_uuid"] == "u_checker"
    prompt = json.dumps(calls["meta"][0])
    assert "Do the thing" in prompt and "did it" in prompt
    assert calls["release"] == []
    # Nothing new to check: no claim and no model call.
    assert agent.execute_checker_step() is False
    assert len(calls["claim"]) == 1 and len(calls["meta"]) == 1


def test_checker_refuses_same_model_before_any_claim_or_model_call(tmp_path: Path) -> None:
    agent, calls = _checker_rig(tmp_path, "{}", maker_model="muse-wonder-1.0")
    assert agent.execute_checker_step() is False
    assert calls["enqueue"] == [] and calls["claim"] == [] and calls["meta"] == []


def test_checker_with_training_history_needs_attested_maker(tmp_path: Path) -> None:
    agent, calls = _checker_rig(tmp_path, "{}")
    agent.checker_identity["training_data_digest"] = "checker-manifest-v1"
    assert agent.execute_checker_step() is False  # the maker has no attested rows, so nothing proves they don't overlap
    assert calls["claim"] == [] and calls["meta"] == []


def test_checker_releases_on_malformed_output_and_never_admits_it(tmp_path: Path) -> None:
    agent, calls = _checker_rig(tmp_path, "not json")
    assert agent.execute_checker_step() is False
    assert calls["submit"] == []
    assert [r["task_id"] for r in calls["release"]] == ["chk1"]
    # A retry after a restart reuses the same check Task.
    agent._checker_tried.clear()
    assert agent.execute_checker_step() is False
    assert len(calls["enqueue"]) == 1 and len(calls["claim"]) == 2
    traces = [json.loads(x) for x in (tmp_path / "state" / "warm-training-traces.jsonl").read_text(encoding="utf-8").splitlines()]
    assert traces and all(t["training_admitted"] is False for t in traces)


def test_checker_gives_back_a_task_it_did_not_ask_for(tmp_path: Path) -> None:
    agent, calls = _checker_rig(tmp_path, "{}", claim_other_task=True)
    assert agent.execute_checker_step() is False
    assert [r["task_id"] for r in calls["release"]] == ["other_task"]
    assert calls["meta"] == []


def test_checker_daily_limit_stops_before_any_network_work(tmp_path: Path) -> None:
    agent, calls = _checker_rig(tmp_path, "{}")
    agent.ops["checker_max_checks_per_day"] = 0
    assert agent.execute_checker_step() is False
    assert calls["claim"] == [] and calls["enqueue"] == []


def test_strict_milli_score_contract_and_checker_correctness_separation(tmp_path: Path) -> None:
    """Milli scores 0,1,10,100,749,750,1000 stay unchanged; floats/1e309/-1/1001/bool fail cleanly."""
    grid = load_warm_agent_grid()
    guard = BannedWordsGuard(grid.section("endpoints_and_paths")["banned_words_path"])
    tuner = TunerLoop(grid, banned_guard=guard, trace_path=tmp_path / "traces.jsonl")

    for exact_val in (0, 1, 10, 100, 749, 750, 1000):
        assert tuner.validate_milli_score(exact_val) == exact_val
        assert tuner.normalize_milli_score(exact_val) == exact_val
        row = tuner.record_outcome_and_trace(
            persona_id="independent_skeptical_verifier",
            model_id="muse-wonder-1.0",
            role="checker",
            prompt_text="p",
            response_text="clean review",
            raw_quality_score=exact_val,
            cost_usd=0.001,
            training_admitted=True,
            target_verdict="CONFIRMED",
            checker_correctness="unknown",
        )
        assert row["quality_milli"] == exact_val
        assert row["passed"] is (exact_val >= 750)
        assert row["training_admitted"] is (exact_val >= 750)
        assert row["checker_correctness"] == "unknown"

    # Unknown checker_correctness leaves posterior trials at 0.0; explicit 'correct' rewards even a rejection!
    assert tuner.posteriors["independent_skeptical_verifier"]["trials"] == 0.0
    reject_row = tuner.record_outcome_and_trace(
        persona_id="independent_skeptical_verifier",
        model_id="muse-wonder-1.0",
        role="checker",
        prompt_text="p",
        response_text="accurately rejected incomplete output",
        raw_quality_score=200,
        cost_usd=0.001,
        training_admitted=True,
        target_verdict="NEEDS_REVISION",
        checker_correctness="correct",
    )
    assert reject_row["training_admitted"] is False
    assert tuner.posteriors["independent_skeptical_verifier"]["alpha"] == pytest.approx(3.0)

    for bad_val in (900.25, 1001, -1, float("inf"), float("nan"), True, "900"):
        assert tuner.validate_milli_score(bad_val) is None


def test_meta_client_fault_injection_and_attempt_reconciliation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed HTTP 200 & absent usage hold reservation; settlement/recorder faults preserve response & reconcile."""
    grid = load_warm_agent_grid()
    key_file = tmp_path / "meta.env"
    key_file.write_text("META_API_KEY=mock_meta_key\n", encoding="utf-8")

    # 1. Malformed HTTP 200 body retains pending reservation (never refunds to 0.0)
    ledger_malformed = SharedSpendLedger(
        tmp_path / "l1.json", daily_cap_usd=5.0, total_cap_usd=25.0, round_digits=6, file_mode=0o600, dir_mode=0o700
    )
    c1 = WarmMetaModelClient(
        grid,
        key_file=key_file,
        ledger=ledger_malformed,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"{not-valid-json")),
    )
    with pytest.raises(ModelCallError):
        c1.complete(model_id="muse-spark-1.3", system_prompt="s", user_prompt="u")
    assert ledger_malformed.read_snapshot()["total_usd"] > 0.0
    c1.close()

    # 2. Absent usage marks usage_exact=False and holds conservative reservation
    ledger_nousage = SharedSpendLedger(
        tmp_path / "l2.json", daily_cap_usd=5.0, total_cap_usd=25.0, round_digits=6, file_mode=0o600, dir_mode=0o700
    )
    c2 = WarmMetaModelClient(
        grid,
        key_file=key_file,
        ledger=ledger_nousage,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "hello world"}}]})
        ),
    )
    res_no_usage = c2.complete(model_id="muse-spark-1.3", system_prompt="s", user_prompt="u")
    assert res_no_usage["usage_exact"] is False
    assert res_no_usage["output_tokens"] is None
    assert res_no_usage["accounting_status"] == "pending_unknown_usage"
    assert ledger_nousage.read_snapshot()["total_usd"] == pytest.approx(res_no_usage["reserved_usd"])
    c2.close()

    # 3. Settlement os.replace failure once + recorder failure once STILL returns response and reconciles on restart
    ledger_fault = SharedSpendLedger(
        tmp_path / "l3.json", daily_cap_usd=5.0, total_cap_usd=25.0, round_digits=6, file_mode=0o600, dir_mode=0o700
    )
    real_replace = __import__("os").replace
    ledger_replaces = {"n": 0}

    def _flaky_replace(src: Any, dst: Any) -> None:
        if Path(dst) == ledger_fault.path:
            ledger_replaces["n"] += 1
            if ledger_replaces["n"] == 2:
                raise OSError("injected post-response settlement replace failure")
        real_replace(src, dst)

    monkeypatch.setattr("os.replace", _flaky_replace)
    rec_rows: list[dict[str, Any]] = []
    rec_fail = {"once": True}

    def _flaky_recorder(row: dict[str, Any]) -> None:
        if rec_fail["once"]:
            rec_fail["once"] = False
            raise OSError("injected recorder failure")
        rec_rows.append(row)

    c3 = WarmMetaModelClient(
        grid,
        key_file=key_file,
        ledger=ledger_fault,
        attempt_recorder=_flaky_recorder,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "preserved content"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 200},
                },
            )
        ),
    )
    out = c3.complete(model_id="muse-spark-1.3", system_prompt="s", user_prompt="u")
    assert out["content"] == "preserved content"
    assert out["cost_usd"] == pytest.approx(0.000975)
    assert out["settlement_status"] == "pending_known_settlement"
    assert out["telemetry_recorded"] is False
    # Reservation was NOT wiped to 0.0!
    assert ledger_fault.read_snapshot()["total_usd"] == pytest.approx(out["reserved_usd"])
    c3.close()

    # Reconstructing client reconciles both exact $0.000975 settlement and pending telemetry without redispatching!
    dispatches = {"n": 0}

    def _should_not_dispatch(_: httpx.Request) -> httpx.Response:
        dispatches["n"] += 1
        return httpx.Response(500)

    c3_restarted = WarmMetaModelClient(
        grid,
        key_file=key_file,
        ledger=ledger_fault,
        attempt_recorder=_flaky_recorder,
        transport=httpx.MockTransport(_should_not_dispatch),
    )
    assert dispatches["n"] == 0
    assert ledger_fault.read_snapshot()["total_usd"] == pytest.approx(0.000975)
    assert ledger_fault.read_snapshot()["calls"] == 1
    assert len(rec_rows) == 1
    assert rec_rows[0]["ok"] is True
    assert rec_rows[0]["cost_usd"] == pytest.approx(0.000975)
    c3_restarted.close()


def test_maker_submit_array_contract_and_unpersisted_200_rejection(tmp_path: Path) -> None:
    """Maker sends `task_objects` as an array, rejects HTTP 200 without `stored_task_objects`, and scrubs `marketing_voice`."""
    grid = load_warm_agent_grid()
    guard = BannedWordsGuard(grid.section("endpoints_and_paths")["banned_words_path"])
    dirty_text = guard.sanitize_visible_text("Verified and confirmed provenance with cryptographic hashes.")
    assert guard.scan_text(dirty_text, include_visible_rules=True, include_marketing_rules=True) == []

    key_file = tmp_path / "meta.env"
    key_file.write_text("META_API_KEY=mock_meta_key\n", encoding="utf-8")
    ledger = SharedSpendLedger(
        tmp_path / "meta-spend.json",
        daily_cap_usd=5.0,
        total_cap_usd=25.0,
        round_digits=6,
        file_mode=0o600,
        dir_mode=0o700,
    )
    persist_objects = {"enabled": False}
    captured_submits: list[dict[str, Any]] = []

    def _mock_meta(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Verified provenance summary",
                                    "findings": ["step 1"],
                                    "recommended_next_step": "peer check",
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 25},
            },
        )

    def _mock_herma(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/q/register":
            aid = json.loads(request.content.decode("utf-8"))["agent_id"]
            return httpx.Response(
                200,
                json={"ok": True, "worker_token": f"tok_{aid}", "worker_profile": {"agent_id": aid, "worker_uuid": f"u_{aid}"}},
            )
        if request.url.path == "/q/claim":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "task": {
                        "task_id": "task_arr_01",
                        "step_mode": "atomic_build_step",
                        "verb_kind": "draft_summary",
                        "title": "Test array contract",
                        "lease_epoch": 2,
                    },
                },
            )
        if request.url.path == "/q/submit":
            body = json.loads(request.content.decode("utf-8"))
            captured_submits.append(body)
            stored = (
                [{"object_key": o["object_key"]} for o in body.get("task_objects", []) if isinstance(o, dict) and o.get("object_key")]
                if persist_objects["enabled"] and isinstance(body.get("task_objects"), list)
                else []
            )
            return httpx.Response(200, json={"ok": True, "stored_task_objects": stored})
        return httpx.Response(404, json={"ok": False})

    meta_client = WarmMetaModelClient(grid, key_file=key_file, ledger=ledger, transport=httpx.MockTransport(_mock_meta))
    agent = WarmServerAgent(
        grid,
        meta_client=meta_client,
        herma_transport=httpx.MockTransport(_mock_herma),
        tessera_transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"ok": True, "queues": {}})),
        state_dir_override=tmp_path / "state",
        credentials_dir_override=tmp_path / "creds",
        loopback_port_override=0,
    )

    # HTTP 200 with empty stored_task_objects must NOT credit maker_submissions!
    assert agent.execute_maker_step() is False
    assert agent.metrics["maker_submissions"] == 0
    assert isinstance(captured_submits[-1]["task_objects"], list)
    assert captured_submits[-1]["task_objects"][0]["object_key"] == "warm_artifact_task_arr_01"
    assert guard.scan_text(
        captured_submits[-1]["summary"],
        include_visible_rules=True,
        include_marketing_rules=True,
    ) == []

    # HTTP 200 with stored_task_objects including warm_artifact_task_arr_01 succeeds!
    persist_objects["enabled"] = True
    assert agent.execute_maker_step() is True
    assert agent.metrics["maker_submissions"] == 1





def test_no_key_audit_picks_only_no_key_work_and_names_a_known_maker_model() -> None:
    from warm_agent.audit_no_key import is_no_key_work, maker_model_for

    base = {"worker_uuid": "w_agent_x", "eval_count": 0, "category": "ngo_public_good", "source_task_id": "t1"}
    assert is_no_key_work(base)
    assert not is_no_key_work({**base, "worker_uuid": "w_teleionwarmm_1"})
    assert not is_no_key_work({**base, "eval_count": 1})
    assert not is_no_key_work({**base, "category": "worker_memory"})
    assert not is_no_key_work({**base, "source_task_id": "self_seed"})
    assert maker_model_for({"producer_agent": "scale-test-03"}) == "muse-spark-1.3-contributor"
    assert maker_model_for({"producer_agent": "someone"}) == ""


def test_unknown_maker_model_still_holds_when_nothing_names_one(tmp_path: Path) -> None:
    agent, calls = _checker_rig(tmp_path, "{}", maker_model="")
    assert agent.execute_checker_step() is False  # the warm path always knows its maker; an empty one is refused
    assert calls["claim"] == [] and calls["meta"] == []


def test_real_audits_move_the_registry_once_and_a_rollback_switches_routes_off(tmp_path: Path) -> None:
    agent, _calls = _checker_rig(tmp_path, "{}")
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    decisions = state / "decisions.jsonl"
    routes = state / "routes.json"
    routes.write_text(json.dumps({"active": True, "routes": {"t": {}}}), encoding="utf-8")
    decisions.write_text(
        "\n".join(json.dumps({"audit_pass": x}) for x in [True, None, True, True, True]) + "\n", encoding="utf-8"
    )
    cand = agent.canary_registry.candidates["muse_glimmer_30b_orchestrator_v1"]
    agent.canary_registry.evaluate_held_out_promotion("muse_glimmer_30b_orchestrator_v1")
    before = cand.rollout_share
    assert agent.ingest_decider_audits() == 0  # the first run starts from now
    (state / "warm-decider-audit-cursor.json").write_text(json.dumps({"rows_read": 0}), encoding="utf-8")
    assert agent.ingest_decider_audits() == 4  # the audit that couldn't run isn't counted
    assert cand.rollout_share > before  # stepped up on four passes
    assert agent.ingest_decider_audits() == 0  # never counted twice
    assert json.loads(routes.read_text(encoding="utf-8"))["active"] is True
    with decisions.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps({"audit_pass": False}) for _ in range(4)) + "\n")
    agent.ingest_decider_audits()
    assert cand.status == "rolled_back" and cand.rollout_share == 0.0
    assert json.loads(routes.read_text(encoding="utf-8"))["active"] is False


def test_a_no_key_maker_with_no_stated_model_is_recorded_as_exactly_that(tmp_path: Path) -> None:
    agent, calls = _checker_rig(tmp_path, json.dumps({"verdict": "CONFIRMED", "quality_milli": 800, "summary": "fine"}), maker_model="muse-spark-1.3")
    target = {
        "object_key": "warm_artifact_t1",
        "worker_uuid": "u_elsewhere",
        "producer_agent": "bot",
        "source_task_id": "src1",
        "payload": {"producer_lineage": {"model_id": "made-up-claim"}},
    }
    assert agent.check_target(target, model_not_stated=True) is True
    assert calls["submit"][0]["evaluations"][0]["rationale"].startswith("The maker's model isn't known")
    assert not (tmp_path / "state" / "warm-training-traces.jsonl").exists()  # never training data
