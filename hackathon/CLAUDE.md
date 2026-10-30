@AGENTS.md

## Mandatory architecture and handoff direction

Follow AGENTS.md and the [worker-first execution policy](guides/worker-first-execution.md): only nouns, verbs, surfaces and narrow supporting infrastructure. Seed packs contain nouns and verbs. Project is a human label for a surface/grouping, not an architectural primitive. This requirement supersedes older three-concept descriptions in a handoff or plan.

Ordinary reasoning must run in authorized workers, including private workers. Server-side nouns and verbs retain permission and evidence requirements; an inference exception does not create another domain authority. Every implementation, review and handoff must name the existing owners, scope and relevant checks. Reject competing queues, hidden server agents, pack auto-activation and unrecorded provider fallback. Do not describe documentation or a test fixture as universal runtime enforcement.

## Claude Code notes

- This is a documentation repo. Prefer editing an existing page over adding a new one, and keep each page short.
- Use WebFetch only for official pages (cerebralvalley.ai event pages, dev.meta.ai, astryx.atmeta.com, the npm
  registry) and record the URL and date next to the fact you took from it.
- When a fact changes, update it everywhere it appears (`grep -rn` for the old value) and add a line to `CHANGELOG.md`.
- `guides/compliance-checklist.md` carries legal and platform sources; change it only with a cited source.
- Run `make index` after adding pages and `make check` before you finish a task.
