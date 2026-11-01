# Open-Weights Fine-Tuning: Muse Glimmer 30B QLoRA, LoRA-as-Memory & Governed Meta API Loop

`ta-amps` treats continuous fine-tuning and specialist adapter routing as ordinary **Tasks** (`verbs`) and **Task Objects** (`nouns`) on [Tessera](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine), without adding a separate model registry, server-side training daemon, or task authority.

> **Scope and honesty boundary:** Every training and evaluation example in the measured adapter runs below comes from owned deterministic made-up MIT repository templates. No Muse API outputs, provider completions, nonprofit files, or private execution traces entered training. Base weights and derived LoRA/QLoRA `.safetensors` weights remain private under their respective licenses. Adapters are recorded as unadmitted candidate manifests, not deployed hosted endpoints or general-capability claims.

## Measured Meta & Open-Weights Fine-Tuning Runs

| Model | Method & Stack | Compute | Target Specialist Task | Pre-Registered Holdout Result |
| --- | --- | --- | --- | --- |
| **Muse Glimmer 30B** (`glimmer-30b-qlora`) | 4-bit NF4 `bitsandbytes` QLoRA (`peft` `r=16, alpha=32`, 364 modules, 95.8M trainable params) | Free cloud **2x NVIDIA T4 16 GB** (Kaggle, `$0`) | Typed Tessera MCP tool calls & refusal reasons on unseen tool families (`n=150`) | **93.3% -> 99.3%** strict exact match (`+6.0%`, 95% CI `[+2.0%, +10.7%]`, `100.0%` valid JSON, 12/12 promotion checks) |
| **Muse Glimmer 30B** (`glimmer-30b-lora-memory`) | 2-GPU layer-24 sharded `fp16` `peft` LoRA-as-Memory (`r=16, alpha=32`, 364 modules, 95.8M trainable params, 48 steps) | Free cloud **2x NVIDIA T4 16 GB** (Kaggle, peak `10.5` / `11.6 GiB`, `$0`) | **LoRA-as-Memory** (`0` shim tokens) on post-cutoff 2026 Task Objects + NGO intake splits (`n=120`) | **0.0% (Base) / 29.2% (BM25 Shim) -> 62.5% (LoRA-as-Memory at 0 shim tokens)** (`+33.3 pp` vs BM25 Shim, 95% CI `[+22.5, +44.2]` pp, `100.0%` valid schema, **`2.28x` faster p50** `19.75s -> 8.67s`, `100.0%` `builder != reviewer` & contributor-tier safety) |

## Directory Contents

- [requirements-train.txt](requirements-train.txt): GPU worker Python dependencies (`torch`, `transformers`, `peft`, `bitsandbytes`, `accelerate`, `safetensors`, `huggingface_hub`, `tokenizers`).
- [adapters/provenance.json](adapters/provenance.json): Full SHA-256 provenance manifest linking base shards, promotion rule (`bf0fa821717c2400...`), holdout receipts, and evaluation outputs across both verified Muse Glimmer 30B adapter runs.
- [adapters/glimmer-30b-qlora/adapter_config.json](adapters/glimmer-30b-qlora/adapter_config.json): PEFT LoRA configuration manifest for the Muse Glimmer 30B 4-bit NF4 tool-call specialist.
- [adapters/glimmer-30b-lora-memory/adapter_config.json](adapters/glimmer-30b-lora-memory/adapter_config.json): PEFT LoRA configuration manifest for the Muse Glimmer 30B 2xT4 LoRA-as-Memory specialist.
- [`../templates/finetune-meta-lora/`](../templates/finetune-meta-lora/README.md): Copy-paste starter script ([`train_lora_template.py`](../templates/finetune-meta-lora/train_lora_template.py)) and made-up MIT fixture ([`sample_practice_tasks.json`](../templates/finetune-meta-lora/sample_practice_tasks.json)).

---

## Step-by-Step Guide 1: Fine-Tune Muse Glimmer 30B on Free Kaggle 2xT4 GPUs

`Muse Glimmer 30B` (`48` language layers, `364` linear attention/MLP projections) fits comfortably inside Kaggle's free weekly `2x NVIDIA Tesla T4` (`2 x 16 GB = 32 GB` total VRAM) quota using either **4-bit NF4 QLoRA** (`bitsandbytes`) or **2-GPU layer-24 sharding** (when dropping the unused vision tower for text/JSON Tasks):

1. **Pre-register holdout digests before training:** Hash `train.jsonl`, `dev.jsonl`, `test_holdout.jsonl`, and `sanity.jsonl` with SHA-256 and commit the receipt JSON so evaluation splits are immutable before any GPU sees them.
2. **Configure Kaggle `kernel-metadata.json` for `2x Tesla T4`:**
   ```json
   {
     "id": "<your-handle>/glimmer-30b-specialist",
     "title": "glimmer-30b-specialist",
     "code_file": "train_glimmer_qlora.py",
     "language": "python",
     "kernel_type": "script",
     "is_private": true,
     "enable_gpu": true,
     "enable_internet": true,
     "machine_shape": "NvidiaTeslaT4",
     "dataset_sources": ["<your-handle>/practice-mit-task-objects"]
   }
   ```
3. **Attach PEFT QLoRA / LoRA across `cuda:0` and `cuda:1`:**
   ```python
   import torch
   from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
   from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

   bnb_cfg = BitsAndBytesConfig(
       load_in_4bit=True,
       bnb_4bit_quant_type="nf4",
       bnb_4bit_use_double_quant=True,
       bnb_4bit_compute_dtype=torch.float16,
   )
   model = AutoModelForCausalLM.from_pretrained(
       MODEL_PATH,
       quantization_config=bnb_cfg,
       device_map="auto",          # shards across cuda:0 and cuda:1 on Kaggle 2xT4
       torch_dtype=torch.float16,
   )
   model.gradient_checkpointing_enable()
   model = prepare_model_for_kbit_training(model)

   lora_cfg = LoraConfig(
       r=16,
       lora_alpha=32,
       lora_dropout=0.05,
       bias="none",
       task_type="CAUSAL_LM",
       target_modules=r"model\.language_model\.layers\.\d+\.(self_attn\.(q|k|v|o)_proj|mlp\.(gate|up|down)_proj)",
   )
   model = get_peft_model(model, lora_cfg)
   ```
4. **Verify reload parity & promotion gate (`bf0fa821717c2400...`):** After completion-only SFT (`lr=2e-4`, cosine schedule, `max_grad_norm=1.0`), verify `with model.disable_adapter()` matches base logits (`max_abs == 0.0`), reload `adapter_model.safetensors` onto a fresh base checkpoint (`8/8` byte-exact greedy decode), and run 2,000-resample paired bootstrap CI checks before recording promotion candidacy.

---

## Step-by-Step Guide 2: Hot-Swapping Specialist Adapters on One Open-Weights Base

Instead of training one monolithic fine-tune where DAG decomposition, retrieval pointers, MCP tool syntax, and verification rubrics interfere with one another, `ta-amps` treats each specialist PEFT adapter as a named **Task Object** (`noun`) attached to one shared open-weights base model in VRAM. Set `BASE_MODEL` to the checkpoint you are licensed to use; this guide makes no claim about results for any particular base:

- `lora.task-decomposer`: Decomposes plain-English intake briefs (`verb.decompose_dag`) into bounded build and review sub-tasks (`builder != reviewer`, `eq02 -> eq03`).
- `lora.shim-retriever`: Selects compact Herma `[NOUN/VERB CONTEXT]` pointers or answers directly (`respond_directly`).
- `lora.builder-toolcalls`: Emits schema-valid Tessera MCP JSON-RPC arguments (`claim`, `get_record`, `put_record`, `submit`).
- `lora.verifier-dpo`: SFT followed by Direct Preference Optimization (`beta = 0.1`) on verified outcomes vs. rejected-attempt tombstones (`noun.negative_tombstone`), aimed at digest mismatches, self-approval attempts, and contributor-tier privacy leaks.

```python
import os
from peft import PeftModel
from transformers import AutoModelForCausalLM

base = AutoModelForCausalLM.from_pretrained(os.environ["BASE_MODEL"], torch_dtype="bfloat16", device_map="cuda:0")
model = PeftModel.from_pretrained(base, "./adapters/lora.task-decomposer", adapter_name="decompose")
model.load_adapter("./adapters/lora.shim-retriever", adapter_name="retrieve")
model.load_adapter("./adapters/lora.builder-toolcalls", adapter_name="build")
model.load_adapter("./adapters/lora.verifier-dpo", adapter_name="review")

# Zero extra base-model VRAM; switch specialist weights per leased Tessera verb kind:
model.set_adapter("review")
```

For high-throughput multi-worker HTTP serving, pass the same named adapters directly to `vLLM`:

```bash
vllm serve "$BASE_MODEL" \
  --enable-lora \
  --max-lora-rank 16 \
  --lora-modules \
    decompose=./adapters/lora.task-decomposer \
    retrieve=./adapters/lora.shim-retriever \
    build=./adapters/lora.builder-toolcalls \
    review=./adapters/lora.verifier-dpo \
  --port 8000
```

---

## Step-by-Step Guide 3: How Meta Hackathon `api.meta.ai` Credits Feed the Governed Loop

Meta's `api.meta.ai` platform (`muse-spark-1.3-contributor` at `$0.10 / $0.20` per 1M input/output tokens and `$0.002` per 1M cached input tokens, plus `Muse Wonder 1.0` and `Muse Code`) powers end-to-end multi-harness verification at penny-scale cost while enforcing strict privacy and licensing separation:

1. **Contributor-Tier Firewall (`ContributorTierRefusedError` & `HTTP 403`):**
   - `muse-spark-1.3-contributor` is used **exclusively** on `100%` made-up or public-domain Task Objects.
   - If a task references any private, sensitive, or NGO-owned record (`visibility_scope != public` and not marked as a made-up practice case), Eranos raises `ContributorTierRefusedError` and Herma returns `HTTP 403 contributor_tier_refused` before any network socket opens.
   - Note on `Muse Code` CLI flags: `--contributor-mode off` only toggles a CLI mode flag; the contributor tier on `api.meta.ai` is selected explicitly via `--model muse-spark-1.3-contributor` routed through a local budget-capped gate (`CAP_USD <= 2.00`).
2. **Multi-Harness Builder + Independent Reviewer Execution (`< $0.03` per E2E Kit):**
   - **Builder (`Muse Code` on `muse-spark-1.3-contributor` via `/v1/responses`):** Claims an `eq02` `build` task under a fenced lease, fetches the made-up input Task Object, writes stdlib Python code + unit tests + README, runs acceptance checks, stores 4 content-addressed Task Objects (`put_record`), and submits with SHA-256 digests (`receipt_hash`).
   - **Independent Reviewer (`nanoMuse` on `muse-spark-1.3-contributor` via `/v1/chat/completions`):** Using a **distinct scoped API key** (`reviewer_key_id != builder_key_id`), claims the dependent `eq03` `review` task, recomputes every SHA-256 digest and `blob_sha256` from scratch, re-executes the unit tests and coverage checks in an isolated workspace, writes the `kit.reviews` Task Object, and submits an independent verdict (`approve` or `refuse`) while holding final publication for a human operator.
3. **Measured Training on Made-Up Data vs. Proposed Live Distillation (Honesty Boundary):**
   - **Measured today:** All open-weights LoRA/QLoRA runs (`Muse Glimmer 30B`) trained **100% on owned deterministic made-up MIT Python generators** -- zero `api.meta.ai` completions entered those adapter weights, ensuring clean open-weights licensing. Meanwhile, our `256`-worker OpenCode/MCP swarm benchmark (`1,000` made-up workflows, `25,620` MCP calls at `54.4 ms` p50, `$0.0007` spend) and real `Muse Code` + `nanoMuse` `api.meta.ai` E2E runs prove the multi-harness execution, receipting, and `noun.negative_tombstone` DPO pair-collection plumbing end to end.
   - **Proposed next step (governed production loop):** When organizations or opted-in contributors explicitly authorize trace learning under Standard (non-contributor) mode and license-compatible terms, Tessera's curation task (`curate_dataset`) filters verified multi-step frontier receipts (`ok: true` + independent `approved: true`) alongside rejected attempts (`ok: false` tombstones) into three-fingerprint-deduplicated SFT and DPO rounds for Tier 1 (`Muse Glimmer 30B`) adapters.

---

## Reproducing the Loop Locally

```bash
# 1. CPU plumbing & starter dry-run receipt (zero GPU or external API required):
make check
python3 templates/finetune-meta-lora/train_lora_template.py \
  --dataset templates/finetune-meta-lora/sample_practice_tasks.json \
  --dry-run-manifest /tmp/lora-dry-run-receipt.json

# 2. Full Tessera continuous tuning loop on a local CUDA GPU:
git clone https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine.git
cd tessera-infrastructure-work-and-storage-engine
make check
python3 -m venv .venv-train && . .venv-train/bin/activate
pip install -r ../ta-amps-hackathon/training/requirements-train.txt
# BASE_NOUN: the base-model noun JSON for the open-weights checkpoint you are licensed to use
# (format: see examples/continuous_tuning/recipes/); TUNING_BASE_PATH: where its weights live.
PYTHONPATH=src:. python -m examples.continuous_tuning.cli tick \
  --root ./tuning-runs/my-run \
  --base "$BASE_NOUN" \
  --base-path "$TUNING_BASE_PATH" --backend hf
```

## Primary Evidence Bundles

- **Muse Glimmer 30B 2xT4 QLoRA Receipts & Pre-Registered Holdout:** [`agora/evidence/glimmer-30b-2026-10-29/README.md`](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution/blob/main/evidence/glimmer-30b-2026-10-29/README.md)
- **Evaluation Charts, LoRA-as-Memory Benchmark & Holdout Guard Analysis:** [`../eval/README.md`](../eval/README.md)
