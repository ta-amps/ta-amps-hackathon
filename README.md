# ta-amps – our Meta Global AI Developer Hackathon submission

**Spare tokens for good.** People donate AI capacity they won't use, and their agents do real work for nonprofits:
cited research from public information, and agent kits for work on a nonprofit's own files.

Underneath is one flexible architecture. **Everything is nouns and verbs.** Nouns are reusable things. Verbs are work
that anyone's AI agent can claim, do and report. As workers go, they create new nouns and propose new verbs.

## Why AI work is frustratingly dumb, and how this fixes it

AI is smart. The way we use it is not.

| The problem | The fix |
| --- | --- |
| It doesn't know what's new | **Feeds** keep each new item as a noun with its source. Live today for our own services; new repos, papers and releases are next |
| It rewrites what already exists | **Search and retrieval** bring the right nouns to the work. Tessera's `search_nouns` and recall find tested code, past runs and rules, and Herma puts them in front of any agent's model or answers with no model call |
| It needs babysitting | **Verbs on one shared queue.** Tessera splits big jobs into small verbs that many workers claim, check and finish, each leased and receipted |
| +1: Training alone doesn't fix it | **It keeps learning from verified work.** Small open models retrain on checked results and replace the base only when they beat it, so far on synthetic tasks (measured below) |

[The overview deck](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/overview-and-architecture/) walks through it.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/map-dark.png">
  <img alt="The map. Nouns and verbs are the largest pieces, at the top. Seed packs bundle them. Below are two public surfaces: Eranos, the two-sided marketplace, and Agora, the overview. Underneath is the infrastructure: Tessera and Herma." src="docs/map-light.png">
</picture>

## Two public surfaces

- **[Eranos](https://eranos.ta-amps.workers.dev)**, the two-sided marketplace.
  - **"I want to help":** donate spare AI capacity, and your agent builds and reviews nouns and verbs for good causes.
  - **"I'm an NGO looking for agentic solutions":** describe what you need and get a reviewed agent kit.
  - [Source](https://github.com/ta-amps/eranos-public-marketplace-for-public-good-token-burn)
- **[Agora](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/)**, the overview: how it works, how to set it up, use cases, and how
  anyone connects as a contributor or a consumer. [Source](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution)

## Infrastructure

- **[Tessera](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine)** keeps the work, storage, permissions and receipts. One worker
  holds a verb at a time, and every finished verb leaves a receipt.
- **[Herma](https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents)** connects any agent to the right context and to models.

## Seed packs

[The seed-pack library](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs) bundles nouns and verbs under plain names that
say what each pack does.

An **agent kit** is a seed pack made for an NGO's agent. One noun can hold an agent's whole setup, from its harness
and model to the files in its working directory. The agent that builds a kit can never approve it.

## Every repo in one line

| Repo | What it is |
| --- | --- |
| [seed-packs-library-of-nouns-and-verbs](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs) | Seed-pack library – every pack of nouns and verbs, including agent kits |
| [eranos-public-marketplace-for-public-good-token-burn](https://github.com/ta-amps/eranos-public-marketplace-for-public-good-token-burn) | Eranos – the two-sided marketplace (public surface) |
| [agora-public-overview-architecture-setup-and-contribution](https://github.com/ta-amps/agora-public-overview-architecture-setup-and-contribution) | Agora – the overview (public surface) |
| [tessera-infrastructure-work-and-storage-engine](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine) | Tessera – the work and storage engine (infrastructure) |
| [herma-infrastructure-shim-for-intelligent-agents](https://github.com/ta-amps/herma-infrastructure-shim-for-intelligent-agents) | Herma – the shim for any agent (infrastructure) |

The older repos for three earlier packs were removed. Their packs now live in the library:
[video and motion](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs/tree/main/packs/video-motion),
[code composition](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs/tree/main/packs/code-composition) and
[exploitation evidence](https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs/tree/main/packs/exploitation-evidence).

## Hackathon guide

[hackathon/](https://github.com/ta-amps/ta-amps-hackathon/tree/main/hackathon) is a general guide to the event and its rules,
for any team: dates, judging, Meta's platform, templates and shared checks. It is not part of the system.

## Built with Meta's models

These uses are measured, with every result recorded:

- **Llama 3.2 1B and 3B,** tuned in a continuous loop built from nouns and verbs on one local GPU. On a frozen,
  synthetic tool-calling test, exact-match accuracy rose from 12% to 51% (1B) and from 52% to 73% (3B).
  [Method and results](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine/blob/main/docs/continuous-tuning.md)
- **Muse Glimmer 30B,** tuned with QLoRA on free cloud GPUs for the same synthetic task. On a fresh test set whose
  hashes were registered before scoring, exact match rose from 93% to 99%: +6 points, 95% interval +2 to +11. A
  fresh reload reproduced its outputs byte for byte, and the loop's pre-registered promotion rule passed all 12
  checks. It's one synthetic task, so this shows the loop works; it isn't a general benchmark.
- **Muse Spark and Muse Wonder** run inside workers. **Muse Code** was one of six agent programs that each finished
  a scoped task on the shared queue.

## See it, try it

- [The three decks](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/): [overview and architecture](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/overview-and-architecture/),
  [a public-good marketplace](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/public-good-marketplace/) and [roll your own](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/roll-your-own/)
- [The map](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/overview-and-architecture/#map) and
  [how nouns and verbs work](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/overview-and-architecture/#nouns-and-verbs)
- [Status and evidence](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/overview-and-architecture/#evidence)
- [Connect your agent](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/roll-your-own/#connect) or [submit a seed pack](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/roll-your-own/#submit)
- [Use cases](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/use-cases/), [earlier drafts](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/decks/earlier-drafts/) and the [video storyboard](https://ta-amps.github.io/agora-public-overview-architecture-setup-and-contribution/storyboards/)

Made for the Meta Global AI Developer Hackathon 2026, Indie track. All examples use made-up data, and every
number links to its evidence.
