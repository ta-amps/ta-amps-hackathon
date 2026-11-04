"""The public learning record: six loops that write something back, from the data, with "not measured" where that is true.

Every number comes from a live read or a record on this machine at the moment it runs. Run: learning_record.py [--publish]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for extra in ("agents/warm-server-agent/src", "omninode"):
    sys.path.insert(0, str(REPO / extra))

STATE = Path.home() / ".local/state/eranos-worker"
SHIM, FABRIC = "https://shim.teleionlabs.com", "https://fabric.teleionlabs.com"
H = {"authorization": "Bearer " + os.environ["FABRIC_KEY"], "x-surface-id": "eranos"}
NOT_MEASURED = "not measured"
RECORD_KEY = "fabric_learning_record"
NOTHING = re.compile(r"(?i)\bno (auditable|executed|actual|deliverable|work product|task statement)|missing|not provided|absent|nothing")
CANDIDATE = "muse_glimmer_30b_orchestrator_v1"


def fabric(path: str) -> Any:
    r = requests.get(FABRIC + path, headers=H, timeout=60)
    r.raise_for_status()
    return r.json()


def shim(path: str) -> Any:
    r = requests.get(SHIM + path, timeout=60)
    r.raise_for_status()
    return r.json()


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def iso(t: float | None) -> str | None:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)) if t else None


def shim_scoring() -> dict[str, Any]:
    arms = shim("/q/routing").get("learned_ucb_arms") or []
    busiest = sorted(arms, key=lambda a: -int(a.get("dispatch_count") or 0))[:3]
    return {
        "loop": "Shim claim scoring",
        "what_changes": "A learned bonus by worker tier, Task complexity and Task kind, added to each claim's score.",
        "outcomes": sum(int(a.get("dispatch_count") or 0) for a in arms),
        "arms": len(arms),
        "busiest": [{k: a.get(k) for k in ("harness_tier", "complexity_bucket", "verb_kind", "dispatch_count", "success_count")} for a in busiest],
        "last_change": max((str(a.get("updated_at") or "") for a in arms), default=None),
        "changes_later_behavior": "Yes: the bonus is part of every claim's score.",
        "measured_better": NOT_MEASURED,
    }


def kit_bandit() -> dict[str, Any]:
    data = shim("/q/experiments")
    arms = data.get("arms") or []
    states: dict[str, int] = {}
    for a in arms:
        states[str(a.get("lifecycle_state"))] = states.get(str(a.get("lifecycle_state")), 0) + 1
    return {
        "loop": "Prompt-kit trials",
        "what_changes": "Which starter prompt and kit a new worker is shown.",
        "outcomes": sum(int(a.get("exposures") or 0) for a in arms),
        "arms": len(arms),
        "arms_by_state": states,
        "changes_later_behavior": "Yes: an arm picks what a new worker sees.",
        "measured_better": NOT_MEASURED,
        "finding": f"{states.get('promoted', 0)} of {len(arms)} arms are promoted, so promotion barely tells them apart.",
    }


def feed_tuner() -> dict[str, Any]:
    spec = fabric("/v1/stores/eranos.instructions/records/omninode.feed-maintenance.spec")
    value = spec["value"]
    model = value["parameters"]["model"]
    log = value.get("change_log") or []
    runs = fabric("/v1/stores/eranos.instructions/records?prefix=omninode.feed-maintenance.run.&limit=100").get("records") or []
    return {
        "loop": "Feed OmniNode tuner",
        "what_changes": "The share of labeling work between Muse Spark and Muse Wonder, and the batch size.",
        "outcomes": (model.get("inputs") or {}).get("outcomes"),
        "mix": model.get("mix"),
        "spec_version": spec.get("version"),
        "runs_on_record": len(runs),
        "last_change": log[-1].get("at") if log else None,
        "changes_later_behavior": "Yes for the mix: the next run reads it.",
        "measured_better": NOT_MEASURED,
        "finding": "Its own record calls this an uncontrolled trace. On November 4 the search was widened by hand, because most runs found nothing new.",
    }


def policy_history() -> list[dict[str, Any]]:
    rows = fabric("/v1/stores/eranos.instructions/records/worker.policy/history").get("versions") or []
    return sorted(rows, key=lambda r: int(r.get("version") or 0))


def eranos_tuner(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest = rows[-1]["value"]
    counts = [int(((r.get("value") or {}).get("inputs") or {}).get("outcomes") or 0) for r in rows]
    rose = sum(1 for a, b in zip(counts, counts[1:]) if b > a)
    by_step: dict[str, int] = {}
    variants = {v.get("id"): v for v in latest.get("variants") or []}
    for vid, stat in (latest.get("stats") or {}).items():
        step = str((variants.get(vid) or {}).get("step"))
        by_step[step] = by_step.get(step, 0) + int(stat.get("outcomes") or 0)
    return {
        "loop": "Eranos worker tuner",
        "what_changes": "The share of each step between Muse models.",
        "outcomes": counts[-1] if counts else 0,
        "outcomes_by_step": by_step,
        "versions": len(rows),
        "versions_with_more_outcomes": rose,
        "last_change": iso(float(rows[-1].get("created_at") or 0)),
        "mix": latest.get("mix"),
        "changes_later_behavior": "Yes for making: workers draw from the mix.",
        "measured_better": NOT_MEASURED,
        "finding": f"Until November 4 a new version was written on a timer, even with no new outcome: outcomes rose in {rose} of {max(0, len(rows) - 1)} steps. It now writes only on new outcomes. "
        "Checking's mix before that was its starting point plus noise from a changing random seed, not learning.",
    }


def variant_writing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest = rows[-1]["value"]
    stats = latest.get("stats") or {}
    written = [v for v in latest.get("variants") or [] if (v.get("origin") or {}).get("by") == "tuner"]
    return {
        "loop": "Variant writing",
        "what_changes": "A Muse model drafts a new worker persona from recorded failures. One that passes the rules runs at a small share.",
        "outcomes": sum(int((stats.get(v.get("id")) or {}).get("outcomes") or 0) for v in written),
        "variants_written": [{"id": v.get("id"), "status": v.get("status"), "outcomes": int((stats.get(v.get("id")) or {}).get("outcomes") or 0)} for v in written],
        "changes_later_behavior": "Only if drawn.",
        "measured_better": NOT_MEASURED,
    }


def replay_from_start(audited: list[bool]) -> dict[str, Any]:
    """The registry's own rule on a copy, from the first audited answer. The live registry is untouched."""
    from warm_agent.canary_and_tuner import ModelCanaryRegistry
    from warm_agent.grid_config import load_warm_agent_grid

    with tempfile.TemporaryDirectory() as d:
        copy = Path(d) / "r.json"
        shutil.copy(STATE / "warm-canary-registry.json", copy)
        saved = json.loads(copy.read_text())
        saved["candidates"][CANDIDATE].update(status="canary_active", recent_outcomes=[], samples_at_current_rung=0)
        copy.write_text(json.dumps(saved))
        registry = ModelCanaryRegistry(load_warm_agent_grid(), state_path=copy)
        policy = registry.policy
        for n, passed in enumerate(audited, 1):
            cand = registry.record_live_outcome(CANDIDATE, passed=passed)
            if cand.status == "rolled_back":
                return {"would_have_rolled_back_at_sample": n, "passed_by_then": sum(audited[:n]), "floor": policy["rollback_pass_rate_floor"], "min_samples": policy["min_canary_samples_per_rung"]}
    return {"would_have_rolled_back_at_sample": None, "floor": policy["rollback_pass_rate_floor"]}


def fine_tune_switch() -> dict[str, Any]:
    rows = jsonl(HERE / "records/decisions.jsonl")
    audited = [r for r in rows if isinstance(r.get("audit_pass"), bool)]
    results = [bool(r["audit_pass"]) for r in audited]
    picks = sum(1 for r in audited if r.get("outcome") == "route")
    registry = json.loads((STATE / "warm-canary-registry.json").read_text())["candidates"][CANDIDATE]
    cursor = json.loads((STATE / "warm-decider-audit-cursor.json").read_text()) if (STATE / "warm-decider-audit-cursor.json").exists() else {}
    last = results[-12:]
    return {
        "loop": "Fine-tune audit switch",
        "what_changes": "A fine-tuned Muse Glimmer's small share of Tasks: up a step on good audits, off if they drop.",
        "outcomes": len(audited),
        "audit_passed": sum(results),
        "of_audited_answers_picks": picks,
        "of_audited_answers_said_nothing_fits": len(audited) - picks,
        "last_12_pass_rate": round(sum(last) / len(last), 3) if last else None,
        "registry_now": {"status": registry.get("status"), "share": registry.get("rollout_share"), "live_samples_since_wiring": len(registry.get("recent_outcomes") or [])},
        "wired_at_row": cursor.get("rows_read"),
        "changes_later_behavior": "The switch has never fired on a live result. Audits were wired into the registry on November 4 and it counts from that point on.",
        "measured_better": NOT_MEASURED,
        "replay_from_the_first_audit": replay_from_start(results),
        "decision_on_the_replay": "Replayed from the start, the rule would have switched this model off early. That series ran before the registry was wired, and overall results did not drop, so the agent coordinating this work chose to start the count from now, with the rule unchanged. If the count from now falls below the floor, it switches off.",
        "open_design_question": "A rollback that can't undo itself, with a 0.70 floor and only a few samples, may fire on the start of any series. Nothing about this was changed on November 4.",
    }


def checks_of_warm_work() -> dict[str, Any]:
    traces = jsonl(STATE / "warm-training-traces.jsonl")
    checks = [t for t in traces if t.get("role") == "checker"]
    old = [t for t in checks if not t.get("attempt_status")]
    new = [t for t in checks if t.get("attempt_status") == "verified_and_stored"]
    verdicts: dict[str, int] = {}
    for t in new:
        verdicts[str(t.get("target_verdict"))] = verdicts.get(str(t.get("target_verdict")), 0) + 1
    log = jsonl(STATE / "warm-agent.jsonl")
    refused = sum(1 for e in log if e.get("kind") == "checker_refused_missing_target")
    return {
        "before_the_fix": {"claims_refused_for_having_no_target": refused, "answers_on_record": len(old), "answers_saying_there_was_nothing_to_check": sum(1 for t in old if NOTHING.search(str(t.get("output_sanitized")))), "note": "Those answers were given a Task's activity numbers, not any work."},
        "since_the_fix": own_checker_counts() or verdicts,
        "note_on_that_count": "Plain Muse Wonder, a different worker from the maker. Most no-key makers don't say which model they used, so those read different worker, model not known. A judge's reading, not a measure of real-world quality.",
    }


def own_checker_counts() -> dict[str, Any] | None:
    """Read-only counts from your shim database, when these settings name it. Without them, the caller's counts stand."""
    where, database, checker = (os.environ.get(n, "").strip() for n in ("LEARNING_D1_DIR", "LEARNING_D1_DATABASE", "WARM_AGENT_CHECKER_NAME"))
    since = os.environ.get("LEARNING_CHECKS_SINCE", "2026-11-04T14:50").strip()
    if not (where and database and checker) or not re.fullmatch(r"[\w.-]+", checker) or not re.fullmatch(r"[\dT:-]+", since):
        return None
    sql = (
        "SELECT CASE WHEN e.rationale LIKE 'The maker%' THEN 'model_not_known' ELSE 'model_known' END m, e.verification_verdict v, COUNT(*) n "
        f"FROM herma_evaluations e WHERE e.evaluator_agent_id='{checker}' AND e.target_kind='object' AND e.created_at >= '{since}' GROUP BY 1,2"
    )
    out = subprocess.run(["npx", "-y", "wrangler@4.154.0", "d1", "execute", database, "--remote", "--json", "--command", sql], cwd=where, capture_output=True, text=True, timeout=90).stdout
    rows = json.JSONDecoder().raw_decode(out[out.index("["):])[0][0]["results"]
    result: dict[str, Any] = {"passed": 0, "failed": 0, "maker_model_not_known": 0}
    for r in rows:
        result["passed" if r["v"] == "CONFIRMED" else "failed"] += r["n"]
        if r["m"] == "model_not_known":
            result["maker_model_not_known"] += r["n"]
    return result


def build() -> dict[str, Any]:
    history = policy_history()
    tasks = fabric("/v1/verbs?status=ready&limit=100").get("verbs") or []
    retrain = [t for t in tasks if str(t.get("task_id")).startswith("omninode_retrain")]
    traces = jsonl(STATE / "warm-training-traces.jsonl")
    return {
        "schema": "teleion.fabric.learning_record.v1",
        "generated_at": iso(time.time()),
        "how_to_read": 'A timer firing is not counted. "not measured" means no test compares results with and without the loop. All real work here is our own fleet\'s or our own example requests; no outside users are on record.',
        "loops": [shim_scoring(), kit_bandit(), feed_tuner(), eranos_tuner(history), variant_writing(history), fine_tune_switch()],
        "negative_findings": {
            "checks_of_the_always_on_agent": checks_of_warm_work(),
            "retraining": {"tasks_waiting": len(retrain), "admitted_as_training_examples": sum(1 for t in traces if t.get("training_admitted")), "of_traces": len(traces), "note": "No model has retrained from these Tasks: nobody claims them."},
            "not_learning": [
                "The always-on agent's persona tuner has one persona per role, keeps its numbers in memory, and its maker's reward can't drop.",
                "The decider's choices aren't credited with outcomes.",
            ],
        },
    }


def main() -> int:
    body = build()
    from omninode_live.shim import Shim
    from warm_agent.banned_words_guard import BannedWordsGuard
    from warm_agent.grid_config import load_warm_agent_grid

    guard = BannedWordsGuard(load_warm_agent_grid(None).section("endpoints_and_paths")["banned_words_path"])
    hits = guard.scan_text(json.dumps(body))
    print(json.dumps(body, indent=1)[:6000])
    if hits:
        print("WORD LIST HITS, not published:", hits)
        return 1
    if "--publish" in sys.argv:
        loops = body["loops"]
        summary = f"What Teleion Fabric's six learning loops changed, with outcomes, and where better results were {NOT_MEASURED}: {sum(1 for x in loops if x['measured_better'] == NOT_MEASURED)} of {len(loops)}."
        identity = Path.home() / ".config/ta-amps/fabric-decider-identity.json"
        res = Shim("fabric-decider", identity).publish(
            {RECORD_KEY: {"summary": summary, "category": "live_record", "search_hints": ["learning", "tuner", "not measured", "self tuning"], "payload": body}},
            summary,
            f"fabric-learning-{int(time.time() // 900)}",
        )
        print(json.dumps(res))
        return 0 if res["ok"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
