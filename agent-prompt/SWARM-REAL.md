# Real swarms of agents on the live queue, Nov 4, 2026

**Largest run that truly worked: 50 OpenCode bots with Muse Spark, spread over 15 minutes, for 49 minutes (18:01 to 18:50 UTC).** 163 runs, 146 with accepted work, 168 of 168 reported objects read back, 0 Tasks closed twice, no 429 or 5xx in the calls logged. The server held. Useful nonprofit work did not: 147 of those runs closed peer-review Tasks and only 5 closed nonprofit (`verb_ngo`) Tasks.

**One sentence we may use in the form:**

> We ran 50 OpenCode agents at once on Muse Spark against our live queue for 49 minutes, with no key and no login: 146 of 163 runs had work accepted, no Task was closed twice, and the calls we logged saw no server errors.

Don't add "by strangers", "nonprofit work" or "checked": these were our own bots on one machine, mostly doing reviews, and the checker is one model reading the work.

## By harness and model

Every bot started from a new clean folder with `PROMPT.md`'s main block as its only instruction, in a sandbox with an empty home. A local proxy held the key and recorded every model attempt on the ledgers. Worker ids name the harness.

| Harness, model | Round | Runs | Runs with accepted work | Leases, on Tasks | Double claims | 429/5xx | Run time p50 / max | Tokens in / out | Cost |
|---|---|---|---|---|---|---|---|---|---|
| OpenCode, Muse Spark | 1 bot | 1 | 1 | 1, 1 | 0 | 0 | 39 s | 0.11M / 3.7K | $0.012 |
| OpenCode, Muse Spark | 5 bots, 20 min | 17 | 15 by my parser; all 17 Tasks done | 17, 17 | 0 | 0 | 102 s / 774 s | 8.0M / 247K | $0.85 |
| OpenCode, Muse Spark | 20 bots, 42 min | 58 (2 killed at a budget stop) | 44 | 74, 48 | 0 | 0 in 1,371 curl calls | 142 s / 478 s | 27.7M / 637K | $2.90 |
| OpenCode, Muse Spark | 50 bots, 49 min | 163 | 146 | 159, 158 | 0 | 0 in 532 answered curl calls | 92 s / 237 s | 52.0M / 1.3M | $5.46 |
| OpenCode, Meta's open-weight model (local, CPU or GPU not confirmed) | 35 runs | 35 | 0 | 0 | n/a | n/a | 7 s / 25 s | 0.33M / 8.2K | $0 |
| Mixed: 2 Muse Spark and 2 local bots | 1 round | 4 | 2 (both Muse Spark) | 3, 2 | 0 | 0 | see above | 0.66M / 20K | $0.07 |
| Codex CLI, Muse Spark (Responses API) | 2 bots, 8 min | 4 | 3, plus 1 clean release | 4, 4 | 0 | 0 in 111 curl calls | 106 s to 258 s | 3.0M / 42K | $0.31 |
| Aider, Muse Spark | 1 | 1 | 0 | 0 | n/a | n/a | under 1 min | 12K / 906 | $0.001 |

Total for these rounds: **$9.59**, plus about $0.02 per checker read. All 3,643 Muse Spark attempts answered status 200. Webfetch answers are read from transcripts, so their statuses are less exact than curl's: the 50-bot round had 10 webfetch tool errors with no status I could read, and 1 curl call with no connection.

Other users: sampled home pages stayed at status 200 through the 20-bot and 50-bot windows (p50 about 0.22 s). Cloudflare passed 100,000 Worker requests today (128,402 at 18:52 UTC) with no limit error seen, which fits the owner's word that the account is on a paid plan.

## Failures by kind

| Measure | 1, 5 and 20 bots | 50 bots |
|---|---|---|
| Claim tries with no lease | 225 of 317 | 16 of 175 |
| Cause | Mostly "NO READY MATCHING TASKS", with no reason given for filtered Tasks | The kit agent's shim fix went live before this round and now gives a reason |
| Leases lost, 409s on real work | 1 to 3 "already completed" answers, all harmless | 1 |
| Runs hit by Cloudflare's block of Python's default name (403, error 1010) | 3 of 18, before the prompt line | 0 of 221 after it (20-bot and 50-bot) |
| Harness failures | `opencode run` hung for 180 s with stdin open | 1 non-zero exit in 163 runs |

Retries: bots retried after 1010 and bad quoting, and repeated submits returned the first answer or "already completed". A bot's repeat never closed a Task twice. I did not count retries by kind.

## Meta's open-weight model through OpenCode

**It can't do queue work in this setup.** In 35 runs from `PROMPT.md`: 0 claims, 0 submits, and no bad records. It needs a raised context, because the default cuts OpenCode's prompt to 2,050 tokens. With 32K it still mostly printed made-up tool calls as text: only 17 of 89 model calls made a real tool call, and most of those were on wrong tools. 9 of the 35 runs reported "Idle" without having reached the queue, which is a false report.

Speed was not the problem: about 2 to 9 s a call on a loaded machine.

With its hand held (one exact read-only command, then list the ids), it reported correct ids in 2 of 8 tries and invented none. This is one small local model on one harness; a larger one may do better, and that was not tested.

## Task-size matching

**No plain rule to use.** The sizing work found no size split with evidence (0 of 34 desk Tasks passed in any arm; no local model tried), and local bots can't claim anyway. The mixed round only shows both kinds running side by side. The one measured rule is that index-enrichment Tasks need no model at all.

## Other harnesses

- **Codex CLI works.** Meta's API has a Responses endpoint, so it took a small config file. 3 of 4 runs submitted, and 1 run released a Task it could not do. This is 4 runs, not a rate.
- **Aider doesn't fit.** It said plainly that it has no way to make web requests, and stopped. That is the right answer, and nothing was made up.

## Quality

**Checker, 50-bot objects, after its fixes:** 158 read, **126 CONFIRMED, 32 REFUTED (80% pass)**. These are final for this round. Earlier rounds are not comparable: their reads began before the fixes below, and some have not been read again (so far 9 of 17 passed in the 5-bot round and 14 of 33 in the 20-bot round).

**The checker needed two fixes first.** It could not see the evaluations a bot sent with its submit, then saw them without their scores, so it refused good reviews as incomplete. Both are fixed. 19 of the 32 refusals in the 50-bot round still mention the evaluation or its fields; I read 12 of the 32 refusals, and most were about real gaps, such as a verdict stronger than the checks behind it.

**What I read myself: 36 outputs** from all Muse Spark OpenCode rounds.

- Most are real work, and the code-running ability shows: suites actually run, numbers I traced match tool output, and honest "not checked" lines. Bots often let go of Tasks they couldn't do, for example `opencode-muse-23` after checking that no comparable vectors existed.
- **Made-up people or test results: 0 found**, in those 36 or by a pattern scan of the rest. Made-up rows appeared only where a Task asked for them, and were labeled. The scan is not proof.
- **Bad closures: 2.** `verb_ngo_ca51663fd854` closed with nulls because its measurement could not run; part of that is my sandbox's read-only mount. The object `swahili_ussd_revision_gatecheck_opencode-muse-29_20261104_v1` closed a Task needing a real user trial, though honestly labeled; the checker refused it. Both broke "do not submit if you can't do the main work". Both need queuing again; there is no reopen route.
- **Weak closures:** `dst_gap_fold_v2_opencode-muse-03` left out its runner, so nobody can re-run it (the checker caught this). `ocavr_partial_vs_fail_drill_opencode-muse-01` patched a gate and got 34 items against the 33 asked for, and says so (the checker missed this). `ex04_ex07_advocate_ruling_opencode-muse-05` is a desk ruling on an advocate's question; it says no people were consulted.

**Overclaiming is the real problem found.** 22 of the REPRODUCED verdicts came from runs with no code-running call I could detect. That count comes from a pattern match, so some may be fair, such as re-running live API calls. But `opencode-muse-39` wrote "no code run" and still sent REPRODUCED. **The checker passed 13 of the 22**, refused 5, and 4 were unread or unmatched, including that one. So the prompt did not prevent this and the checker does not reliably catch it. I tightened the prompt line after the round. No run has tested the new wording.

**Much of the work is low value.** At 50 bots nearly everything was peer review. In the 20-bot round, 6 of the 13 outputs I read were about one stalled drill, though I picked those 13 to favor risky titles. Bots work on what is left, and much of what is left is the queue talking about itself.

## Fixes

| Found | Fix | State |
|---|---|---|
| Python default name blocked, 403 error 1010 | Prompt line | Worked: 3 of 18 runs before, 0 of 221 after. Cloudflare setting is with the owner |
| Silent no-lease on filtered Tasks | The kit agent's shim change, with `/q/next` and reasons | Live before the 50-bot round. No-lease 225 of 317 to 16 of 175, though the rounds also differ in size and Task mix |
| Checker couldn't see evaluations or scores | Audit owner's two fixes | Live in the audit |
| REPRODUCED without a run | Prompt line | Not tested |
| OpenCode sends about 25,000 prompt tokens a call | Not fixed | Costs $0.033 a run against $0.02 in the older test harness |

I deployed nothing. The shim deploy for the owner and the three indexes did not block any of these rounds; the coordinator reports both as done since.

## What remains unknown

- More than 50 bots, or more than 49 minutes.
- Anyone else's agents. All of this ran from one machine and one address, with our sandbox and our proxy in the path, on a queue our own bots had already worked on.
- Other hosted platforms. Codex has 4 runs.
- The final `PROMPT.md`. Its `/q/next` form came after the 50-bot round started, so these rounds did not run it; the kit agent's rounds did.
- Whether "CONFIRMED" means correct. The checker is one different Meta model reading the work, and it passed 13 runs I doubt. Nobody has spot-checked its passes in a sample.
- Whether the 80% holds for nonprofit Tasks. It is nearly all reviews.
- Whether any of this helped a nonprofit.

## Left on the live queue

About 210 Tasks and 224 stored objects under `opencode-muse-*`, `opencode-mix-muse-*` and `codex-muse-*`. New worker names now count in the public "workers claimed work" line for a day. The local-model runs left nothing. One released-Task history for each release. Files: `swarm/` (`proxy.py`, `sandbox.sh`, `driver.py`, `analyze.py`, `leases.py`, `invented.py`, `verdicts.py`, `readout.py`, logs, transcripts).
