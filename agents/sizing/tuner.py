"""Propose a new rule table from recorded outcomes, test it on held-out past Tasks, try it on a small share, and roll back by itself.

Learning counts only when a later decision changes because of an earlier outcome. learning_examples() looks for exactly that.
  tuner.py step        propose, test, canary, promote or roll back, as the records allow
  tuner.py restore N   make version N active
"""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sizer  # noqa: E402
import store  # noqa: E402

SHARE_PCT, MARGIN = 25, 0.02
MIN_TRAIN, MIN_HELD, CANARY_MIN, ROLLBACK_DROP = 10, 8, 6, 0.15


def scored(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Records where a model answered and a different model read it."""
    return [r for r in rows if r.get("audit_pass") is not None and r.get("size") in ("small", "big")]


def is_held(task_id: str, salt: str) -> bool:
    return sizer.bucket(task_id, "held:" + salt) < 35


def propose(train: list[dict[str, Any]], table: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    new, changes = copy.deepcopy(table), []
    # Words in titles of Tasks that keep coming back as needing people, and never passed.
    seen, bad = Counter(), Counter()
    for r in train:
        for w in sizer.words(str(r.get("title") or "")):
            seen[w] += 1
            if not r["audit_pass"] and r.get("audit_needs_people"):
                bad[w] += 1
    common = {w for w, n in seen.items() if n > max(4, len(train) // 3)}  # a word in most titles says nothing
    for w, n in bad.most_common():
        if n >= 3 and n == seen[w] and w not in common and w not in new["needs_people_terms"] and len(changes) < 6:
            new["needs_people_terms"] = sorted({*new["needs_people_terms"], w})
            changes.append(f"needs_people_terms + {w}: {n} of {seen[w]} needed people, none passed")
    # Budgets: what passed answers really used, by kind and size.
    used: dict[tuple[str, str], list[int]] = {}
    cuts: Counter = Counter()
    for r in train:
        key = (r["kind"], r["size"])
        if r.get("budget_cut"):
            cuts[key] += 1
        if r["audit_pass"] and r.get("output_tokens"):
            used.setdefault(key, []).append(int(r["output_tokens"]))
    for (kind, size), vals in used.items():
        if len(vals) < 3:
            continue
        vals.sort()
        wanted = int(vals[min(len(vals) - 1, int(len(vals) * 0.9))] * 1.5) if not cuts[(kind, size)] else int(vals[-1] * 2)
        wanted = max(800, wanted)
        current = sizer.budget_for(kind, size, new)["max_output_tokens"]
        if abs(wanted - current) / current >= 0.2:
            per_token = 4.25e-6 if size == "small" else 20e-6
            new["budgets"].setdefault(kind, {})[size] = {"max_output_tokens": wanted, "usd": round(wanted * per_token * 1.2 + 0.005, 4)}
            changes.append(f"budget {kind} {size}: {current} to {wanted} tokens, from {len(vals)} passed answers, {cuts[(kind, size)]} cut")
    # The big model's threshold isn't tuned: small is read by big and big by small, so their pass rates have different judges.
    return new, changes


def _task_from(r: dict[str, Any]) -> dict[str, Any]:
    d = r.get("decision") or {}
    cat, _, mode = r["kind"].partition("|")
    return {"task_id": r["task_id"], "title": r.get("title"), "category": cat, "step_mode": d.get("step_mode") or f"atomic_{mode}_step", "complexity_milli": d.get("complexity_milli"), "prompt": "x" * int(d.get("prompt_chars") or 0)}


def replay(table: dict[str, Any], rows: list[dict[str, Any]], weights: dict[str, Any]) -> dict[str, Any]:
    """Would this table have done better on these past Tasks? Only what the record shows: a Task it declines earns 0 and costs 0; otherwise the logged result stands.
    A passed answer that its budget would have cut is priced as a second try. A different size has no observation, so it counts as the logged result and is reported."""
    total, declined_bad, declined_good, cut, other_size = 0.0, 0, 0, 0, 0
    for r in rows:
        d = sizer.size_task(_task_from(r), {}, table)
        logged = sizer.reward({"finished_ok": bool(r.get("audit_pass")), "usd": r.get("usd"), "audit_usd": r.get("audit_usd")}, weights)
        if d["size"] == "none":
            declined_good += bool(r.get("audit_pass"))
            declined_bad += not r.get("audit_pass")
            continue
        other_size += d["size"] != r["size"]
        if d["size"] == r["size"] and r.get("audit_pass") and int(r.get("output_tokens") or 0) > int(d["budget"]["max_output_tokens"]):
            cut += 1
            total += logged - float(r.get("usd") or 0.0) * float(weights["per_usd"])
        else:
            total += logged
    return {"mean_reward": round(total / len(rows), 4) if rows else None, "n": len(rows), "declined_failed": declined_bad, "declined_passed": declined_good, "would_cut_passed": cut, "other_size_no_observation": other_size}


def canary_rows(version: int, since: str) -> list[dict[str, Any]]:
    return [r for r in store.read("outcomes.jsonl") if r.get("at", "") >= since and (r.get("decision") or {}).get("table_version") == version and r.get("arm") == "sized"]


def _judged(rows: list[dict[str, Any]], weights: dict[str, Any]) -> list[float]:
    """Model-sized rows and declines count; the index Tasks are the same under every table and would hide any drop."""
    return [sizer.reward(r, weights) for r in rows if r.get("handler") != "client_index" and r.get("stopped") != "claim_empty"]  # a lost race says nothing about a table


def step(run: str = "") -> dict[str, Any]:
    st = store.state()
    active = store.table(int(st["active"]))
    weights = active["reward"]
    outcome: dict[str, Any] = {"run": run, "active": st["active"]}
    can = st.get("canary")
    if can:
        rows_can, rows_act = canary_rows(int(can["version"]), can["since"]), canary_rows(int(st["active"]), can["since"])
        a, b = _judged(rows_can, weights), _judged(rows_act, weights)
        outcome.update(canary=can["version"], canary_n=len(a), active_n=len(b))
        if len(a) >= CANARY_MIN and len(b) >= CANARY_MIN:
            mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
            outcome.update(canary_mean=round(mean_a, 4), active_mean=round(mean_b, 4))
            finished = sum(bool(r.get("finished_ok")) for r in rows_can + rows_act)
            if finished == 0:
                # Every attempt costs and every decline scores 0, so with no finished Task more declining always looks better. That's less spend, not evidence of better work.
                st["history"].append({**outcome, "at": store.now(), "event": "ended_no_evidence", "version": can["version"]})
                st.setdefault("refused_changes", []).append(can.get("changes_key"))
                st["canary"] = None
                outcome["event"] = "ended_no_evidence"
                store.save_state(st)
                store.append("tuner.jsonl", outcome)
            elif mean_a < mean_b - ROLLBACK_DROP:
                st["history"].append({**outcome, "at": store.now(), "event": "rolled_back", "version": can["version"]})
                st.setdefault("refused_changes", []).append(can.get("changes_key"))
                st["canary"] = None
                outcome["event"] = "rolled_back"
                store.save_state(st)
                store.append("tuner.jsonl", outcome)
            elif mean_a >= mean_b - 1e-9:
                st["history"].append({**outcome, "at": store.now(), "event": "promoted", "version": can["version"], "from": st["active"]})
                st["watch"] = {"previous": st["active"], "mean_before": round(mean_b, 4), "since": store.now(), "changes_key": can.get("changes_key")}
                st["active"], st["canary"] = can["version"], None
                outcome["event"] = "promoted"
                store.save_state(st)
                store.append("tuner.jsonl", outcome)
            else:
                outcome["event"] = "waiting_on_canary"
        else:
            outcome["event"] = "waiting_on_canary"
        return outcome
    watch = st.get("watch")
    if watch:  # after a promotion, results that drop send it back by themselves
        after = _judged(canary_rows(int(st["active"]), watch["since"]), weights)
        if len(after) >= CANARY_MIN:
            mean_after = sum(after) / len(after)
            if mean_after < float(watch["mean_before"]) - ROLLBACK_DROP:
                st["history"].append({"at": store.now(), "event": "rolled_back_after_promotion", "version": st["active"], "to": watch["previous"], "mean_after": round(mean_after, 4), "mean_before": watch["mean_before"]})
                st["active"] = watch["previous"]
                st.setdefault("refused_changes", []).append(watch.get("changes_key"))
                outcome["event"] = "rolled_back_after_promotion"
            st["watch"] = None
            store.save_state(st)
            store.append("tuner.jsonl", outcome)
            if outcome.get("event"):
                return outcome
    rows = scored(store.read("outcomes.jsonl"))
    salt = str(active["split_salt"])
    train, held = [r for r in rows if not is_held(r["task_id"], salt)], [r for r in rows if is_held(r["task_id"], salt)]
    outcome.update(train=len(train), held_out=len(held))
    if len(train) < MIN_TRAIN or len(held) < MIN_HELD:
        outcome["event"] = "too_few_records"
        return outcome
    cand, changes = propose(train, active)
    if not changes:
        outcome["event"] = "nothing_to_change"
        store.append("tuner.jsonl", outcome)
        return outcome
    key = json.dumps(sorted(changes))
    if key in (st.get("refused_changes") or []):
        outcome["event"] = "same_proposal_as_a_rolled_back_one"
        return outcome
    old_score, new_score = replay(active, held, weights), replay(cand, held, weights)
    outcome.update(changes=changes, held_out_old=old_score, held_out_new=new_score)
    words_changed = cand["needs_people_terms"] != active["needs_people_terms"]
    any_pass = any(r.get("audit_pass") for r in rows)  # with no pass on record, a decline can't be shown harmless
    better = any_pass and new_score["mean_reward"] >= old_score["mean_reward"] + MARGIN and new_score["declined_failed"] - old_score["declined_failed"] >= 2
    budgets_only_safe = not words_changed and new_score["would_cut_passed"] == 0 and new_score["mean_reward"] >= old_score["mean_reward"]  # a budget saves nothing on a held-out answer; it must simply cut none
    if not (better or budgets_only_safe) or new_score["declined_passed"] > old_score["declined_passed"] + 1:
        outcome["event"] = "proposal_refused_on_held_out"
        store.append("tuner.jsonl", outcome)
        return outcome
    version = store.new_version({**cand, "parent": active["version"], "made_by": "tuner.py", "changes": changes, "held_out_old": old_score, "held_out_new": new_score, "trained_on": len(train)})
    st["canary"] = {"version": version, "share_pct": SHARE_PCT, "since": store.now(), "changes_key": key}
    st["history"].append({"at": store.now(), "event": "canary_started", "version": version, "changes": changes})
    store.save_state(st)
    outcome.update(event="canary_started", version=version)
    store.append("tuner.jsonl", outcome)
    return outcome


def restore(version: int) -> None:
    st = store.state()
    store.table(version)
    st["history"].append({"at": store.now(), "event": "restored", "version": version, "from": st["active"]})
    st["active"], st["canary"] = version, None
    store.save_state(st)


def learning_examples() -> list[dict[str, Any]]:
    """Real Tasks decided differently because of something recorded earlier: by a learned table, or by close past Tasks."""
    out, tables = [], {v: store.table(v) for v in store.versions()}
    for r in store.read("outcomes.jsonl"):
        d = r.get("decision") or {}
        if r.get("arm") != "sized" or d.get("explored_from"):
            continue  # a control or a random try isn't learning
        fired = d.get("rules_fired") or []
        if any(x.startswith("similar_tasks") for x in fired):
            out.append({"how": "close past Tasks", "task_id": r["task_id"], "at": r.get("at"), "size": d.get("size"), "why": d.get("why"), "similar": d.get("similar")})
            continue
        version = d.get("table_version") or 1
        if str(tables.get(version, {}).get("made_by") or "").startswith("tuner"):
            first = sizer.size_task(_task_from(r), {}, tables[1])
            if first["size"] != d.get("size") or first["budget"] != d.get("budget"):
                out.append({"how": "learned table", "task_id": r["task_id"], "at": r.get("at"), "table": version, "table_1_said": {"size": first["size"], "budget": first["budget"]}, "this_table_said": {"size": d.get("size"), "budget": d.get("budget")}, "why": d.get("why"), "changes": tables[version].get("changes")})
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["step"]:
        print(json.dumps(step("by-hand"), indent=1))
    elif sys.argv[1:2] == ["restore"]:
        restore(int(sys.argv[2]))
    elif sys.argv[1:2] == ["examples"]:
        print(json.dumps(learning_examples(), indent=1))
