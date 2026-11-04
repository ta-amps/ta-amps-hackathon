# Awareness v2: pre-registration

Written before any run of these items. The only earlier runs of this harness were on the Nov 2 questions, which are excluded from this set (`dev/`, `records/dev-runs.jsonl`). A first dev run hit a live build without the route; it is kept in `dev/invalid-route-gone/`, unused. After dev no tool text was changed: B and B-cold each got 30 of 30 on those old questions, which are all in the rows, so that says nothing about new ones.

**Build under test:** Worker `herma` version 0a34da10 (source 61ec0b4), or any later build containing it. If `/q/repos` disappears from live, the runner stops (a shared Worker has other deployers). Rows are frozen at `rows/rows-v1.json`, as of 2026-11-04T01:54Z. No refresh runs during the test.

**Model and settings, every arm:** `muse-spark-1.3-contributor` through the Meta API, provider default settings, no output ceiling, same system prompt, same loop, at most 6 tool calls. This is not the Nov 2 tier (standard), so Nov 2 numbers are context only, not a baseline.

## Arms
- **A, plain:** no tools, told not to guess. 3 runs per item.
- **B, Fabric new:** one tool, `/q/repos`, described in the prompt. 3 runs.
- **B-direct:** first asks `/q/repos?ask=<question>`. If the shim answers directly, that is the answer and no model is called (0 tokens). Otherwise it continues as B. 3 runs.
- **B-cold:** told only to start at the shim's `llms.txt`; can read shim addresses only. This measures an agent that doesn't already know the route. 3 runs.
- **B-old:** the Nov 2 tools and tool text, feed pages and `/q/search?full=1`. 1 run.
- **C, plain plus GitHub, trimmed:** the Nov 2 arm. The harness trims GitHub's replies to a few fields, which favours C. **This is the primary comparison.** 3 runs.
- **C-raw:** GitHub's API replies exactly as sent, in 12,000-character parts. Disclosed as a secondary arm, since a real agent gets raw replies, while the harness trim is not something GitHub provides. 1 run.

## Items
`prereg/questions.json`, drawn by `run/build_questions.py`, seed 20261104, answers from GitHub's API at draw time, never from a row. Excludes every Nov 2 repository, the owner `thinkjones` (the two live misses that prompted this, so they can't count as a win), and names hit by the shared word list.
- **primary (30):** repositories in the rows with relevant = yes, created Aug 1 to Oct 31, 2026. 13 from rows on the old feed pages (`on_page`), 13 from rows no page showed (`deep`), 4 discovery. 12 owner, 8 licence, 6 language, same as Nov 2.
- **fresh (10):** created since Nov 1, in the rows from the Nov 4 scan.
- **low_star_unindexed (10):** created since Sep 1, 0 to 2 stars, pushed since Oct 25, found by searches the feed scans don't use, and not in the rows. Fabric can only answer through its GitHub read-through.
- **not_on_feed (6):** stars at least 10, recent, not in the rows; again only the read-through.
- **invented (3):** repositories that don't exist. Reported apart. The right answer names no licence.
- **multi_discovery (8), a different test:** name three repositories fitting topic, language and licence. Correct only if all three pass GitHub's facts and the topic check. Combinations were drawn from the rows, so this favours Fabric. It is reported apart and never pooled.

**Bias stated now:** primary and fresh items come from Fabric's own rows, so Fabric's coverage is assured there by construction, and they measure cost, not reach. **`any_real_repo` (primary + fresh + low_star_unindexed + not_on_feed, 56 items) is the fairer reach test**, and the low_star and not_on_feed groups are the ones Fabric may lose. Agents know GitHub's API already but must be told about Fabric, which B-cold prices in. Tokens to build the rows aren't charged to B (they cost no model tokens; feed runs are outside this).

**Known risk stated now:** anonymous GitHub calls from Cloudflare hit limits quickly on a live probe. When that happens B's read-through answers `rate_limited` and the run counts as a miss. That is the product as it stands and is charged to B. The miss states are counted and reported.

## Scoring
`run/scorer.py` unchanged from Nov 2 (its 41 format fixtures), plus the multi rule. Discovery and multi answers are checked live against GitHub. Outcomes: correct, wrong, unknown. A run with no answer scores unknown.

## Measures
Per arm and group: correct, wrong, unknown; total tokens (input plus output as the API reports, all attempts); tokens per correct; model and tool calls; tool characters; wall seconds. Paired by item. 95% ranges by item bootstrap, 10,000 resamples, seed 99 (`run/analyze.py`), resampling items, not runs, because runs of an item aren't independent. Exact sign test on items where correct rates differ.

## Hypotheses and what counts as a win
- **H1 (primary, cost):** B's tokens per correct against C's on `primary`. **Win:** ratio's 95% range entirely below 1. Range includes 1: no difference shown. Range entirely above 1: C is cheaper.
- **H2 (primary, answers):** B not worse than C on `primary`. **Pass:** the lower end of the difference in correct rate is above -10 points.
- **H3 (fair reach):** H1 and H2 repeated on `any_real_repo`.
- **H4:** B cuts tokens per correct from B-old on `primary` by at least 5 times (ratio's upper end at or below 0.2).
- **H5:** B-cold against C on `primary`, same rule as H1.
- **H6:** B-direct against C on `primary`, same rule. **Stated now:** direct answers are given only for fixed sentence forms, and the question templates here use those forms for licence and language. So its share of direct answers is the upper limit of what a real agent would see, and owner questions with a description fall through to the model.
- **H7:** B against C on `multi_discovery`, reported as a different test.

A film sentence saying Fabric costs fewer tokens than using GitHub's API requires **H1, H2 and H3 all to pass**. If only H1 and H2 pass, the only allowed sentence is limited to repositories already in Fabric's rows. A claim against B-old is a claim about our own earlier version, and says so.

## Rules
No tuning on these items. No repeat runs to get a better answer; a run stopped by a failure may resume only items not yet run, on the record. Every attempt is recorded in `records/attempts.jsonl`, spend in `records/spend.jsonl`, stop at $7.50 of the $8 cap. Meta API contributor tier only. Anthropic and OpenRouter are off. Any later correction is reported with both versions.
