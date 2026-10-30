#!/usr/bin/env python3
"""Check that every JSON file parses and every relative Markdown link resolves.

Usage: python3 scripts/check_docs.py [ROOT]
Stdlib only. Links to http(s), mailto and pure anchors are skipped. Paths listed in `.links-pending`
(one per line) may be missing: they are pages someone else is still writing.
Exit 0 when clean, 1 with a report otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "out", "transcripts"}
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"^(```|~~~)")


def files(root: Path, suffix: str) -> list[Path]:
    return [p for p in root.rglob(f"*{suffix}")
            if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS)]


def pending(root: Path) -> set[str]:
    path = root / ".links-pending"
    if not path.exists():
        return set()
    return {ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")}


def link_targets(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = re.sub(r"`[^`]*`", "", line)
        for match in list(LINK.finditer(line)) + list(IMAGE.finditer(line)):
            out.append((number, match.group(1)))
    return out


def check(root: Path) -> list[str]:
    problems: list[str] = []
    for path in files(root, ".json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            problems.append(f"{path.relative_to(root)}: invalid JSON ({exc})")
    allowed_missing = pending(root)
    for path in files(root, ".md"):
        for number, target in link_targets(path.read_text(encoding="utf-8")):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            try:
                rel = resolved.relative_to(root.resolve()).as_posix()
            except ValueError:
                rel = None
            if rel in allowed_missing:
                continue
            if not resolved.exists():
                problems.append(f"{path.relative_to(root)}:{number}: broken link -> {target}")
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    problems = check(root)
    if problems:
        print(f"check_docs: {len(problems)} problem(s)", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    print("check_docs: JSON valid, links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
