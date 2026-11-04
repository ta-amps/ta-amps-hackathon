import json
import os
import tempfile
from pathlib import Path

# A clean copy has no shared word list. A small generated one lets the tests run; real runs set BANNED_WORDS_FILE.
if not os.environ.get("BANNED_WORDS_FILE") and not os.environ.get("TELEION_NOTES"):
    words = Path(tempfile.mkdtemp()) / "banned-words.json"
    words.write_text(
        json.dumps(
            {
                "always": {"patterns": ["\\bs" + "ynthetic\\b"]},
                "visible_text": {"patterns": []},
                "agent_apps_outside_models_page": {"patterns": []},
                "private_names": {"sha256": []},
            }
        ),
        encoding="utf-8",
    )
    os.environ["BANNED_WORDS_FILE"] = str(words)

import pytest

OFF = Path(__file__).resolve().parent.parent / "omninode_live" / "prestep_off.json"


@pytest.fixture(autouse=True)
def prestep_stays_in_the_test(tmp_path, monkeypatch):
    """Traces never reach the real file. The older tests pin today's path, so they run with the pre-step off;
    test_prestep.py turns the real table on."""
    monkeypatch.setenv("OMNINODE_PRESTEP_TRACES", str(tmp_path / "prestep-traces.jsonl"))
    monkeypatch.setenv("OMNINODE_PRESTEP_RULES", str(OFF))
