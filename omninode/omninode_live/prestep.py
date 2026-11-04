"""A pre-step inside the OmniNode: cheap text signals choose what a model call gets, with no model call.

Tokens, identifiers, repository names, character 3-grams and a term histogram score each resource (BM25 plus small
bonuses), and a plain table (prestep_rules.json) can force a tool, force a code path, load a skill or add a step-back
note between model turns. Anything uncertain or broken behaves as if this file were not here: the run goes on as before.

Forced work takes the normal roads: labels go through the hybrid rule, the store and the independent check; lookups use
the GitHub allowance; model calls use the ledgers. Nothing here spends, approves or publishes on its own.

Every decision is a line in the trace: what it kept and cut, confidence, a token estimate (characters / 4, not a
measurement), the rules that fired, and whether a cut resource was asked for anyway. `learned()` reads those lines.

  python -m omninode_live.prestep            summary of the traces
  python -m omninode_live.prestep --tail 5   the last lines
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

_WORD = re.compile(r"[A-Za-z][a-z0-9]+|[A-Z]+(?![a-z])|[0-9]+[a-z]*")
_IDENT = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)+\b|\b[a-z]+[A-Z][A-Za-z0-9]*\b")
_REPO = re.compile(r"(?<![\w./-])[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*(?![\w/-])")
_PATH = re.compile(r"(?<![\w/-])(?:\.{0,2}/)?(?:[\w.-]+/){2,}[\w.-]*|\b[\w-]+\.(?:py|js|ts|json|md|sh|toml|ya?ml)\b")
_PRIVATE = re.compile(r"[\w.+-]+@[\w-]+\.\w+|\+?\d[\d ()-]{8,}\d")
_STOP = frozenset("a an and are as at be by for from in is it its of on or that the this to with you your".split())


def rules_path() -> Path:
    return Path(os.environ.get("OMNINODE_PRESTEP_RULES") or Path(__file__).with_name("prestep_rules.json"))


def traces_path() -> Path:
    return Path(os.environ.get("OMNINODE_PRESTEP_TRACES") or Path.home() / ".local/state/teleion-omninode/prestep-traces.jsonl")


def est_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def words(text: str) -> list[str]:
    return [w for w in (m.lower() for m in _WORD.findall(text)) if w not in _STOP]


def grams(text: str) -> set[str]:
    flat = " ".join(words(text))
    return {flat[i : i + 3] for i in range(max(0, len(flat) - 2))}


def signals(text: str) -> dict[str, Any]:
    """The text's segment signature, and its histogram."""
    terms = Counter(words(text))
    return {
        "terms": terms,
        "identifiers": {i.lower() for i in _IDENT.findall(text)},
        "repo_names": sorted(set(_REPO.findall(text))),
        "paths": sorted(set(_PATH.findall(text))),
        "signature": {
            "code": bool(terms.keys() & {"code", "repo", "repository", "python", "function", "cli", "lint", "linter", "parser", "compiler", "sdk"}),
            "needs_github": bool(_REPO.search(text)) or "github" in terms,
            "has_repo_name": bool(_REPO.search(text)),
            "has_path": bool(_PATH.search(text)),
        },
    }


def shortlist(task_text: str, universe: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """Score resources against the task. Pinned resources always stay. When confidence is low, everything stays."""
    started = time.perf_counter()
    sig = signals(task_text)
    query_grams, loose = grams(task_text), [r for r in universe if not r.get("pinned")]
    docs = {r["id"]: Counter(words(r["text"])) for r in loose}
    mean_len = sum(sum(d.values()) for d in docs.values()) / max(1, len(docs)) or 1.0
    scores: dict[str, float] = {}
    for r in loose:
        doc, score = docs[r["id"]], 0.0
        size = sum(doc.values())
        for term, tf in sig["terms"].items():
            if term in doc:
                seen_in = sum(term in d for d in docs.values())
                idf = math.log(1 + (len(docs) - seen_in + 0.5) / (seen_in + 0.5))
                score += min(tf, 3) * idf * doc[term] * 2.2 / (doc[term] + 1.2 * (0.25 + 0.75 * size / mean_len))
        doc_grams = grams(r["text"])
        if doc_grams and query_grams:
            score += float(cfg["ngram_weight"]) * len(doc_grams & query_grams) / len(doc_grams | query_grams)
        score += float(cfg["identifier_weight"]) * sum(i in r["text"].lower() for i in sig["identifiers"])
        scores[r["id"]] = round(score, 4)
    top, total = max(scores.values(), default=0.0), sum(scores.values())
    ranked = sorted(loose, key=lambda r: (-scores[r["id"]], r["id"]))
    kept_loose = [r["id"] for r in ranked if scores[r["id"]] > 0 and scores[r["id"]] >= top * float(cfg["keep_share_of_top"])][: int(cfg["keep_at_most"])]
    mass = sum(scores[i] for i in kept_loose) / total if total else 0.0
    confidence = round(mass * min(1.0, top / float(cfg["min_top_score"])), 4)
    reason = None
    if len(loose) < int(cfg["min_universe"]):
        reason = "small_universe"
    elif confidence < float(cfg["min_confidence"]):
        reason = "low_confidence"
    kept_ids = {r["id"] for r in universe} if reason else {r["id"] for r in universe if r.get("pinned")} | set(kept_loose)
    sent = [r for r in universe if r.get("sent")]
    return {
        "kept": [r["id"] for r in universe if r["id"] in kept_ids],
        "cut": [r["id"] for r in universe if r["id"] not in kept_ids],
        "confidence": confidence, "fell_open": bool(reason), "reason": reason, "scores": scores,
        "tokens_before_est": sum(est_tokens(r["text"] if r.get("send_text") is None else r["send_text"]) for r in sent),
        "tokens_after_est": sum(est_tokens(r["text"] if r.get("send_text") is None else r["send_text"]) for r in sent if r["id"] in kept_ids),
        "signature": sig["signature"], "repo_names": len(sig["repo_names"]), "top_terms": [t for t, _ in sig["terms"].most_common(8)],
        "ms": round((time.perf_counter() - started) * 1000, 3),
    }


def merge_decisions(parts: list[dict[str, Any]], universe: list[dict[str, Any]]) -> dict[str, Any]:
    """A group shares one category list, so it keeps what any of its items keeps. One unsure item opens the list for all."""
    unsure = next((p for p in parts if p["fell_open"]), None)
    kept_ids = {r["id"] for r in universe} if unsure or not parts else {i for p in parts for i in p["kept"]}
    size = lambda r: est_tokens(r["send_text"] if r.get("send_text") is not None else r["text"])  # noqa: E731
    sent = [r for r in universe if r.get("sent")]
    scores: dict[str, float] = {}
    for p in parts:
        for key, value in p["scores"].items():
            scores[key] = max(scores.get(key, 0.0), value)
    terms = Counter(t for p in parts for t in p["top_terms"])
    return {
        "kept": [r["id"] for r in universe if r["id"] in kept_ids], "cut": [r["id"] for r in universe if r["id"] not in kept_ids],
        "confidence": min((p["confidence"] for p in parts), default=0.0), "fell_open": bool(unsure) or not parts, "reason": unsure["reason"] if unsure else None if parts else "empty_group",
        "scores": scores, "tokens_before_est": sum(size(r) for r in sent), "tokens_after_est": sum(size(r) for r in sent if r["id"] in kept_ids),
        "signature": {k: any(p["signature"][k] for p in parts) for k in (parts[0]["signature"] if parts else {})},
        "top_terms": [t for t, _ in terms.most_common(8)], "ms": round(sum(p["ms"] for p in parts), 3),
    }


def read_traces(path: Path | None = None, last: int = 5000) -> list[dict[str, Any]]:
    try:
        lines = (path or traces_path()).read_text(encoding="utf-8").splitlines()[-last:]
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def learned(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """What the traces teach: pin what was cut and then wanted, turn off a forced rule the audit keeps refusing,
    add words from labels a different worker approved, and remember items that got nowhere."""
    misses: Counter[str] = Counter()
    owner: dict[str, tuple[str, Any, Any]] = {}  # who made an item's current label; a check may land in a later run
    rule_seen: Counter[str] = Counter()
    rule_bad: Counter[str] = Counter()
    failed: Counter[str] = Counter()
    terms: dict[str, Counter[str]] = {}
    for row in rows:
        kind = row.get("kind")
        if kind == "call":
            misses.update(row.get("asked_for_anyway") or [])
            for key, category in (row.get("answered") or {}).items():
                owner[key] = ("model", category, list(row.get("top_terms") or []))
        elif kind == "forced" and row.get("do") == "force_function":
            owner[str(row.get("key"))] = ("rule", row.get("rule"), None)
        elif kind == "finish":
            failed.update(row.get("failed_keys") or [])
        elif kind == "check" and row.get("verdict") in ("approve", "reject") and str(row.get("key")) in owner:
            who, name, words_ = owner.pop(str(row.get("key")))
            if who == "rule":
                rule_seen[name] += 1
                rule_bad[name] += row.get("verdict") == "reject"
            elif row.get("verdict") == "approve":
                terms.setdefault(name, Counter()).update(words_)
    limit = int(cfg["learned_terms_per_resource"])
    return {
        "pins": sorted(r for r, n in misses.items() if n >= int(cfg["pin_after_misses"])),
        "rules_off": sorted(r for r, n in rule_bad.items() if n >= int(cfg["rule_off_after_rejects"]) and n / rule_seen[r] >= float(cfg["rule_off_reject_share"])),
        "terms": {c: [t for t, _ in n.most_common(limit)] for c, n in terms.items()},
        "failed_keys": failed,
    }


def append(row: dict[str, Any], path: Path | None = None) -> None:
    """A lost trace line never stops the work."""
    try:
        target = path or traces_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **row}, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:  # noqa: BLE001
        pass


def record_check(run_id: str, verdicts: dict[str, Any]) -> None:
    """The independent check's verdicts join the trace, read-only as far as the check is concerned."""
    try:
        for key, row in verdicts.items():
            append({"kind": "check", "run_id": run_id, "key": key, "verdict": row.get("verdict")})
    except Exception:  # noqa: BLE001
        pass


def item_text(item: dict[str, Any]) -> str:
    return " ".join([str(item.get("full_name") or ""), str(item.get("description") or ""), " ".join(item.get("topics") or [])])


def default_plan(categories: list[str]) -> dict[str, Any]:
    return {"categories": list(categories), "skills": [], "step_back": None, "cut": [], "firings": []}


class PreStep:
    """One run's pre-step. Every public method falls open: an error is recorded and the run behaves as today."""

    def __init__(self, run_id: str, *, spec: dict[str, Any]) -> None:
        self.run_id, self.spec = run_id, spec
        self.errors: list[str] = []
        self.summary: dict[str, Any] = {"decisions": 0, "fell_open": 0, "cut": 0, "firings": {}, "asked_for_anyway": 0, "tokens_before_est": 0, "tokens_after_est": 0, "errors": 0}
        self.turns: list[dict[str, Any]] = []
        self.fired: Counter[str] = Counter()
        self.rules: dict[str, Any] = {"enabled": False}
        self.memory: dict[str, Any] = {"pins": [], "rules_off": [], "terms": {}, "failed_keys": Counter()}
        try:
            self.rules = json.loads(rules_path().read_text(encoding="utf-8"))
            if self.rules.get("enabled"):
                self.memory = learned(read_traces(last=int(self.rules["learning"]["traces_read"])), self.rules["learning"])
        except Exception as exc:  # noqa: BLE001
            self.rules = {"enabled": False}
            self._error("load", exc)

    @property
    def enabled(self) -> bool:
        return bool(self.rules.get("enabled"))

    def _error(self, where: str, exc: Exception) -> None:
        self.errors.append(f"{where}: {type(exc).__name__}: {str(exc)[:120]}")
        self.summary["errors"] += 1

    def _firing(self, rule: dict[str, Any], **more: Any) -> dict[str, Any]:
        self.fired[rule["id"]] += 1
        self.summary["firings"][rule["id"]] = self.summary["firings"].get(rule["id"], 0) + 1
        return {"rule": rule["id"], "do": rule["do"], **more}

    def _matches(self, when: dict[str, Any], *, item: dict[str, Any] | None = None, group: list[dict[str, Any]] | None = None) -> bool:
        """Every condition must hold. A condition this code does not know means the rule does not fire."""
        for name, want in when.items():
            if name == "has_repo_name":
                ok = bool(item and _REPO.fullmatch(str(item.get("full_name") or ""))) == bool(want)
            elif name == "field_missing":
                ok = bool(item) and not item.get(want)
            elif name == "trace_outcome":
                ok = bool(item) and any(t.get("outcome") == want for t in item.get("trace", []))
            elif name == "any_topic":
                ok = any(set(want) & {t.lower() for t in i.get("topics") or []} for i in ([item] if item else group or []))
            elif name == "name_or_description_has_any":
                head = f"{(item or {}).get('full_name', '')} {(item or {}).get('description', '')}".lower()
                ok = any(w in head for w in want)
            elif name == "no_prior_failure":  # a new digest from a forced lookup must not end a backoff
                ok = bool(item) and not (item.get("prev_value") or {}).get("failed_digest")
            elif name == "no_prior_label":  # a label a model made and a worker checked is not replaced by a template
                ok = bool(item) and not ((item.get("prev_value") or {}).get("labels"))
            elif name == "text_has_none":
                ok = bool(item) and not any(w in item_text(item).lower() for w in want)
            elif name == "description_chars_below":
                ok = any(len(str(i.get("description") or "")) < int(want) for i in group or ([item] if item else []))
            elif name == "item_failed_before":
                ok = any(self.memory["failed_keys"].get(i.get("key"), 0) >= int(want) for i in group or [])
            elif name == "no_progress_turns":
                recent = self.turns[-int(want) :]
                ok = len(recent) >= int(want) and all(t["labels"] == 0 for t in recent)
            elif name == "tokens_growing_turns":
                recent = [t["tokens"] for t in self.turns[-int(want) :]]
                ok = len(recent) >= int(want) and all(a < b for a, b in zip(recent, recent[1:], strict=False))
            else:
                self.errors.append(f"unknown condition {name}")
                return False
            if not ok:
                return False
        return True

    def before_batch(self, pending: list[dict[str, Any]], *, settings: dict[str, Any], screen: Any, github: Any, validate: Any, trace: Any, digest: Any) -> None:
        """Tools and code paths the text calls for, before any item takes a place in a model batch."""
        if not self.enabled:
            return
        try:
            for rule in self.rules.get("rules", []):
                if rule.get("do") not in ("force_tool", "force_function") or rule["id"] in self.memory["rules_off"]:
                    continue
                for item in pending:
                    try:
                        if item.get("status") != "needs_label" or self.fired[rule["id"]] >= int(rule.get("max_per_run", 1)) or not self._matches(rule["when"], item=item):
                            continue
                        if _PRIVATE.search(item_text(item)):  # a forced path never handles anything that looks personal
                            self._note_refusal(rule, item, "looks_personal")
                        elif rule["do"] == "force_tool":
                            self._force_tool(rule, item, github, trace, digest)
                        else:
                            self._force_function(rule, item, settings, screen, validate, trace)
                    except Exception as exc:  # noqa: BLE001
                        self._error(str(rule.get("id")), exc)
        except Exception as exc:  # noqa: BLE001
            self._error("before_batch", exc)

    def _note_refusal(self, rule: dict[str, Any], item: dict[str, Any], why: str) -> None:
        append({"kind": "refused", "run_id": self.run_id, "key": item.get("key"), "rule": rule["id"], "do": rule["do"], "why": why})

    def _force_tool(self, rule: dict[str, Any], item: dict[str, Any], github: Any, trace: Any, digest: Any) -> None:
        if rule["tool"] != "github_latest_release":
            raise ValueError(f"no such tool here: {rule['tool']}")
        if not github.spare():  # the allowance holds for forced calls too
            self._note_refusal(rule, item, "github_allowance")
            return
        item["latest_release"] = github.latest_release(item["full_name"])
        item["content_digest"] = digest(item)
        trace(item, "release", "deterministic", "forced_tool", rule=rule["id"])
        self._firing(rule, key=item["key"])
        append({"kind": "forced", "run_id": self.run_id, "key": item["key"], "rule": rule["id"], "do": "force_tool", "tool": rule["tool"], "found": bool(item["latest_release"])})

    def _force_function(self, rule: dict[str, Any], item: dict[str, Any], settings: dict[str, Any], screen: Any, validate: Any, trace: Any) -> None:
        """The label from the rule's own words, so no third-party text goes public. A label the hybrid rule
        would refuse is dropped here and the item goes to a model as usual."""
        topics = {t.lower(): t for t in item.get("topics") or []}
        topic = next(topics[t] for t in rule["when"]["any_topic"] if t in topics)
        label = {"key": item["key"], "category": rule["category"], "determinism": rule["determinism"], "use_cases": [t for t in item.get("topics") or [] if t.lower() not in rule["when"]["any_topic"] and len(t) <= 60][:3],
                 "summary": f"A public repository, {item['full_name']}, listed under {topic}: {rule['phrase']}.",
                 "evidence": [topic], "confidence_milli": int(rule["confidence_milli"])}
        failures = validate(label, item, settings, screen)
        if failures:
            self._note_refusal(rule, item, ",".join(failures))
            return
        item.update(proposed=label, status="proposed", maker_variant=None, maker_model="deterministic_rule", cost_usd=0.0, model_seconds=0.0)
        trace(item, "label", "deterministic", "forced_function", rule=rule["id"], tokens=0, cost_usd=0.0)
        self._firing(rule, key=item["key"])
        append({"kind": "forced", "run_id": self.run_id, "key": item["key"], "rule": rule["id"], "do": "force_function", "category": rule["category"],
                "model_call_avoided": True, "tokens_est_if_sent": est_tokens(item_text(item))})

    def before_call(self, group: list[dict[str, Any]], categories: list[str], base_system: str) -> dict[str, Any]:
        """What this model call gets. On any error, exactly what it would have got."""
        plan = default_plan(categories)
        if not self.enabled:
            return plan
        try:
            doc = self.rules["categories"]
            pinned = set(self.rules.get("pinned_categories") or []) | set(self.memory["pins"]) | {f"category:{c}" for c in categories if c not in doc}
            universe = [{"id": f"category:{c}", "kind": "category", "sent": True, "send_text": json.dumps(c),
                         "pinned": c in pinned or f"category:{c}" in pinned,
                         "text": " ".join([c.replace("_", " "), doc.get(c, ""), *self.memory["terms"].get(c, [])])} for c in categories]
            params = self.spec["parameters"]
            for kind, names in (("tool", params["tools"]), ("hook", params["hooks"]), ("skill", list(params["skills"])), ("model", [v["id"] for v in params["model"]["variants"]])):
                universe += [{"id": f"{kind}:{n}", "kind": kind, "text": str(n), "pinned": True} for n in names]  # code runs these; the tuner picks the model
            decision = merge_decisions([shortlist(item_text(i), universe, self.rules["shortlist"]) for i in group], universe)
            plan["decision"] = decision
            plan["categories"] = [c for c in categories if f"category:{c}" in decision["kept"]] or list(categories)
            plan["cut"] = [c for c in categories if c not in plan["categories"]]
            for rule in self.rules.get("rules", []):
                try:
                    if rule.get("do") == "load_skill" and self._matches(rule["when"], group=group):
                        text = self.rules["skills"][rule["skill"]]
                        if not isinstance(text, str):
                            raise TypeError("a skill must be text")
                        plan["skills"].append(text)
                        plan["firings"].append(self._firing(rule, skill=rule["skill"], tokens_est=est_tokens(text)))
                    elif rule.get("do") == "step_back" and not plan["step_back"] and self._matches(rule["when"], group=group):
                        text = self.rules["step_back_text"]
                        if not isinstance(text, str):
                            raise TypeError("the step-back note must be text")
                        plan["step_back"] = text
                        plan["firings"].append(self._firing(rule))
                except Exception as exc:  # noqa: BLE001
                    self._error(rule.get("id", "rule"), exc)
        except Exception as exc:  # noqa: BLE001
            self._error("before_call", exc)
            return default_plan(categories) | {"error": True}
        return plan

    def after_call(self, plan: dict[str, Any], group: list[dict[str, Any]], labels: dict[str, Any], *, tokens: int, variant: str, outcome: str) -> None:
        try:
            self.turns.append({"labels": sum(i.get("key") in labels for i in group), "tokens": tokens})
            decision = plan.get("decision") or {}
            answered = {k: v.get("category") for k, v in labels.items() if isinstance(v, dict) and isinstance(v.get("category"), str)}
            wanted = sorted({f"category:{c}" for c in answered.values() if c in plan["cut"]})
            pinned_after_cut = sum(c in (self.rules.get("pinned_categories") or []) for c in answered.values()) if plan["cut"] else 0  # the model may have wanted a cut one
            before, after = decision.get("tokens_before_est", 0), decision.get("tokens_after_est", 0)
            s = self.summary
            s["decisions"] += 1
            s["fell_open"] += bool(decision.get("fell_open") or plan.get("error"))
            s["cut"] += len(plan["cut"])
            s["asked_for_anyway"] += len(wanted)
            s["tokens_before_est"] += before
            s["tokens_after_est"] += after
            append({"kind": "call", "run_id": self.run_id, "turn": len(self.turns), "keys": [i.get("key") for i in group], "variant": variant, "outcome": outcome,
                    **{k: decision.get(k) for k in ("kept", "cut", "confidence", "fell_open", "reason", "scores", "signature", "top_terms", "ms")},
                    "tokens_before_est": before, "tokens_after_est": after, "firings": plan["firings"],
                    "step_back": bool(plan["step_back"]), "answered": answered, "asked_for_anyway": wanted, "fallback_category_after_cut": pinned_after_cut, "tokens_used": tokens})
        except Exception as exc:  # noqa: BLE001
            self._error("after_call", exc)

    def finish(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """The run's closing line, even when no item needed a model. Its summary goes on the run record."""
        try:
            failed = [i.get("key") for i in items if i.get("status") in ("rule_rejected", "label_failed")]
            forced = [i.get("key") for i in items if i.get("maker_model") == "deterministic_rule" and i.get("maker_variant", "") is None]
            self.summary.update(enabled=self.enabled, forced_items=len(forced), rules_off=self.memory["rules_off"], pins=self.memory["pins"])
            append({"kind": "finish", "run_id": self.run_id, "enabled": self.enabled, "items": len(items), "failed_keys": failed, "forced_keys": forced,
                    "errors": self.errors[:10], "summary": self.summary})
        except Exception as exc:  # noqa: BLE001
            self._error("finish", exc)
        return self.summary


def report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [r for r in rows if r.get("kind") == "call"]
    forced = [r for r in rows if r.get("kind") == "forced"]
    checks = {r.get("key"): r.get("verdict") for r in rows if r.get("kind") == "check"}
    return {
        "runs": sum(r.get("kind") == "finish" for r in rows), "model_calls_seen": len(calls),
        "fell_open": sum(bool(r.get("fell_open")) for r in calls), "cut_resources": sum(len(r.get("cut") or []) for r in calls),
        "asked_for_anyway": Counter(x for r in calls for x in r.get("asked_for_anyway") or []),
        "tokens_est_note": "characters / 4 for what the shortlist covers; an estimate, not a measurement",
        "tokens_before_est": sum(r.get("tokens_before_est") or 0 for r in calls), "tokens_after_est": sum(r.get("tokens_after_est") or 0 for r in calls),
        "firings": Counter(f["rule"] for r in calls for f in r.get("firings") or []) + Counter(r.get("rule") for r in forced),
        "forced_verdicts": Counter(checks.get(r.get("key"), "not_checked_yet") for r in forced if r.get("do") == "force_function"),
        "refused": Counter(r.get("why") for r in rows if r.get("kind") == "refused"),
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    table = read_traces(last=200000)
    if args[:1] == ["--tail"]:
        for line in table[-int(args[1]) :]:
            print(json.dumps(line, ensure_ascii=False))
    else:
        print(json.dumps(report(table), indent=1, default=dict))
