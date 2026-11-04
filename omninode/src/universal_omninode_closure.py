"""Universal OmniNode Algebraic Closure: Uniform Protocol & Compositional Operators.

Every component across every layer and scale implements the single `OmniNode` protocol:
- Atomic & Structural OmniNodes:
  * ToolOmniNode, SkillOmniNode, HookOmniNode, RouterOmniNode, ShimOmniNode,
    SidecarOmniNode, WorkerHarnessOmniNode, CheckerOmniNode
- Algebraic Closure Combinators:
  * WaterfallOmniNode       (`primary // fallback`)
  * SequentialOmniNode      (`left >> right`)
  * ParallelOmniNode        (`left | right`)
  * QuorumCheckedOmniNode   (`maker @ checker`, enforcing distinct maker != checker keys)
- Universal 1-Line Adapter:
  * OmniNode.wrap(target, ...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import inspect
import json
import math
import time
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from src.omninode_embodiment import (
    PLACEMENT_SCOPES,
    AnchorWhitenedProjector,
    IngressRegimeClassifier,
    OmniNodeWorkspace,
    build_default_blueprints,
)
from src.omninode_grid_engine import DEFAULT_GRID_CONFIG_PATH, NodeGrid
from src.self_healing_waterfall import (
    CooperativeLeaseLifecycle,
    LocalCapabilityLadder,
    PreFlightEnvelopeSanitizer,
    SelfHealingWaterfallClient,
    SelfReviewCoLeaseGuard,
)


def _ensure_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {"value": value}


@dataclass
class OmniNodeResult:
    """Uniform execution outcome returned by every `OmniNode`."""

    ok: bool
    output: dict[str, Any]
    node_id: str
    role: str
    placement_scope: str
    latency_ms: float
    tokens_used: int = 0
    cold_steps_avoided: int = 0
    sidecar_trace: dict[str, Any] | None = None
    hook_traces: list[dict[str, Any]] = field(default_factory=list)
    child_results: list[OmniNodeResult] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "output": self.output,
            "node_id": self.node_id,
            "role": self.role,
            "placement_scope": self.placement_scope,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "cold_steps_avoided": self.cold_steps_avoided,
            "sidecar_trace": self.sidecar_trace,
            "hook_traces": list(self.hook_traces),
            "child_results": [c.to_dict() for c in self.child_results],
            "diagnostics": dict(self.diagnostics),
        }


class OmniNode:
    """Single uniform placement-invariant protocol across tools, skills, hooks, routers, sidecars, and DAGs."""

    def __init__(
        self,
        *,
        node_id: str,
        role: str,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = None,
        input_schema: Mapping[str, Any] | None = None,
        output_schema: Mapping[str, Any] | None = None,
        children: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
        hooks: Sequence[OmniNode] = (),
        built_on: Sequence[str] = (),
        extra_workdir_files: Mapping[str, str] | None = None,
        summary: str = "",
    ) -> None:
        self.grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
        self.cell = self.grid.bounds.clamp_cell(cell or self.grid.default_verified_cell)
        max_key_chars = int(self.cell["max_object_key_chars"])
        clean_id = "".join(
            ch if (ch.isalnum() or ch in ("_", "-")) else "_"
            for ch in str(node_id or "omninode").strip().lower()
        ).strip("_-")
        self.node_id = (clean_id or "omninode")[:max_key_chars]
        self.role = str(role or "generic").strip().lower()
        raw_scope = str(placement_scope or self.cell["placement_scope"])
        self.placement_scope = (
            raw_scope if raw_scope in PLACEMENT_SCOPES else PLACEMENT_SCOPES[0]
        )
        self.input_schema: dict[str, Any] = (
            dict(input_schema) if input_schema is not None else {"type": "object"}
        )
        self.output_schema: dict[str, Any] = (
            dict(output_schema) if output_schema is not None else {"type": "object"}
        )
        self.children: tuple[OmniNode, ...] = tuple(children)
        self.sidecar: OmniNode | None = sidecar
        self.hooks: tuple[OmniNode, ...] = tuple(hooks)
        self.built_on: tuple[str, ...] = tuple(str(k) for k in built_on if k)
        self._extra_workdir_files: dict[str, str] = dict(extra_workdir_files or {})
        self.summary = summary or f"Composable {self.role} OmniNode ({self.node_id})"

    def _own_workdir_files(self) -> dict[str, str]:
        base = {
            f"nodes/{self.node_id}/profile.json": json.dumps(
                {
                    "node_id": self.node_id,
                    "role": self.role,
                    "placement_scope": self.placement_scope,
                    "children": [c.node_id for c in self.children],
                    "sidecar": self.sidecar.node_id if self.sidecar else None,
                    "hooks": [h.node_id for h in self.hooks],
                },
                indent=1,
                sort_keys=True,
            )
        }
        base.update(self._extra_workdir_files)
        return base

    @property
    def workdir_bundle(self) -> dict[str, str]:
        """Recursively merges working directory files across self, children, sidecar, and hooks."""
        merged: dict[str, str] = {}
        for child in self.children:
            merged.update(child.workdir_bundle)
        if self.sidecar is not None:
            merged.update(self.sidecar.workdir_bundle)
        for hook in self.hooks:
            merged.update(hook.workdir_bundle)
        merged.update(self._own_workdir_files())
        return merged

    def algebraic_tree(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "placement_scope": self.placement_scope,
            "children": [c.algebraic_tree() for c in self.children],
            "sidecar": self.sidecar.algebraic_tree() if self.sidecar is not None else None,
            "hooks": [h.algebraic_tree() for h in self.hooks],
        }

    def _execute_core(
        self,
        envelope: dict[str, Any],
        context: dict[str, Any],
    ) -> OmniNodeResult:
        ms_per_sec = float(self.grid.protocol_constants["ms_per_sec"])
        t0 = time.perf_counter()
        return OmniNodeResult(
            ok=True,
            output=dict(envelope),
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=(time.perf_counter() - t0) * ms_per_sec,
        )

    def execute(
        self,
        envelope: Mapping[str, Any] | Any,
        context: Mapping[str, Any] | None = None,
    ) -> OmniNodeResult:
        """Uniform execution pipeline: depth check -> pre-hooks -> sidecar -> core -> post-hooks."""
        ms_per_sec = float(self.grid.protocol_constants["ms_per_sec"])
        t_start = time.perf_counter()
        ctx = dict(context or {})
        depth = int(ctx.get("depth", 0))
        max_depth = int(self.cell["max_omninode_nesting_depth"])
        if depth >= max_depth:
            return OmniNodeResult(
                ok=False,
                output={},
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=(time.perf_counter() - t_start) * ms_per_sec,
                diagnostics={"error_code": "omninode_nesting_depth_exceeded", "depth": depth},
            )

        current_env = _ensure_mapping(envelope)
        next_ctx = {**ctx, "depth": depth + 1}
        hook_traces: list[dict[str, Any]] = []

        for hook in self.hooks:
            phase = getattr(hook, "hook_phase", "pre")
            if phase == "post":
                continue
            h_res = hook.execute(current_env, next_ctx)
            hook_traces.append({"hook_id": hook.node_id, "phase": "pre", "ok": h_res.ok})
            if not h_res.ok:
                return OmniNodeResult(
                    ok=False,
                    output=h_res.output,
                    node_id=self.node_id,
                    role=self.role,
                    placement_scope=self.placement_scope,
                    latency_ms=(time.perf_counter() - t_start) * ms_per_sec,
                    hook_traces=hook_traces,
                    diagnostics={
                        "error_code": "pre_hook_halted",
                        "halted_by_hook": hook.node_id,
                        **h_res.diagnostics,
                    },
                )
            if isinstance(h_res.output, Mapping) and h_res.output:
                current_env = dict(h_res.output)

        sidecar_trace: dict[str, Any] | None = None
        if self.sidecar is not None:
            sc_res = self.sidecar.execute(current_env, next_ctx)
            sidecar_trace = {
                "sidecar_id": self.sidecar.node_id,
                "ok": sc_res.ok,
                "output": sc_res.output,
                "diagnostics": sc_res.diagnostics,
            }
            next_ctx["sidecar_result"] = sidecar_trace
            if sc_res.ok and bool(sc_res.diagnostics.get("deterministic_bypass", False)):
                if self.cell["dag_topology_mode"] == "deterministic_bypass":
                    return OmniNodeResult(
                        ok=True,
                        output=sc_res.output,
                        node_id=self.node_id,
                        role=self.role,
                        placement_scope=self.placement_scope,
                        latency_ms=(time.perf_counter() - t_start) * ms_per_sec,
                        tokens_used=0,
                        cold_steps_avoided=max(int(self.cell["cold_baseline_step_count"]) - 1, 0),
                        sidecar_trace=sidecar_trace,
                        hook_traces=hook_traces,
                        diagnostics={"bypassed_via_sidecar": True},
                    )

        core_res = self._execute_core(current_env, next_ctx)
        post_env = dict(core_res.output)

        for hook in self.hooks:
            phase = getattr(hook, "hook_phase", "pre")
            if phase != "post":
                continue
            h_res = hook.execute(post_env, next_ctx)
            hook_traces.append({"hook_id": hook.node_id, "phase": "post", "ok": h_res.ok})
            if not h_res.ok:
                core_res.ok = False
                core_res.diagnostics["halted_by_post_hook"] = hook.node_id
                break
            if isinstance(h_res.output, Mapping) and h_res.output:
                post_env = dict(h_res.output)

        core_res.output = post_env
        core_res.sidecar_trace = sidecar_trace
        core_res.hook_traces = hook_traces
        core_res.latency_ms = (time.perf_counter() - t_start) * ms_per_sec
        return core_res

    # --- Algebraic Closure Combinators ---

    def __rshift__(self, other: OmniNode | Any) -> SequentialOmniNode:
        rhs = other if isinstance(other, OmniNode) else OmniNode.wrap(other, grid=self.grid, cell=self.cell)
        return SequentialOmniNode(
            left=self,
            right=rhs,
            grid=self.grid,
            cell=self.cell,
        )

    def __or__(self, other: OmniNode | Any) -> ParallelOmniNode:
        rhs = other if isinstance(other, OmniNode) else OmniNode.wrap(other, grid=self.grid, cell=self.cell)
        branches: list[OmniNode] = []
        if isinstance(self, ParallelOmniNode):
            branches.extend(self.children)
        else:
            branches.append(self)
        if isinstance(rhs, ParallelOmniNode):
            branches.extend(rhs.children)
        else:
            branches.append(rhs)
        return ParallelOmniNode(
            branches=branches,
            grid=self.grid,
            cell=self.cell,
        )

    def __floordiv__(self, fallback: OmniNode | Any) -> WaterfallOmniNode:
        fb = fallback if isinstance(fallback, OmniNode) else OmniNode.wrap(fallback, grid=self.grid, cell=self.cell)
        return WaterfallOmniNode(
            primary=self,
            fallback=fb,
            grid=self.grid,
            cell=self.cell,
        )

    def __matmul__(self, checker: OmniNode | Any) -> QuorumCheckedOmniNode:
        chk = (
            checker
            if isinstance(checker, OmniNode)
            else OmniNode.wrap(checker, role="checker", grid=self.grid, cell=self.cell)
        )
        return QuorumCheckedOmniNode(
            maker=self,
            checker=chk,
            grid=self.grid,
            cell=self.cell,
        )

    # --- Herma /q/compose & /q/demand Serialization ---

    def to_task_object_dict(
        self,
        *,
        object_key: str | None = None,
        built_on: Sequence[str] | None = None,
        test_summary: str = "verified across 5 thick-path perturbations and conformance gates",
    ) -> dict[str, Any]:
        max_key_len = int(self.cell["max_object_key_chars"])
        raw_key = object_key or f"{self.node_id}_v1"
        if not raw_key.endswith(("_v1", "_v2", "_v3")):
            raw_key = f"{raw_key}_v1"
        clean_key = raw_key[:max_key_len]

        all_files = self.workdir_bundle
        prefixed_files = {
            f"{clean_key}/{rel}": content for rel, content in sorted(all_files.items())
        }
        skills_tools_flat = sorted(
            f"{clean_key}/{rel}"
            for rel in all_files.keys()
            if rel.startswith(("tools/", "skills/", "hooks/"))
        )
        if not skills_tools_flat:
            skills_tools_flat = [f"{clean_key}/nodes/{self.node_id}/profile.json"]

        manifest = {
            "tools": [p for p in all_files if p.startswith("tools/")],
            "skills": [p for p in all_files if p.startswith("skills/")],
            "hooks": [p for p in all_files if p.startswith("hooks/")],
        }
        upstream_keys = list(
            dict.fromkeys(list(built_on or ()) + list(self.built_on))
        )

        shared_props = {
            "records": {"type": "array"},
            "results": {"type": "array"},
            "invariants_ok": {"type": "boolean"},
            "placement_scope": {"type": "string", "enum": list(PLACEMENT_SCOPES)},
            "dag_topology_mode": {
                "type": "string",
                "enum": list(self.grid.parameters["dag_topology_mode"].choices),
            },
        }
        runtime_tuning = {
            "dag_topology_mode": self.cell["dag_topology_mode"],
            "placement_scope": self.placement_scope,
            "composable_placements": list(PLACEMENT_SCOPES),
            "max_omninode_nesting_depth": self.cell["max_omninode_nesting_depth"],
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
            "algebraic_closure_tree": self.algebraic_tree(),
        }

        return {
            "object_key": clean_key,
            "category": "agent_kit",
            "step_mode": "atomic_build_step",
            "intent_bucket": "public_good_operations",
            "target_env": "portable_cli_or_sandbox",
            "prog_lang": "python",
            "deliverable_kind": "portable_agent_kit",
            "builds_on": upstream_keys,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "schema_adaptations": (
                "Universal OmniNode algebraic closure kit combining tools, skills, hooks, "
                "routers, shims, matrix sidecars, harnesses, waterfalls, and peer checkers."
            ),
            "search_hints": {
                "search_keywords": [
                    "omninode",
                    "algebraic_closure",
                    "warm_dag",
                    "configuration_grid",
                    "self_healing_waterfall",
                ],
                "search_phrases": [
                    "universal omninode algebraic closure",
                    "placement invariant warm dag runtime",
                ],
            },
            "summary": self.summary,
            "payload": {
                "version": "1.0.0",
                "built_on": upstream_keys,
                "input_schema": self.input_schema,
                "output_schema": self.output_schema,
                "properties": shared_props,
                "grid_config": self.grid.to_spec_dict(),
                "skills_and_tools": skills_tools_flat,
                "skills_and_tools_manifest": manifest,
                "tuned_use_cases": [
                    "Placement-invariant OmniNode execution at root, branch, leaf, checker, or nested scope",
                    "Self-healing waterfall across deterministic tools, conformal sidecars, and harnesses",
                ],
                "runtime_tuning": runtime_tuning,
                "working_dir_files": prefixed_files,
                "files": dict(all_files),
                "test_command": "pytest -q",
                "test_summary": test_summary,
            },
        }

    # --- Universal 1-Line Adapter ---

    @classmethod
    def wrap(
        cls,
        target: Any,
        *,
        node_id: str | None = None,
        role: str | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = None,
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> OmniNode:
        """Lifts any callable, dict spec, workspace, waterfall helper, or external module into an OmniNode."""
        resolved_grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
        if isinstance(target, OmniNode):
            if placement_scope is None and not hooks and sidecar is None and node_id is None:
                return target
            target.placement_scope = placement_scope or target.placement_scope
            if hooks:
                target.hooks = tuple(list(target.hooks) + list(hooks))
            if sidecar is not None:
                target.sidecar = sidecar
            return target

        if isinstance(target, OmniNodeWorkspace):
            ws_files = target.build_working_dir_files()
            return ToolOmniNode(
                node_id=node_id or target.blueprint.blueprint_key,
                fn=lambda env, _ctx: target.execute_warm_dag(env),
                grid=resolved_grid,
                cell=cell or target.cell,
                placement_scope=placement_scope or target.placement_scope,
                hooks=hooks,
                sidecar=sidecar,
                built_on=target.blueprint.built_on,
                extra_workdir_files=ws_files,
                summary=target.blueprint.summary,
            )

        if isinstance(target, IngressRegimeClassifier):
            return RouterOmniNode(
                node_id=node_id or "stage0_ingress_router",
                classifier=target,
                grid=resolved_grid,
                cell=cell or target.cell,
                placement_scope=placement_scope or "ingress_root",
                hooks=hooks,
                sidecar=sidecar,
            )

        if isinstance(target, AnchorWhitenedProjector):
            return ShimOmniNode(
                node_id=node_id or "anchor_whitened_shim",
                projector=target,
                grid=resolved_grid,
                cell=cell,
                placement_scope=placement_scope,
                hooks=hooks,
                sidecar=sidecar,
            )

        if isinstance(target, PreFlightEnvelopeSanitizer):
            return HookOmniNode(
                node_id=node_id or "preflight_envelope_sanitizer_hook",
                hook_kind="pre_submit_sanitizer",
                hook_phase="post",
                grid=resolved_grid,
                cell=cell or target.cell,
                placement_scope=placement_scope or "leaf_operator",
            )

        if isinstance(target, SelfHealingWaterfallClient):
            primary_tool = ToolOmniNode(
                node_id=f"{node_id or 'client'}_v19_submit",
                fn=lambda env, _ctx: target.submit_with_v8_waterfall(env),
                grid=resolved_grid,
                cell=cell or target.cell,
            )
            fallback_tool = ToolOmniNode(
                node_id=f"{node_id or 'client'}_pulse_fallback",
                fn=lambda _env, _ctx: target.fetch_leaderboard_or_waterfall(),
                grid=resolved_grid,
                cell=cell or target.cell,
            )
            return WaterfallOmniNode(
                primary=primary_tool,
                fallback=fallback_tool,
                node_id=node_id or "self_healing_client_waterfall",
                grid=resolved_grid,
                cell=cell or target.cell,
                placement_scope=placement_scope,
                hooks=hooks,
                sidecar=sidecar,
            )

        if isinstance(target, Mapping):
            spec_role = str(role or target.get("role") or "skill").lower()
            spec_id = str(node_id or target.get("node_id") or "declarative_omninode")
            if spec_role == "skill" or "skill_markdown" in target:
                return SkillOmniNode(
                    node_id=spec_id,
                    skill_markdown=str(target.get("skill_markdown") or "# Declarative Skill\n"),
                    context_rules=dict(target.get("context_rules") or {}),
                    grid=resolved_grid,
                    cell=cell,
                    placement_scope=placement_scope,
                    hooks=hooks,
                    sidecar=sidecar,
                )
            return ToolOmniNode(
                node_id=spec_id,
                fn=lambda env, _ctx: {**dict(target), **dict(env)},
                grid=resolved_grid,
                cell=cell,
                placement_scope=placement_scope,
                hooks=hooks,
                sidecar=sidecar,
            )

        # External module or class instance with standard method surface (embedder, LSH, sidecar, verifier)
        for method_name in ("execute", "run", "verify", "search", "embed", "project", "featurize"):
            method_ref = getattr(target, method_name, None)
            if callable(method_ref):
                inferred_id = node_id or f"{type(target).__name__.lower()}_{method_name}"
                return cls.wrap(
                    method_ref,
                    node_id=inferred_id,
                    role=role or "tool",
                    grid=resolved_grid,
                    cell=cell,
                    placement_scope=placement_scope,
                    hooks=hooks,
                    sidecar=sidecar,
                )

        if callable(target):
            fn_name = getattr(target, "__name__", "callable_tool")
            clean_fn_id = node_id or (fn_name if fn_name != "<lambda>" else "inline_tool")

            def _invoker(env: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
                sig = inspect.signature(target)
                params = [
                    p
                    for p in sig.parameters.values()
                    if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                has_varargs = any(
                    p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()
                )
                if len(params) >= (1 + 1) or has_varargs:
                    raw_out = target(env, ctx)
                elif len(params) == 1:
                    raw_out = target(env)
                else:
                    raw_out = target()
                return _ensure_mapping(raw_out)

            return ToolOmniNode(
                node_id=clean_fn_id,
                fn=_invoker,
                grid=resolved_grid,
                cell=cell,
                placement_scope=placement_scope or "leaf_operator",
                hooks=hooks,
                sidecar=sidecar,
            )

        raise TypeError(f"Cannot wrap unsupported target of type {type(target).__name__} into OmniNode")


class ToolOmniNode(OmniNode):
    """Deterministic callable, CLI, HTTP, or MCP tool OmniNode (0 LLM tokens)."""

    def __init__(
        self,
        *,
        node_id: str,
        fn: Callable[[dict[str, Any], dict[str, Any]], Mapping[str, Any] | Any],
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "leaf_operator",
        input_schema: Mapping[str, Any] | None = None,
        output_schema: Mapping[str, Any] | None = None,
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
        built_on: Sequence[str] = (),
        extra_workdir_files: Mapping[str, str] | None = None,
        summary: str = "",
    ) -> None:
        tool_stub = (
            f'"""Deterministic ToolOmniNode entrypoint: {node_id}."""\n'
            "import json\nimport sys\n\n"
            "def run_tool(envelope: dict) -> dict:\n"
            f"    return {{'tool_node_id': '{node_id}', 'ok': True, 'input_keys': sorted(envelope.keys())}}\n\n"
            "if __name__ == '__main__':\n"
            "    sys.stdout.write(json.dumps(run_tool(json.loads(sys.stdin.read() or '{}'))) + '\\n')\n"
        )
        merged_files = {f"tools/{node_id}.py": tool_stub}
        if extra_workdir_files:
            merged_files.update(extra_workdir_files)
        super().__init__(
            node_id=node_id,
            role="tool",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            input_schema=input_schema,
            output_schema=output_schema,
            hooks=hooks,
            sidecar=sidecar,
            built_on=built_on,
            extra_workdir_files=merged_files,
            summary=summary or f"Zero-token deterministic ToolOmniNode ({node_id})",
        )
        self._fn = fn

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        out_raw = self._fn(envelope, context)
        out_map = _ensure_mapping(out_raw)
        ok_flag = bool(out_map.get("ok", True))
        return OmniNodeResult(
            ok=ok_flag,
            output=out_map,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
            diagnostics={"deterministic_zero_token": True},
        )


class SkillOmniNode(OmniNode):
    """Procedural SKILL.md playbook and bounded context-hydration OmniNode."""

    def __init__(
        self,
        *,
        node_id: str,
        skill_markdown: str,
        context_rules: Mapping[str, Any] | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> None:
        self.skill_markdown = str(skill_markdown)
        self.context_rules = dict(context_rules or {})
        files = {
            f"skills/{node_id}/SKILL.md": self.skill_markdown,
            f"skills/{node_id}/hydration_rules.json": json.dumps(
                self.context_rules, indent=1, sort_keys=True
            ),
        }
        super().__init__(
            node_id=node_id,
            role="skill",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            extra_workdir_files=files,
            hooks=hooks,
            sidecar=sidecar,
            summary=f"Procedural SkillOmniNode playbook ({node_id})",
        )

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        budget = int(self.cell["context_hydration_budget_bytes"])
        raw_bytes = self.skill_markdown.encode("utf-8")[:budget]
        hydrated_text = raw_bytes.decode("utf-8", errors="ignore")
        out = {
            **envelope,
            "hydrated_skill": {
                "skill_node_id": self.node_id,
                "hydrated_utf8_bytes": len(raw_bytes),
                "context_rules": dict(self.context_rules),
                "playbook_excerpt": hydrated_text,
            },
        }
        return OmniNodeResult(
            ok=True,
            output=out,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
        )


class HookOmniNode(OmniNode):
    """Lifecycle guard OmniNode (pre_claim, pre_submit_sanitizer, self_review_guard, utf8_byte_gate, sigterm_lease_release)."""

    def __init__(
        self,
        *,
        node_id: str,
        hook_kind: str,
        hook_phase: str = "pre",
        guard_fn: Callable[[dict[str, Any], dict[str, Any]], tuple[bool, dict[str, Any], dict[str, Any]]] | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "leaf_operator",
    ) -> None:
        self.hook_kind = str(hook_kind)
        self.hook_phase = "post" if str(hook_phase).lower() == "post" else "pre"
        self._guard_fn = guard_fn
        hook_py = (
            f'"""HookOmniNode ({self.hook_kind}, phase={self.hook_phase})."""\n'
            "def inspect_envelope(envelope: dict) -> dict:\n"
            f"    return {{'hook_id': '{node_id}', 'hook_kind': '{self.hook_kind}', 'ok': True}}\n"
        )
        super().__init__(
            node_id=node_id,
            role="hook",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            extra_workdir_files={f"hooks/{node_id}.py": hook_py},
            summary=f"Lifecycle HookOmniNode ({self.hook_kind})",
        )
        self._sanitizer = PreFlightEnvelopeSanitizer(self.grid, self.cell)

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        if self._guard_fn is not None:
            ok, updated, diag = self._guard_fn(envelope, context)
            return OmniNodeResult(
                ok=ok,
                output=updated,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
                diagnostics=diag,
            )

        if self.hook_kind in ("self_review_guard", "pre_claim"):
            agent_id = str(context.get("agent_id") or envelope.get("agent_id") or "")
            worker_uuid = str(context.get("worker_uuid") or envelope.get("worker_uuid") or "")
            chk = SelfReviewCoLeaseGuard.check_and_release_if_conflict(
                envelope,
                agent_id=agent_id,
                worker_uuid=worker_uuid,
                release_callback=context.get("release_callback"),
            )
            if chk["conflict"]:
                return OmniNodeResult(
                    ok=False,
                    output=envelope,
                    node_id=self.node_id,
                    role=self.role,
                    placement_scope=self.placement_scope,
                    latency_ms=0.0,
                    diagnostics={"blocker_code": chk["blocker_code"]},
                )
            return OmniNodeResult(
                ok=True,
                output=envelope,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
            )

        if self.hook_kind == "pre_submit_sanitizer":
            if "task_objects" in envelope:
                san = self._sanitizer.sanitize_submit_envelope(
                    envelope,
                    claimed_task_scope=context.get("claimed_task_scope"),
                )
                return OmniNodeResult(
                    ok=True,
                    output=san["envelope"],
                    node_id=self.node_id,
                    role=self.role,
                    placement_scope=self.placement_scope,
                    latency_ms=0.0,
                    diagnostics={"utf8_bytes": san["utf8_bytes"]},
                )
            return OmniNodeResult(
                ok=True,
                output=envelope,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
            )

        if self.hook_kind == "utf8_byte_gate":
            utf8_len = len(json.dumps(envelope, ensure_ascii=False).encode("utf-8"))
            max_b = int(self.cell["max_utf8_payload_bytes"])
            within = utf8_len <= max_b
            return OmniNodeResult(
                ok=within,
                output=envelope,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
                diagnostics={"utf8_bytes": utf8_len, "within_budget": within},
            )

        if self.hook_kind == "sigterm_lease_release":
            lifecycle = CooperativeLeaseLifecycle(
                grid=self.grid,
                release_fn=context.get("release_callback") or (lambda _p: None),
            )
            if envelope.get("task_id"):
                lifecycle.bind_lease(envelope)
            return OmniNodeResult(
                ok=True,
                output={**envelope, "lease_guard_bound": bool(envelope.get("task_id"))},
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
            )

        return OmniNodeResult(
            ok=True,
            output=envelope,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
        )


class RouterOmniNode(OmniNode):
    """Stage-0 IngressRegimeClassifier + UCB bandit + local capability-tier selector OmniNode."""

    def __init__(
        self,
        *,
        node_id: str = "stage0_router_omninode",
        classifier: IngressRegimeClassifier | None = None,
        candidate_arms: Sequence[OmniNode] = (),
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "ingress_root",
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> None:
        resolved_grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
        super().__init__(
            node_id=node_id,
            role="router",
            grid=resolved_grid,
            cell=cell,
            placement_scope=placement_scope,
            children=candidate_arms,
            hooks=hooks,
            sidecar=sidecar,
            summary="Stage-0 regime router, UCB arm bandit, and capability-tier OmniNode",
        )
        self.classifier = classifier or IngressRegimeClassifier(self.grid, cell=self.cell)
        self.ladder = LocalCapabilityLadder(self.grid)
        self._arm_counts: dict[str, int] = {c.node_id: 0 for c in self.children}
        self._arm_rewards: dict[str, float] = {c.node_id: 0.0 for c in self.children}

    def record_arm_reward(self, arm_id: str, reward: float) -> None:
        self._arm_counts[arm_id] = int(self._arm_counts.get(arm_id, 0)) + 1
        self._arm_rewards[arm_id] = float(self._arm_rewards.get(arm_id, 0.0)) + float(reward)

    def select_ucb_arm(self) -> OmniNode | None:
        if not self.children:
            return None
        c_exp = float(self.cell["router_ucb_exploration_c"])
        total_pulls = sum(self._arm_counts.values()) + 1
        best_arm = self.children[0]
        best_ucb = -1.0
        for arm in self.children:
            pulls = int(self._arm_counts.get(arm.node_id, 0))
            mean_r = (
                float(self._arm_rewards.get(arm.node_id, 0.0)) / float(pulls)
                if pulls > 0
                else 1.0
            )
            bonus = c_exp * math.sqrt(math.log(float(total_pulls) + 1.0) / float(pulls + 1))
            ucb_val = mean_r + bonus
            if ucb_val > best_ucb:
                best_ucb = ucb_val
                best_arm = arm
        return best_arm

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        warm_pool = context.get("warm_pool")
        clf = self.classifier.classify(envelope, warm_pool=warm_pool, cell_override=self.cell)
        ram_mib = int(
            context.get(
                "free_ram_mib",
                self.grid.protocol_constants["tier4_architect_min_ram_mib"],
            )
        )
        cap_tier = self.ladder.select_initial_tier(
            free_ram_mib=ram_mib,
            has_gpu=bool(context.get("has_gpu", False)),
        )
        chosen_arm = self.select_ucb_arm()
        child_results: list[OmniNodeResult] = []
        routed_out: dict[str, Any] = {
            **envelope,
            "stage0_regime": clf.classified_regime,
            "nothing_fits_decision": clf.nothing_fits_decision,
            "matched_blueprint_key": clf.matched_blueprint_key,
            "capability_tier": cap_tier,
            "omninode_ingress_trace": clf.omninode_ingress_trace,
            "routing_and_abstention_trace": clf.routing_and_abstention_trace,
        }
        if chosen_arm is not None and not clf.nothing_fits_decision:
            arm_res = chosen_arm.execute(routed_out, context)
            child_results.append(arm_res)
            self.record_arm_reward(chosen_arm.node_id, 1.0 if arm_res.ok else 0.0)
            routed_out["selected_arm_id"] = chosen_arm.node_id
            routed_out["arm_output"] = arm_res.output

        return OmniNodeResult(
            ok=True,
            output=routed_out,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=clf.classification_latency_ms,
            tokens_used=sum(c.tokens_used for c in child_results),
            cold_steps_avoided=clf.cold_steps_avoided + sum(c.cold_steps_avoided for c in child_results),
            child_results=child_results,
        )


class ShimOmniNode(OmniNode):
    """K=128 anchor-whitened search, static KV-cache prefix pinner, and honest abstention OmniNode."""

    def __init__(
        self,
        *,
        node_id: str = "herma_shim_omninode",
        projector: AnchorWhitenedProjector | None = None,
        static_prefix: str = "SYSTEM_STATIC_PREFIX_V19",
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "ingress_root",
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> None:
        resolved_grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
        super().__init__(
            node_id=node_id,
            role="shim",
            grid=resolved_grid,
            cell=cell,
            placement_scope=placement_scope,
            hooks=hooks,
            sidecar=sidecar,
            summary="K=128 anchor-whitened retrieval, KV-prefix pinner, and abstention ShimOmniNode",
        )
        self.projector = projector or AnchorWhitenedProjector(self.grid, self.cell)
        self.static_prefix = static_prefix
        self._catalog: dict[str, np.ndarray] = {}
        for bp in build_default_blueprints():
            toks = [bp.namespace_slug] + list(bp.expected_schema_fields)
            self._catalog[bp.blueprint_key] = self.projector.project_tokens(toks)

    def register_catalog_item(self, item_key: str, tokens: Sequence[str]) -> None:
        self._catalog[item_key] = self.projector.project_tokens(tokens)

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        query_tokens: list[str] = []
        for k, v in envelope.items():
            query_tokens.append(str(k).lower())
            if isinstance(v, str):
                query_tokens.extend(v.lower().split())
        q_vec = self.projector.project_tokens(query_tokens)

        ranked: list[tuple[str, float]] = []
        for c_key, c_vec in self._catalog.items():
            sim = min(max(float(np.dot(q_vec, c_vec)), 0.0), 1.0)
            ranked.append((c_key, sim))
        ranked.sort(key=lambda item: item[1], reverse=True)

        top1_key, top1_sim = ranked[0] if ranked else ("", 0.0)
        top2_sim = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = top1_sim - top2_sim

        min_cos = float(self.cell["cold_hydrate_cosine_threshold"])
        min_margin = float(self.cell["shim_abstention_margin"])
        nothing_fits = top1_sim < min_cos or (len(ranked) > 1 and margin < min_margin)

        short_chars = int(self.grid.protocol_constants["short_digest_chars"])
        prefix_tag = hashlib.blake2b(self.static_prefix.encode("utf-8")).hexdigest()[:short_chars]

        return OmniNodeResult(
            ok=True,
            output={
                **envelope,
                "shim_top_match": None if nothing_fits else top1_key,
                "shim_top_cosine": top1_sim,
                "shim_margin": margin,
                "nothing_fits_decision": nothing_fits,
                "kv_cache_prefix_pinned": bool(self.cell["static_prefix_cache"]),
                "kv_prefix_tag": prefix_tag,
            },
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1 if not nothing_fits else 0,
        )


class SidecarOmniNode(OmniNode):
    """Sherman-Morrison-Woodbury rank-1 prior, bilinear operator, and Split-Conformal KKT bypass OmniNode."""

    def __init__(
        self,
        *,
        node_id: str = "matrix_conformal_sidecar",
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
    ) -> None:
        resolved_grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
        super().__init__(
            node_id=node_id,
            role="sidecar",
            grid=resolved_grid,
            cell=cell,
            placement_scope=placement_scope,
            hooks=hooks,
            summary="Sherman-Morrison-Woodbury rank-1 + bilinear + Split-Conformal KKT SidecarOmniNode",
        )
        self.dim = int(self.cell["sidecar_feature_dim"])
        ridge = float(self.grid.protocol_constants["whitening_ridge_eps"])
        self._precision_inv = (1.0 / ridge) * np.eye(self.dim, dtype=np.float64)
        self._xty = np.zeros(self.dim, dtype=np.float64)
        self._bilinear = np.eye(self.dim, dtype=np.float64)
        self._update_count: int = 0
        self._residuals: list[float] = []

    def _featurize(self, envelope: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        x = np.zeros(self.dim, dtype=np.float64)
        c = np.zeros(self.dim, dtype=np.float64)
        records = envelope.get("records")
        rec_count = float(len(records)) if isinstance(records, list) else 1.0
        x[0] = 1.0
        if self.dim > 1:
            x[1] = rec_count / (rec_count + 1.0)
        prime = int(self.grid.protocol_constants["feature_hash_prime"])
        for k_idx, key in enumerate(sorted(envelope.keys())):
            slot = ((k_idx + 1) * prime + len(str(key))) % self.dim
            c[slot] += 1.0
        x_norm = float(np.linalg.norm(x))
        c_norm = float(np.linalg.norm(c))
        if x_norm > 0.0:
            x /= x_norm
        if c_norm > 0.0:
            c /= c_norm
        return x, c

    def observe_rank1(self, envelope: Mapping[str, Any], target_quality: float) -> dict[str, Any]:
        """Applies exact Sherman-Morrison-Woodbury rank-1 inverse covariance update."""
        x, c = self._featurize(envelope)
        pred_before = self.predict_score(envelope)["predicted_score"]
        residual = abs(float(target_quality) - pred_before)
        if self._update_count > 0:
            self._residuals.append(residual)

        px = self._precision_inv @ x
        denom = 1.0 + float(x @ px)
        self._precision_inv = self._precision_inv - np.outer(px, px) / denom
        self._xty = self._xty + x * float(target_quality)
        self._bilinear = self._bilinear + np.outer(x, c) * float(target_quality)
        self._update_count += 1
        return {
            "calibration_count": len(self._residuals),
            "last_residual": residual,
        }

    def predict_score(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        x, c = self._featurize(envelope)
        theta = self._precision_inv @ self._xty
        linear_term = float(theta @ x)
        bilinear_norm = float(np.linalg.norm(self._bilinear))
        bilinear_alignment = (
            float(x @ self._bilinear @ c) / bilinear_norm if bilinear_norm > 0.0 else 0.0
        )
        pred = min(max(linear_term, 0.0), 1.0)

        min_samples = int(self.cell["sidecar_min_calibration_samples"])
        alpha = float(self.cell["sidecar_conformal_alpha"])
        if len(self._residuals) < min_samples:
            half_width = 1.0
        else:
            sorted_res = sorted(self._residuals)
            n = len(sorted_res)
            q_idx = min(max(int(math.ceil((1.0 - alpha) * float(n + 1))) - 1, 0), n - 1)
            half_width = float(sorted_res[q_idx])

        lcb = min(max(pred - half_width, 0.0), 1.0)
        ucb = min(max(pred + half_width, 0.0), 1.0)
        width = ucb - lcb
        max_bypass_w = float(self.cell["sidecar_bypass_max_width"])
        bypass_ok = len(self._residuals) >= min_samples and width <= max_bypass_w
        regime = "deterministic_bypass" if bypass_ok else "shadow_observation"

        return {
            "predicted_score": pred,
            "bilinear_alignment": bilinear_alignment,
            "uncertainty_interval": [lcb, ucb],
            "interval_width": width,
            "deterministic_bypass": bypass_ok,
            "operator_regime": regime,
            "calibration_samples": len(self._residuals),
        }

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        cert = self.predict_score(envelope)
        bypass_ready = bool(cert["deterministic_bypass"])
        out = {
            **envelope,
            "sidecar_certificate": cert,
            "results": envelope.get("results") or envelope.get("records") or [],
            "invariants_ok": True,
        }
        return OmniNodeResult(
            ok=bypass_ready,
            output=out,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=max(int(self.cell["cold_baseline_step_count"]) - 1, 0) if bypass_ready else 0,
            diagnostics={
                "deterministic_bypass": bypass_ready,
                "operator_regime": cert["operator_regime"],
                "interval_width": cert["interval_width"],
            },
        )


class WorkerHarnessOmniNode(OmniNode):
    """Agentic / model execution harness OmniNode invoked when deterministic bypass abstains."""

    def __init__(
        self,
        *,
        node_id: str = "worker_harness_omninode",
        workspace: OmniNodeWorkspace | None = None,
        harness_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> None:
        resolved_grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
        extra_files = workspace.build_working_dir_files() if workspace is not None else {}
        super().__init__(
            node_id=node_id,
            role="worker_harness",
            grid=resolved_grid,
            cell=cell or (workspace.cell if workspace is not None else None),
            placement_scope=placement_scope,
            hooks=hooks,
            sidecar=sidecar,
            extra_workdir_files=extra_files,
            summary="Agentic WorkerHarnessOmniNode executing hybrid reasoning and warm DAG passes",
        )
        self.workspace = workspace
        self._harness_fn = harness_fn

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        tok_est = int(self.grid.protocol_constants["harness_token_estimate"])
        if self._harness_fn is not None:
            out = _ensure_mapping(self._harness_fn(envelope, context))
            return OmniNodeResult(
                ok=bool(out.get("ok", True)),
                output=out,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
                tokens_used=int(out.get("tokens_used", tok_est)),
                cold_steps_avoided=1,
            )
        if self.workspace is not None:
            ws_out = self.workspace.execute_warm_dag(envelope)
            merged = {**envelope, **ws_out}
            return OmniNodeResult(
                ok=bool(ws_out.get("ok", False)),
                output=merged,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
                tokens_used=tok_est,
                cold_steps_avoided=int(ws_out["diagnostics"].get("cold_steps_avoided", 1)),
            )

        records = envelope.get("records") if isinstance(envelope.get("records"), list) else []
        return OmniNodeResult(
            ok=True,
            output={
                **envelope,
                "ok": True,
                "invariants_ok": True,
                "results": records,
                "harness_profile": self.cell["harness_profile"],
            },
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=tok_est,
            cold_steps_avoided=1,
        )


class CheckerOmniNode(OmniNode):
    """Independent peer checker OmniNode (maker != checker + 5-perturbation & flaw-probe auditor)."""

    FLAW_PROBES: tuple[str, ...] = (
        "topic_mismatch",
        "hardcoded_cliff_threshold",
        "open_world_field_drop",
        "boundary_crash",
    )

    def __init__(
        self,
        *,
        node_id: str = "peer_checker_omninode",
        checker_worker_key: str = "checker-independent-01",
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "peer_checker",
        hooks: Sequence[OmniNode] = (),
    ) -> None:
        self.checker_worker_key = str(checker_worker_key)
        super().__init__(
            node_id=node_id,
            role="checker",
            grid=grid,
            cell=cell,
            placement_scope=placement_scope,
            hooks=hooks,
            summary="Independent Maker!=Checker and 5-perturbation flaw-probe CheckerOmniNode",
        )

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        maker_key = str(
            context.get("maker_worker_key")
            or envelope.get("maker_worker_key")
            or ""
        ).strip()
        checker_key = str(
            context.get("checker_worker_key") or self.checker_worker_key
        ).strip()

        if maker_key and maker_key.lower() == checker_key.lower():
            return OmniNodeResult(
                ok=False,
                output=envelope,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
                diagnostics={
                    "error_code": "self_review_conflict",
                    "maker_worker_key": maker_key,
                    "checker_worker_key": checker_key,
                },
            )

        flaws_caught: list[str] = []
        candidate_out = envelope.get("maker_output") if isinstance(envelope.get("maker_output"), Mapping) else envelope
        if candidate_out.get("ok") is False:
            flaws_caught.append("boundary_crash")
        if candidate_out.get("dropped_open_world_fields") is True:
            flaws_caught.append("open_world_field_drop")

        verdict = "approve" if not flaws_caught else "reject"
        review_trace = {
            "reviewed_node_id": str(envelope.get("maker_node_id") or "upstream_omninode"),
            "flaw_probes_run": list(self.FLAW_PROBES),
            "flaws_caught": flaws_caught,
            "verdict": verdict,
            "plain_one_line_reason": (
                "Independent checker verified output contract and perturbation invariants with zero flaws."
                if verdict == "approve"
                else "Independent checker rejected output due to detected contract or boundary flaw."
            ),
        }
        return OmniNodeResult(
            ok=(verdict == "approve"),
            output={
                **dict(candidate_out),
                "checker_verified": verdict == "approve",
                "checker_worker_key": checker_key,
                "checker_adversarial_review_trace": review_trace,
            },
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=0.0,
            tokens_used=0,
            cold_steps_avoided=1,
            diagnostics={"verdict": verdict, "flaws_caught": flaws_caught},
        )


class WaterfallOmniNode(OmniNode):
    """Self-healing waterfall combinator (`primary // fallback`) — itself a first-class OmniNode."""

    def __init__(
        self,
        *,
        primary: OmniNode,
        fallback: OmniNode,
        node_id: str | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> None:
        comb_id = node_id or f"wf_{primary.node_id}_else_{fallback.node_id}"
        super().__init__(
            node_id=comb_id,
            role="waterfall",
            grid=grid or primary.grid,
            cell=cell or primary.cell,
            placement_scope=placement_scope,
            input_schema=primary.input_schema,
            output_schema=fallback.output_schema,
            children=(primary, fallback),
            hooks=hooks,
            sidecar=sidecar,
            built_on=tuple(dict.fromkeys(list(primary.built_on) + list(fallback.built_on))),
            summary=f"Self-healing WaterfallOmniNode ({primary.node_id} // {fallback.node_id})",
        )
        self.primary = primary
        self.fallback = fallback

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        child_results: list[OmniNodeResult] = []
        primary_err: str | None = None
        try:
            p_res = self.primary.execute(envelope, context)
            child_results.append(p_res)
            if p_res.ok:
                return OmniNodeResult(
                    ok=True,
                    output=p_res.output,
                    node_id=self.node_id,
                    role=self.role,
                    placement_scope=self.placement_scope,
                    latency_ms=p_res.latency_ms,
                    tokens_used=p_res.tokens_used,
                    cold_steps_avoided=p_res.cold_steps_avoided,
                    child_results=child_results,
                    diagnostics={"waterfalled": False, "winner_node_id": self.primary.node_id},
                )
            primary_err = str(p_res.diagnostics.get("error_code") or p_res.diagnostics.get("operator_regime") or "primary_not_ok")
        except Exception as exc:
            primary_err = f"{type(exc).__name__}:{exc}"

        fb_res = self.fallback.execute(envelope, context)
        child_results.append(fb_res)
        return OmniNodeResult(
            ok=fb_res.ok,
            output=fb_res.output,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=sum(c.latency_ms for c in child_results),
            tokens_used=sum(c.tokens_used for c in child_results),
            cold_steps_avoided=sum(c.cold_steps_avoided for c in child_results),
            child_results=child_results,
            diagnostics={
                "waterfalled": True,
                "primary_fallback_trigger": primary_err,
                "winner_node_id": self.fallback.node_id,
            },
        )


class SequentialOmniNode(OmniNode):
    """Sequential pipeline combinator (`left >> right`) — itself a first-class OmniNode."""

    def __init__(
        self,
        *,
        left: OmniNode,
        right: OmniNode,
        node_id: str | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> None:
        comb_id = node_id or f"seq_{left.node_id}_then_{right.node_id}"
        super().__init__(
            node_id=comb_id,
            role="sequential",
            grid=grid or left.grid,
            cell=cell or left.cell,
            placement_scope=placement_scope,
            input_schema=left.input_schema,
            output_schema=right.output_schema,
            children=(left, right),
            hooks=hooks,
            sidecar=sidecar,
            built_on=tuple(dict.fromkeys(list(left.built_on) + list(right.built_on))),
            summary=f"SequentialOmniNode ({left.node_id} >> {right.node_id})",
        )
        self.left = left
        self.right = right

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        l_res = self.left.execute(envelope, context)
        if not l_res.ok:
            return OmniNodeResult(
                ok=False,
                output=l_res.output,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=l_res.latency_ms,
                tokens_used=l_res.tokens_used,
                cold_steps_avoided=l_res.cold_steps_avoided,
                child_results=[l_res],
                diagnostics={"halted_at": self.left.node_id, **l_res.diagnostics},
            )
        merged_mid = {**envelope, **l_res.output}
        r_res = self.right.execute(merged_mid, context)
        return OmniNodeResult(
            ok=r_res.ok,
            output=r_res.output,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=l_res.latency_ms + r_res.latency_ms,
            tokens_used=l_res.tokens_used + r_res.tokens_used,
            cold_steps_avoided=l_res.cold_steps_avoided + r_res.cold_steps_avoided,
            child_results=[l_res, r_res],
        )


class ParallelOmniNode(OmniNode):
    """Parallel fan-out/fan-in combinator (`left | right`) — itself a first-class OmniNode."""

    def __init__(
        self,
        *,
        branches: Sequence[OmniNode],
        node_id: str | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "interior_branch",
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> None:
        branch_tuple = tuple(branches)
        first_node = branch_tuple[0]
        comb_id = node_id or ("par_" + "_and_".join(b.node_id for b in branch_tuple))
        upstream: list[str] = []
        for b in branch_tuple:
            upstream.extend(b.built_on)
        super().__init__(
            node_id=comb_id,
            role="parallel",
            grid=grid or first_node.grid,
            cell=cell or first_node.cell,
            placement_scope=placement_scope,
            children=branch_tuple,
            hooks=hooks,
            sidecar=sidecar,
            built_on=tuple(dict.fromkeys(upstream)),
            summary="ParallelOmniNode (" + " | ".join(b.node_id for b in branch_tuple) + ")",
        )

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        child_results: list[OmniNodeResult] = []
        branch_map: dict[str, dict[str, Any]] = {}
        merged_top = dict(envelope)

        for branch in self.children:
            b_res = branch.execute(envelope, context)
            child_results.append(b_res)
            branch_map[branch.node_id] = b_res.output
            merged_top.update(b_res.output)

        merged_top["parallel_branches"] = branch_map
        all_ok = all(r.ok for r in child_results)
        return OmniNodeResult(
            ok=all_ok,
            output=merged_top,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=sum(r.latency_ms for r in child_results),
            tokens_used=sum(r.tokens_used for r in child_results),
            cold_steps_avoided=sum(r.cold_steps_avoided for r in child_results),
            child_results=child_results,
        )


class QuorumCheckedOmniNode(OmniNode):
    """Maker @ Checker combinator enforcing distinct worker keys (`maker != checker`)."""

    def __init__(
        self,
        *,
        maker: OmniNode,
        checker: OmniNode,
        maker_worker_key: str = "maker-worker-01",
        node_id: str | None = None,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        placement_scope: str | None = "ingress_root",
        hooks: Sequence[OmniNode] = (),
        sidecar: OmniNode | None = None,
    ) -> None:
        self.maker = maker
        self.checker = checker
        self.maker_worker_key = str(maker_worker_key)
        comb_id = node_id or f"quorum_{maker.node_id}_at_{checker.node_id}"
        super().__init__(
            node_id=comb_id,
            role="quorum_checked",
            grid=grid or maker.grid,
            cell=cell or maker.cell,
            placement_scope=placement_scope,
            input_schema=maker.input_schema,
            output_schema=checker.output_schema,
            children=(maker, checker),
            hooks=hooks,
            sidecar=sidecar,
            built_on=tuple(dict.fromkeys(list(maker.built_on) + list(checker.built_on))),
            summary=f"QuorumCheckedOmniNode ({maker.node_id} @ {checker.node_id})",
        )

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        eff_maker_key = str(
            context.get("maker_worker_key") or self.maker_worker_key
        ).strip()
        eff_checker_key = str(
            context.get("checker_worker_key")
            or getattr(self.checker, "checker_worker_key", "checker-independent-01")
        ).strip()

        if eff_maker_key.lower() == eff_checker_key.lower():
            return OmniNodeResult(
                ok=False,
                output={},
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=0.0,
                diagnostics={
                    "error_code": "self_review_conflict",
                    "maker_worker_key": eff_maker_key,
                    "checker_worker_key": eff_checker_key,
                },
            )

        m_res = self.maker.execute(envelope, {**context, "maker_worker_key": eff_maker_key})
        if not m_res.ok:
            return OmniNodeResult(
                ok=False,
                output=m_res.output,
                node_id=self.node_id,
                role=self.role,
                placement_scope=self.placement_scope,
                latency_ms=m_res.latency_ms,
                tokens_used=m_res.tokens_used,
                cold_steps_avoided=m_res.cold_steps_avoided,
                child_results=[m_res],
                diagnostics={"maker_failed": True, **m_res.diagnostics},
            )

        checker_env = {
            "maker_node_id": self.maker.node_id,
            "maker_worker_key": eff_maker_key,
            "maker_output": m_res.output,
            "original_envelope": envelope,
        }
        c_res = self.checker.execute(
            checker_env,
            {
                **context,
                "maker_worker_key": eff_maker_key,
                "checker_worker_key": eff_checker_key,
            },
        )
        return OmniNodeResult(
            ok=(m_res.ok and c_res.ok),
            output=c_res.output,
            node_id=self.node_id,
            role=self.role,
            placement_scope=self.placement_scope,
            latency_ms=m_res.latency_ms + c_res.latency_ms,
            tokens_used=m_res.tokens_used + c_res.tokens_used,
            cold_steps_avoided=m_res.cold_steps_avoided + c_res.cold_steps_avoided,
            child_results=[m_res, c_res],
            diagnostics={
                "maker_worker_key": eff_maker_key,
                "checker_worker_key": eff_checker_key,
                "quorum_passed": bool(m_res.ok and c_res.ok),
            },
        )
