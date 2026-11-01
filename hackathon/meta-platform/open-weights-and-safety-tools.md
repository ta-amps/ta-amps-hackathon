> Unofficial AI-assisted summary, provided "as is" with no warranty. Meta's documentation governs; read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Open weights and safety tools

## Safety

| Tool | What it is | Notes |
|---|---|---|
| Prompt Guard 2 | A small classifier for prompt injection and jailbreak attempts | Open weights, gated on Hugging Face with manual approval, so request access early. Unverified here: whether the Model API serves it |

## Data and evaluation

| Tool | What it is |
|---|---|
| [ARE and Gaia2](https://huggingface.co/blog/gaia2) | Meta's agent research environment: simulated worlds with apps, timed and triggered events, and JSON traces |
| [Faiss](https://github.com/facebookresearch/faiss) | Vector similarity search; handy for finding duplicates and related items |
| [Ax](https://github.com/facebook/Ax) | Adaptive experimentation and Bayesian optimization; handy for tuning a few settings against a metric |

## Open-weights models and partner inference

- Meta's open-weights models can be run without a Model API account. The docs list them under
  [open-weight models](https://dev.meta.ai/docs/open-weight-models), including
  [Muse Spark Open](https://dev.meta.ai/docs/muse-spark-open) and [Muse Glimmer post-training](https://dev.meta.ai/docs/muse-glimmer/post-training).
  (Linked, not re-read on Oct 26.)
- Partner credits for select participants: Baseten, Modal and Fireworks. See [../event/10-credits.md](../event/10-credits.md).
- Before any fine-tuning that learns from Model API outputs, read the Terms clause that bars training or distilling
  competing models (s.10.1(ix)). See [../event/13-acceptable-use-and-data.md](../event/13-acceptable-use-and-data.md).
- Open-weight model licences carry their own terms, for example attribution requirements for derivatives. Read each
  licence before you ship.

Sources: as linked, checked 2026-10-26 unless marked.
