# Open-Weights Fine-Tuning: QLoRA & Multi-LoRA Specialist Loop

`ta-amps` treats continuous fine-tuning as ordinary **Tasks** (`verbs`) and **Task Objects** (`nouns`) on [Tessera](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine), without adding a separate model registry, server-side training daemon, or task authority.

> **Scope and honesty boundary:** Every training and evaluation example in these runs comes from owned synthetic MIT repository templates. No Muse API outputs, provider completions, nonprofit files, or private execution traces enter training. Base weights and derived LoRA/QLoRA weights remain private under their respective licenses (*Built with Llama* under the Llama 3.2 Community License). Adapters are recorded as unadmitted candidate manifests, not deployed hosted endpoints or general-capability claims.

## Fine-tuned Meta & Open-Weights Models

| Model | Method & Stack | Compute | Target Specialist Task | Holdout Result |
| --- | --- | --- | --- | --- |
| **Muse Glimmer 30B** | 4-bit `bitsandbytes` QLoRA (`peft` rank 16, alpha 32, 364 modules, 95.8M trainable params) | Free cloud **2x NVIDIA T4 16 GB** (Kaggle) | Typed Tessera MCP tool calls & refusal reasons on unseen tool families | **93.3% -> 99.3%** strict exact match on pre-registered fresh holdout (`+6.0%`, 95% CI `[+2.0%, +10.7%]`, 12/12 checks) |
| **Llama 3.2 3B Instruct** | bf16 `peft` LoRA with gradient checkpointing (rank 16, alpha 32, 24.3M trainable params) | Single local **RTX 3060 12 GB** | Continuous tool-call tuning + pre-registered schema-drop guard | **52.0% -> 72.7%** strict exact match on unseen families; stringified arguments **17.5% -> 0.0%** (Round 2 `79.3%` held back by `0.02` schema guard) |
| **Llama 3.2 1B Instruct** | bf16 `peft` LoRA + multi-LoRA parametric memory (`load_adapter` / `set_adapter`, 11.3M trainable params) | Single local **RTX 3060 12 GB** | Continuous multi-round tuning + hot-swappable specialist routing | **12.0% -> 50.7%** strict exact match across 3 rounds (`8.3% -> 0.0%` stringified values); 3 adapters on 1 base verified at **80/80** byte-identical parity |

## Directory Contents

- [requirements-train.txt](requirements-train.txt): GPU worker Python dependencies (`torch`, `transformers`, `peft`, `bitsandbytes`, `accelerate`, `safetensors`, `huggingface_hub`, `tokenizers`).
- [adapters/provenance.json](adapters/provenance.json): Full SHA-256 provenance manifest linking base shards, promotion rule (`bf0fa821717c2400...`), holdout receipts, and evaluation outputs.
- [adapters/glimmer-30b-qlora/adapter_config.json](adapters/glimmer-30b-qlora/adapter_config.json): PEFT LoRA configuration manifest for the Muse Glimmer 30B QLoRA run.
- [adapters/llama-3.2-1b-lora/adapter_config.json](adapters/llama-3.2-1b-lora/adapter_config.json): PEFT LoRA configuration manifest for the Llama 3.2 1B Instruct continuous tuning loop.
- [adapters/llama-3.2-3b-lora/adapter_config.json](adapters/llama-3.2-3b-lora/adapter_config.json): PEFT LoRA configuration manifest for the Llama 3.2 3B Instruct continuous tuning loop.

## How the Continuous Loop Runs on Tasks & Task Objects

Each tuning round is enqueued by a single `tick` task (`verb.decompose_dag`) in [`tessera/examples/continuous_tuning/`](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine/tree/main/examples/continuous_tuning):

1. `curate_dataset` (`verb.ingest`): Fingerprints synthetic rows across exact content, normalized request, and slot-masked template shape so zero evaluation shapes leak into training.
2. `tune_hyperparameters` (`verb.benchmark_harness`) & `train_adapter` (`verb.solve_draft`): Trains PEFT LoRA / QLoRA candidates with completion-only loss.
3. `evaluate` (`verb.benchmark_harness`): Scores greedy decoding on frozen unseen-family test (`n=150`), a freshly generated unseen-family holdout, and a general sanity split (`n=40`).
4. `decide_promotion` (`verb.verify_gate`): Applies pre-registered rule `tool-call-specialist.promotion` v1 (`sha256: bf0fa821717c2400faab77652f067ea85f2616eea329c6e139af33a423e4b3b7`) with 2,000-resample paired bootstrap confidence intervals.
5. `serve_check` (`verb.benchmark_harness`): Loads one base model once and attaches multiple named specialist LoRA Task Objects (`load_adapter` / `set_adapter`) as **LoRAs as Parametric Memory**, routed per turn alongside [Herma](https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents) context shims.

## Horizontal Worker Swarms + Vertical Compute Cascade

- **Horizontal Data Engine (`256` OpenCode & Multi-Harness Workers across `q01..q16`):** Sharded Tessera queues (`q01..q16`, Durable Object / SQLite shards, content-addressed CAS blobs) let up to `256` concurrent multi-harness workers decompose DAGs, retrieve context via Herma, build Task Objects, and enforce `verifier != builder` checks -- pairing verified execution receipts with rejected-attempt tombstones (`noun.negative_tombstone`) as structured preference / DPO pairs once real-trace consent and grading gates are enabled (all measured adapter runs below trained strictly on owned synthetic MIT templates).
- **4-Tier Vertical Compute Cascade & Composable Modular LoRAs:**
  - **Tier 0 (`< 2 ms`):** Deterministic Herma rules & capability firewall (`respond_directly` + contributor-tier refusal).
  - **Tier 1 (Local GPU):** `Llama 3.2 1B & 3B` with hot-swappable PEFT LoRA Task Objects (`shim-router`, `lora-as-memory`, `task-decomposer`, `verifier-dpo`; tool-call specialist measured at `12.0% -> 50.7%` and `52.0% -> 72.7%`, with 3-adapter multi-LoRA serving verified at `80/80` exact parity).
  - **Tier 2 (Kaggle Free 2xT4):** `Muse Glimmer 30B` NF4 `bitsandbytes` QLoRA (`93.3% -> 99.3%` fresh holdout + LoRA-as-Memory).
  - **Tier 3 (Frontier Standard Mode):** `Meta Muse Spark 1.3` and `Muse Wonder 1.0` reserved for novel synthesis whose verified receipts distill back down into Tier 1 and Tier 2 adapters.

## Reproducing the Loop

```bash
# 1. CPU plumbing verification (zero GPU or external API required):
git clone https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine.git
cd tessera-infrastructure-work-and-storage-engine
make check

# 2. Authorized CUDA GPU worker environment:
python3 -m venv .venv-train && . .venv-train/bin/activate
pip install -r training/requirements-train.txt
PYTHONPATH=src:. python -m examples.continuous_tuning.cli tick \
  --root ./tuning-runs/llama-3.2-1b \
  --base examples/continuous_tuning/recipes/base-llama-3.2-1b-instruct.json \
  --base-path "$TUNING_BASE_PATH" --backend hf
```

## Primary Evidence Bundles

- **Llama 3.2 1B & 3B Continuous Tuning Method & Receipts:** [`tessera/docs/continuous-tuning.md`](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine/blob/main/docs/continuous-tuning.md)
- **Muse Glimmer 30B 2xT4 QLoRA Receipts & Pre-Registered Holdout:** [`agora/evidence/glimmer-30b-2026-10-29/README.md`](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution/blob/main/evidence/glimmer-30b-2026-10-29/README.md)
- **Evaluation Charts & Holdout Guard Analysis:** [`../eval/README.md`](../eval/README.md)
