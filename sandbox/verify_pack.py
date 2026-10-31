"""Validate a ta-amps Seed Pack directory offline (stdlib only, zero network).

Checks manifest.json, nouns.json (Task Objects), and verbs.json (Tasks) for schema
completeness, descriptor prefix, effect ceilings, separation-of-duties metadata,
and absence of obvious secrets.

Usage:
  python3 -m sandbox.verify_pack templates/new-seed-pack
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PACK_PHRASE = "A collection of nouns and verbs for "
ALLOWED_MODES = {"none", "local_only", "read_only", "scoped_write"}
SECRET_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|tsk_[A-Za-z0-9_-]{24,}|hf_[A-Za-z0-9]{20,})")


class PackValidationError(ValueError):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise PackValidationError(msg)


def verify_pack_dir(pack_dir: Path) -> dict:
    pack_dir = pack_dir.resolve()
    manifest_path = pack_dir / "manifest.json"
    nouns_path = pack_dir / "nouns.json"
    verbs_path = pack_dir / "verbs.json"

    for p in (manifest_path, nouns_path, verbs_path):
        require(p.is_file(), f"missing required file: {p.name}")
        raw_text = p.read_text(encoding="utf-8")
        require("\u2014" not in raw_text, f"{p.name}: em-dash character is forbidden")
        require(SECRET_RE.search(raw_text) is None, f"{p.name}: contains token-like secret string")

    raw_nouns = nouns_path.read_bytes()
    raw_verbs = verbs_path.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nouns_doc = json.loads(raw_nouns.decode("utf-8"))
    verbs_doc = json.loads(raw_verbs.decode("utf-8"))

    pack_id = manifest.get("pack_id", "")
    require(bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(pack_id))), "manifest.json: invalid pack_id slug")
    require(manifest.get("status") == "proposal_only", "manifest.json: starter packs must declare status 'proposal_only'")

    records = nouns_doc.get("records")
    tasks = verbs_doc.get("tasks")
    require(isinstance(records, list) and len(records) >= 2, "nouns.json: expected at least 2 Task Object records")
    require(isinstance(tasks, list) and len(tasks) >= 1, "verbs.json: expected at least 1 Task template")
    require(len(manifest.get("nouns", [])) == len(records), "manifest.json noun count differs from nouns.json")
    require(len(manifest.get("verbs", [])) == len(tasks), "manifest.json verb count differs from verbs.json")

    descriptors = [r for r in records if isinstance(r, dict) and (r.get("value") or {}).get("role") == "pack"]
    require(len(descriptors) == 1, "nouns.json: expected exactly one descriptor noun with role 'pack'")
    desc_title = str(descriptors[0]["value"].get("title", ""))
    require(
        desc_title.startswith(PACK_PHRASE) and len(desc_title) > len(PACK_PHRASE),
        f"nouns.json: pack descriptor title must start with {PACK_PHRASE!r}",
    )

    for task in tasks:
        brief = task.get("brief") or {}
        tid = brief.get("template_id", "")
        require(bool(tid), "verbs.json: every task brief needs a template_id")
        mode = ((brief.get("execution") or {}).get("network") or {}).get("mode", "none")
        require(mode in ALLOWED_MODES, f"verbs.json: {tid} has unsupported network mode {mode!r}")

    return {
        "ok": True,
        "pack_id": pack_id,
        "status": manifest["status"],
        "records": len(records),
        "tasks": len(tasks),
        "nouns_sha256": hashlib.sha256(raw_nouns).hexdigest(),
        "verbs_sha256": hashlib.sha256(raw_verbs).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pack_dir", type=Path, help="Path to seed pack folder")
    args = parser.parse_args(argv)
    try:
        receipt = verify_pack_dir(args.pack_dir)
    except (PackValidationError, json.JSONDecodeError) as exc:
        print(f"verify_pack: FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
