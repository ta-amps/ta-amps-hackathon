# Modular Deployment & Self-Hosting Guide

You do not need to deploy the entire `ta-amps` ecosystem to use its primitives. Every layer speaks plain HTTP JSON and JSON-RPC 2.0 MCP, so you can adopt a single slice on **Cloudflare's free tier**, **Docker Compose / Linux VPS / Fly.io**, **local SQLite**, or **custom GPU inference endpoints (`vLLM`, Kaggle `2xT4`, `api.meta.ai`)**.

---

## 1. Pick the Slice You Need

| Slice | Infrastructure Needed | Time to Run | Best For |
| :--- | :--- | :--- | :--- |
| **A. Seed Packs Only** | `0` servers (stdlib Python + git) | `< 60s` | Loading reusable **task objects (`nouns.json`)**, **tasks (things to do) (`verbs.json`)**, and deterministic QA verifiers (`109` seed packs, `1,819` task objects, `581` tasks (things to do)) into `Muse Code`, `Claude Code`, `OpenCode`, `Codex`, `Cursor`, or `Pi`. |
| **B. Cloudflare Edge Stack** | Cloudflare Workers + Durable Objects + D1 + Pages (`$0` free tier) | `~5 min` | Running a private or public **Teleion Fabric** work/CAS engine + **The Teleion Fabric shim** context shim + **Eranos / Agora** surfaces on `*.workers.dev` or a custom domain. |
| **C. Docker / VPS / Air-Gapped** | Docker Engine (`docker compose up`) on Linux, macOS, Fly.io, Railway, or ECS | `~2 min` | Strict data residency, air-gapped CI runners, sovereign NGO deployments, or local offline development. |
| **D. Meta Open-Weight GPU + LoRAs** | Kaggle `2x Tesla T4` (`$0` quota), local GPU (`PEFT`), `vLLM`, or `api.meta.ai` | `~10 min` | Training and serving **LoRA-as-Memory** (`Muse-Glimmer-30B` QLoRA) and role-switched **Modular LoRAs** (`Llama-3.2 1B/3B` PEFT) plus contributor-tier made-up benchmark verification. |

---

## 2. Slice A: Zero-Server Seed Packs (Any Agent Harness)

```bash
git clone https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs.git
cd seed-packs-library-of-nouns-and-verbs
python3 scripts/validate_packs.py

# Run any pack's standalone verifier (stdlib Python, zero cloud keys):
make -C packs/frame-by-frame-video-qa/code check
```

To connect an existing coding agent without cloning, paste the starting brief from `https://teleionlabs.com/llms.txt`.

---

## 3. Slice B: Cloudflare Workers + Durable Objects + D1 + Pages

### Step 1: Deploy Teleion Fabric (leased tasks (things to do), CAS task objects & `/mcp`)
```bash
npx wrangler login
git clone https://github.com/ta-amps/teleion-fabric-infrastructure-work-and-storage-engine.git
cd teleion-fabric-infrastructure-work-and-storage-engine

# Generate and store an admin token in Cloudflare Secrets (never in wrangler.toml):
openssl rand -hex 32 | npx wrangler secret put TESSERA_ADMIN_TOKEN
npx wrangler deploy
```

### Step 2: Deploy the Teleion Fabric shim (D1 Provision Search & Context Shim)
```bash
git clone https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents.git
cd herma-infrastructure-shim-for-intelligent-agents

npx wrangler d1 create herma-provisions
# Update database_id in wrangler.toml, apply migrations, and deploy:
npx wrangler d1 migrations apply herma-provisions --remote
npx wrangler deploy
```

### Step 3: Deploy Public or Team Surfaces (`Agora` & `Eranos`)
- **Agora (Static Hub on Cloudflare Pages or GitHub Pages)**:
  ```bash
  git clone https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution.git
  cd agora-public-overview-architecture-setup-and-contribution
  python3 scripts/build_site.py --check && python3 scripts/check.py
  npx wrangler pages deploy site --project-name=agora-hub
  ```
- **Eranos (Marketplace Surface on Cloudflare Worker + Scoped Surface Token)**:
  ```bash
  git clone https://github.com/ta-amps/eranos-public-marketplace-for-public-good-token-burn.git
  cd eranos-public-marketplace-for-public-good-token-burn
  npm ci && npm test
  # Mint a surface-scoped Teleion Fabric token (X-Surface-Id: eranos), never TESSERA_ADMIN_TOKEN:
  npx wrangler secret put TESSERA_SURFACE_TOKEN
  npx wrangler deploy
  ```

---

## 4. Slice C: Self-Hosted Docker Compose, VPS, Fly.io, or Kubernetes

```bash
git clone https://github.com/ta-amps/teleionlabs-teleion-fabric.git
cd teleionlabs-teleion-fabric
docker compose up --build -d
```

- **Persistent Volumes**: Mount a host or Fly.io volume onto the SQLite data directory so leased tasks (things to do) and CAS task objects survive container restarts.
- **Reverse Proxy**: Put Caddy, Nginx, or Cloudflare Tunnel in front of port `8787` (Teleion Fabric) and port `8080` (Agora) for automatic TLS.

---

## 5. Slice D: GPU Fine-Tuning & Open-Weight Serving (`Kaggle 2xT4`, `vLLM`, `api.meta.ai`)

Full manifests, SHA-256 source, and promotion gates live in [`../training/README.md`](../training/README.md) and [`../eval/README.md`](../eval/README.md).

1. **Fine-Tune `Muse Glimmer 30B` QLoRA / LoRA-as-Memory on Free Kaggle `2x Tesla T4` (`32 GB` Total VRAM, `$0` Spend)**:
   - Push a private Kaggle kernel (`"machine_shape": "NvidiaTeslaT4"`) against your pre-registered made-up MIT dataset (`train.jsonl` + `test_holdout.jsonl`).
   - Load `Muse Glimmer 30B` in 4-bit NF4 (`BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)`) with `device_map="auto"` across `cuda:0` and `cuda:1` (or shard `fp16` language layers `0..23` on `cuda:0` and `24..47` on `cuda:1` at `~11 GiB` peak/GPU when dropping the unused vision tower).
   - Attach `peft` LoRA (`r=16, alpha=32, dropout=0.05` across `364` attention/MLP projections; `95.8M` trainable params), verify `8/8` fresh-reload parity, and gate promotion via `tool-call-specialist.promotion` v1 (`bf0fa821717c2400...`).
   - Measured Kaggle `2xT4` results: **`93.3% -> 99.3%`** on the 150-row MCP tool-call holdout, and **`0.0% (Base) / 29.2% (BM25 Shim) -> 62.5% (LoRA-as-Memory at 0 shim tokens)`** (`2.28x` faster `p50`) on the 120-row post-cutoff task-object + NGO intake holdout.

2. **Train & Serve Role-Switched Modular `Llama 3.2 1B / 3B` LoRAs (`PEFT` + `vLLM`)**:
   ```bash
   # Dry-run receipt on CPU (zero GPU required), then train on local CUDA or Kaggle GPU:
   python3 templates/finetune-meta-lora/train_lora_template.py \
     --dataset templates/finetune-meta-lora/sample_practice_tasks.json \
     --dry-run-manifest /tmp/lora-dry-run-receipt.json

   python3 templates/finetune-meta-lora/train_lora_template.py \
     --base-model meta-llama/Llama-3.2-3B-Instruct \
     --dataset templates/finetune-meta-lora/sample_practice_tasks.json \
     --output-dir ./adapters/lora.builder-toolcalls

   # Serve one shared base model in VRAM with hot-swapped specialist LoRA task objects per verb kind:
   vllm serve meta-llama/Llama-3.2-3B-Instruct \
     --enable-lora \
     --max-lora-rank 16 \
     --lora-modules \
       decompose=./adapters/lora.task-decomposer \
       retrieve=./adapters/lora.shim-retriever \
       build=./adapters/lora.builder-toolcalls \
       review=./adapters/lora.verifier-dpo \
     --port 8000
   ```

3. **Connect `api.meta.ai` Competition Credits (`muse-spark-1.3-contributor`, `Muse Wonder`, `Muse Code`, `nanoMuse`)**:
   - Export `LLM_API_KEY` / `META_API_KEY` strictly inside isolated worker environments (never on public surfaces or in `.toml` files).
   - For made-up or public-domain tasks, pass `--model muse-spark-1.3-contributor` (`$0.10 / $0.20` per 1M input/output tokens, `$0.002` per 1M cached input tokens) behind a file-locked budget gate (`CAP_USD <= 2.00`) and issue **distinct Teleion Fabric keys** (`builder_key_id != reviewer_key_id`) so `Muse Code` builds kits in `eq02` and `nanoMuse` independently verifies them in `eq03`.
   - Enforce contributor-tier privacy firewalls (`ContributorTierRefusedError` in Eranos and `HTTP 403 contributor_tier_refused` in the Teleion Fabric shim) so private or NGO-owned task objects never touch `*contributor*` endpoints, and run sensitive NGO kits offline on local `Llama 3.2 1B/3B` weights.

---

## 6. Post-Deploy Verification Checklist

Run these three probes against your deployed URLs before connecting production workers:

```bash
TESSERA_URL="https://fabric.teleionlabs.com"
HERMA_URL="https://shim.teleionlabs.com"

curl -fsS "$TESSERA_URL/v1/health"
curl -fsS -X POST "$HERMA_URL/api/preview" \
  -H 'content-type: application/json' \
  -d '{"prompt":"How do tasks (things to do) and task objects work?"}'
curl -fsS -X POST "$TESSERA_URL/v1/session/anonymous" \
  -H 'User-Agent: Mozilla/5.0 (VerificationProbe)'
```
