"""Always-on warm server-side multi-role agent daemon (`teleion-warm-agent.service`).

Combines four authorized server-agent roles in one warm process:
1. Immediate no-queue responder (`/v1/warm/status`, `/v1/warm/respond`) recording transcripts afterward.
2. Bilateral agent-to-agent responder (`/bridge/*` peer channels and `/q/feedback` roadblock triage).
3. Operations & queue-wake agent (`tessera` + `herma` health checks and `eranos-worker` wake pokes).
4. Dual-principal queue maker (`muse-spark-1.3` + canary deciders) & independent checker (`muse-wonder-1.0`)
   enforcing strict principal, fine-tune, and training-data independence (`MUST-FOLLOW.md`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from urllib.parse import quote
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx

from .banned_words_guard import BannedWordsGuard, scrub_private_info
from .decider import bounded_decide as fabric_bounded_decide
from .decider import _bounded as fabric_bounded
from .decider import cost_of as fabric_cost_of
from .decider import default_decision as fabric_default_decision
from .decider import looks_secret as fabric_looks_secret
from .decider import reserve as fabric_reserve
from .decider import settle as fabric_settle
from .decider import next_routed_task as fabric_next_routed_task
from .canary_and_tuner import (
    LineageDescriptor,
    ModelCanaryRegistry,
    TunerLoop,
    verify_checker_independence,
)
from .grid_config import NodeGrid, load_warm_agent_grid
from .meta_client import ModelCallError, WarmMetaModelClient


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _append_jsonl_secure(path: Path, row: dict[str, Any], *, file_mode: int, dir_mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=dir_mode)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, file_mode)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _maker_json(res: dict[str, Any]) -> dict[str, Any] | None:
    try:
        parsed = json.loads(str(res["content"]))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def agent_name(variable: str) -> str:
    """Names come from the environment, so a copy never speaks as our agents."""
    name = os.environ.get(variable, "").strip()
    if not name:
        raise RuntimeError(f"set {variable} to your own agent name")
    return name


def refuse_unless_live() -> None:
    """This agent claims real Tasks and answers live channels, so a person must ask for that."""
    if os.environ.get("WARM_AGENT_LIVE") != "1":
        raise SystemExit("this agent touches production: set WARM_AGENT_LIVE=1 and your own endpoints to run it")
    for variable in ("WARM_AGENT_NAME", "WARM_AGENT_MAKER_NAME", "WARM_AGENT_CHECKER_NAME"):
        try:
            agent_name(variable)
        except RuntimeError as error:
            raise SystemExit(str(error)) from error


class WarmServerAgent:
    """Persistent warm server-side agent managing bilateral comms, operations, canary routing, and queue work."""

    def __init__(
        self,
        grid: NodeGrid,
        *,
        meta_client: WarmMetaModelClient | None = None,
        herma_transport: httpx.BaseTransport | None = None,
        tessera_transport: httpx.BaseTransport | None = None,
        state_dir_override: str | Path | None = None,
        credentials_dir_override: str | Path | None = None,
        loopback_port_override: int | None = None,
    ) -> None:
        self.grid = grid
        self.paths_cfg = grid.section("endpoints_and_paths")
        self.ops = grid.section("operational_constants")
        self.budget_cfg = grid.section("budget_and_rates")
        self.tuner_cfg = grid.section("tuner_policy")
        _, initial_cell = grid.resolve_regime_cell()
        timeout_sec = float(initial_cell["http_timeout_seconds"])

        self.state_dir = (
            Path(state_dir_override)
            if state_dir_override is not None
            else Path(str(self.paths_cfg["state_dir"]))
        )
        self.credentials_dir = (
            Path(credentials_dir_override)
            if credentials_dir_override is not None
            else Path(str(self.paths_cfg["credentials_dir"]))
        )
        self.wake_dir = (
            self.state_dir / "wake"
            if state_dir_override is not None
            else Path(str(self.paths_cfg["wake_dir"]))
        )
        self.telemetry_path = self.state_dir / str(self.paths_cfg["telemetry_log_file"])
        self.transcript_path = self.state_dir / str(self.paths_cfg["transcript_log_file"])
        self.trace_path = self.state_dir / str(self.paths_cfg["training_trace_file"])
        self.canary_path = self.state_dir / str(self.paths_cfg["canary_state_file"])

        self._routed_tried: set[str] = set()
        self.banned_guard = BannedWordsGuard(self.paths_cfg["banned_words_path"])
        self.canary_registry = ModelCanaryRegistry(grid, state_path=self.canary_path)
        self.tuner = TunerLoop(
            grid,
            banned_guard=self.banned_guard,
            trace_path=self.trace_path,
        )
        self.meta_client = meta_client or WarmMetaModelClient(
            grid,
            attempt_recorder=self._record_model_attempt,
        )

        self.herma_base_url = str(self.paths_cfg["herma_base_url"]).rstrip("/")
        self.tessera_base_url = str(self.paths_cfg["tessera_base_url"]).rstrip("/")
        self._herma_http = httpx.Client(
            base_url=self.herma_base_url,
            headers={"Accept": "application/json"},
            timeout=timeout_sec,
            transport=herma_transport or httpx.HTTPTransport(retries=0),
            trust_env=False,
        )
        self._tessera_http = httpx.Client(
            base_url=self.tessera_base_url,
            headers={"Accept": "application/json"},
            timeout=timeout_sec,
            transport=tessera_transport or httpx.HTTPTransport(retries=0),
            trust_env=False,
        )

        self.loopback_host = str(self.paths_cfg["loopback_host"])
        self.loopback_port = (
            int(loopback_port_override)
            if loopback_port_override is not None
            else int(self.paths_cfg["loopback_port"])
        )
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self.maker_identity: dict[str, str] = {}
        self.checker_identity: dict[str, str] = {}
        self.seen_feedback_ids: list[str] = []
        self.seen_bridge_items: list[str] = []
        self._preload_seen_transcript_keys()
        self.metrics: dict[str, int] = {
            "cycles": 0,
            "instant_responses": 0,
            "bilateral_replies": 0,
            "wake_pokes": 0,
            "maker_submissions": 0,
            "checker_verifications": 0,
            "model_attempts": 0,
            "idle_cycles": 0,
        }
        self.last_health: dict[str, Any] = {}

    def _record_model_attempt(self, row: dict[str, Any]) -> None:
        with self._lock:
            self.metrics["model_attempts"] += 1
        _append_jsonl_secure(
            self.telemetry_path,
            {"kind": "model_attempt", **row},
            file_mode=int(self.ops["owner_rw_file_mode_decimal"]),
            dir_mode=int(self.ops["owner_rwx_dir_mode_decimal"]),
        )

    def _log_event(self, kind: str, **fields: Any) -> None:
        _append_jsonl_secure(
            self.telemetry_path,
            {"at": _utc_now_iso(), "kind": kind, **fields},
            file_mode=int(self.ops["owner_rw_file_mode_decimal"]),
            dir_mode=int(self.ops["owner_rwx_dir_mode_decimal"]),
        )

    def _record_transcript(self, entry: dict[str, Any]) -> None:
        sanitized = dict(entry)
        if "prompt" in sanitized:
            sanitized["prompt"] = scrub_private_info(str(sanitized["prompt"]))
        if "reply" in sanitized:
            sanitized["reply"] = self.banned_guard.sanitize_visible_text(str(sanitized["reply"]))
        _append_jsonl_secure(
            self.transcript_path,
            {"at": _utc_now_iso(), **sanitized},
            file_mode=int(self.ops["owner_rw_file_mode_decimal"]),
            dir_mode=int(self.ops["owner_rwx_dir_mode_decimal"]),
        )

    def _preload_seen_transcript_keys(self) -> None:
        if not self.transcript_path.exists():
            return
        for raw_line in self.transcript_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            fb_id = item.get("feedback_id")
            if fb_id:
                self._remember_seen(self.seen_feedback_ids, str(fb_id))
            msg_key = item.get("bridge_msg_key")
            if msg_key:
                self._remember_seen(self.seen_bridge_items, str(msg_key))

    def _remember_seen(self, bucket: list[str], item_id: str) -> bool:
        if item_id in bucket:
            return False
        bucket.append(item_id)
        cap = int(self.ops["max_seen_ids_cache"])
        if len(bucket) > cap:
            del bucket[:-cap]
        return True

    def ensure_isolated_principals(self) -> tuple[LineageDescriptor, LineageDescriptor]:
        """Load or mint strictly separated maker and checker worker identities (`0600` files, `show_on_map=false`)."""
        self.maker_identity = self._load_or_mint_principal(
            filename=str(self.paths_cfg["maker_credential_file"]),
            agent_id=agent_name("WARM_AGENT_MAKER_NAME"),
            model_hint="muse-spark-1.3",
            focus_note="Always-on warm server maker and bilateral responder",
        )
        self.checker_identity = self._load_or_mint_principal(
            filename=str(self.paths_cfg["checker_credential_file"]),
            agent_id=agent_name("WARM_AGENT_CHECKER_NAME"),
            model_hint="muse-wonder-1.0",
            focus_note="Always-on independent warm server verifier",
        )
        maker_lineage = self.current_maker_lineage()
        checker_lineage = self.current_checker_lineage()
        ok, reason = verify_checker_independence(maker_lineage, checker_lineage)
        if not ok:
            raise PermissionError(f"Maker/checker independence check failed: {reason}")
        return maker_lineage, checker_lineage

    def current_maker_lineage(
        self,
        *,
        executed_model_id: str = "muse-spark-1.3",
        executed_adapter_id: str | None = None,
        executed_corpus_digest: str | None = None,
    ) -> LineageDescriptor:
        """Return truthful execution lineage strictly from the model/adapter that actually ran."""
        return LineageDescriptor(
            worker_uuid=str(self.maker_identity.get("worker_uuid") or ""),
            agent_id=str(self.maker_identity.get("agent_id") or agent_name("WARM_AGENT_MAKER_NAME")),
            model_id=executed_model_id,
            fine_tune_adapter_id=executed_adapter_id,
            training_data_digest=executed_corpus_digest,
        )

    def current_checker_lineage(self) -> LineageDescriptor:
        raw_anc = self.checker_identity.get("ancestor_adapter_ids")
        anc_tuple = (
            tuple(str(x) for x in raw_anc if str(x))
            if isinstance(raw_anc, (list, tuple, set, frozenset))
            else ()
        )
        raw_ex = self.checker_identity.get("training_example_ids")
        ex_tuple = (
            tuple(str(x) for x in raw_ex)
            if isinstance(raw_ex, (list, tuple, set, frozenset))
            else None
        )
        return LineageDescriptor(
            worker_uuid=str(self.checker_identity.get("worker_uuid") or ""),
            agent_id=str(self.checker_identity.get("agent_id") or agent_name("WARM_AGENT_CHECKER_NAME")),
            model_id="muse-wonder-1.0",
            fine_tune_adapter_id=self.checker_identity.get("fine_tune_adapter_id") or None,
            training_data_digest=self.checker_identity.get("training_data_digest") or None,
            ancestor_adapter_ids=anc_tuple,
            training_example_ids=ex_tuple,
        )

    def _load_or_mint_principal(
        self,
        *,
        filename: str,
        agent_id: str,
        model_hint: str,
        focus_note: str,
    ) -> dict[str, Any]:
        dir_mode = int(self.ops["owner_rwx_dir_mode_decimal"])
        file_mode = int(self.ops["owner_rw_file_mode_decimal"])
        self.credentials_dir.mkdir(parents=True, exist_ok=True, mode=dir_mode)
        cred_path = self.credentials_dir / filename
        existing = self.checker_identity if agent_id == agent_name("WARM_AGENT_CHECKER_NAME") else self.maker_identity
        extra_prov = {
            k: existing[k]
            for k in ("fine_tune_adapter_id", "training_data_digest", "ancestor_adapter_ids", "training_example_ids")
            if k in existing
        }
        if cred_path.exists():
            saved = json.loads(cred_path.read_text(encoding="utf-8"))
            if saved.get("worker_uuid") and saved.get("worker_token"):
                out: dict[str, Any] = {
                    "agent_id": str(saved["agent_id"]),
                    "worker_uuid": str(saved["worker_uuid"]),
                    "worker_token": str(saved["worker_token"]),
                }
                for k in ("fine_tune_adapter_id", "training_data_digest", "ancestor_adapter_ids", "training_example_ids"):
                    if k in saved:
                        out[k] = saved[k]
                out.update(extra_prov)
                return out

        ok_low = int(self.ops["http_ok_low"])
        ok_high = int(self.ops["http_ok_high"])
        resp = self._herma_http.post(
            "/q/register",
            json={
                "agent_id": agent_id,
                "mint_new": True,
                "show_on_map": False,
                "model_hint": model_hint,
                "harness_tier": "server_warm_agent",
                "focus_note": focus_note,
            },
        )
        if not (ok_low <= resp.status_code <= ok_high):
            raise RuntimeError(f"Failed to mint Herma worker credential for {agent_id}: HTTP {resp.status_code}")
        data = resp.json()
        prof = data.get("worker_profile") or {}
        record: dict[str, Any] = {
            "agent_id": str(prof.get("agent_id") or agent_id),
            "worker_uuid": str(prof.get("worker_uuid") or ""),
            "worker_token": str(data.get("worker_token") or ""),
        }
        if not record["worker_uuid"] or not record["worker_token"]:
            raise RuntimeError(f"Incomplete registration response for {agent_id}")
        tmp = cred_path.with_name(f".{cred_path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, file_mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, cred_path)
        record.update(extra_prov)
        return record

    def respond_immediately(
        self,
        *,
        prompt: str,
        peer_agent: str = "local_caller",
        channel_id: str = "instant-loopback",
        use_model: bool = False,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Answer immediately with no queue, recording the transcript and model attempt afterward."""
        started = time.monotonic()
        clean_prompt = scrub_private_info(prompt).strip()
        persona = self.tuner.select_persona(role="bilateral")
        used_model_id = "deterministic_warm_router"
        cost_usd = 0.0

        if use_model and clean_prompt:
            out = self.meta_client.complete(
                model_id="muse-spark-1.3",
                system_prompt=str(persona["system_directive"]),
                user_prompt=clean_prompt,
                max_tokens=max_tokens,
                temperature=0.0,
                caller_tag="instant_no_queue_responder",
            )
            reply_text = self.banned_guard.sanitize_visible_text(str(out["content"]))
            used_model_id = str(out["model_id"])
            cost_usd = float(out["cost_usd"])
        else:
            cell_id, _ = self.grid.resolve_regime_cell(idle_cycles=self.metrics["idle_cycles"])
            reply_text = self.banned_guard.sanitize_visible_text(
                f"Warm agent online (cell={cell_id}, generation={self.grid.generation}). "
                f"Received message from {peer_agent} ({len(clean_prompt)} chars) with zero queue wait."
            )

        elapsed = round(time.monotonic() - started, int(self.budget_cfg["usd_round_digits"]))
        with self._lock:
            self.metrics["instant_responses"] += 1
        self._record_transcript(
            {
                "mode": "instant_no_queue",
                "channel_id": channel_id,
                "peer_agent": peer_agent,
                "persona_id": str(persona["persona_id"]),
                "model_id": used_model_id,
                "prompt": clean_prompt,
                "reply": reply_text,
                "cost_usd": cost_usd,
                "elapsed_seconds": elapsed,
            }
        )
        return {
            "ok": True,
            "queued": False,
            "model_id": used_model_id,
            "persona_id": str(persona["persona_id"]),
            "reply": reply_text,
            "cost_usd": cost_usd,
            "elapsed_seconds": elapsed,
        }

    def run_operations_and_wake_check(self) -> dict[str, Any]:
        """Check Tessera & Herma health and immediately wake idle local Eranos workers when queues have ready work."""
        ok_low = int(self.ops["http_ok_low"])
        ok_high = int(self.ops["http_ok_high"])
        dir_mode = int(self.ops["owner_rwx_dir_mode_decimal"])
        file_mode = int(self.ops["owner_rw_file_mode_decimal"])
        wake_map: dict[str, str] = dict(self.paths_cfg.get("queue_wake_map") or {})

        summary: dict[str, Any] = {
            "tessera_ok": False,
            "herma_ok": False,
            "ready_total": 0,
            "woken_roles": [],
        }

        try:
            t_resp = self._tessera_http.get("/v1/health")
            if ok_low <= t_resp.status_code <= ok_high:
                t_body = t_resp.json()
                summary["tessera_ok"] = bool(t_body.get("ok", True))
                queues = t_body.get("queues") or {}
                queue_pairs: list[tuple[str, dict[str, Any]]] = []
                if isinstance(queues, dict):
                    queue_pairs = [(str(k), dict(v or {})) for k, v in queues.items()]
                elif isinstance(queues, list):
                    for q_entry in queues:
                        if isinstance(q_entry, dict):
                            q_counts = q_entry.get("counts") if isinstance(q_entry.get("counts"), dict) else q_entry
                            queue_pairs.append((str(q_entry.get("name") or ""), dict(q_counts or {})))
                total_ready = 0
                for q_name, q_stats in queue_pairs:
                    ready_n = int((q_stats or {}).get("ready") or 0)
                    total_ready += ready_n
                    if ready_n > 0 and q_name in wake_map:
                        role_name = str(wake_map[q_name])
                        self.wake_dir.mkdir(parents=True, exist_ok=True, mode=dir_mode)
                        wake_file = self.wake_dir / role_name
                        fd = os.open(wake_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, file_mode)
                        with os.fdopen(fd, "w", encoding="utf-8") as fh:
                            fh.write(_utc_now_iso() + "\n")
                        summary["woken_roles"].append(role_name)
                        with self._lock:
                            self.metrics["wake_pokes"] += 1
                summary["ready_total"] = total_ready
        except Exception as exc:
            summary["tessera_error"] = type(exc).__name__

        try:
            h_resp = self._herma_http.get("/v1/health")
            summary["herma_ok"] = ok_low <= h_resp.status_code <= ok_high
        except Exception as exc:
            summary["herma_error"] = type(exc).__name__

        self.last_health = summary
        return summary

    def handle_bilateral_communications(self, *, batch_limit: int) -> int:
        """Respond to peer agent messages on `/bridge/*` and newly filed worker roadblocks on `/q/feedback`."""
        ok_low = int(self.ops["http_ok_low"])
        ok_high = int(self.ops["http_ok_high"])
        min_chars = int(self.ops["min_substantive_feedback_chars"])
        prefix_len = int(self.ops["hex_digest_prefix_chars"])
        own_agents = {
            str(self.maker_identity.get("agent_id") or agent_name("WARM_AGENT_MAKER_NAME")),
            str(self.checker_identity.get("agent_id") or agent_name("WARM_AGENT_CHECKER_NAME")),
            agent_name("WARM_AGENT_NAME"),
        }
        replies_sent = 0

        # 1. Check default warm bridge channel + any active channels returned by `/bridge/threads`
        channels = [str(self.paths_cfg["default_bridge_channel"])]
        try:
            th_resp = self._herma_http.get("/bridge/threads")
            if ok_low <= th_resp.status_code <= ok_high:
                th_body = th_resp.json()
                for item in th_body.get("threads") or th_body.get("channels") or []:
                    cid = str((item.get("channel_id") if isinstance(item, dict) else item) or "").strip()
                    if cid and cid not in channels:
                        channels.append(cid)
        except Exception:
            pass

        for cid in channels:
            try:
                st_resp = self._herma_http.get(f"/bridge/{cid}/status")
                if not (ok_low <= st_resp.status_code <= ok_high):
                    continue
                st_body = st_resp.json()
                for msg in st_body.get("inbox") or []:
                    sender = str(msg.get("sender") or "")
                    target = str(msg.get("target_agent") or "*")
                    prompt_text = str(msg.get("prompt_text") or "").strip()
                    msg_key = f"{cid}:{msg.get('id')}:{msg.get('simhash64_hex')}"
                    if not prompt_text or sender in own_agents:
                        continue
                    if target not in {"*", agent_name("WARM_AGENT_NAME"), agent_name("WARM_AGENT_MAKER_NAME")}:
                        continue
                    if not self._remember_seen(self.seen_bridge_items, msg_key):
                        continue
                    reply_text, model_used, cost_usd, persona_id = self._generate_bilateral_reply(
                        peer_agent=sender,
                        context_kind="bridge_inbox",
                        text=prompt_text,
                    )
                    post_resp = self._herma_http.post(
                        f"/bridge/{cid}/inbox",
                        json={
                            "sender": agent_name("WARM_AGENT_NAME"),
                            "target_agent": sender or "*",
                            "prompts": [reply_text],
                        },
                    )
                    delivered = self._is_accepted_submission(post_resp)
                    if model_used != "deterministic_fallback":
                        self.tuner.record_outcome_and_trace(
                            persona_id=persona_id,
                            model_id=model_used,
                            role="bilateral",
                            prompt_text=prompt_text,
                            response_text=reply_text,
                            raw_quality_score=int(self.tuner_cfg["milli_scale"]) if delivered else 0,
                            cost_usd=cost_usd,
                            attempt_status="delivered_unreviewed" if delivered else "delivery_failed",
                            training_admitted=False,
                        )
                    if delivered:
                        replies_sent += 1
                        with self._lock:
                            self.metrics["bilateral_replies"] += 1
                        self._record_transcript(
                            {
                                "mode": "bridge_bilateral",
                                "bridge_msg_key": msg_key,
                                "channel_id": cid,
                                "peer_agent": sender,
                                "persona_id": persona_id,
                                "model_id": model_used,
                                "prompt": prompt_text,
                                "reply": reply_text,
                                "cost_usd": cost_usd,
                            }
                        )
            except Exception as exc:
                self._log_event("bridge_poll_error", channel_id=cid, error=type(exc).__name__)

        # 2. Triage newest peer roadblocks/questions from `/q/feedback` (1 bounded triage per cycle)
        try:
            fb_resp = self._herma_http.get("/q/feedback", params={"limit": batch_limit})
            if ok_low <= fb_resp.status_code <= ok_high:
                fb_body = fb_resp.json()
                items = fb_body.get("reports") or fb_body.get("feedback") or fb_body.get("items") or []
                for fb in items:
                    raw_str = json.dumps(fb, sort_keys=True)
                    fb_id = str(
                        fb.get("feedback_id")
                        or fb.get("object_key")
                        or fb.get("id")
                        or hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:prefix_len]
                    )
                    author = str(
                        fb.get("producer_agent")
                        or fb.get("agent_id")
                        or fb.get("worker_id")
                        or "external-worker"
                    )
                    obs = str(
                        fb.get("summary")
                        or fb.get("observation")
                        or fb.get("roadblocks")
                        or fb.get("questions")
                        or fb.get("message")
                        or ""
                    ).strip()
                    if author in own_agents or len(obs) < min_chars:
                        continue
                    if not self._remember_seen(self.seen_feedback_ids, fb_id):
                        continue
                    reply_text, model_used, cost_usd, persona_id = self._generate_bilateral_reply(
                        peer_agent=author,
                        context_kind="feedback_triage",
                        text=obs,
                    )
                    hub = str(self.paths_cfg["default_bridge_channel"])
                    post_resp = self._herma_http.post(
                        f"/bridge/{hub}/inbox",
                        json={
                            "sender": agent_name("WARM_AGENT_NAME"),
                            "target_agent": author,
                            "prompts": [f"[Re {fb_id}] {reply_text}"],
                        },
                    )
                    delivered = self._is_accepted_submission(post_resp)
                    if model_used != "deterministic_fallback":
                        self.tuner.record_outcome_and_trace(
                            persona_id=persona_id,
                            model_id=model_used,
                            role="bilateral",
                            prompt_text=obs,
                            response_text=reply_text,
                            raw_quality_score=int(self.tuner_cfg["milli_scale"]) if delivered else 0,
                            cost_usd=cost_usd,
                            attempt_status="delivered_unreviewed" if delivered else "delivery_failed",
                            training_admitted=False,
                        )
                    if delivered:
                        replies_sent += 1
                        with self._lock:
                            self.metrics["bilateral_replies"] += 1
                        self._record_transcript(
                            {
                                "mode": "feedback_bilateral_triage",
                                "feedback_id": fb_id,
                                "channel_id": hub,
                                "peer_agent": author,
                                "persona_id": persona_id,
                                "model_id": model_used,
                                "prompt": obs,
                                "reply": reply_text,
                                "cost_usd": cost_usd,
                            }
                        )
                    break
        except Exception as exc:
            self._log_event("feedback_poll_error", error=type(exc).__name__)

        return replies_sent

    def _is_accepted_submission(
        self,
        resp: httpx.Response,
        *,
        expected_object_key: str | None = None,
    ) -> bool:
        """Require HTTP 2xx, explicit JSON acceptance, and persisted `expected_object_key` when requested."""
        ok_low = int(self.ops["http_ok_low"])
        ok_high = int(self.ops["http_ok_high"])
        if not (ok_low <= resp.status_code <= ok_high):
            return False
        try:
            body = resp.json()
        except Exception:
            return False
        if not isinstance(body, dict):
            return False
        if body.get("ok") is not True:
            return False
        if body.get("stored") is False:
            return False
        if body.get("error"):
            return False
        if expected_object_key is not None:
            stored_items = body.get("stored_task_objects")
            if not isinstance(stored_items, list):
                stored_items = body.get("stored_objects")
            stored_keys: set[str] = set()
            if isinstance(stored_items, list):
                for item in stored_items:
                    if isinstance(item, dict) and item.get("object_key"):
                        stored_keys.add(str(item["object_key"]))
                    elif isinstance(item, str):
                        stored_keys.add(item)
            raw_keys = body.get("stored_object_keys")
            if isinstance(raw_keys, list):
                for key_item in raw_keys:
                    if key_item:
                        stored_keys.add(str(key_item))
            if expected_object_key not in stored_keys:
                return False
        return True

    def _generate_bilateral_reply(
        self,
        *,
        peer_agent: str,
        context_kind: str,
        text: str,
    ) -> tuple[str, str, float, str]:
        persona = self.tuner.select_persona(role="bilateral")
        persona_id = str(persona["persona_id"])
        max_chars = int(self.ops["max_prompt_chars"])
        user_msg = (
            f"Peer agent: {peer_agent}\n"
            f"Channel kind: {context_kind}\n"
            f"Observation or question:\n{scrub_private_info(text)[:max_chars]}\n\n"
            "Write a concise, accurate, directly actionable reply (2-4 sentences) addressing this agent's question or roadblock."
        )
        try:
            res = self.meta_client.complete(
                model_id="muse-spark-1.3",
                system_prompt=str(persona["system_directive"]),
                user_prompt=user_msg,
                temperature=0.0,
                caller_tag=f"bilateral_{context_kind}",
            )
            clean_reply = self.banned_guard.sanitize_visible_text(str(res["content"]).strip())
            return clean_reply, str(res["model_id"]), float(res["cost_usd"]), persona_id
        except ModelCallError:
            fallback = self.banned_guard.sanitize_visible_text(
                f"Acknowledged {context_kind} from {peer_agent}; logged for warm server triage and checking."
            )
            return fallback, "deterministic_fallback", 0.0, persona_id

    def _safe_log(self, kind: str, **fields: Any) -> None:
        try:
            self._log_event(kind, **fields)
        except Exception:  # noqa: BLE001 - a record problem must not stop the Task
            return

    def _reserve_for(self, model_id: str) -> str | None:
        """Only the larger model counts against the decider's budget: Muse Spark is what this step already spent. None means no room or no ledger."""
        if model_id == "muse-spark-1.3":
            return None
        cfg = self.grid.section("decider_routes")
        try:
            return fabric_reserve(
                Path(str(cfg["spend_file"])), float(cfg["wonder_hold_usd"]), float(cfg["budget_stop_usd"]), f"maker on {model_id}",
                float(cfg["ledger_lock_wait_seconds"]), float(cfg["ledger_lock_poll_seconds"]),
            )
        except Exception:  # noqa: BLE001 - treated as no room
            return None

    def _settle_for(self, hold_id: str | None, res: dict[str, Any] | None, model_id: str) -> None:
        if hold_id is None:
            return
        try:
            cfg = self.grid.section("decider_routes")
            hold = float(cfg["wonder_hold_usd"])
            fabric_settle(
                Path(str(cfg["spend_file"])), hold_id, fabric_cost_of(res, hold), f"maker on {model_id}",
                float(cfg["ledger_lock_wait_seconds"]), float(cfg["ledger_lock_poll_seconds"]),
            )
        except Exception as exc:  # noqa: BLE001 - the reservation stays counted, which errs on the safe side; the Task goes on
            self._safe_log("fabric_settle_failed", hold_id=hold_id, model=model_id, error=type(exc).__name__)

    def _read_task_object(self, key: str) -> dict[str, Any] | None:
        """Read one Task Object from our own shim, bounded in time and size. Anything off means None: the Task goes on without it."""
        try:
            cfg = self.grid.section("decider_routes")
            limit = float(cfg["tool_timeout_seconds"])

            def read() -> dict[str, Any] | None:
                until, cap, body = time.monotonic() + limit, int(cfg["tool_max_bytes"]), b""
                with self._herma_http.stream("GET", f"/q/object/{quote(key, safe='')}", timeout=limit) as found:
                    if not int(self.ops["http_ok_low"]) <= found.status_code <= int(self.ops["http_ok_high"]):
                        return None
                    for chunk in found.iter_bytes():
                        body += chunk
                        if len(body) > cap or time.monotonic() > until:
                            return None
                record = json.loads(body)
                keep = {"object_key": record.get("object_key"), "summary": record.get("summary"), "payload": record.get("payload")}
                text = json.dumps(keep)
                if fabric_looks_secret(text):
                    return None
                return {"object_key": keep["object_key"], "text": text[: int(cfg["tool_result_chars"])]}

            return fabric_bounded(read, limit)
        except Exception:  # noqa: BLE001 - never stops claimed work
            return None

    def _decide_for_task(self, task: dict[str, Any], task_id: str) -> dict[str, Any]:
        """The ordered route list in decider.py. Any failure here, the record included, means today's behavior."""
        try:
            cfg = self.grid.section("decider_routes")

            def search(query: str) -> list[dict[str, Any]]:
                until, cap, body = time.monotonic() + float(cfg["search_timeout_seconds"]), int(cfg["search_max_bytes"]), b""
                with self._herma_http.stream("POST", "/q/search", json={"q": query, "limit": int(cfg["search_limit"])}, timeout=float(cfg["search_timeout_seconds"])) as found:
                    if not int(self.ops["http_ok_low"]) <= found.status_code <= int(self.ops["http_ok_high"]):
                        return []
                    for chunk in found.iter_bytes():
                        body += chunk
                        if len(body) > cap or time.monotonic() > until:  # a trickling or huge reply is dropped
                            return []
                rows = json.loads(body).get("results") or []
                return [
                    {"id": r["id"], "title": str(r.get("title") or "")[: int(cfg["title_chars"])], "summary": " ".join(str(r.get("summary") or "").split())[: int(cfg["summary_chars"])]}
                    for r in rows
                    if r.get("artifact_kind") == "task_object" and r.get("id")
                ]

            decision = fabric_bounded_decide(task, cfg=cfg, meta_complete=self.meta_client.complete, search=search)
        except Exception as exc:  # noqa: BLE001 - never stops claimed work
            decision = fabric_default_decision(task_id, "the rule: the decider failed", [{"route": "decider", "outcome": "failed", "error": type(exc).__name__}])
        try:
            self._log_event(
                "fabric_decision",
                task_id=task_id,
                verb_kind=task.get("verb_kind"),
                model=decision.get("model"),
                model_route=decision.get("model_route"),
                route_object_id=decision.get("object_id"),
                object_route=decision.get("object_route"),
                tool=decision.get("tool"),
                adapter_sha256=decision.get("adapter_sha256"),
                fallback=decision.get("fallback"),
                why=scrub_private_info(str(decision.get("why") or "")),
                attempts=decision.get("attempts"),
                cost_usd=decision.get("cost_usd"),
                seconds=decision.get("seconds"),
            )
        except Exception:  # noqa: BLE001 - an unrecorded decision has no effect: today's behavior, and the Task goes on
            return fabric_default_decision(task_id, "the rule: the decision could not be recorded")
        return decision

    def execute_maker_step(self) -> bool:
        """Claim and complete one non-verification Task on Herma using `muse-spark-1.3` + canary routing."""
        if not self.maker_identity:
            self.ensure_isolated_principals()
        ok_low = int(self.ops["http_ok_low"])
        ok_high = int(self.ops["http_ok_high"])
        max_prompt = int(self.ops["max_prompt_chars"])
        max_summary = int(self.ops["max_summary_chars"])

        claim_params = {
            "agent_id": self.maker_identity["agent_id"],
            "worker_uuid": self.maker_identity["worker_uuid"],
            "step_mode": "atomic_build_step",
            "show_on_map": "false",
        }
        # A Task with an audited fine-tuned pick goes first, once; if that claim comes back empty, the next cycle claims as usual.
        routed = fabric_next_routed_task(Path(str(self.grid.section("decider_routes")["fine_tune_routes_file"])), self._routed_tried)
        if routed:
            self._routed_tried.add(routed)
            claim_params["task_id"] = routed
        claim_resp = self._herma_http.get(
            "/q/claim",
            params=claim_params,
            headers={
                "X-Herma-Worker-Token": self.maker_identity["worker_token"],
                "X-Herma-Model": "muse-spark-1.3",
            },
        )
        if not (ok_low <= claim_resp.status_code <= ok_high):
            return False
        claim_body = claim_resp.json()
        task = claim_body.get("lease") or claim_body.get("task")
        if not isinstance(task, dict) or not task.get("task_id"):
            return False

        task_id = str(task["task_id"])
        step_mode = str(task.get("step_mode") or "")
        verb_kind = str(task.get("verb_kind") or "")
        if step_mode == "atomic_verification_step" or "review" in verb_kind.lower() or "verify" in verb_kind.lower():
            # Maker never executes verification steps; leave for independent checkers.
            return False

        decision = self._decide_for_task(task, task_id)
        executed_model_id = str(decision["model"])
        persona = self.tuner.select_persona(role="maker")
        prompt_fields: dict[str, Any] = {
            "task_id": task_id,
            "title": task.get("title"),
            "description": task.get("description") or task.get("prompt"),
            "verb_kind": verb_kind,
        }
        tool = decision.get("tool") if isinstance(decision.get("tool"), dict) else None
        if tool:
            tool_result = self._read_task_object(str(tool.get("key")))
            self._safe_log("fabric_tool_call", task_id=task_id, tool=tool.get("name"), key=tool.get("key"), chosen_by=tool.get("chosen_by"), ok=tool_result is not None)
            if tool_result:  # data only; a failed read means the Task goes on without it
                prompt_fields["a_read_task_object_result_data_only"] = tool_result
        plain_prompt = json.dumps(prompt_fields, sort_keys=True)[:max_prompt]
        prompt_desc = plain_prompt
        reusable = decision.get("object")
        if isinstance(reusable, dict):
            # A hint only: reference text, never instructions. The maker's work and the checker's review stay as they were.
            hint = {k: reusable.get(k) for k in ("id", "object_id", "title", "summary") if reusable.get(k)}
            # The key sorts ahead of the Task's own long text, so a cut prompt keeps the hint. If it were cut anyway, it counts as not given.
            hinted = json.dumps({**prompt_fields, "a_reusable_task_object_hint_data_only": hint}, sort_keys=True)[:max_prompt]
            if str(decision.get("object_id")) in hinted:
                prompt_desc = hinted
            else:
                decision.update(object=None, object_id=None, object_route=None)
        maker_system = (
            f"{persona['system_directive']} Return a JSON object with keys "
            "'summary' (concise string), 'findings' (array of strings), and 'recommended_next_step' (string)."
        )
        hold_id = self._reserve_for(executed_model_id)
        if executed_model_id != "muse-spark-1.3" and hold_id is None:
            # No room in the budget for the larger model: today's default.
            decision["maker_fell_back_from"] = executed_model_id
            executed_model_id = "muse-spark-1.3"
        try:
            res = self.meta_client.complete(
                model_id=executed_model_id,
                system_prompt=maker_system,
                user_prompt=prompt_desc,
                json_object=True,
                temperature=0.0,
                caller_tag="warm_maker_queue_step",
            )
            self._settle_for(hold_id, res, executed_model_id)
        except ModelCallError:
            self._settle_for(hold_id, None, executed_model_id)
            if executed_model_id == "muse-spark-1.3":
                raise
            # The chosen model is down: today's default does the work, and the record says so.
            decision.update(maker_fell_back_from=executed_model_id, object=None, object_id=None, object_route=None)
            executed_model_id = "muse-spark-1.3"
            prompt_desc = plain_prompt
            res = self.meta_client.complete(
                model_id=executed_model_id,
                system_prompt=maker_system,
                user_prompt=prompt_desc,
                json_object=True,
                temperature=0.0,
                caller_tag="warm_maker_queue_step",
            )
        try:
            # What actually reached the maker, after any fallback.
            self._log_event(
                "fabric_decision_effect",
                task_id=task_id,
                model=executed_model_id,
                object_id=decision.get("object_id"),
                object_route=decision.get("object_route"),
            )
        except Exception:  # noqa: BLE001 - the record of a finished call must not stop the Task
            self._record_model_attempt({"caller_tag": "fabric_decision_effect", "outcome": "record_failed", "task_id": task_id})
        maker_lineage = self.current_maker_lineage(
            executed_model_id=executed_model_id,
            executed_adapter_id=None,
            executed_corpus_digest=None,
        )
        parsed_out = _maker_json(res)
        if parsed_out is None and executed_model_id == "muse-spark-1.3":
            # Moving up the cost ladder: the cheap answer can't be read, so the larger model tries once. Any failure keeps the cheap answer.
            try:  # on the record before the call; if that can't be written, no move up and the cheap answer stands
                self._log_event("fabric_moving_up", task_id=task_id, from_model=executed_model_id, to_model="muse-wonder-1.0")
                up_hold = self._reserve_for("muse-wonder-1.0")
            except Exception:  # noqa: BLE001
                up_hold = None
            if up_hold is not None:
                try:
                    up = self.meta_client.complete(
                        model_id="muse-wonder-1.0",
                        system_prompt=maker_system,
                        user_prompt=prompt_desc,
                        json_object=True,
                        temperature=0.0,
                        caller_tag="warm_maker_moved_up",
                    )
                    self._settle_for(up_hold, up, "muse-wonder-1.0")
                    self._safe_log("fabric_moved_up", task_id=task_id, from_model=executed_model_id, to_model="muse-wonder-1.0", readable=_maker_json(up) is not None)
                    if _maker_json(up) is not None:
                        res, executed_model_id, parsed_out = up, "muse-wonder-1.0", _maker_json(up)
                except ModelCallError:
                    self._settle_for(up_hold, None, "muse-wonder-1.0")
                    self._safe_log("fabric_moved_up", task_id=task_id, from_model=executed_model_id, to_model="muse-wonder-1.0", readable=False)
        if parsed_out is None:
            parsed_out = {"summary": str(res["content"])[:max_summary]}

        summary_clean = self.banned_guard.sanitize_visible_text(
            str(parsed_out.get("summary") or f"Completed {task_id}")
        )[:max_summary]
        object_key = f"warm_artifact_{task_id}"
        sub_payload = {
            "agent_id": self.maker_identity["agent_id"],
            "worker_uuid": self.maker_identity["worker_uuid"],
            "task_id": task_id,
            "lease_epoch": task.get("lease_epoch") or claim_body.get("lease_epoch"),
            "summary": summary_clean,
            "task_objects": [
                {
                    "object_key": object_key,
                    "summary": summary_clean,
                    "payload": {
                        "summary": summary_clean,
                        "findings": parsed_out.get("findings") or [],
                        "recommended_next_step": parsed_out.get("recommended_next_step") or "",
                        "decision": {
                            "model": executed_model_id,
                            "model_route": decision.get("model_route"),
                            "object_id": decision.get("object_id"),
                            "object_route": decision.get("object_route"),
                        },
                        "producer_lineage": {
                            "worker_uuid": maker_lineage.worker_uuid,
                            "agent_id": maker_lineage.agent_id,
                            "model_id": maker_lineage.model_id,
                            "fine_tune_adapter_id": maker_lineage.fine_tune_adapter_id,
                            "training_data_digest": maker_lineage.training_data_digest,
                        },
                    },
                }
            ],
        }
        sub_resp = self._herma_http.post(
            "/q/submit",
            headers={
                "X-Herma-Worker-Token": self.maker_identity["worker_token"],
                "X-Herma-Model": executed_model_id,
            },
            json=sub_payload,
        )
        ok = self._is_accepted_submission(sub_resp, expected_object_key=object_key)
        # Never credit a fine-tuned candidate unless that candidate's endpoint was actually invoked.
        self.tuner.record_outcome_and_trace(
            persona_id=str(persona["persona_id"]),
            model_id=executed_model_id,
            role="maker",
            prompt_text=prompt_desc,
            response_text=summary_clean,
            raw_quality_score=int(self.tuner_cfg["milli_scale"]) if ok else 0,
            cost_usd=float(res["cost_usd"]),
            task_id=task_id,
            attempt_status="submitted_and_stored" if ok else "submission_rejected",
            training_admitted=False,
        )
        if ok:
            with self._lock:
                self.metrics["maker_submissions"] += 1
        return ok

    def execute_checker_step(self) -> bool:
        """Claim and independently verify one verification Task produced by a strictly independent maker."""
        if not self.checker_identity:
            self.ensure_isolated_principals()
        ok_low = int(self.ops["http_ok_low"])
        ok_high = int(self.ops["http_ok_high"])
        max_prompt = int(self.ops["max_prompt_chars"])
        max_summary = int(self.ops["max_summary_chars"])

        claim_resp = self._herma_http.get(
            "/q/claim",
            params={
                "agent_id": self.checker_identity["agent_id"],
                "worker_uuid": self.checker_identity["worker_uuid"],
                "step_mode": "atomic_verification_step",
                "show_on_map": "false",
            },
            headers={
                "X-Herma-Worker-Token": self.checker_identity["worker_token"],
                "X-Herma-Model": "muse-wonder-1.0",
            },
        )
        if not (ok_low <= claim_resp.status_code <= ok_high):
            return False
        claim_body = claim_resp.json()
        task = claim_body.get("lease") or claim_body.get("task")
        if not isinstance(task, dict) or not task.get("task_id"):
            return False

        target_obj = str(task.get("target_object_key") or task.get("object_key") or "").strip()
        if not target_obj:
            self._log_event(
                "checker_refused_missing_target",
                task_id=str(task["task_id"]),
            )
            return False

        producer_meta = task.get("producer_lineage") or {}
        producer_uuid = str(task.get("producer_worker_uuid") or producer_meta.get("worker_uuid") or "").strip()
        producer_agent = str(task.get("producer_agent_id") or producer_meta.get("agent_id") or "").strip()
        if not producer_uuid:
            self._log_event(
                "checker_refused_unknown_producer",
                task_id=str(task["task_id"]),
            )
            return False

        raw_prod_anc = (
            producer_meta.get("ancestor_adapter_ids")
            if "ancestor_adapter_ids" in producer_meta
            else task.get("producer_ancestor_adapter_ids")
        )
        prod_anc = (
            tuple(str(x) for x in raw_prod_anc if str(x))
            if isinstance(raw_prod_anc, (list, tuple, set, frozenset))
            else ()
        )
        raw_prod_ex = (
            producer_meta.get("training_example_ids")
            if "training_example_ids" in producer_meta
            else task.get("producer_training_example_ids")
        )
        prod_ex = (
            tuple(str(x) for x in raw_prod_ex)
            if isinstance(raw_prod_ex, (list, tuple, set, frozenset))
            else None
        )

        producer_lineage = LineageDescriptor(
            worker_uuid=producer_uuid,
            agent_id=producer_agent,
            model_id=str(producer_meta.get("model_id") or "external-model"),
            fine_tune_adapter_id=producer_meta.get("fine_tune_adapter_id"),
            training_data_digest=producer_meta.get("training_data_digest"),
            ancestor_adapter_ids=prod_anc,
            training_example_ids=prod_ex,
        )
        checker_lineage = self.current_checker_lineage()
        indep_ok, indep_reason = verify_checker_independence(
            producer_lineage,
            checker_lineage,
            require_provenance_attestation=True,
        )
        if not indep_ok or producer_lineage.worker_uuid == self.maker_identity.get("worker_uuid"):
            # Strictly refuse self-review, same-machine maker review, overlapping examples, or unattested provenance
            self._log_event(
                "checker_refused_non_independent_target",
                task_id=str(task["task_id"]),
                reason=indep_reason,
            )
            return False

        persona = self.tuner.select_persona(role="checker")
        prompt_desc = json.dumps(task, sort_keys=True)[:max_prompt]
        res = self.meta_client.complete(
            model_id="muse-wonder-1.0",
            system_prompt=(
                f"{persona['system_directive']} Return JSON with keys "
                "'verdict' ('CONFIRMED' or 'NEEDS_REVISION'), 'quality_milli' (0..1000 integer), and 'summary' (string)."
            ),
            user_prompt=prompt_desc,
            json_object=True,
            temperature=0.0,
            caller_tag="warm_checker_verification_step",
        )
        try:
            verdict_obj = json.loads(str(res["content"]))
        except json.JSONDecodeError:
            verdict_obj = None

        raw_verdict = str((verdict_obj or {}).get("verdict") or "").strip().upper() if isinstance(verdict_obj, dict) else ""
        raw_qm = (verdict_obj or {}).get("quality_milli") if isinstance(verdict_obj, dict) else None
        valid_verdicts = {"CONFIRMED", "PASS", "APPROVED", "NEEDS_REVISION", "REJECTED", "FAIL"}
        validated_qm = self.tuner.validate_milli_score(raw_qm)
        if not isinstance(verdict_obj, dict) or raw_verdict not in valid_verdicts or validated_qm is None:
            self.tuner.record_outcome_and_trace(
                persona_id=str(persona["persona_id"]),
                model_id="muse-wonder-1.0",
                role="checker",
                prompt_text=prompt_desc,
                response_text=str(res["content"])[:max_summary],
                raw_quality_score=0,
                cost_usd=float(res["cost_usd"]),
                maker_checker_independent=indep_ok,
                task_id=str(task["task_id"]),
                attempt_status="malformed_checker_output",
                training_admitted=False,
                target_verdict=None,
                delivery_status="not_submitted",
                checker_correctness="incorrect",
            )
            return False

        quality_milli = validated_qm
        verdict = "CONFIRMED" if raw_verdict in {"CONFIRMED", "PASS", "APPROVED"} else "NEEDS_REVISION"
        summary_clean = self.banned_guard.sanitize_visible_text(
            str(verdict_obj.get("summary") or f"Independent check {verdict} ({quality_milli}/1000)")
        )[:max_summary]

        evaluations = [
            {
                "object_key": target_obj,
                "verdict": verdict,
                "quality_milli": quality_milli,
                "score": quality_milli,
                "note": summary_clean,
            }
        ]
        sub_resp = self._herma_http.post(
            "/q/submit",
            headers={
                "X-Herma-Worker-Token": self.checker_identity["worker_token"],
                "X-Herma-Model": "muse-wonder-1.0",
            },
            json={
                "agent_id": self.checker_identity["agent_id"],
                "worker_uuid": self.checker_identity["worker_uuid"],
                "task_id": str(task["task_id"]),
                "lease_epoch": task.get("lease_epoch") or claim_body.get("lease_epoch"),
                "summary": summary_clean,
                "evaluations": evaluations,
            },
        )
        ok = self._is_accepted_submission(sub_resp)
        assessed_correctness = str(task.get("assessed_checker_correctness") or "unknown")
        if assessed_correctness not in {"correct", "incorrect", "unknown"}:
            assessed_correctness = "unknown"
        self.tuner.record_outcome_and_trace(
            persona_id=str(persona["persona_id"]),
            model_id="muse-wonder-1.0",
            role="checker",
            prompt_text=prompt_desc,
            response_text=summary_clean,
            raw_quality_score=quality_milli if ok else 0,
            cost_usd=float(res["cost_usd"]),
            maker_checker_independent=indep_ok,
            task_id=str(task["task_id"]),
            attempt_status="verified_and_stored" if ok else "submission_rejected",
            training_admitted=ok and (verdict == "CONFIRMED"),
            target_verdict=verdict,
            delivery_status="accepted" if ok else "rejected",
            checker_correctness=assessed_correctness,
        )
        if ok:
            with self._lock:
                self.metrics["checker_verifications"] += 1
        return ok

    def run_single_cycle(self) -> dict[str, Any]:
        """Run one complete warm daemon cycle across operations, bilateral comms, and maker/checker work."""
        cycle_start = time.monotonic()
        self.ensure_isolated_principals()
        health = self.run_operations_and_wake_check()
        ready_total = int(health.get("ready_total") or 0)
        cell_id, cell = self.grid.resolve_regime_cell(
            ready_count=ready_total,
            idle_cycles=self.metrics["idle_cycles"],
        )

        bilateral_count = 0
        if cell.get("enable_bilateral_responder", True):
            bilateral_count = self.handle_bilateral_communications(
                batch_limit=int(cell["feedback_batch_limit"])
            )

        maker_did_work = False
        checker_did_work = False
        claim_stride = max(1, int(self.ops.get("queue_claim_every_n_cycles", 1)))
        should_claim_this_cycle = (self.metrics["cycles"] % claim_stride) == 0
        if cell.get("enable_queue_claiming", True) and should_claim_this_cycle:
            try:
                maker_did_work = self.execute_maker_step()
            except ModelCallError as exc:
                self._log_event("maker_model_unavailable", error=str(exc))
            except Exception as exc:
                self._log_event("maker_step_error", error=type(exc).__name__)

            try:
                checker_did_work = self.execute_checker_step()
            except ModelCallError as exc:
                self._log_event("checker_model_unavailable", error=str(exc))
            except Exception as exc:
                self._log_event("checker_step_error", error=type(exc).__name__)

        did_any = (bilateral_count > 0) or maker_did_work or checker_did_work or bool(health.get("woken_roles"))
        with self._lock:
            self.metrics["cycles"] += 1
            if did_any:
                self.metrics["idle_cycles"] = 0
            else:
                self.metrics["idle_cycles"] += 1

        elapsed = round(time.monotonic() - cycle_start, int(self.budget_cfg["usd_round_digits"]))
        regime_label = "high_backlog" if ready_total >= int(self.grid.regimes["high_backlog_ready_threshold"]) else "default"
        self.grid.cost_ledger.record(
            regime=regime_label,
            cell_id=cell_id,
            latency_seconds=elapsed,
            cost_usd=0.0,
            verified_ok=bool(health.get("herma_ok", True)),
        )
        report = {
            "ok": True,
            "cell_id": cell_id,
            "poll_interval_seconds": int(cell["poll_interval_seconds"]),
            "health": health,
            "bilateral_replies": bilateral_count,
            "maker_did_work": maker_did_work,
            "checker_did_work": checker_did_work,
            "elapsed_seconds": elapsed,
        }
        self._log_event("warm_cycle_heartbeat", **report)
        return report

    def status_snapshot(self) -> dict[str, Any]:
        cell_id, cell = self.grid.resolve_regime_cell(
            ready_count=int(self.last_health.get("ready_total") or 0),
            idle_cycles=self.metrics["idle_cycles"],
        )
        return {
            "ok": True,
            "service": agent_name("WARM_AGENT_NAME"),
            "grid_id": self.grid.grid_id,
            "grid_generation": self.grid.generation,
            "active_cell_id": cell_id,
            "active_cell": cell,
            "maker_agent_id": self.maker_identity.get("agent_id"),
            "checker_agent_id": self.checker_identity.get("agent_id"),
            "maker_checker_distinct": bool(
                self.maker_identity.get("worker_uuid")
                and self.checker_identity.get("worker_uuid")
                and self.maker_identity.get("worker_uuid") != self.checker_identity.get("worker_uuid")
            ),
            "metrics": dict(self.metrics),
            "last_health": dict(self.last_health),
            "spend_ledger": self.meta_client.ledger.read_snapshot(),
            "canary_registry": self.canary_registry.snapshot(),
            "tuner_posteriors": dict(self.tuner.posteriors),
        }

    def start_loopback_server(self) -> int:
        """Start the local instant no-queue HTTP responder thread and return the bound port."""
        agent_ref = self
        ok_code = int(self.ops["http_ok_low"])
        bad_code = int(self.ops["http_bad_request"])
        not_found_code = int(self.ops["http_not_found"])
        err_code = int(self.ops["http_server_error"])

        class _WarmHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send_json(self, code: int, payload: dict[str, Any]) -> None:
                raw = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                if self.path in {"/v1/warm/status", "/healthz"}:
                    self._send_json(ok_code, agent_ref.status_snapshot())
                else:
                    self._send_json(not_found_code, {"ok": False, "error": "not_found"})

            def do_POST(self) -> None:
                if self.path != "/v1/warm/respond":
                    self._send_json(not_found_code, {"ok": False, "error": "not_found"})
                    return
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json(bad_code, {"ok": False, "error": "invalid_json"})
                    return
                try:
                    out = agent_ref.respond_immediately(
                        prompt=str(body.get("prompt") or ""),
                        peer_agent=str(body.get("peer_agent") or "local_caller"),
                        channel_id=str(body.get("channel_id") or "instant-loopback"),
                        use_model=bool(body.get("use_model", False)),
                        max_tokens=int(body["max_tokens"]) if "max_tokens" in body and body["max_tokens"] is not None else None,
                    )
                    self._send_json(ok_code, out)
                except Exception as exc:
                    self._send_json(err_code, {"ok": False, "error": type(exc).__name__})

        self._server = ThreadingHTTPServer((self.loopback_host, self.loopback_port), _WarmHandler)
        bound_port = int(self._server.server_address[1])
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name="warm-loopback-http",
            daemon=True,
        )
        self._server_thread.start()
        return bound_port

    def stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self._herma_http.close()
        self._tessera_http.close()
        self.meta_client.close()

    def serve_forever(self, *, max_cycles: int | None = None) -> None:
        self.start_loopback_server()
        cycles_done = 0
        try:
            while not self._stop_event.is_set():
                report = self.run_single_cycle()
                cycles_done += 1
                if max_cycles is not None and cycles_done >= max_cycles:
                    break
                wait_sec = float(report.get("poll_interval_seconds") or 1.0)
                self._stop_event.wait(timeout=wait_sec)
        finally:
            self.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Teleion Fabric always-on warm server agent")
    parser.add_argument("--grid", default=None, help="Path to warm_agent_grid.json")
    parser.add_argument("--once", action="store_true", help="Run a single warm cycle and exit")
    args = parser.parse_args(argv)
    refuse_unless_live()

    grid = load_warm_agent_grid(args.grid)
    agent = WarmServerAgent(grid)

    def _handle_sig(_signum: int, _frame: Any) -> None:
        agent._stop_event.set()

    signal.signal(signal.SIGTERM, _handle_sig)
    signal.signal(signal.SIGINT, _handle_sig)

    if args.once:
        agent.run_single_cycle()
        agent.stop()
        return 0

    agent.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
