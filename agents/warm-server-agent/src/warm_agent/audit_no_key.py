"""Check no-key work, oldest first, with the warm checker's rules: one Task per object, a plain different model, every attempt recorded.

Run by hand: `python -m warm_agent.audit_no_key --max 20`. It stops on a run of failures, and at --max.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any

from .agent_loop import WarmServerAgent
from .grid_config import load_warm_agent_grid

SKIP_CATEGORIES = {"system_feedback_signal", "worker_issue_report", "worker_memory"}  # notes about work, not work a Task asked for
KNOWN_MAKER_MODELS = (("scale-test-", "muse-spark-1.3-contributor"),)  # from our own ledger for that test


def is_no_key_work(row: dict[str, Any]) -> bool:
    if not str(row.get("worker_uuid") or "").startswith("w_agent_"):
        return False
    if int(row.get("eval_count") or 0) > 0 or str(row.get("category") or "") in SKIP_CATEGORIES:
        return False
    return bool(row.get("source_task_id")) and str(row.get("source_task_id")) != "self_seed"


def maker_model_for(row: dict[str, Any]) -> str:
    """The model from our own ledger, or empty: no-key workers don't tell us theirs, and we won't guess."""
    agent = str(row.get("producer_agent") or "")
    for prefix, model in KNOWN_MAKER_MODELS:
        if agent.startswith(prefix):
            return model
    return ""


def spent_today(agent: WarmServerAgent) -> float:
    return float(agent.meta_client.ledger.read_snapshot().get("days", {}).get(time.strftime("%Y-%m-%d", time.gmtime())) or 0.0)


def oldest_first(agent: WarmServerAgent) -> Any:
    page = int(agent.ops["audit_page"])
    first = agent._herma_http.get("/q/objects", params={"limit": page}).json()
    offset = max(0, int(first.get("total_matching") or 0) - page)
    while True:
        rows = agent._herma_http.get("/q/objects", params={"limit": page, "offset": offset}).json().get("objects") or []
        yield from reversed(rows)
        if not offset:
            return
        offset = max(0, offset - page)


def run(agent: WarmServerAgent, *, maximum: int, pause: float, only: re.Pattern[str] | None = None) -> dict[str, int]:
    counts = dict.fromkeys(("checked", "failed", "refused_or_skipped"), 0)
    in_a_row = 0
    stop_after = int(agent.ops["audit_stop_after_failures"])
    for row in oldest_first(agent):
        if counts["checked"] >= maximum or in_a_row >= stop_after:
            break
        if spent_today(agent) >= float(agent.ops["audit_stop_at_day_usd"]):
            counts["stopped_at_day_usd"] = 1
            break
        if not is_no_key_work(row) or (only is not None and not only.search(str(row.get("object_key")))):
            continue
        read = agent._herma_http.get(f"/q/object/{row['object_key']}")
        target = read.json() if int(agent.ops["http_ok_low"]) <= read.status_code <= int(agent.ops["http_ok_high"]) else None
        if not isinstance(target, dict) or target.get("payload") is None:
            counts["refused_or_skipped"] += 1
            continue
        try:
            known = maker_model_for(row)
            done = agent.check_target(
                target,
                caller_tag="audit_no_key_step",
                maker_model=known,
                model_not_stated=not known,
                tasks_file=str(agent.ops["audit_tasks_file"]),
            )
        except Exception as exc:  # noqa: BLE001 - recorded, and a run of them stops the audit
            agent._log_event("audit_no_key_error", object_key=row["object_key"], error=type(exc).__name__)
            done = False
        if not done and agent.checker_last_step in ("no_brief", "refused"):
            counts["refused_or_skipped"] += 1  # says nothing about the model or the route; a missed claim counts below and stops a run
            continue
        key = "checked" if done else "failed"
        counts[key] += 1
        in_a_row = 0 if done else in_a_row + 1
        time.sleep(pause)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, required=True)
    parser.add_argument("--pause", type=float, default=None)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    agent = WarmServerAgent(load_warm_agent_grid(), loopback_port_override=0)
    agent.ensure_isolated_principals()
    pause = args.pause if args.pause is not None else float(agent.ops["audit_pause_seconds"])
    out = run(agent, maximum=args.max, pause=pause, only=re.compile(args.only) if args.only else None)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
