# Awareness v2 benchmark

A test of how well an agent answers questions about new projects, with and without Teleion Fabric. Start with [RESULTS.md](RESULTS.md). The test was registered before it ran, and a separate session recomputed its figures ([records/REVIEW-RESULTS.md](records/REVIEW-RESULTS.md)).

**What the results allow:** one sentence limited to repositories already in Fabric's rows. They do not support a general token claim. For repositories we don't index, GitHub's API is better.

## What is here

- `RESULTS.md`: the results, unchanged.
- `records/`: the analysis output, the computed results, the exploratory notes, the independent review and the spend ledger.
- `run/`: `run.py`, `analyze.py` and `explore.py`.

## What is withheld, and why

**You can't fully reproduce the run from this folder alone.** You can read the method and the results, and compare the review with the figures here. You can't run these scripts as they stand, because they need files that are not here.

- `run/common2.py` and `run/build_questions.py`: they hold local paths. `run.py` imports `common2`, so it won't start without it.
- `records/runs.jsonl`, `records/scored.json` and `rows/`: the raw runs and frozen rows. `analyze.py` and `explore.py` read them.
- `records/attempts.jsonl`, the record of every model attempt, including failures: it holds model replies that fail our word scan, so it is not published here. It exists, and `analyze.py` counts it for the attempt totals in the results.
- `PREREGISTRATION.md`, `prereg/questions.json`, `prereg/HASHES.txt` and `run/scorer.py`: not here at this time, so you can't check the registration or the scoring from this folder.
- Code reviews, the watchdog log and development runs.

## Scan note

`records/spend.jsonl` holds token counts and costs, with no prompts or replies.
