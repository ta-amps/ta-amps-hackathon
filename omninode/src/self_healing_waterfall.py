"""Self-Troubleshooting, Self-Disabling Circuit Breaker & Protocol Waterfall Runtime.

Remediates all 16 real log and live-audit corner cases (CC-01 through CC-16):
- CC-01: /q/alternatives HTTP 404 -> 24h circuit cooldown + local 4-tier capability step-down
- CC-02: /q/leaderboard timeout -> 15m circuit cooldown + /q/pulse and /q/network waterfall
- CC-03: Semantic GraphQL/RPC HTTP 200 "errors" budget detection and circuit opening
- CC-04: Method-preserving 301/302/307/308 redirect resolver keeping POST + JSON body
- CC-05: Untrusted redirect domain Authorization and capability-header stripping
- CC-06: Automatic v19 -> v8 submit envelope schema waterfall on HTTP 400/422
- CC-07: Self-review co-lease guard (maker != checker) -> immediate /q/release handoff
- CC-08: Lease-budget batch clamping (batch_size <= (lease_ttl - margin) // est_task_sec)
- CC-09: Adaptive batch auto-halving (N -> N // 2) on MemoryError, OOM, HTTP 413, or timeout
- CC-10: /tmp TTL scratch garbage collector and RLIMIT_NOFILE concurrency clamp
- CC-11: Pre-flight nested evaluations and followup_tasks lifter to top-level envelope
- CC-12: Suffix-preserving object_key canonicalizer (object_id/object_name -> <= 64 chars)
- CC-13: Strict UTF-8 multi-byte payload gate + optional gzip compression
- CC-14: Strict acct.<tenant> private scope inheritance + explicit prog_lang + schema mirroring
- CC-15: Pinned upstream digest/verdict verifier + server clock-skew auto-calibrator
- CC-16: Poison-pill task quarantine + SIGTERM/SIGINT/atexit cooperative lease release
"""

from __future__ import annotations

import atexit
import copy
from datetime import datetime
import gzip
import json
import os
from pathlib import Path
import platform
import re
import resource
import secrets
import shutil
import signal
import time
from typing import Any, Callable, Mapping, Sequence
import urllib.error
import urllib.parse
import urllib.request

from src.omninode_grid_engine import DEFAULT_GRID_CONFIG_PATH, NodeGrid

CAPABILITY_TIERS: tuple[str, ...] = (
    "T1_dense_full",
    "T2_anchor_whitened_cpu",
    "T3_lexical_feature_hash",
    "T4_stdlib_minimal_http",
)


def is_trusted_redirect_host(hostname: str, trusted_suffixes: Sequence[str]) -> bool:
    """Checks exact host or subdomain match against trusted canonical suffixes."""
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        return False
    for raw_suffix in trusted_suffixes:
        suf = str(raw_suffix).strip().lower().lstrip(".")
        if host == suf or host.endswith(f".{suf}"):
            return True
    return False


def resolve_redirect_request_spec(
    *,
    method: str,
    src_url: str,
    dst_url: str,
    status_code: int,
    headers: Mapping[str, str],
    body: bytes | None,
    redirect_statuses: Sequence[int],
    trusted_suffixes: Sequence[str],
) -> dict[str, Any]:
    """Computes redirect method, headers, and body preservation across canonical domain hops."""
    upper_method = method.upper()
    src_host = urllib.parse.urlparse(src_url).hostname or ""
    dst_host = urllib.parse.urlparse(dst_url).hostname or ""
    both_trusted = is_trusted_redirect_host(src_host, trusted_suffixes) and (
        is_trusted_redirect_host(dst_host, trusted_suffixes)
    )

    sensitive_header_names = {
        "authorization",
        "cookie",
        "x-herma-worker-token",
        "proxy-authorization",
    }
    clean_headers: dict[str, str] = {}
    stripped_headers: list[str] = []
    for k, v in headers.items():
        kl = k.lower()
        if kl == "host":
            continue
        if not both_trusted and kl in sensitive_header_names:
            stripped_headers.append(k)
            continue
        clean_headers[k] = v

    if int(status_code) in {int(c) for c in redirect_statuses} and upper_method in (
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ):
        preserved_method = upper_method
        preserved_body = body
    else:
        preserved_method = upper_method
        preserved_body = body if upper_method not in ("GET", "HEAD") else None

    return {
        "url": dst_url,
        "method": preserved_method,
        "headers": clean_headers,
        "body": preserved_body,
        "both_hosts_trusted": both_trusted,
        "stripped_headers": stripped_headers,
    }


class MethodPreservingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """urllib redirect handler preserving POST + JSON body and stripping auth on untrusted hops."""

    def __init__(
        self,
        *,
        redirect_statuses: Sequence[int],
        trusted_suffixes: Sequence[str],
    ) -> None:
        super().__init__()
        self._redirect_statuses = tuple(int(c) for c in redirect_statuses)
        self._trusted_suffixes = tuple(str(s) for s in trusted_suffixes)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        merged_headers = dict(req.header_items())
        resolved_url = urllib.parse.urljoin(req.full_url, newurl)
        spec = resolve_redirect_request_spec(
            method=req.get_method(),
            src_url=req.full_url,
            dst_url=resolved_url,
            status_code=int(code),
            headers=merged_headers,
            body=req.data,
            redirect_statuses=self._redirect_statuses,
            trusted_suffixes=self._trusted_suffixes,
        )
        return urllib.request.Request(
            spec["url"],
            data=spec["body"],
            headers=spec["headers"],
            method=spec["method"],
        )


class LocalCapabilityLadder:
    """Zero-remote-dependency 4-tier local capability selection and step-down ladder."""

    def __init__(self, grid: NodeGrid) -> None:
        self._t1_ram = int(grid.protocol_constants["tier1_min_ram_mib"])
        self._t2_ram = int(grid.protocol_constants["tier2_min_ram_mib"])
        self._t3_ram = int(grid.protocol_constants["tier3_min_ram_mib"])

    def select_initial_tier(self, *, free_ram_mib: int, has_gpu: bool = False) -> str:
        if has_gpu or free_ram_mib >= self._t1_ram:
            return CAPABILITY_TIERS[0]
        if free_ram_mib >= self._t2_ram:
            return CAPABILITY_TIERS[1]
        if free_ram_mib >= self._t3_ram:
            return CAPABILITY_TIERS[-1 - 1]
        return CAPABILITY_TIERS[-1]

    @staticmethod
    def step_down(current_tier: str) -> str:
        if current_tier not in CAPABILITY_TIERS:
            return CAPABILITY_TIERS[-1]
        idx = CAPABILITY_TIERS.index(current_tier)
        next_idx = min(idx + 1, len(CAPABILITY_TIERS) - 1)
        return CAPABILITY_TIERS[next_idx]


class RouteCircuitBreaker:
    """Self-disabling per-route HTTP status, latency, and GraphQL semantic-error circuit breaker."""

    def __init__(
        self,
        *,
        grid: NodeGrid,
        cell: Mapping[str, Any] | None = None,
        state_file: Path | None = None,
    ) -> None:
        self.grid = grid
        self.cell = grid.bounds.clamp_cell(cell or grid.default_verified_cell)
        self.state_file = state_file
        self._routes: dict[str, dict[str, Any]] = {}
        self._file_mode = int(grid.protocol_constants["owner_only_file_mode_octal"])
        self._dir_mode = int(grid.protocol_constants["owner_only_dir_mode_octal"])
        if self.state_file is not None and self.state_file.exists():
            try:
                loaded = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(loaded, Mapping):
                    self._routes = {str(k): dict(v) for k, v in loaded.items() if isinstance(v, Mapping)}
            except Exception:
                self._routes = {}

    def _persist(self) -> None:
        if self.state_file is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_file.parent, self._dir_mode)
        self.state_file.write_text(json.dumps(self._routes, indent=1, sort_keys=True), encoding="utf-8")
        os.chmod(self.state_file, self._file_mode)

    def is_route_allowed(self, route_key: str, *, now_ts: float | None = None) -> bool:
        ts = float(now_ts if now_ts is not None else time.time())
        rec = self._routes.get(route_key)
        if rec is None:
            return True
        open_until = float(rec.get("open_until_ts", 0.0))
        if rec.get("state") == "open" and ts < open_until:
            return False
        if rec.get("state") == "open" and ts >= open_until:
            rec["state"] = "closed"
            rec["graphql_error_count"] = 0
            self._persist()
        return True

    def get_route_state(self, route_key: str, *, now_ts: float | None = None) -> dict[str, Any]:
        _ = self.is_route_allowed(route_key, now_ts=now_ts)
        return dict(self._routes.get(route_key, {"state": "closed", "open_until_ts": 0.0}))

    def record_http_outcome(
        self,
        route_key: str,
        *,
        status_code: int,
        latency_ms: float,
        body: Any = None,
        now_ts: float | None = None,
    ) -> dict[str, Any]:
        ts = float(now_ts if now_ts is not None else time.time())
        not_found = int(self.grid.protocol_constants["not_found_status"])
        ok_status = int(self.grid.protocol_constants["http_ok_status"])
        cooldown_404 = float(self.cell["circuit_open_404_cooldown_sec"])
        cooldown_timeout = float(self.cell["circuit_open_timeout_cooldown_sec"])
        timeout_budget_ms = float(self.cell["route_timeout_ms"])
        gql_budget = int(self.cell["graphql_error_budget_count"])

        rec = dict(
            self._routes.get(
                route_key,
                {"state": "closed", "open_until_ts": 0.0, "graphql_error_count": 0},
            )
        )
        rec["last_status"] = int(status_code)
        rec["last_latency_ms"] = float(latency_ms)

        if int(status_code) == not_found:
            rec["state"] = "open"
            rec["reason"] = "http_404_missing_route"
            rec["open_until_ts"] = ts + cooldown_404
            rec["cooldown_sec"] = cooldown_404
        elif float(latency_ms) > timeout_budget_ms:
            rec["state"] = "open"
            rec["reason"] = "latency_budget_exceeded"
            rec["open_until_ts"] = ts + cooldown_timeout
            rec["cooldown_sec"] = cooldown_timeout
        elif int(status_code) == ok_status and isinstance(body, Mapping):
            gql_errors = body.get("errors")
            has_semantic_err = isinstance(gql_errors, list) and len(gql_errors) > 0
            if has_semantic_err:
                err_count = int(rec.get("graphql_error_count", 0)) + 1
                rec["graphql_error_count"] = err_count
                if err_count >= gql_budget:
                    rec["state"] = "open"
                    rec["reason"] = "graphql_semantic_error_budget_exhausted"
                    rec["open_until_ts"] = ts + cooldown_timeout
                    rec["cooldown_sec"] = cooldown_timeout
            else:
                rec["graphql_error_count"] = 0

        self._routes[route_key] = rec
        self._persist()
        return dict(rec)

    def record_timeout(self, route_key: str, *, now_ts: float | None = None) -> dict[str, Any]:
        ts = float(now_ts if now_ts is not None else time.time())
        cooldown_timeout = float(self.cell["circuit_open_timeout_cooldown_sec"])
        rec = dict(
            self._routes.get(
                route_key,
                {"state": "closed", "open_until_ts": 0.0, "graphql_error_count": 0},
            )
        )
        rec["state"] = "open"
        rec["reason"] = "request_timeout"
        rec["open_until_ts"] = ts + cooldown_timeout
        rec["cooldown_sec"] = cooldown_timeout
        self._routes[route_key] = rec
        self._persist()
        return dict(rec)


class ClockSkewCalibrator:
    """Calibrates worker lease math against server time from Tessera /v1/health."""

    def __init__(self, grid: NodeGrid) -> None:
        self.offset_sec: float = 0.0
        self._ms_per_sec = float(grid.protocol_constants["ms_per_sec"])
        self._epoch_ms_cutoff = float(grid.protocol_constants["epoch_ms_cutoff"])

    def _parse_server_time(self, raw_time: Any) -> float | None:
        if isinstance(raw_time, (int, float)) and not isinstance(raw_time, bool):
            val = float(raw_time)
            if val > self._epoch_ms_cutoff:
                return val / self._ms_per_sec
            return val
        if isinstance(raw_time, str) and raw_time.strip():
            txt = raw_time.strip()
            if txt.endswith("Z"):
                txt = txt[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(txt).timestamp()
            except ValueError:
                try:
                    val = float(txt)
                    return val / self._ms_per_sec if val > self._epoch_ms_cutoff else val
                except ValueError:
                    return None
        return None

    def calibrate_from_health_payload(
        self,
        health_payload: Mapping[str, Any],
        *,
        local_now_ts: float | None = None,
    ) -> float:
        local_ts = float(local_now_ts if local_now_ts is not None else time.time())
        raw_t = (
            health_payload.get("time")
            or health_payload.get("server_time")
            or health_payload.get("timestamp")
        )
        parsed = self._parse_server_time(raw_t)
        if parsed is not None:
            self.offset_sec = parsed - local_ts
        return self.offset_sec

    def calibrated_now(self, *, local_now_ts: float | None = None) -> float:
        local_ts = float(local_now_ts if local_now_ts is not None else time.time())
        return local_ts + self.offset_sec

    def remaining_lease_sec(
        self,
        lease_expires_at: float | str,
        *,
        local_now_ts: float | None = None,
    ) -> float:
        exp_ts = self._parse_server_time(lease_expires_at)
        if exp_ts is None:
            return 0.0
        return exp_ts - self.calibrated_now(local_now_ts=local_now_ts)


class PinnedDigestVerifier:
    """Verifies upstream Task Object JSON integrity, quarantine status, and pinned digest."""

    @staticmethod
    def verify_upstream_object(
        upstream_doc: Mapping[str, Any],
        *,
        expected_digest_prefix: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(upstream_doc, Mapping) or not upstream_doc:
            return {"ok": False, "reason": "empty_or_invalid_object"}
        if upstream_doc.get("notFound") or upstream_doc.get("forbidden"):
            return {"ok": False, "reason": "missing_or_forbidden"}
        if upstream_doc.get("payload_json_valid") is False:
            return {"ok": False, "reason": "invalid_payload_json"}
        if upstream_doc.get("integrity_status") == "legacy_truncated_json":
            return {"ok": False, "reason": "truncated_upstream_payload"}

        verdict = str(upstream_doc.get("verification_verdict") or "UNREVIEWED").upper()
        if verdict.startswith("QUARANTINED") or verdict == "VALIDATOR_FAILED":
            return {"ok": False, "reason": f"rejected_verdict:{verdict}"}

        verified_flag = [
            v
            for k, v in upstream_doc.items()
            if k.endswith("_verified") and isinstance(v, bool)
        ]
        if verified_flag and verified_flag[0] is False:
            return {"ok": False, "reason": "digest_verification_failed"}

        if expected_digest_prefix:
            actual_digest = str(
                upstream_doc.get("digest")
                or next(
                    (
                        v
                        for k, v in upstream_doc.items()
                        if k.endswith("_hash") and isinstance(v, str)
                    ),
                    "",
                )
            ).lower()
            if not actual_digest.startswith(expected_digest_prefix.lower()):
                return {"ok": False, "reason": "pinned_digest_mismatch"}

        return {"ok": True, "reason": "verified"}


class SelfReviewCoLeaseGuard:
    """Detects maker == checker co-lease conflicts (F-20261102-38) and triggers immediate release."""

    @staticmethod
    def check_and_release_if_conflict(
        claimed_task: Mapping[str, Any],
        *,
        agent_id: str,
        worker_uuid: str = "",
        release_callback: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any]:
        clean_agent = agent_id.strip().lower()
        clean_uuid = worker_uuid.strip().lower()

        excluded_agents = {
            str(x).strip().lower()
            for x in (claimed_task.get("excluded_reporter_agent_ids") or [])
            if x
        }
        excluded_uuids = {
            str(x).strip().lower()
            for x in (claimed_task.get("excluded_worker_uuids") or [])
            if x
        }
        producers = {
            str(claimed_task.get(fld) or "").strip().lower()
            for fld in (
                "producer_agent",
                "proposer_agent",
                "author_agent_id",
                "target_producer_agent",
            )
        } - {""}
        producer_uuids = {
            str(claimed_task.get(fld) or "").strip().lower()
            for fld in ("producer_worker_uuid", "proposer_worker_uuid")
        } - {""}

        target_obj = claimed_task.get("target_object")
        if isinstance(target_obj, Mapping):
            tp = str(target_obj.get("producer_agent") or "").strip().lower()
            if tp:
                producers.add(tp)

        agent_conflict = bool(clean_agent and (clean_agent in excluded_agents or clean_agent in producers))
        uuid_conflict = bool(clean_uuid and (clean_uuid in excluded_uuids or clean_uuid in producer_uuids))

        if not (agent_conflict or uuid_conflict):
            return {"conflict": False, "released": False, "blocker_code": None}

        release_payload = {
            "agent_id": agent_id,
            "worker_uuid": worker_uuid,
            "task_id": claimed_task.get("task_id", ""),
            "lease_epoch": claimed_task.get("lease_epoch", claimed_task.get("fencing_token", 1)),
            "blocker_code": "self_review_conflict",
            "error_summary": "Maker equals checker conflict detected; releasing cooperatively for independent peer verification.",
        }
        if release_callback is not None:
            release_callback(release_payload)
        return {
            "conflict": True,
            "released": release_callback is not None,
            "blocker_code": "self_review_conflict",
            "release_payload": release_payload,
        }


class AdaptiveBatchAndResourceWaterfall:
    """Clamps claim batches to lease window, auto-halves on OOM/413/timeout, and GCs /tmp."""

    def __init__(self, grid: NodeGrid, cell: Mapping[str, Any] | None = None) -> None:
        self.grid = grid
        self.cell = grid.bounds.clamp_cell(cell or grid.default_verified_cell)

    def clamp_claim_batch_size(
        self,
        requested_batch: int,
        *,
        lease_ttl_sec: float,
        est_task_sec: float,
    ) -> int:
        min_b = int(self.cell["min_batch_size"])
        max_b = int(self.cell["max_batch_size"])
        margin = float(self.cell["lease_safety_margin_sec"])
        usable_sec = max(float(lease_ttl_sec) - margin, 0.0)
        per_task = max(float(est_task_sec), 1.0)
        lease_cap = max(int(usable_sec // per_task), min_b)
        upper = min(max_b, lease_cap)
        return min(max(int(requested_batch), min_b), max(upper, min_b))

    def run_with_batch_halving(
        self,
        items: Sequence[Any],
        processor: Callable[[Sequence[Any]], list[Any]],
        *,
        initial_batch_size: int | None = None,
    ) -> dict[str, Any]:
        min_b = int(self.cell["min_batch_size"])
        max_b = int(self.cell["max_batch_size"])
        divisor = max(int(self.cell["batch_halving_divisor"]), 1 + 1)
        too_large_code = int(self.grid.protocol_constants["payload_too_large_status"])

        cur_batch = min(
            max(int(initial_batch_size if initial_batch_size is not None else max_b), min_b),
            max_b,
        )
        outputs: list[Any] = []
        halving_events: list[dict[str, Any]] = []
        cursor = 0
        total = len(items)

        while cursor < total:
            chunk = items[cursor : cursor + cur_batch]
            try:
                chunk_out = processor(chunk)
                outputs.extend(chunk_out)
                cursor += len(chunk)
            except Exception as exc:
                is_http_413 = isinstance(exc, urllib.error.HTTPError) and int(exc.code) == too_large_code
                msg_low = str(exc).lower()
                is_resource_err = (
                    isinstance(exc, (MemoryError, TimeoutError))
                    or is_http_413
                    or "out of memory" in msg_low
                    or "oom" in msg_low
                    or "payload too large" in msg_low
                    or "timed out" in msg_low
                )
                if not is_resource_err or cur_batch <= min_b:
                    raise
                next_batch = max(min_b, cur_batch // divisor)
                if next_batch == cur_batch:
                    next_batch = min_b
                halving_events.append(
                    {
                        "cursor": cursor,
                        "previous_batch_size": cur_batch,
                        "new_batch_size": next_batch,
                        "trigger": type(exc).__name__,
                    }
                )
                cur_batch = next_batch

        return {
            "results": outputs,
            "final_batch_size": cur_batch,
            "halving_events": halving_events,
        }

    def gc_scratch_dirs(
        self,
        scratch_parent: Path,
        *,
        prefix: str = "tessera_work_",
        now_ts: float | None = None,
    ) -> dict[str, Any]:
        ts = float(now_ts if now_ts is not None else time.time())
        ttl_sec = float(self.cell["scratch_ttl_sec"])
        removed: list[str] = []
        bytes_reclaimed = 0

        if not scratch_parent.exists():
            return {"removed_dirs": removed, "bytes_reclaimed": 0}

        for entry in sorted(scratch_parent.iterdir()):
            if not entry.is_dir() or not entry.name.startswith(prefix):
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if (ts - mtime) > ttl_sec:
                dir_bytes = sum(
                    f.stat().st_size for f in entry.rglob("*") if f.is_file()
                )
                shutil.rmtree(entry, ignore_errors=True)
                removed.append(entry.name)
                bytes_reclaimed += dir_bytes

        return {"removed_dirs": removed, "bytes_reclaimed": bytes_reclaimed}

    def clamp_nofile_concurrency(
        self,
        requested_workers: int,
        *,
        soft_nofile_override: int | None = None,
    ) -> int:
        if soft_nofile_override is not None:
            soft_limit = int(soft_nofile_override)
        else:
            soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        divisor = max(int(self.cell["nofile_per_worker_divisor"]), 1)
        safe_cap = max(int(soft_limit) // divisor, 1)
        return min(max(int(requested_workers), 1), safe_cap)


class PreFlightEnvelopeSanitizer:
    """Sanitizes /q/submit envelopes: lifts nested fields, caps object_key, checks UTF-8 & scope."""

    def __init__(self, grid: NodeGrid, cell: Mapping[str, Any] | None = None) -> None:
        self.grid = grid
        self.cell = grid.bounds.clamp_cell(cell or grid.default_verified_cell)

    def canonicalize_object_key(self, raw_key: str) -> str:
        max_len = int(self.cell["max_object_key_chars"])
        cleaned = re.sub(r"[^a-z0-9_-]+", "_", str(raw_key or "").strip().lower()).strip("_-")
        if not cleaned:
            cleaned = "omninode_task_object"

        ver_match = re.search(r"(_v\d+)$", cleaned)
        suffix = ver_match.group(1) if ver_match is not None else "_v1"
        stem = cleaned[: -len(suffix)] if ver_match is not None else cleaned
        stem = stem.rstrip("_-") or "omninode_object"

        allowed_stem_len = max(max_len - len(suffix), 1)
        if len(stem) > allowed_stem_len:
            stem = stem[:allowed_stem_len].rstrip("_-") or stem[:allowed_stem_len]
        return f"{stem}{suffix}"

    @staticmethod
    def _infer_prog_lang(task_obj: Mapping[str, Any]) -> str:
        explicit = str(task_obj.get("prog_lang") or "").strip().lower()
        if explicit:
            return explicit
        payload = task_obj.get("payload")
        if isinstance(payload, Mapping):
            file_maps = [
                payload.get("working_dir_files"),
                payload.get("files"),
            ]
            for fmap in file_maps:
                if isinstance(fmap, Mapping):
                    keys = [str(k).lower() for k in fmap.keys()]
                    if any(k.endswith(".py") for k in keys):
                        return "python"
                    if any(k.endswith((".js", ".mjs", ".ts")) for k in keys):
                        return "javascript"
                    if any(k.endswith(".md") for k in keys) and not any(
                        k.endswith((".py", ".js", ".json")) for k in keys
                    ):
                        return "markdown_spec"
        return "json_declarative"

    def sanitize_submit_envelope(
        self,
        raw_envelope: Mapping[str, Any],
        *,
        claimed_task_scope: str | None = None,
        allow_public_export: bool = False,
    ) -> dict[str, Any]:
        env = copy.deepcopy(dict(raw_envelope))
        top_evals = list(env.get("evaluations") or [])
        top_followups = list(env.get("followup_tasks") or [])
        lifted_evals = 0
        lifted_followups = 0

        scope_str = str(claimed_task_scope or env.get("workspace_scope") or "").strip()
        is_private_tenant = scope_str.startswith("acct.")

        if is_private_tenant and not allow_public_export:
            env["visibility"] = "private"
            env["workspace_scope"] = scope_str

        sanitized_objects: list[dict[str, Any]] = []
        for raw_obj in env.get("task_objects") or []:
            if not isinstance(raw_obj, Mapping):
                continue
            obj = dict(raw_obj)
            raw_key = (
                obj.get("object_key")
                or obj.pop("object_id", None)
                or obj.pop("object_name", None)
                or "omninode_object_v1"
            )
            obj.pop("object_id", None)
            obj.pop("object_name", None)
            obj["object_key"] = self.canonicalize_object_key(str(raw_key))

            if "evaluations" in obj and isinstance(obj["evaluations"], list):
                top_evals.extend(obj.pop("evaluations"))
                lifted_evals += 1
            if "followup_tasks" in obj and isinstance(obj["followup_tasks"], list):
                top_followups.extend(obj.pop("followup_tasks"))
                lifted_followups += 1

            payload = dict(obj.get("payload") or {})
            if "evaluations" in payload and isinstance(payload["evaluations"], list):
                top_evals.extend(payload.pop("evaluations"))
                lifted_evals += 1
            if "followup_tasks" in payload and isinstance(payload["followup_tasks"], list):
                top_followups.extend(payload.pop("followup_tasks"))
                lifted_followups += 1

            in_schema = obj.get("input_schema") or payload.get("input_schema") or {"type": "object"}
            out_schema = obj.get("output_schema") or payload.get("output_schema") or {"type": "object"}
            obj["input_schema"] = in_schema
            obj["output_schema"] = out_schema
            payload["input_schema"] = in_schema
            payload["output_schema"] = out_schema

            if is_private_tenant and not allow_public_export:
                obj["visibility"] = "private"
                obj["workspace_scope"] = scope_str

            obj["payload"] = payload
            obj["prog_lang"] = self._infer_prog_lang(obj)
            sanitized_objects.append(obj)

        env["task_objects"] = sanitized_objects
        env["evaluations"] = top_evals
        env["followup_tasks"] = top_followups

        serialized = json.dumps(env, ensure_ascii=False)
        utf8_bytes = len(serialized.encode("utf-8"))
        max_bytes = int(self.cell["max_utf8_payload_bytes"])
        if utf8_bytes > max_bytes:
            raise ValueError(
                f"UTF-8 payload size {utf8_bytes} bytes exceeds grid cap {max_bytes} bytes"
            )

        gzip_threshold = int(self.grid.protocol_constants["gzip_min_utf8_bytes"])
        gzip_bytes = (
            gzip.compress(serialized.encode("utf-8"))
            if utf8_bytes >= gzip_threshold
            else None
        )

        return {
            "envelope": env,
            "utf8_bytes": utf8_bytes,
            "char_length": len(serialized),
            "lifted_evaluations_sources": lifted_evals,
            "lifted_followup_sources": lifted_followups,
            "gzip_payload": gzip_bytes,
        }


class PoisonPillQuarantine:
    """Tracks repeated task failures and quarantines poison-pill task_ids locally."""

    def __init__(
        self,
        *,
        grid: NodeGrid,
        cell: Mapping[str, Any] | None = None,
        state_file: Path | None = None,
    ) -> None:
        self.grid = grid
        self.cell = grid.bounds.clamp_cell(cell or grid.default_verified_cell)
        self.state_file = state_file
        self._failures: dict[str, dict[str, Any]] = {}
        self._file_mode = int(grid.protocol_constants["owner_only_file_mode_octal"])
        self._dir_mode = int(grid.protocol_constants["owner_only_dir_mode_octal"])
        if self.state_file is not None and self.state_file.exists():
            try:
                raw = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(raw, Mapping):
                    self._failures = {str(k): dict(v) for k, v in raw.items() if isinstance(v, Mapping)}
            except Exception:
                self._failures = {}

    def _persist(self) -> None:
        if self.state_file is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_file.parent, self._dir_mode)
        self.state_file.write_text(json.dumps(self._failures, indent=1, sort_keys=True), encoding="utf-8")
        os.chmod(self.state_file, self._file_mode)

    def record_failure(self, task_id: str, *, reason: str) -> dict[str, Any]:
        limit = int(self.cell["max_task_failures_before_quarantine"])
        rec = dict(self._failures.get(task_id, {"failures": 0, "quarantined": False, "last_reason": ""}))
        rec["failures"] = int(rec["failures"]) + 1
        rec["last_reason"] = str(reason)
        if int(rec["failures"]) >= limit:
            rec["quarantined"] = True
        self._failures[task_id] = rec
        self._persist()
        return dict(rec)

    def is_quarantined(self, task_id: str) -> bool:
        return bool(self._failures.get(task_id, {}).get("quarantined", False))


class CooperativeLeaseLifecycle:
    """Manages active task lease context and cooperative release on SIGTERM, SIGINT, or exit."""

    def __init__(
        self,
        *,
        grid: NodeGrid,
        release_fn: Callable[[dict[str, Any]], Any],
    ) -> None:
        self._grid = grid
        self._release_fn = release_fn
        self.active_lease: dict[str, Any] = {}
        self._exit_base = int(grid.protocol_constants["exit_signal_base"])

    def bind_lease(self, lease_info: Mapping[str, Any]) -> None:
        self.active_lease = dict(lease_info)

    def clear_lease(self) -> None:
        self.active_lease.clear()

    def release_active_lease(self, *, blocker_code: str = "worker_shutdown_handoff") -> bool:
        if not self.active_lease.get("task_id"):
            return False
        payload = {
            "agent_id": self.active_lease.get("agent_id", ""),
            "worker_uuid": self.active_lease.get("worker_uuid", ""),
            "worker_token": self.active_lease.get("worker_token", ""),
            "task_id": self.active_lease["task_id"],
            "lease_epoch": self.active_lease.get("lease_epoch", 1),
            "blocker_code": blocker_code,
            "error_summary": "Worker exiting cleanly; releasing active lease for peer pickup.",
        }
        self.active_lease.clear()
        try:
            self._release_fn(payload)
            return True
        except Exception:
            return False

    def install_hooks(self, *, register_signals: bool = False) -> None:
        atexit.register(self.release_active_lease)
        if register_signals:
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(
                    sig,
                    lambda signum, _frame: (
                        self.release_active_lease(blocker_code="signal_interrupt_handoff"),
                        os._exit(self._exit_base + int(signum)),
                    ),
                )


class SelfHealingWaterfallClient:
    """End-to-end self-healing Herma/Tessera client with circuit breakers and v19 -> v8 waterfall."""

    def __init__(
        self,
        *,
        grid: NodeGrid | None = None,
        cell: Mapping[str, Any] | None = None,
        workers_dir: Path | None = None,
        transport: Callable[[str, dict[str, Any] | None, dict[str, str], float], tuple[int, Any]] | None = None,
    ) -> None:
        self.grid = grid or NodeGrid.from_json_file(DEFAULT_GRID_CONFIG_PATH)
        self.cell = self.grid.bounds.clamp_cell(cell or self.grid.default_verified_cell)
        self.workers_dir = workers_dir or (Path.home() / ".tessera_workers")

        self.user_agent = str(self.grid.protocol_constants["user_agent"])
        self.herma_primary = str(self.grid.protocol_constants["herma_primary"])
        self.herma_fallback = str(self.grid.protocol_constants["herma_fallback"])
        self.tessera_primary = str(self.grid.protocol_constants["tessera_primary"])
        self._ms_per_sec = float(self.grid.protocol_constants["ms_per_sec"])

        self.circuit_breaker = RouteCircuitBreaker(
            grid=self.grid,
            cell=self.cell,
            state_file=self.workers_dir / "route_health.json",
        )
        self.capability_ladder = LocalCapabilityLadder(self.grid)
        self.clock_calibrator = ClockSkewCalibrator(self.grid)
        self.sanitizer = PreFlightEnvelopeSanitizer(self.grid, self.cell)
        self.batch_waterfall = AdaptiveBatchAndResourceWaterfall(self.grid, self.cell)
        self.quarantine = PoisonPillQuarantine(
            grid=self.grid,
            cell=self.cell,
            state_file=self.workers_dir / "quarantine_state.json",
        )
        self._transport = transport

        redirect_handler = MethodPreservingRedirectHandler(
            redirect_statuses=self.grid.protocol_constants["redirect_statuses"],
            trusted_suffixes=self.grid.protocol_constants["trusted_redirect_suffixes"],
        )
        self._opener = urllib.request.build_opener(redirect_handler)
        self.lease_lifecycle = CooperativeLeaseLifecycle(
            grid=self.grid,
            release_fn=lambda payload: self.request_json("/q/release", payload=payload),
        )

    def _raw_http_call(
        self,
        url: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        timeout_sec: float,
    ) -> tuple[int, Any]:
        if self._transport is not None:
            return self._transport(url, payload, headers, timeout_sec)
        body_bytes = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers=headers,
            method="POST" if body_bytes is not None else "GET",
        )
        with self._opener.open(req, timeout=timeout_sec) as resp:
            status = int(getattr(resp, "status", self.grid.protocol_constants["http_ok_status"]))
            raw_text = resp.read().decode("utf-8")
            parsed = json.loads(raw_text) if raw_text.strip() else {}
            return status, parsed

    def request_json(
        self,
        route_or_url: str,
        *,
        payload: dict[str, Any] | None = None,
        token: str | None = None,
        timeout_ms: float | None = None,
        now_ts: float | None = None,
    ) -> dict[str, Any]:
        if route_or_url.startswith(("http://", "https://")):
            full_url = route_or_url
            parsed_u = urllib.parse.urlparse(full_url)
            route_key = parsed_u.path or "/"
        else:
            route_key = route_or_url if route_or_url.startswith("/") else f"/{route_or_url}"
            full_url = f"{self.herma_primary}{route_key}"

        if not self.circuit_breaker.is_route_allowed(route_key, now_ts=now_ts):
            raise RuntimeError(f"Circuit open for route {route_key}")

        eff_timeout_sec = (
            float(timeout_ms if timeout_ms is not None else self.cell["route_timeout_ms"])
            / self._ms_per_sec
        )
        headers: dict[str, str] = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        urls = [full_url]
        if full_url.startswith(self.herma_primary):
            urls.append(self.herma_fallback + full_url[len(self.herma_primary) :])

        server_err_floor = int(self.grid.protocol_constants["server_error_min_status"])
        last_exc: Exception | None = None

        for candidate_url in urls:
            t0 = time.perf_counter()
            try:
                status, body = self._raw_http_call(candidate_url, payload, headers, eff_timeout_sec)
                lat_ms = (time.perf_counter() - t0) * self._ms_per_sec
                self.circuit_breaker.record_http_outcome(
                    route_key,
                    status_code=status,
                    latency_ms=lat_ms,
                    body=body,
                    now_ts=now_ts,
                )
                return body if isinstance(body, dict) else {"data": body}
            except urllib.error.HTTPError as http_err:
                lat_ms = (time.perf_counter() - t0) * self._ms_per_sec
                self.circuit_breaker.record_http_outcome(
                    route_key,
                    status_code=int(http_err.code),
                    latency_ms=lat_ms,
                    now_ts=now_ts,
                )
                if int(http_err.code) < server_err_floor:
                    raise
                last_exc = http_err
            except TimeoutError as tout_err:
                self.circuit_breaker.record_timeout(route_key, now_ts=now_ts)
                last_exc = tout_err
                break
            except Exception as exc:
                if "timed out" in str(exc).lower():
                    self.circuit_breaker.record_timeout(route_key, now_ts=now_ts)
                    last_exc = exc
                    break
                last_exc = exc

        raise RuntimeError(f"Request failed for {route_key}: {last_exc}") from last_exc

    def resolve_capability_fallback(
        self,
        current_tier: str,
        *,
        now_ts: float | None = None,
    ) -> dict[str, Any]:
        """Attempts /q/alternatives if circuit closed; on 404/open circuit steps down locally."""
        route_key = "/q/alternatives"
        if self.circuit_breaker.is_route_allowed(route_key, now_ts=now_ts):
            try:
                remote = self.request_json(
                    route_key,
                    payload={"current_tier": current_tier},
                    now_ts=now_ts,
                )
                return {
                    "source": "remote_alternatives",
                    "next_tier": remote.get("next_tier") or self.capability_ladder.step_down(current_tier),
                    "circuit_open": False,
                }
            except Exception:
                pass

        next_tier = self.capability_ladder.step_down(current_tier)
        c_state = self.circuit_breaker.get_route_state(route_key, now_ts=now_ts)
        return {
            "source": "local_4tier_ladder",
            "next_tier": next_tier,
            "circuit_open": c_state.get("state") == "open",
            "cooldown_sec": c_state.get("cooldown_sec", 0.0),
        }

    def fetch_leaderboard_or_waterfall(self, *, now_ts: float | None = None) -> dict[str, Any]:
        """Queries /q/leaderboard within budget; auto-waterfalls to /q/pulse + /q/network."""
        lb_route = "/q/leaderboard"
        if self.circuit_breaker.is_route_allowed(lb_route, now_ts=now_ts):
            try:
                lb = self.request_json(
                    lb_route,
                    timeout_ms=float(self.cell["route_timeout_ms"]),
                    now_ts=now_ts,
                )
                if self.circuit_breaker.is_route_allowed(lb_route, now_ts=now_ts):
                    return {"source": "leaderboard", "data": lb, "waterfalled": False}
            except Exception:
                pass

        pulse = self.request_json("/q/pulse", now_ts=now_ts)
        network = self.request_json("/q/network", now_ts=now_ts)
        return {
            "source": "pulse_and_network_waterfall",
            "waterfalled": True,
            "pulse": pulse,
            "network": network,
        }

    def submit_with_v8_waterfall(
        self,
        raw_envelope: Mapping[str, Any],
        *,
        claimed_task_scope: str | None = None,
        allow_public_export: bool = False,
        report_waterfall_feedback: bool = False,
    ) -> dict[str, Any]:
        """Sanitizes and submits v19 envelope; waterfalls to minimal v8 core on HTTP 400/422."""
        sanitized_bundle = self.sanitizer.sanitize_submit_envelope(
            raw_envelope,
            claimed_task_scope=claimed_task_scope,
            allow_public_export=allow_public_export,
        )
        v19_env = sanitized_bundle["envelope"]
        submit_timeout = float(self.grid.protocol_constants["submit_timeout_ms"])
        reject_codes = {int(c) for c in self.grid.protocol_constants["schema_reject_statuses"]}

        try:
            res = self.request_json(
                "/q/submit",
                payload=v19_env,
                timeout_ms=submit_timeout,
            )
            self.lease_lifecycle.clear_lease()
            return {
                "protocol_used": "v19",
                "waterfalled_to_v8": False,
                "utf8_bytes": sanitized_bundle["utf8_bytes"],
                "response": res,
            }
        except urllib.error.HTTPError as exc:
            if int(exc.code) not in reject_codes:
                raise
            v8_keys = list(self.grid.protocol_constants["v8_core_keys"])
            v8_env = {k: v19_env[k] for k in v8_keys if k in v19_env}
            res_v8 = self.request_json(
                "/q/submit",
                payload=v8_env,
                timeout_ms=submit_timeout,
            )
            self.lease_lifecycle.clear_lease()
            if report_waterfall_feedback:
                try:
                    self.request_json(
                        "/q/feedback",
                        payload={
                            "agent_id": v19_env.get("agent_id", "omninode-worker"),
                            "worker_uuid": v19_env.get("worker_uuid", ""),
                            "worker_token": v19_env.get("worker_token", ""),
                            "signal_kind": "better_or_alternative_way",
                            "target_component": "/q/submit",
                            "http_status": int(exc.code),
                            "observation": "Extended v19 telemetry field triggered HTTP schema rejection; automatic v8 core waterfall succeeded cleanly.",
                        },
                    )
                except Exception:
                    pass
            return {
                "protocol_used": "v8_core_fallback",
                "waterfalled_to_v8": True,
                "utf8_bytes": len(json.dumps(v8_env, ensure_ascii=False).encode("utf-8")),
                "response": res_v8,
            }

    def probe_host_profile(self) -> dict[str, Any]:
        """Probes host tools, RAM, RLIMIT_NOFILE, and calibrates Tessera server clock offset."""
        try:
            health = self.request_json(
                f"{self.tessera_primary}/v1/health",
                timeout_ms=float(self.grid.protocol_constants["health_timeout_ms"]),
            )
            self.clock_calibrator.calibrate_from_health_payload(health)
        except Exception:
            pass

        tools = [
            t
            for t in ("python3", "pytest", "node", "git", "curl", "ffmpeg")
            if shutil.which(t)
        ]
        kib = int(self.grid.protocol_constants["kib_bytes"])
        mem_mib = int(self.grid.protocol_constants["tier4_architect_min_ram_mib"])
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    if len(parts) > 1 and parts[1].isdigit():
                        mem_mib = int(parts[1]) // kib
                    break

        soft_nofile, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        t4_ram = int(self.grid.protocol_constants["tier4_architect_min_ram_mib"])
        if "pytest" in tools and "git" in tools and mem_mib >= t4_ram:
            harness_tier = "tier_4_deep_architect_astra"
        elif "python3" in tools:
            harness_tier = "tier_3_cli_code_harness"
        else:
            harness_tier = "tier_2_sandboxed_chat_worker"

        has_gpu = bool(shutil.which("nvidia-smi"))
        return {
            "os_arch": f"{platform.system().lower()}_{platform.machine().lower()}",
            "free_ram_mib": mem_mib,
            "has_gpu": has_gpu,
            "fd_soft_limit": soft_nofile,
            "max_safe_concurrency": self.batch_waterfall.clamp_nofile_concurrency(
                int(self.cell["warm_pool_max_slots"]),
                soft_nofile_override=soft_nofile,
            ),
            "harness_tier": harness_tier,
            "capability_tier": self.capability_ladder.select_initial_tier(
                free_ram_mib=mem_mib,
                has_gpu=has_gpu,
            ),
            "tools_available": tools,
            "clock_offset_sec": self.clock_calibrator.offset_sec,
        }

    def ensure_isolated_worker_slot(
        self,
        *,
        slot_name: str,
        declared_model: str,
        show_on_map: bool = True,
    ) -> tuple[dict[str, Any], Path]:
        """Onboards or reloads an isolated worker credential in ~/.tessera_workers/ (0600)."""
        dir_mode = int(self.grid.protocol_constants["owner_only_dir_mode_octal"])
        file_mode = int(self.grid.protocol_constants["owner_only_file_mode_octal"])
        short_chars = int(self.grid.protocol_constants["short_digest_chars"])

        self.workers_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.workers_dir, dir_mode)

        clean_slot = re.sub(r"[^a-z0-9_-]+", "-", slot_name.lower()).strip("-")
        if not clean_slot:
            clean_slot = f"omninode-{secrets.token_hex(1 + 1)}"

        state_file = self.workers_dir / f"worker_{clean_slot}.json"
        scratch_dir = Path("/tmp") / f"tessera_work_{clean_slot}"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        if state_file.exists():
            existing = json.loads(state_file.read_text(encoding="utf-8"))
            prof = existing.get("worker_profile") if isinstance(existing.get("worker_profile"), Mapping) else {}
            if not existing.get("worker_uuid") and prof.get("worker_uuid"):
                existing["worker_uuid"] = prof["worker_uuid"]
                state_file.write_text(json.dumps(existing, indent=1, sort_keys=True), encoding="utf-8")
                os.chmod(state_file, file_mode)
            if existing.get("worker_token") and existing.get("worker_uuid"):
                return existing, scratch_dir

        host_prof = self.probe_host_profile()
        max_key_len = int(self.cell["max_object_key_chars"])
        agent_id = f"w-{clean_slot}"[: max(max_key_len - short_chars, 1)]
        onboard_res = self.request_json(
            "/q/onboard",
            payload={
                "agent_id": agent_id,
                "declared_model": declared_model,
                "model": declared_model,
                "model_hint": declared_model,
                "harness_tier": host_prof["harness_tier"],
                "show_on_map": bool(show_on_map),
                "capabilities": host_prof["tools_available"]
                + ["omninode_warm_dag", "thick_path_verifier", "self_healing_waterfall"],
            },
            timeout_ms=float(self.grid.protocol_constants["submit_timeout_ms"]),
        )
        prof_out = (
            onboard_res.get("worker_profile")
            if isinstance(onboard_res.get("worker_profile"), Mapping)
            else {}
        )
        onboard_res["worker_slot"] = clean_slot
        onboard_res["agent_id"] = onboard_res.get("agent_id") or prof_out.get("agent_id") or agent_id
        onboard_res["worker_uuid"] = onboard_res.get("worker_uuid") or prof_out.get("worker_uuid") or ""
        onboard_res["declared_model"] = declared_model
        state_file.write_text(json.dumps(onboard_res, indent=1, sort_keys=True), encoding="utf-8")
        os.chmod(state_file, file_mode)
        return onboard_res, scratch_dir
