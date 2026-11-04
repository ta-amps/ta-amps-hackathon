"""Size an Eranos request: is a kit needed at all, and how large? Plain code, 0 tokens. SHADOW ONLY: the live planner doesn't read this.

Uses the kit handler's own signature (which tested class fits, which operations it asks for) and the live catalog, on real requests.
A flag in the planner would be needed to act on it, and the workers restart only with the owner's command.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import sys
import urllib.request
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
HANDLER = Path(os.environ.get("ERANOS_PROCESS_HANDLER", "/nonexistent"))
FABRIC = "https://fabric.teleionlabs.com"
RECURRING_OR_TEMPLATE = ("reusable", "checklist", "template", "every month", "monthly", "each month", "each week", "weekly", "workflow", "process")


def size_kit(text: str, output_type: str | None, signature: dict[str, Any], catalog_keys: set[str]) -> dict[str, Any]:
    ops = sorted(signature.get("operations") or [])
    key = signature.get("key")
    if key and key in catalog_keys:
        return {"needed": "no_a_kit_exists", "kit_key": key, "operations": ops, "size": 0, "tokens": 0}
    if output_type == "information":
        return {"needed": "no_a_cited_answer", "operations": [], "size": 0, "tokens": 0}
    if key:
        return {"needed": "yes", "class": signature.get("class"), "operations": ops, "size": len(ops), "kit_files": "tested class, only the operations asked for", "tokens": 0}
    # asked for a process, and no tested class fits: building is refused later, so say so now and offer what can be done
    return {"needed": "no_tested_class_fits", "operations": [], "size": 0, "next": "cited answer from public sources, or a new tested class", "tokens": 0}


def actual_outcome(v: dict[str, Any]) -> str:
    types = [e.get("type") for e in v.get("events") or []]
    if "published" in types:
        return "kit_published"
    if "delivered" in types:
        return "report_delivered"
    if "work_failed" in types or "blocked" in types or v.get("status") == "closed":
        return "closed_with_nothing_delivered"
    return "open"


def main() -> None:
    spec = importlib.util.spec_from_file_location("eranos_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HANDLER.parent))
    spec.loader.exec_module(mod)
    get = lambda p: json.load(urllib.request.urlopen(urllib.request.Request(FABRIC + p, headers={"User-Agent": "teleion-sizing-worker/1"}), timeout=40))  # noqa: E731
    requests = get("/v1/stores/eranos.requests/records?limit=200")["records"]
    rows, table = [], collections.Counter()
    for r in requests:
        v = r["value"]
        text = str(v.get("text") or v.get("description") or "")
        try:
            sig = mod.reuse_signature(text) or {}
        except Exception as exc:  # noqa: BLE001
            sig = {"error": type(exc).__name__}
        d = size_kit(text, v.get("output_type"), sig, set())
        out = actual_outcome(v)
        rows.append({"request": r["key"], "output_type": v.get("output_type"), "sized": d, "actual": out, "chars": len(text)})
        table[(d["needed"], out)] += 1
    (HERE / "records/kit-shadow.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    print(json.dumps({"requests": len(rows), "sized_then_actual": {f"{a} / {b}": n for (a, b), n in sorted(table.items())}, "ops_sizes": collections.Counter(x["sized"]["size"] for x in rows if x["sized"]["needed"] == "yes")}, indent=1, default=str))


if __name__ == "__main__":
    main()
