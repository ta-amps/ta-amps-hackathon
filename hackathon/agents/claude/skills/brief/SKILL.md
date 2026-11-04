---
name: brief
description: Write a task brief for a Muse Code worker or a Muse assistant as JSON in briefs/<task id>.json, following the brief schema. Writes the file only; never sends, queues or launches anything. Use when asked to brief, hand off or delegate a task.
argument-hint: "<task id>"
disable-model-invocation: true
---

Write a brief for task `$ARGUMENTS`.

1. Find the task in the project's backlog (`../teleionlabs-teleion-fabric/hackathon/project/backlog.md` or the repo's `docs/`). If the id
   isn't there, stop and say so.
2. Fill every required field of `../teleionlabs-teleion-fabric/hackathon/agents/schemas/brief.schema.json`:
   - `done_when`: one command or test that passes or fails, copied from the backlog.
   - `context`: the files the worker must read, and nothing more.
   - `constraints`: the hard rules that apply, in one line each.
   - `effect_class`: never `public`. Public effects stay with a person.
   - `budget`: `max_model_steps` (default 200) and `usd`.
   - `owner_type`: `muse-code` for code in a worktree, `muse-assistant` for research and writing.
3. Keep the brief under 2 KB. A worker that needs more context needs a smaller task.
4. Save it as `briefs/<task id>.json`, validate it against the schema, and show it.
5. Don't queue it, launch a worker or push anything. Say "Brief written, not sent."
