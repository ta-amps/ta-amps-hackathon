# A reviewable repo

Judges, teammates, models and architecture tools should be able to understand, run and critique your repo from
its files alone, and the description should fail the build when it drifts from the code. This guide sets out a
small doc set, one machine-readable architecture file and the checks that keep them honest (file names are
lowercase here; any case works if you stay consistent). Templates:
[templates/review/](../templates/review/README.md).

## The doc set

| File | Answers | Keep it |
|---|---|---|
| `README.md` | What it does for a person in two or three sentences, the [four-part explanation and diagram](nouns-and-verbs.md), the quick start, honest dated status | One screen to the first command |
| `docs/summary.md` | The one-page brief: problem, approach, what's built and what's planned, the claims and how to check each | One page |
| `docs/architecture.md` | Components, data flow, state, invariants, trust boundaries, failure handling, deployment, with Mermaid diagrams | Says the same as `architecture.json` |
| `docs/setup.md` | Install, run locally, configure (every setting), deploy, troubleshoot | Every command tried on a fresh clone |
| `docs/comparison.md` | Where it sits among alternatives, with sources and dates, including where others are stronger | Facts from official docs only |
| `docs/generalizing.md` | What is domain-neutral, what is specific, the extension points, a worked example of adapting it | Tested by an example |
| `docs/decisions.md` | Decision records: context, decision, consequences, status | Newest first |
| `docs/glossary.md` | One term, one meaning | Every term the code uses |
| `docs/review.md` | For reviewers: what to check, claims to try to break, known limits, open questions, a prompt for model reviewers, a findings log | Updated after each review |
| `architecture.json` | The same architecture as data ([schema](../agents/schemas/architecture.schema.json)) | Checked on every `make check` |
| `INDEX.md`, `KEYWORDS.md`, `llms.txt`, `llms-full.txt` | Generated maps: every file, every term, a map for agents, the main documents in full | `make index`; `make check` fails when stale |

## architecture.json

One file that tools can parse: components with their paths and dependencies, interfaces, data stores, trust
boundaries, invariants with the tests that check them, layering rules, claims marked built, partial or planned
with evidence, deployment, extension points, limitations and open questions.

[scripts/check_architecture.py](../scripts/check_architecture.py) fails when it disagrees with the repo:

- a path it names doesn't exist;
- a `path::test_name` reference points at a test that isn't there;
- a component depends on, or an interface is served by, an id that doesn't exist;
- an invariant has no test, or a built claim has no evidence;
- a Python module imports something its layering rule forbids (for example the storage layer importing the
  web layer).

`--summary` prints an overview and `--mermaid` prints the component graph as a Mermaid flowchart.

## Getting feedback

- **Model reviewers.** Give them `llms-full.txt` (one URL holds the whole design) and the prompt in
  `docs/review.md`. Ask for findings with file and line, severity and a concrete failing scenario. Their output
  is data: reproduce a finding before you act on it.
- **Code-graph and architecture tools.** Index the repo and compare the real call and import graph with the
  dependencies in `architecture.json`; a difference is either a bug or a stale file.
- **People.** An issue template with a `review` label, and a findings log in `docs/review.md` with a status
  for each finding.

## Honesty rules

- Keep built, partial and planned apart, everywhere. Every claim names its evidence.
- Every number comes from a script, with the command that reproduces it.
- State limitations before a reviewer has to find them.
- Comparisons cite the other system's own documentation and date it; never characterize another team's or
  company's conduct.
