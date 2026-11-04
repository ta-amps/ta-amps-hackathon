"""Warm Meta Muse API client with shared atomic file-locked spend ledger and per-attempt recovery journal.

Compatible with `~/.local/state/eranos-worker/meta-spend.json` + `.lock`.
Enforces owner daily/total caps, refuses contributor-tier models, preserves native caller
output token settings, never prints/logs API keys, separates observed usage from unknown/estimated
reservations, preserves responses across post-response settlement or recorder faults, and reconciles
pending attempts by stable `attempt_id` without repeating inference.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from .grid_config import NodeGrid

KEY_NAME = "META_API_KEY"
ALLOWED_META_HOSTS = frozenset({"api.meta.ai"})


class ModelCallError(RuntimeError):
    """Model call failed; recorded on the attempt log."""


class SpendCapExceeded(ModelCallError):
    """Requested call could exceed the daily or total Meta spend cap."""


class ContributorTierDenied(PermissionError):
    """Contributor-tier models are strictly refused."""


def extract_meta_key(raw_text: str) -> str:
    """Read only `META_API_KEY=...` or a bare single-line token from an `0600` file."""
    for line in raw_text.splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == KEY_NAME:
            return value.strip().strip("'\"")
    non_empty = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if len(non_empty) == 1 and "=" not in non_empty[0]:
        return non_empty[0]
    return ""


def assert_not_contributor_tier(model_id: str) -> None:
    if "contributor" in str(model_id or "").lower():
        raise ContributorTierDenied(f"Refused contributor-tier model: {model_id}")


class SharedSpendLedger:
    """Atomic file-locked Meta spend ledger shared across all server agents."""

    def __init__(
        self,
        path: str | Path,
        *,
        daily_cap_usd: float,
        total_cap_usd: float,
        round_digits: int,
        file_mode: int,
        dir_mode: int,
    ) -> None:
        self.path = Path(path)
        self.daily_cap_usd = float(daily_cap_usd)
        self.total_cap_usd = float(total_cap_usd)
        self.round_digits = int(round_digits)
        self.file_mode = int(file_mode)
        self.dir_mode = int(dir_mode)

    def _today_utc(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def _atomic_update(self, mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=self.dir_mode)
        lock_fd = os.open(
            self.path.with_name(self.path.name + ".lock"),
            os.O_RDWR | os.O_CREAT,
            self.file_mode,
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            raw = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
            data = json.loads(raw) if raw.strip() else {"days": {}, "total_usd": 0.0, "calls": 0}
            mutator(data)
            tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
            out_fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, self.file_mode)
            with os.fdopen(out_fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(data, sort_keys=True))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
            return dict(data)
        finally:
            os.close(lock_fd)

    def _add_amount(self, data: dict[str, Any], day: str, delta: float) -> None:
        if not math.isfinite(delta):
            raise ValueError("Non-finite spend delta refused")
        days = data.setdefault("days", {})
        days[day] = round(max(0.0, float(days.get(day, 0.0)) + delta), self.round_digits)
        data["total_usd"] = round(max(0.0, float(data.get("total_usd", 0.0)) + delta), self.round_digits)

    def _check_caps(self, data: dict[str, Any], day: str, estimate_usd: float) -> None:
        spent_today = float((data.get("days") or {}).get(day, 0.0))
        spent_total = float(data.get("total_usd", 0.0))
        if not all(math.isfinite(v) and v >= 0.0 for v in (spent_today, spent_total, estimate_usd)):
            raise SpendCapExceeded("Invalid spend ledger state")
        if spent_today + estimate_usd > self.daily_cap_usd:
            raise SpendCapExceeded(f"Daily Meta cap (${self.daily_cap_usd:.2f}) reached")
        if spent_total + estimate_usd > self.total_cap_usd:
            raise SpendCapExceeded(f"Total Meta cap (${self.total_cap_usd:.2f}) reached")

    def read_snapshot(self) -> dict[str, Any]:
        return self._atomic_update(lambda _data: None)

    def reserve(self, estimate_usd: float) -> str:
        day = self._today_utc()

        def _take(data: dict[str, Any]) -> None:
            self._check_caps(data, day, estimate_usd)
            self._add_amount(data, day, estimate_usd)

        self._atomic_update(_take)
        return day

    def settle(self, actual_cost_usd: float, *, reserved_usd: float, day: str) -> dict[str, Any]:
        effective = actual_cost_usd if (math.isfinite(actual_cost_usd) and actual_cost_usd >= 0.0) else reserved_usd

        def _apply(data: dict[str, Any]) -> None:
            self._add_amount(data, day, effective - reserved_usd)
            if effective > 0.0:
                data["calls"] = int(data.get("calls", 0)) + 1

        return self._atomic_update(_apply)


class WarmMetaModelClient:
    """Warm HTTP connection-pooled client for Meta Muse models with durable per-attempt recovery."""

    def __init__(
        self,
        grid: NodeGrid,
        *,
        key_file: str | Path | None = None,
        ledger: SharedSpendLedger | None = None,
        attempt_recorder: Callable[[dict[str, Any]], None] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.grid = grid
        self.budget_cfg = grid.section("budget_and_rates")
        self.paths_cfg = grid.section("endpoints_and_paths")
        self.ops = grid.section("operational_constants")
        _, default_cell = grid.resolve_regime_cell()
        timeout_sec = float(default_cell["http_timeout_seconds"])
        self.default_max_tokens = int(default_cell["default_max_output_tokens"])
        self.models_catalog: dict[str, dict[str, Any]] = dict(self.budget_cfg.get("models") or {})
        self.key_file = Path(key_file) if key_file is not None else Path(str(self.paths_cfg["meta_key_file"]))
        self.ledger = ledger or SharedSpendLedger(
            self.paths_cfg["meta_spend_ledger"],
            daily_cap_usd=min(
                float(self.budget_cfg["warm_cycle_soft_daily_usd"]),
                float(self.budget_cfg["owner_daily_cap_usd"]),
            ),
            total_cap_usd=float(self.budget_cfg["owner_total_cap_usd"]),
            round_digits=int(self.budget_cfg["usd_round_digits"]),
            file_mode=int(self.ops["owner_rw_file_mode_decimal"]),
            dir_mode=int(self.ops["owner_rwx_dir_mode_decimal"]),
        )
        self.attempt_journal_path = self.ledger.path.with_name(self.ledger.path.name + ".attempts.json")
        self.attempt_recorder = attempt_recorder
        self._http = httpx.Client(
            timeout=timeout_sec,
            transport=transport or httpx.HTTPTransport(retries=0),
            trust_env=False,
        )
        self.reconcile_pending_attempts()

    def close(self) -> None:
        self._http.close()

    def _read_api_key(self) -> str:
        if not self.key_file.exists():
            raise ModelCallError("Meta key file not present")
        key = extract_meta_key(self.key_file.read_text(encoding="utf-8"))
        if not key:
            raise ModelCallError("Meta key file contains no META_API_KEY")
        return key

    def _load_attempt_journal(self) -> dict[str, dict[str, Any]]:
        if not self.attempt_journal_path.exists():
            return {}
        try:
            raw = self.attempt_journal_path.read_text(encoding="utf-8")
            parsed = json.loads(raw) if raw.strip() else {}
            return dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _save_attempt_journal(self, entries: dict[str, dict[str, Any]]) -> None:
        try:
            self.attempt_journal_path.parent.mkdir(parents=True, exist_ok=True, mode=self.ledger.dir_mode)
            tmp = self.attempt_journal_path.with_name(f".{self.attempt_journal_path.name}.{os.getpid()}.tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, self.ledger.file_mode)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(entries, sort_keys=True))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.attempt_journal_path)
        except Exception:
            pass

    def _upsert_journal_entry(self, attempt_id: str, entry: dict[str, Any]) -> None:
        entries = self._load_attempt_journal()
        entries[attempt_id] = dict(entry)
        max_cache = int(self.ops["max_seen_ids_cache"])
        if len(entries) > max_cache:
            settled_keys = [
                k
                for k, v in entries.items()
                if v.get("settlement_status") in {"settled", "refunded", "not_dispatched"}
                and v.get("recorder_status") == "recorded"
            ]
            for old_k in settled_keys[: len(entries) - max_cache]:
                entries.pop(old_k, None)
        self._save_attempt_journal(entries)

    def reconcile_pending_attempts(self) -> dict[str, int]:
        """Reconcile any post-response settlement or telemetry records interrupted earlier without redispatching."""
        entries = self._load_attempt_journal()
        settled_count = 0
        recorded_count = 0
        changed = False
        for attempt_id, entry in list(entries.items()):
            if entry.get("settlement_status") == "pending_known_settlement":
                try:
                    self.ledger.settle(
                        float(entry["actual_cost_usd"]),
                        reserved_usd=float(entry["reserved_usd"]),
                        day=str(entry["reserved_day"]),
                    )
                    entry["settlement_status"] = "settled"
                    entry["accounting_status"] = "settled_observed_usage"
                    settled_count += 1
                    changed = True
                except Exception:
                    pass
            if entry.get("recorder_status") == "pending" and self.attempt_recorder is not None:
                row = dict(entry.get("attempt_log_row") or {})
                if row:
                    row["attempt_id"] = attempt_id
                    row["accounting_status"] = entry.get("accounting_status")
                    try:
                        self.attempt_recorder(row)
                        entry["recorder_status"] = "recorded"
                        recorded_count += 1
                        changed = True
                    except Exception:
                        pass
        if changed:
            self._save_attempt_journal(entries)
        return {"settled": settled_count, "recorded": recorded_count}

    def _deliver_attempt_log(self, attempt_id: str, journal_entry: dict[str, Any], row: dict[str, Any]) -> bool:
        """Deliver telemetry safely; never raise or overwrite model completion on recorder failure."""
        full_row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "attempt_id": attempt_id, **row}
        journal_entry["attempt_log_row"] = full_row
        if self.attempt_recorder is None:
            journal_entry["recorder_status"] = "recorded"
            self._upsert_journal_entry(attempt_id, journal_entry)
            return True
        try:
            self.attempt_recorder(dict(full_row))
            journal_entry["recorder_status"] = "recorded"
            self._upsert_journal_entry(attempt_id, journal_entry)
            return True
        except Exception:
            journal_entry["recorder_status"] = "pending"
            self._upsert_journal_entry(attempt_id, journal_entry)
            return False

    def complete(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        json_object: bool = False,
        caller_tag: str = "warm_agent",
    ) -> dict[str, Any]:
        """Execute a warm Meta API completion, preserving native caller max_tokens and exact accounting."""
        assert_not_contributor_tier(model_id)
        spec = self.models_catalog.get(model_id)
        if spec is None:
            raise ValueError(f"Unregistered Meta model id: {model_id}")
        base_url = str(spec["base_url"]).rstrip("/")
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_META_HOSTS:
            raise ValueError("Meta client enforces https://api.meta.ai only")

        self.reconcile_pending_attempts()

        prices = spec["prices_usd_per_million"]
        per_million = float(self.budget_cfg["tokens_per_million"])
        round_digits = int(self.budget_cfg["usd_round_digits"])
        bytes_per_tok = int(self.budget_cfg["bytes_per_token_floor"])
        safety_pad = int(self.budget_cfg["input_token_safety_pad"])
        ok_low = int(self.ops["http_ok_low"])
        ok_high = int(self.ops["http_ok_high"])

        effective_max_tokens = int(max_tokens) if max_tokens is not None else self.default_max_tokens
        est_in_tokens = (len((system_prompt + user_prompt).encode("utf-8")) // bytes_per_tok) + safety_pad
        reserved_usd = round(
            (est_in_tokens * float(prices["input"]) + effective_max_tokens * float(prices["output"])) / per_million,
            round_digits,
        )

        attempt_id = uuid.uuid4().hex
        started = time.monotonic()
        reserved_day: str | None = None
        dispatched = False
        journal_entry: dict[str, Any] = {
            "attempt_id": attempt_id,
            "model_id": model_id,
            "caller_tag": caller_tag,
            "reserved_usd": reserved_usd,
            "dispatched": False,
            "settlement_status": "not_reserved",
            "accounting_status": "initializing",
            "recorder_status": "pending",
        }

        try:
            api_key = self._read_api_key()
            reserved_day = self.ledger.reserve(reserved_usd)
            journal_entry["reserved_day"] = reserved_day
            journal_entry["settlement_status"] = "reserved_in_flight"
            journal_entry["accounting_status"] = "reserved_in_flight"
        except Exception as exc:
            elapsed = round(time.monotonic() - started, round_digits)
            journal_entry["settlement_status"] = "not_dispatched"
            journal_entry["accounting_status"] = "pre_dispatch_refused"
            self._deliver_attempt_log(
                attempt_id,
                journal_entry,
                {
                    "model_id": model_id,
                    "caller_tag": caller_tag,
                    "ok": False,
                    "dispatched": False,
                    "accounting_status": "pre_dispatch_refused",
                    "elapsed_seconds": elapsed,
                    "cost_usd": 0.0,
                    "reserved_usd": 0.0,
                    "error": type(exc).__name__,
                },
            )
            raise

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(temperature),
        }
        effort = spec.get("reasoning_effort")
        if effort:
            payload["reasoning_effort"] = str(effort)
        if max_tokens is not None or self.default_max_tokens > 0:
            payload["max_tokens"] = effective_max_tokens
        if json_object:
            payload["response_format"] = {"type": "json_object"}

        dispatched = True
        journal_entry["dispatched"] = True
        self._upsert_journal_entry(attempt_id, journal_entry)

        try:
            resp = self._http.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as exc:
            elapsed = round(time.monotonic() - started, round_digits)
            # Transport failure after dispatch: outcome is unknown; keep reservation pending until reconciled.
            journal_entry["settlement_status"] = "pending_unknown_reservation"
            journal_entry["accounting_status"] = "pending_unknown_reservation"
            self._deliver_attempt_log(
                attempt_id,
                journal_entry,
                {
                    "model_id": model_id,
                    "caller_tag": caller_tag,
                    "ok": False,
                    "dispatched": True,
                    "accounting_status": "pending_unknown_reservation",
                    "elapsed_seconds": elapsed,
                    "cost_usd": None,
                    "reserved_usd": reserved_usd,
                    "error": type(exc).__name__,
                },
            )
            raise

        elapsed = round(time.monotonic() - started, round_digits)
        if not (ok_low <= resp.status_code <= ok_high):
            # Explicit non-2xx upstream refusal: safe to release unused reservation.
            try:
                self.ledger.settle(0.0, reserved_usd=reserved_usd, day=reserved_day)
                journal_entry["settlement_status"] = "refunded"
                journal_entry["accounting_status"] = "refused_refunded"
            except Exception:
                journal_entry["settlement_status"] = "pending_known_settlement"
                journal_entry["actual_cost_usd"] = 0.0
                journal_entry["accounting_status"] = "refund_pending"
            err_msg = f"Meta HTTP {resp.status_code}"
            self._deliver_attempt_log(
                attempt_id,
                journal_entry,
                {
                    "model_id": model_id,
                    "caller_tag": caller_tag,
                    "ok": False,
                    "dispatched": True,
                    "accounting_status": journal_entry["accounting_status"],
                    "elapsed_seconds": elapsed,
                    "cost_usd": 0.0,
                    "reserved_usd": reserved_usd,
                    "error": err_msg,
                },
            )
            raise ModelCallError(err_msg)

        # HTTP 2xx received: NEVER refund to zero if parsing fails, because provider already executed.
        try:
            body = resp.json()
            if not isinstance(body, dict):
                raise ValueError("Non-object JSON body")
        except Exception as exc:
            journal_entry["settlement_status"] = "pending_unknown_reservation"
            journal_entry["accounting_status"] = "pending_unknown_reservation"
            err_msg = f"Malformed HTTP {resp.status_code} body ({type(exc).__name__})"
            self._deliver_attempt_log(
                attempt_id,
                journal_entry,
                {
                    "model_id": model_id,
                    "caller_tag": caller_tag,
                    "ok": False,
                    "dispatched": True,
                    "accounting_status": "pending_unknown_reservation",
                    "elapsed_seconds": elapsed,
                    "cost_usd": None,
                    "reserved_usd": reserved_usd,
                    "error": err_msg,
                },
            )
            raise ModelCallError(err_msg) from exc

        choices = body.get("choices") or []
        first_choice = choices[0] if (isinstance(choices, list) and choices) else {}
        content = str(((first_choice.get("message") or {}).get("content")) or "")

        raw_usage = body.get("usage")
        has_exact_usage = (
            isinstance(raw_usage, dict)
            and isinstance(raw_usage.get("prompt_tokens"), int)
            and not isinstance(raw_usage.get("prompt_tokens"), bool)
            and isinstance(raw_usage.get("completion_tokens"), int)
            and not isinstance(raw_usage.get("completion_tokens"), bool)
        )

        if has_exact_usage:
            in_tok: int | None = int(raw_usage["prompt_tokens"])
            out_tok: int | None = int(raw_usage["completion_tokens"])
            actual_usd = round(
                (in_tok * float(prices["input"]) + out_tok * float(prices["output"])) / per_million,
                round_digits,
            )
            journal_entry.update(
                {
                    "actual_cost_usd": actual_usd,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "usage_exact": True,
                    "settlement_status": "pending_known_settlement",
                    "accounting_status": "pending_known_settlement",
                }
            )
            # Persist observed usage & response metadata BEFORE fallible file replacement!
            self._upsert_journal_entry(attempt_id, journal_entry)
            try:
                self.ledger.settle(actual_usd, reserved_usd=reserved_usd, day=reserved_day)
                journal_entry["settlement_status"] = "settled"
                journal_entry["accounting_status"] = "settled_observed_usage"
                self._upsert_journal_entry(attempt_id, journal_entry)
            except Exception:
                # Keep conservative reservation in ledger + pending_known_settlement in journal; never lose response!
                pass
            accounted_cost_usd = actual_usd
            est_out_tokens: int | None = None
        else:
            in_tok = None
            out_tok = None
            est_out_tokens = max(1, len(content.encode("utf-8")) // bytes_per_tok)
            accounted_cost_usd = reserved_usd
            journal_entry.update(
                {
                    "actual_cost_usd": None,
                    "estimated_input_tokens": est_in_tokens,
                    "estimated_output_tokens": est_out_tokens,
                    "usage_exact": False,
                    "settlement_status": "pending_unknown_usage",
                    "accounting_status": "pending_unknown_usage",
                }
            )
            self._upsert_journal_entry(attempt_id, journal_entry)

        if not content.strip():
            err_msg = f"Empty completion content (finish_reason={first_choice.get('finish_reason')})"
            self._deliver_attempt_log(
                attempt_id,
                journal_entry,
                {
                    "model_id": model_id,
                    "caller_tag": caller_tag,
                    "ok": False,
                    "dispatched": True,
                    "usage_exact": has_exact_usage,
                    "accounting_status": journal_entry["accounting_status"],
                    "elapsed_seconds": elapsed,
                    "cost_usd": accounted_cost_usd if has_exact_usage else None,
                    "reserved_usd": reserved_usd,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "error": err_msg,
                },
            )
            raise ModelCallError(err_msg)

        telemetry_delivered = self._deliver_attempt_log(
            attempt_id,
            journal_entry,
            {
                "model_id": model_id,
                "caller_tag": caller_tag,
                "ok": True,
                "dispatched": True,
                "usage_exact": has_exact_usage,
                "accounting_status": journal_entry["accounting_status"],
                "elapsed_seconds": elapsed,
                "cost_usd": accounted_cost_usd if has_exact_usage else None,
                "reserved_usd": reserved_usd,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "estimated_input_tokens": None if has_exact_usage else est_in_tokens,
                "estimated_output_tokens": est_out_tokens,
            },
        )
        return {
            "ok": True,
            "attempt_id": attempt_id,
            "model_id": model_id,
            "model_display": str(spec["model_display"]),
            "content": content,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "estimated_input_tokens": None if has_exact_usage else est_in_tokens,
            "estimated_output_tokens": est_out_tokens,
            "usage_exact": has_exact_usage,
            "accounting_status": journal_entry["accounting_status"],
            "settlement_status": journal_entry["settlement_status"],
            "telemetry_recorded": telemetry_delivered,
            "cost_usd": accounted_cost_usd,
            "reserved_usd": reserved_usd,
            "elapsed_seconds": elapsed,
        }
