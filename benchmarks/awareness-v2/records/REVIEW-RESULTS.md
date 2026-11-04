BLOCK

# Independent review of the Awareness v2 write-up

Reviewed `RESULTS.md` as saved at 00:11:00 local on Nov 4. It was edited once after this review began (V034 line and the B-cold lead); findings use the later text.

**Short version.** The numbers are sound: every table figure, range and verdict reproduced from raw records, the checksums match, and the arms, groups and run counts are as registered. No re-run is needed. The block is on the words and the folder: one false statement, a film sentence wider than its evidence, small print that hides the two facts a fair reader most needs, and files that can't go public as they stand. All are text or packaging fixes.

## High

**H-1. The film sentence is wider than its evidence, and the small print omits where the saving stops.** `RESULTS.md:62,64`.
- "New GitHub projects already in the feeds" covers `fresh` too, and `fresh` shows no saving: B 2,687 vs C 2,462 tokens per correct, ratio 1.09 (0.45 to 2.83), 27/30 vs 30/30. Pooling `primary` and `fresh`, all in-row questions: ratio 0.89 (0.66 to 1.23), which includes 1. (Pooled figure is mine, not registered.) The registered test covers only projects created Aug 1 to Oct 31.
- The saving depends on question mix. On licence and language lookups of a named repository, B is dearer: ratio 1.15 (1.09 to 1.21), entirely above 1, and B was cheaper on only 2 of 14 items. Owner alone: 0.79 (0.57 to 1.05), includes 1. Discovery (4 items): 0.55 (0.41 to 0.68). `RESULTS.md:42` reports this as a lead, but a reader of the film sentence and its small print never sees it, and looking up a named repository is what "the one call" suggests.
- H1 is a registered win, but thin. Upper end 0.966 (0.965 to 0.972 across five other seeds); share of resamples at or above 1 is 0.9%. Dropping V017 alone moves the upper end to about 1.00 (2,000 resamples).
- The GitHub arm was harness-trimmed and authenticated, and the sentence says plain "GitHub's API". That trim favours C, so it isn't flattering, but it is unstated.

Fix. Sentence: "For GitHub projects created August to October 2026 and already in Teleion Fabric's feeds, an agent told the one call to make used about 18% fewer tokens per right answer, on our question mix, than the same agent using GitHub's API." Add to the small print: "The saving came from questions that need a search (who owns a name, finding a project). To read the licence or language of a named project, GitHub's API used about 13% fewer tokens (unregistered). On projects added since Nov 1, also in our feeds, no saving was shown."

**H-2. False statement on V016.** `RESULTS.md:37`: "B-direct gave the right owner 3 of 3".
- All three B-direct runs answered `keerthana2003-tech`. The drawn truth is `keerthanak-art`. They score correct only through the scorer's other-owner rule (`run/scorer.py:83`).
- All 9 correct runs on V016 in every arm (C 3, C-raw 1, B-direct 3, B 1, B-cold 1) are that same credit. No run named the drawn owner.
- B's two unknowns gave both owners in the source field and declined to pick. C took one of the two and got the credit. All of H2's -2.2 points come from this item, so the difference shown isn't a coverage or data gap.
- The rule is registered and the score stands. Fix: "Every arm that answered named the other account, which the registered rule accepts; none named the drawn owner. B's two unknowns listed both accounts."

**H-3. The GitHub-limit text understates what happened and blames luck the records don't show.** `RESULTS.md:35,53`.
- Every `repo=` lookup on a real repository outside the rows came back `rate_limited`: 0 of 102 worked (B 33, B-direct 31, B-cold 38), and 0 of 129 with invented items, from 04:37:26 until the end. That route was out for the whole test. "Rate-limit luck depended on the run's moment" isn't supported for it.
- `name=` lookups returned rows in 102 of 104 cases. The quoted "34" is true but hides this split. The registered promise to report miss states is met only in part, and `analyze.py` can't read B-cold's replies because its pattern expects compact JSON.
- Cause: all 23 of B's misses on these groups involve `rate_limited`, so "main reason" holds, but it is half the story. In 20 of the 23 B stopped after that one reply, while the working `name=` route was available. B's tool text says "One call is usually enough" (`run/common2.py:141`).
- "No credential" holds by source (`repo_rows.js:122`). "Shared Cloudflare addresses" is inference; no record shows it. `rate_limited` is also returned from the shim's own stored backoff with no GitHub call (`repo_rows.js:119`), so records can't separate a GitHub refusal from a backoff. How far the test's own traffic and earlier probes fed that state is unknown.
- V049 fails in all 9 runs of B, B-direct and B-cold, with no explanation given. `repo=` was limited and `name=`, on a common word, didn't list that owner.
- H3's Fail stands, as the registration charged this to B. Say plainly that H3 measured the read-through with its `repo=` route out, so another day could differ in either direction. Any repeat needs its own registration.

**H-4. The 83% and "in general" flatter Fabric on reach.** `RESULTS.md:3,64`. `any_real_repo` is 40 of 56 questions from Fabric's own rows. On the 16 questions truly outside the rows, B got 25 of 48 (52%) against C's 48 of 48, at 4,584 vs 1,819 tokens per correct, about 2.5 times. (Pool is mine, from registered groups.) The write-up never shows this pool, and "Across repositories in general" describes a set that is 71% ours. Fix: replace "in general" with "across our 56-question set, 40 of them from our rows", and add "on the 16 outside our feeds, 52% against 100%, at about 2.5 times the tokens".

**H-5. The folder isn't safe to publish whole.** See the publication section.

## Medium

**M-1. Undisclosed asymmetry favouring B in tool-result format.** `run/common2.py:135` sends B's replies with compact separators. `run/common2.py:93` sends C's trimmed replies with default separators, a space after every comma and colon. Those spaces are the harness's, not GitHub's. C replies carry about 0.04 separators per character. Rough sensitivity from `result_chars` and re-sends, assuming a token saved per separator: C falls 4.0%, ratio 0.85, upper end 1.005, H1 no longer a win. At half a token: upper end 0.985, still a win. At a quarter: 0.975. The real figure is likely at the low end, as tokenizers often merge such spaces, but I had no tokenizer for this model and the replies aren't stored in full. Fix: add it to "Favour B" with this range. A future run should format both alike.

**M-2. The small print's 2.4 times reads as wider than it is.** `RESULTS.md:64`. It follows the 56-question sentence but applies only to `primary`. On `any_real_repo` B-cold is 9,222 vs 2,154, about 4.3 times. Fix: state both.

**M-3. H7's 24/24 overstates B's fit to the topic.** `RESULTS.md:17`. The topic rule is a loose word match over name, description and topics. 12 of 24 runs in each of B, B-direct and B-cold include at least one of 7 names that look off-topic to me (for example `CubeLink-oss/voltdir`, a disk tool that passes "memory" on the words "low memory"). C: 0 of 24. This is my judgment, not a registered rule. B's rows carry no description, so B never sees what a project does, while part of C's extra tokens goes on reading exactly that. The score stands under the rule. Fix: add one clause to the H7 row saying the gap partly buys a topic check B doesn't make. H7 is not a film claim.

**M-4. H6's zero-token path has no agent in it.** `RESULTS.md:16`, `run/common2.py` `run_one`. The 42 direct runs of 90 cost 0 because no model is involved, yet any real agent needs a model to make the call and read the reply. "Upper limit" is said of the share, not of this. Sensitivity: charging direct runs at B's mean for that item gives ratio 0.75 (0.65 to 0.87). Still a win, with far less saving than 0.48. `ask=` replies that aren't direct are not recorded, so their miss states and their share of limit use are unknown. Fix: add the 0.75 and the reason.

**M-5. Undisclosed departures in drawing questions; neither changes a verdict.**
- The registration says names hit by the shared word list are excluded. `run/build_questions.py:17` checks only two of its sections, so V034's name (on the `marketing_voice` section) was drawn, and the shim's wider filter withheld it. This works against B: 9 misses, and B's dearest fresh item (34,290 vs 10,062 tokens). Without V034, H3 is ratio 1.05 and 140 of 165: same verdict. Disclose.
- `run/build_questions.py:55-61` keeps owner questions only where the name is at least 6 characters and GitHub's search finds at most 8 matches, which suits C's 8-result search. Stated in neither the registration nor the write-up. Add to "Favour C".

**M-6. "30 times" against our own earlier version needs its conditions.** `RESULTS.md:48,66`. The arithmetic holds (ratio 0.031, range 0.022 to 0.045). But "half" is 13 of 30, and 55 of 67 B-old runs hit the six-tool limit, which caps its tokens and cuts its answers; that isn't stated. On questions the old route could reach, the gap is 31,679 vs 1,484, about 21 times. B-old's `/q/search` also ran on the new build with one field removed, so it isn't exactly the Nov 2 route. H4 passes on any of these. Fix: quote about 20 times on reachable questions, or state 13 of 30 and the limit.

**M-7. "Not supported" is incomplete.** `RESULTS.md:68`. Add: that a named-repository lookup costs fewer tokens than GitHub's API; any saving on projects since Nov 1; any saving outside our feeds.

## Low

- `RESULTS.md:57`: "under three days old at most for the scan part" is muddled. Rows: 1,780 seen Nov 1, 1,836 seen Nov 4. Say so.
- The registered sign test isn't reported: B vs C `primary` 0 better, 1 worse, p = 1; `any_real_repo` 0 better, 13 worse, p = 0.0002. Add a line.
- `RESULTS.md:59`: the per-million prices cover the Muse spend only; the $0.87 review ran on another model at another price.
- `RESULTS.md:47` and the registration differ on row-building cost: the registration says none, the write-up says earlier feed runs aren't counted. The write-up is the safer wording; state the correction. I didn't check that cost.
- `RESULTS.md:43`: "the records don't" support the B-cold cause is too modest. Records show all 44 of its correct runs on these groups got rows from `name=`, and 12 went straight there, so "second lookup" fits only some.
- The checksums have no outside anchor. COORDINATION at 04:37:10Z names the file but not the values, and the questions, registration and checksum file are 33 seconds apart, ending 2 seconds before the first attempt. Timing agrees with the disclosure, but "read only group counts" can't be tested. Next time post the values first.
- V045 also has two owners with the same name in the same month. No effect: all credited answers name the truth.

## Reproduced

Own script over `runs.jsonl` and `attempts.jsonl`, with outcomes from `scored.json` after re-scoring checks. All match `RESULTS.md`:
- Tables 1 and 2, every cell, including wrong and unknown counts. "No wrong answer except one in B-old" holds; "B's misses were all unknown" holds.
- H1 0.8185 (0.6822, 0.9663). H2 -2.22 (-6.67, 0). H3 1.1532 (0.8807, 1.5402), -16.67 (-25.6, -8.93). H4 0.0105 (0.0043, 0.021), total 0.0308. H5 2.4035 (2.0379, 2.8751). H6 0.4814 (0.3632, 0.576), 42 of 90 direct. H7 0.2343 (0.2054, 0.2631). C-raw 0.2932 (0.1775, 0.5032).
- On-page 9/13 at 31,679 vs 39/39 at 1,484. Seconds 8.8 vs 15.5. Attempts: 3,201 with 62 + 1 + 1 + 1 failed, none with tokens; 13 `tool_calls`, all B-old. Tokens reconcile with 0 mismatches. Test spend $1.011, total $2.074.
- Exploratory figures, and "6 to 19 times" per run (5.8 and 18.8).
- All 8 checksums match. Scorer identical to Nov 2; 41 of 41 fixtures pass. Dev: B and B-cold 30/30 each.

Numbers I could not reproduce: none. Unchecked figure: "The Nov 2 26/30" (`RESULTS.md:48`).

## Verdicts against the registered rules

H1 Win, H2 Pass, H3 Fail, H4 Pass, H5 C cheaper, H6 Win, H7 Win as a separate test: each follows the registered rule. The film rule is applied correctly: H3 failed, so only a sentence limited to our rows is allowed. Analysis is the registered one: item bootstrap, 10,000 resamples, seed 99. 67 items, 6 groups, 13/13/4 strata, 12/8/6 kinds, 17 runs per item, 1,139 runs. The 12 workers are disclosed. Undisclosed departures: M-5 only.

## Re-scoring and truth

- Answers: 73 runs (fixed seed 20261104): all 28 non-correct B runs, plus correct runs across groups from B 12, B-direct 10, C 12, B-cold 4, C-raw 4, B-old 3. Checked against `gh api`. 73 of 73 agree on facts.
- Every licence, language and owner answer in all runs compared to the truth by plain exact match. Only differences: the 9 V016 credits, and "Apache License 2.0" style forms, correctly accepted.
- Truth: all 55 named-repository truths and creation dates match GitHub now; the 3 invented names still return 404; none forked or archived. Group membership against `rows-v1.json`: clean. No row disagrees with a truth.
- Scorer false positives: V016 by rule (H-2); topic fit in multi (M-3). False negatives: none on facts. B's V016 unknowns could fairly count as right.

## Fairness, checked

- Tokens: none escape. Failed attempts report none, reasoning tokens are inside completion tokens, and API totals agree on every attempt. On `primary`, all of B's saving is prompt tokens (80,930 vs 126,864); its completion tokens are higher (79,724 vs 73,881). Cached share is 61% vs 42%. Counted in full, as registered; cost isn't measured.
- Ordering: one seeded shuffle across arms, 12 workers, no arm favoured. `as_of` is the same in all 730 replies that show it. No shim deploy logged after 0a34da10.
- Leakage: no question's full repository name in the served-route source, the two `llms` files on disk, or tool text. Two bare hits in the gateway are ordinary words. Feed names in B's text match question wording: disclosed. The parser strips the template's "Answer with" ending and predates the draw: disclosed in substance.
- C's "not found" appears only on invented items, so no GitHub failure was misread. 0 search errors.
- Shared edge cache: disclosed. It can only have applied to `name=`, since `repo=` never returned data.
- Stated causes: V034 withheld, 9 runs: shown. C never limited: shown. Wilson 89%: right.

## Publication

`check_public.py` on a copy without `shim/`, make-check logs and `__pycache__`: clean, no credentials or private names. My own scan: no real-length credential anywhere. Token-like strings are repository-name fragments, plus masked test shapes in the code reviews. Private-name list: 0 in every file. Counts below are word-list hits only.

| Status | Files | Why |
|---|---|---|
| Safe | `records/analysis-output.txt`, `results.json`, `exploratory.txt`, the `live-*-backoff.txt` log, `where-tokens-went-nov2.txt`, `run/analyze.py`, `run/run.py`, `run/explore.py`, `dev/questions-old-primary.json`, `records/spend.jsonl` | 0 hits, or only false hits on long hex strings and digits |
| Safe as raw record, no words shown on a page | `prereg/questions.json` (2 voice, from a repository name), `records/attempts.jsonl` (451 voice, others are hex), `records/dev-runs.jsonl`, `attempts-dev.jsonl`, `run.log`, `run/scorer.py` (4 voice, inside a regex) | Word list allows record files as raw downloads |
| Change first | `RESULTS.md` | Findings above. 3 voice hits (the checksum file's name twice, V034's name) and 1 `visible_text` hit; old product name once at line 56 |
| Change first | `run/common2.py`, `run/build_questions.py` | Home-relative paths, including the key file's location (no value). `build_questions.py` also names a real third-party account |
| Change first or keep raw | `PREREGISTRATION.md` | Old product name once, one `visible_text` hit, the same third-party account. Editing breaks its checksum, so publish unchanged as a raw record, or publish an edited copy with both versions, as its own rule requires |
| Change first or keep out | `records/runs.jsonl`, `records/scored.json` (6 `always` each), `rows/rows-v1.json` (9), `rows/rows-v1.sql` (16) | `always` hits have no raw-file allowance. They come from third-party repository names and descriptions; filter them, and note the filter |
| Keep out | `records/REVIEW-INDEPENDENT.md`, `review-*.md`, `review-context-2.txt` | Internal security review detail, masked test shapes, internal words |
| Keep out | `records/watchdog-0a34da10.log`, `run/review.py`, `run/analyze_old.py`, `run/__pycache__/`, `dev/invalid-route-gone/`, `records/.lock` | Old product names and alias addresses; local paths including a provider key file's location; compiled files; an invalid run the write-up can cite without shipping |

## Not checked

- The live site and the live GitHub limit at run time; I made no shim requests. Replies beyond the stored first 300 characters.
- The served `llms.txt` beyond its stored head, and the build deployed, beyond the deploy log and watchdog line.
- Whether rows reflect all feeds, or the row-building cost.
- The Nov 2 figure, and full reading of all records by eye; the word scan is pattern-based. The list's `third_party_names`, `data_rendering` and `repo_rule` entries are descriptions, not patterns, so they weren't scanned as such.

Nothing but this file was written in the project. No model was called; only read-only `gh api` calls. My check scripts are in the session scratchpad.

## Second pass

BLOCK, on six short text edits. If they are made as written below, the text of `RESULTS.md` is approved and no third pass is needed. The folder conditions under "Publication" remain until the files are sorted.

Reviewed `RESULTS.md` as saved at 00:27:32 on Nov 4, against `records/RESULTS-before-review-fixes.md`, the raw records and the first-pass findings.

**First-pass findings.** H-1 to H-4 and M-1 to M-7 and the low items are all addressed in `RESULTS.md`. H-5 (the folder) is not a text matter and is still open. The hypothesis and group tables are unchanged from the first pass, and the raw records and checksums are unchanged. Each new figure was recomputed and matches, including these, which I had not fully run before:
- Without V034, H3 is 1.05 (0.84 to 1.34), -15.2 points (-23.6 to -7.9): still Fail, as stated.
- Without V017, H1's upper end is 0.996 at 10,000 resamples, so "about 1.00" is right, but on that seed it stays just under 1.

The word-list and private-name scan of `RESULTS.md` now gives 0 hits, and the old product name is gone.

### Remaining findings

**S-1 (Medium). The opening overstates this review.** `RESULTS.md:5`: "An independent review recomputed every figure below".
- Not every figure: the Nov 2 26/30 was not recomputed (it appears in that run's `results/RESULTS.txt`, line 6, which I read only now), and row-building cost has no figure I could check.
- "Independent" needs its condition. I did not run the test, but I am another Claude session, on the same model family, started from the author's session. That is separate work, not an outside party.
- Replace with: "A separate Claude session that did not run the test recomputed the tables and hypothesis figures from the raw records and they matched, and it re-scored 73 runs against GitHub. It did not recompute the Nov 2 figure."

**S-2 (Medium). The small print's 2.5 times can be misread, and my first-pass wording caused it.** `RESULTS.md`, "Its small print": "at about 2.5 times the tokens". That figure is per right answer, and its range is wide: 2.5 (1.47 to 4.74). Per question, B used 2,387 vs 1,819, ratio 1.31 (0.94 to 1.71), which includes 1. Pool is mine, not registered. Replace with: "at about 2.5 times the tokens per right answer (1.5 to 4.7), because it answered so few; per question, no difference was shown."

**S-3 (Medium). A factual error on B-old.** `RESULTS.md`, "B-old": "with the new search fields off". `run/common2.py` `tool_search` removes one field, `repo_matches`. The other changes on the new build stayed on. My first-pass M-6 said one field. Replace with: "with one new search field removed; the search's other changes stayed on".

**S-4 (Medium, against Fabric). "Could account for it" goes too far.** `RESULTS.md`, opening of "What may be said". Even at the worst case the formatting moves the ratio from 0.82 to 0.85. It could remove the win's margin under the registered rule, not the 18% itself. "Undisclosed" is also out of date, as the write-up now discloses it. Replace with: "because the win is thin, and a formatting difference in our harness could be enough to lose it under the registered rule". The small print's "may account for part of the difference" is fine.

**S-5 (Low). V049 wording, also from my first pass.** `RESULTS.md`, "Where Fabric lost". Only 5 of the 9 runs tried `name=`; the other 4 stopped after `repo=`. Replace the clause with: "`repo=` was limited; 4 runs stopped there, and in the 5 that tried `name=`, on a common word, it didn't list that owner."

**S-6 (Low). Two small precision edits.**
- Small print: "On projects added since Nov 1" should be "created since Nov 1"; the group is defined by creation date.
- "Where Fabric lost": "in all arms" should be "in all three arms that use it".

### Not required, worth considering

- The old-version sentence is now a subset of H4, not its own registered test, and has no range. Per run it is about 21 times (9 to 37). The parenthetical could carry that. The sentence itself holds, and H4 passes.
- "`name=` returned rows 102 of 104" counts replies with rows. The asked repository is in the stored first 300 characters in 93; the other 9 include V049's 5, and the rest can't be told from stored text. "Working route" is fair, not exact.
- The dropped sentence that limit state is shared with other callers was true by source (`repo_rows.js:85`). The new text names only the test's own traffic and earlier probes as possible feeders. Adding "and other callers" would be more complete.
- The plain answer gives the licence and language result without saying it is unregistered; the small print does say so.
- "GitHub's API counted every answer right" reads oddly. "Scored right on every answer" says what was meant.

### Publication, corrections to my first-pass table

- `run/common2.py`, `run/build_questions.py`, `run/run.py`, `run/analyze.py` and `run/scorer.py` are under the same checksums as `PREREGISTRATION.md`, which my table noted only for the latter. The two I marked "change first" should be handled the same way: publish unchanged as raw records, since the paths hold no secret, or publish edited copies beside the originals and say so.
- `records/RESULTS-before-review-fixes.md` is new and `RESULTS.md` now cites it. It has the old text's 3 voice hits, 1 `visible_text` hit and the old product name once. It is fine as a raw record if the old product name is accepted there, otherwise keep it out and drop the citation.
- `RESULTS.md` still cites `dev/invalid-route-gone/`, which my table keeps out. If so, say it is held privately, or the reference dangles.
- `records/REVIEW-RESULTS.md`, this file: 0 word-list and private-name hits before this section, and I rescanned after adding it. It needs no change to go with `RESULTS.md`, but it describes the earlier wording in detail.
- `run/explore.py` is not under the checksums, as it should not be; it was written after the run and is labelled exploratory.

Second pass checked no live site and made no model calls. Only read-only local checks ran, and nothing but this section was written.
