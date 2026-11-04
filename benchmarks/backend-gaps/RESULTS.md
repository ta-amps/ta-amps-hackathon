# Backend gaps, Nov 4, 2026

## Live now

- **Shim** source `dc41b33`, on `545d921`. Watchdog 0, release guard passed, full vitest 476 of 476 before the last small fixes, focused tests and page-check after them.
- **Eranos workers**, all five on `dc753d2` (branch `claude/gaps-20261104`), worker noun v15, 0 restarts. Undo: reset the checkout to `9d022e8`, write the noun from it, restart all five.
- **23 labeled upkeep Tasks** on the shim queue, category `report_upkeep`. 2 done, 21 ready.

## 1. Reuse

**Cause.** Our own test label was part of the text being compared. Stored questions end in "Test run, Nov 4, our own example, not a real organization's request."

- A person's repeat has no label, so it scored 0.42 to 0.56 against its own report, under the 0.8 bar. It never matched. Control before the fix, same words, no label in the text: built fresh, 96 s.
- Labeled questions looked alike because of the label's words: 124 of 148 reports had a rival at 0.7 or above. So 67 of 69 reuse checks said no, and each one cost a model call and queue time.
- Short questions also failed: "Should a small nonprofit get an independent audit?" keeps 2 distinctive words, below the minimum of 3.
- The "0 of 200" count was also wrong. `backend.py` 9c read a field that is only on the request's part, and the records come in key order, not newest first. True count before today's tests: 2 of 229. Fixed.

**Fix.** Exact label text at the end of a request is stripped. The same question word for word matches first, and the reuse check approves it under the other key with no model. Bar 0.8 to 0.5 (floor in code too), because a check decides anyway. Up to 1,000 candidates, as the library would soon pass 200.

**Measured, labeled, through the form's own calls:**

| Group | Answered from the library | Notes |
|---|---|---|
| Exact repeat | 5 of 5 | No model, $0. Includes the short audit question and 2 with no label words in the text |
| Reworded | 2 of 10 | 5 went to a check and got no; 3 never reached the bar. 8 built fresh |
| Related, should not reuse | 0 of 5 | 1 went to a check and got no |
| Exact repeat of a taken-off report | Not reused | Went to another candidate, the check said no, built fresh |

- **Time:** one exact repeat sent alone was delivered in 31 s. Single fresh requests took 96 and 127 s, before the fix. The batch's exact repeats took about 200 s only because they waited behind the rest of the batch in line.
- **Tokens:** an exact repeat uses 0. A fresh request's maker used a median of 3,319 tokens (16 requests, 2,904 to 9,104). The checker's tokens aren't on the request record, so the true saving is higher and I did not measure it. The whole test moved the ledger $1.75 (61.39 to 63.14), which includes other agents' spend, so it is only a ceiling.
- **A no costs a little:** a check that says no adds about $0.003 and a queue trip before the fresh build.
- **Reworded is weak.** Word overlap misses most rewordings, and some nos are fair: "covers hand washing but includes no glove rules" was about a thin report of ours. Whether the 2 reworded reuses truly fit was judged by the model check only, not by a person or a second reader.

## 2. Bot-sized Tasks

23 real Tasks at `ngo_priority`, opened through `/q/enqueue`, labeled in their text, by `seed_upkeep.py`: 12 source rechecks, 5 plain language copies, 6 adaptations for a place or audience. Plain copies and adaptations use only the 5 reports that both careful reads passed. No taken-off report. `needs_people` is false on all, and `/q/next` returns them first.

**Not shown: a model-driven bot finishing one.** 3 real OpenCode bots started and stopped at the test proxy's day budget (503) before submitting. I left that budget alone. No lease was left behind.

**Shown: a plain script finished 2**, claim to submit, no model. RPT-R0DE92AB-01: 6 of 6 quotes found on irs.gov. RPT-R08129DA-01: dol.gov answers 403 to this machine, so no quote was checked.

My errors, on record: the script's first version counted page markup spacing as a change, and stored "3 not found" on the IRS report; the other summary read as "0 of 3 found". I corrected both summaries in the database by exact key and marked the wrong one refuted. Correct copy: `sources_rechecked_rpt_r0de92ab_01_20261104__by_eranos-source-recheck-script`. The two closed Tasks' own summaries still have the old lines.

No timer repeats the rechecks: these are one round, not recurring yet.

## 3. Confidence scores

Export sample, 200 rows, on `545d921`:

| Kind | Rows | Score |
|---|---|---|
| Refuted | 41 | 0.05, all |
| Reviewed | 66 | 0.72 median, up to 0.82 with a keyed checker |
| Unreviewed | 77 | 0.32 to 0.36 mostly; 0.62 with tests run again |

A made-up name moves a score by 0.02, capped at 0.06: 4 name-only evaluations gave 0.34 against a base of 0.30. **No row in the sample has several keyed checkers,** so "reviewed by several reads high" is read in the formula (up to 0.96), not seen on data.

Added at the coordinator's request, live: `review_status` no longer calls refuted or name-only work `peer_reviewed` on `/q/object`, `/q/starter`, `/q/help`, lists and the catalog. A live refuted row now reads `failed`, 0.05. `/q/starter` had 23 of 23 `peer_reviewed`; now 6 reviewed, 17 unreviewed. The dashboard's objects table says "A check found it wrong" instead of showing quality. `min_confidence` works on search, lists and `/q/object`, and confidence shows on `/q/object` and search hits.

## 4. Tests and watch

- **e2e after the deploys:** fabric, shim, queue, Eranos, names 114 of 114. Crawl and names, before them, 19 of 19, so the 2 earlier crawl failures are gone (test fixes someone made at 14:48). Browser stage not rerun after the deploys.
- **page-check:** the 2 phone-width `/c/` failures were one long label at 432 of 390 px. Shortened; page-check passes. Not a phone check on live pages.
- **Watch:** `records/watch.log`, hosts, units, worker errors, once a minute until about 5:20 PM ET. See the last section.

## Independent read

Change to reuse: NO-GO at first, 3 real defects, all fixed before going live, with tests: a label pattern could treat Ohio and Texas as the same question; non-Latin text, `$` and `€` were dropped when comparing; a queued check could still approve a report taken off later. Shim: conditional GO; refuted rows in the dashboard table, paging and the search score fixed. Seeder: its word guard checked nothing; fixed, and it now stops on a hit. **The fixes themselves were not re-read,** as time ran out.

Not fixed: `check_claimed` still names a model on a same-words check.

## Files

`seed_upkeep.py`, `send.py`, `tally.py`, `recheck_one.py`, `watch.py`, `records/repeats-result.json`, `records/upkeep-sent.jsonl`. Worktrees `worker/`, `shim/`.

## Watch, read at 5:13 PM ET

See `records/watch.log`. Read before its 30 minutes ended; anything after this time is not covered here.
