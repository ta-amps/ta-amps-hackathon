"""Batch serving for the fine-tuned Fabric decider: Muse Glimmer 30B plus the adopted rank-16 none-fix adapter.

Modal profile teleionlabs, one H100, nothing warm: the container loads, answers one batch, exits.
  deploy:  MODAL_PROFILE=teleionlabs modal deploy modal_decider.py
  batch:   MODAL_PROFILE=teleionlabs python modal_decider.py in.json out.json
Same settings as the evaluation and the earlier serving test: bf16, greedy, reasoning strength low.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import modal

_P = Path(__file__).resolve()  # in the container this file sits at /root, with none of the local tree around it
COMMON = (_P.parents[2] if len(_P.parents) > 2 else _P.parent) / "claude-work-2026-10-29/glimmer-kaggle/tools/glimmer_common.py"
PER_S = 0.001097 + 4 * 0.0000131 + 48 * 0.00000222  # H100 + 4 cores + 48 GiB, Modal list price read Nov 3
TIMEOUT_S = 600
app = modal.App("glimmer-decider")
models = modal.Volume.from_name("weight-edit-models")
adapters = modal.Volume.from_name("glimmer-decider", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "torch==2.8.0", "transformers==5.22.0", "peft==0.21.2", "accelerate==1.15.0", "safetensors==0.8.0"
)
if COMMON.exists():
    image = image.add_local_file(str(COMMON), "/root/orch/tools/glimmer_common.py")


@app.function(image=image, gpu="H100", cpu=4, memory=48 * 1024, volumes={"/models": models, "/adapters": adapters},
              max_containers=1, scaledown_window=2, timeout=TIMEOUT_S)
def decide(rows: list[dict], max_new: int = 128, time_budget_s: float = 480.0) -> dict:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    sys.path.insert(0, "/root/orch/tools")
    import glimmer_common as g

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained("/models/hf-glimmer")
    m = AutoModelForImageTextToText.from_pretrained("/models/hf-glimmer", dtype=torch.bfloat16, device_map={"": "cuda"},
                                                    attn_implementation="sdpa", low_cpu_mem_usage=True)
    for name in ("vision_tower", "vision_adapter", "vision_projection"):
        if hasattr(m.model, name):
            delattr(m.model, name)
    pm = PeftModel.from_pretrained(m, "/adapters/none-fix", adapter_name="orchestrator", is_trainable=False).eval()
    load_s = round(time.time() - t0, 1)
    eos = [tok.convert_tokens_to_ids(x) for x in ("<|eot|>", "<|eom|>", "<|end_of_text|>")]
    out = []
    for row in rows:
        if time.time() - t0 > time_budget_s:
            out.append({"id": row["id"], "error": "time_budget"})
            continue
        t1 = time.time()
        try:
            prompt = tok.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=True, **g.template_kwargs(None))
            ids = tok(prompt, add_special_tokens=False, return_tensors="pt")["input_ids"].to("cuda")
            if ids.shape[1] > 2048:
                out.append({"id": row["id"], "error": "prompt_too_long", "prompt_tokens": int(ids.shape[1])})
                continue
            with torch.no_grad():
                gen = pm.generate(input_ids=ids, attention_mask=torch.ones_like(ids), max_new_tokens=max_new,
                                  do_sample=False, eos_token_id=eos, pad_token_id=eos[0], use_cache=True)
            tk = gen[0, ids.shape[1]:].tolist()
            cut = next((k for k, t in enumerate(tk) if t in eos), None)
            tk = tk[: cut + 1] if cut is not None else tk
            out.append({"id": row["id"], "text": g.extract_user_response(tok.decode(tk, skip_special_tokens=False)),
                        "prompt_tokens": int(ids.shape[1]), "completion_tokens": len(tk), "seconds": round(time.time() - t1, 3)})
        except Exception as exc:  # one bad row must not lose the batch
            out.append({"id": row["id"], "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
    wall = round(time.time() - t0, 1)
    return {"rows": out, "load_s": load_s, "wall_s": wall, "usd_estimate": round(wall * PER_S, 4)}


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    body = json.loads(Path(src).read_text())
    started = time.time()
    result = modal.Function.from_name("glimmer-decider", "decide").remote(body["rows"], body.get("max_new", 128), body.get("time_budget_s", 480.0))
    result["client_wall_s"] = round(time.time() - started, 1)
    Path(dst).write_text(json.dumps(result))
