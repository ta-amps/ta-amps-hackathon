"""The feed-maintenance pipeline as runtime OmniNodes: every stage records which mode handled each item."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from eranos.model_client import BudgetExhausted, ModelUnavailable, UsageMeter
from eranos.pipeline import tuning
from src.universal_omninode_closure import CheckerOmniNode, OmniNode, OmniNodeResult

from omninode_live import prestep
from omninode_live.core import ITEMS_STORE, Heartbeat, Screen, digest

UA = "teleion-fabric-feed-maintenance/1 (public metadata only)"
_URL = re.compile(r"https?:|www\.|\b[\w-]+\.(?:com|org|net|io|ai|dev)\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.\w+")


class GitHub:
    """Public API, no credential. One search per 7 s (10 a minute is the limit), and no call once the
    allowance is nearly spent: the items wait for the next run, on the record."""

    def __init__(self, transport: httpx.BaseTransport | None = None, sleep: Any = time.sleep) -> None:
        self.http = httpx.Client(base_url="https://api.github.com", timeout=30, transport=transport, trust_env=False,
                                 headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
        self.sleep, self.calls, self.failures, self._last_search = sleep, 0, [], 0.0
        self.core_remaining: int | None = None

    def _get(self, path: str, **params: Any) -> tuple[int, Any]:
        self.calls += 1
        try:
            r = self.http.get(path, params=params or None)
        except httpx.HTTPError as exc:
            self.failures.append({"path": path, "error": type(exc).__name__})
            return 0, None
        if "/search/" not in path and r.headers.get("x-ratelimit-remaining"):
            self.core_remaining = int(r.headers["x-ratelimit-remaining"])
        if r.status_code not in (200, 404):
            self.failures.append({"path": path, "status": r.status_code})
        return r.status_code, r.json() if r.status_code == 200 else None

    def search(self, query: str, per_page: int) -> list[dict[str, Any]]:
        gap = 7.0 - (time.monotonic() - self._last_search)
        if self._last_search and gap > 0:
            self.sleep(gap)
        self._last_search = time.monotonic()
        status, data = self._get("/search/repositories", q=query, sort="stars", per_page=per_page)
        return list((data or {}).get("items") or []) if status == 200 else []

    def spare(self) -> bool:
        return self.core_remaining is None or self.core_remaining > 8

    def latest_release(self, full_name: str) -> dict[str, Any] | None:
        status, data = self._get(f"/repos/{full_name}/releases/latest")
        if status == 200 and isinstance(data, dict):
            return {"tag": str(data.get("tag_name") or "")[:80], "published_at": data.get("published_at")}
        return None

    def repo(self, full_name: str) -> tuple[str, dict[str, Any] | None]:
        """The repository as GitHub says now: ("ok", fields), ("gone", None) or ("unreachable", None).
        A failed call says nothing about the item, so it never counts as a finding."""
        status, data = self._get(f"/repos/{full_name}")
        if status == 200 and isinstance(data, dict):
            return "ok", repo_item(data)
        return ("gone", None) if status == 404 else ("unreachable", None)


def item_key(full_name: str) -> str:
    return "repo-" + re.sub(r"[^a-z0-9._-]", "--", full_name.lower())


def content_digest(item: dict[str, Any]) -> str:
    """What makes an item the same item. `pushed_at` is out on purpose: a push is not a release."""
    return digest({k: item.get(k) for k in ("full_name", "description", "license", "topics", "latest_release")})


def trace(item: dict[str, Any], stage: str, mode: str, outcome: str, **more: Any) -> None:
    item.setdefault("trace", []).append({"stage": stage, "mode": mode, "outcome": outcome, **more})


def repo_item(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": item_key(str(repo["full_name"])),
        "full_name": str(repo["full_name"]),
        "source_url": str(repo.get("html_url") or f"https://github.com/{repo['full_name']}"),
        "description": str(repo.get("description") or "")[:400],
        "license": (repo.get("license") or {}).get("spdx_id"),
        "stars": int(repo.get("stargazers_count") or 0),
        "topics": [str(t) for t in (repo.get("topics") or [])][:12],
        "pushed_at": repo.get("pushed_at"),
        "default_branch": repo.get("default_branch"),
    }


def validate_label(label: Any, item: dict[str, Any], settings: dict[str, Any], screen: Screen) -> list[str]:
    """The hybrid rule: a proposed label stands only if it passes every check on the item's own text."""
    if not isinstance(label, dict):
        return ["not_an_object"]
    failures: list[str] = []
    if label.get("category") not in settings["categories"]:
        failures.append("category_not_in_taxonomy")
    if label.get("determinism") not in ("deterministic", "model_assisted", "mixed"):
        failures.append("determinism_not_allowed")
    conf = label.get("confidence_milli")
    if isinstance(conf, bool) or not isinstance(conf, int) or not 0 <= conf <= 1000:
        failures.append("confidence_not_an_integer")
    elif conf < int(settings["min_confidence_milli"]):
        failures.append("confidence_below_threshold")
    summary = label.get("summary")
    if not isinstance(summary, str) or not 30 <= len(summary) <= 220:
        failures.append("summary_length")
    elif _URL.search(summary) or _EMAIL.search(summary):
        failures.append("summary_has_link_or_address")
    elif screen.visible_hit(summary):
        failures.append("summary_word_list")
    haystack = (item.get("description", "") + " " + " ".join(item.get("topics", []))).lower()
    evidence = label.get("evidence")
    if not isinstance(evidence, list) or not evidence or len(evidence) > 2:
        failures.append("evidence_count")
    elif not all(isinstance(q, str) and len(q.strip()) >= 4 and q.strip().lower() in haystack for q in evidence):
        failures.append("evidence_not_in_source")
    text = haystack + " " + item.get("full_name", "").lower()
    if label.get("category") == "skill_pack" and "skill" not in text:
        failures.append("skill_pack_without_skill_in_source")
    uses = label.get("use_cases")
    if not isinstance(uses, list) or len(uses) > 3 or not all(isinstance(u, str) and len(u) <= 60 for u in uses):
        failures.append("use_cases_shape")
    elif any(screen.visible_hit(u) or _URL.search(u) for u in uses):
        failures.append("use_cases_word_list")
    return failures


@dataclass
class RunContext:
    run_id: str
    spec: dict[str, Any]
    spec_version: int
    fabric: Any
    github: Any
    screen: Screen
    models: Any  # model id -> ChatModel
    heartbeat: Heartbeat | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    draws: dict[str, int] = field(default_factory=dict)
    prestep: Any = None

    @property
    def settings(self) -> dict[str, Any]:
        return self.spec["parameters"]["settings"]


class Stage(OmniNode):
    def __init__(self, ctx: RunContext, node_id: str, role: str, grid: Any, cell: Any, **kw: Any) -> None:
        self.ctx = ctx
        super().__init__(node_id=node_id, role=role, grid=grid, cell=cell, placement_scope="interior_branch", **kw)

    def done(self, output: dict[str, Any], tokens: int = 0, avoided: int = 0, ok: bool = True, **diag: Any) -> OmniNodeResult:
        return OmniNodeResult(ok=ok, output=output, node_id=self.node_id, role=self.role, placement_scope=self.placement_scope,
                              latency_ms=0.0, tokens_used=tokens, cold_steps_avoided=avoided, diagnostics=diag)


class GitHubSearch(Stage):
    """Deterministic: search, then keep only what passes the license check and the word screen."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx, s = self.ctx, self.ctx.settings
        since = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400 * int(s["pushed_within_days"])))
        seen: dict[str, dict[str, Any]] = {}
        for query in s["queries"]:
            for repo in ctx.github.search(f"{query} pushed:>={since}", int(s["per_query"])):
                seen.setdefault(str(repo.get("full_name")), repo)
        ranked = sorted(seen.values(), key=lambda r: (-int(r.get("stargazers_count") or 0), str(r.get("full_name"))))
        items = []
        for repo in ranked[: int(s["max_candidates"])]:
            item = repo_item(repo)
            trace(item, "search", "deterministic", "seen")
            blob = " ".join([item["full_name"], item["description"], *item["topics"]])
            if ctx.screen.blocked(blob):
                item["status"] = "dropped_word_list"
                item.pop("description")  # a name on the list stays off the record's text
                item["key"] = "withheld-" + digest(item["key"])[:10]
                item["full_name"] = item["source_url"] = "(withheld by the word list)"
                item["topics"] = []
                trace(item, "screen", "deterministic", "dropped_word_list")
            elif item["license"] not in s["allowed_licenses"]:
                item["status"] = "dropped_license"
                trace(item, "license", "deterministic", "dropped_license", license=item["license"])
            else:
                item["status"] = "candidate"
                trace(item, "license", "deterministic", "license_allowed", license=item["license"])
            items.append(item)
        return self.done({**envelope, "items": items, "queries_run": len(s["queries"])})


class ReuseCheck(Stage):
    """Reuse: already checked and unchanged answers with no model call, and costs no release lookup
    when nothing was pushed since."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx = self.ctx
        stored = {key: (value, version) for key, value, version in ctx.fabric.list(ITEMS_STORE)}
        avoided = 0
        for item in envelope["items"]:
            if item["status"] != "candidate":
                continue
            prev, version = stored.get(item["key"], (None, None))
            item["stored_version"] = version
            item["prev_value"] = prev
            if prev and prev.get("pushed_at") == item["pushed_at"]:
                item["latest_release"] = prev.get("latest_release")
                trace(item, "release", "reuse", "unchanged_since_last_push")
            elif ctx.github.spare():
                item["latest_release"] = ctx.github.latest_release(item["full_name"])
                trace(item, "release", "deterministic", "looked_up")
            else:
                item["status"] = "deferred_rate_limit"
                trace(item, "release", "deterministic", "deferred_rate_limit")
                continue
            item["content_digest"] = content_digest(item)
            if prev and prev.get("failed_digest") == item["content_digest"] and float(prev.get("retry_after") or 0) > time.time():
                item["status"] = "deferred_backoff"
                trace(item, "reuse", "deterministic", "deferred_backoff", failures=prev.get("failures"))
                continue
            same = bool(prev) and prev.get("content_digest") == item["content_digest"]
            verdict = ((prev or {}).get("check") or {}).get("verdict")
            if same and verdict == "approve":
                item["status"] = "reused"
                item["reused_from_version"] = version
                item["labels"] = prev.get("labels")
                avoided += 1
                trace(item, "reuse", "reuse", "answered_with_no_model_call", tokens=0, from_version=version)
            elif same and verdict == "reject" and prev.get("maker_model") != "deterministic_rule":  # a refused template still gets a model's try
                item["status"] = "reused_rejection"
                avoided += 1
                trace(item, "reuse", "reuse", "already_rejected_unchanged", tokens=0, from_version=version)
            elif same and verdict == "pending":
                item["status"] = "awaiting_check"
                item["labels"] = prev.get("labels")
                item["maker_model"] = prev.get("maker_model")
                trace(item, "reuse", "reuse", "labeled_awaiting_check", tokens=0, from_version=version)
            else:
                item["status"] = "needs_label"
                trace(item, "reuse", "deterministic", "new_or_changed")
        return self.done(envelope, avoided=avoided)


def parse_labels(answer: Any) -> dict[str, Any]:
    rows = answer.get("labels") if isinstance(answer, dict) else None
    return {str(r.get("key")): r for r in rows if isinstance(r, dict)} if isinstance(rows, list) else {}


class ModelLabel(Stage):
    """Model: the tuned mix chooses Muse Spark 1.3 or Muse Wonder 1.0 for each group. Every attempt is recorded, failures included."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx, s = self.ctx, self.ctx.settings
        params = ctx.spec["parameters"]
        pending = [i for i in envelope["items"] if i["status"] == "needs_label"]
        pre = ctx.prestep
        if pre is not None:
            pre.before_batch(pending, settings=s, screen=ctx.screen, github=ctx.github, validate=validate_label, trace=trace, digest=content_digest)
            pending = [i for i in pending if i["status"] == "needs_label"]
        chosen, extra = pending[: int(s["batch_size"])], pending[int(s["batch_size"]) :]
        for item in extra:
            item["status"] = "deferred_batch_size"
            trace(item, "label", "deterministic", "deferred_batch_size")
        tokens, size = 0, max(1, int(s["items_per_call"]))
        rng = random.Random(ctx.run_id)  # noqa: S311 - reproducible; only the recorded mix moves a draw
        stop = False
        for start in range(0, len(chosen), size):
            group = chosen[start : start + size]
            if stop:
                for item in group:
                    item["status"] = "deferred_budget"
                    trace(item, "label", "model", "deferred_budget")
                continue
            pick = tuning.pick(params["model"], "make", rng)
            variant = pick["variant"]
            ctx.draws[variant["id"]] = ctx.draws.get(variant["id"], 0) + 1
            meter = UsageMeter()
            plan = pre.before_call(group, s["categories"], params["skills"]["label"]["system"]) if pre is not None else prestep.default_plan(s["categories"])
            payload = {
                "categories": plan["categories"],
                "repositories": [{k: i.get(k) for k in ("key", "full_name", "description", "topics", "latest_release")} for i in group],
            }
            if plan["step_back"]:
                payload["step_back"] = plan["step_back"]
            system = " ".join([params["skills"]["label"]["system"], *[x for x in plan["skills"] if isinstance(x, str)]])
            attempt: dict[str, Any] = {"step": "label", "variant": variant["id"], "model": variant["model"], "share": pick["probability"],
                                       "tuner_version": pick["tuner_version"], "fine_tune": None, "item_keys": [i["key"] for i in group],
                                       "max_output_tokens": int(s.get("max_output_tokens", 8000)), "reasoning_effort": s.get("reasoning_effort", "low")}
            if plan["cut"]:
                attempt["categories_cut"] = plan["cut"]
            started = time.time()
            try:
                answer = ctx.models(variant["model"]).chat_json(system, _json(payload), meter=meter,
                                                                max_tokens=int(s.get("max_output_tokens", 8000)), temperature=0.0, seed=start)
                attempt["outcome"] = "answered" if "unparsed" not in answer else "unparsed"
            except BudgetExhausted as exc:
                answer, stop = {}, True
                attempt.update(outcome="refused_by_ceiling", error=str(exc)[:200])
            except ModelUnavailable as exc:
                answer = {}
                attempt.update(outcome="failed", error=str(exc)[:200])
            attempt.update(seconds=round(time.time() - started, 2), calls=len(meter.calls), input_tokens=meter.input_tokens,
                           output_tokens=meter.output_tokens, cost_usd=meter.cost_usd)
            ctx.attempts.append(attempt)
            tokens += meter.total_tokens
            labels, per_item = parse_labels(answer), meter.cost_usd / len(group)
            if pre is not None:
                pre.after_call(plan, group, labels, tokens=meter.total_tokens, variant=variant["id"], outcome=attempt["outcome"])
            per_item_seconds = attempt["seconds"] / len(group)
            for item in group:
                item.update(maker_variant=variant["id"], maker_model=variant["model"], cost_usd=round(per_item, 6), model_seconds=round(per_item_seconds, 2))
                if item["key"] in labels:
                    item["proposed"] = labels[item["key"]]
                    item["status"] = "proposed"
                    trace(item, "label", "model", "proposed", variant=variant["id"], model=variant["model"],
                          tokens=meter.total_tokens // len(group), cost_usd=round(per_item, 6))
                else:
                    item["status"] = "label_failed"
                    trace(item, "label", "model", attempt["outcome"] if attempt["outcome"] != "answered" else "no_label_returned",
                          variant=variant["id"], model=variant["model"], tokens=meter.total_tokens // len(group), cost_usd=round(per_item, 6))
        return self.done(envelope, tokens=tokens)


class HybridRuleCheck(Stage):
    """Hybrid: the model proposed, and this rule decides whether the proposal stands."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        for item in envelope["items"]:
            if item["status"] != "proposed":
                continue
            failures = validate_label(item["proposed"], item, self.ctx.settings, self.ctx.screen)
            if failures:
                item["status"] = "rule_rejected"
                item["rule_failures"] = failures
                trace(item, "rule", "hybrid", "rejected", failures=failures)
            else:
                item["status"] = "rule_accepted"
                item["labels"] = {k: item["proposed"].get(k) for k in ("category", "determinism", "use_cases", "summary", "evidence", "confidence_milli")}
                trace(item, "rule", "hybrid", "accepted")
        return self.done(envelope)


class StoreTaskObjects(Stage):
    """Store what the rule accepted as searchable Task Objects with source, license and metadata, awaiting the check."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx = self.ctx
        if ctx.heartbeat is not None and ctx.heartbeat.lost.is_set():
            return self.done(envelope, ok=False, error_code="lease_lost")
        for item in envelope["items"]:
            if item["status"] in ("rule_rejected", "label_failed"):
                self._remember_failure(item)
                continue
            if item["status"] != "rule_accepted":
                continue
            value = {
                "kind": "task_object", "node": ctx.spec["id"], "full_name": item["full_name"], "source_url": item["source_url"],
                "license": item["license"], "description": item["description"], "topics": item["topics"], "stars": item["stars"],
                "pushed_at": item["pushed_at"], "latest_release": item.get("latest_release"), "content_digest": item["content_digest"],
                "labels": item["labels"], "maker_model": item["maker_model"], "maker_variant": item["maker_variant"], "fine_tune": None,
                "made_in_run": ctx.run_id, "made_with_spec_version": ctx.spec_version, "check": {"verdict": "pending"},
            }
            version = ctx.fabric.put(ITEMS_STORE, item["key"], value, expected=item.get("stored_version"),
                                     tags=["kind:feed_item", "omninode:feed-maintenance", "status:pending_check", f"license:{item['license']}"])
            item["status"], item["stored_version"] = "awaiting_check", version
            trace(item, "store", "deterministic", "stored", record_version=version)
        return self.done(envelope)

    def _remember_failure(self, item: dict[str, Any]) -> None:
        """A paid label that failed waits before it is paid for again, and leaves the batch to others.
        A checked older version of the item stays as it was, apart from these fields."""
        prev = item.get("prev_value")
        failures = int((prev or {}).get("failures") or 0) + 1 if (prev or {}).get("failed_digest") == item["content_digest"] else 1
        base = prev or {"kind": "task_object", "node": self.ctx.spec["id"], "full_name": item["full_name"], "source_url": item["source_url"],
                        "license": item["license"], "labels": None, "check": {"verdict": "none"}}
        value = {**base, "failed_digest": item["content_digest"], "failures": failures, "failed_in_run": self.ctx.run_id,
                 "retry_after": time.time() + min(7 * 86400, 6 * 3600 * 2 ** (failures - 1))}
        version = self.ctx.fabric.put(ITEMS_STORE, item["key"], value, expected=item.get("stored_version"),
                                      tags=["kind:feed_item", "omninode:feed-maintenance", "status:label_failed" if not prev else "status:verified"])
        item["stored_version"] = version
        trace(item, "store", "deterministic", "failure_remembered", failures=failures)


class HandoffCheck(CheckerOmniNode):
    """The `@` in the maker's process: the combinator refuses equal keys, and the real check runs in the
    checker's own process with its own key. This node only says the work awaits it."""

    def __init__(self, *, checker_key_id: str, grid: Any, cell: Any) -> None:
        super().__init__(node_id="independent_check_handoff", checker_worker_key=checker_key_id, grid=grid, cell=cell)

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        return OmniNodeResult(ok=True, output={**envelope["maker_output"], "check_state": "awaiting_independent_check",
                                               "checker_key_id": self.checker_worker_key},
                              node_id=self.node_id, role=self.role, placement_scope=self.placement_scope, latency_ms=0.0)


def build_pipeline(ctx: RunContext, grid: Any, cell: Any, *, maker_key_id: str, checker_key_id: str) -> OmniNode:
    kw = {"grid": grid, "cell": cell}
    maker = (GitHubSearch(ctx, "github_search", "tool", **kw) >> ReuseCheck(ctx, "reuse_check", "router", **kw)
             >> ModelLabel(ctx, "model_label", "skill", **kw) >> HybridRuleCheck(ctx, "hybrid_rule_check", "checker_rule", **kw)
             >> StoreTaskObjects(ctx, "store_task_objects", "tool", **kw))
    node = maker @ HandoffCheck(checker_key_id=checker_key_id, grid=grid, cell=cell)
    node.maker_worker_key = maker_key_id
    return node


def mode_counts(items: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    status = [i["status"] for i in items]
    labelled = [a for a in attempts if a["step"] == "label"]
    return {
        "deterministic": {"seen": len(items), "dropped_license": status.count("dropped_license"), "dropped_word_list": status.count("dropped_word_list"),
                          "deferred": sum(s.startswith("deferred") for s in status),
                          "forced_function": sum(i.get("maker_model") == "deterministic_rule" and i.get("maker_variant", "") is None for i in items)},
        "reuse": {"answered_no_model": status.count("reused"), "already_rejected_unchanged": status.count("reused_rejection"),
                  "labeled_awaiting_check": sum(1 for i in items if i["status"] == "awaiting_check" and i.get("stored_version") and "maker_variant" not in i)},
        "model": {"attempts": len(labelled), "attempts_failed": sum(a["outcome"] != "answered" for a in labelled),
                  "items_sent": sum(len(a["item_keys"]) for a in labelled),
                  "by_model": {m: sum(len(a["item_keys"]) for a in labelled if a["model"] == m) for m in sorted({a["model"] for a in labelled})}},
        "hybrid": {"rule_accepted": sum(any(t.get("mode") == "hybrid" and t["outcome"] == "accepted" for t in i.get("trace", [])) for i in items),
                   "rule_rejected": status.count("rule_rejected")},
        "tokens": {"input": sum(a["input_tokens"] for a in attempts), "output": sum(a["output_tokens"] for a in attempts)},
        "cost_usd": round(sum(a["cost_usd"] for a in attempts), 6),
    }


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
