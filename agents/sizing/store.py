"""The record: every decision and outcome, every table version, what's active. Append-only; any version can be restored."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RECORDS = Path(os.environ.get("SIZING_RECORDS") or HERE / "records")
VERSIONS = Path(os.environ.get("SIZING_VERSIONS") or HERE / "versions")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def append(name: str, row: dict[str, Any]) -> None:
    RECORDS.mkdir(parents=True, exist_ok=True)
    with (RECORDS / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), **row}) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read(name: str) -> list[dict[str, Any]]:
    path = RECORDS / name
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    if name == "outcomes.jsonl":  # corrections sit beside the row they correct; the row itself stays as written
        fixes = {c["task_id"]: c["set"] for c in read("corrections.jsonl")}
        out = [{**r, **fixes.get(r.get("task_id"), {}), **({"corrected": True} if r.get("task_id") in fixes else {})} for r in out]
    return out


def _write_json(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def table(version: int) -> dict[str, Any]:
    return json.loads((VERSIONS / f"v{version}.json").read_text(encoding="utf-8"))


def versions() -> list[int]:
    return sorted(int(p.stem[1:]) for p in VERSIONS.glob("v[0-9]*.json"))


def new_version(body: dict[str, Any]) -> int:
    version = (versions() or [0])[-1] + 1
    _write_json(VERSIONS / f"v{version}.json", {**body, "version": version})
    return version


def state() -> dict[str, Any]:
    path = VERSIONS / "state.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"active": 1, "canary": None, "history": []}


def save_state(body: dict[str, Any]) -> None:
    _write_json(VERSIONS / "state.json", body)


def choose_table(task_id: str, st: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Most Tasks use the active table; a small, hash-chosen share uses a candidate."""
    can = st.get("canary")
    if can:
        digest = int(hashlib.sha256(f"canary:{can['version']}:{task_id}".encode()).hexdigest(), 16) % 100
        if digest < int(can["share_pct"]):
            return table(int(can["version"])), "canary"
    return table(int(st["active"])), "active"
