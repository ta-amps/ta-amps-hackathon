# Pre-Registered Evaluation, LoRA-as-Memory & Scalability Benchmarks

Every model-tuning round in `ta-amps` is scored by a deterministic evaluation Task (`verb.benchmark_harness`) and gated by a pre-registered promotion rule Task Object (`tool-call-specialist.promotion` v1, `sha256: bf0fa821717c2400faab77652f067ea85f2616eea329c6e139af33a423e4b3b7`) fixed before training runs.

> **What these benchmarks show -- and what they do not:** All splits evaluate bounded, made-up Tasks (producing schema-valid Tessera MCP JSON tool calls, recalling post-cutoff 2026 Task Objects without context bloat, or decomposing nonprofit intake briefs with `builder != reviewer` and contributor-tier privacy checks). They prove that the continuous Task and Task-Object learning loop measures real specialist gains, blocks contaminated rows, and gates promotion on pre-registered checks; they are not general LLM capability claims.

## 1. Typed MCP Tool-Call Specialist Accuracy (`n = 150`)

![Strict Exact-Match Accuracy Before and After PEFT QLoRA Fine-Tuning of Muse Glimmer 30B](tool-call-accuracy.svg)

| Base Model | Tuning Method | Split (`n = 150`) | Base | Tuned | Paired Delta & Gate Outcome |
| --- | --- | --- | --- | --- | --- |
| **Muse Glimmer 30B** | 4-bit `bitsandbytes` QLoRA (`2x T4`) | Pre-registered fresh holdout | `93.3%` | **`99.3%`** | `+6.0%` (`95% CI [+2.0%, +10.7%]`), **12/12 checks passed** |
| **Muse Glimmer 30B** | 4-bit `bitsandbytes` QLoRA (`2x T4`) | Frozen unseen-family test | `87.3%` | **`98.7%`** | `+11.3%` (`95% CI [+5.3%, +18.0%]`), 8/8 reload match |

![Muse Glimmer 30B JSON Validity and Refusal Recall Before and After Fine-Tuning](schema-and-json-validity.svg)

---

## 2. Muse Glimmer 30B LoRA-as-Memory Benchmark (`n = 120`, Pre-Registered SHA-256 Holdout)

Can a PEFT LoRA adapter (`r=16, alpha=32`, trained in `48` steps on free Kaggle `2x Tesla T4` GPUs) internalize post-cutoff 2026 Agent Harness & Fabric **Task Objects** (`Subtask A`, `n=60`) and plain-English nonprofit intake decomposition (`Subtask B`, `n=60`) directly into weights -- eliminating repetitive `[NOUN/VERB CONTEXT]` shim tokens at inference time?

![Muse Glimmer 30B LoRA-as-Memory Benchmark](glimmer-30b-lora-memory.svg)

| Evaluation Regime (`test_holdout.jsonl`, `sha256: a5f59267...`) | Avg Shim Tokens | Overall Exact Match | Subtask A Recall (`n=60`) | Subtask B NGO Split (`n=60`) | JSON / Schema Valid | Median Amortized Sec / Row (`batch=8`) |
| --- | --- | --- | --- | --- | --- | --- |
| **Base Closed-Book** | `0.0` | `0.0%` | `0.0%` (`0.0%` F1) | `0.0%` (`0.0%` F1) | `59.2%` / `21.7%` | `18.07s` |
| **Base + BM25 Top-2 Context Shim** | `222.3` | `29.2%` | `58.3%` (`64.2%` F1; `25.0%` 2-obj) | `0.0%` (`0.0%` F1) | `36.7%` / `35.0%` | `19.75s` |
| **LoRA-as-Memory (Weights Only)** | **`0.0`** | **`62.5%`** | **`68.3%`** (`86.9%` F1; **`45.8%`** 2-obj) | **`56.7%`** (**`98.1%`** F1) | **`100.0%` / `100.0%`** | **`8.67s` (`2.28x` lower)** |
| **Hybrid (`LoRA + 71-tok Pointer`)** | `71.0` | `55.0%` | `68.3%` (**`94.4%`** F1; **`50.0%`** 2-obj) | `41.7%` (`90.7%` F1) | **`100.0%` / `100.0%`** | `9.22s` |

- **Paired bootstrap significance:** LoRA-as-Memory (`0` shim tokens, 4-bit NF4 storage with float16 compute on `2x T4`, `352`-token cap) beat Base + BM25 Top-2 Shim (`222.3` shim tokens; `48` improved vs `8` regressed rows) by **`+33.3` percentage points** (`95% CI [+22.5, +44.2]` pp; recall alone `41/60` vs `35/60`, `95% CI [-5.0, +25.0]` pp; intake splitting `34/60` vs `0/60`) and Base Closed-Book by **`+62.5` percentage points** (`95% CI [+53.3, +70.8]` pp).
- **Generated-plan field checks & reload parity:** All `60/60` generated intake plans passed `builder_principal != reviewer_principal` separation and contributor-routing field checks, `95.0%` plain-text sanity retention (`0.0%` JSON intrusion), and `8/8` byte-exact fresh-base reload regeneration (`max_abs = 0.0`).

---

## 3. Horizontal 256-Worker Swarm & Vertical Compute Cascade

![Horizontal Scaling Across 256 Scoped OpenCode & Multi-Harness Workers](horizontal-scaling-256-workers.svg)

- **Measured 256-Worker OpenCode / MCP Swarm (`SCALABILITY_BENCHMARK.json`):** `256` distinct scoped worker principals across `4` `workerd` cells (`q01..q16` queues) executed `1,000` made-up workflows (`5,000` leased Tasks, `25,620` MCP JSON-RPC calls at `54.4 ms` p50 latency, `0` lease collisions, `0` self-approvals, `100%` contributor-tier refusal on private fixtures), emitting `2,500` verified made-up training rows and `200` disjoint holdout rows (`0` overlap).

![Vertical Compute Cascade and Specialist Adapter Flywheel](vertical-modular-architecture.svg)

---

## Three Anti-Cheating Guarantees

1. **Disjoint Tool Families & Three-Fingerprint De-duplication:** Tool-call training prompts only expose `lease`, `verb discovery`, `records`, and `access` tools while holdouts test unseen `buckets` and `feeds` families. Curation hashes exact text, normalized request, and slot-masked template shape so zero evaluation shapes leak into training.
2. **Pre-Registered SHA-256 Holdouts:** Both the 150-row Glimmer tool-call holdout (`0ce30e9f...`) and the 120-row Glimmer LoRA-as-Memory holdout (`a5f59267...`) were SHA-256-pinned before any GPU scored them.
3. **A Gate That Can Say No:** The pre-registered promotion rule (`tool-call-specialist.promotion` v1) is applied by `decide_promotion` to every candidate; one that hurts schema validity beyond the `0.020` guard or fails paired bootstrap bounds is kept out automatically. Muse Glimmer 30B cleared all `12/12` checks.

## Raw Receipts & Reproducible Verifiers

- **Muse Glimmer 30B Orchestrator, Abstention & Retrieval (`2026-11-02`):** [`glimmer-orchestrator-2026-11-02/README.md`](glimmer-orchestrator-2026-11-02/README.md)
- **Muse Glimmer 30B Evidence Bundle:** [`agora/evidence/glimmer-30b-2026-10-29/`](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution/tree/main/evidence/glimmer-30b-2026-10-29)
- **Adapter Configs, Step-by-Step Kaggle Guides & Provenance Digests:** [`../training/README.md`](../training/README.md)
