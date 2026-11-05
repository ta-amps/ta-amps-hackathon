"""Muse calls for the assembler: Meta API, standard tier, on the owner's shared ledger, stopping at the $145 total. Every call is journaled, failures too."""
from __future__ import annotations
import json, os, threading, time
from pathlib import Path
from typing import Any
from eranos.model_client import Ledger, MetaModel, UsageMeter
HERE = Path(__file__).resolve().parent
SHARED = Path.home() / ".local/state/eranos-worker/meta-spend.json"
RATES = {"muse-spark-1.3": {"input": 1.25, "output": 4.25}, "muse-wonder-1.0": {"input": 4.0, "output": 20.0}}
DISPLAY = {"muse-spark-1.3": "Muse Spark 1.3", "muse-wonder-1.0": "Muse Wonder 1.0"}
_cache: dict[str, MetaModel] = {}
_lock = threading.Lock()
def model(model_id: str, max_tokens: int = 1500) -> MetaModel:
    key = f"{model_id}:{max_tokens}"
    with _lock:
        if key not in _cache:
            _cache[key] = MetaModel({"id": model_id, "model_display": DISPLAY[model_id], "base_url": "https://api.meta.ai/v1", "prices_usd_per_million": RATES[model_id],
                                     "max_tokens": max_tokens, "reasoning_effort": "low"}, ledger=Ledger(SHARED, daily_usd=145.0, total_usd=145.0))
        return _cache[key]
def journal(row: dict[str, Any]) -> None:
    with _lock, open(HERE / "records/model_attempts.jsonl", "a") as f:
        f.write(json.dumps({"at": time.strftime("%FT%TZ", time.gmtime()), **row}) + "\n")
def chat_json(model_id: str, system: str, user: str, *, purpose: str, max_tokens: int = 1500) -> tuple[Any, float]:
    meter = UsageMeter(); t0 = time.time()
    try:
        out = model(model_id, max_tokens).chat_json(system, user, meter=meter, max_tokens=max_tokens, temperature=0.0)
        journal({"purpose": purpose, "model": model_id, "ok": True, "usd": meter.cost_usd, "in": meter.input_tokens, "out": meter.output_tokens, "s": round(time.time() - t0, 2)})
        return out, meter.cost_usd
    except Exception as exc:
        journal({"purpose": purpose, "model": model_id, "ok": False, "usd": meter.cost_usd, "error": f"{type(exc).__name__}: {str(exc)[:200]}", "s": round(time.time() - t0, 2)})
        raise
