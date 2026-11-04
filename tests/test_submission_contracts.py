"""Automated submission contract and environment template verification."""

from __future__ import annotations

import unittest
from pathlib import Path

from sandbox.verify_pack import verify_pack_dir

ROOT = Path(__file__).resolve().parents[1]


class SubmissionContractsTest(unittest.TestCase):
    def test_env_example_declares_meta_and_partner_keys_without_secrets(self) -> None:
        env_path = ROOT / ".env.example"
        self.assertTrue(env_path.is_file(), "missing .env.example")
        content = env_path.read_text(encoding="utf-8")
        for key in ("MODEL_API_KEY=", "BASETEN_API_KEY=", "FIREWORKS_API_KEY=", "TESSERA_URL=", "HERMA_URL="):
            self.assertIn(key, content)
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.endswith("_KEY") or "SECRET" in name or "TOKEN" in name:
                self.assertEqual(value, "", f"secret placeholder must be empty: {name}")

    def test_starter_seed_pack_verifies_cleanly(self) -> None:
        report = verify_pack_dir(ROOT / "templates" / "new-seed-pack")
        self.assertTrue(report["ok"], report)

    def test_readme_declares_startup_track_light_only_and_rubric(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Startup Track", readme)
        self.assertIn("Teleion Labs Incorporated", readme)
        self.assertIn("System-1", readme)
        self.assertIn("My NGO needs help", readme)
        self.assertNotIn("Indie team", readme)
        self.assertNotIn("prefers-color-scheme: dark", readme)


if __name__ == "__main__":
    unittest.main()
