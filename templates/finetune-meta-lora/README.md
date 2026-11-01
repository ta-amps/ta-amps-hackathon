# Template 3: Fine-Tune a Meta Specialist LoRA Adapter

Use this starter folder to train a hot-swappable **PEFT LoRA Task Object** on an open-weights base model of your choice (`bf16` on 1 local GPU or `fp16` on Kaggle `2xT4`) or a **4-bit NF4 QLoRA / LoRA-as-Memory** specialist on **Muse Glimmer 30B** (free Kaggle `2x NVIDIA Tesla T4` GPUs, `32 GB` total VRAM) from owned made-up MIT task templates.

- **Full measured runs, step-by-step Kaggle/vLLM/Meta-API guides & SHA-256 provenance:** [`../../training/README.md`](../../training/README.md) and [`../../eval/README.md`](../../eval/README.md)
- **Starter script:** [`train_lora_template.py`](train_lora_template.py)
- **Made-up dataset fixture:** [`sample_practice_tasks.json`](sample_practice_tasks.json)

## 1. Verify the Dataset & Emit a Deterministic Dry-Run Manifest (No GPU Required)

```bash
python3 templates/finetune-meta-lora/train_lora_template.py \
  --dataset templates/finetune-meta-lora/sample_practice_tasks.json \
  --dry-run-manifest /tmp/lora-dry-run-receipt.json
```

## 2. Train a Specialist PEFT LoRA on an Open-Weights Base of Your Choice

```bash
pip install -r training/requirements-train.txt
# BASE_MODEL: a local path or Hugging Face id of an open-weights checkpoint you are licensed to use
python3 templates/finetune-meta-lora/train_lora_template.py \
  --base-model "$BASE_MODEL" \
  --dataset templates/finetune-meta-lora/sample_practice_tasks.json \
  --output-dir /tmp/specialist-lora
```

`--base-model` has no default and is required for training; the dry run in step 1 does not need it. Examples are rendered with the base model's own chat template. Attach multiple specialist Task Objects (`decompose`, `retrieve`, `build`, `review`) to one shared base checkpoint via `peft` `load_adapter()` / `set_adapter(role)` or `vllm serve --enable-lora --lora-modules ...` with zero extra base-model VRAM.

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

> **Governance & licensing boundary:** Train open-weights LoRA/QLoRA adapters strictly on owned deterministic made-up MIT templates (`practice_mit_template: true`) or explicitly consented Standard-mode traces under license-compatible terms -- never on private NGO records, unconsented user data, or contributor-tier outputs. When running made-up E2E benchmarks on `api.meta.ai` competition credits, use `--model muse-spark-1.3-contributor` behind a hard budget cap (`< $2.00`) and enforce `ContributorTierRefusedError` / `HTTP 403 contributor_tier_refused` whenever non-public Task Objects are in scope. Open-weights base models and the adapters derived from them remain governed by each model's own license.
