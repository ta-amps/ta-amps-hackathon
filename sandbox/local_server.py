"""Local loopback developer sandbox server for offline Task and Task-Object testing.

Implements a lightweight SQLite-backed loopback HTTP simulator of the core
Task (verb) and Task-Object (noun) wire contract so developers can test Seed Packs
and worker harnesses locally without Cloudflare credentials or external API keys.

Boundary notice: Production work authority belongs solely to Tessera. This module
is strictly an offline local developer sandbox (`127.0.0.1` / Docker bridge).

Usage:
  python3 -m sandbox.local_server --host 127.0.0.1 --port 8787
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class ContributorTierRefusedError(PermissionError):
    """Raised when a caller attempts to use a contributor/training-shared model tier."""


class SelfVerificationRefusedError(PermissionError):
    """Raised when the same worker attempts to verify its own drafted task."""


# Default model label recorded on claims and verifications. A label only: the sandbox never calls a model.
DEFAULT_MODEL = "muse-spark-1.3"


def check_model_tier(model: str) -> None:
    if "contributor" in str(model or "").lower():
        raise ContributorTierRefusedError(
            f"ContributorTierRefusedError: model {model!r} is on a contributor tier and is deterministically refused"
        )


class SandboxEngine:
    """Thread-safe SQLite-backed store for local developer smoke tests."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS nouns (
                    store TEXT NOT NULL,
                    key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    value_json TEXT NOT NULL,
                    value_sha256 TEXT NOT NULL,
                    PRIMARY KEY (store, key)
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    lease_token TEXT,
                    builder_worker TEXT,
                    verifier_worker TEXT,
                    output_key TEXT,
                    receipt_sha256 TEXT
                );
                """
            )

    def store_put(self, store: str, key: str, value: Any) -> dict:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT version FROM nouns WHERE store = ? AND key = ?", (store, key)
            ).fetchone()
            version = (int(row["version"]) + 1) if row else 1
            self._conn.execute(
                "INSERT OR REPLACE INTO nouns (store, key, version, value_json, value_sha256) VALUES (?, ?, ?, ?, ?)",
                (store, key, version, canonical, digest),
            )
        return {"store": store, "key": key, "version": version, "value_sha256": digest}

    def store_get(self, store: str, key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT store, key, version, value_json, value_sha256 FROM nouns WHERE store = ? AND key = ?",
                (store, key),
            ).fetchone()
        if not row:
            return None
        return {
            "store": row["store"],
            "key": row["key"],
            "version": row["version"],
            "value": json.loads(row["value_json"]),
            "value_sha256": row["value_sha256"],
        }

    def search_nouns(self, query: str) -> list[dict]:
        needle = f"%{query.lower()}%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT store, key, version, value_sha256, value_json FROM nouns "
                "WHERE lower(key) LIKE ? OR lower(value_json) LIKE ? ORDER BY store, key LIMIT 25",
                (needle, needle),
            ).fetchall()
        return [
            {"store": r["store"], "key": r["key"], "version": r["version"], "value_sha256": r["value_sha256"]}
            for r in rows
        ]

    def create_task(self, kind: str, title: str) -> dict:
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO tasks (task_id, kind, title, status) VALUES (?, ?, ?, 'queued')",
                (task_id, kind, title),
            )
        return {"task_id": task_id, "kind": kind, "title": title, "status": "queued"}

    def claim_task(self, task_id: str, worker_id: str, model: str = DEFAULT_MODEL) -> dict:
        check_model_tier(model)
        lease = f"lease-{uuid.uuid4().hex[:12]}"
        with self._lock, self._conn:
            row = self._conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                raise KeyError(f"unknown task_id {task_id}")
            if row["status"] != "queued":
                raise ValueError(f"task {task_id} is {row['status']}, expected queued")
            self._conn.execute(
                "UPDATE tasks SET status = 'leased', lease_token = ?, builder_worker = ? WHERE task_id = ?",
                (lease, worker_id, task_id),
            )
        return {"task_id": task_id, "status": "leased", "lease_token": lease, "worker_id": worker_id}

    def submit_draft(self, task_id: str, lease_token: str, worker_id: str, output_key: str) -> dict:
        with self._lock, self._conn:
            row = self._conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row or row["lease_token"] != lease_token or row["builder_worker"] != worker_id:
                raise PermissionError("fenced lease token mismatch")
            self._conn.execute(
                "UPDATE tasks SET status = 'awaiting_verification', output_key = ? WHERE task_id = ?",
                (output_key, task_id),
            )
        return {"task_id": task_id, "status": "awaiting_verification", "output_key": output_key}

    def verify_task(self, task_id: str, verifier_worker: str, model: str = DEFAULT_MODEL) -> dict:
        check_model_tier(model)
        with self._lock, self._conn:
            row = self._conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row or row["status"] != "awaiting_verification":
                raise ValueError(f"task {task_id} is not awaiting_verification")
            if row["builder_worker"] == verifier_worker:
                raise SelfVerificationRefusedError(
                    "SelfVerificationRefusedError: verifier must differ from builder (verifier != builder)"
                )
            receipt_payload = json.dumps(
                {
                    "task_id": task_id,
                    "builder": row["builder_worker"],
                    "verifier": verifier_worker,
                    "output_key": row["output_key"],
                },
                sort_keys=True,
            )
            receipt_sha = hashlib.sha256(receipt_payload.encode("utf-8")).hexdigest()
            self._conn.execute(
                "UPDATE tasks SET status = 'verified', verifier_worker = ?, receipt_sha256 = ? WHERE task_id = ?",
                (verifier_worker, receipt_sha, task_id),
            )
        return {
            "task_id": task_id,
            "status": "verified",
            "builder_worker": row["builder_worker"],
            "verifier_worker": verifier_worker,
            "receipt_sha256": receipt_sha,
        }

    def dispatch(self, action: str, params: dict) -> Any:
        if action == "store_put":
            return self.store_put(params["store"], params["key"], params["value"])
        if action == "store_get":
            return self.store_get(params["store"], params["key"])
        if action == "search_nouns":
            return self.search_nouns(params.get("query", ""))
        if action == "create_task":
            return self.create_task(params["kind"], params["title"])
        if action == "claim_task":
            return self.claim_task(params["task_id"], params["worker_id"], params.get("model", DEFAULT_MODEL))
        if action == "submit_draft":
            return self.submit_draft(
                params["task_id"], params["lease_token"], params["worker_id"], params["output_key"]
            )
        if action == "verify_task":
            return self.verify_task(params["task_id"], params["verifier_worker"], params.get("model", DEFAULT_MODEL))
        raise ValueError(f"unsupported sandbox action: {action}")


def make_server(host: str = "127.0.0.1", port: int = 8787, engine: SandboxEngine | None = None) -> ThreadingHTTPServer:
    store_engine = engine or SandboxEngine()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def _send(self, code: int, body: dict) -> None:
            raw = json.dumps(body, sort_keys=True).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send(
                    200,
                    {
                        "ok": True,
                        "mode": "local_offline_developer_sandbox",
                        "production_authority": "tessera",
                    },
                )
                return
            self._send(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/mcp":
                self._send(404, {"ok": False, "error": "not_found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            try:
                result = store_engine.dispatch(payload["action"], payload.get("params") or {})
                self._send(200, {"ok": True, "result": result})
            except (ContributorTierRefusedError, SelfVerificationRefusedError, PermissionError) as exc:
                self._send(403, {"ok": False, "error": type(exc).__name__, "message": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._send(400, {"ok": False, "error": type(exc).__name__, "message": str(exc)})

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port)
    print(f"sandbox.local_server: listening on http://{args.host}:{server.server_port} (offline developer sandbox)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
