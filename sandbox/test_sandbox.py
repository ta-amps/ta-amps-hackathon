"""Unit tests for the local offline developer sandbox and starter templates."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from sandbox.local_server import (
    ContributorTierRefusedError,
    SandboxEngine,
    SelfVerificationRefusedError,
    make_server,
)
from sandbox.verify_pack import PackValidationError, verify_pack_dir
from sandbox.worker_smoke import run_smoke

ROOT = Path(__file__).resolve().parents[1]
STARTER_PACK = ROOT / "templates" / "new-seed-pack"


class SandboxTests(unittest.TestCase):
    def test_starter_seed_pack_template_is_valid(self) -> None:
        receipt = verify_pack_dir(STARTER_PACK)
        self.assertTrue(receipt["ok"])
        self.assertEqual("proposal_only", receipt["status"])
        self.assertGreaterEqual(receipt["records"], 3)
        self.assertGreaterEqual(receipt["tasks"], 3)

    def test_verify_pack_rejects_non_proposal_or_em_dash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in ("manifest.json", "nouns.json", "verbs.json"):
                (p / name).write_text((STARTER_PACK / name).read_text(encoding="utf-8"), encoding="utf-8")
            manifest = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
            manifest["status"] = "admitted"
            (p / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(PackValidationError):
                verify_pack_dir(p)

    def test_engine_enforces_contributor_refusal_and_independent_verifier(self) -> None:
        engine = SandboxEngine()
        put = engine.store_put("seedpack.demo", "noun:1", {"role": "item"})
        self.assertEqual(1, put["version"])
        task = engine.create_task("verb.solve_draft", "Test task")
        with self.assertRaises(ContributorTierRefusedError):
            engine.claim_task(task["task_id"], "w1", model="muse-spark-contributor")
        claim = engine.claim_task(task["task_id"], "w1", model="muse-spark-1.3")
        engine.submit_draft(task["task_id"], claim["lease_token"], "w1", "noun:1")
        with self.assertRaises(SelfVerificationRefusedError):
            engine.verify_task(task["task_id"], "w1", model="muse-spark-1.3")
        verified = engine.verify_task(task["task_id"], "w2", model="muse-spark-1.3")
        self.assertEqual("verified", verified["status"])
        self.assertEqual(64, len(verified["receipt_sha256"]))

    def test_end_to_end_http_worker_smoke(self) -> None:
        server = make_server("127.0.0.1", 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            receipt = run_smoke(f"http://127.0.0.1:{server.server_port}", STARTER_PACK)
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual("local_sandbox_smoke_passed", receipt["status"])
        self.assertTrue(receipt["contributor_tier_refused"])
        self.assertTrue(receipt["self_verification_refused"])

    def test_harness_and_lora_starter_templates_validate_offline(self) -> None:
        import subprocess
        import sys

        mcp_cfg = json.loads(
            (ROOT / "templates" / "connect-agent-harness" / "mcp-config.example.json").read_text(encoding="utf-8")
        )
        self.assertIn("tessera-local-sandbox", mcp_cfg["mcpServers"])

        out = subprocess.check_output(
            [
                sys.executable,
                str(ROOT / "templates" / "finetune-meta-lora" / "train_lora_template.py"),
                "--dry-run-manifest",
                "-",
            ],
            text=True,
        )
        manifest = json.loads(out)
        self.assertEqual("practice_template_run", manifest["status"])
        self.assertFalse(manifest["admitted_artifact"])
        self.assertEqual(3, manifest["examples_verified"])

    def test_lora_template_requires_base_model_for_training(self) -> None:
        import subprocess
        import sys

        script = ROOT / "templates" / "finetune-meta-lora" / "train_lora_template.py"
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        self.assertEqual(2, proc.returncode)
        self.assertIn("--base-model is required", proc.stderr)

    def test_lora_template_renders_examples_with_the_tokenizers_own_chat_template(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "train_lora_template", ROOT / "templates" / "finetune-meta-lora" / "train_lora_template.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class WithTemplate:
            chat_template = "template"

            def apply_chat_template(self, messages, tokenize=False):
                return "|".join(f"{m['role']}={m['content']}" for m in messages)

        class WithoutTemplate:
            chat_template = None

        row = {"system": "s", "user": "u", "assistant": "a"}
        self.assertEqual("system=s|user=u|assistant=a", module.render_example(WithTemplate(), row))
        self.assertEqual("system: s\nuser: u\nassistant: a", module.render_example(WithoutTemplate(), row))


if __name__ == "__main__":
    unittest.main()
