# Template 3: Fine-Tune a Meta Specialist LoRA Adapter

Use this starter folder to train a hot-swappable **PEFT LoRA Task Object** on **Meta Llama 3.2 1B / 3B Instruct** (local GPU, bf16) or a **4-bit NF4 QLoRA** specialist on **Muse Glimmer 30B** (free 2x NVIDIA T4 GPUs) from owned synthetic MIT task templates.

- **Full measured runs & adapter manifests:** [`../../training/README.md`](../../training/README.md) and [`../../eval/README.md`](../../eval/README.md)
- **Starter script:** [`train_lora_template.py`](train_lora_template.py)
- **Synthetic dataset fixture:** [`sample_synthetic_tasks.json`](sample_synthetic_tasks.json)

## 1. Verify the Dataset & Emit a Deterministic Dry-Run Manifest (No GPU Required)

```bash
python3 templates/finetune-meta-lora/train_lora_template.py \
  --dataset templates/finetune-meta-lora/sample_synthetic_tasks.json \
  --dry-run-manifest /tmp/lora-dry-run-receipt.json
```

## 2. Run bf16 PEFT LoRA on Local Llama 3.2 3B Instruct

```bash
pip install -r training/requirements-train.txt
python3 templates/finetune-meta-lora/train_lora_template.py \
  --base-model meta-llama/Llama-3.2-3B-Instruct \
  --dataset templates/finetune-meta-lora/sample_synthetic_tasks.json \
  --output-dir /tmp/llama32-3b-specialist-lora
```

## 3. Run 4-bit NF4 QLoRA (`--qlora-4bit`) for 30B Open-Weights Checkpoints

```bash
python3 templates/finetune-meta-lora/train_lora_template.py \
  --base-model meta-llama/Llama-3.2-3B-Instruct \
  --qlora-4bit \
  --dataset templates/finetune-meta-lora/sample_synthetic_tasks.json \
  --output-dir /tmp/qlora-nf4-specialist
```

> **Governance & licensing boundary:** Train strictly on owned synthetic MIT templates (`synthetic_mit_template: true`), never on contributor-tier prompts, private NGO records, or unconsented API outputs. Llama 3.2 weights and derivatives remain governed by the Llama 3.2 Community License.
