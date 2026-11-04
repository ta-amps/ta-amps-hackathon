"""Learning: the recorded trace feeds the grid and Thompson sampling, and the next run reads the changed parameter."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from eranos.pipeline import tuning

from omninode_live import core, grid as gridmod
from omninode_live.shim import Shim

QUEUE, KIND = "eq02", "tune"
TRAINING_QUEUE = "eq03"  # no worker holds both this queue and this kind except the planner's key; it waits, unstarted


def outcomes_from_runs(runs: list[dict[str, Any]], rewards: dict[str, Any]) -> list[tuning.Outcome]:
    """One outcome per item a model labeled: reward 1 when the rule accepted it and a different worker
    approved it, 0 when either refused, less its recorded cost. A failed call says nothing about a model."""
    out = []
    for run in runs:
        verdicts = (run.get("check") or {}).get("verdicts") or {}
        if not run.get("check"):
            continue
        for item in run.get("items", []):
            variant = item.get("maker_variant")
            if not variant:
                continue
            if any(t.get("outcome") == "deferred_budget" for t in item.get("trace", [])):
                continue
            attempt = next((a for a in run.get("attempts", []) if a.get("step") == "label" and item["key"] in a.get("item_keys", [])), {})
            if attempt.get("outcome") not in (None, "answered", "unparsed"):
                # A failed call says nothing about a model. Running out of tokens does, once the budget
                # and effort this node sets are on the attempt: before that it was this node's setting.
                if not ("used all" in str(attempt.get("error")) and attempt.get("max_output_tokens")):
                    continue
            verdict = (verdicts.get(item["key"]) or {}).get("verdict")
            if item["status"] == "awaiting_check" and verdict == "pending":
                continue  # not yet judged
            won = item["status"] == "awaiting_check" and verdict == "approve"
            reduce = tuning.penalty(rewards, float(item.get("cost_usd") or 0.0), float(item.get("model_seconds") or 0.0))
            out.append(tuning.Outcome(step="make", variant=variant, success=max(0.0, 1.0 - reduce) if won else 0.0, weight=1.0,
                                      ref=f"{run['run_id']}:{item['key']}", reason=item.get("status", "")))
    return out


def excluded_outcomes(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the tuner did not count, on the record, so a reader can replay it with these as losses."""
    out = []
    for run in runs:
        for a in run.get("attempts", []):
            if a.get("step") == "label" and a.get("outcome") not in (None, "answered", "unparsed") and not ("used all" in str(a.get("error")) and a.get("max_output_tokens")):
                out.append({"run": run["run_id"], "variant": a.get("variant"), "items": len(a.get("item_keys", [])), "outcome": a.get("outcome"), "error": str(a.get("error"))[:120],
                            "why": "the call failed for a reason that says nothing about the model, or under a token budget this node set too low"})
    return out


def next_mix(model: dict[str, Any], outcomes: list[tuning.Outcome], now: float) -> dict[str, Any]:
    return tuning.retune(model, outcomes, now=now)


def walk_grid(ledger: Any, costs: Any, grid: Any, spec: dict[str, Any], run: dict[str, Any], prior_rate: float | None, observations: list[dict[str, Any]]) -> dict[str, Any]:
    """The run's parameter set moves through the stages on its recorded evidence; a set that fails
    verification stays where it stopped, on the record."""
    cell = gridmod.cell_of(spec, grid) if not run.get("cell") else run["cell"]
    cid = ledger.register_cell(cell, regime=gridmod.REGIME)
    rec = ledger.get_record(cid)
    order = ["represented", "applicable", "proposed", "dispatched"]
    evidence = {"dispatched": {"run_id": run["run_id"], "spec_version": run["spec_version"]}}
    while rec.stage in order[:-1]:
        ledger.advance_stage(cid, order[order.index(rec.stage) + 1], evidence=evidence.get(order[order.index(rec.stage) + 1]))
    verdicts = (run.get("check") or {}).get("verdicts") or {}
    templates = {i["key"] for i in run.get("items", []) if i.get("maker_model") == "deterministic_rule"}  # says nothing about these model settings
    judged = [v["verdict"] for k, v in verdicts.items() if v["verdict"] != "pending" and k not in templates]
    rate = sum(v == "approve" for v in judged) / len(judged) if judged else None
    attempts = run["attempts"] + (run.get("check") or {}).get("attempts", [])
    tokens = sum(a["input_tokens"] + a["output_tokens"] for a in attempts)
    failed = any(a["outcome"] != "answered" for a in attempts) or not run.get("ok")
    obs = {"regime": gridmod.REGIME, "cell": cell, "latency_ms": float(run["seconds"]) * 1000, "tokens_used": tokens,
           "cold_steps_avoided": int(run["counts"]["reuse"]["answered_no_model"]), "perturbation_min_score": rate if rate is not None else 0.0, "had_error": failed}
    made = costs.record_observation(**obs)
    observations.append(obs)
    result = {"cell_id": cid, "approve_rate": rate, "utility": round(made.utility_score, 4), "run_id": run["run_id"]}
    if rec.stage == "dispatched":
        ledger.advance_stage(cid, "evaluated", evidence={"latency_ms": obs["latency_ms"], "tokens": tokens, "run_id": run["run_id"]})
    if rec.stage == "evaluated":
        neighbor = min(x for x in (rate, prior_rate if prior_rate is not None else rate) if x is not None) if rate is not None else 0.0
        cliff = max(0.0, (prior_rate or 0.0) - (rate or 0.0))
        proof = {"tests_passed": rate is not None and not failed, "neighbor_min": neighbor, "cliff_drop": cliff, "run_id": run["run_id"]}
        try:
            ledger.advance_stage(cid, "verified", evidence=proof)
            ledger.advance_stage(cid, "promoted", evidence=proof)
        except ValueError as exc:
            result["not_verified"] = str(exc)[:200]
    result["stage"] = rec.stage
    return result


def retrain_trigger(fabric: Any, runs: list[dict[str, Any]], items: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any] | None:
    """Enough checked examples: export a real dataset and create a real Task for a person or trainer.
    It only queues the Task; nothing here starts or pays for training."""
    rows = []
    for key, value in sorted(items.items()):
        check = value.get("check") or {}
        if check.get("verdict") in ("approve", "reject") and value.get("labels") and value.get("maker_model") != "deterministic_rule":  # a template is not training data
            rows.append({"key": key, "input": {"name": value["full_name"], "description": value["description"], "topics": value["topics"]},
                         "output": value["labels"], "maker_model": value["maker_model"], "verdict": check["verdict"], "run": value.get("made_in_run")})
    if len(rows) < int(spec["parameters"]["settings"]["retrain_min_examples"]):
        return {"state": "not_enough_examples", "examples": len(rows)}
    dataset_digest = core.digest(rows)
    key = core.DATASET_PREFIX + dataset_digest[:16]
    if fabric.get(core.RECORD_STORE, key) is None:
        fabric.put(core.RECORD_STORE, key, {"kind": "task_object", "schema": "teleion.omninode.dataset.v1", "node": spec["id"], "rows": rows, "digest": dataset_digest,
                                            "contains": "public repository metadata and checked labels only"}, expected=None, tags=["kind:instructions", "kind:training_dataset"])
        task_id = f"omninode_retrain_{dataset_digest[:16]}"
        fabric.enqueue(queue=TRAINING_QUEUE, task_id=task_id, kind=KIND, brief={
            "title": "Consider retraining the feed labeler on this dataset", "node": spec["id"], "dataset_record": f"{core.RECORD_STORE}/{key}", "examples": len(rows),
            "spend": "This Task starts no training. Paid training needs a Kaggle or Modal run posted in COORDINATION first.",
            "held_out": "A fine-tune replaces a default only after it beats it on held-out tests; a checker never shares a fine-tune or its data with the maker."})
        return {"state": "task_created", "task_id": task_id, "dataset_record": key, "examples": len(rows)}
    return {"state": "already_exported", "dataset_record": key, "examples": len(rows)}


def step(fabric: Any, now: float) -> dict[str, Any] | None:
    latest = fabric.get(core.RECORD_STORE, core.LATEST_KEY)
    if not latest or latest[0].get("status") != "checked":
        return None
    run_id = latest[0]["run_id"]
    spec, spec_version = fabric.get(core.RECORD_STORE, core.SPEC_KEY)
    model = spec["parameters"]["model"]
    runs_rows = fabric.list(core.RECORD_STORE, prefix=core.RUN_PREFIX, limit=200)
    runs = sorted((v for _k, v, _ in runs_rows), key=lambda r: r["run_id"])
    outcomes = outcomes_from_runs(runs, model["rewards"])
    before = dict(model["mix"]["make"])
    nxt = next_mix(model, outcomes, now)
    grid = gridmod.node_grid()
    stored = fabric.get(core.RECORD_STORE, core.GRID_KEY)
    ledger, costs = gridmod.load_ledger(grid, stored[0] if stored else None)
    observations = list((stored[0] if stored else {}).get("observations") or [])
    this = next(r for r in runs if r["run_id"] == run_id)
    prior = (stored[0] if stored else {}).get("last_rate")
    walked = walk_grid(ledger, costs, grid, spec, this, prior, observations)
    share = grid.bounds.clamp_value("label_share_muse_spark", nxt["mix"]["make"][gridmod.SPARK])
    share = round(share, 4)
    new_mix = {gridmod.SPARK: share, gridmod.WONDER: round(1.0 - share, 4)}
    spec["parameters"]["model"] = {**nxt, "mix": {"make": new_mix}, "inputs": {"outcomes": len(outcomes), "refs": nxt["inputs"]["refs"][-40:]}}
    # The grid gates batch size: only a parameter set that reached `promoted` may widen the batch.
    settings = spec["parameters"]["settings"]
    batch_before = int(settings["batch_size"])
    if walked["stage"] == "promoted":
        settings["batch_size"] = grid.bounds.clamp_value("batch_size", batch_before + 2)
    excluded = excluded_outcomes(runs)
    change = {
        "tuner_version": nxt["tuner_version"], "at": core.utc_stamp(now), "from_spec_version": spec_version, "caused_by_run": run_id,
        "parameter": "parameters.model.mix.make", "from": before, "to": new_mix, "method": "Thompson sampling over recorded outcomes",
        "outcomes": len(outcomes), "stats": nxt["stats"], "grid": walked,
        "batch_size": {"from": batch_before, "to": settings["batch_size"], "gate": "the run's parameter set reached promoted" if walked["stage"] == "promoted" else "held: the set did not reach promoted"},
        "excluded_from_outcomes": excluded,
        "reading": "An uncontrolled trace, not a model comparison: the models saw different items, were graded by each other, and settings changed between runs. Shares are small-sample and include a cost penalty.",
    }
    spec["change_log"] = (spec.get("change_log") or [])[-19:] + [change]
    cand = gridmod.cell_of(spec, grid)
    cid = ledger.register_cell(cand, regime=gridmod.REGIME)
    if ledger.get_record(cid).stage == "represented":
        ledger.advance_stage(cid, "applicable")
        ledger.advance_stage(cid, "proposed", evidence={"tuner_version": nxt["tuner_version"], "from_run": run_id})
    items = {k: v for k, v, _ in fabric.list(core.ITEMS_STORE, limit=200)}
    spec["last_retrain_trigger"] = retrain_trigger(fabric, runs, items, spec)
    saved = fabric.put(core.RECORD_STORE, core.SPEC_KEY, spec, expected=spec_version, tags=["kind:instructions", "kind:omninode_spec"])
    fabric.put(core.RECORD_STORE, core.GRID_KEY, gridmod.dump_state(ledger, observations, last_rate=walked["approve_rate"], current_cell=cid),
               expected=stored[1] if stored else None, tags=["kind:instructions", "kind:omninode_grid"])
    fabric.put(core.RECORD_STORE, core.LATEST_KEY, {**latest[0], "status": "tuned", "next_spec_version": saved}, expected=latest[1], tags=["kind:instructions"])
    return {"run_id": run_id, "spec_version": saved, "change": change, "retrain": spec["last_retrain_trigger"]}


def main() -> int:
    label = os.environ.get("OMNINODE_LABEL", "omninode-feed-tuner")
    fabric = core.from_env(label)
    latest = fabric.get(core.RECORD_STORE, core.LATEST_KEY)
    if not latest or latest[0].get("status") != "checked":
        print("no checked run to learn from")
        return 0
    task_id = f"omninode_tune_{latest[0]['run_id']}"
    fabric.enqueue(queue=QUEUE, task_id=task_id, kind=KIND, brief={"title": "Tune the OmniNode feed from recorded outcomes", "node": core.NODE_ID, "run_id": latest[0]["run_id"]})
    lease = fabric.claim(QUEUE, KIND)
    if lease is None:
        print("nothing to claim")
        return 1
    if (lease.brief or {}).get("node") != core.NODE_ID:
        print(f"claimed a Task that is not this node's: {lease.task_id}")
        return 1
    try:
        done = step(fabric, time.time())
    except Exception as exc:
        fabric.submit(lease.task_id, lease.fencing_token, {"status": "failed"}, ok=False, error=f"{type(exc).__name__}: {str(exc)[:300]}",
                      report=core.execution_report("tuner", label, "Tune the OmniNode feed from recorded outcomes", f"failed: {type(exc).__name__}", []))
        raise
    receipt = fabric.submit(lease.task_id, lease.fencing_token, {"status": "tuned", **(done or {})}, ok=True,
                            report=core.execution_report("tuner", label, "Tune the OmniNode feed from recorded outcomes", f"tuned from run {latest[0]['run_id']}", []))
    spec, version = fabric.get(core.RECORD_STORE, core.SPEC_KEY)
    published = Shim("omninode-feed-tuner", Path(os.environ.get("OMNINODE_SHIM_CRED", str(Path.home() / ".config/eranos-worker/omninode-shim-tuner.json")))).publish(
        {"omninode_feed_maintenance_spec": {"summary": "The current spec of the feed maintenance OmniNode on Teleion Fabric: its tools, skills, model mix, hooks and settings, with every change the tuner made.",
                                             "category": "omninode_spec", "search_hints": ["omninode", "spec", "feed", "tuner"], "payload": {"fabric_version": version, "spec": spec}}},
        f"OmniNode spec version {version}", f"omninode_spec_v{version}")
    shim = Shim("omninode-feed-tuner", Path(os.environ.get("OMNINODE_SHIM_CRED", str(Path.home() / ".config/eranos-worker/omninode-shim-tuner.json"))))
    runs = {}
    for key, value, _ in fabric.list(core.RECORD_STORE, prefix=core.RUN_PREFIX):
        object_key = "omninode_feed_run_" + key.removeprefix(core.RUN_PREFIX).lower()
        if value.get("check") and shim.http.get(f"/q/object/{object_key}").status_code != 200:
            runs[object_key] = {"summary": f"A recorded run of the feed maintenance OmniNode on Teleion Fabric, with which mode handled each item, tokens, cost and outcome: {value['run_id']}.",
                                "category": "omninode_run", "search_hints": ["omninode", "feed", "run", "trace"], "payload": value}
    runs_published = shim.publish(runs, "OmniNode run records", f"omninode_runs_{latest[0]['run_id']}") if runs else None
    print(json.dumps({"receipt": receipt, "spec_published": published, "runs_published": runs_published, **(done or {})})[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
