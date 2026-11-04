"""Declarative NodeGrid, ParameterBounds, GridLedger, OperationCostLedger, and Boundary Auto-Expansion."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LIFECYCLE_STAGES: tuple[str, ...] = (
    "represented",
    "applicable",
    "proposed",
    "dispatched",
    "evaluated",
    "verified",
    "promoted",
)


@dataclass
class NodeParameter:
    """Single tunable dimension on a NodeGrid axis."""

    name: str
    kind: str
    low: int | None = None
    high: int | None = None
    step: int = 1
    choices: list[str] = field(default_factory=list)

    def accepts(self, value: Any) -> bool:
        if self.kind == "boolean":
            return isinstance(value, bool)
        if self.kind == "choice":
            return isinstance(value, str) and value in self.choices
        if self.kind == "integer_range":
            if isinstance(value, bool) or not isinstance(value, int):
                return False
            if self.low is None or self.high is None:
                return False
            return self.low <= value <= self.high
        return False


@dataclass
class ParameterBounds:
    """Hard runtime clamping bounds and boundary auto-expansion policy."""

    bounds: dict[str, dict[str, int]]
    expansion_factor: int

    def clamp(self, axis_name: str, value: Any) -> Any:
        entry = self.bounds.get(axis_name)
        if not entry or isinstance(value, bool) or not isinstance(value, int):
            return value
        low = int(entry["min"])
        high = int(entry["max"])
        if value < low:
            return low
        if value > high:
            return high
        return value


@dataclass
class GridLedger:
    """Tracks every configuration cell strictly across the seven-stage lifecycle."""

    cell_states: dict[str, str] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)

    def register(self, cell_id: str) -> None:
        if cell_id not in self.cell_states:
            self.cell_states[cell_id] = LIFECYCLE_STAGES[0]
            self.history.append({"cell_id": cell_id, "stage": LIFECYCLE_STAGES[0]})

    def advance(self, cell_id: str, target_stage: str) -> None:
        if cell_id not in self.cell_states:
            raise KeyError(f"Unknown configuration cell: {cell_id}")
        if target_stage not in LIFECYCLE_STAGES:
            raise ValueError(f"Invalid lifecycle stage: {target_stage}")
        current_idx = LIFECYCLE_STAGES.index(self.cell_states[cell_id])
        target_idx = LIFECYCLE_STAGES.index(target_stage)
        if target_idx == current_idx:
            return
        if target_idx != current_idx + 1:
            raise ValueError(
                f"Cannot skip lifecycle stages from {self.cell_states[cell_id]} to {target_stage}"
            )
        self.cell_states[cell_id] = target_stage
        self.history.append({"cell_id": cell_id, "stage": target_stage})

    def advance_through_verified(self, cell_id: str) -> None:
        self.register(cell_id)
        for stage in LIFECYCLE_STAGES[1:]:
            if stage == "promoted":
                break
            current_idx = LIFECYCLE_STAGES.index(self.cell_states[cell_id])
            stage_idx = LIFECYCLE_STAGES.index(stage)
            if stage_idx == current_idx + 1:
                self.advance(cell_id, stage)

    def promote_verified(self, cell_id: str) -> None:
        if self.cell_states.get(cell_id) != "verified":
            raise PermissionError(f"Cell {cell_id} must be verified before promotion")
        self.advance(cell_id, "promoted")


@dataclass
class OperationCostLedger:
    """Empirical operation cost and reward evidence per workload regime and cell."""

    records: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        *,
        regime: str,
        cell_id: str,
        latency_seconds: float,
        cost_usd: float,
        verified_ok: bool,
    ) -> None:
        self.records.append(
            {
                "regime": regime,
                "cell_id": cell_id,
                "latency_seconds": float(latency_seconds),
                "cost_usd": float(cost_usd),
                "verified_ok": bool(verified_ok),
            }
        )

    def best_verified_cell(self, regime: str, verified_cells: set[str]) -> str | None:
        grouped: dict[str, list[float]] = {}
        for row in self.records:
            cid = str(row["cell_id"])
            if row["regime"] == regime and row["verified_ok"] and cid in verified_cells:
                grouped.setdefault(cid, []).append(float(row["latency_seconds"]) + float(row["cost_usd"]))
        if not grouped:
            return None
        return min(grouped.items(), key=lambda item: sum(item[1]) / len(item[1]))[0]


class NodeGrid:
    """Multi-dimensional declarative configuration grid with constraint checks and boundary expansion."""

    def __init__(self, raw_spec: dict[str, Any]) -> None:
        self.raw_spec = dict(raw_spec)
        self.schema_id = str(raw_spec["schema_id"])
        self.grid_id = str(raw_spec["grid_id"])
        self.generation = int(raw_spec["generation"])
        self.axes: dict[str, NodeParameter] = {}
        for axis_raw in raw_spec.get("axes", []):
            param = NodeParameter(
                name=str(axis_raw["name"]),
                kind=str(axis_raw["kind"]),
                low=int(axis_raw["low"]) if "low" in axis_raw else None,
                high=int(axis_raw["high"]) if "high" in axis_raw else None,
                step=int(axis_raw.get("step", 1)),
                choices=[str(c) for c in axis_raw.get("choices", [])],
            )
            self.axes[param.name] = param
        self.constraints: list[dict[str, Any]] = list(raw_spec.get("constraints", []))
        pb_raw = dict(raw_spec.get("parameter_bounds", {}))
        expansion_factor = int(pb_raw.pop("expansion_factor", 1))
        self.bounds = ParameterBounds(bounds=pb_raw, expansion_factor=expansion_factor)
        self.cells: dict[str, dict[str, Any]] = {
            str(k): dict(v) for k, v in raw_spec.get("cells", {}).items()
        }
        self.regimes: dict[str, Any] = dict(raw_spec.get("regimes", {}))
        self.ledger = GridLedger()
        self.cost_ledger = OperationCostLedger()
        for cell_id, cell_values in self.cells.items():
            self.validate_cell(cell_values)
            self.ledger.advance_through_verified(cell_id)
            self.ledger.promote_verified(cell_id)

    def validate_cell(self, cell: dict[str, Any]) -> dict[str, Any]:
        clamped: dict[str, Any] = {}
        for axis_name, axis in self.axes.items():
            if axis_name not in cell:
                raise ValueError(f"Missing axis {axis_name} in cell")
            val = self.bounds.clamp(axis_name, cell[axis_name])
            if not axis.accepts(val):
                raise ValueError(f"Value {val!r} rejected by axis {axis_name}")
            clamped[axis_name] = val
        for rule in self.constraints:
            left = clamped[str(rule["left_axis"])]
            right = clamped[str(rule["right_axis"])]
            op = str(rule["operator"])
            if op == "gte" and not (left >= right):
                raise ValueError(f"Constraint {rule['id']} failed: {left} < {right}")
            if op == "lte" and not (left <= right):
                raise ValueError(f"Constraint {rule['id']} failed: {left} > {right}")
        return clamped

    def resolve_regime_cell(self, *, ready_count: int = 0, idle_cycles: int = 0) -> tuple[str, dict[str, Any]]:
        high_threshold = int(self.regimes.get("high_backlog_ready_threshold", 1))
        if ready_count >= high_threshold:
            regime_name = "high_backlog"
        elif idle_cycles > 1 and ready_count == 0:
            regime_name = "idle_conservation"
        else:
            regime_name = "default"
        promoted_cells = {
            cid for cid, st in self.ledger.cell_states.items() if st in {"verified", "promoted"}
        }
        empirical_best = self.cost_ledger.best_verified_cell(regime_name, promoted_cells)
        cell_id = empirical_best or str(self.regimes.get(regime_name, self.regimes["default"]))
        return cell_id, self.validate_cell(self.cells[cell_id])

    def maybe_expand_boundary(self, axis_name: str, observed_optimum: int) -> bool:
        """Expand integer_range axis into a new NodeGrid generation when empirical optimum saturates high/low."""
        axis = self.axes[axis_name]
        if axis.kind != "integer_range" or axis.low is None or axis.high is None:
            return False
        hard = self.bounds.bounds.get(axis_name, {})
        expanded = False
        if observed_optimum >= axis.high and "max" in hard and axis.high < int(hard["max"]):
            axis.high = min(int(hard["max"]), axis.high * self.bounds.expansion_factor)
            expanded = True
        elif observed_optimum <= axis.low and "min" in hard and axis.low > int(hard["min"]):
            axis.low = max(int(hard["min"]), axis.low - axis.step)
            expanded = True
        if expanded:
            self.generation += 1
        return expanded

    def section(self, key: str) -> dict[str, Any]:
        return dict(self.raw_spec.get(key, {}))

    def list_section(self, key: str) -> list[dict[str, Any]]:
        return [dict(item) for item in self.raw_spec.get(key, [])]


def load_warm_agent_grid(path: str | Path | None = None) -> NodeGrid:
    default_path = Path(__file__).resolve().parent.parent.parent / "config" / "warm_agent_grid.json"
    resolved = Path(path) if path is not None else default_path
    data = json.loads(os.path.expandvars(resolved.read_text(encoding="utf-8")))
    return NodeGrid(data)
