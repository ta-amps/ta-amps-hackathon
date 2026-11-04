"""Runtime protocol to real Fabric calls: spec, runs as Durable Tasks, heartbeats, spend ceiling, word screen."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eranos.model_client import Ledger, MetaModel
from tessera import NotFound
from tessera.client import Client, TaskSpec

RECORD_STORE = "eranos.instructions"  # public read: eranosforgood.org/api/nouns/<store>/<key>
ITEMS_STORE = "omninode.feed_items"
PREFIX = "omninode.feed-maintenance"
SPEC_KEY = f"{PREFIX}.spec"
GRID_KEY = f"{PREFIX}.grid"
LATEST_KEY = f"{PREFIX}.latest"
RUN_PREFIX = f"{PREFIX}.run."
DATASET_PREFIX = f"{PREFIX}.dataset."
PRODUCER = "surface:eranos"
NODE_ID = "omninode.feed-maintenance"
DAILY_CEILING_USD = 3.0
ALLOWED_MODELS = frozenset({"muse-spark-1.3", "muse-wonder-1.0"})
SHARED_LEDGER = Path.home() / ".local/state/eranos-worker/meta-spend.json"
NODE_LEDGER = Path.home() / ".local/state/eranos-worker/omninode-feed-spend.json"
BANNED_FILE = Path(
    os.environ.get(
        "BANNED_WORDS_FILE",
        str(Path(os.environ.get("TELEION_NOTES", "/nonexistent")) / "coordination-2026-10-31/rules/banned-words.json"),
    )
)


def utc_stamp(now: float | None = None) -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now if now is not None else time.time()))


def digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Screen:
    """The one shared word list. `always` and private names keep a third-party item out entirely;
    the visible-text list applies to what this node writes in its own words."""

    def __init__(self, path: Path = BANNED_FILE) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._always = [re.compile(p, re.I) for p in raw["always"]["patterns"]]
        self._visible = [re.compile(p, re.I) for p in raw["visible_text"]["patterns"]]
        self._visible += [
            re.compile(p, re.I) for p in raw["agent_apps_outside_models_page"]["patterns"]
        ]
        self._private = set(raw["private_names"]["sha256"])

    def _private_hit(self, text: str) -> bool:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return any(hashlib.sha256(t.encode()).hexdigest() in self._private for t in tokens)

    def blocked(self, text: str) -> bool:
        return self._private_hit(text) or any(p.search(text) for p in self._always)

    def visible_hit(self, text: str) -> bool:
        return self.blocked(text) or any(p.search(text) for p in self._visible)


class TwoLedgers:
    """The node's own $3 a UTC day inside the owner's shared ledger: a call must fit both, and both
    keep its reservation until the answer's real cost replaces it."""

    def __init__(self, shared: Ledger, node: Ledger) -> None:
        self.shared, self.node = shared, node

    def check(self, estimate: float) -> None:
        self.node.check(estimate)
        self.shared.check(estimate)

    def reserve(self, estimate: float) -> str:
        day = self.node.reserve(estimate)
        try:
            self.shared.reserve(estimate)
        except Exception:
            self.node.settle(0.0, reserved=estimate, day=day)
            raise
        return day

    def settle(self, cost: float, *, reserved: float = 0.0, day: str | None = None) -> dict[str, Any]:
        self.node.settle(cost, reserved=reserved, day=day)
        return self.shared.settle(cost, reserved=reserved, day=day)


def ledgers(shared: Path = SHARED_LEDGER, node: Path = NODE_LEDGER, ceiling: float = DAILY_CEILING_USD) -> TwoLedgers:
    return TwoLedgers(
        Ledger(shared, daily_usd=25.0, total_usd=150.0),
        Ledger(node, daily_usd=min(ceiling, DAILY_CEILING_USD), total_usd=150.0),
    )


def meta_model(model_id: str, catalog: dict[str, Any], ledger: Any, *, effort: str = "low") -> MetaModel:
    """Only Muse Spark 1.3 and Muse Wonder 1.0 through the Meta API, no fine-tune, no other provider."""
    if model_id not in ALLOWED_MODELS:
        raise ValueError(f"{model_id} is not a model this node may call")
    runtime = catalog["runtime"]
    return MetaModel(
        {
            "id": model_id,
            "model_display": runtime["display_by_id"][model_id],
            "base_url": "https://api.meta.ai/v1",
            "prices_usd_per_million": runtime["rates_usd_per_million_tokens"][model_id],
            "max_tokens": 1500,
            "reasoning_effort": effort,
        },
        ledger=ledger,
    )


class Heartbeat(threading.Thread):
    def __init__(self, beat: Callable[[], Any], seconds: float) -> None:
        super().__init__(daemon=True)
        self._beat, self._seconds = beat, max(5.0, seconds / 2)
        self._done = threading.Event()
        self.lost = threading.Event()
        self.beats = 0

    def run(self) -> None:
        while not self._done.wait(self._seconds):
            try:
                self._beat()
                self.beats += 1
            except Exception:  # noqa: BLE001 - a lost lease stops further writes, it is not fatal here
                self.lost.set()
                return

    def stop(self) -> None:
        self._done.set()


class Fabric:
    """The adapter: every call goes to real Teleion Fabric with this worker's own scoped key."""

    def __init__(self, url: str, key: str, label: str) -> None:
        self.client = Client(url, key=key, surface_id="eranos")
        self.label = label
        self.key_id = str(self.client._call("GET", "/v1/me").json()["key_id"])

    def enqueue(self, *, queue: str, task_id: str, kind: str, brief: dict[str, Any],
                visibility: str = "public_commons", depends_on: list[str] | None = None) -> str:
        spec = TaskSpec(
            queue=queue, task_id=task_id, kind=kind, effect_class="write-internal",
            producer_surface=PRODUCER, brief=brief, visibility_scope=visibility,
            depends_on=depends_on or [], tags=["omninode:feed-maintenance"],
        )
        return self.client.enqueue(spec, idempotency_key=task_id)

    def ready(self, queue: str, kind: str) -> list[dict[str, Any]]:
        """Ready Tasks of a kind this key may see: a read that claims nothing."""
        rows = self.client._call("GET", "/v1/verbs", params={"queue": queue, "status": "ready", "limit": 100}).json().get("verbs") or []
        return [dict(v) for v in rows if v.get("kind") == kind]

    def claim(self, queue: str, kind: str) -> Any:
        return self.client.claim(queue, self.label, kinds=[kind])

    def heartbeat(self, task_id: str, token: int) -> Any:
        return self.client.heartbeat(task_id, token)

    def submit(self, task_id: str, token: int, output: Any, *, ok: bool, error: str | None = None,
               report: dict[str, Any] | None = None) -> str:
        receipt = self.client.submit(task_id, token, output, idempotency_key=f"{task_id}:{token}",
                                     ok=ok, error=error, execution_report=report)
        return str(getattr(receipt, "receipt_hash", "") or getattr(receipt, "hash", ""))

    def get(self, store: str, key: str) -> tuple[Any, int] | None:
        try:
            record = self.client.get_record(store, key)
        except NotFound:
            return None
        return record.value, int(record.version)

    def put(self, store: str, key: str, value: Any, *, expected: int | None, tags: list[str]) -> int:
        saved = self.client.put_record(store, key, value, expected_version=expected, producer_surface=PRODUCER,
                                       visibility_scope="public_commons", tags=tags)
        return int(saved.version)

    def list(self, store: str, prefix: str = "", limit: int = 200) -> list[tuple[str, Any, int]]:
        rows = self.client.list_records(store, prefix=prefix, limit=limit)
        return [(r.key, r.value, int(r.version)) for r in rows]


def from_env(label: str) -> Fabric:
    return Fabric(os.environ["TESSERA_URL"], os.environ["TESSERA_KEY"], label)


def execution_report(role: str, worker: str, problem: str, solution: str, attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """The contract's report: the harness, every model attempt's tokens and cost, and a plain line."""
    models = sorted({str(a.get("model")) for a in attempts})
    cost = round(sum(float(a.get("cost_usd") or 0.0) for a in attempts), 6)
    return {
        "version": 1,
        "harness": {"name": "omninode-live", "version": "1", "role": role, "worker": worker, "tier": "standard" if attempts else None,
                    "cost_usd": cost, "payer": "operator's Meta key" if attempts else "no model call; no charge"},
        "model": {"provider": "meta", "ids": models, "attempts": len(attempts), "cost_usd": cost, "fine_tune": None} if attempts else None,
        "summaries": {"problem": problem[:4000], "solution": solution[:4000]},
        "usage": {
            "input_tokens": sum(int(a.get("input_tokens") or 0) for a in attempts),
            "output_tokens": sum(int(a.get("output_tokens") or 0) for a in attempts),
            "total_tokens": sum(int(a.get("input_tokens") or 0) + int(a.get("output_tokens") or 0) for a in attempts),
            "source": "Meta API response usage" if attempts else "no model was called; deterministic code only",
        },
    }
