"""The runtime's grid and 7-stage GridLedger, extended with this node's real parameters and kept in Fabric."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from src.omninode_grid_engine import DEFAULT_GRID_CONFIG_PATH, GridLedger, LedgerCellRecord, NodeGrid, OperationCostLedger

REGIME = "single_worker"
SPARK, WONDER = "label-muse-spark", "label-muse-wonder"


def node_grid() -> NodeGrid:
    raw = copy.deepcopy(json.loads(Path(DEFAULT_GRID_CONFIG_PATH).read_text(encoding="utf-8")))
    raw["schema_id"] = "teleion.omninode.feed-maintenance.grid.v1"
    raw["parameters"].update({
        "label_share_muse_spark": {"type": "float_range", "low": 0.05, "high": 0.95, "default": 0.5},
        "batch_size": {"type": "integer_range", "low": 2, "high": 20, "step": 1, "default": 8},
        "min_confidence_milli": {"type": "integer_range", "low": 300, "high": 900, "step": 50, "default": 600},
    })
    raw["default_verified_cell"].update(label_share_muse_spark=0.5, batch_size=8, min_confidence_milli=600)
    return NodeGrid.from_dict(raw)


def cell_of(spec: dict[str, Any], grid: NodeGrid) -> dict[str, Any]:
    params = spec["parameters"]
    return grid.bounds.clamp_cell({
        **grid.default_verified_cell,
        "label_share_muse_spark": params["model"]["mix"]["make"][SPARK],
        "batch_size": params["settings"]["batch_size"],
        "min_confidence_milli": params["settings"]["min_confidence_milli"],
    })


def load_ledger(grid: NodeGrid, state: dict[str, Any] | None) -> tuple[GridLedger, OperationCostLedger]:
    ledger, costs = GridLedger(grid), OperationCostLedger(grid)
    for cid, row in ((state or {}).get("cells") or {}).items():
        ledger._records[cid] = LedgerCellRecord(cell_id=cid, regime=row["regime"], cell=row["cell"], stage=row["stage"], history=row["history"])
    for obs in (state or {}).get("observations") or []:
        costs.record_observation(**obs)
    return ledger, costs


def dump_state(ledger: GridLedger, observations: list[dict[str, Any]], **more: Any) -> dict[str, Any]:
    return {
        "kind": "task_object", "schema": "teleion.omninode.grid.v1",
        "cells": {cid: {"regime": r.regime, "cell": r.cell, "stage": r.stage, "history": r.history} for cid, r in ledger._records.items()},
        "observations": observations, **more,
    }
