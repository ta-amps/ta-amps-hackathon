"""One run: a Durable Task with a claim, heartbeats, a report and a record. Key: the maker's own."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from src.universal_omninode_closure import OmniNodeResult

from omninode_live import core, feed, grid as gridmod, prestep
from omninode_live.spec import seed_spec

QUEUE, KIND = "eq02", "spec"  # the planner key may claim spec here; builders do not claim spec, and the planner only claims on eq01


def load_spec(fabric: Any) -> tuple[dict[str, Any], int]:
    found = fabric.get(core.RECORD_STORE, core.SPEC_KEY)
    if found is not None:
        current, version = found
        have = current["parameters"]["settings"]
        added = {k: v for k, v in seed_spec()["parameters"]["settings"].items() if k not in have}
        if not added:
            return found
        have.update(added)
        current.setdefault("change_log", []).append({"at": core.utc_stamp(), "from_spec_version": version, "by": "code change, not the tuner", "added_settings": added})
        return current, fabric.put(core.RECORD_STORE, core.SPEC_KEY, current, expected=version, tags=["kind:instructions", "kind:omninode_spec"])
    spec = seed_spec()
    version = fabric.put(core.RECORD_STORE, core.SPEC_KEY, spec, expected=None, tags=["kind:instructions", "kind:omninode_spec"])
    return spec, version


def compact(item: dict[str, Any]) -> dict[str, Any]:
    keep = ("key", "full_name", "license", "status", "maker_variant", "maker_model", "cost_usd", "model_seconds", "rule_failures",
            "reused_from_version", "stored_version", "content_digest", "trace")
    return {k: item[k] for k in keep if k in item}


def execute(fabric: Any, github: Any, screen: Any, models: Any, checker_key_id: str, *, run_id: str, task_id: str,
            token: int, heartbeat: Any = None, workdir: Path | None = None) -> dict[str, Any]:
    """The pipeline under an open lease; returns the run record, written before the report."""
    spec, version = load_spec(fabric)
    grid = gridmod.node_grid()
    cell = gridmod.cell_of(spec, grid)
    ctx = feed.RunContext(run_id=run_id, spec=spec, spec_version=version, fabric=fabric, github=github, screen=screen, models=models, heartbeat=heartbeat,
                          prestep=prestep.PreStep(run_id, spec=spec))
    node = feed.build_pipeline(ctx, grid, cell, maker_key_id=fabric.key_id, checker_key_id=checker_key_id)
    started = time.time()
    try:
        result: OmniNodeResult = node.execute({"run_id": run_id, "node": spec["id"]})
    except Exception as exc:  # paid attempts stay on the record whatever broke after them
        result = OmniNodeResult(ok=False, output={}, node_id=node.node_id, role=node.role, placement_scope=node.placement_scope,
                                latency_ms=0.0, diagnostics={"error_code": f"{type(exc).__name__}: {str(exc)[:200]}"})
    seconds = round(time.time() - started, 2)
    items = list(result.output.get("items") or [])
    if workdir is not None:
        files = dict(node.workdir_bundle) | {"spec.json": json.dumps(spec, indent=1, sort_keys=True)}
        for rel, text in files.items():
            path = workdir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    record = {
        "kind": "task_object", "schema": "teleion.omninode.run.v1", "node": spec["id"], "run_id": run_id, "task_id": task_id,
        "fencing_token": token, "spec_version": version, "mix_used": spec["parameters"]["model"]["mix"]["make"],
        "tuner_version_used": spec["parameters"]["model"]["tuner_version"], "batch_size_used": spec["parameters"]["settings"]["batch_size"],
        "composition": spec["composition"], "ok": result.ok, "seconds": seconds, "tokens_used_by_runtime": result.tokens_used,
        "maker_key_id": fabric.key_id, "maker_worker": fabric.label, "expected_checker_key_id": checker_key_id,
        "status": "awaiting_check" if result.ok else "failed", "error": result.diagnostics.get("error_code") if not result.ok else None,
        "github": {"calls": github.calls, "failures": github.failures[:10], "credential": "none, public API"},
        "counts": feed.mode_counts(items, ctx.attempts), "draws": ctx.draws, "attempts": ctx.attempts, "prestep": ctx.prestep.finish(items),
        "items": [compact(i) for i in items],
    }
    tags = ["kind:instructions", "kind:omninode_run"]
    fabric.put(core.RECORD_STORE, core.RUN_PREFIX + run_id, record, expected=None, tags=tags)
    prior = fabric.get(core.RECORD_STORE, core.LATEST_KEY)
    fabric.put(core.RECORD_STORE, core.LATEST_KEY, {"run_id": run_id, "status": record["status"], "spec_version": version},
               expected=prior[1] if prior else None, tags=["kind:instructions"])
    return record


def main() -> int:
    label = os.environ.get("OMNINODE_LABEL", "omninode-feed-maker")
    fabric = core.from_env(label)
    checker = os.environ["OMNINODE_CHECKER_KEY_ID"]
    if checker == fabric.key_id:
        print("refused: the maker's key is the checker's key", file=sys.stderr)
        return 2
    now = core.utc_stamp()
    spec, _ = load_spec(fabric)
    task_id = f"omninode_feed_{now}"
    fabric.enqueue(queue=QUEUE, task_id=task_id, kind=KIND, brief={"title": "OmniNode feed maintenance run", "node": spec["id"], "run_id": now, "instruction": spec["instruction"]})
    lease = fabric.claim(QUEUE, KIND)
    for _ in range(4):
        if lease is None:
            print("nothing to claim", file=sys.stderr)
            return 1
        brief = lease.brief if isinstance(lease.brief, dict) else {}
        if brief.get("node") != spec["id"]:
            print(f"claimed a Task that is not this node's: {lease.task_id}; leaving it to lapse", file=sys.stderr)
            return 1
        run_id = str(brief.get("run_id") or now)
        existing = fabric.get(core.RECORD_STORE, core.RUN_PREFIX + run_id)
        if existing is None:
            break
        # An earlier attempt did the work and lost the report: report that record, never redo paid work.
        record = existing[0]
        receipt = fabric.submit(lease.task_id, lease.fencing_token, {"status": record["status"], "run_id": run_id, "counts": record["counts"], "record": f"{core.RECORD_STORE}/{core.RUN_PREFIX}{run_id}", "reported_after_retry": True},
                                ok=bool(record["ok"]), error=record.get("error"), report=core.execution_report("maker", label, spec["instruction"], f"feed run {run_id}: {record['status']} (reported on a later attempt)", record["attempts"]))
        print(json.dumps({"run_id": run_id, "task_id": lease.task_id, "receipt": receipt, "reported_after_retry": True}))
        lease = fabric.claim(QUEUE, KIND)
    else:
        return 1
    beat = core.Heartbeat(lambda: fabric.heartbeat(lease.task_id, lease.fencing_token), float(lease.heartbeat_seconds or 60))
    beat.start()
    ledger = core.ledgers()
    catalog, _ = fabric.get(core.RECORD_STORE, "models.meta")
    cache: dict[str, Any] = {}

    def models(model_id: str) -> Any:
        return cache.setdefault(model_id, core.meta_model(model_id, catalog, ledger, effort=str(spec["parameters"]["settings"]["reasoning_effort"])))

    workdir = Path.home() / ".local/state/teleion-omninode/runs" / run_id
    try:
        record = execute(fabric, feed.GitHub(), core.Screen(), models, checker, run_id=run_id, task_id=lease.task_id,
                         token=lease.fencing_token, heartbeat=beat, workdir=workdir)
    except Exception as exc:  # the failure goes on the record too
        beat.stop()
        fabric.submit(lease.task_id, lease.fencing_token, {"status": "failed", "run_id": run_id}, ok=False,
                      error=f"{type(exc).__name__}: {str(exc)[:300]}", report=core.execution_report("maker", label, spec["instruction"], f"failed: {type(exc).__name__}", []))
        raise
    beat.stop()
    receipt = fabric.submit(lease.task_id, lease.fencing_token, {"status": record["status"], "run_id": run_id, "counts": record["counts"], "record": f"{core.RECORD_STORE}/{core.RUN_PREFIX}{run_id}"},
                            ok=bool(record["ok"]), error=record["error"], report=core.execution_report("maker", label, spec["instruction"], f"feed run {run_id}: {record['status']}", record["attempts"]))
    print(json.dumps({"run_id": run_id, "task_id": lease.task_id, "status": record["status"], "receipt": receipt, "counts": record["counts"], "draws": record["draws"]}))
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
