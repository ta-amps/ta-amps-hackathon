#!/usr/bin/env python3
"""Starter PEFT LoRA / 4-bit NF4 QLoRA fine-tuning template for open weights.

Supports:
  1. Offline schema + provenance check (`--dry-run-manifest`) with stdlib only,
     emitting a deterministic `practice_template_run` receipt for CI and prep.
  2. Real bf16 PEFT LoRA or 4-bit NF4 `bitsandbytes` QLoRA (`--qlora-4bit`) on the
     open-weights base named by `--base-model` (required, no default), when `torch`,
     `transformers`, and `peft` are installed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DEFAULT_DATASET = Path(__file__).resolve().with_name("sample_practice_tasks.json")
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def load_verified_practice_examples(dataset_path: Path) -> tuple[list[dict], str]:
    raw = dataset_path.read_bytes()
    rows = json.loads(raw.decode("utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("dataset must be a non-empty JSON list")
    for idx, row in enumerate(rows):
        if not row.get("practice_mit_template"):
            raise ValueError(f"row {idx}: practice_mit_template=true is required")
        for key in ("system", "user", "assistant"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"row {idx}: missing non-empty {key!r}")
        json.loads(row["assistant"])
    return rows, hashlib.sha256(raw).hexdigest()


def build_dry_run_manifest(args: argparse.Namespace, rows: list[dict], sha256_hex: str) -> dict:
    return {
        "status": "practice_template_run",
        "admitted_artifact": False,
        "base_model": args.base_model,
        "quantization": "nf4_4bit_qlora" if args.qlora_4bit else "bf16_peft_lora",
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "target_modules": TARGET_MODULES,
        "examples_verified": len(rows),
        "dataset_sha256": sha256_hex,
    }


def render_example(tokenizer, row: dict) -> str:
    """Render one example with the base model's own chat template (plain text if it has none)."""
    messages = [
        {"role": "system", "content": row["system"]},
        {"role": "user", "content": row["user"]},
        {"role": "assistant", "content": row["assistant"]},
    ]
    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(messages, tokenize=False)
    return "\n".join(f"{m['role']}: {m['content']}" for m in messages)


def run_peft_training(args: argparse.Namespace, rows: list[dict], sha256_hex: str) -> dict:
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    quant_cfg = None
    if args.qlora_4bit:
        quant_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quant_cfg,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    if args.qlora_4bit:
        model = prepare_model_for_kbit_training(model)

    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=TARGET_MODULES,
    )
    peft_model = get_peft_model(model, lora_cfg)
    peft_model.train()

    optimizer = torch.optim.AdamW(peft_model.parameters(), lr=args.lr)
    final_loss = 0.0
    for _ in range(args.epochs):
        for row in rows:
            prompt = render_example(tokenizer, row)
            batch = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512).to(peft_model.device)
            batch["labels"] = batch["input_ids"].clone()
            out = peft_model(**batch)
            out.loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            final_loss = float(out.loss.detach().cpu().item())

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    peft_model.save_pretrained(out_dir)
    receipt = build_dry_run_manifest(args, rows, sha256_hex)
    receipt["status"] = "smoke_training_completed_not_promoted"
    receipt["final_loss"] = round(final_loss, 6)
    (out_dir / "training_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-model",
        default=None,
        help="Open-weights base: a local path or Hugging Face id you are licensed to use (required for training)",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", default="/tmp/ta-amps-lora-template")
    parser.add_argument("--qlora-4bit", action="store_true", help="Enable 4-bit NF4 QLoRA via bitsandbytes")
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument(
        "--dry-run-manifest",
        default="",
        help="Validate dataset offline and write deterministic receipt JSON (pass '-' for stdout)",
    )
    args = parser.parse_args(argv)
    if not args.dry_run_manifest and not args.base_model:
        parser.error("--base-model is required for training (it is optional with --dry-run-manifest)")

    rows, sha256_hex = load_verified_practice_examples(args.dataset)
    if args.dry_run_manifest:
        manifest = build_dry_run_manifest(args, rows, sha256_hex)
        payload = json.dumps(manifest, indent=2, sort_keys=True)
        if args.dry_run_manifest != "-":
            Path(args.dry_run_manifest).write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return 0

    receipt = run_peft_training(args, rows, sha256_hex)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
