# Pre-Registered Evaluation & Promotion Gate Benchmarks

Every model-tuning round in `ta-amps` is scored by a deterministic evaluation Task (`verb.benchmark_harness`) and gated by a pre-registered promotion rule Task Object (`tool-call-specialist.promotion` v1, `sha256: bf0fa821717c2400faab77652f067ea85f2616eea329c6e139af33a423e4b3b7`) fixed before training runs.

> **What these benchmarks show -- and what they do not:** All splits evaluate one narrow, synthetic task (producing schema-valid Tessera MCP JSON tool calls or exact refusal reasons on unseen tool families). They prove that the continuous Task and Task-Object learning loop measures real specialist gains, blocks contaminated rows, and rejects regressions; they are not general LLM capability benchmarks.

## Holdout Exact-Match Accuracy

![Strict Exact-Match Accuracy Before and After PEFT LoRA / QLoRA Fine-Tuning](tool-call-accuracy.svg)

| Base Model | Tuning Method | Split (`n = 150`) | Base | Tuned | Paired Delta & Gate Outcome |
| --- | --- | --- | --- | --- | --- |
| **Muse Glimmer 30B** | 4-bit `bitsandbytes` QLoRA (`2x T4`) | Pre-registered fresh holdout | `93.3%` | **`99.3%`** | `+6.0%` (`95% CI [+2.0%, +10.7%]`), **12/12 checks passed** |
| **Muse Glimmer 30B** | 4-bit `bitsandbytes` QLoRA (`2x T4`) | Frozen unseen-family test | `87.3%` | **`98.7%`** | `+11.3%` (`95% CI [+5.3%, +18.0%]`), 8/8 reload match |
| **Llama 3.2 3B Instruct** | bf16 `peft` LoRA (`1x RTX 3060`) | Frozen unseen-family test | `52.0%` | **`72.7%`** | `+20.7%` (`95% CI [+12.0%, +29.3%]`), Round 1 promoted |
| **Llama 3.2 3B Instruct** | bf16 `peft` LoRA (`1x RTX 3060`) | Round 2 candidate (rejected) | `72.7%` (champ) | `79.3%` | **Rejected by gate:** schema validity fell `0.025` (limit `0.020`) |
| **Llama 3.2 1B Instruct** | bf16 `peft` LoRA (`1x RTX 3060`) | Frozen unseen-family test | `12.0%` | **`50.7%`** | `+38.7%` cumulative by Round 3; Round 4 rejected on schema drop |

## Field Failure Elimination (Stringified Values, Schema & JSON Validity)

![Schema Validity, JSON Validity, and Stringified-Argument Elimination](schema-and-json-validity.svg)

## Three Anti-Cheating Guarantees

1. **Disjoint Tool Families & Three-Fingerprint De-duplication:** Training prompts only ever expose `lease`, `verb discovery`, `records`, and `access` tools. Frozen test and fresh holdouts test unseen `buckets` and `feeds` families. Curation hashes exact text, normalized request, and slot-masked template shape so zero evaluation shapes leak into training.
2. **Pre-Registered SHA-256 Fresh Holdouts:** For Muse Glimmer 30B, the 150-row fresh holdout digest (`0ce30e9ff593a4e7238012236e38368c219fc235284d03e1fb898d728c196d56`) was recorded before any model scored it.
3. **Negative Results Caught by the Gate:** On both Llama 3.2 1B (Round 2 and Round 4) and Llama 3.2 3B (Round 2, despite `79.3%` exact match), candidates that hurt schema validity or failed to clear paired bootstrap bounds were automatically kept out by `decide_promotion`.

## Raw Receipts & Reproducible Verifiers

- **Muse Glimmer 30B Evidence Bundle:** [`agora/evidence/glimmer-30b-2026-10-29/`](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution/tree/main/evidence/glimmer-30b-2026-10-29)
- **Llama 3.2 1B & 3B Evidence JSONs:** [`tessera/examples/continuous_tuning/evidence/`](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine/tree/main/examples/continuous_tuning/evidence)
- **Adapter Configs & Provenance Digests:** [`../training/README.md`](../training/README.md)
