@AGENTS.md

## Mandatory architecture and handoffs

Follow AGENTS.md: only nouns, verbs, surfaces and narrow supporting
infrastructure. Seed packs contain nouns and verbs. Project is a convenient
surface/grouping label, not a separate primitive or service authority. Reconcile
older plans and handoffs to this requirement before continuing their work.
Ordinary reasoning belongs to authorized workers; server-side nouns and verbs
retain scope, permission and evidence requirements. Reject competing queues,
hidden server agents, pack auto-activation and unrecorded inference fallback.
Record exact implementation, checks and limits; prose alone does not prove
runtime enforcement.

## Claude Code notes

- One task per session; `/clear` between tasks so context stays on the task.
- Plan mode first for anything larger than a small fix; paste the task's done-when check into the prompt.
- The guard hook (`.claude/hooks/guard.py`) blocks protected paths and risky commands in every mode. If it blocks you,
  don't look for a way around it: stop and ask.
- Ask the `reviewer` subagent to read the diff before every commit; fix every blocker it reports.
- `/brief <task id>` writes a brief for a Muse Code worker without sending it.
- Product model calls go to Meta's models only. Claude Code writes and integrates code; it never makes a model call
  inside the product.
