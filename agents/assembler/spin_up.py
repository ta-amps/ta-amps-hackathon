"""spin_up: an agent assembled for one Task from how the Task looks and what worked for Tasks that looked like it.

  fingerprint(task) -> nearest earlier Tasks with scores -> what worked for them, from recorded outcomes -> an assembly:
  harness, model, tools, skills (Task Objects, seed packs), rules, budget. The assembly is recorded with its fingerprint and outcome;
  outcomes feed the lookup. No neighbors or too few outcomes: the default assembly for the Task's needs. assemble() calls no model.
"""
from __future__ import annotations

import collections
import json
import os
import re
from pathlib import Path
from typing import Any

import fp

HERE = Path(__file__).resolve().parent
MEMORY = HERE / "records/memory.jsonl"
SPARK, WONDER = "muse-spark-1.3-contributor", "muse-wonder-1.0"
FUZZY = os.environ.get("ASSEMBLER_FUZZY", "1") == "1"  # set from records/fingerprint_test.json; see RESULTS
FLOOR = float(os.environ.get("ASSEMBLER_FLOOR", "0.72"))
MIN_OUTCOMES = 3
SWITCH_MARGIN = 0.15
TOOLS = {"plain": [], "read": ["read"], "web": ["read", "write", "webfetch"], "code": ["read", "write", "edit", "bash"], "code_web": ["read", "write", "edit", "bash", "webfetch"]}
BUDGET_USD = {"opencode": {SPARK: 0.25, WONDER: 2.0}, "codex": {SPARK: 0.5, WONDER: 2.0}, "json_answer": {SPARK: 0.05, WONDER: 0.4}, "shape_runner": {WONDER: 2.5}}


def load_memory(path: Path = MEMORY) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def remember(row: dict[str, Any], path: Path = MEMORY) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


def lookup(fingerprint: dict[str, Any], memory: list[dict[str, Any]], floor: float = FLOOR) -> dict[str, Any]:
    """What worked for similar fingerprints: score-weighted pass rates by harness and model, and how often neighbors needed people."""
    near = [n for n in fp.neighbors(fingerprint, [r for r in memory if r.get("outcome")], k=30, floor=floor)] if FUZZY else []
    combos: dict[str, dict[str, float]] = collections.defaultdict(lambda: {"n": 0, "w": 0.0, "pass": 0.0, "usd": 0.0})
    people_w = total_w = 0.0
    for n in near:
        out, asm = n["row"]["outcome"], n["row"]["assembly"]
        total_w += n["score"]
        people_w += n["score"] * float(bool(out.get("needs_people")))
        if out.get("pass") is None:
            continue
        c = combos[f"{asm['harness']}|{asm.get('model')}"]
        c["n"] += 1
        c["w"] += n["score"]
        c["pass"] += n["score"] * float(bool(out["pass"]))
        c["usd"] += float(out.get("usd") or 0)
    table = {k: {"n": int(v["n"]), "pass_rate": round(v["pass"] / v["w"], 3), "mean_usd": round(v["usd"] / v["n"], 4)} for k, v in combos.items() if v["w"]}
    return {"neighbors": [{"task_id": n["row"].get("task_id"), "score": n["score"], "harness": n["row"]["assembly"]["harness"], "model": n["row"]["assembly"].get("model"),
                           "pass": n["row"]["outcome"].get("pass"), "source": n["row"].get("source")} for n in near[:8]],
            "n_neighbors": len(near), "by_assembly": table, "people_share": round(people_w / total_w, 3) if total_w else 0.0}


def default_harness(f: dict[str, Any]) -> tuple[str, str, str | None]:
    """(harness, tool set, handler), from the Task's needs alone."""
    needs = set(f["needs"])
    if f["category"] == "distributed_index_enrichment":
        return "deterministic_only", "plain", "client_index"
    if f["category"] == "version_propagation_recheck":
        return "shape_runner", "plain", None
    if "run_code" in needs:
        return "opencode", "code_web" if needs & {"read_url", "sources"} else "code", None
    if needs & {"read_url", "sources"}:
        return "opencode", "web", None
    return "json_answer", "plain", None


def rules_for(f: dict[str, Any], text: str) -> list[str]:
    rules = ["screen_credentials_and_personal_data", "no_placeholder_text", "second_worker_reads_before_submit"]
    if f["output_shape"] == "code_and_tests" and "run_code" in f["needs"]:
        rules.append("tests_pass_when_rerun_by_the_runner")
    if re.search(r"\(C\d\)|claim id", text):
        rules.append("cites_claim_ids")
    if f["input_shape"]["urls"]:
        rules.append("only_named_sources_or_links_shown")
    if f["output_shape"] == "short_sheet":
        rules.append("short_output_under_1500_words")
    return rules


def named_objects(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_-]*_v\d+\b", text)))[:3]


def assemble(task: dict[str, Any], memory: list[dict[str, Any]], *, find: Any = None) -> dict[str, Any]:
    text = fp.text_of(task)
    f = fp.fingerprint(task)
    seen = lookup(f, memory)
    harness, toolset, handler = default_harness(f)
    model: str | None = None if harness == "deterministic_only" else (WONDER if harness == "shape_runner" or int(task.get("complexity_milli") or 0) >= 900 else SPARK)
    why = [f"default for needs {f['needs']}: {harness}"]
    changed_by: list[dict[str, Any]] = []
    # People or hardware: leave it open, no model. A rule on the words, or the neighbors' recorded outcomes.
    people_rule = "people_or_hardware" in f["needs"] and "run_code" not in f["needs"] and f["category"] != "eval_and_rank"  # a review reads a report about a trial; it needs no trial
    people_seen = seen["n_neighbors"] >= MIN_OUTCOMES and seen["people_share"] >= 0.6
    if harness != "deterministic_only" and (people_rule or people_seen):
        if people_seen and not people_rule:
            changed_by.append({"because": "neighbors needed people", "people_share": seen["people_share"], "neighbors": seen["neighbors"][:3]})
        why.append("needs people or hardware: " + ("words in the Task" if people_rule else f"{seen['people_share']} of neighbors"))
        harness, toolset, handler, model = "deterministic_only", "plain", "leave_open", None
    # What worked for similar Tasks moves the choice, if the evidence clears a small bar.
    if harness not in ("deterministic_only", "shape_runner") and seen["by_assembly"]:
        mine = seen["by_assembly"].get(f"{harness}|{model}")
        best = max((v["pass_rate"], -v["mean_usd"], k) for k, v in seen["by_assembly"].items() if v["n"] >= MIN_OUTCOMES and k.split("|")[0] in ("opencode", "json_answer", "codex")) if any(
            v["n"] >= MIN_OUTCOMES and k.split("|")[0] in ("opencode", "json_answer", "codex") for k, v in seen["by_assembly"].items()) else None
        if best and best[2] != f"{harness}|{model}" and best[0] >= (mine["pass_rate"] if mine and mine["n"] >= MIN_OUTCOMES else 0.0) + SWITCH_MARGIN:
            new_h, new_m = best[2].split("|")
            changed_by.append({"because": "similar Tasks did better", "from": f"{harness}|{model}", "to": best[2], "table": seen["by_assembly"], "neighbors": seen["neighbors"][:4]})
            why.append(f"neighbors: {best[2]} passed {best[0]} against {(mine or {}).get('pass_rate')}")
            harness, model = new_h, new_m if new_m != "None" else SPARK
            if toolset == "plain" and harness in ("opencode", "codex"):
                toolset = "web"
    skills: list[dict[str, Any]] = [{"kind": "task_object", "id": k, "why": "named in the Task"} for k in named_objects(text)]
    if find and harness in ("opencode", "codex", "json_answer"):
        for hit in find(str(task.get("title") or ""))[:3 - len(skills) if len(skills) < 3 else 0]:
            skills.append(hit)
    budget = {"usd": BUDGET_USD.get(harness, {}).get(model, 0.0), "wall_seconds": 360 if harness in ("opencode", "codex") else 240 if harness == "shape_runner" else 90}
    return {"schema": "teleion.assembly.v1", "task_id": task.get("task_id"), "fingerprint": f, "assembly": {"harness": harness, "model": model, "tools": TOOLS[toolset], "handler": handler,
            "skills": skills, "rules": rules_for(f, text), "budget": budget}, "similar": seen, "why": why, "changed_by_outcomes": changed_by, "fallback_default": not changed_by}
