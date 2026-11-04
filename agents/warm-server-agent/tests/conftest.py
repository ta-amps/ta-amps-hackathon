"""Tests never reach a real partner route or the real spend ledger. (A first run did: about a dozen tiny Baseten calls, on the record.)"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# A clean copy has no shared word list. A small generated one lets the tests run.
if not os.environ.get("TELEION_NOTES"):
    _notes = Path(tempfile.mkdtemp())
    _list = _notes / "coordination-2026-10-31/rules/banned-words.json"
    _list.parent.mkdir(parents=True)
    _list.write_text(json.dumps({"always": {"patterns": ["\\bs" + "ynthetic\\b"]}, "private_names": {"sha256": []}}), encoding="utf-8")
    os.environ["TELEION_NOTES"] = str(_notes)

import pytest

for _variable, _name in (("WARM_AGENT_NAME", "test-agent"), ("WARM_AGENT_MAKER_NAME", "test-maker"), ("WARM_AGENT_CHECKER_NAME", "test-checker")):
    os.environ.setdefault(_variable, _name)


@pytest.fixture(autouse=True)
def _no_real_routes(monkeypatch, tmp_path):
    from warm_agent import agent_loop, decider

    real = decider.bounded_decide
    monkeypatch.setattr(decider, "partner_settings", lambda *_a, **_k: None)
    monkeypatch.setattr(agent_loop, "fabric_bounded_decide", lambda task, **kw: real(task, routes_path=tmp_path / "routes.json", spend_path=tmp_path / "spend.jsonl", **kw))
