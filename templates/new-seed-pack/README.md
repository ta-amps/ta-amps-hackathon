# Template 1: Create a New Seed Pack in 60 Seconds

A **Seed Pack** is a portable folder of **task objects (`nouns.json`)** and **tasks (things to do) (`verbs.json`)** plus a **`manifest.json`**. Starter packs begin at `status: "proposal_only"` until reviewed and admitted into the [`seed-packs-library-of-nouns-and-verbs`](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs) repository.

## Files in This Starter Folder

- [`manifest.json`](manifest.json) -- pack slug (`pack_id`), `proposal_only` status, and explicit inventory of task objects and tasks (things to do).
- [`nouns.json`](nouns.json) -- reusable **task objects**, including the required pack descriptor (`"A collection of nouns and verbs for ..."`), a public data source, and a context-shim guardrail.
- [`verbs.json`](verbs.json) -- schedulable **Tasks** (`verb.probe_source`, `verb.solve_draft`, `verb.verify_gate`) with network effect ceilings (`none`, `local_only`, `read_only`, `scoped_write`) and `require_distinct_verifier: true`.

## Copy, Customize, and Verify Offline

```bash
# 1. Copy this template to a new pack folder
cp -R templates/new-seed-pack /tmp/my-custom-pack

# 2. Validate schema, effect ceilings, em-dash rules, and SHA-256 digests offline
python3 -m sandbox.verify_pack /tmp/my-custom-pack

# 3. Run an end-to-end local worker lease + independent verification smoke test
python3 -m sandbox.worker_smoke --pack /tmp/my-custom-pack
```

See [`../../sandbox/README.md`](../../sandbox/README.md) for the local developer sandbox details.
