"""Fine-tune v2: train variants of the Muse Glimmer 30B Task Object adapter and answer eval rows. Modal profile teleionlabs only.
  MODAL_PROFILE=teleionlabs modal run tools/modal_v2.py::run_train --variant a
  MODAL_PROFILE=teleionlabs python tools/modal_v2.py answer <adapter> <in.json> <out.json>   (adapter: none-fix or a v2 variant)
Weights stay private on the volume, with the license and notice beside them. Same recipe as train_h100.py unless a variant says otherwise."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import modal

_P = Path(__file__).resolve()
IN_CONTAINER = str(_P).startswith("/root")
if not IN_CONTAINER and os.environ.get("MODAL_PROFILE") != "teleionlabs":
    raise SystemExit("set MODAL_PROFILE=teleionlabs")
PER_S = 0.001097 + 4 * 0.0000131 + 48 * 0.00000222
app = modal.App("glimmer-pick-v2")
models = modal.Volume.from_name("weight-edit-models")
adapters = modal.Volume.from_name("glimmer-decider")
vol = modal.Volume.from_name("glimmer-pick-v2", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install("torch==2.8.0", "transformers==5.22.0", "peft==0.21.2", "accelerate==1.15.0", "safetensors==0.8.0")
if not IN_CONTAINER:
    NOTES = _P.parents[3]
    ORCH = NOTES / "claude-work-2026-10-31/glimmer-orchestrator"
    image = (image.add_local_file(str(NOTES / "claude-work-2026-10-29/glimmer-kaggle/tools/glimmer_common.py"), "/root/orch/tools/glimmer_common.py")
             .add_local_file(str(ORCH / "h100/train_h100.py"), "/root/orch/h100/train_h100.py")
             .add_local_file(str(_P.parents[1] / "data/train.jsonl"), "/root/data/train.jsonl")
             .add_local_file(str(NOTES / "work-2026-11-04-license/MUSE-MODEL-LICENSE.txt"), "/root/MUSE-MODEL-LICENSE.txt")
             .add_local_file(str(NOTES / "work-2026-11-04-license/NOTICE-META-MODELS.txt"), "/root/NOTICE-META-MODELS.txt"))
VOLS = {"/models": models, "/adapters": adapters, "/vol": vol}
REAL = ["object_names_object", "task_names_object", "cross_family_none", "search_dev_rule_label", "search_dev_hand_checked_none"]
VARIANTS = {
    "a": {"init": None, "lr": 2e-4, "epochs": 2, "sources": None, "note": "fresh rank-16 on seed-pack plus real rows"},
    "b": {"init": "/adapters/none-fix", "lr": 1e-4, "epochs": 2, "sources": REAL, "note": "continue the current adapter on real rows only"},
    "c": {"init": None, "lr": 2e-4, "epochs": 3, "sources": REAL, "note": "fresh rank-16 on real rows only"},
}


def _load():
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tok = AutoTokenizer.from_pretrained("/models/hf-glimmer")
    m = AutoModelForImageTextToText.from_pretrained("/models/hf-glimmer", dtype=torch.bfloat16, device_map={"": "cuda"}, attn_implementation="sdpa", low_cpu_mem_usage=True)
    for name in ("vision_tower", "vision_adapter", "vision_projection"):
        if hasattr(m.model, name):
            delattr(m.model, name)
    return tok, m


@app.function(image=image, gpu="H100", cpu=4, memory=48 * 1024, volumes=VOLS, timeout=3000, scaledown_window=2)
def train(variant: str) -> dict:
    import torch

    sys.path[:0] = ["/root/orch/tools", "/root/orch/h100"]
    import glimmer_common as g
    import train_h100 as T
    from peft import LoraConfig, PeftModel, get_peft_model, get_peft_model_state_dict
    from safetensors.torch import save_file

    v = VARIANTS[variant]
    t0 = time.time()
    out = Path(f"/vol/{variant}/adapter")
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(x) for x in open("/root/data/train.jsonl")]
    if v["sources"]:
        rows = [r for r in rows if r["src"] in v["sources"]]
    tok, m = _load()
    pad = tok.convert_tokens_to_ids("<|finetune_right_pad|>")
    encs, too = [], 0
    for r in rows:
        e = g.encode(tok, r, 1408)
        if e["too_long"]:
            too += 1
            continue
        encs.append(e)
    for p in m.parameters():
        p.requires_grad_(False)
    m.config.use_cache = False
    if v["init"]:
        pm = PeftModel.from_pretrained(m, v["init"], is_trainable=True)
    else:
        L = T.LORA
        pm = get_peft_model(m, LoraConfig(r=L["r"], lora_alpha=L["alpha"], lora_dropout=L["dropout"], target_modules=T.LORA_REGEX, bias="none", task_type="CAUSAL_LM"))
    pm.get_base_model().gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    pm.train()
    bm = pm.get_base_model()
    params = [p for p in pm.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=v["lr"], betas=(0.9, 0.999), eps=1e-8, weight_decay=0.0)
    tr = dict(T.TRAIN, epochs=v["epochs"], micro_batch=8, micro_batch_long=4)
    steps = T.plan_steps(encs, tr)
    log = []
    for k, step in enumerate(steps):
        if time.time() - t0 > 2500:
            break
        ntok = sum(encs[i]["end"] - encs[i]["start"] for (_, _, _, ch, ma) in step for i, mk in zip(ch, ma) if not mk)
        tot = 0.0
        for (_ep, S, K, chunk, masked) in step:
            ids, att, pos, lab, _ = T.train_batch([encs[i] for i in chunk], S, K, pad, masked)
            ids, att, pos, lab = ids.to("cuda"), att.to("cuda"), pos.to("cuda"), lab.to("cuda")
            logits = T.text_forward(bm, ids, T.causal_pad_mask(att), pos, (S - K - 1, S - 1)).float()
            loss = torch.nn.functional.cross_entropy(logits.reshape(-1, logits.shape[-1]), lab.reshape(-1), ignore_index=-100, reduction="sum")
            (loss / max(1, ntok)).backward()
            tot += float(loss.detach())
        gn = torch.nn.utils.clip_grad_norm_(params, 1.0)
        lr = T.lr_at(k, len(steps), v["lr"], 0.1)
        for gr in opt.param_groups:
            gr["lr"] = lr
        opt.step()
        opt.zero_grad(set_to_none=True)
        log.append({"step": k, "loss": round(tot / max(1, ntok), 5), "gn": round(float(gn), 3), "s": round(time.time() - t0, 1)})
        if k % 10 == 0:
            print(log[-1], flush=True)
    sd = {k: x.detach().cpu().contiguous() for k, x in get_peft_model_state_dict(pm).items()}
    save_file(sd, str(out / "adapter_model.safetensors"))
    pm.peft_config["default"].save_pretrained(str(out))
    for n in ("MUSE-MODEL-LICENSE.txt", "NOTICE-META-MODELS.txt"):
        Path(f"/vol/{variant}/{n}").write_bytes(Path(f"/root/{n}").read_bytes())
    sha = hashlib.sha256((out / "adapter_model.safetensors").read_bytes()).hexdigest()
    wall = round(time.time() - t0, 1)
    verified = Path("/models/hf-glimmer/.verified")
    rec = {"variant": variant, "init": v["init"], "lr": v["lr"], "epochs": v["epochs"], "note": v["note"], "sources": v["sources"], "rows_used": len(encs), "rows_too_long": too,
           "steps_planned": len(steps), "steps_done": len(log), "first_loss": log[0]["loss"] if log else None, "last_loss": log[-1]["loss"] if log else None, "adapter_sha256": sha,
           "wall_s": wall, "usd_estimate": round(wall * PER_S, 3), "train_sha256": hashlib.sha256(Path("/root/data/train.jsonl").read_bytes()).hexdigest(),
           "base_on_volume": verified.read_text()[:200] if verified.exists() else "no .verified file on this volume", "recipe": {"lora": T.LORA, "train": tr}}
    (Path(f"/vol/{variant}") / "receipt.json").write_text(json.dumps(rec, indent=1))
    (Path(f"/vol/{variant}") / "train-log.jsonl").write_text("\n".join(json.dumps(x) for x in log))
    vol.commit()
    return rec


@app.function(image=image, gpu="H100", cpu=4, memory=48 * 1024, volumes=VOLS, timeout=3000, scaledown_window=2)
def answer(adapter: str, rows: list, max_new: int = 128, budget_s: float = 2500.0) -> dict:
    import torch
    from peft import PeftModel

    sys.path.insert(0, "/root/orch/tools")
    import glimmer_common as g

    t0 = time.time()
    tok, m = _load()
    path = "/adapters/none-fix" if adapter == "none-fix" else f"/vol/{adapter}/adapter"
    pm = PeftModel.from_pretrained(m, path, adapter_name="orchestrator", is_trainable=False).eval()
    load_s = round(time.time() - t0, 1)
    eos = [tok.convert_tokens_to_ids(x) for x in ("<|eot|>", "<|eom|>", "<|end_of_text|>")]
    out = []
    for row in rows:
        if time.time() - t0 > budget_s:
            out.append({"id": row["id"], "error": "time_budget"})
            continue
        t1 = time.time()
        try:
            prompt = tok.apply_chat_template(row["messages"][:2], tokenize=False, add_generation_prompt=True, **g.template_kwargs(None))
            ids = tok(prompt, add_special_tokens=False, return_tensors="pt")["input_ids"].to("cuda")
            if ids.shape[1] > 2048:
                out.append({"id": row["id"], "error": "prompt_too_long"})
                continue
            with torch.no_grad():
                gen = pm.generate(input_ids=ids, attention_mask=torch.ones_like(ids), max_new_tokens=max_new, do_sample=False, eos_token_id=eos, pad_token_id=eos[0], use_cache=True)
            tk = gen[0, ids.shape[1]:].tolist()
            cut = next((k for k, t in enumerate(tk) if t in eos), None)
            tk = tk[: cut + 1] if cut is not None else tk
            out.append({"id": row["id"], "text": g.extract_user_response(tok.decode(tk, skip_special_tokens=False)), "prompt_tokens": int(ids.shape[1]), "completion_tokens": len(tk), "seconds": round(time.time() - t1, 3)})
        except Exception as exc:  # one bad row must not lose the batch
            out.append({"id": row["id"], "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
    wall = round(time.time() - t0, 1)
    return {"rows": out, "load_s": load_s, "wall_s": wall, "usd_estimate": round(wall * PER_S, 4), "adapter": adapter,
            "adapter_sha256": hashlib.sha256(Path(path + "/adapter_model.safetensors").read_bytes()).hexdigest()}


@app.local_entrypoint()
def run_train(variant: str = "a"):
    r = train.remote(variant)
    (_P.parents[1] / f"records/train-{variant}.json").write_text(json.dumps(r, indent=1))
    print(json.dumps({k: r[k] for k in r if k != "recipe"}))


@app.local_entrypoint()
def run_answer(adapter: str, src: str, dst: str):
    body = json.loads(Path(src).read_text())
    t = time.time()
    res = answer.remote(adapter, body["rows"])
    res["client_wall_s"] = round(time.time() - t, 1)
    Path(dst).write_text(json.dumps(res))
    print(json.dumps({k: res[k] for k in res if k != "rows"}))
