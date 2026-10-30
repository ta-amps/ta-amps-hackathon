# Agent templates

Drop-in files that make coding agents follow a project's hard rules: instructions, enforcement and shared formats.
They come from working project repos, where they run every day.

| File | For | What it does |
|---|---|---|
| [AGENTS.template.md](AGENTS.template.md) | Muse Code and Claude Code | One rules file both agents read. Muse Code reads `AGENTS.md` first; Claude Code imports it from `CLAUDE.md` |
| [CLAUDE.template.md](CLAUDE.template.md) | Claude Code | Imports `AGENTS.md`, plus Claude-only notes |
| [claude/settings.template.json](claude/settings.template.json) | Claude Code | Allow, ask and deny rules; bypass mode switched off; the two hooks |
| [claude/hooks/guard.py](claude/hooks/guard.py) | Claude Code | PreToolUse hook. Blocks protected paths and risky commands in every permission mode, and fails closed |
| [claude/guard.example.json](claude/guard.example.json) | Claude Code | The guard's rules: protected paths and denied command patterns |
| [claude/hooks/format.py](claude/hooks/format.py) | Claude Code | PostToolUse hook. Formats each edited file with ruff or prettier; never blocks |
| [claude/agents/reviewer.md](claude/agents/reviewer.md) | Claude Code | A read-only subagent that reviews a diff against the hard rules before each commit |
| [claude/skills/brief/SKILL.md](claude/skills/brief/SKILL.md) | Claude Code | `/brief <task id>` writes a task brief for a worker without sending it |
| [muse/README.md](muse/README.md) | Muse Code | Safe headless runs, settings, skills and MCP |
| [muse/settings.example.json](muse/settings.example.json) | Muse Code | Minimal user settings (verify before use) |
| [schemas/brief.schema.json](schemas/brief.schema.json) | Both | JSON Schema for a task brief |
| [schemas/receipt.schema.json](schemas/receipt.schema.json) | Both | JSON Schema for a task receipt |

## Install in a repo (Claude Code)

```bash
mkdir -p .claude/hooks
cp ../ta-amps/hackathon/agents/claude/hooks/*.py .claude/hooks/
cp ../ta-amps/hackathon/agents/claude/settings.template.json .claude/settings.json
cp ../ta-amps/hackathon/agents/claude/guard.example.json .claude/guard.json
cp -r ../ta-amps/hackathon/agents/claude/agents ../ta-amps/hackathon/agents/claude/skills .claude/
cp ../ta-amps/hackathon/agents/AGENTS.template.md AGENTS.md
cp ../ta-amps/hackathon/agents/CLAUDE.template.md CLAUDE.md
```

Then edit `.claude/guard.json` for your protected paths, and fill in `AGENTS.md`. Run `claude` from the repo root, trust
the folder, and check `/status` lists the project settings. Test the guard by asking Claude to read `.env`; it must refuse.

## Why both instructions and enforcement

Claude Code treats `CLAUDE.md` as context, not as law. A PreToolUse hook that exits with code 2 blocks a call in every
permission mode, so the rules that must never break live in the hook. The deny rules in `settings.json` are a second layer.

## Keep copies in sync

`claude/hooks/guard.py` and `format.py` must stay byte-identical to the copies in each code repo. Change them in one
place, copy them everywhere, and run each repo's guard tests.
