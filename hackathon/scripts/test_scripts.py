"""Tests for the shared scripts: the architecture check, the leak scan and the index builder's link base."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parent / "templates" / "review" / "architecture.example.json"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


check_architecture = load("check_architecture")
check_public = load("check_public")
build_index = load("build_index")


class ArchitectureCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.data = json.loads(EXAMPLE.read_text())
        for doc in self.data["read_order"]:
            path = self.root / doc
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# doc\n")
        package = self.root / "src" / "my_app"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "store.py").write_text("import sqlite3\nfrom . import __name__ as _n\n")
        (package / "api.py").write_text("from my_app.store import sqlite3\n")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_store.py").write_text("def test_claim_is_exclusive():\n    pass\n")

    def problems(self) -> list[str]:
        return check_architecture.check(self.root, self.data)

    def test_example_matches_a_tree_that_has_its_files(self) -> None:
        self.assertEqual(self.problems(), [])

    def test_missing_path_is_reported(self) -> None:
        (self.root / "docs" / "setup.md").unlink()
        self.assertTrue(any("missing path: docs/setup.md" in p for p in self.problems()))

    def test_missing_test_function_is_reported(self) -> None:
        (self.root / "tests" / "test_store.py").write_text("def test_other():\n    pass\n")
        self.assertTrue(any("no test or class named test_claim_is_exclusive" in p for p in self.problems()))

    def test_forbidden_import_is_reported(self) -> None:
        (self.root / "src" / "my_app" / "store.py").write_text("from .api import router\n")
        found = [p for p in self.problems() if "must not import" in p]
        self.assertIn("src/my_app/store.py:1", found[0])
        self.assertEqual(len(found), 1)
        self.assertIn("my_app.api", found[0])

    def test_rule_files_must_sit_in_the_package(self) -> None:
        self.data["import_rules"][0]["files"] = ["tests/test_store.py"]
        self.assertTrue(any("outside package_root" in p for p in self.problems()))

    def test_unknown_dependency_and_unchecked_invariant(self) -> None:
        self.data["components"][1]["depends_on"] = ["cache"]
        self.data["invariants"][0]["checked_by"] = []
        problems = " ".join(self.problems())
        self.assertIn("unknown component cache", problems)
        self.assertIn("an unchecked invariant is a wish", problems)

    def test_paths_must_stay_inside_the_repo(self) -> None:
        self.data["docs"]["summary"] = "../elsewhere/SUMMARY.md"
        self.assertTrue(any("inside the repo" in p for p in self.problems()))

    def test_the_docs_table_must_match_and_can_be_synced(self) -> None:
        doc = self.root / "docs" / "architecture.md"
        doc.write_text("# doc\n\n## Invariants\n\n| Id | Always true | Checked by |\n|---|---|---|\n| I9 | old |  |\n")
        self.assertTrue(any("differs from architecture.json" in p for p in self.problems()))
        check_architecture.sync_docs(self.root, self.data)
        self.assertEqual(self.problems(), [])
        self.assertIn("| I1 | An item is claimed by at most one worker at a time |", doc.read_text())

    def test_mermaid_lists_components_and_edges(self) -> None:
        graph = check_architecture.mermaid(self.data)
        self.assertIn('store["Store"]', graph)
        self.assertIn("api --> store", graph)


class PublicCheck(unittest.TestCase):
    def test_hash_line_and_match(self) -> None:
        digest = check_public.hash_line("Example-Name")
        self.assertTrue(check_public.private_names("see example-name here", frozenset({digest})))
        self.assertFalse(check_public.private_names("an example of a name", frozenset({digest})))

    def test_hash_line_refuses_phrases(self) -> None:
        with self.assertRaises(ValueError):
            check_public.hash_line("two words")

    def test_load_hashes_skips_comments_and_junk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "names.sha256"
            path.write_text("# comment\n" + "a" * 64 + "  # trailing\nnot-a-hash\n")
            self.assertEqual(check_public.load_hashes(path), frozenset({"a" * 64}))


class IndexLinks(unittest.TestCase):
    def test_github_remote_forms(self) -> None:
        for url in (
            "https://github.com/owner/repo.git",
            "https://github.com/owner/repo",
            "git@github.com:owner/repo.git",
            "https://user:secret@github.com/owner/repo.git",
        ):
            match = build_index.GITHUB.search(url)
            self.assertIsNotNone(match, url)
            self.assertEqual((match.group(1), match.group(2)), ("owner", "repo"), url)


if __name__ == "__main__":
    unittest.main()
