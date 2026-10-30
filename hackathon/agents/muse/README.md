# Muse Code: running workers safely

Notes for running Meta's Muse Code as a headless worker on a project. Platform facts are in
[../../meta-platform/muse-code.md](../../meta-platform/muse-code.md), checked 2026-10-26.

## A safe headless run

```bash
MUSE_CONTRIBUTOR_MODE=0 muse exec --json \
  --prompt-file briefs/L8.md \
  --max-model-steps 200 \
  --disable-approval \
  --contributor-mode off
```

- `--disable-approval` skips prompts but **keeps the sandbox**. Never use `--yolo` or `--disable-sandbox`.
- Contributor mode lets Meta train on your content, and subscriptions default to it. Turn it off on every run that
  touches anything sensitive.
- Exit code 0 means the turn completed, not that the task passed. Run the task's own done-when check afterwards.
- Run one task per git worktree, so parallel workers can't collide.

## Settings

User settings live in `~/.config/muse/settings.json` and must include `"schema_version": 1`.
[settings.example.json](settings.example.json) sets only that and `agents.execution_capacity` (4 parallel agents instead
of the default 8, so the work stays reviewable). Check both keys against the current
[configuration docs](https://dev.meta.ai/docs/muse-code/configuration) before you use the file.

## Instructions and skills

- Muse Code reads the first of `AGENTS.md`, `CLAUDE.md`, `.agents/AGENTS.md`, `.claude/CLAUDE.md`, so keep one `AGENTS.md`
  that both Muse Code and Claude Code follow.
- Project skills go in `.agents/skills/<skill-id>/SKILL.md`. Muse Code also scans `.claude/skills` and `.codex/skills`.
- Inside the sandbox, `.git`, `.muse` and `.agents` are read-only, so a worker can't rewrite its own skills or hooks.

## Hooks

Hooks (`<repo>/.muse/hooks.json`) run **outside the sandbox and outside approvals**, and the file format isn't
documented (as of Oct 26). This kit therefore ships no hooks template. Add hooks only after the format is documented,
and only hooks you wrote. Project hooks run only in a folder you have trusted.

## MCP

Servers go under `mcp_servers` in settings, as `stdio` or `streamable_http` (with `url` and `headers`). The default
`mode` is `required`, which aborts a run if the server fails; use `optional` for anything non-essential. MCP tools are
not sandboxed. Add only servers you run or trust, and keep tokens in the environment.

## Before a demo

Set `MUSE_NO_AUTO_UPDATE=1`, so the CLI can't update itself in the middle of a recording.
