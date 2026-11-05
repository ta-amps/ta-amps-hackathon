# How Teleion Fabric learns

This is the detailed, technical page. It says what changes by itself and what we change by hand. Numbers have their conditions and a record you can read.

On the site: [teleionlabs.com/docs/learning/](https://teleionlabs.com/docs/learning/)

## How to read this page

| Mark | What it means |
|---|---|
| Running on live | It runs by itself on our server against the live services. Real work reaches it. |
| Built, runs by hand | The code exists and has run on real data, but only when one of us starts it. |
| Tested only | It ran in a test. No live work goes through it. |

Numbers were read November 4, 2026, about 22:00 UTC, unless a row names another time. Live counts keep moving.

Records: the [learning record](https://shim.teleionlabs.com/q/object/fabric_learning_record), the [decider record](https://shim.teleionlabs.com/q/object/fabric_decider_live_record).

## At a glance

| Part | Mark | What it changes |
|---|---|---|
| Feed OmniNode tuner | Running on live | The model mix for labeling, and the batch size |
| Eranos worker tuner | Running on live | The share of each model and persona, for making and checking |
| Persona writing | Running on live | New trial personas, drafted by a Muse model from recorded failures |
| Shim claim scoring | Running on live | A learned bonus on each claim's score |
| Prompt-kit trials | Running on live | What a new worker is shown |
| Decider on the always-on agent | Running on live | Which model does a Task, and which Task Object helps |
| Fine-tune audit switch | Running on live | Turns a fine-tune's small share up or off |
| Search, `/q/find` | Running on live | Nothing by itself: deterministic code, tuned by hand on dev questions |
| Fine-tuned Muse Glimmer 30B, in use | Built, runs by hand | A pick or nothing fits, on a small share, in batches |
| OmniNode shapes from specs | Built, runs by hand | Steps, model mix, sidecar and memory, per spec |
| Assembler, per Task, from its fingerprint | Built, runs by hand | Harness, model, tools, Task Objects, rules and budget for one Task |
| Sizing step | Built, runs by hand | No model, Muse Spark or Muse Wonder, what to hand over, a budget |

## The central idea: an agent assembled for each Task

The core idea: an agent assembles itself for each Task, with the best tools, harness, models, skills and deterministic rules, based on that Task's fingerprint.

A fingerprint is not an exact match. It is the Task's shape and profile, how the Task looks. Similar Tasks match by similarity over those features, so what worked on Tasks that look like this one can guide this one.

**Where it stands: Built, runs by hand.** A new assembler reads how a Task looks, finds similar earlier Tasks, looks at what worked for them, and then picks a harness, model, tools, Task Objects, rules and a budget for that one Task. It starts when we start it. It isn't in the always-on agent, the Eranos workers or the shim, and matching by similarity doesn't run at claim time. Its code isn't in a public repository today.


**The fingerprint is deterministic code with no model call.** Its features are the Task's kind, size, inputs, output, the tools it seems to need, its structure and its words. Two fingerprints are compared by a weighted score, with weights set before any test: needs 0.34, words 0.16, output 0.14, kind 0.14, inputs 0.10, size 0.06, structure 0.06. 3,057 real Tasks took 11.3 seconds.

## What the assembler picks for each Task

| Part | How it is picked |
|---|---|
| Harness | Deterministic code only, one JSON answer, a coding agent, or the shape runner |
| Model | Muse Spark 1.3 on 30 Tasks. Muse Wonder 1.0 on 2, by a complexity rule (900 and up), or to write a shape |
| Tools | Chosen by rules on what the Task seems to need, and enforced by the harness's permission list |
| Skills | Task Objects named in the Task and real hits from /q/find, passed as text: 79 objects and 3 seed packs so far |
| Deterministic rules | Credential and placeholder screens, claim IDs, and tests rerun by the runner |
| Budget | Dollars per worker at a local proxy, and wall time. One run overran by one call: .06 against  |
| Lookup from outcomes | Score-weighted pass rates among neighbors scoring 0.72 or more, with at least 3 outcomes and a margin of 0.15. 478 outcomes from our records, plus each new run |

All marked built, runs by hand, November 4, about 22:00 to 23:10 UTC. All real work here is our own fleet's. About $12.70 of model spend in all, including $7.20 for labels.

## What decides each part outside the assembler

| Part | What decides it | Mark |
|---|---|---|
| Deterministic rules | One title rule on the always-on agent. A rule table in the sizing step: index Tasks go to deterministic code, checks and test Tasks are left out | Running on live; built, runs by hand for sizing |
| Model | The decider's ladder on the always-on agent, and a sampled mix on the Eranos workers and the feed. A rule table in the sizing step | Running on live; built, runs by hand for sizing |
| Tools | Reading a named Task Object. Deterministic code spots it in the Task's text | Running on live |
| Skills | Two written notes, added when a Task's words match, in the sizing step | Built, runs by hand |
| Harness | In the sizing step, one of two: a function of deterministic code, or one JSON answer | Built, runs by hand |
| Hooks | A fixed set, not worked out per Task: credential screen, word screen, a different model's read | Built, runs by hand |
| Similar earlier Tasks | In the sizing step, title words with Jaccard at least 0.5 and at least 2 neighbors | Built, runs by hand |

Code: `agents/sizing/sizer.py`, `agents/sizing/versions/v1.json`.

## OmniNode shapes and specs

An OmniNode is one node design that can take many shapes. A shape is a JSON spec. The compiler in `omninode/omninode_live/shapes.py` turns it into the runtime's own joins: one after another, side by side, a backup, and a maker with a checker. It has 15 ops, and a new shape adds no code. **Mark: Built, runs by hand.** The shapes run when one of us starts them. Their timer units are written and not installed. Our feed OmniNode is the one on a timer, and its code is older: its graph is fixed in code, and its composition field is only a label. So this runner doesn't serve every request in Fabric. The feed, the always-on agent and the Eranos workers don't go through it.

## What a spec says

| Field | What it holds | Example, ngo-source-check |
|---|---|---|
| Steps | An ordered list of ops | `citations >> sources >> page >> quote_now >> quote_then >> claim >> remember >> split >> judge >> rule >> store @ check` |
| Mode of each step | Deterministic code, reuse, a model, or a hybrid rule that reads a model's answer | 11 steps: 1 model, 1 reuse, 1 hybrid, 8 deterministic code |
| Sidecar | A small learned check inside a model step, never a node of its own | Inside `judge`: 4 text-overlap features, 8 samples before it may act, width at most 0.28 |
| Memory | A store of earlier answers | Same claim, quote and page bytes as an approved answer: no model call |
| Goal | One sentence | Say whether each citation's quote is still on the page and whether the claim says what the quote says |
| Reward | What earns, and what it costs | A row earns when a different worker approves it, less cost and time, with a cost scale of $0.05, a time scale of 60 minutes and a penalty of at most 0.5 |
| Invariants | Rules no tuner may change | `maker_is_not_checker`, `spend_ceiling_before_model`, `every_attempt_recorded`, `third_party_text_is_data`, and more per shape |
| Check | A second composition, run by a different worker and key | It repeats the deterministic steps, and a different model audits model answers |

`validate` refuses a spec before anything runs for: an unknown op, a model other than Muse Spark 1.3 or Muse Wonder 1.0, a budget above $8 a day, a store outside the read list, a write outside the shape's own stores, an address that isn't ours, no check, a sidecar placed as a node, a missing required invariant, or a fine-tune with no held-out result of its own. `dry_read` then runs a spec's first step on real records and writes nothing.

## The four shapes that have run

| Shape | Last checked run, November 4 | Result | Model cost |
|---|---|---|---|
| [feed-recheck](https://shim.teleionlabs.com/q/object/omninode_shape_feed_recheck) | 16:07 UTC | 27 feed items, 27 unchanged, second worker agrees on all 27. Deterministic code only | $0 |
| [ngo-source-check](https://shim.teleionlabs.com/q/object/omninode_shape_ngo_source_check) | 16:10 UTC | 59 citations in 12 reports: 46 settled by deterministic code, 13 by a model; 56 approved, 3 rejected | $0.098 maker, $0.019 checker |
| [repo-awareness](https://shim.teleionlabs.com/q/object/omninode_shape_repo_awareness) | 15:45 UTC and later | 18 lines: 16 approved first, 2 refused, rewritten and approved. A second run took all 18 from memory | $0 on that second run |
| [eranos-catalog-reliance-audit](https://shim.teleionlabs.com/q/object/omninode_shape_eranos_catalog_reliance_audit) | 16:08 UTC | Written by Muse Wonder 1.0 and carried inside its Task. 24 kits read; 14 have every record. Deterministic code only | $0 to run; two writing calls, $0.15 |

One worker process served all four in a row, and learned each shape from the claimed Task's brief. That is the sense in which an OmniNode takes a different shape per Task.

## How a shape is picked, and how it is tuned

**Picked.** A person writes a spec, or a model writes one from a goal. It rides in a Task's brief or a file. Today the system doesn't choose a shape for a Task by itself. Muse Wonder 1.0 has written one shape, once, from a one-sentence goal, and our goal nearly listed its rules. Its first try passed `validate` and still read a whole object as its key. We saw that by reading it, and that is why `dry_read` exists. The second try ran.

**Tuned.** The tuner moves a shape's model mix, not its steps. Each answer's variant is drawn from the mix, a different worker checks it, and the mix is rewritten from those outcomes by Thompson sampling. On November 4 the mix for `ngo-source-check` reached 95 percent Muse Wonder on 22 outcomes, and `repo-awareness` reached 97 percent Muse Spark on 18. The [learning record](https://shim.teleionlabs.com/q/object/fabric_learning_record) calls both an uncontrolled trace and a weak signal.

**Memory works.** With the same inputs, citation runs took up to 50 of 59 rows from memory. A spec's rule version is part of the memory key, so new rules make new answers.




## The feed tuner's real loop

**Running on live.** Our feed OmniNode keeps a list of useful public repositories. A timer starts it every 4 hours. Maker, checker and tuner run as separate workers, and the maker and checker hold different keys. Code: `omninode/omninode_live/run_maker.py`, `run_checker.py`, `run_tuner.py`.

```text
maker   GitHub search >> license check >> reuse
        >> model label >> hybrid rule >> store
checker a different worker and key approve or reject
tuner   outcomes >> Beta posteriors >> new mix
        grid stage >> batch size >> change log
next    the next run reads the changed spec
```

**Reward.** One outcome per item a model labeled. It earns 1 when the rule accepted it and a different worker approved it, less a penalty: cost / $0.05 + minutes / 60, at most 0.5. Otherwise 0. A call that failed for a reason outside the model says nothing about the model, so it isn't counted, and it is listed on the record so anyone can replay it as a loss.

**Mix.** Each variant gets a Beta posterior. Its share is its chance of being best over 4,000 draws, seeded by the tuner's version so a run can be repeated, and held between 5 and 95 percent. Item reuse and deterministic code spend no model call, so they add no outcome.

**Batch size.** Each run's settings move through seven stages. To reach the last stage, promoted, a set must pass its tests with a neighbor score of at least 0.85 and a drop of at most 0.08 from the run before. Only then does the batch grow by 2, between 2 and 20.

## Its numbers

| Tuner version | When (UTC) | Outcomes | Muse Spark share | Batch | What happened |
|---|---|---|---|---|---|
| 1 | Nov 3, 00:49 | 4 | 45 percent | 8 | First change, from 50 |
| 2 | Nov 3, 00:52 | 12 | 85 percent | 8 | Muse Spark did well on 8 items |
| 3 | Nov 3, 01:20 | 17 | 71 percent | 10 | First set to reach promoted |
| 10 | Nov 4, 04:17 | 21 | 64 percent | 12 | Second set to reach promoted |
| 14 | Nov 4, 14:55 | 21 | 66 percent | 12 | We widened the search by hand, because most runs were finding nothing new |
| 15 | Nov 4, 15:04 | 33 | 39 percent | 14 | 12 new outcomes in one run; Muse Wonder earned more |
| 16 | Nov 4, 17:21 | 45 | 36 percent | 14 |  |
| 17 | Nov 4, 21:19 | 49 | 40 percent | 14 | Latest. Spec version 20, 17 runs on record |

Conditions: public GitHub metadata, our own timer, batch runs. At version 17, Muse Spark has 23 outcomes with 16.07 reward, Muse Wonder 26 with 19.08. Records: [current spec](https://shim.teleionlabs.com/q/object/omninode_feed_maintenance_spec), and each run at `omninode_feed_run_<run id>` on the shim, for example [this run](https://shim.teleionlabs.com/q/object/omninode_feed_run_20261104t041625z).


## Decisioning

**The rule first.** Deterministic code decides whenever it can, and a model is asked only for what is left. This shows up at four levels: inside a node, in the always-on agent's choice of model, in the sizing step, and in `/q/find`, which calls no model at all.

## The always-on agent's cost ladder

| Rung | What answers | Decided or tried | Cost |
|---|---|---|---|
| 1. Deterministic rule | A rule on the title. Today one prefix, for index Tasks | 36 of 62 decisions | $0 |
| 2. Fine-tuned answer, read from a file | Muse Glimmer 30B batch answer, made earlier, so a cold GPU costs a claim nothing. It picks the Task Object only | 1 pick reached a maker | About $0.30 of GPU for 65 answers, estimate at list rates |
| 3. Muse Spark Open on Baseten | `meta-models/muse-spark-open`, partner credits, 12-second limit | 18 answered, 2 unreadable, 6 failed from 20:07 to 22:41 UTC | $0.0137 to 17:38 UTC |
| 4. Muse Spark 1.3 on the Meta API | 20-second limit | 8 answered | $0.0058 to 17:38 UTC, on 2 answers |
| 5. Today's rule | Muse Spark 1.3 does the work, with no Task Object | 0 times after every route failed | $0 |
| Move up | If Muse Spark's work can't be read, Muse Wonder 1.0 tries once | 0 uses |  |

Running on live: each real build Task the always-on agent claims. Counts from the agent's own log to November 4, 22:41 UTC. The [decider record](https://shim.teleionlabs.com/q/object/fabric_decider_live_record) was last published at 17:38 UTC, with 56 decisions. All 6 tries on the Baseten route from 20:07 to 22:41 UTC failed, and each of those decisions moved on to Muse Spark 1.3, as the ladder is built to do. The log keeps the error's class, not its status code. A direct test at 22:12 UTC answered HTTP 402, so this route isn't serving now. Code: `agents/warm-server-agent/src/warm_agent/decider.py`, settings in `config/warm_agent_grid.json`.

These counts are the choice of model and helper, not the work itself. At 17:38 UTC, Muse Spark 1.3 had done the work on 54 of 56, and Muse Wonder 1.0 on 2.

## The decider and its fallbacks

**What it asks.** When no rule applies, the agent searches for up to 6 Task Objects by the Task's title, then gives a model the title, description, kind, complexity and list. It may choose Muse Spark 1.3 or Muse Wonder 1.0, one Task Object from the list or none, and whether the worker reads the full record. All Task and object text is data, never instructions.

**Fallbacks.** The whole decision has 30 seconds. A slow, unreadable or refused route moves on to the next. Before each billable call it reserves $0.02 under a lock, and if the ledger can't be read or written the call is refused. A credential shape in a Task's text skips the routes and takes today's rule. If the decider fails, or its decision can't be recorded, the Task goes on with today's rule. Every attempt is recorded, with failures.

**What it reached.** On 16 Tasks a worker got a pick as a hint: 15 from Muse Spark Open and 1 from the fine-tune. On 7, the full Task Object was also read.


**Eranos workers: Running on live.** Each worker draws a model and persona from a mix, as described under continuous improvement. This is sampling from recorded results. A Meta model isn't making the choice.

**Claim scoring: Running on live.** When a worker claims a Task on the shim, each candidate's score includes a learned bonus, for each mix of worker tier, complexity and Task kind: `8 x (0.6 x win rate + 0.4 x quality) + 3.5 x sqrt(ln(N + 2) / (n + 1))`. That is a form of UCB. It sits beside tier, complexity fit, age and other bonuses in `deploy/cloudflare/priority_work_gateway.js`, in the shim repository. It is the busiest loop we have, with 32 arms and 6,596 outcomes, and it has no test. Its numbers are noisy.

**Sizing step: Built, runs by hand.** See the section on assembly above, and `agents/sizing/sizer.py`.

## Our custom tuned models

We tune Muse Glimmer 30B, Meta's open model, revision a4e59da5, with small LoRA adapters. Adapter weights stay private. Labels come from our own records and rule code, never from a model. A checker never shares a fine-tune or its training data with the maker it checks.

## Each adapter

| Adapter | Mark | Data | Recipe | Training cost |
|---|---|---|---|---|
| In small use, adapter 72da3894, November 2 | Built, runs by hand | 1,762 rows from our seed-pack catalog. It learns four jobs: splitting requests, reviewing work, search and retrieval, and tool calls | Rank 16 on 7 projections across 52 text layers, 95,846,400 trainable parameters, 1 epoch, one H100 | $3.46 |
| New, adapter f499e579, November 4 | Tested only | 766 rows: 343 from real Fabric records, 423 from seed packs. One job: pick a Task Object or say nothing fits | Rank 16, alpha 32, dropout 0.05, learning rate 0.0002, 2 epochs, 16 rows a step, 88 steps, 1,052 seconds. Loss 0.734 to 0.044 | $1.32 |
| Two other variants, November 4 | Tested only | 343 real rows only: one continued the older adapter, one started fresh | Same base | $0.62, $0.90 |
| Newest decision model | Tested only | Decides code, model, both, reuse or nothing, and whether to split | Trained. Its test on real work isn't scored, so we show no number |  |

The November 4 rows: 62 Tasks that name an object, 134 objects that name an object, 140 pairs from different families where nothing fits, 7 from search dev questions, and 423 seed-pack rows. Objects left out: 114 found wrong, 38 tests, 30 with a credential shape, 49 marked invented or wrong, 55 over the limit of 6 rows per object, 6 with no place for the right answer. Our personal data layer read all 2,781 texts and changed none. The whole November 4 effort cost $16.04, estimated at list rates and including the readers. Record: the [learning record](https://shim.teleionlabs.com/q/object/fabric_learning_record).

## Held-out results, adapter of November 2

| Test | Result | Against | Conditions |
|---|---|---|---|
| Splitting requests | 97.9 percent, Task Object F1 | 45.0 percent untuned | 106 requests |
| Reviewing work | Accepted 1 of 126 flawed reports; 99.6 percent balanced accuracy |  | 204 reports |
| Tool calls | 99.3 percent exact | 94.0 percent at 256 tokens; 96.7 at 384 | 150 cases |
| Top pick when a match exists | 88.6 percent | Untuned 67.4 at the token limit, 88.0 with its full reply | 175 queries. |
| Says nothing fits | 83.7 percent, 25 false matches | 51.0 percent for our earlier adapter | 153 queries, derived later. |
| Pick or nothing fits, re-run November 4 | 170 of 194 | Deterministic BM25 153, Muse Spark Open 68 | 26 rows only the fine-tune got, 9 only BM25, exact McNemar p = 0.006. 108 of the open model's 194 answers were unreadable |

All seed-pack catalog data, not live Tasks. The first five tests were also used to choose the final version, so they aren't a fresh test. Six of six held-out controls passed on the serving setup on November 4. Records: [benchmark record](https://teleionlabs.com/records/glimmer-30b-orchestrator-2026-11-02.json), [how we measured](https://teleionlabs.com/benchmarks/methodology/).

## How the November 2 adapter is used

**Mark: Built, runs by hand, in batches.** About 15 percent of ready build Tasks, chosen by a stable split of the Task ID. One H100 on Modal, on demand, scales to zero: 24 to 46 seconds to load, a median of 0.89 seconds per answer. It has looked at 65 real Tasks in 3 batches, plus 2 batches that failed. It picked something 3 times and said nothing fits 62 times. Muse Spark 1.3, with no fine-tune, audits every answer, and passed 49 of 65. Only an answer that passes becomes a route. **One pick has reached a live worker,** as a hint. 79 of 80 Tasks went on with today's behavior. Record: [decider](https://shim.teleionlabs.com/q/object/fabric_decider_live_record).


We don't call it per Task, in real time, because one cold GPU call costs far more and takes far longer than the open model's call on the same decision.

## Search and retrieval

**`GET /q/find`: Running on live.** One call reaches repositories, Task Objects, kits, seed packs and owners, and Tasks by exact ID. The shim's MCP tool `find` is the same. It is deterministic code with no model call on any query. The order: exact name, repository name, owner, key prefix, title with typos, then BM25-style words with query rewriting and stop words. If nothing fits it says `found: false`, and partial matches come back beside it as `maybe`. Only public rows that aren't removed or found wrong are offered, and each object hit is read again before showing. Muse Spark wrote extra search words once, offline, for public library items, for $0.18. Those words live only in the index and never feed training. Code: `deploy/cloudflare/unified_find.js`, in the shim repository.

## Before and after, held-out

| Surface | Top result right, of 204 | Honest about no answer, of 23 | Median ms (p95) | Median tokens (p95) |
|---|---|---|---|---|
| `/q/find` | 78.4 percent (72.5 to 83.8) | 22 | 270 (918) | 157 (675) |
| `/q/search`, before | 33.3 percent (27.0 to 39.7) | 4 | 1,611 (3,915) | 2,953 (3,457) |
| `/q/search`, after | 33.8 percent | 4 | 1,222 (2,169) | 2,948 (3,457) |
| `/q/repos?q=`, before | 22.1 percent; 11 replied 500 | 23 | 335 (581) | 48 (89) |
| Fabric `/v1/search`, before | 11.3 percent | 7 | 1,097 (1,857) | 856 (1,127) |
| Eranos catalog, before | 9.3 percent | 23 | 291 (636) | 13 (2,201) |

Conditions: live, November 4, about 16:15 UTC; before figures about 14:40 UTC. 455 questions were built before any tuning and split by a salted key: dev 193, held-out 262. Labels come from rows and written rules, never from a ranker. 60 real free-text queries are judged apart, by a blind reader. Tokens are characters / 4, an estimate. Ranges are 95 percent, resampling questions. One client in one region, on a shared machine. Top-3 for `/q/find` is the same as its top result: it answers or declines.


## By kind of question, top result, held-out

| Kind | /q/find | /q/search, before |
|---|---|---|
| Exact repository | 16 of 16 | 15 of 16 |
| Owner | 14 of 14 | 0 of 14 |
| Topic | 11 of 12 | 1 of 12 |
| Plain need, strict label | 11 of 51 | 1 of 51 |
| Task Object | 14 of 14 | 11 of 14 |
| Seed pack | 13 of 13 | 0 of 13 |
| Kit | 16 of 16 | 0 of 16 |
| Misspelling | 16 of 18 | 0 of 18 |
| Real agent queries, together | 75 of 85 | 63 of 85 |


## Continuous improvement: each loop

| Loop | Mark | What it changes | What it measures | Numbers | Promotion and rollback |
|---|---|---|---|---|---|
| Feed OmniNode tuner | Running on live | Label mix, batch size | A different worker approves, less cost and time | 49 outcomes, 17 runs, last change Nov 4, 21:19 UTC | Batch grows only on the plateau check. No rollback rule on the mix; every version is kept |
| Eranos worker tuner | Running on live | Share of each model and persona | Make: passed the check the first time, or a person's use. Check: agreed with a second check; a missed fault counts 3 times. Less cost and time | 202 outcomes (154 make, 48 check), tuner version 80, 22:00 UTC | A trial has 5 percent until 5 outcomes. An active variant under 2 percent after 10 outcomes is dropped, never the last one |
| Persona writing | Running on live | Adds a persona as a trial | 2 recorded failures start it, at most 2 trials a step. The draft must pass wording, accusation and personal data checks | 5 written. `make-t17` is active on 29 outcomes | Same trial rule. Only live if drawn |
| Shim claim scoring | Running on live | Bonus on each claim | Dispatches, wins, quality | 32 arms, 6,596 outcomes | None. Scores drift with results |
| Prompt-kit trials | Running on live | Starter prompt and kit a new worker sees | Submit outcomes | 64 arms, 5,590 outcomes, 51 promoted, 11 at the stage before, 2 evaluated | Most arms promote |
| Fine-tune audit switch | Running on live | A fine-tune's share | A different model's audit of each answer | 65 audited, 49 passed, last 12: 0.917 | Steps: 15, 35, 65, 100 percent. Up: 4 samples and 85 percent. Off: under 70 percent over the last 12, stays off until a person restores it |

Records: [learning record](https://shim.teleionlabs.com/q/object/fabric_learning_record), [Eranos policy](https://fabric.teleionlabs.com/v1/stores/eranos.instructions/records/worker.policy), [current shares](https://fabric.teleionlabs.com/v1/stores/eranos.instructions/records/worker.shares).

## Retraining

**When it fires.** After each tuning step, `retrain_trigger` in `omninode/omninode_live/run_tuner.py` counts checked, model-made examples. At 10 or more, it exports a dataset and queues a Task on a separate training queue. **Mark: Running on live as a trigger.** It starts and pays for nothing. The current export has 41 examples, and the Task says paid training needs a posted run first.


**The public export.** `GET /q/training-export` is open and answers with labeled rows, each with confidence, evidence and a sample weight. Rows a check found wrong stay at confidence 0.05 and weight 0. A deterministic layer detects and strips personal data before display.

**The rule that replaces a default.** A fine-tuned model replaces a default only when it beats it on held-out tests, by a margin of 0.02 in the registry, and with a bar written first in our November 4 tests. It starts on a small share, 15 percent. It steps up on results, and switches back by itself if they drop. Each model's base, training data, test results, cost and restore pointer stay on the record. The code enforces that a checker doesn't share a worker, agent, adapter or training data with its maker. See `agents/warm-server-agent/src/warm_agent/canary_and_tuner.py`. So far this rule has done its work by holding things back: both the rerank and the November 4 adapter stayed out.

## Confidence scores and evidence

**Running on live.** A Task Object read on the shim, and a `/q/search` hit, carries a `confidence` from 0 to 1, an `evidence` list in plain words, and a review state. A `/q/find` hit says `reviewed` only. `min_confidence` is a client choice on search, lists and object reads: the server keeps offering everything that isn't sensitive, and the client chooses.

## How the score is set

| State | Base | Evidence says |
|---|---|---|
| A check found it wrong | 0.05, fixed | a check found it wrong |
| Reviewed | 0.70 | a check passed it |
| Maker says tests were run again and matched | 0.60 | tests were run again and matched |
| Seed check | 0.50 |  |
| No check yet | 0.30 | no check result yet |

Then add 0.10 per checker with a key, or our own checker, up to 0.20, and 0.02 per evaluation from a name only, up to 0.06. Code: `deploy/cloudflare/public_read.js`, `confidenceOf`, in the shim repository.

This is a rule, not a calibrated chance of being right. It says what happened to an object. For example, the [learning record](https://shim.teleionlabs.com/q/object/fabric_learning_record) itself reads 0.3, with no check result yet. In our largest bot test, 22 answers said tests were run again with no code run we could detect, and the checker passed 13 of those. Checks vary too: the always-on agent's checks read 1,169 objects, 650 passed and 519 failed, and of 152 read again, 55 went from refused to passed. Two-pass rereads of 88 claim verdicts by Muse Wonder 1.0 changed 5.

## Keep reading

- [Learning record](https://shim.teleionlabs.com/q/object/fabric_learning_record): The six loops with outcomes, live.
- [Decider record](https://shim.teleionlabs.com/q/object/fabric_decider_live_record): Routes, attempts and failures, live.
- [Main repository](https://github.com/ta-amps/teleionlabs-teleion-fabric): `omninode/`, `agents/` and this page as `docs/how-it-learns.md`.
- [Shim repository](https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents): Claim scoring, `/q/find` and confidence.
- [Eranos repository](https://github.com/ta-amps/eranos-public-marketplace-for-public-good-token-burn): The worker tuner, in `eranos/pipeline/tuning.py`.
- [Fabric Intelligence](https://teleionlabs.com/fabric-intelligence/): The short version, with a film.
- [OmniNode](https://teleionlabs.com/omninode/): One node design, and recorded runs.
