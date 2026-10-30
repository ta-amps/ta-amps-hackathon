# Security

## Reporting

If you find a secret, a personal detail or a security problem in this repo or its history, don't open a public
issue. Use GitHub's private vulnerability reporting on the repository ("Security" tab, "Report a vulnerability").
We'll respond as fast as we can during the hackathon.

## What this repo does with credentials

- Nothing here stores or needs a credential, except `tools/transcribe/transcribe.py`. It reads `MODEL_API_KEY` from
  your environment, sends it only to `https://api.meta.ai`, and never prints or writes it.
- `scripts/install-muse-code.sh` downloads Meta's installer to a temporary file, shows its checksum and first lines,
  and runs it only after you type `y`. Nothing is piped straight into a shell.
- `make check` runs `scripts/check_public.py`, which fails on GitHub, Meta, Hugging Face, AWS, Slack and
  OpenAI-style keys and private keys.

## If you leaked a key

Revoke it at its provider first, then remove it from the repo and its history. Deleting the line alone isn't enough.
