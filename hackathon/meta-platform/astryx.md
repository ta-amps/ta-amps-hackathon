> Unofficial AI-assisted summary, provided "as is" with no warranty. Meta's documentation governs; read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Astryx

Meta's open-source design system for React: MIT licence, built on React 19 and StyleX, still in beta
([repository](https://github.com/facebook/astryx), [getting started](https://astryx.atmeta.com/docs/getting-started)).

## Packages (npm registry, all released Oct 23, 2026)

| Package | Version | Notes |
|---|---|---|
| `@astryxdesign/core` | 0.7.4 | Needs React and React DOM 19 or newer, and `@stylexjs/stylex` ^0.19.0 |
| `@astryxdesign/theme-neutral` | 0.7.4 | Needs `@astryxdesign/core` at exactly the same version |
| `@astryxdesign/cli` | 0.7.4 | Needs Node 22.13.0 or newer |
| `@astryxdesign/build` | 0.7.4 | StyleX build plugins, only for compiling from source (needs Vite ^8.1.3) |
| `@stylexjs/stylex` | 0.19.1 | |

React was at 19.3.1 on Oct 26. Pin exact versions: it's a 0.x beta.

## Setup

- Install core, StyleX, a theme and the CLI. The packages ship pre-built, so no build plugin is needed unless you
  compile StyleX from source.
- Import the reset and base stylesheets, wrap the app in the theme provider, and import each component from its own entry
  point, as the getting-started page shows.
- Agents can look components up with the CLI: `npx @astryxdesign/cli component --list` and `component <Name> --dense`.

## Cautions

- `npx @astryxdesign/cli init` writes `AGENTS.md` and `CLAUDE.md` without asking. Don't run it in a repo that already
  has its own agent files.
- Never run plain `npx astryx`: the unscoped name is an unrelated npm package ([CLI docs](https://astryx.atmeta.com/docs/cli)).
- It's a beta. Keep a fallback (plain React with the same design tokens) if a component blocks you for long.

Sources: as linked plus https://registry.npmjs.org for versions, checked 2026-10-26.
