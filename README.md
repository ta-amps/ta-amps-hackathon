# ta-amps -- Meta Global AI Developer Hackathon 2026 Submission

**Three live products built on one open-source Task and Task-Object engine for clinics, food pantries, grassroots nonprofits, and AI agent builders:**
1. **[Eranos Public Goods Marketplace](https://eranos.ta-amps.workers.dev):** Volunteers donate spare AI capacity so multi-harness agents draft and independently verify (`drafter != reviewer`) cited public-data research and offline local **Llama 3.2** agent kits for resource-constrained nonprofits.
2. **[Tessera](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine) + [Herma](https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents) Task & Task-Object Engine:** Fenced work leases, content-addressed storage, `< 2 ms` context shims, and contributor-tier privacy firewalls across **Muse Code**, **OpenCode**, **Pi**, and **Harness Square**.
3. **[Roll Your Own Seed Packs, Harness Feeds & Meta Specialist LoRAs](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/library/#explorer):** Portable Seed Packs (`75` packs, `473` tasks, `1,470` task objects, `45` worked examples), a `707`-repo Meta Hackathon Ecosystem Explorer, an offline developer sandbox ([`docker-compose.yml`](docker-compose.yml)), and open-weights **Llama 3.2** / **Muse Glimmer 30B** PEFT QLoRA & LoRA-as-Memory recipes.

**[Watch the film & explore live](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/)** ([Interactive Live Studio (`/studio/`)](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/studio/); [3D Spatial Hub (`/hub-3d/`)](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/hub-3d/); [Cloudflare & Self-Host Deployment Guide (`/deploy/`)](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/deploy/) / [`docs/deployment-guide.md`](docs/deployment-guide.md); [outline and storyboard](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/film/); [how it was made, with every receipt](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution/tree/main/evidence/video-production-2026-10-30); [search Tasks & Task Objects](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/library/#explorer)).

---

## Push the Frontier + Build for Public Good

- **The exact problem:** AI models are smart, yet everyday agent use is frustratingly dumb: models miss post-cutoff facts, rewrite non-novel code from scratch, and stall on multi-step queues that need constant human babysitting. Meanwhile, grassroots nonprofits have urgent research and reporting bottlenecks, no AI engineering budget, and strict confidentiality obligations.
- **Who uses it:**
  1. **Resource-constrained nonprofits (via [Eranos](https://eranos.ta-amps.workers.dev)):** Ask for help in plain words with zero jargon. Public-web questions become multi-agent research briefs with verified citations (`drafter != reviewer`). Private-file workflows become inspected **agent kits** that the nonprofit runs on its own computer.
  2. **Open-source agent builders & contributors (via [Agora](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/), [Tessera](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine), and [Herma](https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents)):** Connect any coding harness (`Muse Code`, `OpenCode`, `Pi`, `Harness Square`, `Claude Code`, `Codex`) to claim leased tasks, retrieve versioned artifacts, subscribe to research feeds, and fine-tune open-weights specialist LoRA adapters.
- **Where your data goes (strict privacy & contributor-tier boundary):**
  - **Private and NGO files never touch volunteer machines or contributor-tier APIs.** Any model identifier on a contributor/training-shared tier (`*contributor*`) is deterministically blocked (`ContributorTierRefusedError` in Eranos and `HTTP 403 contributor_tier_refused` in Herma).
  - **Local open-weights execution:** Nonprofits and privacy-sensitive workers can run inspected agent kits completely offline against local **Meta Llama 3.2 1B / 3B Instruct** weights via Ollama or Hugging Face PEFT, keeping sensitive spreadsheets and case notes inside their own machine.
  - **Zero training on user or API traces:** All LoRA and QLoRA specialist runs train strictly on owned synthetic MIT templates -- never on Muse API outputs, nonprofit requests, or private execution logs.

## Which Meta Models Do What

| Meta Model / Open-Weights Stack | Role in `ta-amps` | Measured Evidence & Provenance |
| --- | --- | --- |
| **Muse Glimmer 30B (QLoRA & LoRA-as-Memory fine-tuned)** | 4-bit NF4 `bitsandbytes` QLoRA & 2-GPU layer-24 sharded `peft` LoRA (`r=16`, `alpha=32`, 95.8M trainable params) trained on free Kaggle `2x NVIDIA T4` GPUs (`$0`) | **1) Tool-call specialist (`n=150`):** **93.3% -> 99.3%** exact match (`+6.0%`, 95% CI `[+2.0%, +10.7%]`, 12/12 checks). **2) LoRA-as-Memory (`n=120`):** **0.0% (Base) / 29.2% (BM25 Shim) -> 62.5% (LoRA at 0 shim tokens)** (`+33.3 pp` vs BM25 Shim, `100.0%` valid schema, **`2.28x` faster p50**); [`training/README.md`](training/README.md), [`eval/README.md`](eval/README.md), [Glimmer receipts](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution/tree/main/evidence/glimmer-30b-2026-10-29) |
| **Llama 3.2 1B & 3B Instruct (PEFT LoRA fine-tuned)** | **Role-Switched Modular LoRAs**, **Herma Shim Router** micromodel option, offline NGO kit model, and continuous tool-call tuning (`r=16`, `bf16`, `load_adapter` / `set_adapter`) | **12.0% -> 50.7%** (1B) and **52.0% -> 72.7%** (3B) on unseen tool families; stringified arguments **17.5% -> 0.0%** (3B) and **8.3% -> 0.0%** (1B); 3 specialist LoRAs on 1 base at **80/80** parity; [continuous-tuning.md](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine/blob/main/docs/continuous-tuning.md) |
| **Muse Spark 1.3** | Frontier reasoning & multi-step synthesis worker model (`muse-spark-1.3-contributor` on synthetic/public tasks; Standard mode for non-contributor work) | Verified real `api.meta.ai` multi-step E2E kit build (`Muse Code`) + independent review (`nanoMuse`, `reviewer_key_id != builder_key_id`, `$0.017` approved E2E run; `$0.105` total across all attempts under `< $2.00` cap) and Herma budget/privacy guards |
| **Muse Wonder 1.0** | Fast drafting, triage decomposition (`verb.decompose_dag`), and structured schema extraction inside authorized workers | Scoped worker execution across public-good marketplace tasks and seed-pack pipelines |
| **Muse Code & nanoMuse** | Native coding harness (`muse-code`) claiming leased `eq02` build verbs + independent `nanoMuse` reviewer claiming `eq03` review verbs and Tier-3 shim routing (`HERMA_MICROMODEL_URL`) | Verified end-to-end on real `workerd` Tessera queues (both catching an unscripted 1-hex-char `blob_sha256` slip in `v5` with `verdict=refuse` and passing full digest + test verification in `v7` with `verdict=approve`) alongside `OpenCode`, `Pi`, and `Harness Square` |
| **Meta SAM (`facebook/sam-vit-base`) + `wav2vec2` Multimodal Video/Audio QA** | Local `facebook/sam-vit-base` UI-control segmentation mask adapter (detecting caption/callout occlusions in `frame-by-frame-video-qa`) + local `wav2vec2-base-960h` speech-to-caption verification | 16/16 receipted tasks verified in [`video-production-2026-10-30`](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution/tree/main/evidence/video-production-2026-10-30) and [`frame-by-frame-video-qa`](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs/tree/main/packs/frame-by-frame-video-qa) |

---

## Tasks and Task Objects (Nouns and Verbs)

Underneath every surface is one flexible architecture, and any project can reuse it. **Tasks and Task Objects -- on the wire, verbs are tasks and nouns are task objects.** It is not a new model architecture; it is how the work is organized:

- **Tasks (`verbs` on the wire):** the smallest unit of schedulable work an authorized worker can claim under a fenced lease, execute, verify, and finish with a cryptographic SHA-256 receipt.
- **Task Objects (`nouns` on the wire):** everything a task uses or makes -- context rules, reusable code, skills, MCP tool definitions, research feeds, whole agent setups (harness, model, and workspace files), datasets, PEFT LoRA adapter manifests, run traces, and receipts. Each Task Object is typed, versioned, content-addressed, and searchable.

**Three examples, in plain words:**
1. *A data-cleaning pipeline.* The request becomes one task (`verb`) whose first job is to split itself into smaller tasks. Workers anywhere claim and solve them, and every input, output, and trace is stored as a Task Object (`noun`). A final task combines the pieces into one reusable solution Task Object.
2. *The same request again.* Search and retrieval find the stored Task Object: no duplicate work and zero wasted tokens.
3. *Staying current via Agent Harness Research Feeds (an illustration; automated live feeds for external repos are planned).* Hundreds of new harnesses and memory systems appear on GitHub in days. Feed Task Objects capture comparable profiles, `HarnessTax` overhead, and trial benchmarks across harnesses like `Harness Square`, `OpenCode`, `Pi`, and `Muse Code`. Our public scan already decomposed 705 of the 739 public hackathon repositories into searchable Tasks and Task Objects ([evidence](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution/tree/main/evidence/hackathon-repo-scan-2026-10-29)).

## Why AI Work Is Frustratingly Dumb -- and How This Fixes It

| The everyday failure | The `ta-amps` fix |
| --- | --- |
| Models miss post-cutoff facts and tools | **Feed Task Objects** record each new release, benchmark, or service update with its source provenance |
| Agents rewrite existing code from scratch | **Search, recall, and context shimming:** Tessera's `search_nouns` + `recall_execution` find verified code and runs; Herma shims them before the LLM call or answers directly at zero token cost |
| Multi-step queues stall and need babysitting | **Leased Tasks on one shared queue:** Tessera decomposes big jobs into fenced, heartbeated tasks (`drafter != reviewer`) with dead-letter recovery and SHA-256 receipts |
| Static prompts do not compound over time | **Built to keep learning from verified work:** Open-weights Llama 3.2 and Muse Glimmer 30B adapters train on checked synthetic tasks and advance only when pre-registered holdout gates pass ([`training/`](training/README.md), [`eval/`](eval/README.md)) |

## Horizontal + Vertical Scalability & Modularity Flywheel

`ta-amps` pairs **horizontal multi-worker task scaling** with a **vertical compute cascade and composable modular LoRAs** so frontier quality compounds into fast, private, low-cost execution:

1. **Breaking Data Scarcity via Horizontal Worker Swarms (`256` OpenCode & Multi-Harness Workers):**
   - Verified at `256` distinct scoped worker principals across `4` `workerd` cells (`q01..q16` queues, Durable Object / SQLite shards, content-addressed CAS blobs): `1,000` synthetic workflows completed (`5,000` leased Tasks, `25,620` MCP calls at `54.4 ms` p50, `0` lease collisions, `0` self-approvals, `2,500` verified synthetic training rows + `200` disjoint holdout rows).
   - Verified multi-worker execution traces -- paired with rejected-attempt tombstones (`noun.negative_tombstone`) structured for preference / DPO pairs -- establish the governed pipeline for turning real multi-harness work into checked training data (note: all fine-tuning runs recorded to date used owned synthetic MIT templates while real-trace consent and outcome-grading gates are finalized).
2. **Vertical Compute Cascade & Composable Modular LoRAs (Local GPU + Kaggle 2xT4):**
   - **Tier 0 -- Deterministic Herma Rules & Capability Firewall (`< 2 ms`):** Keyword, regex, path, and semantic triggers answer directly (`respond_directly`) or shim `[NOUN/VERB CONTEXT]` with zero model calls while blocking contributor-tier leakage (`403 contributor_tier_refused`).
   - **Tier 1 -- Local `Llama 3.2 1B & 3B` Hot-Swappable PEFT LoRA Task Objects:** One base model in VRAM attaches modular specialist LoRA Task Objects by verb role (`lora.task-decomposer`, `lora.shim-retriever`, `lora.builder-toolcalls`, `lora.verifier-dpo` via `load_adapter` / `set_adapter`; 3-adapter hot-swap verified at `80/80` exact parity on 1x RTX 3060, lifting unseen-family tool calls `12.0% -> 50.7%` on 1B and `52.0% -> 72.7%` on 3B).
   - **Tier 2 -- `Muse Glimmer 30B` QLoRA & LoRA-as-Memory Specialist (Kaggle Free 2xT4):** `95.8M` trainable params across `364` linear modules internalize Task Object schemas into weights (`93.3% -> 99.3%` on 150-row tool-call holdout; `0.0% Base / 29.2% BM25 Shim -> 62.5% LoRA-as-Memory at 0 shim tokens` on 120-row post-cutoff + NGO intake holdout, `100.0%` valid schema, `2.28x` faster p50).
   - **Tier 3 -- Frontier `Meta Muse Spark 1.3` & `Muse Wonder 1.0`:** Reserved for novel multi-step synthesis and cross-agent review (`Muse Code` + `nanoMuse`) whose verified workflow shapes distill back down into Tier 1 and Tier 2 specialist adapters under explicit consent and licensing gates.
3. **Why Tasks & Task Objects Instead of Ad-Hoc Agent Persona Prompts:**
   - Empirical studies across coding harnesses and multi-agent benchmarks (`Zheng 2311.10054`, `Basil 2512.05858`, `de Araujo 2508.19764`, `Cao 2602.12285`, `Li 2402.10962`) show that expert role-play lines add zero factual accuracy while irrelevant or demographic persona fluff degrades agent performance by `26-30%` and system instructions drift within `8` turns.
   - `ta-amps` separates **routing descriptions** from **permissions** (*"hierarchy routes, it never authorizes"*) and puts precision into typed **Task Objects**, **output contracts**, **scoped tool limits**, and **Herma context shims** rather than brittle persona prose.

[The overview deck](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/overview-and-architecture/) walks through the whole system visually.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/map-dark.png">
  <img alt="The map. Tasks (verbs) and Task Objects (nouns) sit at the top. Seed packs bundle them. Below are two public surfaces: Eranos, the two-sided public-good marketplace, and Agora, the overview and explorer. Underneath is the infrastructure: Tessera and Herma." src="docs/map-light.png">
</picture>

## Two Public Surfaces + Narrow Infrastructure

- **[Eranos](https://eranos.ta-amps.workers.dev)** -- the two-sided public-good marketplace ([source](https://github.com/ta-amps/eranos-public-marketplace-for-public-good-token-burn)):
  - **"I want to help":** Donate spare AI capacity so your agent drafts and independently reviews research and kits for nonprofits.
  - **"I'm an NGO looking for agentic solutions":** Describe what you need in plain English. Public-data questions are answered with verified citations; private-file needs become an inspected agent kit you run locally.
- **[Agora](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/)** -- the 1x3 product hub, interactive [Task & Task-Object Explorer](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/library/#explorer), decks, and contributor setup ([source](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution)).
- **[Tessera](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine)** -- infrastructure for fenced task leases, content-addressed Task Objects, permissions, and receipts.
- **[Herma](https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents)** -- infrastructure shim connecting any coding harness to scoped context, direct answers, and models.
- **[Seed Packs Library](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs)** -- reusable bundles of Tasks and Task Objects, including inspected NGO agent kits, [video and motion](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs/tree/main/packs/video-motion), [code composition](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs/tree/main/packs/code-composition), and [exploitation evidence](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs/tree/main/packs/exploitation-evidence).

## Every Repo in One Line

| Repo | What it is |
| --- | --- |
| [seed-packs-library-of-nouns-and-verbs](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs) | Seed-pack library -- reusable bundles of Tasks (`verbs`) and Task Objects (`nouns`), including NGO agent kits |
| [eranos-public-marketplace-for-public-good-token-burn](https://github.com/ta-amps/eranos-public-marketplace-for-public-good-token-burn) | Eranos -- two-sided public-good token marketplace (public surface) |
| [agora-public-overview-architecture-setup-and-contribution](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution) | Agora -- overview, 1x3 product hub, decks, and interactive explorer (public surface) |
| [tessera-infrastructure-work-and-storage-engine](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine) | Tessera -- leased work queue and versioned Task-Object storage engine (infrastructure) |
| [herma-infrastructure-shim-for-intelligent-agents](https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents) | Herma -- context-shimming middleware and router for any agent harness (infrastructure) |

## Roll Your Own in 60 Seconds: Offline Sandbox & Starter Templates

Run the complete local developer sandbox offline with zero cloud credentials, or copy one of the three starter folders to ship your own pack, harness integration, or Meta LoRA specialist:

- **One-Command Offline Developer Sandbox ([`docker-compose.yml`](docker-compose.yml), [`sandbox/README.md`](sandbox/README.md)):**
  - `docker compose up --build --abort-on-container-exit --exit-code-from sample-worker-smoke` (or `python3 -m sandbox.worker_smoke` without Docker) spins up the local Tessera protocol simulator (`tessera-local`), validates [`templates/new-seed-pack/`](templates/new-seed-pack/README.md), verifies `ContributorTierRefusedError` and `SelfVerificationRefusedError` (`verifier != builder`), and emits a SHA-256 verification receipt.
  - *Governance note:* `sandbox/` is a local offline protocol simulator for development and CI; production work scheduling and leases live strictly in Tessera.
- **Copy-Paste Starter Templates (`templates/`):**
  1. **[`templates/new-seed-pack/`](templates/new-seed-pack/README.md)** -- starter `manifest.json`, `nouns.json` (Task Objects), and `verbs.json` (Tasks) ready for `python3 -m sandbox.verify_pack`.
  2. **[`templates/connect-agent-harness/`](templates/connect-agent-harness/README.md)** -- MCP JSON-RPC config ([`mcp-config.example.json`](templates/connect-agent-harness/mcp-config.example.json)) and Herma environment setup ([`herma-env.example.sh`](templates/connect-agent-harness/herma-env.example.sh)) for **Muse Code**, **OpenCode**, **Pi**, **Claude Code**, and **Codex**.
  3. **[`templates/finetune-meta-lora/`](templates/finetune-meta-lora/README.md)** -- runnable PEFT LoRA (`Llama 3.2 1B/3B`) and 4-bit NF4 QLoRA ([`train_lora_template.py`](templates/finetune-meta-lora/train_lora_template.py)) with an offline `--dry-run-manifest` check over synthetic MIT fixtures ([`sample_synthetic_tasks.json`](templates/finetune-meta-lora/sample_synthetic_tasks.json)).

## Reproducible Verification, Training & Evaluation in This Repo

- **[`training/README.md`](training/README.md):** Open-weights QLoRA (`bitsandbytes` + `peft`) and bf16 multi-LoRA training pipeline, [`requirements-train.txt`](training/requirements-train.txt), PEFT `adapter_config.json` manifests, and [`adapters/provenance.json`](training/adapters/provenance.json).
- **[`eval/README.md`](eval/README.md):** Pre-registered holdout benchmarks, LoRA-as-Memory & 256-worker scalability receipts, paired bootstrap confidence intervals, negative-result promotion guards, and SVG charts ([`tool-call-accuracy.svg`](eval/tool-call-accuracy.svg), [`schema-and-json-validity.svg`](eval/schema-and-json-validity.svg), [`glimmer-30b-lora-memory.svg`](eval/glimmer-30b-lora-memory.svg), [`horizontal-scaling-256-workers.svg`](eval/horizontal-scaling-256-workers.svg), [`vertical-modular-architecture.svg`](eval/vertical-modular-architecture.svg)).
- **[`Dockerfile`](Dockerfile) & [`docker-compose.yml`](docker-compose.yml):** Deterministic `python:3.12-slim` verification and local developer sandbox containers.
- **[`hackathon/`](hackathon/README.md):** Reusable handbook, submission templates, and public-safety checks (`make check`) for hackathon teams.

```bash
make check
python3 -m sandbox.worker_smoke
```

## See It, Try It

- [Interactive Task & Task-Object Explorer](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/library/#explorer) (Seed Packs, Harness Feeds, and Meta Hackathon Ecosystem Explorer)
- [The three decks](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/): [overview and architecture](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/overview-and-architecture/), [a public-good marketplace](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/public-good-marketplace/), and [roll your own](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/roll-your-own/)
- [Status and evidence](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/overview-and-architecture/#evidence), [use cases](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/use-cases/), and [connect your agent](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/roll-your-own/#connect)

Made for the Meta Global AI Developer Hackathon 2026, Indie track. Built with Llama (Llama 3.2 Community License applies to Llama 3.2 materials). All examples use synthetic data, and every measured number links to its SHA-256 receipt.
