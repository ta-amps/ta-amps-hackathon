"""Fine-tuned model canary registry, automatic held-out promotion, gradual rollout, auto-rollback,
independent maker/checker lineage verification, and Thompson-sampling self-tuner.

The rules:
- Automatic promotion when held-out score beats baseline + margin.
- Starts on a small share of live work (`initial_rollout_share`) and advances across `rollout_rungs`,
  switching back to `0.0` automatically if live results drop below `rollback_pass_rate_floor`.
- Records each model's base, training data digest, test results, cost, and restore pointer.
- Enforces strict checker independence: checker must not share `worker_uuid`, `agent_id`,
  `fine_tune_adapter_id`, or `training_data_digest` with the maker it checks.
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .banned_words_guard import BannedWordsGuard, scrub_private_info
from .grid_config import NodeGrid


@dataclass
class LineageDescriptor:
    """Identity, model, adapter, and training-data provenance for maker/checker independence."""

    worker_uuid: str
    agent_id: str
    model_id: str
    fine_tune_adapter_id: str | None = None
    training_data_digest: str | None = None
    ancestor_adapter_ids: tuple[str, ...] = ()
    training_example_ids: tuple[str, ...] | frozenset[str] | None = None


def verify_checker_independence(
    maker: LineageDescriptor,
    checker: LineageDescriptor,
    *,
    require_provenance_attestation: bool = False,
) -> tuple[bool, str]:
    """Return `(True, 'ok')` iff checker shares neither principal, fine-tune ancestry, nor training examples with maker."""
    if not maker.worker_uuid or not checker.worker_uuid:
        return False, "missing_worker_uuid"
    if maker.worker_uuid == checker.worker_uuid:
        return False, "same_worker_uuid"
    if maker.agent_id and checker.agent_id and maker.agent_id == checker.agent_id:
        return False, "same_agent_id"

    maker_adapters = {
        a for a in (maker.fine_tune_adapter_id, *maker.ancestor_adapter_ids) if a
    }
    checker_adapters = {
        a for a in (checker.fine_tune_adapter_id, *checker.ancestor_adapter_ids) if a
    }
    if maker_adapters and checker_adapters and (maker_adapters & checker_adapters):
        return False, "shared_fine_tune_adapter"

    if (
        maker.training_data_digest
        and checker.training_data_digest
        and maker.training_data_digest == checker.training_data_digest
    ):
        return False, "shared_training_data_corpus"

    if maker.training_example_ids is not None and checker.training_example_ids is not None:
        if set(maker.training_example_ids) & set(checker.training_example_ids):
            return False, "overlapping_training_examples"

    if require_provenance_attestation:
        if maker.training_example_ids is None or checker.training_example_ids is None:
            return False, "provenance_not_established"
        if not maker.training_data_digest or not checker.training_data_digest:
            return False, "provenance_not_established"

    return True, "ok"


@dataclass
class CanaryCandidateState:
    candidate_id: str
    display_name: str
    role_scope: str
    base_model: str
    fine_tune_adapter_id: str
    training_data_digest: str
    held_out_score: float
    baseline_score: float
    held_out_breakdown: dict[str, Any]
    training_cost_usd: float
    restore_pointer: str
    serving_endpoint: str | None = None
    status: str = "registered"
    rollout_share: float = 0.0
    rung_index: int = 0
    recent_outcomes: list[bool] = field(default_factory=list)
    samples_at_current_rung: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def revision_signature(self) -> dict[str, Any]:
        return {
            "base_model": self.base_model,
            "fine_tune_adapter_id": self.fine_tune_adapter_id,
            "training_data_digest": self.training_data_digest,
            "held_out_score": self.held_out_score,
            "baseline_score": self.baseline_score,
            "restore_pointer": self.restore_pointer,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "display_name": self.display_name,
            "role_scope": self.role_scope,
            "base_model": self.base_model,
            "fine_tune_adapter_id": self.fine_tune_adapter_id,
            "training_data_digest": self.training_data_digest,
            "held_out_score": self.held_out_score,
            "baseline_score": self.baseline_score,
            "held_out_breakdown": self.held_out_breakdown,
            "training_cost_usd": self.training_cost_usd,
            "restore_pointer": self.restore_pointer,
            "serving_endpoint": self.serving_endpoint,
            "live_serving_active": bool(self.serving_endpoint) and self.rollout_share > 0.0,
            "revision_signature": self.revision_signature(),
            "status": self.status,
            "rollout_share": self.rollout_share,
            "rung_index": self.rung_index,
            "recent_outcomes": list(self.recent_outcomes),
            "samples_at_current_rung": self.samples_at_current_rung,
            "events": list(self.events),
        }


class ModelCanaryRegistry:
    """Manages held-out promotion, gradual live canary rollout, and automatic rollback."""

    def __init__(self, grid: NodeGrid, *, state_path: str | Path | None = None) -> None:
        self.grid = grid
        self.policy = grid.section("canary_policy")
        self.ops = grid.section("operational_constants")
        self.state_path = Path(state_path) if state_path is not None else None
        self.candidates: dict[str, CanaryCandidateState] = {}
        saved_candidates = self._load_saved_candidates()
        for raw in grid.list_section("fine_tuned_candidates"):
            cand = CanaryCandidateState(
                candidate_id=str(raw["candidate_id"]),
                display_name=str(raw["display_name"]),
                role_scope=str(raw["role_scope"]),
                base_model=str(raw["base_model"]),
                fine_tune_adapter_id=str(raw["fine_tune_adapter_id"]),
                training_data_digest=str(raw["training_data_digest"]),
                held_out_score=float(raw["held_out_score"]),
                baseline_score=float(raw["baseline_score"]),
                held_out_breakdown=dict(raw.get("held_out_breakdown") or {}),
                training_cost_usd=float(raw["training_cost_usd"]),
                restore_pointer=str(raw["restore_pointer"]),
                serving_endpoint=raw.get("serving_endpoint"),
            )
            self.candidates[cand.candidate_id] = cand
            saved = saved_candidates.get(cand.candidate_id)
            if isinstance(saved, dict) and self._matches_saved_revision(cand, saved):
                cand.status = str(saved.get("status") or "registered")
                cand.rollout_share = (
                    0.0 if cand.status == "rolled_back" else float(saved.get("rollout_share") or 0.0)
                )
                cand.rung_index = int(saved.get("rung_index") or 0)
                cand.recent_outcomes = [bool(x) for x in (saved.get("recent_outcomes") or [])]
                cand.samples_at_current_rung = int(saved.get("samples_at_current_rung") or 0)
                cand.events = list(saved.get("events") or [])
                self._persist()
            else:
                self.evaluate_held_out_promotion(cand.candidate_id)

    def _load_saved_candidates(self) -> dict[str, Any]:
        if self.state_path is None or not self.state_path.exists():
            return {}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            cands = payload.get("candidates")
            return dict(cands) if isinstance(cands, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _matches_saved_revision(cand: CanaryCandidateState, saved: dict[str, Any]) -> bool:
        saved_sig = saved.get("revision_signature")
        if isinstance(saved_sig, dict):
            return saved_sig == cand.revision_signature()
        return (
            str(saved.get("base_model") or "") == cand.base_model
            and str(saved.get("fine_tune_adapter_id") or "") == cand.fine_tune_adapter_id
            and str(saved.get("training_data_digest") or "") == cand.training_data_digest
            and float(saved.get("held_out_score") or 0.0) == cand.held_out_score
            and float(saved.get("baseline_score") or 0.0) == cand.baseline_score
            and str(saved.get("restore_pointer") or "") == cand.restore_pointer
        )

    def evaluate_held_out_promotion(self, candidate_id: str) -> CanaryCandidateState:
        cand = self.candidates[candidate_id]
        margin = float(self.policy["promotion_margin"])
        rungs = [float(r) for r in self.policy["rollout_rungs"]]
        if cand.held_out_score >= cand.baseline_score + margin:
            cand.status = "canary_active"
            cand.rung_index = 0
            cand.rollout_share = rungs[0] if rungs else float(self.policy["initial_rollout_share"])
            cand.samples_at_current_rung = 0
            cand.events.append(
                {
                    "event": "auto_promoted_to_canary",
                    "held_out_score": cand.held_out_score,
                    "baseline_score": cand.baseline_score,
                    "rollout_share": cand.rollout_share,
                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )
        else:
            cand.status = "held_back_below_baseline"
            cand.rollout_share = 0.0
        self._persist()
        return cand

    def should_route_to_canary(
        self,
        candidate_id: str,
        *,
        rng: random.Random,
        require_live_endpoint: bool = False,
    ) -> bool:
        cand = self.candidates.get(candidate_id)
        if cand is None or cand.status not in {"canary_active", "promoted_default"}:
            return False
        if require_live_endpoint and not cand.serving_endpoint:
            return False
        if cand.rollout_share <= 0.0:
            return False
        if cand.rollout_share >= 1.0:
            return True
        return rng.random() < cand.rollout_share

    def record_live_outcome(self, candidate_id: str, *, passed: bool) -> CanaryCandidateState:
        cand = self.candidates[candidate_id]
        if cand.status == "rolled_back":
            return cand
        window = int(self.policy["rolling_window_size"])
        min_samples = int(self.policy["min_canary_samples_per_rung"])
        min_pass = float(self.policy["min_live_pass_rate"])
        rollback_floor = float(self.policy["rollback_pass_rate_floor"])
        rungs = [float(r) for r in self.policy["rollout_rungs"]]

        cand.recent_outcomes.append(bool(passed))
        if len(cand.recent_outcomes) > window:
            cand.recent_outcomes = cand.recent_outcomes[-window:]
        cand.samples_at_current_rung += 1

        if len(cand.recent_outcomes) >= min_samples:
            live_rate = sum(1 for x in cand.recent_outcomes if x) / len(cand.recent_outcomes)
            if live_rate < rollback_floor:
                cand.status = "rolled_back"
                cand.rollout_share = 0.0
                cand.events.append(
                    {
                        "event": "auto_rollback_on_live_drop",
                        "live_pass_rate": live_rate,
                        "restore_pointer": cand.restore_pointer,
                        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                )
                self._persist()
                return cand
            if cand.samples_at_current_rung >= min_samples and live_rate >= min_pass:
                if cand.rung_index + 1 < len(rungs):
                    cand.rung_index += 1
                    cand.rollout_share = rungs[cand.rung_index]
                    cand.samples_at_current_rung = 0
                    if cand.rollout_share >= 1.0:
                        cand.status = "promoted_default"
                    cand.events.append(
                        {
                            "event": "gradual_rollout_step_up",
                            "live_pass_rate": live_rate,
                            "rollout_share": cand.rollout_share,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        }
                    )
        self._persist()
        return cand

    def snapshot(self) -> dict[str, Any]:
        return {
            "candidates": {cid: c.to_dict() for cid, c in self.candidates.items()},
        }

    def _persist(self) -> None:
        if self.state_path is None:
            return
        dir_mode = int(self.ops["owner_rwx_dir_mode_decimal"])
        file_mode = int(self.ops["owner_rw_file_mode_decimal"])
        self.state_path.parent.mkdir(parents=True, exist_ok=True, mode=dir_mode)
        tmp = self.state_path.with_name(f".{self.state_path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, file_mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(self.snapshot(), indent=1, sort_keys=True))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.state_path)


class TunerLoop:
    """Thompson-sampling self-tuner over (model_id, persona_id) arms + sanitized trace exporter."""

    def __init__(
        self,
        grid: NodeGrid,
        *,
        banned_guard: BannedWordsGuard,
        trace_path: str | Path | None = None,
        seed: int | None = None,
    ) -> None:
        self.grid = grid
        self.tuner_cfg = grid.section("tuner_policy")
        self.ops = grid.section("operational_constants")
        self.banned_guard = banned_guard
        self.trace_path = Path(trace_path) if trace_path is not None else None
        resolved_seed = int(seed if seed is not None else self.tuner_cfg["rng_seed_default"])
        self.rng = random.Random(resolved_seed)
        prior_alpha = float(self.tuner_cfg["prior_alpha"])
        prior_beta = float(self.tuner_cfg["prior_beta"])
        self.posteriors: dict[str, dict[str, float]] = {}
        for persona in grid.list_section("personas"):
            pid = str(persona["persona_id"])
            self.posteriors[pid] = {"alpha": prior_alpha, "beta": prior_beta, "trials": 0.0}

    def validate_milli_score(self, raw_score: Any) -> int | None:
        """Strictly validate a finite integer `0 <= score <= milli_scale` with zero rounding, clamping, or unit guessing."""
        scale = int(self.tuner_cfg["milli_scale"])
        if isinstance(raw_score, bool) or not isinstance(raw_score, int):
            return None
        if raw_score < 0 or raw_score > scale:
            return None
        return int(raw_score)

    def normalize_milli_score(self, raw_score: int | float, *, unit: str = "milli") -> int:
        """Preserve declared milli integers unchanged; convert fraction/percent ONLY when `unit` is explicitly specified."""
        scale = int(self.tuner_cfg["milli_scale"])
        pct_ceiling = int(self.tuner_cfg["score_percent_ceiling"])
        mult = int(self.tuner_cfg["percent_to_milli_multiplier"])
        if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)) or not math.isfinite(float(raw_score)):
            raise ValueError("Score must be a finite numeric value")
        if unit == "milli":
            checked = self.validate_milli_score(raw_score)
            if checked is None:
                raise ValueError(f"Milli score must be an integer in 0..{scale}")
            return checked
        val = float(raw_score)
        if unit == "fraction":
            if val < 0.0 or val > 1.0:
                raise ValueError("Fraction score out of 0.0..1.0 range")
            return int(round(val * scale))
        if unit == "percent":
            if val < 0.0 or val > float(pct_ceiling):
                raise ValueError("Percent score out of range")
            return int(round(val * mult))
        raise ValueError(f"Unsupported score unit: {unit}")

    def select_persona(self, *, role: str, strategy: str = "thompson_canary_hybrid") -> dict[str, Any]:
        matching = [p for p in self.grid.list_section("personas") if str(p.get("role")) == role]
        if not matching:
            matching = self.grid.list_section("personas")
        if strategy == "deterministic_exploit":
            return max(
                matching,
                key=lambda p: (
                    self.posteriors[str(p["persona_id"])]["alpha"]
                    / (
                        self.posteriors[str(p["persona_id"])]["alpha"]
                        + self.posteriors[str(p["persona_id"])]["beta"]
                    )
                ),
            )
        return max(
            matching,
            key=lambda p: self.rng.betavariate(
                self.posteriors[str(p["persona_id"])]["alpha"],
                self.posteriors[str(p["persona_id"])]["beta"],
            ),
        )

    def record_outcome_and_trace(
        self,
        *,
        persona_id: str,
        model_id: str,
        role: str,
        prompt_text: str,
        response_text: str,
        raw_quality_score: int | float,
        cost_usd: float,
        maker_checker_independent: bool = True,
        task_id: str | None = None,
        attempt_status: str = "completed",
        training_admitted: bool = False,
        target_verdict: str | None = None,
        delivery_status: str = "delivered",
        checker_correctness: str = "unknown",
    ) -> dict[str, Any]:
        checked_milli = self.validate_milli_score(raw_quality_score)
        milli = checked_milli if checked_milli is not None else 0
        pass_threshold = int(self.tuner_cfg["milli_pass_threshold"])
        banned_hits = self.banned_guard.scan_text(response_text, include_visible_rules=False)
        invariants_ok = (len(banned_hits) == 0) and bool(maker_checker_independent) and (checked_milli is not None)
        verdict_allows_pass = target_verdict in {None, "CONFIRMED"}
        passed = invariants_ok and verdict_allows_pass and (milli >= pass_threshold)

        post = self.posteriors.setdefault(
            persona_id,
            {
                "alpha": float(self.tuner_cfg["prior_alpha"]),
                "beta": float(self.tuner_cfg["prior_beta"]),
                "trials": 0.0,
            },
        )
        if role == "checker":
            if not invariants_ok or attempt_status == "malformed_checker_output" or checker_correctness == "incorrect":
                post["trials"] += 1.0
                post["beta"] += 1.0
            elif checker_correctness == "correct":
                post["trials"] += 1.0
                post["alpha"] += 1.0
        else:
            post["trials"] += 1.0
            if passed:
                post["alpha"] += 1.0
            else:
                post["beta"] += 1.0

        max_chars = int(self.ops["max_prompt_chars"])
        trace_row = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "role": role,
            "model_id": model_id,
            "persona_id": persona_id,
            "task_id": task_id,
            "attempt_status": attempt_status,
            "delivery_status": delivery_status,
            "target_verdict": target_verdict,
            "checker_correctness": checker_correctness if role == "checker" else None,
            "training_admitted": bool(training_admitted) and passed,
            "quality_milli": milli,
            "passed": passed,
            "invariants_ok": invariants_ok,
            "banned_hits_count": len(banned_hits),
            "cost_usd": cost_usd,
            "private_info_filtered": True,
            "input_sanitized": scrub_private_info(prompt_text)[:max_chars],
            "output_sanitized": self.banned_guard.sanitize_visible_text(response_text)[:max_chars],
        }
        if self.trace_path is not None and invariants_ok:
            dir_mode = int(self.ops["owner_rwx_dir_mode_decimal"])
            file_mode = int(self.ops["owner_rw_file_mode_decimal"])
            self.trace_path.parent.mkdir(parents=True, exist_ok=True, mode=dir_mode)
            fd = os.open(self.trace_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, file_mode)
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(trace_row, sort_keys=True) + "\n")
        return trace_row
