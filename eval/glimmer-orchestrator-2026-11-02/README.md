# Muse Glimmer 30B Orchestrator, Abstention & Retrieval Evaluations (`2026-11-02`)

Pre-registered held-out evaluations of **Muse Glimmer 30B** LoRA adapters (`bf16` base weights with `rank-16` LoRA on one `NVIDIA H100 80GB`, holdout splits hashed at `2026-11-02T00:33:21Z` before training; plus `4-bit NF4` QLoRA on `2x NVIDIA T4` for the zero-shim Task-Object recall run) alongside the live hourly `worker.policy` Thompson-sampling mix (`tuner_version 28`).

> **Serving honesty:** Muse Glimmer 30B adapters are measured on pre-registered held-out splits and do not serve live requests today; live dedicated workers run **Muse Spark 1.3** and **Muse Wonder 1.0** under the hourly policy tuner.

| Benchmark Split | Base / Baseline | Tuned Result | Key Finding |
| --- | --- | --- | --- |
| **Orchestrator routing (`n = 106` held-out)** | `45.0%` base · `89.6%` F1 (`r = 64` adapter) | **`97.8%` F1** (`r = 16` adapter; `97.9%` adopted `none-fix`) | Rank-16 adapter beat the `4x` larger rank-64 adapter by `+8.2` percentage points. Bigger wasn't better. |
| **Flawed-report false-accept (`n = 204` reviews, `126` flawed)** | `1.6%` false-accept (before fix) | **`0.8%` false-accept** (after `"nothing fits"` fix) | Cut flawed-report false approvals in half (`99.6%` balanced accuracy, `100%` self-review catch rate). |
| **Task-Object retrieval (`n = 175` match + `153` abstention)** | `1.7%` hit@1 (`51.0%` abstention before fix) | **`88.6%` hit@1** (`83.7%` abstention on adopted `none-fix`; `89.1%` hit@1 before fix) | First-pick selection jumped from `1.7%` to `88.6%` (`155/156` right when naming an object) while raising out-of-scope abstention from `51.0%` to `83.7%`. |
| **Typed MCP tool calls (`n = 150` held-out)** | `94.0%` exact match | **`99.3%` exact match** | Pre-registered schema-valid MCP tool-call split (`bf16` H100 multi-role run; `93.3% -> 99.3%` on earlier `2x T4` `4-bit NF4` tool-only run). |
| **Live hourly policy share (`v28`, `15` outcomes)** | Equal prior | **`Spark 77% · Wonder 23%`** (`make`) | Check step converged to `Muse Spark 1.3 66% · Muse Wonder 1.0 34%`. |

Public summary record served on `teleionlabs.com`: [`/records/glimmer-30b-orchestrator-2026-11-02.json`](../../teleionlabs/static/records/glimmer-30b-orchestrator-2026-11-02.json).
