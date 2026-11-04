"""Dynamic reader for the single workspace banned-word list and PII trace scrubber.

Reads patterns dynamically from `notes/coordination-2026-10-31/rules/banned-words.json`
without copying forbidden strings into repository source files.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

WORD_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
BEARER_RE = re.compile(r"\b(?:Bearer\s+[A-Za-z0-9._\-~+/=]+|tsk_[A-Za-z0-9._\-]+|tan_[A-Za-z0-9._\-]+|hmk_[A-Za-z0-9._\-]+)\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\w)")


class BannedWordsGuard:
    """Enforces the single workspace banned-words specification and scrubs private information."""

    def __init__(self, rules_path: str | Path) -> None:
        self.rules_path = Path(rules_path)
        spec: dict[str, Any] = json.loads(self.rules_path.read_text(encoding="utf-8"))
        flags = re.IGNORECASE if spec.get("case_insensitive", True) else 0
        always_raw = list((spec.get("always") or {}).get("patterns") or [])
        visible_raw = list((spec.get("visible_text") or {}).get("patterns") or [])
        marketing_raw = list((spec.get("marketing_voice") or {}).get("patterns") or [])
        self.always_patterns = [re.compile(pat, flags) for pat in always_raw]
        self.visible_patterns = [re.compile(pat, flags) for pat in visible_raw]
        self.marketing_patterns = [re.compile(pat, flags) for pat in marketing_raw]
        self.private_sha256: frozenset[str] = frozenset(
            str(h).lower() for h in ((spec.get("private_names") or {}).get("sha256") or [])
        )

    def scan_text(
        self,
        text: str,
        *,
        include_visible_rules: bool = True,
        include_marketing_rules: bool = False,
    ) -> list[str]:
        hits: list[str] = []
        for rx in self.always_patterns:
            if rx.search(text):
                hits.append(f"always:{rx.pattern}")
        if include_visible_rules:
            for rx in self.visible_patterns:
                if rx.search(text):
                    hits.append(f"visible:{rx.pattern}")
        if include_marketing_rules:
            for rx in self.marketing_patterns:
                if rx.search(text):
                    hits.append(f"marketing:{rx.pattern}")
        for match in WORD_TOKEN_RE.finditer(text):
            token_lower = match.group(0).lower()
            if token_lower == "teleion" or token_lower == "teleionlabs":
                continue
            digest = hashlib.sha256(token_lower.encode("utf-8")).hexdigest()
            if digest in self.private_sha256:
                hits.append(f"private_name_hash:{digest}")
        return hits

    def sanitize_visible_text(self, text: str) -> str:
        """Replace banned patterns and private tokens so agent outputs stay clean."""
        cleaned = scrub_private_info(text)
        for rx in self.always_patterns:
            cleaned = rx.sub("checked example", cleaned)
        for rx in self.marketing_patterns:
            cleaned = rx.sub("checked", cleaned)
        for rx in self.visible_patterns:
            cleaned = rx.sub("record", cleaned)
        def _replace_private(match: re.Match[str]) -> str:
            tok = match.group(0)
            low = tok.lower()
            if low in {"teleion", "teleionlabs"}:
                return tok
            digest = hashlib.sha256(low.encode("utf-8")).hexdigest()
            if digest in self.private_sha256:
                return "Teleion"
            return tok

        return WORD_TOKEN_RE.sub(_replace_private, cleaned)


def scrub_private_info(text: str) -> str:
    """Strip emails, phone numbers, and bearer/session credentials before persisting traces."""
    out = BEARER_RE.sub("[REDACTED_CREDENTIAL]", str(text or ""))
    out = EMAIL_RE.sub("[REDACTED_EMAIL]", out)
    out = PHONE_RE.sub("[REDACTED_PHONE]", out)
    return out
