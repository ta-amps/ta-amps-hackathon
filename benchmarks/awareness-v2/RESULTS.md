# Awareness v2: results

**Plain answer:** on 30 questions about projects created August to October and already in Fabric's rows, an agent told the one call to make used about 18% fewer tokens per right answer than the same agent with GitHub's API. That win is registered, but thin. It came only from questions that need a search; to read the licence or language of a named project, GitHub's API was cheaper (not registered). Across our 56-question set, 40 of them from our rows, Fabric answered fewer questions and showed no token advantage. On the 16 outside our rows it got 52% against 100%, at about 2.5 times the tokens per right answer (1.5 to 4.7), because it answered so few; per question, no difference was shown. GitHub's API scored right on every answer. By the rule we registered, we may not say Fabric costs fewer tokens than GitHub's API in general.

A separate agent session that did not run the test recomputed the tables and hypothesis figures from the raw records and they matched, and it re-scored 73 runs against GitHub. It did not recompute the Nov 2 figure. It is separate work, on the same model family, not an outside party. Its findings are in `records/REVIEW-RESULTS.md`; the text before those fixes is kept privately.

## Conditions
Muse Spark 1.3, contributor tier, Meta API, default settings, Nov 4, 2026, 04:37 to 05:01 UTC. Fabric build 0a34da10 (source 61ec0b4), rows frozen at 01:54 UTC. 67 held-out questions, answers from GitHub at draw time. Registered in `PREREGISTRATION.md` before the run; the files listed in the checksum file in `prereg/` still match. 1,139 of 1,139 registered runs finished, none lost. Ranges are 95%, resampling questions. Output of the registered analysis: `records/analysis-output.txt`, `records/results.json`. Nov 2 ran on the standard tier, so its numbers are not a baseline here.

## Registered hypotheses
| | Test | Result | Verdict |
|---|---|---|---|
| H1 | B vs C, tokens per correct, `primary` (30 questions, in our rows) | 1,826 vs 2,230, ratio 0.82 (0.68 to 0.97) | **Win, but thin:** 0.9% of resamples at or above 1; dropping one question (V017) moves the upper end to about 1.00 |
| H2 | B not worse than C, `primary` | 88/90 vs 90/90, -2.2 points (-6.7 to 0) | **Pass.** All of the -2.2 points come from one question, V016 |
| H3 | H1 and H2 on `any_real_repo` (56 questions) | 2,484 vs 2,154, ratio 1.15 (0.88 to 1.54); 140/168 vs 168/168, -16.7 points (-25.6 to -8.9) | **Fail**: no token difference shown, and answers clearly worse. This measured the read-through with its `repo=` route out for the whole test |
| H4 | B vs B-old, tokens per correct, `primary`, at least 5 times fewer | 1,826 vs 174,006, ratio 0.010 (0.004 to 0.021). Total tokens per run 1,785 vs 58,002, ratio 0.031 | **Pass** |
| H5 | B-cold vs C, `primary` | 5,361 vs 2,230, ratio 2.40 (2.04 to 2.88) | **C cheaper**: told only to start at `llms.txt`, Fabric costs about 2.4 times more here, about 4.3 times on the 56 questions |
| H6 | B-direct vs C, `primary` | 1,074 vs 2,230, ratio 0.48 (0.36 to 0.58), 90/90; 47% of runs answered with no model call | **Win, and an upper limit**: the licence and language templates match the sentence forms the shim answers. Those 42 runs of 90 cost 0 because no agent is involved, yet a real agent needs a model to make the call. Charging them at B's mean gives 0.75 (0.65 to 0.87): still a win, with far less saving |
| H7 | B vs C, `multi_discovery`, a different test | 1,903 vs 8,124, ratio 0.23 (0.21 to 0.26), both 24/24 | **Win, favours Fabric by construction**: combinations were drawn from our rows. Part of the gap buys a topic check B doesn't make: B's rows have no description, and a reviewer judged that 12 of B's 24 runs include a name that looks off topic, against 0 of C's. The score stands under the loose registered rule |

The film rule needed H1, H2 and H3. H3 failed, so only a sentence limited to repositories in Fabric's rows is allowed. Registered sign tests, B against C: `primary` 0 questions better, 1 worse, p = 1; `any_real_repo` 0 better, 13 worse, p = 0.0002.

## Every group, tokens per run and correct
| Group | A plain | B | B-direct | B-cold | B-old | C | C-raw |
|---|---|---|---|---|---|---|---|
| primary | 0/90, 1,003 | 88/90, 1,785 | 90/90, 1,074 | 88/90, 5,242 | 10/30, 58,002 | 90/90, 2,230 | 30/30, 7,048 |
| fresh, since Nov 1 | 0/30, 1,064 | 27/30, 2,419 | 27/30, 1,536 | 27/30, 7,171 | 0/10, 78,739 | 30/30, 2,462 | 10/10, 13,977 |
| low stars, not in rows | 0/30, 1,008 | **21/30**, 2,622 | **21/30**, 1,889 | 27/30, 12,936 | 0/10, 88,107 | 30/30, 2,219 | 10/10, 10,818 |
| not on feed | 0/18, 1,021 | **4/18**, 1,997 | **7/18**, 2,243 | 17/18, 21,737 | 0/6, 84,934 | 18/18, 1,154 | 6/6, 2,511 |
| invented, right answer names no licence | 9/9, 820 | 9/9, 2,098 | 9/9, 1,880 | 9/9, 24,842 | 3/3, 82,401 | 9/9, 2,516 | 3/3, 11,641 |
| multi_discovery, different test | 0/24, 989 | 24/24, 1,903 | 24/24, 1,859 | 24/24, 7,258 | 0/8, 54,480 | 24/24, 8,124 | 8/8, 36,397 |
| any_real_repo | 0/168, 1,017 | 140/168, 2,070 | 145/168, 1,427 | 159/168, 8,728 | 10/56, 69,967 | 168/168, 2,154 | 56/56, 8,472 |

No arm gave a wrong answer on the 56 real-repository questions except one in B-old. B's misses were all "unknown". C-raw is secondary: on `any_real_repo` B's tokens per correct against it are 0.29 (0.18 to 0.50), with the same 16.7-point loss in answers.

## Where Fabric lost
- **The `repo=` read-through never worked in this test.** On real repositories outside the rows, `/q/repos?repo=` returned rows 0 of 102 times, in all three arms that use it, from the first such call to the end. `name=` returned rows 102 of 104 times, though not always the asked repository (it shows in the stored text in 93). Every one of B's 23 misses on these groups involves a `rate_limited` reply, and in 20 of them B stopped after that one reply, though the working `name=` route was there. Our tool text said "One call is usually enough". The shim calls GitHub with no credential. The records can't separate a refusal by GitHub from the shim's own stored wait, so we don't know how far the test's own traffic, earlier probes and other callers fed it. We expect shared Cloudflare addresses play a part, but no record shows that. A fix belongs in the route, and any repeat needs its own registration.
- **A name our filter withholds:** V034 failed in all 9 B, B-direct and B-cold runs because a word in the repository's name is on the shared list, so the shim withholds it and doesn't serve it. A real repository, and the filter's cost. The draw checked only two sections of the list, which is how it got in.
- **V049 failed in all 9 of those runs too:** `repo=` was limited; 4 runs stopped there, and in the 5 that tried `name=`, on a common word, it didn't list that owner.
- **Two owners:** V016 has two accounts with that name in the same month. Every arm that answered named the other account, which the registered rule accepts; none named the drawn owner. B's two unknowns listed both accounts and declined to pick, and could fairly count as right. All of H2's -2.2 points are this.
- **Not knowing the route:** an agent knows GitHub's API already but must be told about Fabric (H5).

## Exploratory, not registered: read as leads only
`run/explore.py`, `records/exploratory.txt`.
- **The H1 saving doesn't hold for every question.** On a named repository's licence or language, B costs more than C: ratio 1.15 (1.09 to 1.21), cheaper on only 2 of 14 questions. Owner questions: 0.79 (0.57 to 1.05), which includes 1. Discovery, 4 questions: 0.55 (0.41 to 0.68). So "the one call" doesn't save tokens on the simplest lookup, and all of B's saving on `primary` is prompt tokens.
- **Projects since Nov 1, in our rows too, show no saving:** 1.09 (0.45 to 2.83). Pooling `primary` and `fresh`: 0.89 (0.66 to 1.23), which includes 1.
- B-cold reached more unindexed repositories than B (27/30 and 17/18). All 44 of its correct runs there got rows from `name=`. It paid about 6 to 19 times C's tokens per run on those groups. A lead for a fix: fall back from `repo=` to the search path. This has not been tested.

## Things that favour one side
**Favour C:** its GitHub calls used an authenticated token (`gh`), so it never met the anonymous limit B's read-through hit, and an anonymous agent might. The harness also trims GitHub's replies, which GitHub itself doesn't do; C-raw shows the untrimmed cost. Owner questions were kept only where the name has at least 6 characters and GitHub finds at most 8 matches, which suits C's 8-result search. This filter was in neither the registration nor the first write-up.
**Favour B:** `primary` and `fresh` come from Fabric's own rows, so coverage is assured there. Tool text for B and the question wording fit each other, and B's prompt names the feeds. B-direct's forms match the templates. **The harness sends B compact JSON and C JSON with spaces after commas and colons, which isn't GitHub's doing and wasn't disclosed in the registration.** It could matter: at a worst-case token per separator, H1's upper end reaches 1.005 and the win is lost; at half a token it is 0.985. We had no tokenizer for this model, so the real figure is unknown, and likely at the low end. A future run should format both alike. Tokens to build rows aren't charged. The registration said they cost none; the Nov 4 scan used no model, but earlier feed runs aren't counted, and we didn't measure them.
**B-old:** 13 of the 30 `primary` questions are rows no feed page ever showed, which B-old can't reach, and 55 of its 67 runs hit the six-tool limit, which caps its tokens and cuts its answers. It also ran on the new build with one new search field removed; the search's other changes stayed on, so it isn't exactly the Nov 2 route. On the 13 on-page named questions it got 9/13 at 31,679 tokens a run against B's 39/39 at 1,484, about 21 times. The Nov 2 26/30 was on page rows only, on another tier.
**Time is not a fair comparison:** C's seconds include the harness's 2.2 s wait between GitHub calls, so B's 8.8 s against 15.5 s should not be quoted.

## Failures and departures, on the record
- 65 of 3,201 model attempts failed: 62 Meta 429s, one timeout, one 502, one 503. All were retried and no run was lost. They report no tokens, so they cost none here. 13 attempts in B-old finished with `tool_calls`.
- **Not registered, found afterwards:** the shim's edge cache is shared, so an answer one arm got from GitHub could serve a later run of any arm. This can only have applied to `name=`, since `repo=` never returned data. Runs on those items aren't fully independent, and results could differ on another day, in either direction.
- Registered ranges collapse to a point when every run is right (C's 100.0 to 100.0). 30 of 30 questions right fits a true rate as low as about 89% (Wilson, not registered).
- The pre-registration was finished while the questions were being drawn. I read only group counts and star counts before the run, not the questions, but nothing outside can show that: the checksums weren't posted anywhere first. The run used 12 workers, set before the checksums were taken.
- **Departure in the draw:** the registration excludes names hit by the shared word list, but the script checked two of its sections, so V034 got in. This works against B. Without V034, H3 is ratio 1.05 and 140 of 165: same verdict.
- The registered promise to report miss states is met only in part: `analyze.py`'s pattern can't read B-cold's replies, and B-direct's `ask=` replies that weren't direct aren't stored. The `repo=` and `name=` counts above come from the reviewer's own script.
- First dev run hit a live build without the route, since another deploy had replaced mine. It is kept privately, unused. After that, the runner stopped itself on a missing route; that never fired, and the deploy log shows no shim deploy after mine during the run.
- Rows: 1,780 last read on Nov 1 and 1,836 on Nov 4. There is no refresh timer yet.
- Scoring reused the Nov 2 scorer unchanged, plus the registered multi rule. Tokens in `runs.jsonl` reconcile exactly with `attempts.jsonl` per arm.
- Spend: $2.07 of $8 ($0.87 review of the code, $0.20 dev, $1.01 test), the Muse part estimated at $0.10 and $0.20 per million; the review ran on another model at its own price.

## What may be said
**A narrow sentence is the most the rule allows, and we don't recommend it as a film line,** because the win is thin, and a formatting difference in our harness could be enough to lose it under the registered rule.

**The sentence, if it is used:** "For GitHub projects created August to October 2026 and already in Teleion Fabric's feeds, an agent told the one call to make used about 18% fewer tokens per right answer, on our question mix, than the same agent using GitHub's API."

**Its small print:** Muse Spark 1.3, contributor tier, Nov 4, 2026; 30 held-out questions drawn from our own feeds, 3 runs each; 1,826 vs 2,230 tokens per right answer (range 3% to 32% fewer); 88 of 90 right vs 90 of 90. The saving came from questions that need a search (who owns a name, finding a project). To read the licence or language of a named project, GitHub's API used about 13% fewer tokens (not registered). On projects created since Nov 1, also in our feeds, no saving was shown. Across our 56-question set, 40 of them from our feeds, Fabric got 83% right against 100%, with no token saving shown; on the 16 outside our feeds, 52% against 100%, at about 2.5 times the tokens per right answer (1.5 to 4.7), because it answered so few; per question, no difference was shown. An agent not told the call used about 2.4 to 4.3 times more tokens than GitHub's API. GitHub replies were trimmed by our test and reached with a token; our replies had fewer spaces, which may account for part of the difference.

**About our own earlier version, the stronger result:** "Our new lookup used about 20 times fewer tokens per question than our old route, on questions the old route could reach" (1,484 vs 31,679 tokens a run on 13 questions, about 21 times, range 9 to 37, a subset of H4; 39 of 39 right vs 9 of 13, one run each for the old route). It says nothing about GitHub's API.

**Not supported:** that Fabric costs fewer tokens than GitHub's API in general; that a named-repository lookup costs fewer tokens than GitHub's API; any saving on projects since Nov 1; any saving outside our feeds; that it is more accurate; that it finds repositories GitHub can't; zero tokens as a general result; any time saving.
