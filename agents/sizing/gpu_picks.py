"""The fine-tune's small live share: picks a Task Object (or says nothing fits) for a hash-chosen share of the sized Tasks in one worker run.
One H100 on Modal teleionlabs, loaded once per run, answers before those Tasks are claimed. Any failure means the plain search picks stand.
Each answer is read by Muse Spark, which has no fine-tune and no share in its training data, before it counts. Every attempt is recorded.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIVE = REPO / "agents/live-decider"
sys.path[:0] = [str(HERE), str(LIVE), str(REPO / "agents/warm-server-agent/src")]

import decider as dec  # noqa: E402  (meta-live: messages, parsing, Modal paths, billing guard)
import sizer  # noqa: E402
import store  # noqa: E402
from warm_agent.decider import SpendRefused, reserve, settle  # noqa: E402

GPU_SPEND = HERE / "gpu-spend.jsonl"
GPU_STOP = float(os.environ.get("SIZING_GPU_STOP_USD", "4.5"))  # as in worker.py
FLOOR, WINDOW = 0.70, 12
SHARE = 30


def in_share(task_id: str) -> bool:
    return sizer.bucket(task_id, "fine-tune-share") < SHARE


def still_on() -> bool:
    """Switches back by itself: below the floor over the last answers read, and no GPU starts."""
    seen = [r["audit_pass"] for r in store.read("fine-tune.jsonl") if isinstance(r.get("audit_pass"), bool)][-WINDOW:]
    return len(seen) < WINDOW or sum(seen) / len(seen) >= FLOOR


def run_batch(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    worst = round(600 * dec.H100_S, 4)
    try:
        rid = reserve(GPU_SPEND, worst, GPU_STOP, f"H100 batch worst case, {len(rows)} rows, modal teleionlabs")
    except SpendRefused as exc:
        store.append("fine-tune.jsonl", {"event": "gpu_refused", "why": str(exc)})
        return None
    t0, result, failure = time.time(), None, None
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.json", Path(td) / "out.json"
        src.write_text(json.dumps({"rows": rows, "max_new": 128, "time_budget_s": 300.0}))
        try:
            p = subprocess.run([str(dec.MODAL_PY), str(LIVE / "modal_decider.py"), str(src), str(dst)], capture_output=True, text=True, timeout=600, env={**os.environ, "MODAL_PROFILE": "teleionlabs", "PYTHONDONTWRITEBYTECODE": "1"})
            failure = f"exit_{p.returncode}" if p.returncode != 0 or not dst.exists() else None
            if failure is None:
                result = json.loads(dst.read_text())
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            failure = type(exc).__name__
    usd = round(max(float((result or {}).get("client_wall_s") or 0), time.time() - t0 if failure else 0) * dec.H100_S, 4)
    settle(GPU_SPEND, rid, usd, f"H100 batch ({failure or 'answered'}), list price estimate")
    store.append("fine-tune.jsonl", {"event": "gpu_batch", "rows": len(rows), "failure": failure, "usd_estimate": usd, "load_s": (result or {}).get("load_s"), "wall_s": (result or {}).get("wall_s")})
    return result


def picks_for(tasks: list[dict[str, Any]], hits_by_task: dict[str, list[dict[str, Any]]], models: Any, run: str) -> dict[str, dict[str, Any]]:
    from warm_agent.banned_words_guard import scrub_private_info
    from warm_agent.decider import looks_secret

    if not still_on():
        store.append("fine-tune.jsonl", {"event": "switched_off", "why": f"read pass below {FLOOR:.0%} over the last {WINDOW}"})
        return {}
    billed = dec.billed_usd()
    if billed is None or billed > 0:
        store.append("fine-tune.jsonl", {"event": "skipped_billing_guard", "billed": billed})
        return {}
    rows, ctx = [], {}
    for t in tasks:
        cands = [{"id": h["id"], "title": h["title"][:100], "summary": h["summary"]} for h in hits_by_task.get(t["task_id"], []) if h["kind"] == "task_object" and not looks_secret(f"{h['id']} {h['title']} {h['summary']}")][:8]
        if len(cands) < 2:
            continue
        ctx[t["task_id"]] = (t, cands)
        rows.append({"id": t["task_id"], "messages": dec.build_messages(t, cands, scrub_private_info)})
    if not rows:
        return {}
    result = run_batch(rows)
    if result is None:
        return {}
    answers = {r["id"]: r for r in result.get("rows") or []}
    out: dict[str, dict[str, Any]] = {}
    for tid, (t, cands) in ctx.items():
        a = answers.get(tid) or {}
        parsed = dec.parse_answer(a.get("text"), cands)
        row: dict[str, Any] = {"event": "answer", "run": run, "task_id": tid, "outcome": parsed["outcome"], "object_id": parsed.get("object_id"), "seconds": a.get("seconds"), "error": a.get("error"), "candidates": [c["id"] for c in cands], "plain_top": cands[0]["id"], "adapter_sha256": dec.ADAPTER_SHA}
        if parsed["outcome"] in ("route", "no_fit"):
            listed = "\n".join(f"- {c['id']} | {c['title']}. {c['summary']}" for c in cands)
            ask = (f"Need: {dec.need_text(t, scrub_private_info)}\n\nCandidates:\n{listed}\n\nA router said: " + (f"{parsed['object_id']} helps most." if parsed["outcome"] == "route" else "none of these would clearly help.") +
                   ' Is that right? Reply as JSON: {"pass": true or false, "why": "under 15 words"}.')
            got = models.call(sizer.SMALL, "You audit routing decisions. Answer plainly and strictly.", ask, "sizing_fine_tune_audit")
            body = None
            if got.get("ok"):
                try:
                    body = json.loads(got["content"][got["content"].index("{"): got["content"].rindex("}") + 1])
                except ValueError:
                    body = None
            passed = body.get("pass") if isinstance(body, dict) and isinstance(body.get("pass"), bool) else None
            row.update(audit_pass=passed, audit_why=scrub_private_info(str((body or {}).get("why") or ""))[:160], audit_usd=got.get("usd", 0.0))
            if passed:
                out[tid] = {"route": "fine_tuned", "outcome": parsed["outcome"], "use_object": parsed.get("object_id"), "no_fit": parsed["outcome"] == "no_fit"}
            else:
                out[tid] = {"route": "plain_search", "fine_tuned_refused": True}
        store.append("fine-tune.jsonl", row)
    return out
