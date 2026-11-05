"""A Task's fingerprint: how the Task looks, not a hash.

Kind, size, inputs, output, the tools it seems to need, its structure and its words. score() compares two fingerprints over those
features and neighbors() returns the nearest earlier Tasks with their scores. Deterministic, no model. The word part uses Fabric's own
tested MinHash library (in the Fabric repository), so only the profile features are new.
"""
from __future__ import annotations

import hashlib
import re
import sys
import os
from pathlib import Path
from typing import Any

FABRIC = Path(os.environ.get("FABRIC_SRC", "/nonexistent"))
if str(FABRIC) not in sys.path:
    sys.path.insert(0, str(FABRIC))
from tessera import fingerprints as lib  # noqa: E402

ID_SHAPES = re.compile(r"\b(?:verb_[a-z]+_[0-9a-f]{6,}|RPT-[A-Z0-9-]+|[0-9a-f]{10,})\b")
URL = re.compile(r"https?://[^\s)\"'<>]+")
_NEEDS = [
    ("people_or_hardware", r"\b(field team|in person|physical|print the|gloved|sensor|soldering|on-site|hardware|signed|bench test|trial rows|live rows|calibrat\w*|real device|phone call|interview)\b"),
    ("run_code", r"\b(python|pytest|unit test|fixtures?|script|validator|regression test|function|csv|json schema|parser|implement|extend|sha-?256|reproduce)\b"),
    ("read_url", r"https?://"),
    ("read_object", r"\b[a-z][a-z0-9_-]*_v\d+\b|/q/object/"),
    ("sources", r"\b(official|sources?|look up|cite|citations?|research|latest|public pages?)\b"),
    ("write_prose", r"\b(summari[sz]e|summary|adapt|sheet|draft|write|translate|checklist|plain language|narration|captions?)\b"),
    ("judge_other_work", r"\b(review|evaluate|verify|check whether|audit|score|rank|falsif\w*)\b"),
]
_OUT = [
    ("code_and_tests", r"\b(test|tests|fixtures?|validator|script|function|module)\b"),
    ("verdict", r"\b(review|evaluate|verdict|score|rank|pass/fail|verify)\b"),
    ("table", r"\b(table|rows|matrix|csv)\b"),
    ("short_sheet", r"\b(sheet|checklist|card|one-page|two minutes|summary)\b"),
    ("structured_fields", r"\b(fields?|keywords|index|schema|json)\b"),
]
WEIGHTS = {"needs": 0.34, "output": 0.14, "kind": 0.14, "inputs": 0.10, "size": 0.06, "structure": 0.06, "words": 0.16}  # set before any test; not tuned on held-out pairs


def text_of(task: dict[str, Any]) -> str:
    return f"{task.get('title') or ''}\n{task.get('prompt') or task.get('prompt_head') or ''}"


def exact(task: dict[str, Any]) -> str:
    return hashlib.sha256(" ".join(text_of(task).lower().split()).encode()).hexdigest()[:24]


def needs(text: str) -> list[str]:
    low = text.lower()
    return [n for n, p in _NEEDS if re.search(p, low)]


def output_shape(text: str) -> str:
    low = text.lower()
    return next((n for n, p in _OUT if re.search(p, low)), "prose")


def input_shape(text: str) -> dict[str, int]:
    return {"urls": len(URL.findall(text)), "objects_named": len(set(re.findall(r"\b[a-z][a-z0-9_-]*_v\d+\b", text.lower())))}


def structure(text: str) -> dict[str, bool]:
    return {"lists": bool(re.search(r"(^|\n)\s*(?:[-*]|\d+[.)])\s", text)), "numbered_steps": len(re.findall(r"(?:^|\n)\s*\d+[.)]\s", text)) >= 2,
            "has_numbers": len(re.findall(r"\b\d+(?:\.\d+)?\b", text)) >= 3, "waits_on": bool(re.search(r"\b(once|until|blocked)\b", text.lower()))}


def minhash(task: dict[str, Any]) -> str | None:
    view = lib.brief_view({"title": str(task.get("title") or ""), "instructions": ID_SHAPES.sub(" ", text_of(task))})
    return lib.minhash(lib.features(str(task.get("category") or "unknown"), view, {}))


def fingerprint(task: dict[str, Any]) -> dict[str, Any]:
    t = text_of(task)
    mh = minhash(task)
    return {"profile": "assembler-fp-2", "exact": exact(task), "minhash": mh, "bands": lib.bands(mh) if mh else [],
            "category": "e2e-canary" if str(task.get("category")).startswith("e2e-canary") else str(task.get("category") or "unknown"),
            "step_mode": str(task.get("step_mode") or ""), "size": min(5, len(t) // 400), "complexity_band": int(task.get("complexity_milli") or 0) // 250,
            "needs": needs(t), "input_shape": input_shape(t), "output_shape": output_shape(t), "structure": structure(t)}


def similarity(a: str | None, b: str | None) -> float:
    return float(lib.similarity(a, b) or 0.0) if a and b else 0.0


def parts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, float]:
    na, nb = set(a["needs"]), set(b["needs"])
    ia, ib = a["input_shape"], b["input_shape"]

    def close(x: float, y: float, span: float) -> float:
        return max(0.0, 1.0 - abs(x - y) / span)

    return {"needs": (len(na & nb) / len(na | nb)) if (na | nb) else 1.0,
            "output": float(a["output_shape"] == b["output_shape"]),
            "kind": 0.5 * float(a["category"] == b["category"]) + 0.5 * float(a["step_mode"] == b["step_mode"]),
            "inputs": (float(bool(ia["urls"]) == bool(ib["urls"])) + float(bool(ia["objects_named"]) == bool(ib["objects_named"]))) / 2,
            "size": 0.5 * close(a["size"], b["size"], 3) + 0.5 * close(a["complexity_band"], b["complexity_band"], 3),
            "structure": sum(a["structure"][k] == b["structure"][k] for k in a["structure"]) / len(a["structure"]),
            "words": similarity(a["minhash"], b["minhash"])}


def score(a: dict[str, Any], b: dict[str, Any]) -> float:
    p = parts(a, b)
    return round(sum(WEIGHTS[k] * p[k] for k in WEIGHTS), 4)


def neighbors(query: dict[str, Any], rows: list[dict[str, Any]], k: int = 8, floor: float = 0.0) -> list[dict[str, Any]]:
    """Nearest rows by score, best first. Each row carries `fp`."""
    found = [{"score": score(query, r["fp"]), "row": r} for r in rows]
    found = [f for f in found if f["score"] >= floor]
    found.sort(key=lambda x: -x["score"])
    return found[:k]
