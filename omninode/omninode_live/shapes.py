"""One OmniNode, many shapes: a declarative spec compiled to the runtime's own algebra (>>, //, |, @).

A shape names its steps, says for each whether plain code or a model does it, and carries its goal, reward, invariants,
memory and sidecar. This module holds a fixed set of ops; a new shape is a JSON spec and adds no code. `validate` refuses a
spec that breaks an invariant, before anything runs. The sidecar sits inside the model step, never in the composition.
A field that starts with `_` lives only during the run and is never stored.
"""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx
import numpy as np
from eranos.model_client import BudgetExhausted, ModelUnavailable, UsageMeter
from eranos.pipeline import tuning
from src.universal_omninode_closure import CheckerOmniNode, OmniNode, OmniNodeResult, SidecarOmniNode

from omninode_live.core import ALLOWED_MODELS, digest

SCHEMA = "teleion.omninode.shape.v1"
ITEM_STORE_PREFIX = "omninode.shape_"
READ_STORES = frozenset({"eranos.solutions", "eranos.sources", "eranos.catalog", "omninode.feed_items", "omninode.shape_items"})
READ_HOSTS = frozenset({"shim.teleionlabs.com", "fabric.teleionlabs.com", "eranosforgood.org"})
REQUIRED_INVARIANTS = frozenset({"maker_is_not_checker", "spend_ceiling_before_model", "every_attempt_recorded", "third_party_text_is_data"})
MAX_BUDGET_USD = 8.0
OTHER_MODEL = {"muse-spark-1.3": "muse-wonder-1.0", "muse-wonder-1.0": "muse-spark-1.3"}
_LINK = re.compile(r"https?:|www\.|\b[\w-]+\.(?:com|org|net|io|ai|dev|gov)\b|[\w.+-]+@[\w-]+\.\w+", re.I)
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_NUMBER = re.compile(r"\d[\d,.]*\d|\d")


class ShapeError(ValueError):
    """The spec breaks a rule, so nothing runs."""


@dataclass
class ShapeContext:
    run_id: str
    spec: dict[str, Any]
    spec_version: int
    fabric: Any
    screen: Any
    models: Any  # model id -> ChatModel
    http: Any = None  # read-only client for allowed public hosts
    github: Any = None
    page: Any = None  # url -> (status, text, sha)
    shim: Any = None
    heartbeat: Any = None
    now: float = 0.0
    attempts: list[dict[str, Any]] = field(default_factory=list)
    draws: dict[str, int] = field(default_factory=dict)
    sidecars: dict[str, dict[str, Any]] = field(default_factory=dict)
    published: dict[str, Any] = field(default_factory=dict)


def trace(row: dict[str, Any], step: str, mode: str, outcome: str, **more: Any) -> None:
    row.setdefault("trace", []).append({"step": step, "mode": mode, "outcome": outcome, **more})


def path_get(value: Any, path: str) -> Any:
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def holds(row: dict[str, Any], test: dict[str, Any], screen: Any) -> bool:
    """One declarative test on a row. Unknown ops are refused by `validate`."""
    have, op, want = path_get(row, test["field"]), test["op"], test.get("value")
    if op == "eq":
        return have == want
    if op == "ne":
        return have != want
    if op == "in":
        return have in want
    if op == "notin":
        return have not in want
    if op == "gte":
        return isinstance(have, (int, float)) and have >= want
    if op == "lte":
        return isinstance(have, (int, float)) and have <= want
    if op == "truthy":
        return bool(have)
    if op == "falsy":
        return not have
    if op == "same_as":
        return have == path_get(row, want)
    if op == "differs_from":
        return have != path_get(row, want)
    if op == "word_list":
        return screen.blocked(json.dumps(have, ensure_ascii=False)) if have else False
    if op == "visible_words":
        return screen.visible_hit(json.dumps(have, ensure_ascii=False)) if have else False
    raise ShapeError(f"unknown test op {op}")


TEST_OPS = frozenset({"eq", "ne", "in", "notin", "gte", "lte", "truthy", "falsy", "same_as", "differs_from", "word_list", "visible_words"})


def normal_words(text: str) -> list[str]:
    return _TOKEN.findall(str(text or "").casefold())


def compare_text(needle: str, hay: str, window_chars: int = 900) -> dict[str, Any]:
    """Exact, then word coverage, then the part of `hay` nearest to `needle`: plain code, repeatable by a checker."""
    want, words = normal_words(needle), normal_words(hay)
    exact = bool(want) and " ".join(want) in " ".join(words)
    bag = set(want)
    coverage = round(len(bag & set(words)) / len(bag), 3) if bag else 0.0
    best_at, best, size = 0, -1, max(len(want), 1)
    hits = [1 if w in bag else 0 for w in words]
    running = sum(hits[:size])
    for at in range(max(len(words) - size + 1, 1)):
        if running > best:
            best, best_at = running, at
        if at + size < len(words):
            running += hits[at + size] - hits[at]
    window = " ".join(words[best_at : best_at + size + 40])[:window_chars]
    numbers = set(_NUMBER.findall(str(needle or "")))
    return {"exact": exact, "coverage": coverage, "same_numbers": numbers <= set(_NUMBER.findall(str(hay or ""))), "window": window,
            "needle_words": len(want)}


class RowSidecar(SidecarOmniNode):
    """The runtime's rank-1 prior and conformal interval, on features the spec names from the row itself. The stock
    features read only an envelope's key names, so unlike content looks alike: tested, and that is why this exists."""

    def __init__(self, conf: dict[str, Any], grid: Any, cell: Any, state: dict[str, Any] | None) -> None:
        settings = {**cell, "sidecar_feature_dim": len(conf["features"]) + 1,
                    "sidecar_min_calibration_samples": int(conf.get("min_samples", 6)),
                    "sidecar_conformal_alpha": float(conf.get("alpha", 0.1)), "sidecar_bypass_max_width": float(conf.get("max_width", 0.28))}
        super().__init__(node_id="row_sidecar", grid=grid, cell=settings)
        self.features = list(conf["features"])
        # The grid rounds the size to its own steps; this sidecar's size is its feature list.
        self.dim = len(self.features) + 1
        ridge = float(self.grid.protocol_constants["whitening_ridge_eps"])
        self._precision_inv = (1.0 / ridge) * np.eye(self.dim, dtype=np.float64)
        self._xty = np.zeros(self.dim, dtype=np.float64)
        self._bilinear = np.eye(self.dim, dtype=np.float64)
        self.skips, self.observed, self.audits = 0, 0, []
        if state and len(state.get("xty") or []) == self.dim:
            self._precision_inv = np.array(state["precision_inv"], dtype=np.float64)
            self._xty = np.array(state["xty"], dtype=np.float64)
            self._residuals = [float(x) for x in state["residuals"]]
            self._update_count = int(state["updates"])

    def _featurize(self, envelope: Any) -> tuple[np.ndarray, np.ndarray]:
        x = np.zeros(self.dim, dtype=np.float64)
        x[0] = 1.0
        for at, name in enumerate(self.features, start=1):
            value = path_get(envelope, name)
            x[at] = float(value) if isinstance(value, (bool, int, float)) else 0.0
        return x, x.copy()

    def state(self) -> dict[str, Any]:
        return {"features": self.features, "precision_inv": self._precision_inv.round(8).tolist(), "xty": self._xty.round(8).tolist(),
                "residuals": [round(r, 5) for r in self._residuals][-500:], "updates": self._update_count}


class Step(OmniNode):
    mode = "deterministic"

    def __init__(self, ctx: ShapeContext, conf: dict[str, Any], grid: Any, cell: Any, **kw: Any) -> None:
        self.ctx, self.conf, self.args = ctx, conf, conf.get("args") or {}
        super().__init__(node_id=conf["id"], role=conf.get("role", "tool"), grid=grid, cell=cell, placement_scope="interior_branch", **kw)

    def done(self, output: dict[str, Any], *, ok: bool = True, tokens: int = 0, avoided: int = 0, **diag: Any) -> OmniNodeResult:
        return OmniNodeResult(ok=ok, output=output, node_id=self.node_id, role=self.role, placement_scope=self.placement_scope,
                              latency_ms=0.0, tokens_used=tokens, cold_steps_avoided=avoided, diagnostics=diag)

    def active(self, envelope: dict[str, Any]) -> list[dict[str, Any]]:
        wanted = self.args.get("only_status")
        rows = envelope.get("rows") or []
        return [r for r in rows if r.get("status") in wanted] if wanted else [r for r in rows if r.get("status") == "open"]


class RowsFromRecords(Step):
    """A Fabric store becomes rows. `explode` walks lists inside each record; `$key`, `$0.x`, `$1.x` name the levels."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        a, rows, seen = self.args, [], {}
        for key, value, version in self.ctx.fabric.list(a["store"], prefix=a.get("prefix", ""), limit=int(a.get("limit", 200))):
            if not all(holds(value, t, self.ctx.screen) for t in a.get("where") or []):
                continue
            levels: list[list[Any]] = [[value]]
            for path in a.get("explode") or []:
                levels = [[*chain, nested] for chain in levels for nested in (path_get(chain[-1], path) or [])]
            for chain in levels:
                row: dict[str, Any] = {"status": "open", "source_record": key, "source_version": version}
                for name, ref in a["fields"].items():
                    if ref == "$key":
                        row[name] = key
                    else:
                        depth, _, rest = ref[1:].partition(".")
                        row[name] = path_get(chain[int(depth)], rest) if rest else chain[int(depth)]
                base = "--".join(str(row[k]) for k in a["key_fields"])
                seen[base] = seen.get(base, 0) + 1
                row["key"] = base if seen[base] == 1 else f"{base}--{seen[base]}"  # two rows from one place stay two rows
                trace(row, self.node_id, "deterministic", "read")
                rows.append(row)
        return self.done({**envelope, "rows": rows}, ok=bool(rows) or not a.get("must_find"))


class RowsFromHttp(Step):
    """Rows from a read-only public address on our own hosts, in the `cols` and `rows` table form."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        a, rows, failed = self.args, {}, 0
        since = time.strftime("%Y-%m-%d", time.gmtime(self.ctx.now - 86400 * int(a.get("since_days", 30))))
        for url in a["urls"]:
            try:
                answer = self.ctx.http.get(url.replace("{since}", since))
                body = answer.json() if answer.status_code == 200 else {}
            except (httpx.HTTPError, ValueError):
                body = {}
            if not body.get("rows"):
                failed += 1
                continue
            for raw in body["rows"]:
                row = dict(zip(body["cols"], raw, strict=False))
                row.update(status="open", key=str(row[a["key_field"]]).lower().replace("/", "--"))
                trace(row, self.node_id, "deterministic", "read", address=url.split("?")[0])
                rows.setdefault(row["key"], row)
        return self.done({**envelope, "rows": list(rows.values())}, ok=not failed, failed_addresses=failed)


class JoinRecord(Step):
    """Adds one record's fields to each row, without reading a record twice."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        a, cache = self.args, {}
        for row in self.active(envelope):
            key = str(row.get(a["key_field"]))
            if key not in cache:
                found = self.ctx.fabric.get(a["store"], key)
                cache[key] = found[0] if found else None
            value = cache[key]
            trace(row, self.node_id, "deterministic", "joined" if value else "no_record")
            for name, source in a["fields"].items():
                row[name] = path_get(value, source) if value else None
        return self.done(envelope)


class GithubRepo(Step):
    """The repository as GitHub says now. A failed call says nothing about the item, so the row waits."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        github, name = self.ctx.github, self.args["repo_field"]
        for row in self.active(envelope):
            if not github.spare():
                row["status"] = "deferred_rate_limit"
                trace(row, self.node_id, "deterministic", "deferred_rate_limit")
                continue
            state, now = github.repo(str(row[name]))
            row["github_state"] = state
            if state == "unreachable":
                row["status"] = "deferred_unreachable"
            elif now:
                prefix = self.args.get("prefix", "")
                row.update({f"{prefix}{k}": now.get(k) for k in ("description", "license", "stars", "topics", "pushed_at", "source_url")})
            trace(row, self.node_id, "deterministic", state)
        return self.done(envelope)


class FetchPage(Step):
    """A page through the same checked fetcher Eranos research uses: https, public addresses only, one read per address."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        a, cache = self.args, {}
        for row in self.active(envelope):
            url = str(row.get(a["url_field"]) or "")
            if url and url not in cache:
                cache[url] = self.ctx.page(url)
            status, text, sha = cache.get(url, (0, "", None))
            row.update(page_status=status, page_sha=sha, _page_text=text)
            trace(row, self.node_id, "deterministic", "read" if status == 200 else "unreachable", status=status)
        return self.done(envelope, pages=len(cache))


class TextCompare(Step):
    """Is this text in that text? Exact words, coverage, numbers, and the nearest passage for anyone reading further."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        a = self.args
        for row in self.active(envelope):
            found = compare_text(str(row.get(a["needle"]) or ""), str(row.get(a["hay"]) or ""))
            out = a["out"]
            row.update({f"{out}_exact": found["exact"], f"{out}_coverage": found["coverage"], f"{out}_same_numbers": found["same_numbers"],
                        f"_{out}_window": found["window"]})
            trace(row, self.node_id, "deterministic", "exact" if found["exact"] else "not_exact", coverage=found["coverage"])
        return self.done(envelope)


class Sort(Step):
    """Keeps the top `keep` rows by a field; the others say why they stopped."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        a, live = self.args, self.active(envelope)
        live.sort(key=lambda r: (-float(path_get(r, a["by"]) or 0), str(r["key"])))
        for row in live[int(a["keep"]) :]:
            row["status"] = "over_limit"
            trace(row, self.node_id, "deterministic", "over_limit")
        return self.done(envelope)


class Classify(Step):
    """A plain rule table: the first row of `rules` that holds sets the fields. This is where plain code decides without a model."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        for row in self.active(envelope):
            for rule in self.args["rules"]:
                if all(holds(row, t, self.ctx.screen) for t in rule.get("when") or []):
                    row.update(rule["set"])
                    trace(row, self.node_id, "deterministic", str(rule["set"].get("status") or rule["set"].get("finding") or "set"), rule=rule.get("name"))
                    break
        return self.done(envelope)


class MemoryReuse(Step):
    """The node's memory: a row whose inputs match an approved earlier answer takes that answer with no model call."""

    mode = "reuse"

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        a, ctx = self.args, self.ctx
        stored = {k: (v, ver) for k, v, ver in ctx.fabric.list(ctx.spec["memory"]["store"], prefix=f"{ctx.spec['id']}.", limit=int(a.get("limit", 500)))}
        avoided = 0
        for row in self.active(envelope):
            row["input_digest"] = digest({**{k: row.get(k) for k in a["digest_fields"]}, "rules_version": a.get("rules_version")})  # new rules, new answers
            prev, version = stored.get(item_key(ctx.spec, row), (None, None))
            row["stored_version"] = version
            verdict = ((prev or {}).get("check") or {}).get("verdict")
            if prev and prev.get("input_digest") == row["input_digest"] and verdict == "approve":
                row.update(status="reused", reused_from_version=version, answer=prev.get("answer"), finding=prev.get("finding"))
                avoided += 1
                trace(row, self.node_id, "reuse", "answered_with_no_model_call", tokens=0, from_version=version)
            else:
                trace(row, self.node_id, "deterministic", "new_or_changed")
        return self.done(envelope, avoided=avoided)


class ModelStep(Step):
    """A Muse model answers for rows plain code left open. Every attempt is recorded, failures included. The sidecar,
    if the spec has one, lives here: it predicts each answer and may spare a call once its interval earns it."""

    mode = "model"

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx, a = self.ctx, self.args
        model_conf = ctx.spec["parameters"]["model"]
        rows, size = self.active(envelope), max(1, int(a.get("group_size", 4)))
        rng = random.Random(f"{ctx.run_id}:{self.node_id}")  # noqa: S311 - reproducible; only the recorded mix moves a draw
        sidecar: RowSidecar | None = self.sidecar if isinstance(self.sidecar, RowSidecar) else None
        conf = ctx.spec.get("sidecar") or {}
        tokens, stop, queue = 0, False, list(rows)
        while queue:
            group: list[dict[str, Any]] = []
            while queue and len(group) < size:
                row = queue.pop(0)
                if sidecar is not None and self._spared(row, sidecar, conf):
                    continue
                group.append(row)
            if not group:
                break
            if stop:
                for row in group:
                    row["status"] = "deferred_budget"
                    trace(row, self.node_id, "model", "deferred_budget")
                continue
            for model_id, part in self._by_model(group, model_conf, rng):
                answers, cost, used, outcome, seconds, variant = self._call(model_id, part, model_conf, rng)
                stop = stop or outcome == "refused_by_ceiling"
                tokens += used
                who = "checker" if a.get("other_than_field") else "maker"  # a check never overwrites who made the row
                for row in part:
                    answer = answers.get(row["key"])
                    row.update({f"{who}_model": model_id, f"{who}_variant": variant, f"{who}_cost_usd": round(cost / len(part), 6), f"{who}_seconds": round(seconds / len(part), 2)})
                    if answer is None:
                        row["status"] = a.get("failed_status", "model_failed")
                        trace(row, self.node_id, "model", outcome if outcome != "answered" else "no_answer_returned", model=model_id)
                        continue
                    row["_proposed"] = {k: answer.get(k) for k in a["out_fields"]}
                    row["status"] = a.get("next_status", "proposed")
                    trace(row, self.node_id, "model", "proposed", model=model_id, variant=variant, tokens=used // len(part))
                    if sidecar is not None:
                        self._learn(row, sidecar, conf)
        return self.done(envelope, tokens=tokens)

    def _spared(self, row: dict[str, Any], sidecar: RowSidecar, conf: dict[str, Any]) -> bool:
        cert = sidecar.predict_score(row)
        row["sidecar_prediction"] = {"score": round(cert["predicted_score"], 4), "width": round(cert["interval_width"], 4),
                                     "regime": cert["operator_regime"], "samples": cert["calibration_samples"]}
        if not cert["deterministic_bypass"] or cert["predicted_score"] < float(conf.get("skip_above", 0.9)):
            return False
        sidecar.skips += 1
        if sidecar.skips % max(1, int(conf.get("audit_every", 4))) == 0:  # this one goes to the model anyway, so the skip gets tested
            row["sidecar_would_skip"] = True
            return False
        row["_proposed"] = dict(conf["answer_when_skipped"])
        row["status"], row["maker_model"], row["maker_variant"] = self.args.get("next_status", "proposed"), "sidecar", None
        trace(row, self.node_id, "sidecar", "spared_a_model_call", score=row["sidecar_prediction"]["score"], width=row["sidecar_prediction"]["width"])
        return True

    def _learn(self, row: dict[str, Any], sidecar: RowSidecar, conf: dict[str, Any]) -> None:
        target = 1.0 if path_get(row["_proposed"], conf["target_field"]) == conf["target_value"] else 0.0
        sidecar.observe_rank1(row, target)
        sidecar.observed += 1
        if row.get("sidecar_would_skip"):
            sidecar.audits.append({"key": row["key"], "agreed": bool(target)})

    def _by_model(self, group: list[dict[str, Any]], model_conf: dict[str, Any], rng: random.Random) -> list[tuple[str, list[dict[str, Any]]]]:
        other = self.args.get("other_than_field")
        if not other:  # a maker draws from the tuned mix, once for a group
            pick = tuning.pick(model_conf, "make", rng)
            self._pick = pick
            return [(pick["variant"]["model"], group)]
        parts: dict[str, list[dict[str, Any]]] = {}  # a checker never uses the model that made the row
        for row in group:
            parts.setdefault(OTHER_MODEL.get(str(row.get(other)), self.args.get("default_model", "muse-spark-1.3")), []).append(row)
        self._pick = None
        return list(parts.items())

    def _call(self, model_id: str, part: list[dict[str, Any]], model_conf: dict[str, Any], rng: random.Random) -> tuple[dict[str, dict[str, Any]], float, int, str, float, str | None]:
        ctx, a, meter = self.ctx, self.args, UsageMeter()
        pick = self._pick
        variant = pick["variant"]["id"] if pick else None
        if variant:
            ctx.draws[variant] = ctx.draws.get(variant, 0) + 1
        attempt: dict[str, Any] = {"step": self.node_id, "model": model_id, "variant": variant, "share": pick["probability"] if pick else None,
                                   "tuner_version": pick["tuner_version"] if pick else None, "fine_tune": None, "item_keys": [r["key"] for r in part],
                                   "max_output_tokens": int(a.get("max_output_tokens", 8000))}
        payload = {"rows": [{"key": r["key"], **{k.lstrip("_"): r.get(k) for k in a["input_fields"]}} for r in part]}
        started, answer = time.time(), {}
        try:
            answer = ctx.models(model_id).chat_json(a["system"], json.dumps(payload, ensure_ascii=False), meter=meter,
                                                    max_tokens=int(a.get("max_output_tokens", 8000)), temperature=0.0, seed=len(ctx.attempts))
            attempt["outcome"] = "answered" if "unparsed" not in answer else "unparsed"
        except BudgetExhausted as exc:
            attempt.update(outcome="refused_by_ceiling", error=str(exc)[:200])
        except ModelUnavailable as exc:
            attempt.update(outcome="failed", error=str(exc)[:200])
        seconds = round(time.time() - started, 2)
        attempt.update(seconds=seconds, calls=len(meter.calls), input_tokens=meter.input_tokens, output_tokens=meter.output_tokens, cost_usd=meter.cost_usd)
        ctx.attempts.append(attempt)
        rows = answer.get("answers") if isinstance(answer, dict) else None
        found = {str(r.get("key")): r for r in rows if isinstance(r, dict)} if isinstance(rows, list) else {}
        return found, meter.cost_usd, meter.total_tokens, attempt["outcome"], seconds, variant


class RuleValidate(Step):
    """Hybrid: a model proposed, and this table decides whether the proposal stands, judged against the row's own text."""

    mode = "hybrid"

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        for row in self.active(envelope):
            proposed = row.get("_proposed") or {}
            failures = [f for rule in self.args["rules"] for f in self._failures(rule, proposed, row)]
            if failures:
                row.update(status=self.args.get("failed_status", "rule_rejected"), rule_failures=failures)
                trace(row, self.node_id, "hybrid", "rejected", failures=failures)
            else:
                row.update({"status": self.args.get("next_status", "rule_accepted"), self.args.get("answer_field", "answer"): proposed})
                trace(row, self.node_id, "hybrid", "accepted")
        return self.done(envelope)

    def _failures(self, rule: dict[str, Any], proposed: dict[str, Any], row: dict[str, Any]) -> list[str]:
        name, value, out = rule["field"], proposed.get(rule["field"]), []
        if "enum" in rule and value not in rule["enum"]:
            out.append(f"{name}_not_allowed")
        if "when" in rule and not all(holds(proposed, t, self.ctx.screen) for t in rule["when"]):
            return out
        if not isinstance(value, str):
            return [*out, f"{name}_not_text"] if {"min_len", "max_len", "quoted_from"} & set(rule) else out
        if not int(rule.get("min_len", 0)) <= len(value) <= int(rule.get("max_len", 100000)):
            out.append(f"{name}_length")
        if rule.get("no_links") and _LINK.search(value):
            out.append(f"{name}_has_link_or_address")
        if rule.get("word_list") and self.ctx.screen.visible_hit(value):
            out.append(f"{name}_word_list")
        if "quoted_from" in rule:
            haystack = " ".join(normal_words(" ".join(json.dumps(row.get(f), ensure_ascii=False) for f in rule["quoted_from"])))
            words = " ".join(normal_words(value))
            if len(words) < 4 or words not in haystack:
                out.append(f"{name}_not_in_source")
        return out


def item_key(spec: dict[str, Any], row: dict[str, Any]) -> str:
    return f"{spec['id']}." + re.sub(r"[^a-zA-Z0-9._-]+", "-", str(row["key"]))[:180]


def stored_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if not k.startswith("_") and k not in ("trace", "stored_version")}


class StoreItems(Step):
    """What the step table accepted is stored as Task Objects in the node's memory, awaiting the independent check."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx = self.ctx
        if ctx.heartbeat is not None and ctx.heartbeat.lost.is_set():
            return self.done(envelope, ok=False, error_code="lease_lost")
        store = ctx.spec["memory"]["store"]
        for row in self.active(envelope):
            value = {"kind": "task_object", "node": ctx.spec["id"], **stored_fields(row), "status": "awaiting_check", "made_in_run": ctx.run_id,
                     "made_with_spec_version": ctx.spec_version, "check": {"verdict": "pending"}}
            if row.get("stored_version") is None:  # a shape with no memory step still updates its own item on the next run
                found = ctx.fabric.get(store, item_key(ctx.spec, row))
                row["stored_version"] = found[1] if found else None
            version = ctx.fabric.put(store, item_key(ctx.spec, row), value, expected=row.get("stored_version"),
                                     tags=["kind:shape_item", f"omninode:{ctx.spec['id']}", "status:pending_check"])
            row.update(status="awaiting_check", stored_version=version)
            trace(row, self.node_id, "deterministic", "stored", record_version=version)
        return self.done(envelope)


class LoadRunRows(Step):
    """The checker's first step: the maker's stored items for this run, read again from the store, not from the maker's report."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx, rows = self.ctx, []
        for made in envelope["maker_output"]["items"]:
            if made["status"] != "awaiting_check":
                continue
            found = ctx.fabric.get(ctx.spec["memory"]["store"], item_key(ctx.spec, made))
            if found:
                value, version = found
                row = {**value, "key": made["key"], "status": "open", "stored_version": version}
                trace(row, self.node_id, "deterministic", "read")
                rows.append(row)
        return self.done({**envelope, "rows": rows})


class StoreVerdicts(Step):
    """The check's result goes on each item; `verdict` left unset by the steps before stays pending."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx = self.ctx
        maker = str(envelope.get("maker_worker_key"))
        for row in envelope.get("rows") or []:
            proposed = row.pop("_proposed", None) or {}
            verdict = "pending" if row.get("status") == "rule_rejected" else proposed.get("verdict") or row.get("verdict") or "pending"
            row["verdict"] = verdict
            stamp = {"verdict": verdict, "reason": str(proposed.get("reason") or row.get("check_reason") or "")[:240], "checker_key_id": ctx.fabric.key_id,
                     "maker_key_id": maker, "audit_model": row.get("checker_model") if proposed else None, "run_id": ctx.run_id, "at": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())}
            if ctx.screen.visible_hit(stamp["reason"]) or _LINK.search(stamp["reason"]):
                stamp["reason"] = "(the reason was withheld by the word list)"
            row["check"] = stamp
            value = {k: v for k, v in stored_fields(row).items() if k not in ("verdict", "check_reason")}
            value["status"] = {"approve": "checked", "reject": "rejected"}.get(verdict, "awaiting_check")
            version = ctx.fabric.put(ctx.spec["memory"]["store"], item_key(ctx.spec, row), value, expected=row["stored_version"],
                                     tags=["kind:shape_item", f"omninode:{ctx.spec['id']}", f"status:{value['status']}"])
            row["stored_version"] = version
            trace(row, self.node_id, "deterministic", verdict, record_version=version)
        return self.done(envelope)


class PublishObjects(Step):
    """Approved rows go to the shared public catalog as Task Objects, in our words: a name and a line only. Read back, not assumed."""

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        ctx, a, objects = self.ctx, self.args, {}
        rows_now = list(envelope.get("rows") or [])
        here = {r["key"] for r in rows_now}
        for _key, value, version in ctx.fabric.list(ctx.spec["memory"]["store"], prefix=f"{ctx.spec['id']}.", limit=500):  # approved earlier, not yet public
            if value.get("key") not in here and (value.get("check") or {}).get("verdict") == "approve" and not value.get("public_object"):
                rows_now.append({**value, "verdict": "approve", "stored_version": version})
        for row in rows_now:
            if row.get("verdict") != "approve" or row.get("public_object"):
                continue
            answer = row.get("answer") or {}
            fields = {**row, **answer}
            summary = str(a["summary"]).format_map(_Blank(fields))
            hints = [str(fields.get(h)) for h in a.get("hints") or [] if fields.get(h)]
            if ctx.screen.visible_hit(summary) or ctx.screen.visible_hit(" ".join(hints)):
                trace(row, self.node_id, "deterministic", "kept_private_by_word_list")
                continue
            key = (a["prefix"] + re.sub(r"[^a-z0-9_-]+", "_", str(row["key"]).lower()))[:120]
            objects[key] = {"summary": summary[:1500], "category": a.get("category", "shape_item"), "search_hints": [*hints, "omninode"],
                            "payload": {**{f: fields.get(f) for f in a.get("payload") or []}, "made_by": {"model": row.get("maker_model"), "run": row.get("made_in_run")},
                                        "record": f"fabric store {ctx.spec['memory']['store']}, key {item_key(ctx.spec, row)}"},
                            "_row": row}
        if objects and ctx.shim is not None:
            rows = {k: v.pop("_row") for k, v in objects.items()}
            keys, size, ctx.published = sorted(objects), max(1, int(a.get("batch", 10))), {"sent": 0, "readable": [], "redirected": [], "ok": True, "status": []}
            for start in range(0, len(keys), size):  # the shim stores at most 12 from one submit and says 200
                part = {k: objects[k] for k in keys[start : start + size]}
                got = ctx.shim.publish(part, f"OmniNode shape {ctx.spec['id']} run {ctx.run_id}: {len(part)} checked items", f"shape:{ctx.spec['id']}:{ctx.run_id}:{start}:{len(part)}")
                ctx.published["sent"] += len(part)
                ctx.published["readable"] += got.get("readable") or []
                ctx.published["redirected"] += got.get("redirected") or []
                ctx.published["ok"] = ctx.published["ok"] and bool(got.get("ok"))
                ctx.published["status"].append(got.get("status"))
            for key in ctx.published.get("readable") or []:
                row = rows[key]
                row["public_object"] = key
                value = {**stored_fields(row)}
                value["status"] = "checked"
                value.pop("verdict", None)
                row["stored_version"] = ctx.fabric.put(ctx.spec["memory"]["store"], item_key(ctx.spec, row), value, expected=row["stored_version"],
                                                       tags=["kind:shape_item", f"omninode:{ctx.spec['id']}", "status:checked"])
        return self.done(envelope)


class _Blank(dict):
    def __missing__(self, key: str) -> str:
        return ""


OPS: dict[str, type[Step]] = {
    "rows_from_records": RowsFromRecords, "rows_from_http": RowsFromHttp, "join_record": JoinRecord, "github_repo": GithubRepo,
    "fetch_page": FetchPage, "text_compare": TextCompare, "sort": Sort, "classify": Classify, "memory_reuse": MemoryReuse,
    "model": ModelStep, "rule_validate": RuleValidate, "store_items": StoreItems, "load_run_rows": LoadRunRows,
    "store_verdicts": StoreVerdicts, "publish_objects": PublishObjects,
}
MODE_OF_OP = {"model": "model", "rule_validate": "hybrid", "memory_reuse": "reuse"}
_TOKENS = re.compile(r"\s*(>>|//|\||@|\(|\)|[a-z][a-z0-9_]*)")


def tokenize(text: str) -> list[str]:
    out, at = [], 0
    while at < len(text.rstrip()):
        match = _TOKENS.match(text, at)
        if not match:
            raise ShapeError(f"composition: cannot read {text[at:at + 20]!r}")
        out.append(match.group(1))
        at = match.end()
    return out


def parse(text: str) -> Any:
    """A tree of ids: `check` binds last with @, then >>, then |, then // tightest."""
    tokens, at = tokenize(text), [0]

    def peek() -> str | None:
        return tokens[at[0]] if at[0] < len(tokens) else None

    def take() -> str:
        at[0] += 1
        return tokens[at[0] - 1]

    def atom() -> Any:
        tok = take() if peek() else None
        if tok == "(":
            inner = level(0)
            if peek() != ")":
                raise ShapeError("composition: a bracket is left open")
            take()
            return inner
        if tok is None or tok in (">>", "//", "|", "@", ")"):
            raise ShapeError(f"composition: expected a step, found {tok}")
        return tok

    order = ("@", ">>", "|", "//")

    def level(n: int) -> Any:
        if n == len(order):
            return atom()
        left = level(n + 1)
        while peek() == order[n]:
            take()
            left = (order[n], left, level(n + 1))
        return left

    tree = level(0)
    if peek() is not None:
        raise ShapeError(f"composition: unexpected {peek()}")
    return tree


def leaves(tree: Any) -> list[str]:
    return [tree] if isinstance(tree, str) else [*leaves(tree[1]), *leaves(tree[2])]


def _validate_steps(block: dict[str, Any], where: str, errors: list[str]) -> list[dict[str, Any]]:
    steps = block.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append(f"{where}: no steps")
        return []
    ids = [s.get("id") for s in steps]
    if len(set(ids)) != len(ids):
        errors.append(f"{where}: two steps share an id")
    for s in steps:
        if s.get("op") not in OPS:
            errors.append(f"{where}: unknown op {s.get('op')}")
        declared, expected = s.get("mode"), MODE_OF_OP.get(s.get("op"), "code")
        if declared != expected:
            errors.append(f"{where}: step {s.get('id')} says mode {declared}, its op is {expected}")
    try:
        names = leaves(parse(str(block.get("composition") or "")))
    except ShapeError as exc:
        errors.append(f"{where}: {exc}")
        return steps
    if set(names) - {"check"} != set(ids):
        errors.append(f"{where}: composition and steps differ: {sorted(set(names) ^ set(ids))}")
    return steps


def validate(spec: dict[str, Any]) -> list[str]:
    """Every reason this spec may not run. A spec can change everything except these."""
    errors: list[str] = []
    if spec.get("schema") != SCHEMA:
        errors.append("schema")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,60}", str(spec.get("id") or "")):
        errors.append("id")
    for name in ("goal", "reward", "invariants"):
        if not spec.get(name):
            errors.append(f"needs a {name}")
    missing = REQUIRED_INVARIANTS - set(spec.get("invariants") or [])
    if missing:
        errors.append(f"invariants missing: {sorted(missing)}")
    store = str((spec.get("memory") or {}).get("store") or "")
    if not store.startswith(ITEM_STORE_PREFIX):
        errors.append(f"memory store must start with {ITEM_STORE_PREFIX}")
    budget = spec.get("budget_usd_per_day")
    if not isinstance(budget, (int, float)) or isinstance(budget, bool) or not 0 <= budget <= MAX_BUDGET_USD:
        errors.append(f"budget must be 0 to {MAX_BUDGET_USD}")
    model = (spec.get("parameters") or {}).get("model") or {}
    for v in model.get("variants") or []:
        if v.get("model") not in ALLOWED_MODELS:
            errors.append(f"model {v.get('model')} is not allowed")
        if v.get("fine_tune"):
            errors.append("a fine-tune needs its own held-out result first")
    steps = _validate_steps(spec, "maker", errors)
    check = spec.get("check")
    if not isinstance(check, dict):
        errors.append("every shape has an independent check")
        check_steps: list[dict[str, Any]] = []
    else:
        check_steps = _validate_steps(check, "check", errors)
        if "check" in {s.get("id") for s in steps}:
            errors.append("`check` is reserved")
        if "@ check" not in str(spec.get("composition")):
            errors.append("the composition must end @ check")
        if not any(s.get("op") == "store_verdicts" for s in check_steps):
            errors.append("the check must store its verdicts")
    all_steps = [*steps, *check_steps]
    used_model = any(s.get("op") == "model" for s in all_steps)
    if used_model and not model.get("variants"):
        errors.append("a model step needs model variants")
    if used_model and not budget:
        errors.append("a model step needs a budget")
    for s in all_steps:
        args = s.get("args") or {}
        for url in args.get("urls") or []:
            if urlsplit(url).hostname not in READ_HOSTS or urlsplit(url).scheme != "https":
                errors.append(f"address {url} is not one of ours")
        if s.get("op") == "join_record" and any(str(v).startswith("$") for v in (args.get("fields") or {}).values()):
            errors.append(f"step {s.get('id')}: join_record fields are plain paths, without $")
        if s.get("op") in ("rows_from_records", "join_record") and args.get("store") not in READ_STORES:
            errors.append(f"step {s.get('id')}: store {args.get('store')} is not one a shape may read")  # run records are public, so what a shape reads is too
        for rule in args.get("rules") or []:
            for test in rule.get("when") or []:
                if test.get("op") not in TEST_OPS:
                    errors.append(f"step {s.get('id')}: unknown test {test.get('op')}")
    sidecar = spec.get("sidecar")
    if sidecar:
        if str(sidecar.get("inside")) not in {s["id"] for s in steps if s.get("op") == "model"}:
            errors.append("the sidecar sits inside one of this shape's model steps")
        if "sidecar" in leaves_or_empty(spec):
            errors.append("the sidecar is not a node")
        for need in ("features", "target_field", "target_value", "answer_when_skipped"):
            if not sidecar.get(need):
                errors.append(f"sidecar needs {need}")
    return errors


def dry_read(spec: dict[str, Any], fabric: Any, screen: Any, grid: Any, cell: Any) -> list[str]:
    """Runs a spec's first step on real records, writing nothing: does each declared field hold something, and are keys short names?"""
    first = spec["steps"][0]
    if first["op"] != "rows_from_records":
        return []
    ctx = ShapeContext(run_id="dry", spec=spec, spec_version=0, fabric=fabric, screen=screen, models=None)
    rows = OPS[first["op"]](ctx, first, grid, cell).execute({}).output.get("rows") or []
    if not rows:
        return ["the first step found no rows in the real store"]
    errors = [f"key is not a short name: {rows[0]['key'][:60]}"] if any(len(r["key"]) > 160 for r in rows) else []
    fields = first["args"]["fields"]
    empty = [name for name in fields if all(r.get(name) is None for r in rows)]
    if empty:
        errors.append(f"these fields are empty in all {len(rows)} real rows: {empty}")
    return errors


def leaves_or_empty(spec: dict[str, Any]) -> list[str]:
    try:
        return leaves(parse(str(spec.get("composition") or "")))
    except ShapeError:
        return []


class HandoffCheck(CheckerOmniNode):
    """The `@`: the combinator refuses equal keys; the real check runs in another process with another key."""

    def __init__(self, *, checker_key_id: str, grid: Any, cell: Any) -> None:
        super().__init__(node_id="independent_check_handoff", checker_worker_key=checker_key_id, grid=grid, cell=cell)

    def _execute_core(self, envelope: dict[str, Any], _context: dict[str, Any]) -> OmniNodeResult:
        return OmniNodeResult(ok=True, output={**envelope["maker_output"], "check_state": "awaiting_independent_check", "checker_key_id": self.checker_worker_key},
                              node_id=self.node_id, role=self.role, placement_scope=self.placement_scope, latency_ms=0.0)


def _build(tree: Any, nodes: dict[str, OmniNode], checker: OmniNode | None) -> OmniNode:
    if isinstance(tree, str):
        if tree == "check" and checker is not None:
            return checker
        return nodes[tree]
    op, left, right = tree
    a, b = _build(left, nodes, checker), _build(right, nodes, checker)
    return {">>": lambda: a >> b, "//": lambda: a // b, "|": lambda: a | b, "@": lambda: a @ b}[op]()


def _balanced(tree: Any) -> Any:
    """`a >> b >> c >> d` balanced, so depth grows with the log of the steps, and the runtime's nesting limit holds."""
    if isinstance(tree, str):
        return tree
    op, left, right = tree
    if op != ">>":
        return (op, _balanced(left), _balanced(right))
    chain: list[Any] = []

    def walk(t: Any) -> None:
        if isinstance(t, tuple) and t[0] == ">>":
            walk(t[1])
            walk(t[2])
        else:
            chain.append(_balanced(t))

    walk(tree)

    def fold(part: list[Any]) -> Any:
        if len(part) == 1:
            return part[0]
        mid = len(part) // 2
        return (">>", fold(part[:mid]), fold(part[mid:]))

    return fold(chain)


def compile_nodes(ctx: ShapeContext, block: dict[str, Any], grid: Any, cell: Any, *, sidecar_state: dict[str, Any] | None = None) -> dict[str, OmniNode]:
    conf, nodes = ctx.spec.get("sidecar"), {}
    for s in block["steps"]:
        kw: dict[str, Any] = {}
        if conf and conf.get("inside") == s["id"]:
            kw["sidecar"] = RowSidecar(conf, grid, cell, sidecar_state)
        nodes[s["id"]] = OPS[s["op"]](ctx, s, grid, cell, **kw)
    return nodes


def compile_shape(ctx: ShapeContext, grid: Any, cell: Any, *, maker_key_id: str, checker_key_id: str, sidecar_state: dict[str, Any] | None = None) -> tuple[OmniNode, dict[str, OmniNode]]:
    errors = validate(ctx.spec)
    if errors:
        raise ShapeError("; ".join(errors))
    nodes = compile_nodes(ctx, ctx.spec, grid, cell, sidecar_state=sidecar_state)
    checker = HandoffCheck(checker_key_id=checker_key_id, grid=grid, cell=cell)
    node = _build(_balanced(parse(ctx.spec["composition"])), nodes, checker)
    node.maker_worker_key = maker_key_id
    return node, nodes


def compile_check(ctx: ShapeContext, grid: Any, cell: Any) -> OmniNode:
    errors = validate(ctx.spec)
    if errors:
        raise ShapeError("; ".join(errors))
    nodes = compile_nodes(ctx, ctx.spec["check"], grid, cell)
    return _build(_balanced(parse(ctx.spec["check"]["composition"])), nodes, None)


def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[str(row.get("status"))] = out.get(str(row.get("status")), 0) + 1
    return dict(sorted(out.items()))


def mode_counts(rows: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """How many rows each kind of worker settled, from each row's trace."""
    settled = {"deterministic_only": 0, "reuse": 0, "sidecar": 0, "model": 0}
    for row in rows:
        modes = {t.get("mode") for t in row.get("trace") or []}
        outcomes = {t.get("outcome") for t in row.get("trace") or []}
        if "model" in modes and "proposed" in outcomes:
            settled["model"] += 1
        elif "sidecar" in modes:
            settled["sidecar"] += 1
        elif "answered_with_no_model_call" in outcomes:
            settled["reuse"] += 1
        else:
            settled["deterministic_only"] += 1
    return {"rows": len(rows), "settled_by": settled, "model_attempts": len(attempts), "model_attempts_failed": sum(a["outcome"] != "answered" for a in attempts),
            "by_model": {m: sum(len(a["item_keys"]) for a in attempts if a["model"] == m) for m in sorted({a["model"] for a in attempts})},
            "tokens": {"input": sum(a["input_tokens"] for a in attempts), "output": sum(a["output_tokens"] for a in attempts)},
            "cost_usd": round(sum(a["cost_usd"] for a in attempts), 6)}


def page_reader(policy: Any, fetch: Any, extract: Any, sha: Any) -> Any:
    def read(url: str) -> tuple[int, str, str | None]:
        try:
            got = fetch(url, policy)
            text = extract(got.content_type, got.raw)[1]
            return int(got.status), text, sha(got.raw)
        except Exception as exc:  # noqa: BLE001 - a refused or failed address is a finding about the row, not a crash
            return 0, "", f"unreadable:{type(exc).__name__}"

    return read
