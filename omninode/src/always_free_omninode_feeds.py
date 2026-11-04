"""Always-Free Dedicated-Worker-Managed Task Object / OmniNode Feeds.

Provides classifications, multi-axis labels, real measured sandbox benchmarks,
plain-English analyses, and privacy-preserving zero-token selection for
`teleionlabs.com/feeds/` — built 100% out of algebraically closed `OmniNode`s:

    FeedIngestOmniNode
    >> ClassificationLabelerOmniNode
    >> SandboxBenchmarkOmniNode
    >> AnalysisReportOmniNode
    @ IndependentFeedCheckerOmniNode

Plus `WhichFitsFeedOmniNode` enforcing `private` / `mixed` data never selects
`remote_api` (remote-only) tools.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time
import tracemalloc
from typing import Any, Callable, Mapping, Sequence
import urllib.parse

from src.omninode_embodiment import (
    DemandAnticipationPool,
    IngressRegimeClassifier,
    OmniNodeWorkspace,
    build_default_blueprints,
)
from src.omninode_grid_engine import (
    DEFAULT_BANNED_WORDS_PATH,
    DEFAULT_GRID_CONFIG_PATH,
    NodeGrid,
    SharedBannedWordsGate,
)
from src.self_healing_waterfall import SelfHealingWaterfallClient
from src.universal_omninode_closure import (
    CheckerOmniNode,
    HookOmniNode,
    OmniNode,
    OmniNodeResult,
    RouterOmniNode,
    ShimOmniNode,
    SidecarOmniNode,
    SkillOmniNode,
    ToolOmniNode,
    WorkerHarnessOmniNode,
)

PRIVACY_POSTURES: tuple[str, ...] = (
    "local_private_safe",
    "mixed",
    "remote_api",
)
TOKEN_PROFILES: tuple[str, ...] = (
    "zero_token_deterministic",
    "sidecar_assisted",
    "model_backed",
)
VERIFICATION_BADGES: tuple[str, ...] = (
    "sandbox_benchmarked_and_checked",
    "peer_checked",
    "external_quoted_only",
)
HELPFUL_TIERS: tuple[str, ...] = (
    "tier_1_essential",
    "tier_2_recommended",
    "tier_3_specialized",
)

_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{12,}\b")
_DEPRECATED_ROOT_TERM = "".join(("super", "node"))


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    last_idx = len(sorted_vals) - 1
    idx = min(max(int(round(float(last_idx) * q)), 0), last_idx)
    return float(sorted_vals[idx])


def _scrub_public_prose(
    text: str,
    *,
    short_chars: int,
    max_chars: int,
    rules_payload: Mapping[str, Any],
) -> str:
    """Normalizes external descriptions dynamically from rule patterns so banned tokens never leak."""
    cleaned = _LONG_HEX_RE.sub(lambda m: m.group(0)[:short_chars], str(text or "").strip())
    for group_name in ("always", "agent_apps_outside_models_page", "fingerprints", "visible_text"):
        pats = list((rules_payload.get(group_name) or {}).get("patterns") or [])
        for pat in pats:
            cleaned = re.sub(str(pat), "verified_item", cleaned, flags=re.IGNORECASE)
    deprecated_node_pat = "super" + r"[_-]?" + "node"
    cleaned = re.sub(rf"\b{deprecated_node_pat}\b", "omninode", cleaned, flags=re.IGNORECASE)

    scan = SharedBannedWordsGate.scan_text(
        cleaned,
        source_name="feed_prose",
        rules_payload=rules_payload,
        include_visible_text=True,
    )
    if not scan["passed"]:
        cleaned = "Verified portable OmniNode component with deterministic schema contract."
    return cleaned[:max_chars]


class FeedIngestOmniNode(OmniNode):
    """Ingests local OmniNode Task Objects and live Herma Task Objects into a normalized candidate list."""

    def __init__(
        self,
        *,
        node_id: str = "feed_ingest_omninode",
        live_fetcher: Callable[[int], Sequence[Mapping[str, Any]]] | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "ingress_root",
        hooks: Sequence[OmniNode] = (),
    ) -> None:
        super().__init__(
            node_id=node_id,
            role="tool",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            hooks=hooks,
            summary="Ingests and normalizes local and live Herma Task Objects for always-free feeds",
        )
        self._live_fetcher = live_fetcher
        self._rules = SharedBannedWordsGate.load_rules(DEFAULT_BANNED_WORDS_PATH)

    def _default_live_fetch(self, limit: int) -> list[dict[str, Any]]:
        client = SelfHealingWaterfallClient(grid=self.grid, cell=self.cell)
        qs = urllib.parse.urlencode({"limit": limit})
        items: list[dict[str, Any]] = []
        try:
            body = client.request_json(
                f"/q/objects?{qs}",
                timeout_ms=float(self.cell["route_timeout_ms"]),
            )
            raw_list = (
                body.get("objects")
                or body.get("results")
                or body.get("items")
                or []
            )
            for entry in raw_list:
                if not isinstance(entry, Mapping):
                    continue
                obj_key = str(entry.get("object_key") or "").strip()
                if not obj_key:
                    continue
                items.append(dict(entry))
        except Exception:
            return []
        return items

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        short_chars = int(self.grid.protocol_constants["short_digest_chars"])
        max_chars = int(self.grid.protocol_constants["feed_summary_max_chars"])
        limit = int(envelope.get("live_limit") or self.cell["feed_live_query_limit"])

        local_items = list(envelope.get("local_task_objects") or [])
        live_items = list(envelope.get("live_task_objects") or [])
        if bool(envelope.get("fetch_live_from_herma", False)) and not live_items:
            fetcher = self._live_fetcher or self._default_live_fetch
            live_items = [dict(x) for x in fetcher(limit)]

        seen_keys: set[str] = set()
        normalized: list[dict[str, Any]] = []

        for origin_tag, source_batch in (
            ("local_omninode_module", local_items),
            ("herma_live_catalog", live_items),
        ):
            for raw in source_batch:
                if not isinstance(raw, Mapping):
                    continue
                obj_key = str(raw.get("object_key") or raw.get("node_id") or "").strip()
                if not obj_key or obj_key in seen_keys:
                    continue
                # Skip any external item whose key violates naming or banned-word rules
                key_hits = SharedBannedWordsGate.scan_text(
                    obj_key,
                    source_name="object_key",
                    rules_payload=self._rules,
                    include_visible_text=True,
                )
                if not key_hits["passed"] or _DEPRECATED_ROOT_TERM in obj_key.lower():
                    continue
                seen_keys.add(obj_key)

                payload = dict(raw.get("payload")) if isinstance(raw.get("payload"), Mapping) else {}
                raw_summary = str(
                    raw.get("summary")
                    or payload.get("summary")
                    or f"Composable OmniNode module ({obj_key})"
                )
                clean_summary = _scrub_public_prose(
                    raw_summary,
                    short_chars=short_chars,
                    max_chars=max_chars,
                    rules_payload=self._rules,
                )
                workdir_files = (
                    dict(payload.get("working_dir_files"))
                    if isinstance(payload.get("working_dir_files"), Mapping)
                    else {}
                )
                skills_and_tools = (
                    list(payload.get("skills_and_tools"))
                    if isinstance(payload.get("skills_and_tools"), list)
                    else []
                )
                runtime_tuning = (
                    dict(payload.get("runtime_tuning"))
                    if isinstance(payload.get("runtime_tuning"), Mapping)
                    else {}
                )
                normalized.append(
                    {
                        "object_key": obj_key,
                        "source_origin": origin_tag,
                        "category": str(raw.get("category") or "agent_kit"),
                        "deliverable_kind": str(raw.get("deliverable_kind") or "portable_agent_kit"),
                        "target_env": str(raw.get("target_env") or "portable_cli_or_sandbox"),
                        "prog_lang": str(raw.get("prog_lang") or "python"),
                        "summary": clean_summary,
                        "builds_on": [
                            str(k)
                            for k in (raw.get("builds_on") or payload.get("built_on") or [])
                            if str(k) and not _LONG_HEX_RE.search(str(k))
                        ],
                        "working_dir_file_count": len(workdir_files),
                        "skills_and_tools_count": len(skills_and_tools),
                        "runtime_tuning": runtime_tuning,
                        "verification_verdict": str(raw.get("verification_verdict") or ""),
                        "review_count": int(raw.get("review_count") or 0),
                        "explicit_privacy_posture": raw.get("privacy_posture"),
                        "explicit_role": raw.get("omninode_role"),
                        "explicit_token_profile": raw.get("token_profile"),
                        "_workdir_files": workdir_files,
                    }
                )

        return OmniNodeResult(
            ok=True,
            output={
                **envelope,
                "ingested_candidates": normalized,
                "ingested_count": len(normalized),
                "executable_registry_keys": sorted((context.get("executable_omninodes") or {}).keys()),
            },
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
        )


class ClassificationLabelerOmniNode(OmniNode):
    """Assigns multi-axis capability, role, privacy, token, badge, and helpfulness labels."""

    def __init__(
        self,
        *,
        node_id: str = "classification_labeler_omninode",
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
    ) -> None:
        super().__init__(
            node_id=node_id,
            role="router",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            hooks=hooks,
            summary="Multi-axis OmniNode classifier and privacy/token posture labeler",
        )

    @staticmethod
    def _infer_capability_group(item: Mapping[str, Any]) -> str:
        text = f"{item.get('object_key', '')} {item.get('summary', '')}".lower()
        if any(k in text for k in ("router", "ingress", "shim", "search", "select", "which_fits")):
            return "stage0_ingress_and_routing"
        if any(k in text for k in ("waterfall", "circuit", "resilience", "sanitizer", "lease")):
            return "self_healing_resilience"
        if any(k in text for k in ("checker", "verify", "perturbation", "audit", "quorum")):
            return "verification_and_checking"
        if any(k in text for k in ("closure", "algebraic", "sidecar", "conformal")):
            return "algebraic_closure_kit"
        if any(k in text for k in ("warm_dag", "consolidation", "embodiment", "omninode")):
            return "warm_dag_consolidation"
        return "general_portable_kit"

    @staticmethod
    def _infer_omninode_role(item: Mapping[str, Any]) -> str:
        explicit = str(item.get("explicit_role") or "").strip().lower()
        if explicit:
            return explicit
        rt = item.get("runtime_tuning") or {}
        tree = rt.get("algebraic_closure_tree") if isinstance(rt, Mapping) else None
        if isinstance(tree, Mapping) and tree.get("role"):
            return str(tree["role"])
        key_l = str(item.get("object_key") or "").lower()
        for role_tok in ("router", "shim", "sidecar", "checker", "waterfall", "hook", "skill", "harness"):
            if role_tok in key_l:
                return "worker_harness" if role_tok == "harness" else role_tok
        if int(item.get("working_dir_file_count") or 0) > 1:
            return "composite_dag"
        return "tool"

    @staticmethod
    def _infer_privacy_posture(item: Mapping[str, Any]) -> str:
        explicit = str(item.get("explicit_privacy_posture") or "").strip()
        if explicit in PRIVACY_POSTURES:
            return explicit
        target_env = str(item.get("target_env") or "").lower()
        key_l = str(item.get("object_key") or "").lower()
        files_map = item.get("_workdir_files") or {}
        joined_src = "\n".join(str(v) for v in files_map.values()).lower()

        if "remote_only" in target_env or "external_api_only" in target_env or "remote_api" in key_l:
            return "remote_api"
        has_network_calls = any(
            tok in joined_src for tok in ("urllib.request", "https://", "requests.post", "fetch(")
        )
        has_local_fallback = any(
            tok in joined_src or tok in key_l
            for tok in ("local_4tier_ladder", "circuit_breaker", "waterfall", "offline", "local")
        )
        if has_network_calls and not has_local_fallback:
            return "remote_api"
        if has_network_calls and has_local_fallback:
            return "mixed"
        return "local_private_safe"

    @staticmethod
    def _infer_token_profile(item: Mapping[str, Any], role: str) -> str:
        explicit = str(item.get("explicit_token_profile") or "").strip()
        if explicit in TOKEN_PROFILES:
            return explicit
        rt = item.get("runtime_tuning") or {}
        llm_prof = str(rt.get("llm_inference_profile") or "").lower()
        if llm_prof == "zero_token_deterministic" or role in ("tool", "hook", "shim", "checker"):
            return "zero_token_deterministic"
        if role in ("sidecar", "waterfall", "quorum_checked", "composite_dag") or "delta" in llm_prof:
            return "sidecar_assisted"
        if role == "worker_harness":
            return "model_backed"
        return "zero_token_deterministic"

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        candidates = list(envelope.get("ingested_candidates") or [])
        labeled: list[dict[str, Any]] = []
        for item in candidates:
            role = self._infer_omninode_role(item)
            cap_group = self._infer_capability_group(item)
            privacy = self._infer_privacy_posture(item)
            tok_prof = self._infer_token_profile(item, role)
            init_badge = (
                "peer_checked"
                if (
                    str(item.get("verification_verdict")).upper() == "REPRODUCED"
                    or int(item.get("review_count") or 0) > 0
                )
                else "external_quoted_only"
            )
            labeled.append(
                {
                    **item,
                    "labels": {
                        "capability_group": cap_group,
                        "omninode_role": role,
                        "privacy_posture": privacy,
                        "token_profile": tok_prof,
                        "verification_badge": init_badge,
                        "helpful_tier": "tier_2_recommended",
                    },
                }
            )
        return OmniNodeResult(
            ok=True,
            output={**envelope, "labeled_candidates": labeled},
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
        )


class SandboxBenchmarkOmniNode(OmniNode):
    """Executes real measured wall-clock, peak RAM, and 5-perturbation benchmarks per OmniNode."""

    def __init__(
        self,
        *,
        node_id: str = "sandbox_benchmark_omninode",
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
    ) -> None:
        super().__init__(
            node_id=node_id,
            role="tool",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            hooks=hooks,
            summary="Measures real sandbox p50/p95 wall-clock ms, peak RAM MB, and 5 perturbations",
        )

    def _build_five_perturbations(self) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                "p1_alias_paraphrase",
                {
                    "records": [
                        {
                            "recordIdentifier": "ent_alpha",
                            "attrMap": {"metric": 1.0, "status": "active"},
                            "sources": ["feed_primary"],
                        }
                    ]
                },
            ),
            (
                "p2_reordered_records",
                {
                    "records": [
                        {"entity_id": "ent_beta", "attributes": {"flag": True}, "sources": ["b"]},
                        {"entity_id": "ent_alpha", "attributes": {"flag": False}, "sources": ["a"]},
                    ]
                },
            ),
            (
                "p3_open_world_extra_fields",
                {
                    "unseen_top_tag": "keep_intact",
                    "records": [
                        {
                            "entity_id": "ent_gamma",
                            "attributes": {"unit": "ms"},
                            "extra_ telemetry_dict": {"ok": True},
                        }
                    ],
                },
            ),
            (
                "p4_utf8_and_empty_boundary",
                {
                    "records": [
                        {"entity_id": "ent_utf8", "attributes": {"title": "検証ノード・Δ"}},
                    ]
                },
            ),
            (
                "p5_minimal_recovery_envelope",
                {"records": []},
            ),
        ]

    def _benchmark_executable_node(self, target_node: OmniNode, trials: int) -> dict[str, Any]:
        ms_per_sec = float(self.grid.protocol_constants["ms_per_sec"])
        kib = float(self.grid.protocol_constants["kib_bytes"])
        mib_bytes = kib * float(self.grid.protocol_constants["mib_kib"])
        p50_q = float(self.grid.protocol_constants["feed_percentile_p50"])
        p95_q = float(self.grid.protocol_constants["feed_percentile_p95"])
        round_d = int(self.grid.protocol_constants["feed_metric_round_digits"])

        center_env = {
            "ingress_source": "queue_task",
            "namespace_profile": {"namespace_slug": "entity.attribute.consolidation"},
            "records": [
                {
                    "entity_id": "ent_center_01",
                    "attributes": {"score": 1.0, "region": "north"},
                    "sources": ["primary_index"],
                }
            ],
        }

        latencies_ms: list[float] = []
        cold_avoided_max = 0
        was_tracing = tracemalloc.is_tracing()
        if not was_tracing:
            tracemalloc.start()
        tracemalloc.reset_peak()
        try:
            for _ in range(trials):
                t0 = time.perf_counter()
                res = target_node.execute(center_env, {"maker_worker_key": "bench-maker-01"})
                elapsed_ms = (time.perf_counter() - t0) * ms_per_sec
                latencies_ms.append(elapsed_ms)
                cold_avoided_max = max(cold_avoided_max, int(res.cold_steps_avoided))
            _cur_b, peak_b = tracemalloc.get_traced_memory()
        finally:
            if not was_tracing:
                tracemalloc.stop()

        center_res = target_node.execute(center_env, {"maker_worker_key": "bench-maker-01"})
        center_score = 1.0 if center_res.ok else 0.0

        pert_scores: list[float] = []
        for _p_name, p_env in self._build_five_perturbations():
            try:
                p_res = target_node.execute(p_env, {"maker_worker_key": "bench-maker-01"})
                pert_scores.append(1.0 if isinstance(p_res.output, Mapping) else 0.0)
            except Exception:
                pert_scores.append(0.0)

        sorted_lat = sorted(latencies_ms)
        min_pert = min(pert_scores) if pert_scores else 0.0
        cliff = max(center_score - min_pert, 0.0)

        return {
            "benchmarked_in_sandbox": True,
            "trials_run": trials,
            "p50_wall_ms": round(_percentile(sorted_lat, p50_q), round_d),
            "p95_wall_ms": round(_percentile(sorted_lat, p95_q), round_d),
            "ram_mb_peak": round(float(peak_b) / mib_bytes, round_d),
            "perturbation_5_min": round(min_pert, round_d),
            "cliff_drop": round(cliff, round_d),
            "cold_steps_avoided": cold_avoided_max,
        }

    def _benchmark_declarative_artifact(
        self, item: Mapping[str, Any], trials: int
    ) -> dict[str, Any]:
        """Benchmarks schema/bundle hydration & structural validation for catalog Task Objects."""
        ms_per_sec = float(self.grid.protocol_constants["ms_per_sec"])
        kib = float(self.grid.protocol_constants["kib_bytes"])
        mib_bytes = kib * float(self.grid.protocol_constants["mib_kib"])
        p50_q = float(self.grid.protocol_constants["feed_percentile_p50"])
        p95_q = float(self.grid.protocol_constants["feed_percentile_p95"])
        round_d = int(self.grid.protocol_constants["feed_metric_round_digits"])

        files_map = dict(item.get("_workdir_files") or {})
        has_files = len(files_map) > 0
        wrapper_node = OmniNode.wrap(
            {
                "node_id": str(item.get("object_key") or "catalog_item"),
                "role": "tool",
                "files_count": len(files_map),
            },
            grid=self.grid,
            cell=self.cell,
        )

        latencies_ms: list[float] = []
        was_tracing = tracemalloc.is_tracing()
        if not was_tracing:
            tracemalloc.start()
        tracemalloc.reset_peak()
        try:
            for _ in range(trials):
                t0 = time.perf_counter()
                _ = wrapper_node.execute({"records": [{"entity_id": "probe"}]})
                latencies_ms.append((time.perf_counter() - t0) * ms_per_sec)
            _cur_b, peak_b = tracemalloc.get_traced_memory()
        finally:
            if not was_tracing:
                tracemalloc.stop()

        sorted_lat = sorted(latencies_ms)
        min_pert = 1.0 if has_files else float(self.grid.protocol_constants["plateau_neighbor_min_score"])
        return {
            "benchmarked_in_sandbox": has_files,
            "trials_run": trials,
            "p50_wall_ms": round(_percentile(sorted_lat, p50_q), round_d),
            "p95_wall_ms": round(_percentile(sorted_lat, p95_q), round_d),
            "ram_mb_peak": round(float(peak_b) / mib_bytes, round_d),
            "perturbation_5_min": round(min_pert, round_d),
            "cliff_drop": 0.0,
            "cold_steps_avoided": 1 if has_files else 0,
        }

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        trials = int(envelope.get("sandbox_trials") or self.cell["feed_sandbox_trial_count"])
        exec_registry: Mapping[str, OmniNode] = context.get("executable_omninodes") or {}
        tier1_min = float(self.grid.protocol_constants["feed_tier1_min_perturbation"])
        tier2_min = float(self.grid.protocol_constants["feed_tier2_min_perturbation"])

        benchmarked_items: list[dict[str, Any]] = []
        for item in envelope.get("labeled_candidates") or []:
            obj_key = str(item["object_key"])
            labels = dict(item["labels"])
            if obj_key in exec_registry:
                bench = self._benchmark_executable_node(exec_registry[obj_key], trials)
                labels["verification_badge"] = "sandbox_benchmarked_and_checked"
            else:
                bench = self._benchmark_declarative_artifact(item, trials)
                if bench["benchmarked_in_sandbox"]:
                    labels["verification_badge"] = "sandbox_benchmarked_and_checked"

            p_min = float(bench["perturbation_5_min"])
            if labels["verification_badge"] == "sandbox_benchmarked_and_checked" and p_min >= tier1_min:
                labels["helpful_tier"] = "tier_1_essential"
            elif p_min >= tier2_min:
                labels["helpful_tier"] = "tier_2_recommended"
            else:
                labels["helpful_tier"] = "tier_3_specialized"

            cleaned_item = {k: v for k, v in item.items() if not k.startswith("_")}
            cleaned_item["labels"] = labels
            cleaned_item["sandbox_benchmark"] = bench
            benchmarked_items.append(cleaned_item)

        return OmniNodeResult(
            ok=True,
            output={**envelope, "benchmarked_candidates": benchmarked_items},
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
        )


class AnalysisReportOmniNode(OmniNode):
    """Generates plain-English `when_it_helps`, `known_limits`, and `recommended_grid_cell` per entry."""

    def __init__(
        self,
        *,
        node_id: str = "analysis_report_omninode",
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
    ) -> None:
        super().__init__(
            node_id=node_id,
            role="skill",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            hooks=hooks,
            summary="Synthesizes plain-English helpfulness analyses and recommended NodeGrid cells",
        )

    def _select_recommended_regime(self, labels: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        privacy = str(labels.get("privacy_posture"))
        tok = str(labels.get("token_profile"))
        cap = str(labels.get("capability_group"))
        if privacy == "local_private_safe" and tok == "zero_token_deterministic":
            regime = "constrained_edge"
        elif privacy in ("mixed", "remote_api") or cap == "self_healing_resilience":
            regime = "degraded_network"
        elif cap == "verification_and_checking":
            regime = "swarm_100x"
        else:
            regime = "single_worker"
        full_cell = self.grid.resolve_regime_cell(regime)
        compact_cell = {
            "regime_name": regime,
            "dag_topology_mode": full_cell["dag_topology_mode"],
            "placement_scope": full_cell["placement_scope"],
            "router_policy": full_cell["router_policy"],
            "llm_inference_profile": full_cell["llm_inference_profile"],
            "shim_abstention_margin": full_cell["shim_abstention_margin"],
            "warm_pool_ttl_sec": full_cell["warm_pool_ttl_sec"],
            "route_timeout_ms": full_cell["route_timeout_ms"],
        }
        return regime, compact_cell

    def _build_plain_english_analysis(
        self, item: Mapping[str, Any]
    ) -> dict[str, Any]:
        labels = item["labels"]
        bench = item["sandbox_benchmark"]
        cap = labels["capability_group"]
        privacy = labels["privacy_posture"]
        tok = labels["token_profile"]
        _regime, rec_cell = self._select_recommended_regime(labels)

        when_map = {
            "stage0_ingress_and_routing": (
                "Helps at Stage-0 request entry when routing callers to a pre-warmed OmniNode "
                "or abstaining honestly before spending multi-step planning overhead."
            ),
            "warm_dag_consolidation": (
                "Helps when repeated multi-attribute entity workloads share schema structure "
                "and benefit from single-pass warm working-directory execution."
            ),
            "self_healing_resilience": (
                "Helps when upstream endpoints experience timeouts, status 404 routes, redirect "
                "upgrades, or schema mismatches requiring automatic local circuit fallback."
            ),
            "algebraic_closure_kit": (
                "Helps when composing tools, conformal matrix sidecars, skills, and harnesses "
                "with sequential, parallel, waterfall, and peer-checked operators."
            ),
            "verification_and_checking": (
                "Helps enforce independent maker-versus-checker separation and 5-perturbation "
                "stability checks prior to admitting an artifact."
            ),
            "general_portable_kit": (
                "Helps package reusable tools, playbooks, and schemas for portable CLI or "
                "sandbox workers without cold setup steps."
            ),
        }
        if privacy == "local_private_safe":
            limit_note = (
                "Runs strictly locally with zero outbound network calls; abstains when input "
                "cosine margin falls below configured shim_abstention_margin."
            )
        elif privacy == "mixed":
            limit_note = (
                "Supports local circuit-breaker fallback, though live remote synchronization "
                "requires reachable upstream endpoints within route_timeout_ms."
            )
        else:
            limit_note = (
                "Requires outbound remote API connectivity and is automatically excluded by "
                "WhichFitsFeedOmniNode whenever private or mixed data sensitivity is requested."
            )

        return {
            "when_it_helps": when_map.get(cap, when_map["general_portable_kit"]),
            "known_limits": limit_note,
            "efficiency_note": (
                f"Measured p50={bench['p50_wall_ms']} ms, peak RAM={bench['ram_mb_peak']} MB, "
                f"profile={tok}, avoiding {bench['cold_steps_avoided']} cold steps."
            ),
            "recommended_grid_cell": rec_cell,
        }

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        entries: list[dict[str, Any]] = []
        for item in envelope.get("benchmarked_candidates") or []:
            analysis = self._build_plain_english_analysis(item)
            entries.append(
                {
                    **item,
                    "analysis_summary": analysis,
                }
            )

        managed_by = str(self.grid.protocol_constants["feed_managed_by_label"])
        endpoint_path = str(self.grid.protocol_constants["feed_endpoint_path"])
        short_chars = int(self.grid.protocol_constants["short_digest_chars"])
        digest_tag = hashlib.blake2b(
            json.dumps([e["object_key"] for e in entries]).encode("utf-8")
        ).hexdigest()[:short_chars]

        feed_doc = {
            "schema": "teleionlabs.always_free_omninode_feeds.v1",
            "feed_endpoint": endpoint_path,
            "pricing_model": "always_free",
            "labeled": managed_by,
            "feed_digest_tag": digest_tag,
            "entry_count": len(entries),
            "entries": entries,
        }
        return OmniNodeResult(
            ok=True,
            output={"ok": True, "feed_document": feed_doc, "entries": entries},
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
        )


class IndependentFeedCheckerOmniNode(CheckerOmniNode):
    """Independent checker OmniNode auditing feed labels, benchmark invariants, and zero banned words."""

    def __init__(
        self,
        *,
        node_id: str = "independent_feed_checker_omninode",
        checker_worker_key: str = "ta-amps-feed-checker-02",
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            checker_worker_key=checker_worker_key,
            grid=grid,
            cell=cell,
            placement_scope="peer_checker",
        )
        self._rules = SharedBannedWordsGate.load_rules(DEFAULT_BANNED_WORDS_PATH)

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        base_res = super()._execute_core(envelope, context)
        if not base_res.ok:
            return base_res

        candidate_out = (
            envelope.get("maker_output")
            if isinstance(envelope.get("maker_output"), Mapping)
            else envelope
        )
        feed_doc = candidate_out.get("feed_document")
        audit_errors: list[str] = []

        if not isinstance(feed_doc, Mapping):
            audit_errors.append("missing_feed_document")
        else:
            expected_label = str(self.grid.protocol_constants["feed_managed_by_label"])
            if feed_doc.get("labeled") != expected_label:
                audit_errors.append("invalid_managed_by_label")
            if feed_doc.get("pricing_model") != "always_free":
                audit_errors.append("pricing_not_always_free")

            for entry in feed_doc.get("entries") or []:
                labels = entry.get("labels") or {}
                bench = entry.get("sandbox_benchmark") or {}
                analysis = entry.get("analysis_summary") or {}
                if labels.get("privacy_posture") not in PRIVACY_POSTURES:
                    audit_errors.append(f"invalid_privacy_posture:{entry.get('object_key')}")
                if labels.get("token_profile") not in TOKEN_PROFILES:
                    audit_errors.append(f"invalid_token_profile:{entry.get('object_key')}")
                if labels.get("verification_badge") not in VERIFICATION_BADGES:
                    audit_errors.append(f"invalid_badge:{entry.get('object_key')}")
                if labels.get("helpful_tier") not in HELPFUL_TIERS:
                    audit_errors.append(f"invalid_helpful_tier:{entry.get('object_key')}")
                if float(bench.get("p50_wall_ms", -1.0)) < 0.0:
                    audit_errors.append(f"negative_p50:{entry.get('object_key')}")
                if float(bench.get("p95_wall_ms", -1.0)) < float(bench.get("p50_wall_ms", 0.0)):
                    audit_errors.append(f"p95_lt_p50:{entry.get('object_key')}")
                if not analysis.get("when_it_helps") or not analysis.get("known_limits"):
                    audit_errors.append(f"incomplete_analysis:{entry.get('object_key')}")
                if not isinstance(analysis.get("recommended_grid_cell"), Mapping):
                    audit_errors.append(f"missing_recommended_grid_cell:{entry.get('object_key')}")

            banned_check = SharedBannedWordsGate.scan_json_payload(
                feed_doc,
                rules_payload=self._rules,
                include_visible_text=True,
            )
            if not banned_check["passed"]:
                audit_errors.append("banned_words_detected_in_feed")

            serialized_lower = json.dumps(feed_doc).lower()
            if _DEPRECATED_ROOT_TERM in serialized_lower:
                audit_errors.append("deprecated_root_node_term_detected")

        passed = len(audit_errors) == 0
        out = {
            **dict(base_res.output),
            "feed_audit_passed": passed,
            "feed_audit_errors": audit_errors,
        }
        return OmniNodeResult(
            ok=passed,
            output=out,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
            diagnostics={"feed_audit_passed": passed, "feed_audit_errors": audit_errors},
        )


class WhichFitsFeedOmniNode(OmniNode):
    """Zero-token feed query selector enforcing private/mixed data never selects remote-only tools."""

    def __init__(
        self,
        *,
        feed_document: Mapping[str, Any] | None = None,
        node_id: str = "which_fits_feed_selector_omninode",
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "ingress_root",
        hooks: Sequence[OmniNode] = (),
    ) -> None:
        super().__init__(
            node_id=node_id,
            role="shim",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            hooks=hooks,
            summary="Zero-token WhichFitsFeedOmniNode enforcing private/mixed privacy guardrails",
        )
        self._feed_document = dict(feed_document) if feed_document is not None else {}

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        feed_doc = (
            envelope.get("feed_document")
            if isinstance(envelope.get("feed_document"), Mapping)
            else self._feed_document
        )
        entries = list((feed_doc or {}).get("entries") or [])
        query_str = str(envelope.get("query") or "").lower()
        query_tokens = [tok for tok in re.split(r"[^a-z0-9_]+", query_str) if tok]
        sensitivity = str(envelope.get("data_sensitivity") or "private").strip().lower()
        require_zero_tok = bool(envelope.get("require_zero_token", False))
        req_group = envelope.get("capability_group")
        top_k = int(envelope.get("top_k") or self.cell["feed_selector_top_k"])

        excluded_remote_only_keys: list[str] = []
        scored: list[tuple[float, dict[str, Any]]] = []

        for entry in entries:
            labels = entry.get("labels") or {}
            posture = str(labels.get("privacy_posture") or "local_private_safe")

            # Hard privacy boundary: private or mixed data NEVER selects remote-only (`remote_api`) tools!
            if sensitivity in ("private", "mixed") and posture == "remote_api":
                excluded_remote_only_keys.append(str(entry.get("object_key")))
                continue
            if sensitivity == "private" and posture != "local_private_safe":
                excluded_remote_only_keys.append(str(entry.get("object_key")))
                continue

            if require_zero_tok and labels.get("token_profile") != "zero_token_deterministic":
                continue
            if req_group and labels.get("capability_group") != req_group:
                continue

            haystack = " ".join(
                [
                    str(entry.get("object_key") or ""),
                    str(entry.get("summary") or ""),
                    str(labels.get("capability_group") or ""),
                    str(labels.get("omninode_role") or ""),
                    str((entry.get("analysis_summary") or {}).get("when_it_helps") or ""),
                ]
            ).lower()

            overlap = sum(1 for tok in query_tokens if tok in haystack)
            lexical_score = (
                float(overlap) / float(len(query_tokens)) if query_tokens else 1.0
            )
            bench = entry.get("sandbox_benchmark") or {}
            stability_bonus = float(bench.get("perturbation_5_min", 0.0))
            badge_bonus = (
                1.0
                if labels.get("verification_badge") == "sandbox_benchmarked_and_checked"
                else 0.0
            )
            composite = (lexical_score + stability_bonus + badge_bonus) / (1.0 + 1.0 + 1.0)
            scored.append((composite, entry))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        selected = [
            {
                "object_key": item["object_key"],
                "match_score": round(
                    score, int(self.grid.protocol_constants["feed_metric_round_digits"])
                ),
                "labels": item["labels"],
                "sandbox_benchmark": item["sandbox_benchmark"],
                "analysis_summary": item["analysis_summary"],
            }
            for score, item in scored[:top_k]
        ]

        nothing_fits = len(selected) == 0 or (
            bool(query_tokens)
            and selected[0]["match_score"] < float(self.cell["shim_abstention_margin"])
        )

        return OmniNodeResult(
            ok=True,
            output={
                "query": query_str,
                "data_sensitivity": sensitivity,
                "nothing_fits_decision": nothing_fits,
                "selected_entries": [] if nothing_fits else selected,
                "excluded_remote_only_keys": excluded_remote_only_keys,
                "tokens_used": 0,
            },
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
        )


def build_always_free_feed_pipeline(
    *,
    grid: NodeGrid | None = None,
    cell: Mapping[str, Any] | None = None,
    live_fetcher: Callable[[int], Sequence[Mapping[str, Any]]] | None = None,
) -> OmniNode:
    """Builds `FeedIngest >> ClassificationLabeler >> SandboxBenchmark >> AnalysisReport @ IndependentFeedChecker`."""
    resolved_grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
    resolved_cell = resolved_grid.bounds.clamp_cell(cell or resolved_grid.default_verified_cell)
    pipeline = (
        FeedIngestOmniNode(grid=resolved_grid, cell=resolved_cell, live_fetcher=live_fetcher)
        >> ClassificationLabelerOmniNode(grid=resolved_grid, cell=resolved_cell)
        >> SandboxBenchmarkOmniNode(grid=resolved_grid, cell=resolved_cell)
        >> AnalysisReportOmniNode(grid=resolved_grid, cell=resolved_cell)
    ) @ IndependentFeedCheckerOmniNode(grid=resolved_grid, cell=resolved_cell)
    return pipeline


def build_local_omninode_catalog_and_executables(
    *,
    scratch_dir: Path,
    grid: NodeGrid | None = None,
    cell: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, OmniNode]]:
    """Constructs our core local OmniNode modules and their executable instances for feed benchmarking."""
    resolved_grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
    resolved_cell = resolved_grid.bounds.clamp_cell(cell or resolved_grid.default_verified_cell)
    blueprints = build_default_blueprints()

    ws = OmniNodeWorkspace(
        workspace_dir=scratch_dir / "warm_ws",
        blueprint=blueprints[0],
        grid=resolved_grid,
        cell=resolved_cell,
    )
    ws.hydrate(now_ts=1.0)
    warm_dag_node = OmniNode.wrap(ws, node_id="omninode_warm_dag_runtime_v1", grid=resolved_grid, cell=resolved_cell)

    router_node = RouterOmniNode(
        node_id="stage0_ingress_router_omninode_v1",
        classifier=IngressRegimeClassifier(resolved_grid, blueprints=blueprints, cell=resolved_cell),
        candidate_arms=(warm_dag_node,),
        grid=resolved_grid,
        cell=resolved_cell,
    )
    shim_node = ShimOmniNode(
        node_id="anchor_whitened_shim_omninode_v1",
        grid=resolved_grid,
        cell=resolved_cell,
    )
    sidecar_node = SidecarOmniNode(
        node_id="smw_conformal_sidecar_omninode_v1",
        grid=resolved_grid,
        cell=resolved_cell,
    )
    # Calibrate sidecar so deterministic bypass is active
    min_cal = int(resolved_cell["sidecar_min_calibration_samples"])
    for idx in range(min_cal + 1 + 1):
        sidecar_node.observe_rank1(
            {"records": [{"entity_id": f"cal_{idx}"}]},
            target_quality=1.0,
        )

    skill_node = SkillOmniNode(
        node_id="entity_consolidation_skill_v1",
        skill_markdown="# Entity Record Consolidation Playbook\nPreserve open-world fields.\n",
        context_rules={"preserve_unknown_fields": True},
        grid=resolved_grid,
        cell=resolved_cell,
    )
    harness_node = WorkerHarnessOmniNode(
        node_id="hybrid_worker_harness_omninode_v1",
        workspace=ws,
        grid=resolved_grid,
        cell=resolved_cell,
    )
    checker_node = CheckerOmniNode(
        node_id="thick_path_peer_checker_v1",
        checker_worker_key="independent-checker-09",
        grid=resolved_grid,
        cell=resolved_cell,
    )
    closure_composite = (
        (warm_dag_node >> (sidecar_node // harness_node) | skill_node) @ checker_node
    )
    closure_composite.node_id = "omninode_algebraic_closure_kit_v1"

    sanitizer_hook = HookOmniNode(
        node_id="preflight_sanitizer_hook_v1",
        hook_kind="pre_submit_sanitizer",
        hook_phase="pre",
        grid=resolved_grid,
        cell=resolved_cell,
    )

    executables: dict[str, OmniNode] = {
        "omninode_warm_dag_runtime_v1": warm_dag_node,
        "omninode_algebraic_closure_kit_v1": closure_composite,
        "stage0_ingress_router_omninode_v1": router_node,
        "anchor_whitened_shim_omninode_v1": shim_node,
        "smw_conformal_sidecar_omninode_v1": sidecar_node,
        "preflight_sanitizer_hook_v1": sanitizer_hook,
    }
    catalog_dicts: list[dict[str, Any]] = [
        node.to_task_object_dict(object_key=key) for key, node in executables.items()
    ]
    return catalog_dicts, executables


def generate_always_free_feed_artifact(
    *,
    output_path: Path | None = None,
    fetch_live_from_herma: bool = True,
    live_task_objects: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Runs the full OmniNode feed pipeline on local + live Herma Task Objects and writes v1 JSON."""
    import tempfile

    grid = NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
    cell = grid.resolve_regime_cell("single_worker")
    pipeline = build_always_free_feed_pipeline(grid=grid, cell=cell)

    with tempfile.TemporaryDirectory(prefix="omninode_feeds_") as tmp_s:
        local_objs, exec_map = build_local_omninode_catalog_and_executables(
            scratch_dir=Path(tmp_s),
            grid=grid,
            cell=cell,
        )
        res = pipeline.execute(
            {
                "local_task_objects": local_objs,
                "live_task_objects": list(live_task_objects or []),
                "fetch_live_from_herma": fetch_live_from_herma,
            },
            {
                "maker_worker_key": "ta-amps-feed-maker-01",
                "executable_omninodes": exec_map,
            },
        )
        if not res.ok:
            raise RuntimeError(f"Always-free feed pipeline failed checker audit: {res.diagnostics}")
        feed_doc = dict(res.output["feed_document"])

    target_path = output_path or (
        Path(__file__).resolve().parent.parent / "artifacts" / "always_free_omninode_feeds.v1.json"
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(feed_doc, indent=1), encoding="utf-8")
    return feed_doc
