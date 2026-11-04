# Sizing step

Sizes a Task before a worker takes it: how much work it needs, and which model and share of work fit. It includes a tuner with a held-out test and a canary, a fine-tune share and a kit size check.

A trial on Nov 4, 2026 ended with no promotion: there was no finished work on either side to compare.

```bash
BANNED_WORDS_FILE=/path/to/banned-words.json python3 -m pytest -q tests
```

Live runs need your own settings: `BANNED_WORDS_FILE`, `SIZING_HOLDOUT_DATA` and `ERANOS_PROCESS_HANDLER`. Records and spend ledgers stay out of git.
