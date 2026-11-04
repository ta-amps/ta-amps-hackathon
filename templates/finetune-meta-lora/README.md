# Template 3: Fine-Tune a Meta Specialist LoRA Adapter

Use this starter folder to train a hot-swappable **PEFT LoRA task object** on **Meta Llama 3.2 1B / 3B Instruct** (`bf16` on 1 local GPU or `fp16` on Kaggle `2xT4`) or a **4-bit NF4 QLoRA / LoRA-as-Memory** specialist on **Muse Glimmer 30B** (free Kaggle `2x NVIDIA Tesla T4` GPUs, `32 GB` total VRAM) from owned made-up MIT task templates.

- **Full measured runs, step-by-step Kaggle/vLLM/Meta-API guides & SHA-256 source:** [`../../training/README.md`](../../training/README.md) and [`../../eval/README.md`](../../eval/README.md)
- **Starter script:** [`train_lora_template.py`](train_lora_template.py)
- **Practice dataset fixture:** [`sample_practice_tasks.json`](sample_practice_tasks.json)

## 1. Verify the Dataset & Emit a Deterministic Dry-Run Manifest (No GPU Required)

```bash
python3 templates/finetune-meta-lora/train_lora_template.py \
  --dataset templates/finetune-meta-lora/sample_practice_tasks.json \
  --dry-run-manifest /tmp/lora-dry-run-receipt.json
```

## 2. Train Role-Switched Modular PEFT LoRA on Llama 3.2 1B / 3B Instruct

```bash
pip install -r training/requirements-train.txt
python3 templates/finetune-meta-lora/train_lora_template.py \
  --base-model meta-llama/Llama-3.2-3B-Instruct \
  --dataset templates/finetune-meta-lora/sample_practice_tasks.json \
  --output-dir /tmp/llama32-3b-specialist-lora
```

Attach multiple specialist task objects (`decompose`, `retrieve`, `build`, `review`) to one shared `Llama 3.2` checkpoint via `peft` `load_adapter()` / `set_adapter(role)` or `vllm serve --enable-lora --lora-modules ...` with zero extra base-model VRAM.

## 3. Train 4-bit NF4 QLoRA (`--qlora-4bit`) on Muse Glimmer 30B (Free Kaggle 2xT4)

```bash
python3 templates/finetune-meta-lora/train_lora_template.py \
  --base-model /kaggle/input/muse-glimmer-30b \
  --qlora-4bit \
  --dataset templates/finetune-meta-lora/sample_practice_tasks.json \
  --output-dir /kaggle/working/glimmer-30b-qlora-specialist
```

On Kaggle `2x Tesla T4` (`"machine_shape": "NvidiaTeslaT4"`), `device_map="auto"` shards `Muse Glimmer 30B` across `cuda:0` and `cuda:1` (`95.8M` trainable params across `364` attention/MLP projections at `r=16, alpha=32`).

## 4. Meta `api.meta.ai` Contributor-Tier & Privacy Boundary

> **Governance & licensing boundary:** Train open-weights LoRA/QLoRA adapters strictly on owned deterministic made-up MIT templates or explicitly consented Standard-mode traces under license-compatible terms -- never on private NGO records, unconsented user data, or contributor-tier outputs. When running made-up E2E benchmarks on `api.meta.ai` competition credits, use `--model muse-spark-1.3-contributor` behind a hard budget cap (`< $2.00`) and enforce `ContributorTierRefusedError` / `HTTP 403 contributor_tier_refused` whenever non-public task objects are in scope. Llama 3.2 weights and derivatives remain governed by the Llama 3.2 Community License (*Built with Llama*).
