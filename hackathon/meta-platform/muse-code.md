> Unofficial AI-assisted summary, provided "as is" with no warranty. Meta's documentation governs; read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Muse Code

Meta's coding agent CLI. Stable release 1.4.13 on Oct 26 ([channel](https://api.meta.ai/muse-code/channels/muse-stable)).

## Install: download, read, then run

The docs ([Muse Code](https://dev.meta.ai/docs/muse-code), [quickstart](https://dev.meta.ai/docs/quickstart)) pipe
`https://dev.meta.ai/install.sh` straight into a shell. The script uses bash-only syntax, so if you pipe it, use bash.
Better still, download it, read it and then run it: [../scripts/install-muse-code.sh](../scripts/install-muse-code.sh)
does exactly that.

| What the installer does | Detail |
|---|---|
| Installs to | `${MUSE_INSTALL_DIR:-$HOME/.local/bin}` |
| Edits your shell rc files | Unless `MUSE_NO_MODIFY_PATH` is set |
| Platforms | Linux x86_64 and aarch64 (macOS needs 12 or later on Apple silicon) |
| Auto-update | Hourly, unless `MUSE_NO_AUTO_UPDATE=1`. Consider setting it while you record a demo |
| Size | The Linux x86 binary is about 400 MB |

The CLI isn't on npm. `@muse-code/sdk` is a separate TypeScript SDK.

## Sandbox (Linux)

From [permissions](https://dev.meta.ai/docs/muse-code/permissions):

- Linux uses a bundled bubblewrap helper. Without a working bubblewrap, every shell command fails as an environment error.
- Inside the sandbox only the workspace and a temp directory are writable. `.git`, `.muse` and `.agents` stay read-only,
  so an agent can't rewrite its own skills or hooks.
- Network modes: `--sandbox-network proxy-only` (default), `restricted` or `unrestricted`.

## Sign-in, billing and Contributor mode

- Sign in through the browser or paste an API key. In CI, `META_API_KEY` is used first, then a stored key, then a browser session ([auth](https://dev.meta.ai/docs/muse-code/auth)).
- Billing is pay-as-you-go, or a subscription (the docs list Everyday, High, Power and Maximum) ([subscriptions](https://dev.meta.ai/docs/muse-code/subscriptions)).
- **Subscriptions default to Contributor mode**, which lets Meta train on your content. A headless run can have it on if
  the setting was never saved. Pass `--contributor-mode off`, or set `MUSE_CONTRIBUTOR_MODE=0`, on every run that
  touches anything sensitive.

## Headless runs

From [extending](https://dev.meta.ai/docs/muse-code/extending) and [configuration](https://dev.meta.ai/docs/muse-code/configuration):

| Flag | Effect |
|---|---|
| `muse exec --json` | Run headless; JSON Lines events on stdout |
| `--prompt-file <path>` | Take the task from a file |
| `--max-model-steps <n>` | Stop after n model steps |
| `--disable-approval` | Skip approval prompts **but keep the sandbox** (the safe long-run mode) |
| `--approval-mode on-request\|untrusted\|never` | Approval policy |
| `--yolo` | Disables approvals **and the sandbox**, and trusts the workspace. Don't use it |
| `--disable-sandbox` | Turns the sandbox off. Don't use it |
| `--trust-workspace`, `--session-id`, `--approval-judge on\|off` | Other options |

Exit codes: 0 when the turn completes; 1 when it fails or is cancelled (including hitting the step cap); 2 for a usage
error; 130 or 143 on SIGINT or SIGTERM. The default model is `muse-spark-1.2`.

## Configuration

- User settings live in `~/.config/muse/settings.json`, which **must** contain `"schema_version": 1`. No project-level
  settings file is documented.
- `agents.execution_capacity` sets how many agents run at once: 1 to 64, default 8.

## Instructions, skills, hooks, MCP, workflows

| Topic | What the docs say |
|---|---|
| Instruction files | Reads the first that exists of `AGENTS.md`, `CLAUDE.md`, `.agents/AGENTS.md`, `.claude/CLAUDE.md`, and only after you trust the workspace |
| Skills | `<repo>/.agents/skills/<skill-id>/SKILL.md`; also scans `.codex/skills` and `.claude/skills`. Frontmatter isn't documented beyond `metadata.display-name` and `allowed-tools` |
| Hooks | Project file `<repo>/.muse/hooks.json`; 17 events including SessionStart, PreToolUse, PostToolUse, Stop and SessionEnd. **Hooks run outside the sandbox and approvals.** The file format isn't documented |
| MCP | `mcp_servers` in settings; `stdio` or `streamable_http` (url, headers); `mode` `required` (default, aborts the run on failure) or `optional`. **MCP tools aren't sandboxed.** Trusted project `.mcp.json` files load too |
| Workflows | `.agents/workflows/<name>.js`; up to 1,000 child tasks, 16 active; availability depends on build and rollout ([workflows](https://dev.meta.ai/docs/muse-code/workflows)) |

## Safety checklist

- [ ] Sandbox on; never `--yolo` or `--disable-sandbox`
- [ ] `--contributor-mode off` on anything sensitive
- [ ] `--max-model-steps` set on every headless run
- [ ] Only hooks and MCP servers you wrote or reviewed
- [ ] `MUSE_NO_AUTO_UPDATE=1` while recording a demo
- [ ] Keys in the environment or a secret store, never in prompts or files

More: [../agents/muse/README.md](../agents/muse/README.md). Sources: as linked, checked 2026-10-26.
