# Moved here on October 29, 2026

This guide used to be its own repo, `ta-amps/hackathon-context`. On October 29, 2026 it moved into this
`hackathon/` folder of [ta-amps/teleionlabs-teleion-fabric](https://github.com/ta-amps/teleionlabs-teleion-fabric), so there are fewer repos to follow.

The last commit in the old repo was `7b02420d610ea7b174b04d0c6a5014ffd6a05e20` (October 29, 2026, "Merge #4: Add
a plain four-part explanation and the official event themes"). The files here are copies of that commit, with
these changes:

- Links, clone commands and workspace paths point here: `https://github.com/ta-amps/teleionlabs-teleion-fabric` and
  `../teleionlabs-teleion-fabric/hackathon/` instead of the old repo.
- GitHub reads workflows and issue templates only at the root of a repo, so the check workflow and the Correction
  issue template moved to the root `.github/` folder. `make check` at the root also runs this folder's checks.
- `make index` points the links in `llms.txt` and `llms-full.txt` at this folder, and the indexes were rebuilt.
- `AGENTS.md` and the README's licence line say "this folder" instead of "this repo", so they cover the same files
  as before.
- The shared scripts (`check_public.py`, `build_index.py`, `check_architecture.py` and `bootstrap-hosting.sh`) and
  the hooks in `agents/claude/hooks/` are unchanged, byte for byte.

## Renamed

The repository was later renamed to `ta-amps/teleionlabs-teleion-fabric`, so links, clone commands and workspace paths now use
that name directly. One docstring line in `check_architecture.py` now names where the schema lives; the copies in the
other repos changed the same way and stay byte-identical. See the [changelog](CHANGELOG.md).
