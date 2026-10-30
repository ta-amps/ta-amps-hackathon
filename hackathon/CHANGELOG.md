# Changelog

Newest first. Each entry names what changed and the date the facts were checked.

## 2026-10-29

- Moved the kit into the `hackathon/` folder of ta-amps/ta-amps, so there are fewer repos. Links, clone commands and workspace paths now point there; see [MOVED.md](MOVED.md). No facts changed.
- Filled [event/05-problem-statements.md](event/05-problem-statements.md). Meta's event page and the Cerebral Valley event page publish no separate problem statements, only two themes and two tracks. The page quotes their official text, names the Meta tools the pages list, notes that there are no per-theme prize categories or video-length rules, points to the Official Rules pages for the judging weights, and adds a short note on choosing a theme. The overview, themes, communications and FAQ pages, the event index and the README now say the same. Sources: https://dev.meta.ai/events/global-hackathon, https://cerebralvalley.ai/e/meta-ai-developer-hackathon and the Official Rules, checked 2026-10-29; the participants-only details page was checked signed out.
- Added [nouns and verbs in one minute](guides/nouns-and-verbs.md): a plain four-part explanation (nouns, verbs, surfaces, infrastructure) with an accessible SVG diagram that follows light and dark themes, plus its Mermaid source, for teams to copy into their READMEs. The README, the guides index, the worker-first policy, the AGENTS.md template and the reviewable repo guide now point to it. Kit design guidance, not an event rule.
- Clarified the required [worker-first architecture](guides/worker-first-execution.md): nouns, verbs, surfaces and narrow supporting infrastructure; seed packs bundle nouns and verbs, while project is only a human label. Updated the repository and reusable agent/Claude instructions so implementation, review and handoffs retain these boundaries. This is kit design policy, not an event rule or proof of completed runtime migration.

## 2026-10-28

- Added generic [typed agent recovery and lightweight review](guides/agent-recovery-and-review.md) guidance: omission versus malformed input, bounded correction loops, service-credential audience boundaries, deterministic proof gates, independent review tasks and explicit evidence limits. This is a suggested implementation pattern, not an event rule.

## 2026-10-26 (later)

- The kit now names no project. The plan pages and the project's hosting setup moved out to the project's own
  repo; what was generic about them became [guides/](guides/README.md): a ten-day plan, the agent workflow,
  local-first hosting and a compliance checklist (sources checked Oct 26).
- New: [guides/reviewable-repo.md](guides/reviewable-repo.md), the review doc templates in
  [templates/review/](templates/review/README.md), an [architecture.json schema](agents/schemas/architecture.schema.json)
  and [scripts/check_architecture.py](scripts/check_architecture.py), which fails when the file and the code disagree.
- Shared scripts made project-neutral: `check_public.py` reads private names (as hashes) from
  `scripts/private-names.sha256` and adds `--hash`; `build_index.py` takes links from the git remote and also writes
  `llms-full.txt`; `bootstrap-hosting.sh` reads `deploy/hosting.env`; `bootstrap-workspace.sh` clones any repos you name.
- The brief schema's `repo` field accepts any repo name.

## 2026-10-26

- First version. Event sections built from the event page, the Official Rules (waiver page, dated Oct 25) and the
  Oct 26 participant emails, all checked Oct 26.
- Meta platform notes from dev.meta.ai docs, the npm registry and Astryx docs, checked Oct 26.
- Agent templates, brief and receipt schemas, the transcription tool and scripts.
- Not yet covered: the problem statements and the workshop schedule (participants-only details page), and kickoff notes.
