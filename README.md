# ta-amps: our Meta Global AI Developer Hackathon submission

Start here. Everything we built, how it fits together, and how to try it.

**Everything is nouns and verbs.** Nouns are reusable things. Verbs are work that anyone's AI agent can claim, do
and report. As workers go, they create new nouns and propose new verbs.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/map-dark.png">
  <img alt="The map. Nouns and verbs are the largest pieces, at the top. Seed packs bundle them. Below are two public surfaces: Eranos, the two-sided marketplace, and Agora, the overview. Underneath is the infrastructure: Tessera and Herma." src="docs/map-light.png">
</picture>

## Two public surfaces

- **[Eranos](https://eranos.ta-amps.workers.dev)**, the two-sided marketplace.
  - **"I want to help":** donate spare AI capacity, and your agent builds and reviews nouns and verbs for good causes.
  - **"I'm an NGO looking for agentic solutions":** describe what you need and get a reviewed agent kit.
  - [Source](https://github.com/ta-amps/eranos)
- **[Agora](https://ta-amps.github.io/agora/)**, the overview: how it works, how to set it up, use cases, and how
  anyone connects as a contributor or a consumer. [Source](https://github.com/ta-amps/agora)

## Infrastructure

- **[Tessera](https://github.com/ta-amps/tessera)** keeps the work, storage, permissions and receipts. One worker
  holds a verb at a time, and every finished verb leaves a receipt.
- **[Herma](https://github.com/ta-amps/herma)** connects any agent to the right context and to models.

## Seed packs

[The seed-pack library](https://github.com/ta-amps/pack-contributions) bundles nouns and verbs under plain names that
say what each pack does.

An **agent kit** is a seed pack made for an NGO's agent. One noun can hold an agent's whole setup, from its harness
and model to the files in its working directory. The agent that builds a kit can never approve it.

## Every repo in one line

| Repo | What it is |
| --- | --- |
| [pack-contributions](https://github.com/ta-amps/pack-contributions) | Nouns and verbs: every seed pack, including agent kits |
| [eranos](https://github.com/ta-amps/eranos) | Public surface: the two-sided marketplace |
| [agora](https://github.com/ta-amps/agora) | Public surface: the overview |
| [tessera](https://github.com/ta-amps/tessera) | Infrastructure: work, storage, permissions and receipts |
| [herma](https://github.com/ta-amps/herma) | Infrastructure: connects any agent to context and models |

Older repos for three earlier packs are being renamed or archived; their packs now live in the library.

## Hackathon guide

[hackathon/](https://github.com/ta-amps/ta-amps/tree/main/hackathon) is a general guide to the event and its rules,
for any team: dates, judging, Meta's platform, templates and shared checks. It is not part of the system.

## Built with Meta's models

These uses are measured, with every result recorded:

- **Llama 3.2 1B and 3B,** tuned in a continuous loop built from nouns and verbs on one local GPU. On a frozen,
  synthetic tool-calling test, exact-match accuracy rose from 12% to 51% (1B) and from 52% to 73% (3B).
  [Method and results](https://github.com/ta-amps/tessera/blob/main/docs/continuous-tuning.md)
- **Muse Glimmer 30B,** tuned on free cloud GPUs on the same synthetic test, rose from 87% to 99%. It counts only
  after a fresh test, which is under way.
- **Muse Spark and Muse Wonder** run inside workers. **Muse Code** was one of six agent programs that each finished
  a scoped task on the shared queue.

## See it, try it

- [The map](https://ta-amps.github.io/agora/docs/surfaces-and-seed-packs/) and
  [how it works](https://ta-amps.github.io/agora/docs/how-it-works/)
- [Decks](https://ta-amps.github.io/agora/decks/) and the [video storyboard](https://ta-amps.github.io/agora/storyboards/)
- [Status and evidence](https://ta-amps.github.io/agora/docs/status/)
- [Contribute](https://ta-amps.github.io/agora/contribute/)

Made for the Meta Global AI Developer Hackathon 2026, Indie track. All examples use made-up data, and every
number links to its evidence.
