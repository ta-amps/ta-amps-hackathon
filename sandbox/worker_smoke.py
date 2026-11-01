"""Run an end-to-end offline developer smoke test against the local sandbox.

Validates `templates/new-seed-pack`, loads its Task Objects (`nouns`) into the
sandbox store, executes a fenced Task (`verb`) as `worker-drafter`, confirms that
self-verification (`verifier == builder`) and contributor-tier models are
deterministically refused, completes verification as `worker-reviewer`, and emits
a JSON smoke receipt.

Usage:
  python3 -m sandbox.worker_smoke                       # ephemeral in-process loopback server
  python3 -m sandbox.worker_smoke --endpoint http://tessera-local:8787
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from sandbox.local_server import DEFAULT_MODEL, make_server
from sandbox.verify_pack import verify_pack_dir

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "templates" / "new-seed-pack"


def rpc(endpoint: str, action: str, params: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/mcp",
        data=json.dumps({"action": action, "params": params}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read().decode("utf-8"))
        finally:
            err.close()


def wait_healthy(endpoint: str, retries: int = 25) -> dict:
    for _ in range(retries):
        try:
            with urllib.request.urlopen(f"{endpoint.rstrip('/')}/health", timeout=2) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"sandbox endpoint {endpoint} did not become healthy")


def run_smoke(endpoint: str, pack_dir: Path = DEFAULT_PACK) -> dict:
    pack_receipt = verify_pack_dir(pack_dir)
    health = wait_healthy(endpoint)

    nouns_doc = json.loads((pack_dir / "nouns.json").read_text(encoding="utf-8"))
    store_name = f"seedpack.{pack_receipt['pack_id']}"
    stored = 0
    for rec in nouns_doc["records"]:
        code, body = rpc(endpoint, "store_put", {"store": store_name, "key": rec["key"], "value": rec["value"]})
        if code != 200 or not body.get("ok"):
            raise RuntimeError(f"store_put failed: {body}")
        stored += 1

    code, hits = rpc(endpoint, "search_nouns", {"query": "civic"})
    if code != 200 or not hits["result"]:
        raise RuntimeError("search_nouns returned no Task Objects")

    _, task_res = rpc(endpoint, "create_task", {"kind": "verb.solve_draft", "title": "Draft cited public civic brief"})
    task_id = task_res["result"]["task_id"]

    # Confirm contributor-tier model refusal (ContributorTierRefusedError -> HTTP 403).
    refused_code, refused_body = rpc(
        endpoint,
        "claim_task",
        {"task_id": task_id, "worker_id": "worker-drafter", "model": "muse-spark-contributor"},
    )
    if refused_code != 403 or refused_body.get("error") != "ContributorTierRefusedError":
        raise RuntimeError(f"expected ContributorTierRefusedError, got {refused_code}: {refused_body}")

    # Claim with a Standard-tier (non-contributor) Muse model label, write the draft Task Object, and submit
    # for verification. The label is only recorded; the simulator never calls a model.
    claim_code, claim_body = rpc(
        endpoint, "claim_task", {"task_id": task_id, "worker_id": "worker-drafter", "model": DEFAULT_MODEL}
    )
    if claim_code != 200:
        raise RuntimeError(f"claim_task failed: {claim_body}")
    lease_token = claim_body["result"]["lease_token"]

    _, draft_put = rpc(
        endpoint,
        "store_put",
        {
            "store": store_name,
            "key": "artifact:civic-brief-v1",
            "value": {"role": "draft_brief", "citations": ["https://data.gov/"], "practice_demo": True},
        },
    )
    rpc(
        endpoint,
        "submit_draft",
        {
            "task_id": task_id,
            "lease_token": lease_token,
            "worker_id": "worker-drafter",
            "output_key": draft_put["result"]["key"],
        },
    )

    # Confirm self-verification refusal (verifier == builder -> HTTP 403).
    self_code, self_body = rpc(
        endpoint, "verify_task", {"task_id": task_id, "verifier_worker": "worker-drafter", "model": DEFAULT_MODEL}
    )
    if self_code != 403 or self_body.get("error") != "SelfVerificationRefusedError":
        raise RuntimeError(f"expected SelfVerificationRefusedError, got {self_code}: {self_body}")

    # Independent verification (verifier != builder) succeeds and emits SHA-256 receipt.
    ver_code, ver_body = rpc(
        endpoint, "verify_task", {"task_id": task_id, "verifier_worker": "worker-reviewer", "model": DEFAULT_MODEL}
    )
    if ver_code != 200:
        raise RuntimeError(f"verify_task failed: {ver_body}")

    return {
        "status": "local_sandbox_smoke_passed",
        "sandbox_mode": health["mode"],
        "pack_verified": pack_receipt,
        "nouns_stored": stored,
        "contributor_tier_refused": True,
        "self_verification_refused": True,
        "verified_task": ver_body["result"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--endpoint", default="", help="Existing local_server URL; starts ephemeral loopback if omitted")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK, help="Seed pack directory to verify and load")
    args = parser.parse_args(argv)

    server = None
    endpoint = args.endpoint
    if not endpoint:
        server = make_server("127.0.0.1", 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        endpoint = f"http://127.0.0.1:{server.server_port}"

    try:
        summary = run_smoke(endpoint, args.pack)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
