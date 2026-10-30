# Scripts

Stdlib Python 3.12+ and bash. The four marked **shared** are written to be copied into any repo unchanged;
keep the copies byte-identical so a fix lands everywhere.

| Script | What it does |
|---|---|
| [check_public.py](check_public.py) | **Shared.** Fails on secrets (GitHub, Meta Model API, Hugging Face, AWS, Slack, OpenAI-style and worker keys, private keys) and on private names, matched by SHA-256 hash from [private-names.sha256](private-names.sha256). `--hash` prompts for a name and prints its line |
| [build_index.py](build_index.py) | **Shared.** Writes INDEX.md, KEYWORDS.md (terms from `keywords.txt`), llms.txt and llms-full.txt; `--check` fails when they are stale |
| [check_architecture.py](check_architecture.py) | **Shared.** Fails when `architecture.json` disagrees with the repo: paths, test references, ids, layering rules. `--summary`, `--mermaid` |
| [bootstrap-hosting.sh](bootstrap-hosting.sh) | **Shared** (lives in `deploy/` in a project). One-time Fly.io and Cloudflare setup from `deploy/hosting.env`; never prints a secret, deploys nothing. See [guides/hosting.md](../guides/hosting.md) |
| [check_docs.py](check_docs.py) | Every JSON file parses and every relative Markdown link resolves |
| [test_scripts.py](test_scripts.py) | Tests for the shared scripts |
| [bootstrap-workspace.sh](bootstrap-workspace.sh) | Clones this kit and your repos side by side |
| [check-prereqs.sh](check-prereqs.sh) | Reports which tools are installed and which versions |
| [install-muse-code.sh](install-muse-code.sh) | Downloads the Muse Code installer, shows it to you, and runs it only after you agree |

To use your own private-name list in a copied `check_public.py`, replace `private-names.sha256` with lines
from `python3 scripts/check_public.py --hash`. The names themselves never touch the repo or your shell history.
