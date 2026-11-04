"""Declarative NodeGrid, 7-stage GridLedger, Boundary Auto-Expansion, and Conformance Gates.

Implements:
- NodeParameter, ParameterBounds, NodeGrid, OperationCostLedger, GridLedger
- Boundary Auto-Expansion when empirical verified optima saturate grid axis bounds
- ZeroHardcodedValuesAstGate, DomainAgnosticNamingGate, SharedBannedWordsGate
"""

from __future__ import annotations

import os

import ast
import copy
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

CELL_LIFECYCLE_STATES: tuple[str, ...] = (
    "represented",
    "applicable",
    "proposed",
    "dispatched",
    "evaluated",
    "verified",
    "promoted",
)

DEFAULT_GRID_CONFIG_PATH: Path = (
    Path(__file__).resolve().parent.parent / "config" / "omninode_resilience_grid.json"
)

DEFAULT_BANNED_WORDS_PATH: Path = (
    Path(os.environ.get("TELEION_NOTES", "/nonexistent")) / "coordination-2026-10-31/rules/banned-words.json"
)

DEFAULT_FORBIDDEN_INDUSTRY_TOKENS: tuple[str, ...] = (
    "real_estate",
    "realestate",
    "insurance",
    "address_enricher",
    "mortgage",
    "healthcare",
    "fintech",
    "ecommerce",
    "hospitality",
    "realtor",
    "brokerage",
    "underwriting",
    "escrow",
    "clinic",
    "patient",
)


class ZeroHardcodedValuesAstGate:
    """Mechanical AST gate rejecting numeric literals outside canonical algebraic identities."""

    @staticmethod
    def scan_source(
        source_code: str,
        *,
        allowed_identities: Sequence[int | float] = (-1, 0, 1, -1.0, 0.0, 1.0),
        source_name: str = "<memory>",
    ) -> dict[str, Any]:
        allowed = {float(val) for val in allowed_identities}
        tree = ast.parse(source_code, filename=source_name)
        violations: list[dict[str, Any]] = []

        def _walk(node: ast.AST, in_annotation: bool) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                all_args = (
                    list(node.args.posonlyargs)
                    + list(node.args.args)
                    + list(node.args.kwonlyargs)
                    + ([node.args.vararg] if node.args.vararg else [])
                    + ([node.args.kwarg] if node.args.kwarg else [])
                )
                for arg in all_args:
                    if arg.annotation is not None:
                        _walk(arg.annotation, True)
                if node.returns is not None:
                    _walk(node.returns, True)
                for default_expr in list(node.args.defaults) + [
                    item for item in node.args.kw_defaults if item is not None
                ]:
                    _walk(default_expr, False)
                for stmt in node.body:
                    _walk(stmt, False)
                return
            if isinstance(node, ast.AnnAssign):
                _walk(node.annotation, True)
                if node.value is not None:
                    _walk(node.value, False)
                return
            if not in_annotation:
                if (
                    isinstance(node, ast.UnaryOp)
                    and isinstance(node.op, ast.USub)
                    and isinstance(node.operand, ast.Constant)
                    and isinstance(node.operand.value, (int, float))
                    and not isinstance(node.operand.value, bool)
                ):
                    neg_val = -node.operand.value
                    if float(neg_val) not in allowed:
                        violations.append(
                            {
                                "source": source_name,
                                "line": node.lineno,
                                "col": node.col_offset,
                                "literal": neg_val,
                            }
                        )
                    return
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, (int, float))
                    and not isinstance(node.value, bool)
                ):
                    if float(node.value) not in allowed:
                        violations.append(
                            {
                                "source": source_name,
                                "line": node.lineno,
                                "col": node.col_offset,
                                "literal": node.value,
                            }
                        )
            for child in ast.iter_child_nodes(node):
                _walk(child, in_annotation)

        _walk(tree, False)
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }

    @classmethod
    def scan_paths(
        cls,
        paths: Sequence[Path],
        *,
        allowed_identities: Sequence[int | float] = (-1, 0, 1, -1.0, 0.0, 1.0),
    ) -> dict[str, Any]:
        all_violations: list[dict[str, Any]] = []
        scanned = 0
        for path in sorted(paths):
            files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
            for py_file in files:
                if any(
                    part.startswith(".") or part == "__pycache__"
                    for part in py_file.parts
                ):
                    continue
                scanned += 1
                res = cls.scan_source(
                    py_file.read_text(encoding="utf-8"),
                    allowed_identities=allowed_identities,
                    source_name=py_file.name,
                )
                all_violations.extend(res["violations"])
        return {
            "passed": len(all_violations) == 0,
            "files_scanned": scanned,
            "violation_count": len(all_violations),
            "violations": all_violations,
        }


class DomainAgnosticNamingGate:
    """Mechanical naming gate rejecting narrow industry names and deprecated root-only terms."""

    _DEPRECATED_ROOT_ONLY_PATTERN = re.compile(r"super[_-]?node", re.IGNORECASE)

    @staticmethod
    def _split_tokens(identifier: str) -> list[str]:
        return [
            word.lower()
            for word in re.findall(
                r"[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|[A-Z]?[a-z]+|\d+", identifier
            )
        ]

    @classmethod
    def _matches_banned(cls, name: str, forbidden_tokens: Sequence[str]) -> str | None:
        if cls._DEPRECATED_ROOT_ONLY_PATTERN.search(str(name)):
            return "deprecated_root_only_node_term"
        words = cls._split_tokens(name)
        joined = "_".join(words)
        for raw_token in forbidden_tokens:
            tok = str(raw_token).lower()
            if tok in words or ("_" in tok and f"_{tok}_" in f"_{joined}_"):
                return tok
        return None

    @classmethod
    def scan_nomenclature_text(cls, text: str, *, source_name: str = "<memory>") -> dict[str, Any]:
        violations: list[dict[str, str]] = []
        for match in cls._DEPRECATED_ROOT_ONLY_PATTERN.finditer(text):
            violations.append(
                {
                    "source": source_name,
                    "identifier": match.group(0),
                    "token": "deprecated_root_only_node_term",
                }
            )
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }

    @classmethod
    def scan_source(
        cls,
        source_code: str,
        *,
        forbidden_tokens: Sequence[str] = DEFAULT_FORBIDDEN_INDUSTRY_TOKENS,
        source_name: str = "<memory>",
    ) -> dict[str, Any]:
        tree = ast.parse(source_code, filename=source_name)
        violations: list[dict[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                matched = cls._matches_banned(node.name, forbidden_tokens)
                if matched is not None:
                    violations.append(
                        {
                            "source": source_name,
                            "identifier": node.name,
                            "token": matched,
                        }
                    )
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }

    @classmethod
    def scan_workspace(
        cls,
        paths: Sequence[Path],
        *,
        forbidden_tokens: Sequence[str] = DEFAULT_FORBIDDEN_INDUSTRY_TOKENS,
        schema_ids: Sequence[str] = (),
        object_keys: Sequence[str] = (),
    ) -> dict[str, Any]:
        violations: list[dict[str, str]] = []
        for sid in schema_ids:
            matched = cls._matches_banned(sid, forbidden_tokens)
            if matched is not None:
                violations.append(
                    {"source": "<schema_id>", "identifier": sid, "token": matched}
                )
        for okey in object_keys:
            matched = cls._matches_banned(okey, forbidden_tokens)
            if matched is not None:
                violations.append(
                    {"source": "<object_key>", "identifier": okey, "token": matched}
                )
        for path in sorted(paths):
            entries = sorted(path.rglob("*")) if path.is_dir() else [path]
            for entry in entries:
                if any(
                    part.startswith(".") or part == "__pycache__"
                    for part in entry.parts
                ):
                    continue
                matched_name = cls._matches_banned(entry.stem, forbidden_tokens)
                if matched_name is not None:
                    violations.append(
                        {
                            "source": entry.name,
                            "identifier": entry.name,
                            "token": matched_name,
                        }
                    )
                if entry.is_file() and entry.suffix in (".py", ".json", ".md", ".toml"):
                    content_str = entry.read_text(encoding="utf-8")
                    nom_res = cls.scan_nomenclature_text(
                        content_str,
                        source_name=entry.name,
                    )
                    violations.extend(nom_res["violations"])
                    if entry.suffix == ".py":
                        res = cls.scan_source(
                            content_str,
                            forbidden_tokens=forbidden_tokens,
                            source_name=entry.name,
                        )
                        violations.extend(res["violations"])
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }


class SharedBannedWordsGate:
    """Enforces shared `banned-words.json` across `always`, `visible_text`, and `private_names`."""

    @staticmethod
    def load_rules(rules_path: Path = DEFAULT_BANNED_WORDS_PATH) -> dict[str, Any]:
        return json.loads(rules_path.read_text(encoding="utf-8"))

    @classmethod
    def scan_text(
        cls,
        text: str,
        *,
        rules_payload: Mapping[str, Any],
        include_visible_text: bool = True,
        source_name: str = "<string>",
    ) -> dict[str, Any]:
        flags = (
            re.IGNORECASE | re.MULTILINE
            if bool(rules_payload.get("case_insensitive", True))
            else re.MULTILINE
        )
        violations: list[dict[str, str]] = []

        for group_name in ("always", "agent_apps_outside_models_page", "fingerprints"):
            pats = list((rules_payload.get(group_name) or {}).get("patterns") or [])
            for pat in pats:
                m = re.search(str(pat), text, flags=flags)
                if m is not None:
                    violations.append(
                        {
                            "source": source_name,
                            "group": group_name,
                            "pattern": str(pat),
                            "match": m.group(0),
                        }
                    )

        if include_visible_text:
            vis_pats = list((rules_payload.get("visible_text") or {}).get("patterns") or [])
            for pat in vis_pats:
                m = re.search(str(pat), text, flags=flags)
                if m is not None:
                    violations.append(
                        {
                            "source": source_name,
                            "group": "visible_text",
                            "pattern": str(pat),
                            "match": m.group(0),
                        }
                    )

        priv_section = rules_payload.get("private_names") or {}
        priv_lists = [v for v in priv_section.values() if isinstance(v, list)]
        priv_hashes = {
            str(h).lower()
            for sublist in priv_lists
            for h in sublist
        }
        if priv_hashes:
            for tok in re.findall(r"[A-Za-z0-9]+", text):
                low_tok = tok.lower()
                if low_tok in ("teleion", "teleionlabs"):
                    continue
                digest = hashlib.sha256(low_tok.encode("utf-8")).hexdigest()
                if digest in priv_hashes:
                    violations.append(
                        {
                            "source": source_name,
                            "group": "private_names",
                            "pattern": "private_token_digest",
                            "match": "<redacted_private_name>",
                        }
                    )

        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }

    @classmethod
    def scan_json_payload(
        cls,
        payload: Any,
        *,
        rules_payload: Mapping[str, Any],
        include_visible_text: bool = True,
        machine_exempt_keys: Sequence[str] = ("worker_token", "task_id", "worker_uuid"),
    ) -> dict[str, Any]:
        exempt_set = {str(k) for k in machine_exempt_keys}
        violations: list[dict[str, str]] = []

        def _visit(obj: Any, path_label: str, current_key: str) -> None:
            if isinstance(obj, Mapping):
                for k, v in obj.items():
                    key_str = str(k)
                    key_res = cls.scan_text(
                        key_str,
                        rules_payload=rules_payload,
                        include_visible_text=False,
                        source_name=f"{path_label}.<key:{key_str}>",
                    )
                    violations.extend(key_res["violations"])
                    _visit(v, f"{path_label}.{key_str}", key_str)
            elif isinstance(obj, (list, tuple)):
                for idx, item in enumerate(obj):
                    _visit(item, f"{path_label}[{idx}]", current_key)
            elif isinstance(obj, str):
                check_vis = include_visible_text and (current_key not in exempt_set)
                res = cls.scan_text(
                    obj,
                    rules_payload=rules_payload,
                    include_visible_text=check_vis,
                    source_name=path_label,
                )
                violations.extend(res["violations"])

        _visit(payload, "$", "")
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }

    @classmethod
    def scan_paths(
        cls,
        paths: Sequence[Path],
        *,
        rules_path: Path = DEFAULT_BANNED_WORDS_PATH,
        include_visible_text_for_prose: bool = True,
    ) -> dict[str, Any]:
        rules_payload = cls.load_rules(rules_path)
        violations: list[dict[str, str]] = []
        scanned = 0
        for path in sorted(paths):
            files = sorted(path.rglob("*")) if path.is_dir() else [path]
            for fpath in files:
                if not fpath.is_file():
                    continue
                if any(
                    part.startswith(".") or part == "__pycache__"
                    for part in fpath.parts
                ):
                    continue
                if fpath.suffix not in (".py", ".json", ".md", ".toml"):
                    continue
                scanned += 1
                check_vis = include_visible_text_for_prose and fpath.suffix in (".md", ".json")
                res = cls.scan_text(
                    fpath.read_text(encoding="utf-8"),
                    rules_payload=rules_payload,
                    include_visible_text=check_vis,
                    source_name=fpath.name,
                )
                violations.extend(res["violations"])
        return {
            "passed": len(violations) == 0,
            "files_scanned": scanned,
            "violation_count": len(violations),
            "violations": violations,
        }


@dataclass(frozen=True)
class NodeParameter:
    """Single typed parameter axis inside a multi-dimensional `NodeGrid`."""

    name: str
    param_type: str
    default: Any
    choices: tuple[Any, ...] = ()
    low: int | float | None = None
    high: int | float | None = None
    step: int | float | None = None


class ParameterBounds:
    """Runtime clamping of candidate grid cells to axis domains and hard outer safety bounds."""

    def __init__(
        self,
        parameters: Mapping[str, NodeParameter],
        hard_bounds: Mapping[str, Mapping[str, int | float]],
    ) -> None:
        self._parameters = dict(parameters)
        self._hard_bounds = {k: dict(v) for k, v in hard_bounds.items()}

    def clamp_value(self, name: str, raw_value: Any) -> Any:
        param = self._parameters[name]
        if param.param_type == "boolean":
            if isinstance(raw_value, bool):
                return raw_value
            if isinstance(raw_value, (int, float)) and not math.isnan(float(raw_value)):
                return bool(raw_value)
            return bool(param.default)

        if param.param_type == "choice":
            return raw_value if raw_value in param.choices else param.default

        if param.param_type in ("integer_range", "float_range"):
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                val = float(param.default)
            else:
                val = float(raw_value)
                if not math.isfinite(val):
                    val = float(param.default)

            low_bound = float(param.low) if param.low is not None else val
            high_bound = float(param.high) if param.high is not None else val
            hb = self._hard_bounds.get(name)
            if hb is not None:
                if "min" in hb:
                    low_bound = max(low_bound, float(hb["min"]))
                if "max" in hb:
                    high_bound = min(high_bound, float(hb["max"]))

            clamped = min(max(val, low_bound), high_bound)
            if param.param_type == "integer_range":
                if param.step is not None and int(param.step) > 1:
                    step_int = int(param.step)
                    base_int = int(round(low_bound))
                    snapped = base_int + int(round((clamped - base_int) / step_int)) * step_int
                    clamped = float(min(max(snapped, int(round(low_bound))), int(round(high_bound))))
                return int(round(clamped))
            return float(clamped)

        return param.default

    def clamp_cell(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for name, param in self._parameters.items():
            raw = candidate.get(name, param.default)
            resolved[name] = self.clamp_value(name, raw)
        return resolved


class NodeGrid:
    """Multi-dimensional Configuration Settings Grid with constraints, regimes, and axis expansion."""

    def __init__(
        self,
        *,
        schema_id: str,
        generation: int,
        parameters: Mapping[str, NodeParameter],
        hard_bounds: Mapping[str, Mapping[str, int | float]],
        constraints: Sequence[Mapping[str, Any]],
        default_verified_cell: Mapping[str, Any],
        regimes: Mapping[str, Mapping[str, Any]],
        protocol_constants: Mapping[str, Any],
    ) -> None:
        self.schema_id = schema_id
        self.generation = int(generation)
        self.parameters = dict(parameters)
        self.hard_bounds = {k: dict(v) for k, v in hard_bounds.items()}
        self.constraints = [dict(c) for c in constraints]
        self.bounds = ParameterBounds(self.parameters, self.hard_bounds)
        self.default_verified_cell = self.bounds.clamp_cell(default_verified_cell)
        self.regimes = {
            rname: {
                "description": str(rspec.get("description", "")),
                "cell": self.bounds.clamp_cell(rspec.get("cell") or default_verified_cell),
            }
            for rname, rspec in regimes.items()
        }
        self.protocol_constants = copy.deepcopy(dict(protocol_constants))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> NodeGrid:
        params: dict[str, NodeParameter] = {}
        for name, pspec in (raw.get("parameters") or {}).items():
            ptype = str(pspec["type"])
            choices = tuple(pspec.get("choices") or ())
            params[name] = NodeParameter(
                name=name,
                param_type=ptype,
                default=pspec["default"],
                choices=choices,
                low=pspec.get("low"),
                high=pspec.get("high"),
                step=pspec.get("step"),
            )
        return cls(
            schema_id=str(raw["schema_id"]),
            generation=int(raw.get("generation", 1)),
            parameters=params,
            hard_bounds=raw.get("hard_bounds") or {},
            constraints=raw.get("constraints") or [],
            default_verified_cell=raw.get("default_verified_cell") or {},
            regimes=raw.get("regimes") or {},
            protocol_constants=raw.get("protocol_constants") or {},
        )

    @classmethod
    def from_json_file(cls, path: Path = DEFAULT_GRID_CONFIG_PATH) -> NodeGrid:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def compute_cell_id(cell: Mapping[str, Any], *, short_chars: int) -> str:
        canonical = json.dumps(dict(sorted(cell.items())), sort_keys=True, separators=(",", ":"))
        digest = hashlib.blake2b(canonical.encode("utf-8")).hexdigest()
        return f"cell_{digest[:short_chars]}"

    def cell_id_for(self, cell: Mapping[str, Any]) -> str:
        short_chars = int(self.protocol_constants["short_digest_chars"])
        return self.compute_cell_id(cell, short_chars=short_chars)

    def validate_constraints(self, candidate: Mapping[str, Any]) -> tuple[bool, list[str]]:
        clamped = self.bounds.clamp_cell(candidate)
        failures: list[str] = []
        for rule in self.constraints:
            cid = str(rule.get("id", "unnamed_constraint"))
            kind = str(rule.get("kind", ""))
            if kind == "lte_param":
                left_val = clamped[str(rule["left"])]
                right_val = clamped[str(rule["right"])]
                if left_val > right_val:
                    failures.append(cid)
            elif kind == "when_eq_require_in":
                if clamped.get(str(rule["when_param"])) == rule.get("when_value"):
                    allowed = list(rule.get("allowed_values") or [])
                    if clamped.get(str(rule["target_param"])) not in allowed:
                        failures.append(cid)
            elif kind == "when_eq_require_min":
                if clamped.get(str(rule["when_param"])) == rule.get("when_value"):
                    min_val = float(rule["min_value"])
                    if float(clamped[str(rule["target_param"])]) < min_val:
                        failures.append(cid)
            elif kind == "when_eq_require_max":
                if clamped.get(str(rule["when_param"])) == rule.get("when_value"):
                    max_val = float(rule["max_value"])
                    if float(clamped[str(rule["target_param"])]) > max_val:
                        failures.append(cid)
        return (len(failures) == 0, failures)

    def resolve_regime_cell(
        self,
        regime_name: str,
        *,
        overrides: Mapping[str, Any] | None = None,
        cost_ledger: OperationCostLedger | None = None,
        grid_ledger: GridLedger | None = None,
    ) -> dict[str, Any]:
        if cost_ledger is not None:
            allowed_ids: set[str] | None = None
            if grid_ledger is not None:
                allowed_ids = grid_ledger.verified_or_promoted_ids()
            empirical = cost_ledger.best_cell_for_regime(
                regime_name,
                allowed_cell_ids=allowed_ids,
            )
            if empirical is not None and overrides is None:
                return self.bounds.clamp_cell(empirical)

        base_cell = (
            self.regimes[regime_name]["cell"]
            if regime_name in self.regimes
            else self.default_verified_cell
        )
        merged = dict(base_cell)
        if overrides:
            merged.update(overrides)
        clamped = self.bounds.clamp_cell(merged)
        ok, _ = self.validate_constraints(clamped)
        if not ok:
            return dict(base_cell)
        return clamped

    def expand_axis_boundary(
        self,
        param_name: str,
        direction: str,
        *,
        expansion_factor: float | None = None,
    ) -> NodeGrid:
        param = self.parameters[param_name]
        if param.param_type not in ("integer_range", "float_range"):
            raise ValueError(f"Parameter {param_name} is not a numeric range axis")

        factor = (
            float(expansion_factor)
            if expansion_factor is not None
            else float(self.protocol_constants["boundary_expansion_factor"])
        )
        hb = self.hard_bounds.get(param_name, {})
        cur_low = float(param.low) if param.low is not None else 0.0
        cur_high = float(param.high) if param.high is not None else 1.0
        span = max(cur_high - cur_low, float(param.step or 1.0))

        new_low = cur_low
        new_high = cur_high
        if direction == "high":
            proposed_high = cur_high + span * (factor - 1.0)
            if "max" in hb:
                proposed_high = min(proposed_high, float(hb["max"]))
            new_high = max(cur_high, proposed_high)
        elif direction == "low":
            proposed_low = cur_low - span * (factor - 1.0)
            if "min" in hb:
                proposed_low = max(proposed_low, float(hb["min"]))
            new_low = min(cur_low, proposed_low)
        else:
            raise ValueError(f"Unsupported boundary direction: {direction}")

        updated_params = dict(self.parameters)
        if param.param_type == "integer_range":
            updated_params[param_name] = NodeParameter(
                name=param.name,
                param_type=param.param_type,
                default=param.default,
                choices=param.choices,
                low=int(round(new_low)),
                high=int(round(new_high)),
                step=param.step,
            )
        else:
            updated_params[param_name] = NodeParameter(
                name=param.name,
                param_type=param.param_type,
                default=param.default,
                choices=param.choices,
                low=float(new_low),
                high=float(new_high),
                step=param.step,
            )

        return NodeGrid(
            schema_id=self.schema_id,
            generation=self.generation + 1,
            parameters=updated_params,
            hard_bounds=self.hard_bounds,
            constraints=self.constraints,
            default_verified_cell=self.default_verified_cell,
            regimes=self.regimes,
            protocol_constants=self.protocol_constants,
        )

    def to_spec_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "generation": self.generation,
            "parameters": {
                name: {
                    "type": p.param_type,
                    "default": p.default,
                    **({"choices": list(p.choices)} if p.choices else {}),
                    **({"low": p.low, "high": p.high, "step": p.step} if p.low is not None else {}),
                }
                for name, p in self.parameters.items()
            },
            "constraints": copy.deepcopy(self.constraints),
            "default_verified_cell": copy.deepcopy(self.default_verified_cell),
            "regimes": copy.deepcopy(self.regimes),
        }


@dataclass
class CostObservation:
    """Single empirical execution observation recorded in `OperationCostLedger`."""

    regime: str
    cell_id: str
    cell: dict[str, Any]
    latency_ms: float
    tokens_used: int
    cold_steps_avoided: int
    perturbation_min_score: float
    had_error: bool
    utility_score: float


class OperationCostLedger:
    """Empirical workload evidence ledger backing contextual regime selection."""

    def __init__(self, grid: NodeGrid) -> None:
        self._grid = grid
        self._observations: list[CostObservation] = []

    @property
    def observations(self) -> list[CostObservation]:
        return list(self._observations)

    def record_observation(
        self,
        *,
        regime: str,
        cell: Mapping[str, Any],
        latency_ms: float,
        tokens_used: int,
        cold_steps_avoided: int,
        perturbation_min_score: float,
        had_error: bool = False,
    ) -> CostObservation:
        clamped = self._grid.bounds.clamp_cell(cell)
        cid = self._grid.cell_id_for(clamped)
        timeout_budget = max(float(clamped["route_timeout_ms"]), 1.0)
        token_scale = max(
            float(self._grid.protocol_constants["recommended_max_output_tokens"]),
            1.0,
        )
        baseline_steps = max(float(clamped["cold_baseline_step_count"]), 1.0)

        norm_latency = min(max(float(latency_ms) / timeout_budget, 0.0), 1.0)
        norm_tokens = min(max(float(tokens_used) / token_scale, 0.0), 1.0)
        avoided_ratio = min(max(float(cold_steps_avoided) / baseline_steps, 0.0), 1.0)
        error_penalty = 1.0 if had_error else 0.0

        utility = (
            float(perturbation_min_score)
            + avoided_ratio
            - norm_latency
            - norm_tokens
            - error_penalty
        )
        obs = CostObservation(
            regime=regime,
            cell_id=cid,
            cell=clamped,
            latency_ms=float(latency_ms),
            tokens_used=int(tokens_used),
            cold_steps_avoided=int(cold_steps_avoided),
            perturbation_min_score=float(perturbation_min_score),
            had_error=bool(had_error),
            utility_score=utility,
        )
        self._observations.append(obs)
        return obs

    def best_entry_for_regime(
        self,
        regime: str,
        *,
        allowed_cell_ids: set[str] | None = None,
    ) -> tuple[str, dict[str, Any], float] | None:
        grouped: dict[str, list[CostObservation]] = {}
        for obs in self._observations:
            if obs.regime != regime or obs.had_error:
                continue
            if allowed_cell_ids is not None and obs.cell_id not in allowed_cell_ids:
                continue
            grouped.setdefault(obs.cell_id, []).append(obs)

        best_tuple: tuple[str, dict[str, Any], float] | None = None
        for cid, items in grouped.items():
            mean_util = sum(x.utility_score for x in items) / float(len(items))
            if best_tuple is None or mean_util > best_tuple[-1]:
                best_tuple = (cid, dict(items[-1].cell), mean_util)
        return best_tuple

    def best_cell_for_regime(
        self,
        regime: str,
        *,
        allowed_cell_ids: set[str] | None = None,
    ) -> dict[str, Any] | None:
        entry = self.best_entry_for_regime(regime, allowed_cell_ids=allowed_cell_ids)
        return dict(entry[1]) if entry is not None else None


@dataclass
class LedgerCellRecord:
    """Lifecycle record for a configuration cell in `GridLedger`."""

    cell_id: str
    regime: str
    cell: dict[str, Any]
    stage: str
    history: list[dict[str, Any]] = field(default_factory=list)


class GridLedger:
    """7-stage configuration cell lifecycle tracker with Boundary Auto-Expansion."""

    def __init__(self, grid: NodeGrid) -> None:
        self.grid = grid
        self._records: dict[str, LedgerCellRecord] = {}
        self.expansion_events: list[dict[str, Any]] = []

    def get_record(self, cell_id: str) -> LedgerCellRecord:
        if cell_id not in self._records:
            raise KeyError(f"Unknown grid cell_id: {cell_id}")
        return self._records[cell_id]

    def verified_or_promoted_ids(self) -> set[str]:
        return {
            cid
            for cid, rec in self._records.items()
            if rec.stage in ("verified", "promoted")
        }

    def register_cell(self, candidate: Mapping[str, Any], *, regime: str = "single_worker") -> str:
        clamped = self.grid.bounds.clamp_cell(candidate)
        cid = self.grid.cell_id_for(clamped)
        if cid not in self._records:
            self._records[cid] = LedgerCellRecord(
                cell_id=cid,
                regime=regime,
                cell=clamped,
                stage=CELL_LIFECYCLE_STATES[0],
                history=[{"stage": CELL_LIFECYCLE_STATES[0], "regime": regime}],
            )
        return cid

    def advance_stage(
        self,
        cell_id: str,
        target_stage: str,
        *,
        evidence: Mapping[str, Any] | None = None,
    ) -> LedgerCellRecord:
        if target_stage not in CELL_LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle stage: {target_stage}")
        rec = self.get_record(cell_id)
        cur_idx = CELL_LIFECYCLE_STATES.index(rec.stage)
        tgt_idx = CELL_LIFECYCLE_STATES.index(target_stage)
        if tgt_idx != cur_idx + 1:
            raise ValueError(
                f"Illegal stage transition {rec.stage} -> {target_stage}; "
                "must step sequentially and never promote an unverified cell."
            )

        ev = dict(evidence or {})
        if target_stage == "applicable":
            ok, failed = self.grid.validate_constraints(rec.cell)
            if not ok:
                raise ValueError(f"Cell {cell_id} failed grid constraints: {failed}")
        elif target_stage == "evaluated":
            if "latency_ms" not in ev:
                raise ValueError("Stage 'evaluated' requires empirical latency_ms evidence")
        elif target_stage == "verified":
            min_plateau = float(self.grid.protocol_constants["plateau_neighbor_min_score"])
            max_cliff = float(self.grid.protocol_constants["plateau_max_cliff_drop"])
            neighbor_min = float(ev.get("neighbor_min", 0.0))
            cliff_drop = float(ev.get("cliff_drop", 1.0))
            if not bool(ev.get("tests_passed", False)):
                raise ValueError("Stage 'verified' requires tests_passed=True")
            if neighbor_min < min_plateau or cliff_drop > max_cliff:
                raise ValueError(
                    f"Cell {cell_id} failed thick-path plateau check: "
                    f"neighbor_min={neighbor_min}, cliff_drop={cliff_drop}"
                )
        elif target_stage == "promoted":
            if rec.stage != "verified":
                raise ValueError("Cannot promote unverified cell")

        rec.stage = target_stage
        rec.history.append({"stage": target_stage, "evidence": ev})
        return rec

    def promote_through_full_lifecycle(
        self,
        candidate: Mapping[str, Any],
        *,
        regime: str,
        evaluation_evidence: Mapping[str, Any],
        verification_evidence: Mapping[str, Any],
    ) -> LedgerCellRecord:
        cid = self.register_cell(candidate, regime=regime)
        self.advance_stage(cid, "applicable")
        self.advance_stage(cid, "proposed")
        self.advance_stage(cid, "dispatched")
        self.advance_stage(cid, "evaluated", evidence=evaluation_evidence)
        self.advance_stage(cid, "verified", evidence=verification_evidence)
        return self.advance_stage(cid, "promoted", evidence=verification_evidence)

    def maybe_auto_expand_boundaries(
        self,
        cost_ledger: OperationCostLedger,
        *,
        regime: str,
    ) -> tuple[NodeGrid, list[dict[str, Any]]]:
        best_entry = cost_ledger.best_entry_for_regime(
            regime,
            allowed_cell_ids=self.verified_or_promoted_ids(),
        )
        if best_entry is None:
            return self.grid, []

        best_cid, best_cell, best_util = best_entry
        eps = float(self.grid.protocol_constants["boundary_touch_eps"])
        updated_grid = self.grid
        triggered: list[dict[str, Any]] = []

        for pname, param in list(self.grid.parameters.items()):
            if param.param_type not in ("integer_range", "float_range"):
                continue
            if param.low is None or param.high is None:
                continue
            val = float(best_cell[pname])
            hb = self.grid.hard_bounds.get(pname, {})
            hb_max = float(hb.get("max", param.high))
            hb_min = float(hb.get("min", param.low))

            if abs(val - float(param.high)) <= eps and float(param.high) < hb_max:
                prev_high = param.high
                updated_grid = updated_grid.expand_axis_boundary(pname, "high")
                new_high = updated_grid.parameters[pname].high
                if float(new_high or prev_high) > float(prev_high):
                    event = {
                        "regime": regime,
                        "cell_id": best_cid,
                        "parameter": pname,
                        "direction": "high",
                        "previous_bound": prev_high,
                        "expanded_bound": new_high,
                        "new_generation": updated_grid.generation,
                        "utility_score": best_util,
                    }
                    triggered.append(event)
                    self.expansion_events.append(event)
            elif abs(val - float(param.low)) <= eps and float(param.low) > hb_min:
                prev_low = param.low
                updated_grid = updated_grid.expand_axis_boundary(pname, "low")
                new_low = updated_grid.parameters[pname].low
                if float(new_low if new_low is not None else prev_low) < float(prev_low):
                    event = {
                        "regime": regime,
                        "cell_id": best_cid,
                        "parameter": pname,
                        "direction": "low",
                        "previous_bound": prev_low,
                        "expanded_bound": new_low,
                        "new_generation": updated_grid.generation,
                        "utility_score": best_util,
                    }
                    triggered.append(event)
                    self.expansion_events.append(event)

        self.grid = updated_grid
        return updated_grid, triggered
