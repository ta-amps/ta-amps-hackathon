"""The `@`: a different worker, a different Fabric key, its own Durable Task. Re-reads the source itself,
re-runs the rule, and asks the other Muse model. It approves or rejects; it never labels."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from eranos.model_client import BudgetExhausted, ModelUnavailable, UsageMeter
from src.universal_omninode_closure import CheckerOmniNode, OmniNodeResult

from omninode_live import core, feed, grid as gridmod, prestep
from omninode_live.shim import Shim, item_object, public_key

QUEUE, KIND = "eq03", "review"
TRANSIENT = {"github_allowance_spent", "github_unreachable"}  # says nothing about the item
OTHER = {"muse-spark-1.3": "muse-wonder-1.0", "muse-wonder-1.0": "muse-spark-1.3"}


class LiveFeedChecker(CheckerOmniNode):
    def __init__(self, *, fabric: Any, github: Any, screen: Any, models: Any, spec: dict[str, Any], grid: Any, cell: Any) -> None:
        self.fabric, self.github, self.screen, self.models, self.spec = fabric, github, screen, models, spec
        self.attempts: list[dict[str, Any]] = []
        super().__init__(node_id="independent_feed_check", checker_worker_key=fabric.key_id, grid=grid, cell=cell)

    def _source_check(self, value: dict[str, Any]) -> list[str]:
        if not self.github.spare():
            return ["github_allowance_spent"]
        s = self.spec["parameters"]["settings"]
        state, now = self.github.repo(value["full_name"])
        if state == "unreachable":
            return ["github_unreachable"]
        if state == "gone" or now is None:
            return ["source_gone"]
        found: list[str] = []
        if now["license"] != value["license"]:
            found.append(f"license_differs:{now['license']}")
        if now["license"] not in s["allowed_licenses"]:
            found.append("license_not_allowed")
        if now["description"] != value["description"] or now["topics"] != value["topics"]:
            found.append("source_text_changed")
        if self.screen.blocked(" ".join([now["full_name"], now["description"], *now["topics"]])):
            found.append("word_list")
        if value["content_digest"] != feed.content_digest(value):
            found.append("digest_mismatch")
        return found

    def _audit(self, model_id: str, rows: list[tuple[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
        meter = UsageMeter()
        payload = [{"key": k, "description": v["description"], "topics": v["topics"], "name": v["full_name"],
                    "category": v["labels"]["category"], "determinism": v["labels"]["determinism"], "use_cases": v["labels"]["use_cases"],
                    "evidence": v["labels"]["evidence"], "summary": v["labels"]["summary"]} for k, v in rows]
        attempt: dict[str, Any] = {"step": "audit", "model": model_id, "fine_tune": None, "item_keys": [k for k, _ in rows]}
        started = time.time()
        try:
            answer = self.models(model_id).chat_json(self.spec["parameters"]["skills"]["audit"]["system"], json.dumps(payload, ensure_ascii=False),
                                                     meter=meter, max_tokens=int(self.spec["parameters"]["settings"].get("max_output_tokens", 8000)), temperature=0.0)
            attempt["outcome"] = "answered" if "unparsed" not in answer else "unparsed"
        except BudgetExhausted as exc:
            answer = {}
            attempt.update(outcome="refused_by_ceiling", error=str(exc)[:200])
        except ModelUnavailable as exc:
            answer = {}
            attempt.update(outcome="failed", error=str(exc)[:200])
        attempt.update(seconds=round(time.time() - started, 2), calls=len(meter.calls), input_tokens=meter.input_tokens,
                       output_tokens=meter.output_tokens, cost_usd=meter.cost_usd)
        self.attempts.append(attempt)
        rows_out = answer.get("checks") if isinstance(answer, dict) else None
        return {str(r.get("key")): r for r in rows_out if isinstance(r, dict)} if isinstance(rows_out, list) else {}

    def _execute_core(self, envelope: dict[str, Any], context: dict[str, Any]) -> OmniNodeResult:
        run, fabric = envelope["maker_output"], self.fabric
        maker = str(envelope["maker_worker_key"])
        if maker.lower() == self.checker_worker_key.lower():
            return OmniNodeResult(ok=False, output={}, node_id=self.node_id, role=self.role, placement_scope=self.placement_scope, latency_ms=0.0,
                                  diagnostics={"error_code": "self_review_conflict"})
        pending, verdicts, reuse_checks, withdrawn = [], {}, [], []
        for row in run["items"]:
            if row["status"] == "awaiting_check":
                found = fabric.get(core.ITEMS_STORE, row["key"])
                if found:
                    pending.append((row["key"], found[0], found[1], row))
        by_model: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        settings = self.spec["parameters"]["settings"]
        for key, value, _version, _row in pending:
            if value.get("fine_tune"):
                verdicts[key] = {"verdict": "reject", "findings": ["maker_used_a_fine_tune_this_checker_cannot_vouch_for"]}
                continue
            found = self._source_check(value)
            rule = feed.validate_label({**value["labels"]}, value, settings, self.screen)
            if found or rule:
                # A spent GitHub allowance is not a finding about the item: it stays pending.
                verdicts[key] = {"verdict": "pending" if set(found) & TRANSIENT else "reject", "findings": found + rule}
                continue
            by_model.setdefault("muse-spark-1.3" if value["maker_model"] == "deterministic_rule" else OTHER[value["maker_model"]], []).append((key, value))
        for model_id, rows in by_model.items():
            for start in range(0, len(rows), 6):
                group = rows[start : start + 6]
                answers = self._audit(model_id, group)
                for key, _value in group:
                    a = answers.get(key) or {}
                    reason = str(a.get("reason") or "")[:240]
                    if self.screen.visible_hit(reason) or feed._URL.search(reason) or feed._EMAIL.search(reason):
                        reason = "(the reason was withheld by the word list)"
                    if a.get("verdict") == "approve":
                        verdicts[key] = {"verdict": "approve", "audit_model": model_id, "reason": reason, "findings": []}
                    elif a.get("verdict") == "reject":
                        verdicts[key] = {"verdict": "reject", "audit_model": model_id, "reason": reason, "findings": ["audit_model_rejected"]}
                    else:
                        verdicts[key] = {"verdict": "pending", "audit_model": model_id, "findings": ["no_audit_answer"]}
        for key, value, version, _row in pending:
            verdict = verdicts.get(key) or {"verdict": "pending", "findings": ["not_checked"]}
            stamp = {**verdict, "checker_key_id": self.checker_worker_key, "maker_key_id": maker, "run_id": run["run_id"], "at": core.utc_stamp()}
            value["check"] = stamp
            status = {"approve": "status:verified", "reject": "status:rejected"}.get(verdict["verdict"], "status:pending_check")
            fabric.put(core.ITEMS_STORE, key, value, expected=version, tags=["kind:feed_item", "omninode:feed-maintenance", status, f"license:{value['license']}"])
            verdict["value"] = value
        for row in [r for r in run["items"] if r["status"] == "reused"][: int(settings["reuse_sample_checks"])]:
            found = fabric.get(core.ITEMS_STORE, row["key"])
            if found:
                problems = self._source_check(found[0])
                reuse_checks.append({"key": row["key"], "from_version": row.get("reused_from_version"), "findings": problems})
                if problems and not set(problems) & TRANSIENT and "source_text_changed" not in problems:
                    value = {**found[0], "check": {**found[0]["check"], "verdict": "reject", "findings": problems, "withdrawn_in_run": run["run_id"]}}
                    fabric.put(core.ITEMS_STORE, row["key"], value, expected=found[1], tags=["kind:feed_item", "omninode:feed-maintenance", "status:rejected", f"license:{value['license']}"])
                    withdrawn.append(row["key"])
        return OmniNodeResult(ok=True, output={"verdicts": verdicts, "reuse_checks": reuse_checks, "withdrawn": withdrawn}, node_id=self.node_id, role=self.role,
                              placement_scope=self.placement_scope, latency_ms=0.0,
                              tokens_used=sum(a["input_tokens"] + a["output_tokens"] for a in self.attempts))


def main() -> int:
    label = os.environ.get("OMNINODE_LABEL", "omninode-feed-checker")
    fabric = core.from_env(label)
    latest = fabric.get(core.RECORD_STORE, core.LATEST_KEY)
    if not latest or latest[0].get("status") != "awaiting_check":
        print("no run is awaiting a check")
        return 0
    run_id = latest[0]["run_id"]
    run, run_version = fabric.get(core.RECORD_STORE, core.RUN_PREFIX + run_id)
    if run["maker_key_id"] == fabric.key_id:
        print("refused: this worker's key made this run", file=sys.stderr)
        return 2
    spec, _ = fabric.get(core.RECORD_STORE, core.SPEC_KEY)
    task_id = f"omninode_check_{run_id}"
    # Live reviewers work this queue and kind. If a Task of theirs is ready, leave it alone and check next time.
    foreign = [v["id"] for v in fabric.ready(QUEUE, KIND) if (v.get("brief") or {}).get("node") != spec["id"]]
    if foreign:
        print(f"a live review Task is ready ({len(foreign)}); this check waits for the next run")
        return 0
    # Owned by this key and private, so only this key sees it; enqueued and claimed at once.
    fabric.enqueue(queue=QUEUE, task_id=task_id, kind=KIND, visibility="private",
                   brief={"title": "Check an OmniNode feed run", "node": spec["id"], "run_id": run_id, "maker_key_id": run["maker_key_id"]})
    lease = fabric.claim(QUEUE, KIND)
    for _ in range(3):  # an earlier check that lost its lease comes back first: close it on the record
        if lease is None or lease.task_id == task_id or (lease.brief or {}).get("node") != spec["id"]:
            break
        fabric.submit(lease.task_id, lease.fencing_token, {"status": "superseded", "by": task_id}, ok=False, error="superseded by a newer check",
                      report=core.execution_report("checker", label, "Check an OmniNode feed run", "superseded by a newer check", []))
        lease = fabric.claim(QUEUE, KIND)
    if lease is None or lease.task_id != task_id:
        print(f"claim did not return this check's Task: {getattr(lease, 'task_id', None)}", file=sys.stderr)
        return 1
    beat = core.Heartbeat(lambda: fabric.heartbeat(lease.task_id, lease.fencing_token), float(lease.heartbeat_seconds or 60))
    beat.start()
    ledger = core.ledgers()
    catalog, _ = fabric.get(core.RECORD_STORE, "models.meta")
    cache: dict[str, Any] = {}
    grid = gridmod.node_grid()
    checker = LiveFeedChecker(fabric=fabric, github=feed.GitHub(), screen=core.Screen(), spec=spec, grid=grid, cell=gridmod.cell_of(spec, grid),
                              models=lambda m: cache.setdefault(m, core.meta_model(m, catalog, ledger, effort=str(spec["parameters"]["settings"].get("reasoning_effort", "low")))))
    try:
        result = checker.execute({"maker_worker_key": run["maker_key_id"], "maker_output": run}, {"checker_worker_key": fabric.key_id})
        verdicts = result.output.get("verdicts") or {}
        shim = Shim("omninode-feed-checker", Path(os.environ.get("OMNINODE_SHIM_CRED", str(Path.home() / ".config/eranos-worker/omninode-shim-checker.json"))))
        # Every approved item not yet readable publicly, from this run or an earlier one.
        objects: dict[str, dict[str, Any]] = {}
        unpublished = {}
        for key, value, version in fabric.list(core.ITEMS_STORE):
            if (value.get("check") or {}).get("verdict") == "approve" and not value.get("public_object"):
                obj = item_object(key, value, value.get("made_in_run") or run_id, (value.get("check") or {}).get("maker_key_id") or run["maker_key_id"], fabric.key_id, checker.screen.visible_hit)
                if obj:
                    object_key = public_key(key)
                    objects[object_key] = obj
                    unpublished[object_key] = (key, value, version)
        published = shim.publish(objects, f"OmniNode feed run {run_id}: {len(objects)} checked items", f"{task_id}:publish:{len(objects)}") if objects else {"status": None, "ok": True, "readable": [], "sent": 0}
        for object_key in published["readable"]:
            key, value, version = unpublished[object_key]
            fabric.put(core.ITEMS_STORE, key, {**value, "public_object": object_key}, expected=version,
                       tags=["kind:feed_item", "omninode:feed-maintenance", "status:verified", f"license:{value['license']}"])
        check = {
            "by_worker": label, "checker_key_id": fabric.key_id, "task_id": task_id, "fencing_token": lease.fencing_token, "ok": result.ok,
            "verdicts": {k: {x: v[x] for x in v if x != "value"} for k, v in verdicts.items()},
            "reuse_checks": result.output.get("reuse_checks") or [], "withdrawn": result.output.get("withdrawn") or [], "attempts": checker.attempts, "published": published,
            "published_keys": sorted(objects), "github_calls": checker.github.calls,
            "tokens": {"input": sum(a["input_tokens"] for a in checker.attempts), "output": sum(a["output_tokens"] for a in checker.attempts)},
            "cost_usd": round(sum(a["cost_usd"] for a in checker.attempts), 6),
        }
        prestep.record_check(run_id, check["verdicts"])
        run["check"], run["status"] = check, "checked" if result.ok else "check_failed"
        fabric.put(core.RECORD_STORE, core.RUN_PREFIX + run_id, run, expected=run_version, tags=["kind:instructions", "kind:omninode_run"])
        latest = fabric.get(core.RECORD_STORE, core.LATEST_KEY)
        fabric.put(core.RECORD_STORE, core.LATEST_KEY, {**latest[0], "status": run["status"]}, expected=latest[1], tags=["kind:instructions"])
    except Exception as exc:
        beat.stop()
        fabric.submit(lease.task_id, lease.fencing_token, {"status": "failed", "run_id": run_id}, ok=False,
                      error=f"{type(exc).__name__}: {str(exc)[:300]}", report=core.execution_report("checker", label, "Check an OmniNode feed run", f"failed: {type(exc).__name__}", checker.attempts))
        raise
    beat.stop()
    tally = {x: sum(v["verdict"] == x for v in verdicts.values()) for x in ("approve", "reject", "pending")}
    receipt = fabric.submit(lease.task_id, lease.fencing_token, {"status": run["status"], "run_id": run_id, "verdicts": tally}, ok=result.ok,
                            report=core.execution_report("checker", label, "Check an OmniNode feed run", f"checked run {run_id}: {tally}", checker.attempts))
    print(json.dumps({"run_id": run_id, "task_id": task_id, "receipt": receipt, "verdicts": tally, "published": published, "cost_usd": check["cost_usd"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
