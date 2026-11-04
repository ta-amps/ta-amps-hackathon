"""Publishing checked results to the shim's public queue, so `/q/search` and `/q/object` can find them."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

SHIM = os.environ.get("OMNINODE_SHIM_URL", "https://shim.teleionlabs.com")


class Shim:
    def __init__(self, agent_id: str, cred_path: Path, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(base_url=SHIM, timeout=60, trust_env=False, headers={"User-Agent": "teleion-fabric-omninode/1"})
        self.agent_id = agent_id
        self.cred_path = cred_path

    def identity(self) -> dict[str, str]:
        if self.cred_path.exists():
            return json.loads(self.cred_path.read_text(encoding="utf-8"))
        r = self.http.post("/q/register", json={"agent_id": self.agent_id, "mint_new": True, "show_on_map": False,
                                                "model_hint": "muse-spark-1.3", "harness_tier": "server_omninode",
                                                "focus_note": "feed maintenance OmniNode"})
        r.raise_for_status()
        data = r.json()
        record = {"agent_id": str(data["worker_profile"]["agent_id"]), "worker_uuid": str(data["worker_profile"]["worker_uuid"]),
                  "worker_token": str(data["worker_token"])}
        fd = os.open(self.cred_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(record))
        return record

    def publish(self, objects: dict[str, dict[str, Any]], summary: str, idempotency_key: str) -> dict[str, Any]:
        """Submit, then read each object back: a 200 alone does not mean it was stored."""
        who = self.identity()
        rows = [{"object_key": key, **obj} for key, obj in objects.items()]
        r = self.http.post("/q/submit", headers={"X-Herma-Worker-Token": who["worker_token"], "X-Herma-Model": "muse-spark-1.3"},
                           json={"agent_id": who["agent_id"], "worker_uuid": who["worker_uuid"], "task_id": "self_seed",
                                 "idempotency_key": idempotency_key, "summary": summary[:600], "task_objects": rows})
        readable = [key for key in objects if self.http.get(f"/q/object/{key}").status_code == 200]
        return {"status": r.status_code, "ok": r.status_code < 300 and len(readable) == len(objects), "readable": sorted(readable), "sent": len(objects)}


def public_key(item_key: str) -> str:
    return "feed_" + re.sub(r"[^a-z0-9_-]+", "_", item_key.lower().replace("--", "_"))[:118]


def item_object(key: str, value: dict[str, Any], run_id: str, maker: str, checker: str, visible_hit: Any) -> dict[str, Any] | None:
    """Only a name and our own words that pass the visible word list go public; the third-party
    description stays in the Fabric record."""
    if visible_hit(value["full_name"]) or visible_hit(" ".join(value["topics"])):
        return None
    labels = value["labels"]
    summary = f"{labels['summary']} License {value['license']}. Source {value['source_url']}. Checked by a second worker."
    return {
        "summary": summary[:1500],
        "category": "feed_item",
        "search_hints": [labels["category"], value["license"], labels["determinism"], *labels["use_cases"], "omninode", "feed"],
        "payload": {
            "source": value["source_url"], "name": value["full_name"], "license": value["license"], "stars": value["stars"],
            "latest_release": value.get("latest_release"), "pushed_at": value["pushed_at"],
            "labels": {k: labels[k] for k in ("category", "determinism", "use_cases", "summary", "confidence_milli")},
            "labeled_by": {"model": value["maker_model"], "fine_tune": None, "run": run_id, "worker_key": maker},
            "checked_by": {"model": value["check"].get("audit_model"), "fine_tune": None, "worker_key": checker, "verdict": value["check"]["verdict"]},
            "record": f"fabric store omninode.feed_items, key {key}",
        },
    }
