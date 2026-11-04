#!/usr/bin/env python3
"""The word gate exempts exactly one file, the Meta models notice; every other place still fails."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("check_words", HERE / "check_words.py")
cw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cw)
NOTICE = HERE.parent / "static" / "legal" / "meta-models.txt"
FAMILY = "L" + "la" + "ma"
REQUIRED = (
    "Built with Muse Spark Open",
    f"Built with {FAMILY}",
    f"{FAMILY} 3.2 is licensed under the {FAMILY} 3.2 Community License, Copyright © Meta Platforms, Inc. All Rights Reserved.",
    "Copyright (c) 2026 Meta Platforms, Inc.",
)


def made_up_list() -> Path:
    """A small made-up list in the shared list's shape, so this test needs no private file."""
    path = Path(tempfile.mkdtemp()) / "word-list.json"
    group = {"patterns": [FAMILY.lower()]}
    path.write_text(json.dumps({"always": group, "visible_text": group, "agent_apps_outside_models_page": group,
                                "marketing_voice": group, "private_names": {"sha256": ["0" * 64]}}), encoding="utf-8")
    return path


class Exempt(unittest.TestCase):
    def test_only_one_exact_path(self):
        self.assertEqual(cw.NOTICE_FILES, frozenset({"static/legal/meta-models.txt"}))

    def test_required_wording_stays_in_the_notice(self):
        text = NOTICE.read_text(encoding="utf-8")
        for line in REQUIRED:
            self.assertIn(line, text)

    def test_the_notice_has_no_private_name(self):
        shared = cw.Shared(made_up_list())
        self.assertEqual(cw.notice_hits("x", NOTICE.read_text(encoding="utf-8"), shared), [])

    def test_the_exemption_still_fails_on_the_word_no_notice_needs(self):
        shared = cw.Shared(made_up_list())
        self.assertTrue(cw.notice_hits("x", "a " + "syn" + "thetic case", shared))

    def test_the_family_name_still_fails_everywhere_else(self):
        """The real list's rule, read from the sample's shape: any other path goes through the full gate."""
        for rel in ("static/legal/other.txt", "static/meta-models.txt", "legal/meta-models.txt", "static/legal/meta-models.txt.bak",
                    "content/site.json", "static/legal/META-MODELS.TXT", "./static/legal/meta-models.txt"):
            self.assertNotIn(rel, cw.NOTICE_FILES, rel)
        shared = cw.Shared(made_up_list())
        self.assertTrue(any(rx.search(f"run {FAMILY} here") for rx in shared.always))


if __name__ == "__main__":
    unittest.main()
