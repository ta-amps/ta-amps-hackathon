from pathlib import Path

import pytest

OFF = Path(__file__).resolve().parent.parent / "omninode_live" / "prestep_off.json"


@pytest.fixture(autouse=True)
def prestep_stays_in_the_test(tmp_path, monkeypatch):
    """Traces never reach the real file. The older tests pin today's path, so they run with the pre-step off;
    test_prestep.py turns the real table on."""
    monkeypatch.setenv("OMNINODE_PRESTEP_TRACES", str(tmp_path / "prestep-traces.jsonl"))
    monkeypatch.setenv("OMNINODE_PRESTEP_RULES", str(OFF))
