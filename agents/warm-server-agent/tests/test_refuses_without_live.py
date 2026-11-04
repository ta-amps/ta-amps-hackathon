"""A copy of this agent never touches production unless a person asks for that."""

import pytest

from warm_agent import agent_loop


def _must_not_run(*_args, **_kwargs):
    raise AssertionError("the agent started")


def test_refuses_without_the_live_setting(monkeypatch):
    monkeypatch.delenv("WARM_AGENT_LIVE", raising=False)
    monkeypatch.setattr(agent_loop, "WarmServerAgent", _must_not_run)
    with pytest.raises(SystemExit, match="WARM_AGENT_LIVE"):
        agent_loop.main(["--once"])


def test_refuses_without_its_own_names(monkeypatch):
    monkeypatch.setenv("WARM_AGENT_LIVE", "1")
    monkeypatch.delenv("WARM_AGENT_MAKER_NAME", raising=False)
    monkeypatch.setattr(agent_loop, "WarmServerAgent", _must_not_run)
    with pytest.raises(SystemExit, match="WARM_AGENT_MAKER_NAME"):
        agent_loop.main(["--once"])
