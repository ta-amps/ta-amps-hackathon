#!/usr/bin/env bash
# Example environment setup for connecting Muse Code, OpenCode, or Pi via Herma.
# Source in your shell after substituting your own local or Standard-tier endpoint.

export HERMA_BASE_URL="${HERMA_BASE_URL:-http://127.0.0.1:11434/v1}"
export HERMA_HARNESS="${HERMA_HARNESS:-opencode}"
export HERMA_MODEL="${HERMA_MODEL:-llama3.2:3b}"
export HERMA_TIER_POLICY="standard_or_local"

# Local developer sandbox endpoint (used by python3 -m sandbox.worker_smoke)
export TESSERA_SANDBOX_URL="${TESSERA_SANDBOX_URL:-http://127.0.0.1:8787}"

echo "Configured harness=${HERMA_HARNESS} model=${HERMA_MODEL} policy=${HERMA_TIER_POLICY}"
