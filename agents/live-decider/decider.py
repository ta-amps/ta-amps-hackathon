"""Teleion Fabric decider, the batch half.

For about 15% of real ready build Tasks (by a hash of the Task id), the fine-tuned Glimmer picks a reusable Task Object or
says nothing fits. Muse Spark, a different model with no fine-tune, audits each answer. Only an answer that passes the audit
becomes a route, which the warm agent gives its maker when it claims that Task. Any failure means no route: today's behavior.
If the rolling audit pass rate falls below the canary floor, routes switch off and no GPU runs until a person restores them.

  decider.py --gpu [--max N] [--controls N]   one batch
  decider.py --publish                        refresh the public record from local records (no model call)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "agents/warm-server-agent/src"), str(REPO / "omninode")]

SHIM = os.environ.get("DECIDER_SHIM_URL", "https://shim.teleionlabs.com")
STATE = Path.home() / ".local/state/eranos-worker"
ROUTES = STATE / "fabric-decider-routes.json"
WARM_LOG = STATE / "warm-agent.jsonl"
DECISIONS = HERE.parent / "records/decisions.jsonl"
RUNS = HERE.parent / "records/runs.jsonl"
SPEND = HERE.parent / "spend.jsonl"
HOLDOUT = Path(os.environ.get("DECIDER_HOLDOUT", "/nonexistent"))
MODAL_PY = Path(os.environ.get("DECIDER_MODAL_PYTHON", sys.executable))
MODAL_CLI = Path(os.environ.get("DECIDER_MODAL_CLI", "modal"))
SEARCHES = HERE.parent / "records/search-orders.jsonl"
SHARE_PCT = 15
GLIMMER_ROUTE = "fine_tuned_glimmer_30b_modal_batch"
BUDGET_USD, STOP_USD = 10.0, 9.0
WINDOW, FLOOR = 12, 0.70  # warm_agent_grid canary_policy: rolling_window_size, rollback_pass_rate_floor
H100_S = 0.001097 + 4 * 0.0000131 + 48 * 0.00000222
ADAPTER_SHA = "72da3894ee2906b1d8132d55e4ac95110283c8b86696efa9d349adb7b8b0cdd7"
SYSTEM = ("Role: search and retrieval. You choose Task Objects from a library for a plain-language need.\n"
          "You get the need and a numbered list of candidate Task Objects. Each candidate shows its id, title, what it does, "
          "what it takes in and what it gives back.\nReply with exactly one JSON object and nothing else: "
          '{"ranked": [<up to 5 candidate ids, best fit first>]}.\nRank by fit to the need: the job it does, its inputs and '
          'its outputs. Use only ids from the list. If no candidate fits the need, reply {"ranked": []}.')
MODEL_RECORD = {
    "base": "Muse Glimmer 30B (meta-models/Muse-Glimmer-30B, revision a4e59da5)",
    "fine_tune": "rank-16 LoRA, none-fix, adapter weights private",
    "adapter_sha256": ADAPTER_SHA,
    "training_data": "1,762 rows, orchestrator-v1, gold labels from our records and rule code, none from a model",
    "training_cost_usd": 3.46,
    "held_out_tests": {"top_pick_hit_at_1_of_175": 0.886, "says_nothing_fits_of_153": 0.837, "base_top_pick_hit_at_1": 0.017},
    "held_out_condition": "Task Objects from our seed-pack catalog, Nov 2, 2026. Real Fabric Tasks are a different mix; the live audit below is the only measure on them.",
    "serving": "One H100 on demand in a batch, Modal, scales to zero. Not a always-on endpoint.",
    "live_rule": f"About {SHARE_PCT}% of ready build Tasks. Muse Spark audits each answer. Below {FLOOR:.0%} audit pass over the last {WINDOW}, routes switch off.",
}


# pure helpers -------------------------------------------------------------------------------------------------------
def in_share(task_id: str, pct: int = SHARE_PCT) -> bool:
    return int(hashlib.sha256(task_id.encode()).hexdigest(), 16) % 100 < pct


def candidates_from_search(results: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    out = []
    for r in results:
        if r.get("artifact_kind") == "task_object" and r.get("id"):
            out.append({"id": str(r["id"]), "title": str(r.get("title") or "")[:100], "summary": " ".join(str(r.get("summary") or "").split())[:260]})
        if len(out) == limit:
            break
    return out


def need_text(task: dict[str, Any], scrub: Any = lambda s: s) -> str:
    text = f"{task.get('title') or ''}. {task.get('prompt') or task.get('description') or ''}"
    return scrub(" ".join(text.split()))[:900]


def build_messages(task: dict[str, Any], cands: list[dict[str, str]], scrub: Any = lambda s: s) -> list[dict[str, str]]:
    lines = [f"{i}. {c['id']} | {c['title']}. {c['summary']}" for i, c in enumerate(cands, 1)]
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Need: {need_text(task, scrub)}\n\nCandidates:\n" + "\n".join(lines)}]


def parse_answer(text: Any, cands: list[dict[str, str]]) -> dict[str, Any]:
    """route, no_fit or invalid. An id outside the list is invalid: the model never chooses outside what it was shown."""
    if not isinstance(text, str):
        return {"outcome": "invalid", "why": "no_text"}
    m = re.search(r"\{.*\}", text, re.S)
    try:
        ranked = json.loads(m.group(0) if m else text)["ranked"]
    except (ValueError, KeyError, TypeError):
        return {"outcome": "invalid", "why": "not_json"}
    if not isinstance(ranked, list):
        return {"outcome": "invalid", "why": "not_a_list"}
    if not ranked:
        return {"outcome": "no_fit"}
    known = {c["id"] for c in cands}
    if not all(isinstance(x, str) and x in known for x in ranked):
        return {"outcome": "invalid", "why": "id_not_in_list"}
    return {"outcome": "route", "object_id": ranked[0], "ranked": ranked[:5]}


def rolling_pass(rows: list[dict[str, Any]], window: int = WINDOW) -> float | None:
    """Pass rate of the last audited decisions; a Spark outage is not counted against the model."""
    seen = [r["audit_pass"] for r in rows if isinstance(r.get("audit_pass"), bool)][-window:]
    return sum(seen) / len(seen) if seen else None


def routes_stay_on(rows: list[dict[str, Any]], window: int = WINDOW, floor: float = FLOOR) -> bool:
    seen = [r["audit_pass"] for r in rows if isinstance(r.get("audit_pass"), bool)][-window:]
    return len(seen) < window or sum(seen) / len(seen) >= floor


def spent(path: Path = SPEND) -> float:
    """Each row's usd, with a reservation counted until its settle row replaces it. Same ledger and lock as the live half."""
    from warm_agent.decider import _total

    return round(_total(path.read_text()), 4) if path.exists() else 0.0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def write_routes(active: bool, routes: dict[str, Any], why: str = "") -> None:
    ROUTES.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ROUTES.parent, prefix=".routes")
    with os.fdopen(fd, "w") as f:
        json.dump({"active": active, "why": why, "routes": routes, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f)
    os.replace(tmp, ROUTES)


def billed_usd() -> float | None:
    try:
        o = subprocess.run([str(MODAL_CLI), "billing", "summary"], capture_output=True, text=True, timeout=60,
                           env={**os.environ, "MODAL_PROFILE": "teleionlabs"}).stdout
        m = re.search(r"Billed Cost:\s+\$?([\d.,]+)", o)
        return float(m[1].replace(",", "")) if m else None
    except (OSError, subprocess.SubprocessError):
        return None


# live steps ---------------------------------------------------------------------------------------------------------
def ready_tasks(http: httpx.Client) -> tuple[int, list[dict[str, Any]]]:
    tasks: list[dict[str, Any]] = []
    total = 0
    for offset in range(0, 1000, 200):
        d = http.get("/q/tasks", params={"state": "ready", "step_mode": "atomic_build_step", "limit": 200, "offset": offset}).json()
        total = int(d.get("total_matching") or 0)
        tasks += d.get("tasks") or []
        if offset + 200 >= total:
            break
    return total, tasks


def audit(client: Any, task: dict[str, Any], cands: list[dict[str, str]], parsed: dict[str, Any], scrub: Any) -> dict[str, Any]:
    """Muse Spark, no fine-tune, a different model from the one it checks. Failure leaves audit_pass None and no route."""
    from warm_agent.decider import SpendRefused, reserve, settle

    hold, usd, rid = 0.02, 0.0, None
    try:
        rid = reserve(SPEND, hold, STOP_USD, "Muse Spark audit")
    except SpendRefused as exc:
        return {"audit_pass": None, "audit_error": f"refused_budget_{exc}", "audit_usd": 0.0}
    if parsed["outcome"] == "route":
        chosen = next(c for c in cands if c["id"] == parsed["object_id"])
        ask = f"Need: {need_text(task, scrub)}\n\nChosen Task Object: {chosen['id']} | {chosen['title']}. {chosen['summary']}\n\nWould this Task Object help a worker doing this need? Reply as JSON: {{\"pass\": true or false, \"why\": \"under 15 words\"}}."
    else:
        listed = "\n".join(f"- {c['id']} | {c['title']}. {c['summary']}" for c in cands)
        ask = f"Need: {need_text(task, scrub)}\n\nA router said none of these Task Objects fits:\n{listed}\n\nIs that right, so none would clearly help a worker doing this need? Reply as JSON: {{\"pass\": true or false, \"why\": \"under 15 words\"}}."
    try:
        res = client.complete(model_id="muse-spark-1.3", system_prompt="You audit routing decisions. Answer plainly and strictly.",
                              user_prompt=ask, json_object=True, temperature=0.0, caller_tag="fabric_decider_audit")
        usd = float(res.get("cost_usd") or 0)
        body = json.loads(str(res["content"]))
        if not isinstance(body.get("pass"), bool):
            raise ValueError("no pass field")
        settle(SPEND, rid, usd, "Muse Spark audit")
        rid = None
        return {"audit_pass": body["pass"], "audit_why": scrub(str(body.get("why") or ""))[:160], "audit_usd": usd}
    except Exception as exc:  # noqa: BLE001 - an audit failure only means no route
        if rid is not None:
            settle(SPEND, rid, usd if usd else hold, "Muse Spark audit, no usable answer")
        return {"audit_pass": None, "audit_error": type(exc).__name__, "audit_usd": usd}


def _record_audit_attempt(row: dict[str, Any]) -> None:
    with DECISIONS.parent.joinpath("audit-attempts.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


def run_gpu(max_tasks: int, controls: int) -> int:
    from warm_agent.banned_words_guard import scrub_private_info
    from warm_agent.decider import looks_secret
    from warm_agent.grid_config import load_warm_agent_grid
    from warm_agent.meta_client import WarmMetaModelClient

    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    history = read_jsonl(DECISIONS)
    if not routes_stay_on(history):
        write_routes(False, {}, f"audit pass below {FLOOR:.0%} over the last {WINDOW}")
        print(json.dumps({"run": run_id, "skipped": "rolled_back"}))
        return 0
    billed = billed_usd()
    if billed is None or billed > 0:
        print(json.dumps({"run": run_id, "skipped": "teleionlabs_billing_guard", "billed": billed}))
        return 0
    http = httpx.Client(base_url=SHIM, timeout=45, trust_env=False, headers={"User-Agent": "teleion-fabric-decider/1"})
    total, tasks = ready_tasks(http)
    done = {r.get("task_id") for r in history}
    picks = [t for t in tasks if in_share(str(t["task_id"])) and t["task_id"] not in done]
    in_share_count = sum(in_share(str(t["task_id"])) for t in tasks)
    # Tasks with their own content first: "index this object" Tasks give a search little to go on.
    picks.sort(key=lambda t: (str(t["task_id"]).startswith("verb_index_enrich_"), -int(t.get("priority") or 0)))
    picks = picks[:max_tasks]
    rows, ctx = [], {}
    for t in picks:
        title = str(t.get("title") or "")[:120]
        if looks_secret(title):  # a credential never goes into a request
            cands = []
        else:
            r = http.post("/q/search", json={"q": title, "limit": 30})
            cands = candidates_from_search(r.json().get("results") or []) if r.status_code == 200 else []
        cands = [c for c in cands if c["id"] != t["task_id"] and not looks_secret(f"{c['id']} {c['title']} {c['summary']}")]
        if len(cands) < 2:
            ctx[t["task_id"]] = (t, cands)
            continue
        ctx[t["task_id"]] = (t, cands)
        rows.append({"id": t["task_id"], "messages": build_messages(t, cands, scrub_private_info)})
    ctrl: dict[str, dict] = {}
    if controls:
        for line in HOLDOUT.read_text().splitlines()[:controls]:
            r = json.loads(line)
            ctrl[r["id"]] = r["meta"]
            rows.append({"id": r["id"], "messages": r["messages"][:2]})
    if not rows:
        print(json.dumps({"run": run_id, "skipped": "nothing_to_decide", "ready": total}))
        return 0
    worst = round(600 * H100_S, 4)
    if spent() + worst > STOP_USD:
        print(json.dumps({"run": run_id, "skipped": "budget", "spent": spent()}))
        return 0
    from warm_agent.decider import reserve, settle

    try:
        gpu_rid = reserve(SPEND, worst, STOP_USD, f"H100 batch worst case, {len(rows)} rows, modal teleionlabs")
    except Exception as exc:  # noqa: BLE001 - no ledger, no GPU
        print(json.dumps({"run": run_id, "skipped": "spend_ledger", "error": type(exc).__name__}))
        return 0
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.json", Path(td) / "out.json"
        src.write_text(json.dumps({"rows": rows, "max_new": 128, "time_budget_s": 480.0}))
        t_gpu, result, failure = time.time(), None, None
        try:
            p = subprocess.run([str(MODAL_PY), str(HERE.parent / "modal_decider.py"), str(src), str(dst)], capture_output=True, text=True,
                               timeout=900, env={**os.environ, "MODAL_PROFILE": "teleionlabs", "PYTHONDONTWRITEBYTECODE": "1"})
            failure = f"exit_{p.returncode}" if p.returncode != 0 or not dst.exists() else None
            if failure is None:
                result = json.loads(dst.read_text())
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            failure = type(exc).__name__
        if failure is not None:
            usd = round(min(worst, (time.time() - t_gpu) * H100_S), 4)  # at most this long at list price
            settle(SPEND, gpu_rid, usd, f"batch failed ({failure}), elapsed time at list price")
            with RUNS.open("a") as f:  # the Tasks it held, and no raw error text
                f.write(json.dumps({"run": run_id, "failed": True, "why": failure, "attempted_ids": [r["id"] for r in rows]}) + "\n")
            print(json.dumps({"run": run_id, "failed": True, "why": failure}))
            return 1
    with DECISIONS.parent.joinpath("gpu-answers.jsonl").open("a") as f:  # on disk before any audit starts
        for r in result["rows"]:
            f.write(json.dumps({"run": run_id, **r}) + "\n")
    gpu_usd = round(max(float(result["client_wall_s"]), float(result["wall_s"])) * H100_S, 4)
    settle(SPEND, gpu_rid, gpu_usd, f"H100 {result['client_wall_s']} s at list price, estimate")
    client = WarmMetaModelClient(load_warm_agent_grid(None), attempt_recorder=_record_audit_attempt)
    answers = {r["id"]: r for r in result["rows"]}
    control_rows = []
    for cid, meta in ctrl.items():
        a = answers.get(cid) or {}
        parsed = parse_answer(a.get("text"), [{"id": c} for c in meta["candidate_ids"]])
        control_rows.append({"id": cid, "gold": meta["gold_id"], "got": parsed.get("object_id"), "correct": parsed.get("object_id") == meta["gold_id"], "seconds": a.get("seconds")})
    previous = json.loads(ROUTES.read_text()).get("routes", {}) if ROUTES.exists() else {}
    routes, new_rows, audit_usd = dict(previous), [], 0.0
    for task_id, (t, cands) in ctx.items():
        a = answers.get(task_id)
        row: dict[str, Any] = {"run": run_id, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "task_id": task_id, "priority": t.get("priority"),
                               "verb_kind": t.get("verb_kind"), "candidates": [c["id"] for c in cands]}
        if a is None:
            row.update(outcome="no_candidates", fallback=True)
        elif a.get("error"):
            row.update(outcome="failed", error=str(a["error"]).split(":")[0], fallback=True)
        else:
            parsed = parse_answer(a.get("text"), cands)
            row.update(parsed, seconds=a.get("seconds"), prompt_tokens=a.get("prompt_tokens"), completion_tokens=a.get("completion_tokens"))
            if parsed["outcome"] == "invalid":
                row.update(fallback=True, audit_pass=False, failed_validation=True)
            else:
                row.update(audit(client, t, cands, parsed, scrub_private_info))
                audit_usd += float(row.get("audit_usd") or 0)
                row["fallback"] = parsed["outcome"] != "route" or row.get("audit_pass") is not True
                if not row["fallback"]:
                    chosen = next(c for c in cands if c["id"] == parsed["object_id"])
                    routes[task_id] = {"object_id": chosen["id"], "title": chosen["title"], "summary": chosen["summary"], "run": run_id, "adapter_sha256": ADAPTER_SHA}
        new_rows.append(row)
        with DECISIONS.open("a") as f:
            f.write(json.dumps(row) + "\n")
    on = routes_stay_on(history + new_rows)
    write_routes(on, routes if on else {}, "" if on else f"audit pass below {FLOOR:.0%} over the last {WINDOW}")
    summary = {"run": run_id, "ready_build_tasks": total, "listed": len(tasks), "in_share_listed": in_share_count, "attempted": len(new_rows),
               "load_s": result["load_s"], "wall_s": result["wall_s"], "gpu_usd_estimate": gpu_usd, "audit_usd": round(audit_usd, 6), "controls": control_rows, "routes_active": on}
    with RUNS.open("a") as f:
        f.write(json.dumps(summary) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "controls"}), "controls_correct", sum(c["correct"] for c in control_rows), "of", len(control_rows))
    return 0


def run_search(n: int) -> int:
    """Real searches agents made (the shim's own demand list): the fine-tuned model reorders the candidates, Muse Spark audits the
    new first pick, and the order goes on the public record. The live search order itself doesn't change."""
    from warm_agent.banned_words_guard import scrub_private_info
    from warm_agent.decider import looks_secret, reserve, settle
    from warm_agent.grid_config import load_warm_agent_grid
    from warm_agent.meta_client import WarmMetaModelClient

    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    billed = billed_usd()
    if billed is None or billed > 0:
        print(json.dumps({"run": run_id, "skipped": "teleionlabs_billing_guard", "billed": billed}))
        return 0
    http = httpx.Client(base_url=SHIM, timeout=45, trust_env=False, headers={"User-Agent": "teleion-fabric-decider/1"})
    signals = http.get("/q/demand").json().get("live_demand_signals") or []
    seen = {r.get("query") for r in read_jsonl(SEARCHES)}
    rows, ctx = [], {}
    for sig in sorted(signals, key=lambda x: -int(x.get("query_count") or 0)):
        q = str(sig.get("raw_sample_query") or "")[:120]
        if not q or q in seen or looks_secret(q) or len(rows) >= n:
            continue
        cands = candidates_from_search(http.post("/q/search", json={"q": q, "limit": 30}).json().get("results") or [])
        cands = [c for c in cands if not looks_secret(f"{c['id']} {c['title']} {c['summary']}")]
        if len(cands) < 2:
            continue
        rid = f"search-{len(rows)}"
        ctx[rid] = (q, cands, sig.get("query_count"))
        rows.append({"id": rid, "messages": build_messages({"title": q}, cands, scrub_private_info)})
    if not rows:
        print(json.dumps({"run": run_id, "skipped": "nothing_to_reorder"}))
        return 0
    worst = round(600 * H100_S, 4)
    try:
        gpu_rid = reserve(SPEND, worst, STOP_USD, f"H100 search batch worst case, {len(rows)} rows, modal teleionlabs")
    except Exception as exc:  # noqa: BLE001 - no ledger, no GPU
        print(json.dumps({"run": run_id, "skipped": "spend_ledger", "error": type(exc).__name__}))
        return 0
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.json", Path(td) / "out.json"
        src.write_text(json.dumps({"rows": rows, "max_new": 128, "time_budget_s": 300.0}))
        t_gpu, result, failure = time.time(), None, None
        try:
            p = subprocess.run([str(MODAL_PY), str(HERE.parent / "modal_decider.py"), str(src), str(dst)], capture_output=True, text=True,
                               timeout=700, env={**os.environ, "MODAL_PROFILE": "teleionlabs", "PYTHONDONTWRITEBYTECODE": "1"})
            failure = f"exit_{p.returncode}" if p.returncode != 0 or not dst.exists() else None
            if failure is None:
                result = json.loads(dst.read_text())
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            failure = type(exc).__name__
        if failure is not None:
            settle(SPEND, gpu_rid, round(min(worst, (time.time() - t_gpu) * H100_S), 4), f"search batch failed ({failure}), elapsed time at list price")
            with RUNS.open("a") as f:
                f.write(json.dumps({"run": run_id, "kind": "search", "failed": True, "why": failure, "attempted_queries": [c[0] for c in ctx.values()]}) + "\n")
            print(json.dumps({"run": run_id, "failed": True, "why": failure}))
            return 1
    gpu_usd = round(max(float(result["client_wall_s"]), float(result["wall_s"])) * H100_S, 4)
    settle(SPEND, gpu_rid, gpu_usd, f"H100 search batch {result['client_wall_s']} s at list price, estimate")
    client = WarmMetaModelClient(load_warm_agent_grid(None), attempt_recorder=_record_audit_attempt)
    answers = {r["id"]: r for r in result["rows"]}
    for rid, (q, cands, count) in ctx.items():
        a = answers.get(rid) or {}
        parsed = parse_answer(a.get("text"), cands) if not a.get("error") else {"outcome": "failed"}
        row = {"run": run_id, "query": q, "query_count": count, "search_order": [c["id"] for c in cands], "seconds": a.get("seconds"), **parsed}
        row["moved"] = parsed.get("outcome") == "route" and parsed.get("object_id") != cands[0]["id"]
        if parsed["outcome"] in {"route", "no_fit"}:
            row.update(audit(client, {"title": q}, cands, parsed, scrub_private_info))
        with SEARCHES.open("a") as f:
            f.write(json.dumps(row) + "\n")
    with RUNS.open("a") as f:
        f.write(json.dumps({"run": run_id, "kind": "search", "attempted": len(ctx), "load_s": result["load_s"], "wall_s": result["wall_s"], "search_gpu_usd_estimate": gpu_usd}) + "\n")
    print(json.dumps({"run": run_id, "kind": "search", "attempted": len(ctx), "gpu_usd_estimate": gpu_usd}))
    return 0


def tally() -> dict[str, Any]:
    rows, runs = read_jsonl(DECISIONS), read_jsonl(RUNS)
    outcomes: dict[str, int] = {}
    for r in rows:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    answered = [r for r in rows if r.get("seconds")]
    ran = [r for r in rows if r.get("outcome") in {"route", "no_fit", "invalid", "failed"}]
    effects = [r for r in read_jsonl(WARM_LOG) if r.get("kind") == "fabric_decision_effect"]
    secs = sorted(float(r["seconds"]) for r in answered)
    events = [r for r in read_jsonl(WARM_LOG) if r.get("kind") == "fabric_decision"]
    chosen: dict[str, int] = {}
    route_stats: dict[str, dict[str, Any]] = {}
    for e in events:
        chosen[e.get("model", "?")] = chosen.get(e.get("model", "?"), 0) + 1
        for a in e.get("attempts") or []:
            st = route_stats.setdefault(a.get("route", "?"), {"answered": 0, "other_outcomes": {}, "seconds": [], "cost_usd": 0.0})
            if a.get("outcome") == "answered":
                st["answered"] += 1
            else:
                st["other_outcomes"][a.get("outcome", "?")] = st["other_outcomes"].get(a.get("outcome", "?"), 0) + 1
            if a.get("seconds") is not None:
                st["seconds"].append(a["seconds"])
            st["cost_usd"] = round(st["cost_usd"] + float(a.get("cost_usd") or 0), 6)
    for st in route_stats.values():
        secs_r = sorted(st.pop("seconds"))
        st["median_seconds"] = secs_r[len(secs_r) // 2] if secs_r else None
    good_runs = [r for r in runs if not r.get("failed") and r.get("kind") != "search"]
    searches = read_jsonl(SEARCHES)
    tools = [r for r in read_jsonl(WARM_LOG) if r.get("kind") == "fabric_tool_call"]
    moved_up = [r for r in read_jsonl(WARM_LOG) if r.get("kind") == "fabric_moved_up"]
    effect_routes: dict[str, int] = {}
    for e in effects:
        if e.get("object_route"):
            effect_routes[e["object_route"]] = effect_routes.get(e["object_route"], 0) + 1
    audited = [r for r in rows if isinstance(r.get("audit_pass"), bool) and not r.get("failed_validation")]
    return {
        "fine_tuned_decider": {
            "model": MODEL_RECORD,
            "real_tasks_sent_to_the_model": len(ran), "model_answered": len(answered), "tasks_with_too_few_candidates_not_sent": outcomes.get("no_candidates", 0), "outcomes": outcomes, "fell_back_to_todays_behavior": sum(1 for r in rows if r.get("fallback")),
            "audited": len(audited), "audit_passed": sum(1 for r in audited if r["audit_pass"]),
            "audit_pass_last_12": rolling_pass(rows), "routes_active": routes_stay_on(rows),
            "median_seconds_per_decision_on_gpu": secs[len(secs) // 2] if secs else None,
            "batches": len(good_runs), "failed_batches": sum(1 for r in runs if r.get("failed")),
            "load_seconds": [r.get("load_s") for r in good_runs], "gpu_usd_estimate_list_price": round(sum(float(r.get("gpu_usd_estimate") or 0) for r in good_runs), 4),
            "ready_build_tasks_last_seen": good_runs[-1].get("ready_build_tasks") if good_runs else None,
            "routes_passed_audit": sum(1 for r in rows if r.get("outcome") == "route" and r.get("audit_pass") is True),
            "fine_tuned_picks_given_to_a_live_maker": sum(1 for e in effects if e.get("object_route") == GLIMMER_ROUTE),
            "held_out_controls": [c for r in good_runs for c in r.get("controls") or []][:12],
            "latest": [{k: r.get(k) for k in ("task_id", "outcome", "object_id", "audit_pass", "seconds")} for r in rows[-30:]],
        },
        "live_route_list": {
            "where": "The always-on warm agent, each real build Task it claims. Order: fine-tuned batch answer, Meta open model through partner credits, Muse Spark through the Meta API, then the rule.", "decisions": len(events), "models_chosen": chosen,
            "decided_by_a_model": sum(1 for e in events if not e.get("fallback")), "fell_back_to_the_rule": sum(1 for e in events if e.get("fallback")),
            "routes": route_stats, "task_object_given_to_a_maker_by_route": effect_routes, "maker_runs_after_a_decision": len(effects),
            "latest": [{k: e.get(k) for k in ("at", "task_id", "model", "model_route", "object_route", "route_object_id", "fallback", "seconds")} for e in events[-20:]],
        },
        "search_reorder": {
            "what": "Real searches from the shim's demand list. The fine-tuned model reorders the candidates and Muse Spark audits the new first pick. The order is on this record; the live search order is unchanged.",
            "queries": len(searches), "first_pick_changed": sum(1 for r in searches if r.get("moved")), "said_nothing_fits": sum(1 for r in searches if r.get("outcome") == "no_fit"),
            "audited": sum(1 for r in searches if isinstance(r.get("audit_pass"), bool)), "audit_passed": sum(1 for r in searches if r.get("audit_pass") is True),
            "latest": [{k: r.get(k) for k in ("query", "object_id", "moved", "audit_pass", "seconds")} for r in searches[-15:]],
        },
        "tool_calls": {
            "what": "The warm agent reads a Task Object for its worker. Plain code first: when the Task names one. A model can ask for one too.",
            "calls": len(tools), "worked": sum(1 for t in tools if t.get("ok")), "chosen_by": {k: sum(1 for t in tools if t.get("chosen_by") == k) for k in {t.get("chosen_by") for t in tools}},
        },
        "moved_up_the_cost_ladder": {"what": "Muse Spark's answer couldn't be read, so Muse Wonder tried once.", "times": len(moved_up), "readable_after": sum(1 for r in moved_up if r.get("readable"))},
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def publish() -> int:
    record_key = os.environ.get("DECIDER_RECORD_KEY", "").strip()
    if not record_key:  # no default: a copy of this code must not write to anyone's existing record by accident
        print("set DECIDER_RECORD_KEY to your own record key to publish", file=sys.stderr)
        return 2
    from omninode_live.shim import Shim
    from warm_agent.banned_words_guard import BannedWordsGuard
    from warm_agent.grid_config import load_warm_agent_grid

    body = tally()
    guard = BannedWordsGuard(load_warm_agent_grid(None).section("endpoints_and_paths")["banned_words_path"])
    if guard.scan_text(json.dumps(body)):  # a Task id or a reason trips the word list: counts only
        body["fine_tuned_decider"].pop("latest", None)
        body["live_route_list"].pop("latest", None)
        body["search_reorder"].pop("latest", None)
    f, m = body["fine_tuned_decider"], body["live_route_list"]
    summary = (f"Live record of Teleion Fabric's Meta-based deciding. Fine-tuned Muse Glimmer 30B answered on {f['model_answered']} real Tasks in "
               f"{f['batches']} batches; {f['audit_passed']} of {f['audited']} answers passed a Muse Spark audit; {f['fine_tuned_picks_given_to_a_live_maker']} of its picks reached a live worker so far. Live route list: {m['decisions']} real Tasks.")
    shim = Shim("fabric-decider", Path.home() / ".config/ta-amps/fabric-decider-identity.json")
    res = shim.publish({record_key: {"summary": summary, "category": "live_record", "search_hints": ["decider", "fine-tuned", "muse glimmer", "muse spark", "routing"], "payload": body}},
                       summary, f"fabric-decider-{int(time.time() // 900)}")
    print(json.dumps({"published": res, "summary": summary}))
    return 0 if res["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--controls", type=int, default=0)
    ap.add_argument("--search", type=int, default=0)
    a = ap.parse_args()
    rc = run_gpu(a.max, a.controls) if a.gpu else 0
    if a.search:
        rc = run_search(a.search) or rc
    if a.publish:
        rc = publish() or rc
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
