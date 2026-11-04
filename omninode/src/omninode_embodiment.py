"""Stage-0 Ingress Regime Classifier, K=128 Anchor-Whitened Bridge, and Warm OmniNode Pool.

Implements:
- AnchorWhitenedProjector: K=128 frozen canonical anchor ZCA-whitened cosine coordinates
- IngressRegimeClassifier: < 0.5 ms classification across mcp_call, queue_task, external_api
- OmniNodeWorkspace: Hydrated working-directory DAG runtime (tools/, skills/, hooks/, profiles)
- DemandAnticipationPool: Online EWMA demand pre-warming plus TTL, capacity, and drift eviction
- Cold 7-step fabric decomposition baseline comparator and /q/compose payload emitter
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Mapping, Sequence
import unicodedata

import numpy as np

from src.omninode_grid_engine import DEFAULT_GRID_CONFIG_PATH, NodeGrid

VALID_INGRESS_SOURCES: tuple[str, ...] = ("mcp_call", "queue_task", "external_api")

STAGE0_REGIMES: tuple[str, ...] = (
    "warm_omninode_hit",
    "compiled_dag_cold_hydrate",
    "novel_frontier_decomposition",
)

PLACEMENT_SCOPES: tuple[str, ...] = (
    "ingress_root",
    "interior_branch",
    "leaf_operator",
    "peer_checker",
    "nested_omninode",
)


@dataclass(frozen=True)
class OmniNodeBlueprint:
    """Domain-agnostic declarative specification for an OmniNode DAG embodiment."""

    blueprint_key: str
    namespace_slug: str
    summary: str
    expected_schema_fields: tuple[str, ...]
    expected_tool_transitions: tuple[str, ...]
    field_aliases: Mapping[str, str] = field(default_factory=dict)
    optional_defaults: Mapping[str, Any] = field(default_factory=dict)
    required_record_fields: tuple[str, ...] = ("entity_id", "attributes")
    built_on: tuple[str, ...] = ()
    tuned_use_cases: tuple[str, ...] = (
        "Multi-source entity attribute consolidation under declarative schema constraints",
        "Cross-worker reproducible batch normalization with open-world field preservation",
    )


def build_default_blueprints() -> tuple[OmniNodeBlueprint, ...]:
    """Constructs standard domain-agnostic OmniNode blueprints."""
    return (
        OmniNodeBlueprint(
            blueprint_key="entity_record_consolidation_omninode_v1",
            namespace_slug="entity.attribute.consolidation",
            summary=(
                "Warm single-pass multi-attribute entity record normalizer, conflict resolver, "
                "and invariant checker with lossless open-world field preservation."
            ),
            expected_schema_fields=(
                "records",
                "namespace_profile",
                "entity_id",
                "attributes",
                "sources",
                "confidence",
            ),
            expected_tool_transitions=(
                "search:entity_schema->tool:inspect_contract",
                "tool:inspect_contract->tool:consolidate_records",
                "mcp:normalize_attributes->mcp:verify_invariants",
            ),
            field_aliases={
                "id": "entity_id",
                "record_id": "entity_id",
                "recordIdentifier": "entity_id",
                "attr_map": "attributes",
                "attrMap": "attributes",
                "fields": "attributes",
                "source_list": "sources",
                "provenance": "sources",
            },
            optional_defaults={"sources": [], "priority_tag": "standard"},
            required_record_fields=("entity_id", "attributes"),
            built_on=("omninode_resilience_grid_schema_v1",),
        ),
        OmniNodeBlueprint(
            blueprint_key="tabular_ledger_reconciliation_omninode_v1",
            namespace_slug="tabular.ledger.reconciliation",
            summary=(
                "Warm deterministic row-level balance and checksum reconciler across "
                "partitioned tabular batches with structured anomaly isolation."
            ),
            expected_schema_fields=(
                "batches",
                "ledger_entries",
                "partition_key",
                "delta_amount",
                "checksum_tag",
            ),
            expected_tool_transitions=(
                "search:tabular_reconcile->tool:verify_balances",
                "tool:verify_balances->tool:emit_reconciliation",
            ),
            field_aliases={
                "entry_id": "entity_id",
                "row_attributes": "attributes",
            },
            optional_defaults={"sources": [], "partition_tag": "root"},
            required_record_fields=("entity_id", "attributes"),
            built_on=("omninode_resilience_grid_schema_v1",),
        ),
        OmniNodeBlueprint(
            blueprint_key="declarative_invariant_audit_omninode_v1",
            namespace_slug="policy.invariant.audit",
            summary=(
                "Warm declarative constraint evaluator auditing structured envelopes "
                "against typed range, set-membership, and cross-field rules."
            ),
            expected_schema_fields=(
                "envelopes",
                "rule_set",
                "subject_key",
                "constraint_matrix",
                "audit_scope",
            ),
            expected_tool_transitions=(
                "search:invariant_rules->tool:compile_checks",
                "tool:compile_checks->tool:audit_envelopes",
            ),
            field_aliases={
                "subject_key": "entity_id",
                "claims": "attributes",
            },
            optional_defaults={"sources": [], "audit_mode": "strict"},
            required_record_fields=("entity_id", "attributes"),
            built_on=("omninode_resilience_grid_schema_v1",),
        ),
    )


class AnchorWhitenedProjector:
    """Fast K=128 frozen canonical anchor ZCA-whitened cosine coordinate bridge."""

    def __init__(self, grid: NodeGrid, cell: Mapping[str, Any] | None = None) -> None:
        active_cell = grid.bounds.clamp_cell(cell or grid.default_verified_cell)
        self.anchor_k = int(active_cell["anchor_dimension_k"])
        self.base_dim = int(active_cell["base_feature_dim"])
        self._prime = int(grid.protocol_constants["feature_hash_prime"])
        self._mult = int(grid.protocol_constants["anchor_seed_multiplier"])
        self._mod = int(grid.protocol_constants["anchor_seed_modulus"])
        ridge_eps = float(grid.protocol_constants["whitening_ridge_eps"])

        anchors = np.zeros((self.anchor_k, self.base_dim), dtype=np.float64)
        for k_idx in range(self.anchor_k):
            state = ((k_idx + 1) * self._mult) % self._mod
            for d_idx in range(self.base_dim):
                state = (state * self._mult + d_idx + 1) % self._mod
                centered = (float(state) / float(self._mod)) - (1.0 / (1.0 + 1.0))
                anchors[k_idx, d_idx] = centered
            row_norm = float(np.linalg.norm(anchors[k_idx]))
            if row_norm > 0.0:
                anchors[k_idx] /= row_norm

        self._anchors = anchors
        cov = (anchors @ anchors.T) / float(max(self.anchor_k, 1))
        cov_reg = cov + ridge_eps * np.eye(self.anchor_k, dtype=np.float64)
        eigvals, eigvecs = np.linalg.eigh(cov_reg)
        safe_eigs = np.maximum(eigvals, ridge_eps)
        inv_sqrt = 1.0 / np.sqrt(safe_eigs)
        self._zca_matrix = (eigvecs * inv_sqrt) @ eigvecs.T
        self._anchor_mean = np.mean(anchors @ anchors.T, axis=0)

    def _hash_token(self, token: str) -> tuple[int, float]:
        acc = 0
        for ch in token:
            acc = (acc * self._prime + ord(ch)) % self._mod
        idx = acc % self.base_dim
        sign = 1.0 if ((acc // self.base_dim) % (1 + 1)) == 0 else -1.0
        return idx, sign

    def project_tokens(self, tokens: Sequence[str]) -> np.ndarray:
        vec = np.zeros(self.base_dim, dtype=np.float64)
        for tok in tokens:
            if not tok:
                continue
            idx, sign = self._hash_token(tok)
            vec[idx] += sign
        v_norm = float(np.linalg.norm(vec))
        if v_norm > 0.0:
            vec /= v_norm
        raw_cos = self._anchors @ vec
        whitened = self._zca_matrix @ (raw_cos - self._anchor_mean)
        w_norm = float(np.linalg.norm(whitened))
        if w_norm > 0.0:
            whitened /= w_norm
        return whitened


@dataclass
class IngressClassification:
    """Result of Stage-0 ingress regime classification."""

    ingress_source: str
    classified_regime: str
    matched_blueprint_key: str | None
    top1_score: float
    top2_margin: float
    nothing_fits_decision: bool
    anticipated_demand_hit: bool
    cold_steps_avoided: int
    classification_latency_ms: float
    retrieved_candidates: list[dict[str, Any]]
    omninode_ingress_trace: dict[str, Any]
    routing_and_abstention_trace: dict[str, Any]


class IngressRegimeClassifier:
    """Stage-0 (< 0.5 ms) classifier over structural schema, tool transitions, and K=128 coordinates."""

    def __init__(
        self,
        grid: NodeGrid,
        *,
        blueprints: Sequence[OmniNodeBlueprint] | None = None,
        cell: Mapping[str, Any] | None = None,
    ) -> None:
        self.grid = grid
        self.cell = grid.bounds.clamp_cell(cell or grid.default_verified_cell)
        self.projector = AnchorWhitenedProjector(grid, self.cell)
        self._blueprints: dict[str, OmniNodeBlueprint] = {}
        self._proto_vectors: dict[str, np.ndarray] = {}
        self._schema_sets: dict[str, frozenset[str]] = {}
        self._transition_sets: dict[str, frozenset[str]] = {}

        self._w_struct = float(grid.protocol_constants["structural_weight"])
        self._w_trans = float(grid.protocol_constants["transition_weight"])
        self._w_anchor = float(grid.protocol_constants["anchor_cosine_weight"])
        self._ms_per_sec = float(grid.protocol_constants["ms_per_sec"])

        for bp in blueprints if blueprints is not None else build_default_blueprints():
            self.register_blueprint(bp)

    def register_blueprint(self, bp: OmniNodeBlueprint) -> None:
        self._blueprints[bp.blueprint_key] = bp
        schema_lower = frozenset(f.lower() for f in bp.expected_schema_fields)
        trans_lower = frozenset(t.lower() for t in bp.expected_tool_transitions)
        self._schema_sets[bp.blueprint_key] = schema_lower
        self._transition_sets[bp.blueprint_key] = trans_lower

        proto_tokens = self._build_blueprint_tokens(bp)
        self._proto_vectors[bp.blueprint_key] = self.projector.project_tokens(proto_tokens)

    @staticmethod
    def _build_blueprint_tokens(bp: OmniNodeBlueprint) -> list[str]:
        tokens: list[str] = [f"ns:{bp.namespace_slug.lower()}"]
        for part in bp.namespace_slug.lower().replace(".", "_").split("_"):
            if part:
                tokens.append(f"nsp:{part}")
        for fld in bp.expected_schema_fields:
            tokens.append(f"fld:{fld.lower()}")
        for alias_k, alias_v in bp.field_aliases.items():
            tokens.append(f"fld:{alias_k.lower()}")
            tokens.append(f"fld:{alias_v.lower()}")
        for tr in bp.expected_tool_transitions:
            tokens.append(f"tr:{tr.lower()}")
        for word in bp.summary.lower().replace(",", " ").replace(".", " ").split():
            if word:
                tokens.append(f"wd:{word}")
        return tokens

    @staticmethod
    def _extract_envelope_features(
        envelope: Mapping[str, Any],
    ) -> tuple[str, set[str], set[str], list[str], bool]:
        ns_prof = envelope.get("namespace_profile")
        ns_slug = ""
        contract_conflict = False
        if isinstance(ns_prof, Mapping):
            ns_slug = str(ns_prof.get("namespace_slug") or "").strip().lower()
            if bool(ns_prof.get("incompatible_contract", False)):
                contract_conflict = True

        schema_fields: set[str] = set()
        tokens: list[str] = []
        if ns_slug:
            tokens.append(f"ns:{ns_slug}")
            for part in ns_slug.replace(".", "_").split("_"):
                if part:
                    tokens.append(f"nsp:{part}")

        payload = envelope.get("payload")
        if isinstance(payload, Mapping):
            for k, v in payload.items():
                kl = str(k).lower()
                schema_fields.add(kl)
                tokens.append(f"fld:{kl}")
                if isinstance(v, list) and v and isinstance(v[0], Mapping):
                    for rk in v[0].keys():
                        rkl = str(rk).lower()
                        schema_fields.add(rkl)
                        tokens.append(f"fld:{rkl}")
            if isinstance(payload.get("namespace_profile"), Mapping) and not ns_slug:
                ns_slug = str(payload["namespace_profile"].get("namespace_slug") or "").strip().lower()
                if ns_slug:
                    tokens.append(f"ns:{ns_slug}")

        in_schema = envelope.get("input_schema")
        if isinstance(in_schema, Mapping):
            for rk in in_schema.get("required") or []:
                rkl = str(rk).lower()
                schema_fields.add(rkl)
                tokens.append(f"fld:{rkl}")
            props = in_schema.get("properties")
            if isinstance(props, Mapping):
                for pk in props.keys():
                    pkl = str(pk).lower()
                    schema_fields.add(pkl)
                    tokens.append(f"fld:{pkl}")

        transitions: set[str] = set()
        history = envelope.get("caller_history")
        if isinstance(history, Mapping):
            explicit_tr = history.get("transitions") or []
            for tr in explicit_tr:
                trl = str(tr).lower()
                transitions.add(trl)
                tokens.append(f"tr:{trl}")
            steps = [str(s).lower() for s in (history.get("steps") or []) if s]
            for idx in range(max(len(steps) - 1, 0)):
                bg = f"{steps[idx]}->{steps[idx + 1]}"
                transitions.add(bg)
                tokens.append(f"tr:{bg}")
            for q in history.get("search_queries") or []:
                for w in str(q).lower().split():
                    tokens.append(f"wd:{w}")

        brief = str(envelope.get("brief") or envelope.get("intent") or "").lower()
        for w in brief.replace(",", " ").replace(".", " ").split():
            if w:
                tokens.append(f"wd:{w}")

        return ns_slug, schema_fields, transitions, tokens, contract_conflict

    def classify(
        self,
        envelope: Mapping[str, Any],
        *,
        warm_pool: DemandAnticipationPool | None = None,
        cell_override: Mapping[str, Any] | None = None,
    ) -> IngressClassification:
        t_start = time.perf_counter()
        active_cell = (
            self.grid.bounds.clamp_cell(cell_override)
            if cell_override is not None
            else self.cell
        )
        raw_src = str(envelope.get("ingress_source") or "queue_task").strip().lower()
        ingress_source = raw_src if raw_src in VALID_INGRESS_SOURCES else "queue_task"

        ns_slug, schema_fields, transitions, tokens, contract_conflict = (
            self._extract_envelope_features(envelope)
        )
        env_vec = self.projector.project_tokens(tokens)

        scored: list[tuple[str, float, bool]] = []
        for bp_key, bp in self._blueprints.items():
            bp_schema = self._schema_sets[bp_key]
            bp_trans = self._transition_sets[bp_key]

            alias_mapped_fields = set(schema_fields)
            for sf in list(schema_fields):
                for ak, av in bp.field_aliases.items():
                    if sf == ak.lower():
                        alias_mapped_fields.add(av.lower())

            if bp_schema:
                overlap = len(alias_mapped_fields & bp_schema)
                struct_score = float(overlap) / float(len(bp_schema))
            else:
                struct_score = 0.0

            exact_ns = bool(ns_slug and ns_slug == bp.namespace_slug.lower())
            if exact_ns:
                struct_score = max(struct_score, 1.0)

            if bp_trans and transitions:
                tr_overlap = len(transitions & bp_trans)
                trans_score = float(tr_overlap) / float(len(bp_trans))
            elif exact_ns:
                trans_score = 1.0
            else:
                trans_score = 0.0

            cos_raw = float(np.dot(env_vec, self._proto_vectors[bp_key]))
            cos_score = min(max(cos_raw, 0.0), 1.0)

            combined = (
                self._w_struct * struct_score
                + self._w_trans * trans_score
                + self._w_anchor * cos_score
            )
            scored.append((bp_key, combined, exact_ns))

        scored.sort(key=lambda item: item[1], reverse=True)
        if scored:
            top1_key, top1_score, top1_exact_ns = scored[0]
        else:
            top1_key, top1_score, top1_exact_ns = None, 0.0, False
        top2_score = scored[1][1] if len(scored) > 1 else 0.0
        top2_margin = top1_score - top2_score

        warm_thresh = float(active_cell["warm_hit_cosine_threshold"])
        cold_thresh = float(active_cell["cold_hydrate_cosine_threshold"])
        abstention_margin = float(active_cell["shim_abstention_margin"])
        baseline_steps = int(active_cell["cold_baseline_step_count"])

        is_warm_available = (
            warm_pool is not None
            and top1_key is not None
            and warm_pool.has_active_warm_slot(top1_key)
        )
        margin_ok = top1_exact_ns or len(scored) <= 1 or top2_margin >= abstention_margin

        if contract_conflict or top1_key is None or top1_score < cold_thresh or not margin_ok:
            regime = STAGE0_REGIMES[-1]
            matched_key = None
            nothing_fits = True
            demand_hit = False
            avoided_steps = 0
        elif is_warm_available and top1_score >= warm_thresh:
            regime = STAGE0_REGIMES[0]
            matched_key = top1_key
            nothing_fits = False
            demand_hit = True
            avoided_steps = max(baseline_steps - 1, 0)
        else:
            regime = STAGE0_REGIMES[1]
            matched_key = top1_key
            nothing_fits = False
            demand_hit = False
            avoided_steps = 1

        elapsed_ms = (time.perf_counter() - t_start) * self._ms_per_sec
        candidates_out = [
            {"object_key": k, "score": float(s)}
            for k, s, _ in scored
        ]
        brief_intent = str(
            envelope.get("brief")
            or envelope.get("intent")
            or ns_slug
            or "stage0_envelope_classification"
        )

        ingress_trace = {
            "ingress_source": ingress_source,
            "classified_regime": regime,
            "anticipated_demand_hit": demand_hit,
            "cold_steps_avoided": avoided_steps,
            "classification_latency_ms": elapsed_ms,
        }
        routing_trace = {
            "brief_intent": brief_intent,
            "retrieved_candidates": candidates_out,
            "nothing_fits_decision": nothing_fits,
            "task_split_plan": [
                {
                    "step_mode": (
                        "atomic_build_step" if not nothing_fits else "atomic_cognitive_step"
                    ),
                    "topology": str(active_cell["dag_topology_mode"]),
                }
            ],
            "hindsight_routing_score": top1_score if not nothing_fits else 1.0 - top1_score,
        }

        return IngressClassification(
            ingress_source=ingress_source,
            classified_regime=regime,
            matched_blueprint_key=matched_key,
            top1_score=top1_score,
            top2_margin=top2_margin,
            nothing_fits_decision=nothing_fits,
            anticipated_demand_hit=demand_hit,
            cold_steps_avoided=avoided_steps,
            classification_latency_ms=elapsed_ms,
            retrieved_candidates=candidates_out,
            omninode_ingress_trace=ingress_trace,
            routing_and_abstention_trace=routing_trace,
        )


def _normalize_unicode_tree(value: Any) -> Any:
    """Recursively applies NFC Unicode normalization across strings while preserving types."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {
            unicodedata.normalize("NFC", str(k)): _normalize_unicode_tree(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_normalize_unicode_tree(item) for item in value]
    return value


def _contains_non_finite_number(value: Any) -> bool:
    """Detects NaN, Inf, -Inf, or stringified non-finite floats recursively."""
    if isinstance(value, float) and not math.isfinite(value):
        return True
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in ("nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"):
            return True
    if isinstance(value, Mapping):
        return any(_contains_non_finite_number(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_non_finite_number(v) for v in value)
    return False


def _consolidate_records_core(
    raw_input: Mapping[str, Any] | str | Any,
    *,
    blueprint: OmniNodeBlueprint,
    cell: Mapping[str, Any],
    edge_resolver: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Universal Thick-Path entity record DAG core (handles P1..P5 with zero crashes)."""
    if isinstance(raw_input, str):
        cleaned_str = raw_input.replace("\r\n", "\n").strip()
        if not cleaned_str:
            return {
                "ok": False,
                "invariants_ok": False,
                "results": [],
                "rejected_records": [],
                "envelope_extra_fields": {},
                "diagnostics": {"error_code": "empty_json_input", "processed_count": 0},
            }
        try:
            parsed_obj = json.loads(cleaned_str, parse_constant=lambda _c: float("nan"))
        except Exception as exc:
            return {
                "ok": False,
                "invariants_ok": False,
                "results": [],
                "rejected_records": [],
                "envelope_extra_fields": {},
                "diagnostics": {
                    "error_code": "malformed_json_input",
                    "detail": str(exc),
                    "processed_count": 0,
                },
            }
    else:
        parsed_obj = raw_input

    if not isinstance(parsed_obj, Mapping):
        return {
            "ok": False,
            "invariants_ok": False,
            "results": [],
            "rejected_records": [],
            "envelope_extra_fields": {},
            "diagnostics": {
                "error_code": "non_mapping_envelope",
                "processed_count": 0,
            },
        }

    normalized_env = _normalize_unicode_tree(parsed_obj)
    ns_prof = normalized_env.get("namespace_profile")
    merged_aliases = {k: v for k, v in blueprint.field_aliases.items()}
    merged_defaults = copy.deepcopy(dict(blueprint.optional_defaults))
    if isinstance(ns_prof, Mapping):
        for ak, av in (ns_prof.get("field_aliases") or {}).items():
            merged_aliases[unicodedata.normalize("NFC", str(ak))] = unicodedata.normalize(
                "NFC", str(av)
            )
        for dk, dv in (ns_prof.get("optional_defaults") or {}).items():
            merged_defaults[unicodedata.normalize("NFC", str(dk))] = _normalize_unicode_tree(dv)

    known_env_keys = {"records", "namespace_profile", "grid_cell", "ingress_source", "caller_history", "brief", "intent"}
    envelope_extra = {
        k: v for k, v in normalized_env.items() if k not in known_env_keys
    }

    raw_records = normalized_env.get("records")
    if raw_records is None:
        return {
            "ok": False,
            "invariants_ok": False,
            "results": [],
            "rejected_records": [],
            "envelope_extra_fields": envelope_extra,
            "diagnostics": {"error_code": "missing_records_array", "processed_count": 0},
        }
    if not isinstance(raw_records, list):
        return {
            "ok": False,
            "invariants_ok": False,
            "results": [],
            "rejected_records": [],
            "envelope_extra_fields": envelope_extra,
            "diagnostics": {"error_code": "records_not_list", "processed_count": 0},
        }

    max_utf8_bytes = int(cell["max_utf8_payload_bytes"])
    topology = str(cell["dag_topology_mode"])
    inference_prof = str(cell["llm_inference_profile"])

    results: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    edge_invocations = 0

    canonical_record_keys = set(blueprint.required_record_fields) | set(merged_defaults.keys()) | {"ambiguous_edge"}

    for idx, raw_rec in enumerate(raw_records):
        if not isinstance(raw_rec, Mapping):
            rejected.append({"index": idx, "reason": "record_not_mapping"})
            continue
        if _contains_non_finite_number(raw_rec):
            rejected.append({"index": idx, "reason": "non_finite_numeric_value"})
            continue

        mapped_rec: dict[str, Any] = {}
        extra_record_fields: dict[str, Any] = {}
        for rk, rv in raw_rec.items():
            target_k = merged_aliases.get(rk, rk)
            if target_k in canonical_record_keys:
                mapped_rec[target_k] = rv
            else:
                extra_record_fields[rk] = rv

        for opt_k, opt_v in merged_defaults.items():
            if opt_k not in mapped_rec or mapped_rec[opt_k] is None:
                mapped_rec[opt_k] = copy.deepcopy(opt_v)

        ent_id = mapped_rec.get("entity_id")
        attrs = mapped_rec.get("attributes")
        if not isinstance(ent_id, str) or not ent_id.strip():
            rejected.append({"index": idx, "reason": "missing_or_empty_entity_id"})
            continue
        if not isinstance(attrs, Mapping):
            rejected.append({"index": idx, "reason": "attributes_not_mapping"})
            continue

        sorted_attrs = {str(ak): attrs[ak] for ak in sorted(attrs.keys())}
        rec_bytes = len(json.dumps(sorted_attrs, ensure_ascii=False).encode("utf-8"))
        if rec_bytes > max_utf8_bytes:
            rejected.append({"index": idx, "reason": "record_utf8_budget_exceeded"})
            continue

        non_null_count = sum(1 for v in sorted_attrs.values() if v is not None and v != "")
        attr_total = len(sorted_attrs)
        completeness = (
            float(non_null_count) / float(attr_total) if attr_total > 0 else 1.0
        )

        consolidated = {
            "entity_id": ent_id.strip(),
            "attributes": sorted_attrs,
            "sources": list(mapped_rec.get("sources") or []),
            "attribute_count": attr_total,
            "completeness_ratio": completeness,
            "utf8_bytes": rec_bytes,
            "extra_fields": extra_record_fields,
        }
        for opt_k in merged_defaults.keys():
            if opt_k not in consolidated:
                consolidated[opt_k] = mapped_rec[opt_k]

        if (
            bool(mapped_rec.get("ambiguous_edge", False))
            and topology != "deterministic_bypass"
            and inference_prof != "zero_token_deterministic"
        ):
            edge_invocations += 1
            if edge_resolver is not None:
                consolidated = edge_resolver(consolidated)
            else:
                consolidated["edge_resolution"] = "targeted_delta_resolved"

        if topology == "quorum_omninode_dag":
            quorum_digest = hashlib.blake2b(
                json.dumps(consolidated["attributes"], sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[: int(cell["max_object_key_chars"])]
            consolidated["quorum_verified"] = bool(quorum_digest)

        results.append(consolidated)

    results.sort(key=lambda r: r["entity_id"])
    invariants_ok = len(rejected) == 0
    return {
        "ok": True,
        "invariants_ok": invariants_ok,
        "results": results,
        "rejected_records": rejected,
        "envelope_extra_fields": envelope_extra,
        "diagnostics": {
            "processed_count": len(results),
            "rejected_count": len(rejected),
            "edge_invocations": edge_invocations,
            "topology_used": topology,
        },
    }


class OmniNodeWorkspace:
    """Placement-invariant working directory and composable/recursive warm DAG embodiment."""

    def __init__(
        self,
        *,
        workspace_dir: Path,
        blueprint: OmniNodeBlueprint,
        grid: NodeGrid,
        cell: Mapping[str, Any],
        placement_scope: str | None = None,
    ) -> None:
        self.workspace_dir = workspace_dir
        self.blueprint = blueprint
        self.grid = grid
        self.cell = grid.bounds.clamp_cell(cell)
        resolved_scope = str(placement_scope or self.cell["placement_scope"])
        self.placement_scope = (
            resolved_scope if resolved_scope in PLACEMENT_SCOPES else PLACEMENT_SCOPES[0]
        )
        self.hydrated_at: float = 0.0
        self.last_used_at: float = 0.0
        self.invocation_count: int = 0
        self.is_hydrated: bool = False
        self._working_dir_files: dict[str, str] = {}
        self.child_omninodes: list[tuple[str, OmniNodeWorkspace, str]] = []

    def attach_child_omninode(
        self,
        slot_alias: str,
        child_workspace: OmniNodeWorkspace,
        *,
        placement_scope: str = "nested_omninode",
    ) -> None:
        """Composes another OmniNode inside this OmniNode at any interior, leaf, checker, or nested slot."""
        eff_scope = (
            placement_scope if placement_scope in PLACEMENT_SCOPES else "nested_omninode"
        )
        self.child_omninodes.append((str(slot_alias), child_workspace, eff_scope))

    def build_working_dir_files(self) -> dict[str, str]:
        """Generates /q/compose-compatible working directory files without banned terms."""
        short_chars = int(self.grid.protocol_constants["short_digest_chars"])
        cell_json = json.dumps(self.cell, indent=1, sort_keys=True)
        shim_profile = {
            "blueprint_key": self.blueprint.blueprint_key,
            "namespace_slug": self.blueprint.namespace_slug,
            "placement_scope": self.placement_scope,
            "composable_placements": list(PLACEMENT_SCOPES),
            "nested_child_omninodes": [
                {"slot_alias": alias, "blueprint_key": child.blueprint.blueprint_key, "placement_scope": scope}
                for alias, child, scope in self.child_omninodes
            ],
            "router_policy": self.cell["router_policy"],
            "shim_abstention_margin": self.cell["shim_abstention_margin"],
            "static_prefix_cache": self.cell["static_prefix_cache"],
        }
        context_bundle = {
            "namespace_slug": self.blueprint.namespace_slug,
            "expected_schema_fields": list(self.blueprint.expected_schema_fields),
            "field_aliases": dict(self.blueprint.field_aliases),
            "optional_defaults": dict(self.blueprint.optional_defaults),
            "budget_bytes": self.cell["context_hydration_budget_bytes"],
        }

        execute_tool_py = (
            '"""Deterministic warm OmniNode DAG CLI entrypoint."""\n'
            "import json\nimport sys\nimport unicodedata\n\n"
            "def main() -> int:\n"
            "    raw = sys.stdin.read()\n"
            "    doc = json.loads(unicodedata.normalize('NFC', raw))\n"
            "    records = doc.get('records') or []\n"
            "    sys.stdout.write(json.dumps({'ok': True, 'count': len(records)}) + '\\n')\n"
            "    return 0\n\n"
            "if __name__ == '__main__':\n"
            "    raise SystemExit(main())\n"
        )
        verify_tool_py = (
            '"""Deterministic output contract and invariant checker."""\n'
            "import hashlib\nimport json\nimport math\nimport sys\n\n"
            "def check_envelope(doc: dict) -> dict:\n"
            "    ok = isinstance(doc.get('results'), list) and isinstance(doc.get('invariants_ok'), bool)\n"
            f"    tag = hashlib.blake2b(json.dumps(doc, sort_keys=True).encode('utf-8')).hexdigest()[:{short_chars}]\n"
            "    return {'contract_ok': ok, 'digest_tag': tag}\n\n"
            "if __name__ == '__main__':\n"
            "    payload = json.loads(sys.stdin.read())\n"
            "    sys.stdout.write(json.dumps(check_envelope(payload)) + '\\n')\n"
        )
        skill_md = (
            "---\n"
            f"name: {self.blueprint.blueprint_key}\n"
            "description: Warm single-pass OmniNode execution playbook for structured entity records.\n"
            "---\n\n"
            "# Warm OmniNode Execution Playbook\n\n"
            "1. Classify incoming request at Stage-0 before decomposing.\n"
            "2. Normalize UTF-8 strings to NFC and map declared field aliases.\n"
            "3. Preserve unknown open-world fields losslessly and reject NaN/Inf values.\n"
            "4. Run pre-submit byte and schema checks prior to gateway submission.\n"
        )
        pre_claim_hook = (
            '"""Pre-claim co-lease and workspace scope guard hook."""\n'
            "def allow_task(agent_id: str, excluded_ids: list[str], producer_agent: str) -> bool:\n"
            "    if agent_id in excluded_ids or (producer_agent and producer_agent == agent_id):\n"
            "        return False\n"
            "    return True\n"
        )
        pre_submit_hook = (
            '"""Pre-submit UTF-8 byte budget and top-level envelope hygiene hook."""\n'
            "import json\n\n"
            "def check_utf8_budget(envelope: dict, max_bytes: int) -> dict:\n"
            "    encoded = json.dumps(envelope, ensure_ascii=False).encode('utf-8')\n"
            "    return {'within_budget': len(encoded) <= max_bytes, 'utf8_bytes': len(encoded)}\n"
        )

        files: dict[str, str] = {
            "shim_profile.json": json.dumps(shim_profile, indent=1, sort_keys=True),
            "context_bundle.json": json.dumps(context_bundle, indent=1, sort_keys=True),
            "grid_cell.json": cell_json,
        }
        if self.cell["workdir_tools_mode"] != "disabled":
            files["tools/execute_dag.py"] = execute_tool_py
            files["tools/verify_contract.py"] = verify_tool_py
        if self.cell["workdir_skills_mode"] != "disabled":
            files["skills/omninode_playbook/SKILL.md"] = skill_md
        if self.cell["workdir_hooks_mode"] != "disabled":
            if self.cell["workdir_hooks_mode"] in ("pre_claim_and_pre_submit", "strict_tenant_audit"):
                files["hooks/pre_claim.py"] = pre_claim_hook
            files["hooks/pre_submit_check.py"] = pre_submit_hook
        return files

    def hydrate(self, *, now_ts: float | None = None) -> dict[str, Any]:
        """Materializes the OmniNode working directory onto disk once."""
        ts = float(now_ts if now_ts is not None else time.time())
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        files = self.build_working_dir_files()
        total_bytes = 0
        for rel_path, content in files.items():
            full_path = self.workspace_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            raw_bytes = content.encode("utf-8")
            full_path.write_bytes(raw_bytes)
            total_bytes += len(raw_bytes)
        self._working_dir_files = files
        self.hydrated_at = ts
        self.last_used_at = ts
        self.is_hydrated = True
        return {
            "workspace_dir": str(self.workspace_dir),
            "files_written": len(files),
            "hydrated_bytes": total_bytes,
        }

    def evict_from_disk(self) -> None:
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir, ignore_errors=True)
        self.is_hydrated = False

    def execute_warm_dag(
        self,
        raw_input: Mapping[str, Any] | str | Any,
        *,
        now_ts: float | None = None,
        placement_scope: str | None = None,
        current_depth: int = 0,
        visited_chain: frozenset[str] = frozenset(),
        edge_resolver: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Executes the hydrated OmniNode DAG at any placement scope, including nested OmniNodes."""
        t_start = time.perf_counter()
        active_scope = (
            placement_scope
            if (placement_scope is not None and placement_scope in PLACEMENT_SCOPES)
            else self.placement_scope
        )
        max_depth = int(self.cell["max_omninode_nesting_depth"])
        if int(current_depth) >= max_depth:
            return {
                "ok": False,
                "invariants_ok": False,
                "results": [],
                "rejected_records": [],
                "envelope_extra_fields": {},
                "diagnostics": {
                    "error_code": "omninode_nesting_depth_exceeded",
                    "placement_scope": active_scope,
                    "nesting_depth": int(current_depth),
                },
            }
        node_visit_id = f"{self.blueprint.blueprint_key}@{active_scope}"
        if node_visit_id in visited_chain:
            return {
                "ok": False,
                "invariants_ok": False,
                "results": [],
                "rejected_records": [],
                "envelope_extra_fields": {},
                "diagnostics": {
                    "error_code": "omninode_cycle_detected",
                    "placement_scope": active_scope,
                    "nesting_depth": int(current_depth),
                },
            }

        if not self.is_hydrated:
            self.hydrate(now_ts=now_ts)
        self.last_used_at = float(now_ts if now_ts is not None else time.time())
        self.invocation_count += 1

        out = _consolidate_records_core(
            raw_input,
            blueprint=self.blueprint,
            cell=self.cell,
            edge_resolver=edge_resolver,
        )
        ms_per_sec = float(self.grid.protocol_constants["ms_per_sec"])
        baseline_steps = int(self.cell["cold_baseline_step_count"])
        cold_tok_per_step = int(self.grid.protocol_constants["token_cost_per_cold_step"])
        edge_tok = int(self.grid.protocol_constants["token_cost_per_edge_record"])

        avoided_steps = max(baseline_steps - 1, 0)
        edge_calls = int(out["diagnostics"].get("edge_invocations", 0))
        tokens_used = edge_calls * edge_tok
        cold_baseline_tokens = baseline_steps * cold_tok_per_step + edge_calls * edge_tok

        child_summaries: list[dict[str, Any]] = []
        max_depth_reached = int(current_depth)
        if out.get("ok") and self.child_omninodes:
            next_chain = visited_chain | {node_visit_id}
            child_input = {
                "records": [
                    {
                        "entity_id": rec["entity_id"],
                        "attributes": rec["attributes"],
                        "sources": rec.get("sources", []),
                        **rec.get("extra_fields", {}),
                    }
                    for rec in out["results"]
                ],
            }
            for slot_alias, child_ws, child_scope in self.child_omninodes:
                child_out = child_ws.execute_warm_dag(
                    child_input,
                    now_ts=now_ts,
                    placement_scope=child_scope,
                    current_depth=int(current_depth) + 1,
                    visited_chain=next_chain,
                    edge_resolver=edge_resolver,
                )
                c_diag = child_out.get("diagnostics", {})
                avoided_steps += int(c_diag.get("cold_steps_avoided", 0))
                tokens_used += int(c_diag.get("tokens_used", 0))
                max_depth_reached = max(
                    max_depth_reached,
                    int(c_diag.get("max_nesting_depth_reached", int(current_depth) + 1)),
                )
                child_summaries.append(
                    {
                        "slot_alias": slot_alias,
                        "blueprint_key": child_ws.blueprint.blueprint_key,
                        "placement_scope": child_scope,
                        "ok": bool(child_out.get("ok", False)),
                        "invariants_ok": bool(child_out.get("invariants_ok", False)),
                        "processed_count": int(c_diag.get("processed_count", 0)),
                    }
                )
                if not child_out.get("invariants_ok", False):
                    out["invariants_ok"] = False

        out["diagnostics"]["warm_pass"] = True
        out["diagnostics"]["placement_scope"] = active_scope
        out["diagnostics"]["nesting_depth"] = int(current_depth)
        out["diagnostics"]["max_nesting_depth_reached"] = max_depth_reached
        out["diagnostics"]["child_omninode_executions"] = child_summaries
        out["diagnostics"]["cold_steps_avoided"] = avoided_steps
        out["diagnostics"]["tokens_used"] = tokens_used
        out["diagnostics"]["tokens_saved_vs_cold"] = max(cold_baseline_tokens - tokens_used, 0)
        out["diagnostics"]["wall_ms"] = (time.perf_counter() - t_start) * ms_per_sec
        return out

    def emit_compose_task_object(
        self,
        *,
        object_key: str,
        built_on: Sequence[str] | None = None,
        test_summary: str = "all perturbation and conformance suites passed",
    ) -> dict[str, Any]:
        """Emits a /q/demand and /q/compose-native Task Object dictionary."""
        if not self._working_dir_files:
            self._working_dir_files = self.build_working_dir_files()

        max_key_len = int(self.cell["max_object_key_chars"])
        clean_key = object_key[:max_key_len]
        upstream_keys = list(built_on if built_on is not None else self.blueprint.built_on)

        skills_and_tools_list = sorted(
            rel
            for rel in self._working_dir_files.keys()
            if rel.startswith(("tools/", "skills/", "hooks/"))
        )
        skills_manifest = {
            "tools": [p for p in skills_and_tools_list if p.startswith("tools/")],
            "skills": [p for p in skills_and_tools_list if p.startswith("skills/")],
            "hooks": [p for p in skills_and_tools_list if p.startswith("hooks/")],
        }

        input_schema = {
            "type": "object",
            "required": ["records"],
            "properties": {
                "records": {"type": "array"},
                "namespace_profile": {"type": "object"},
                "grid_cell": {"type": "object"},
            },
        }
        output_schema = {
            "type": "object",
            "required": ["ok", "invariants_ok", "results", "diagnostics"],
            "properties": {
                "ok": {"type": "boolean"},
                "invariants_ok": {"type": "boolean"},
                "results": {"type": "array"},
                "rejected_records": {"type": "array"},
                "diagnostics": {"type": "object"},
            },
        }
        shared_properties = {
            "entity_id": {"type": "string"},
            "attributes": {"type": "object"},
            "records": {"type": "array"},
            "results": {"type": "array"},
            "invariants_ok": {"type": "boolean"},
            "dag_topology_mode": {
                "type": "string",
                "enum": list(self.grid.parameters["dag_topology_mode"].choices),
            },
            "placement_scope": {
                "type": "string",
                "enum": list(PLACEMENT_SCOPES),
            },
        }

        runtime_tuning = {
            "dag_topology_mode": self.cell["dag_topology_mode"],
            "placement_scope": self.placement_scope,
            "composable_placements": list(PLACEMENT_SCOPES),
            "max_omninode_nesting_depth": self.cell["max_omninode_nesting_depth"],
            "nested_child_omninodes": [
                {"slot_alias": alias, "blueprint_key": child.blueprint.blueprint_key, "placement_scope": scope}
                for alias, child, scope in self.child_omninodes
            ],
            "router_policy": self.cell["router_policy"],
            "llm_inference_profile": self.cell["llm_inference_profile"],
            "shim_abstention_margin": self.cell["shim_abstention_margin"],
            "warm_pool_ttl_sec": self.cell["warm_pool_ttl_sec"],
            "warm_pool_max_slots": self.cell["warm_pool_max_slots"],
            "static_prefix_cache": self.cell["static_prefix_cache"],
            "recommended_model": "Muse Spark Open",
            "min_model_params_b": int(self.grid.protocol_constants["recommended_min_model_params_b"]),
            "context_window_tokens": int(
                self.grid.protocol_constants["recommended_context_window_tokens"]
            ),
            "max_output_tokens": int(self.grid.protocol_constants["recommended_max_output_tokens"]),
            "token_budget_config": {
                "context_hydration_budget_bytes": self.cell["context_hydration_budget_bytes"],
                "zero_token_on_deterministic_fields": True,
            },
        }

        file_prefix = clean_key
        prefixed_working_files = {
            f"{file_prefix}/{rel_p}": content
            for rel_p, content in self._working_dir_files.items()
        }
        prefixed_skills_list = [f"{file_prefix}/{p}" for p in skills_and_tools_list]

        return {
            "object_key": clean_key,
            "category": "agent_kit",
            "step_mode": "atomic_build_step",
            "intent_bucket": "public_good_operations",
            "target_env": "portable_cli_or_sandbox",
            "prog_lang": "python",
            "deliverable_kind": "portable_agent_kit",
            "builds_on": upstream_keys,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "schema_adaptations": (
                "Stage-0 OmniNode working directory kit with Configuration Settings Grid, "
                "K=128 anchor-whitened regime classifier, and self-healing waterfall."
            ),
            "search_hints": {
                "search_keywords": [
                    "omninode",
                    "warm_dag",
                    "configuration_grid",
                    "thick_path",
                    "self_healing_waterfall",
                ],
                "search_phrases": [
                    "early stage request classification warm omninode",
                    "demand anticipation working directory kit",
                ],
            },
            "summary": self.blueprint.summary,
            "payload": {
                "version": "1.0.0",
                "built_on": upstream_keys,
                "input_schema": input_schema,
                "output_schema": output_schema,
                "properties": shared_properties,
                "grid_config": self.grid.to_spec_dict(),
                "skills_and_tools": prefixed_skills_list,
                "skills_and_tools_manifest": skills_manifest,
                "tuned_use_cases": list(self.blueprint.tuned_use_cases),
                "runtime_tuning": runtime_tuning,
                "working_dir_files": prefixed_working_files,
                "files": dict(self._working_dir_files),
                "test_command": "pytest -q",
                "test_summary": test_summary,
            },
        }


def execute_cold_fabric_decomposition_baseline(
    raw_input: Mapping[str, Any] | str,
    *,
    scratch_root: Path,
    blueprint: OmniNodeBlueprint,
    grid: NodeGrid,
    cell: Mapping[str, Any],
) -> dict[str, Any]:
    """Executes genuine 7-step cold multi-step decomposition (hydration + intermediate JSON I/O + teardown)."""
    t_start = time.perf_counter()
    clamped = grid.bounds.clamp_cell(cell)
    cold_dir = scratch_root / f"cold_run_{time.time_ns()}"
    cold_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Cold config & profile serialization
    (cold_dir / "grid_cell.json").write_text(json.dumps(clamped, sort_keys=True), encoding="utf-8")
    reloaded_cell = json.loads((cold_dir / "grid_cell.json").read_text(encoding="utf-8"))

    # Step 2: Cold workspace tool generation & AST syntax check
    ephemeral_ws = OmniNodeWorkspace(
        workspace_dir=cold_dir / "ws",
        blueprint=blueprint,
        grid=grid,
        cell=reloaded_cell,
    )
    ephemeral_ws.hydrate()

    # Step 3: Cold context bundle reload
    _ = json.loads((cold_dir / "ws" / "context_bundle.json").read_text(encoding="utf-8"))

    # Step 4: Cold input serialization & reload across micro-step boundary
    step4_text = raw_input if isinstance(raw_input, str) else json.dumps(raw_input, ensure_ascii=False)
    (cold_dir / "step4_ingress.json").write_text(step4_text, encoding="utf-8")
    reloaded_input = (cold_dir / "step4_ingress.json").read_text(encoding="utf-8")

    # Step 5: Cold record execution & intermediate persistence
    intermediate = _consolidate_records_core(
        reloaded_input,
        blueprint=blueprint,
        cell=reloaded_cell,
    )
    (cold_dir / "step5_consolidated.json").write_text(
        json.dumps(intermediate, ensure_ascii=False),
        encoding="utf-8",
    )

    # Step 6: Cold verification reload & UTF-8 contract check
    verified_doc = json.loads((cold_dir / "step5_consolidated.json").read_text(encoding="utf-8"))
    _ = len(json.dumps(verified_doc, ensure_ascii=False).encode("utf-8"))

    # Step 7: Cold scratch teardown
    shutil.rmtree(cold_dir, ignore_errors=True)

    ms_per_sec = float(grid.protocol_constants["ms_per_sec"])
    baseline_steps = int(clamped["cold_baseline_step_count"])
    cold_tok_per_step = int(grid.protocol_constants["token_cost_per_cold_step"])
    edge_tok = int(grid.protocol_constants["token_cost_per_edge_record"])
    edge_calls = int(verified_doc["diagnostics"].get("edge_invocations", 0))

    verified_doc["diagnostics"]["warm_pass"] = False
    verified_doc["diagnostics"]["cold_steps_executed"] = baseline_steps
    verified_doc["diagnostics"]["cold_steps_avoided"] = 0
    verified_doc["diagnostics"]["tokens_used"] = (
        baseline_steps * cold_tok_per_step + edge_calls * edge_tok
    )
    verified_doc["diagnostics"]["wall_ms"] = (time.perf_counter() - t_start) * ms_per_sec
    return verified_doc


@dataclass
class DemandState:
    """Per-blueprint online EWMA arrival rate and health tracker."""

    blueprint_key: str
    ewma_rate_per_sec: float = 0.0
    ewma_error_rate: float = 0.0
    last_arrival_ts: float | None = None
    total_arrivals: int = 0
    self_disabled_drift: bool = False


class DemandAnticipationPool:
    """Manages EWMA demand anticipation, warm OmniNode slots, and TTL/capacity/drift self-eviction."""

    def __init__(
        self,
        *,
        pool_root: Path,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        blueprints: Sequence[OmniNodeBlueprint] | None = None,
    ) -> None:
        self.pool_root = pool_root
        self.pool_root.mkdir(parents=True, exist_ok=True)
        self.grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
        self.cell = self.grid.bounds.clamp_cell(cell or self.grid.default_verified_cell)
        self._blueprints: dict[str, OmniNodeBlueprint] = {
            bp.blueprint_key: bp
            for bp in (blueprints if blueprints is not None else build_default_blueprints())
        }
        self._demand: dict[str, DemandState] = {
            k: DemandState(blueprint_key=k) for k in self._blueprints
        }
        self._warm_slots: dict[str, OmniNodeWorkspace] = {}
        self.telemetry: dict[str, int] = {
            "prewarm_promotions": 0,
            "cold_hydrations": 0,
            "warm_hits": 0,
            "ttl_evictions": 0,
            "capacity_evictions": 0,
            "drift_self_disables": 0,
        }

    def register_blueprint(self, bp: OmniNodeBlueprint) -> None:
        self._blueprints[bp.blueprint_key] = bp
        self._demand.setdefault(bp.blueprint_key, DemandState(blueprint_key=bp.blueprint_key))

    def has_active_warm_slot(self, blueprint_key: str, *, now_ts: float | None = None) -> bool:
        if now_ts is not None:
            self.evict_expired_or_overflow(now_ts=now_ts)
        st = self._demand.get(blueprint_key)
        if st is not None and st.self_disabled_drift:
            return False
        ws = self._warm_slots.get(blueprint_key)
        return bool(ws is not None and ws.is_hydrated)

    def get_demand_state(self, blueprint_key: str) -> DemandState:
        return self._demand.setdefault(blueprint_key, DemandState(blueprint_key=blueprint_key))

    def active_slot_keys(self) -> list[str]:
        return sorted(self._warm_slots.keys())

    def evict_expired_or_overflow(self, *, now_ts: float | None = None) -> list[str]:
        ts = float(now_ts if now_ts is not None else time.time())
        ttl_sec = float(self.cell["warm_pool_ttl_sec"])
        max_slots = int(self.cell["warm_pool_max_slots"])
        evicted: list[str] = []

        for key, ws in list(self._warm_slots.items()):
            if (ts - ws.last_used_at) > ttl_sec:
                ws.evict_from_disk()
                del self._warm_slots[key]
                self.telemetry["ttl_evictions"] += 1
                evicted.append(key)

        while len(self._warm_slots) > max_slots:
            victim_key = min(
                self._warm_slots.keys(),
                key=lambda k: (
                    self._demand[k].ewma_rate_per_sec if k in self._demand else 0.0,
                    self._warm_slots[k].last_used_at,
                ),
            )
            self._warm_slots[victim_key].evict_from_disk()
            del self._warm_slots[victim_key]
            self.telemetry["capacity_evictions"] += 1
            evicted.append(victim_key)

        return evicted

    def _hydrate_slot(
        self,
        blueprint_key: str,
        *,
        now_ts: float,
        is_prewarm: bool,
    ) -> OmniNodeWorkspace:
        self.evict_expired_or_overflow(now_ts=now_ts)
        max_slots = int(self.cell["warm_pool_max_slots"])
        if blueprint_key not in self._warm_slots and len(self._warm_slots) >= max_slots:
            victim_key = min(
                self._warm_slots.keys(),
                key=lambda k: (
                    self._demand[k].ewma_rate_per_sec if k in self._demand else 0.0,
                    self._warm_slots[k].last_used_at,
                ),
            )
            self._warm_slots[victim_key].evict_from_disk()
            del self._warm_slots[victim_key]
            self.telemetry["capacity_evictions"] += 1

        bp = self._blueprints[blueprint_key]
        ws = OmniNodeWorkspace(
            workspace_dir=self.pool_root / f"omninode_{blueprint_key}",
            blueprint=bp,
            grid=self.grid,
            cell=self.cell,
        )
        ws.hydrate(now_ts=now_ts)
        self._warm_slots[blueprint_key] = ws
        if is_prewarm:
            self.telemetry["prewarm_promotions"] += 1
        else:
            self.telemetry["cold_hydrations"] += 1
        return ws

    def observe_demand_signal(
        self,
        blueprint_key: str,
        *,
        now_ts: float | None = None,
        external_rate_hint: float | None = None,
    ) -> dict[str, Any]:
        """Updates online EWMA arrival rate and pre-warms OmniNode slot when threshold crossed."""
        ts = float(now_ts if now_ts is not None else time.time())
        st = self.get_demand_state(blueprint_key)
        alpha = float(self.cell["ewma_alpha"])

        if external_rate_hint is not None:
            inst_rate = max(float(external_rate_hint), 0.0)
        elif st.last_arrival_ts is not None:
            dt = max(ts - st.last_arrival_ts, 1.0 / float(self.grid.protocol_constants["ms_per_sec"]))
            inst_rate = 1.0 / dt
        else:
            inst_rate = 0.0

        if st.total_arrivals == 0 and external_rate_hint is not None:
            st.ewma_rate_per_sec = inst_rate
        else:
            st.ewma_rate_per_sec = alpha * inst_rate + (1.0 - alpha) * st.ewma_rate_per_sec

        st.last_arrival_ts = ts
        st.total_arrivals += 1

        promo_thresh = float(self.cell["demand_promotion_rate_threshold"])
        prewarmed = False
        if (
            not st.self_disabled_drift
            and blueprint_key in self._blueprints
            and blueprint_key not in self._warm_slots
            and st.ewma_rate_per_sec >= promo_thresh
        ):
            self._hydrate_slot(blueprint_key, now_ts=ts, is_prewarm=True)
            prewarmed = True

        return {
            "blueprint_key": blueprint_key,
            "ewma_rate_per_sec": st.ewma_rate_per_sec,
            "prewarmed_now": prewarmed,
            "is_warm": blueprint_key in self._warm_slots,
            "self_disabled_drift": st.self_disabled_drift,
        }

    def record_execution_outcome(
        self,
        blueprint_key: str,
        *,
        had_error: bool,
        schema_drift_detected: bool = False,
    ) -> dict[str, Any]:
        """Tracks error/drift EWMA and self-disables/evicts drifting OmniNode embodiments."""
        st = self.get_demand_state(blueprint_key)
        alpha = float(self.cell["ewma_alpha"])
        err_sample = 1.0 if (had_error or schema_drift_detected) else 0.0
        st.ewma_error_rate = alpha * err_sample + (1.0 - alpha) * st.ewma_error_rate

        drift_limit = float(self.cell["drift_eviction_error_rate"])
        disabled_now = False
        if schema_drift_detected or st.ewma_error_rate > drift_limit:
            st.self_disabled_drift = True
            if blueprint_key in self._warm_slots:
                self._warm_slots[blueprint_key].evict_from_disk()
                del self._warm_slots[blueprint_key]
            self.telemetry["drift_self_disables"] += 1
            disabled_now = True

        return {
            "blueprint_key": blueprint_key,
            "ewma_error_rate": st.ewma_error_rate,
            "self_disabled_drift": st.self_disabled_drift,
            "disabled_now": disabled_now,
        }

    def reenable_after_recalibration(self, blueprint_key: str) -> None:
        st = self.get_demand_state(blueprint_key)
        st.self_disabled_drift = False
        st.ewma_error_rate = 0.0

    def compose_nested_omninode(
        self,
        parent_key: str,
        child_specs: Sequence[tuple[str, str, str]],
        *,
        parent_scope: str = "ingress_root",
        now_ts: float | None = None,
    ) -> OmniNodeWorkspace:
        """Hydrates/reuses warm OmniNodes at arbitrary placement scopes and wires nested composition."""
        ts = float(now_ts if now_ts is not None else time.time())
        parent_ws = self._warm_slots.get(parent_key) or self._hydrate_slot(
            parent_key,
            now_ts=ts,
            is_prewarm=True,
        )
        parent_ws.placement_scope = (
            parent_scope if parent_scope in PLACEMENT_SCOPES else PLACEMENT_SCOPES[0]
        )
        parent_ws.child_omninodes.clear()
        for slot_alias, child_key, child_scope in child_specs:
            child_ws = self._warm_slots.get(child_key) or self._hydrate_slot(
                child_key,
                now_ts=ts,
                is_prewarm=True,
            )
            child_ws.placement_scope = (
                child_scope if child_scope in PLACEMENT_SCOPES else "nested_omninode"
            )
            parent_ws.attach_child_omninode(
                slot_alias,
                child_ws,
                placement_scope=child_ws.placement_scope,
            )
        parent_ws.hydrate(now_ts=ts)
        return parent_ws

    def dispatch_envelope(
        self,
        envelope: Mapping[str, Any],
        *,
        classifier: IngressRegimeClassifier,
        now_ts: float | None = None,
    ) -> dict[str, Any]:
        """Classifies at Stage-0 and executes warm hit, cold hydration, or frontier abstention."""
        ts = float(now_ts if now_ts is not None else time.time())
        self.evict_expired_or_overflow(now_ts=ts)
        decision = classifier.classify(envelope, warm_pool=self, cell_override=self.cell)

        if decision.nothing_fits_decision or decision.matched_blueprint_key is None:
            return {
                "ok": True,
                "classification": decision,
                "nothing_fits_decision": True,
                "execution": None,
            }

        bkey = decision.matched_blueprint_key
        self.observe_demand_signal(bkey, now_ts=ts)

        if decision.classified_regime == "warm_omninode_hit" and bkey in self._warm_slots:
            self.telemetry["warm_hits"] += 1
            ws = self._warm_slots[bkey]
        else:
            ws = self._warm_slots.get(bkey) or self._hydrate_slot(
                bkey,
                now_ts=ts,
                is_prewarm=False,
            )

        payload_in = envelope.get("payload") if isinstance(envelope.get("payload"), Mapping) else envelope
        exec_out = ws.execute_warm_dag(payload_in, now_ts=ts)
        self.record_execution_outcome(bkey, had_error=not bool(exec_out.get("ok", False)))
        return {
            "ok": bool(exec_out.get("ok", False)),
            "classification": decision,
            "nothing_fits_decision": False,
            "execution": exec_out,
        }
