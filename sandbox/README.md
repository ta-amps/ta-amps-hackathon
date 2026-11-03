# One-Command Local Offline Developer Sandbox (`sandbox/`)

Run a complete local simulation of **Seed-Pack verification**, **Task Object (`noun`) storage & search**, **fenced Task (`verb`) leasing**, **`ContributorTierRefusedError` privacy enforcement**, and **independent verification (`verifier != builder`)** in one command -- using only the Python 3.12 standard library, with **zero Cloudflare credentials** and **zero external API keys**.

> **Architecture boundary:** Production task scheduling and storage authority belongs solely to **[Tessera](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine)**. This `sandbox/` package is an offline loopback simulator (`127.0.0.1` / Docker bridge) so open-source builders can author Seed Packs and test worker lifecycles locally in under 60 seconds.

## 1. Run with Docker Compose (3 containers, zero credentials)

From the repository root:

```bash
docker compose up --build --abort-on-container-exit
```

What `docker-compose.yml` launches:
1. **`tessera-local`** (`python3 -m sandbox.local_server --host 0.0.0.0 --port 8787`): Local SQLite-backed loopback simulator serving `/health` and `/mcp`.
2. **`seed-pack-verifier`** (`python3 -m sandbox.verify_pack templates/new-seed-pack`): Offline validator checking [`templates/new-seed-pack/`](../templates/new-seed-pack/README.md) schemas, Task Object roles, effect ceilings, and SHA-256 digests.
3. **`sample-worker-smoke`** (`python3 -m sandbox.worker_smoke --endpoint http://tessera-local:8787`): Connects to `tessera-local`, stores Task Objects, proves `muse-spark-contributor` is refused (`403 ContributorTierRefusedError`), drafts a brief as `worker-drafter` under the Standard-tier model label `muse-spark-1.3` (a label only; the simulator never calls a model), proves self-verification is refused (`403 SelfVerificationRefusedError`), and verifies the output as `worker-reviewer` with a 64-hex SHA-256 receipt.

## 2. Run Directly with Python (no Docker needed)

```bash
# Verify a seed pack folder offline:
python3 -m sandbox.verify_pack templates/new-seed-pack

# Run the full drafter + independent reviewer smoke test in-process:
python3 -m sandbox.worker_smoke

# Run the sandbox unit test suite:
python3 -m unittest discover -s sandbox -p 'test_*.py' -v
```
