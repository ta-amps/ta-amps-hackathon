"""Size a Task before anyone spends on it. Plain code, no model call.

Goal: more Tasks really finished per dollar. Reward: reward() below. Invariants: spend caps, every choice on the record, a
checker that isn't the maker, nothing private. Everything else lives in a rule table (versions/vN.json) that tuner.py rewrites.

  size_task(task, signals, table) -> decision: none, small or big, what to hand over, and the budget for the attempt.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

SMALL, BIG = "muse-spark-1.3", "muse-wonder-1.0"
_WORD = re.compile(r"[a-z][a-z0-9]{2,}")
_STOP = frozenset("the and for with from this that into then each any all not but are was its use using after before via per one two".split())
_OBJECT = re.compile(r"(?<![\w/-])[a-z][a-z0-9_-]*_v\d+\b|/q/object/([A-Za-z0-9_.:-]{3,160})")


def words(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def kind_of(task: dict[str, Any]) -> str:
    cat = str(task.get("category") or "unknown")
    if cat.startswith("e2e-canary"):
        cat = "e2e-canary"
    return f"{cat}|{str(task.get('step_mode') or '').replace('atomic_', '').replace('_step', '')}"


def bucket(task_id: str, salt: str) -> int:
    return int(hashlib.sha256(f"{salt}:{task_id}".encode()).hexdigest(), 16) % 100


def named_objects(task: dict[str, Any]) -> list[str]:
    """Task Object keys the Task's own text names. The target of a Task never needs a model to find."""
    out: list[str] = []
    for m in _OBJECT.finditer(f"{task.get('title') or ''} {task.get('prompt') or ''}"):
        key = m.group(1) or m.group(0)
        if key not in out:
            out.append(key)
    return out[:6]


_NAMED_TASK = re.compile(r"\bverb_[a-z]+_[0-9a-f]{8,}\b")
_WAITS = re.compile(r"\b(once|when|after|until)\b", re.I)


def named_tasks(task: dict[str, Any]) -> list[str]:
    found = _NAMED_TASK.findall(f"{task.get('title') or ''} {task.get('prompt') or ''}")
    return [t for t in dict.fromkeys(found) if t != task.get("task_id")][:4]


def similar_past(task: dict[str, Any], past: list[dict[str, Any]], min_jaccard: float) -> list[dict[str, Any]]:
    """Earlier audited attempts on Tasks with close titles, other than this Task."""
    mine = words(str(task.get("title") or ""))
    found = []
    for r in past:
        if r.get("task_id") == task.get("task_id") or r.get("audit_pass") is None:
            continue
        theirs = words(str(r.get("title") or ""))
        union = mine | theirs
        if union and len(mine & theirs) / len(union) >= min_jaccard:
            found.append(r)
    return found


def needs_people_hits(task: dict[str, Any], table: dict[str, Any]) -> list[str]:
    title = words(str(task.get("title") or ""))
    return sorted(title & set(table["needs_people_terms"]))


def budget_for(kind: str, size: str, table: dict[str, Any]) -> dict[str, Any]:
    per_kind = (table["budgets"].get(kind) or {}).get(size)
    return dict(per_kind or table["budgets"]["default"][size])


def size_task(task: dict[str, Any], signals: dict[str, Any], table: dict[str, Any]) -> dict[str, Any]:
    """signals: search_hits (list of {id, kind, title, state, score}), past (earlier audited records). Never calls a model."""
    kind = kind_of(task)
    task_id = str(task.get("task_id") or "")
    prompt = str(task.get("prompt") or "")
    fired: list[str] = []
    base = {"task_id": task_id, "kind": kind, "table_version": table["version"], "title_chars": len(str(task.get("title") or "")), "prompt_chars": len(prompt),
            "complexity_milli": task.get("complexity_milli"), "step_mode": task.get("step_mode"), "tools": [], "skills": [], "hooks": [], "task_objects": [], "budget": {"max_output_tokens": 0, "usd": 0.0}}

    def none(handler: str, why: str, **extra: Any) -> dict[str, Any]:
        return {**base, "size": "none", "model": None, "harness": "plain_function", "handler": handler, "why": why, "rules_fired": fired + [handler], **extra}

    for rule in table["plain_code"]:
        if task_id.startswith(rule["task_id_prefix"]):
            return none(rule["handler"], rule["why"], hooks=["server_field_check", "read_back"], tools=["read_task_object"])
    if str(task.get("step_mode")) == "atomic_verification_step":
        return none("not_for_a_maker", "a check: the maker path never does checks")
    if kind.startswith("e2e-canary"):
        return none("not_for_a_maker", "a test fixture owned by the end-to-end run")

    hits = signals.get("search_hits") or []
    title_norm = " ".join(sorted(words(str(task.get("title") or ""))))
    for h in hits:
        if h.get("kind") == "durable_task" and h.get("state") in ("done", "completed", "verified") and h.get("id") != task_id \
                and title_norm and " ".join(sorted(words(str(h.get("title") or "")))) == title_norm:
            return none("earlier_result", "a finished Task with the same title may already answer this", earlier_task=h["id"], hooks=["small_audit"])

    states = signals.get("named_task_states") or {}
    waiting_on = [t for t, st in states.items() if st not in ("done", "completed", "verified")]
    if waiting_on and _WAITS.search(f"{task.get('title') or ''} {prompt}"):
        return none("decline_blocked", f"it waits on a Task that isn't finished: {waiting_on[0]}", waiting_on=waiting_on)
    people = needs_people_hits(task, table)
    if people:
        fired.append("needs_people_terms")
        return none("decline_needs_people", f"title says this needs people, a place or a device: {', '.join(people[:4])}", terms=people)
    sim = table["similar"]
    near = similar_past(task, signals.get("past") or [], float(sim["min_jaccard"]))
    if len(near) >= int(sim["min_n"]) and not any(r["audit_pass"] for r in near) and all(r.get("audit_needs_people") for r in near):
        fired.append("similar_tasks_needed_people")
        return none("decline_needs_people", f"{len(near)} close Tasks came back needing people or hardware", similar=[r["task_id"] for r in near][:5])

    big = table["big"]
    wants_big = int(task.get("complexity_milli") or 0) >= int(big["min_complexity_milli"]) or len(prompt) >= int(big["min_prompt_chars"]) or bool(words(str(task.get("title") or "")) & set(big["terms"]))
    near_big = [r for r in near if r.get("size") == "big"]
    near_small = [r for r in near if r.get("size") == "small"]
    if len(near_small) >= int(sim["min_n"]) and not any(r["audit_pass"] for r in near_small) and not any(r.get("audit_needs_people") for r in near_small):
        wants_big = True
        fired.append("similar_tasks_failed_small")
    elif wants_big and len(near_small) >= int(sim["min_n"]) and all(r["audit_pass"] for r in near_small):
        wants_big = False
        fired.append("similar_tasks_passed_small")
    size = "big" if wants_big else "small"
    if wants_big:
        fired.append("big_signal")
    objects: list[str] = list(named_objects(task))
    limit = int(table["objects"]["max"])
    found = [h["id"] for h in hits if h.get("kind") == "task_object" and float(h.get("score") or 0) >= float(table["objects"]["min_score"]) and h["id"] != task_id]
    for key in found:
        if len(objects) >= limit:
            break
        if key not in objects:
            objects.append(key)
    objects = objects[:limit]
    skills = [s["id"] for s in table["skills"] if words(f"{task.get('title') or ''} {prompt}") & set(s["when_any"])]
    tools = (["read_task_object"] if objects else [])
    return {**base, "size": size, "model": BIG if size == "big" else SMALL, "harness": "one_json_answer", "handler": "model", "why": ", ".join(fired) or "the default: small model",
            "rules_fired": fired, "tools": tools, "skills": skills, "hooks": ["secret_screen", "word_screen", "model_audit"], "task_objects": objects, "budget": budget_for(kind, size, table),
            "near": len(near), "near_passed": sum(1 for r in near if r["audit_pass"])}


def reward(row: dict[str, Any], weights: dict[str, Any]) -> float:
    """1 for a Task really finished, less what it cost. A Task left for someone able to do it costs nothing and earns nothing."""
    done = 1.0 if row.get("finished_ok") else 0.0
    return done - (float(row.get("usd") or 0.0) + float(row.get("audit_usd") or 0.0)) * float(weights["per_usd"]) - float(row.get("seconds") or 0.0) * float(weights["per_second"])
