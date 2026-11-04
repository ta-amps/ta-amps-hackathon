#!/usr/bin/env python3
"""Fails on any gap over 3 s between spoken words in the main body of a voice key. voice_gaps.py <key> [<key> ...]"""
import json, re, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent; bad = 0
for k in sys.argv[1:]:
    s = (R / f"voices/{k}/data.js").read_text(); C = json.loads(re.search(r"window\.CUES=(\{.*?\});?\n", s)[1]); W = sorted((w[1], w[2], w[0], n) for n, c in C.items() for w in c.get("words") or [])
    gaps = [(round(a[1], 1), round(b[0], 1), round(b[0] - a[1], 1), a[2], b[2]) for a, b in zip(W, W[1:]) if b[0] - a[1] > 3]
    print(k, "words", len(W), "first", round(W[0][0], 1), "last", round(W[-1][1], 1), "gaps>3s:", gaps or "none"); bad += len(gaps)
sys.exit(1 if bad else 0)
