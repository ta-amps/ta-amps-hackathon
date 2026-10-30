# <Project>: architecture

*Say the same thing as architecture.json, in prose and diagrams. `python3 scripts/check_architecture.py --mermaid`
prints the component graph to start from.*

## Context

```mermaid
flowchart LR
  user["<who uses it>"] --> app["<this system>"]
  app --> dep["<what it depends on>"]
```

## Components

| Component | Path | Role | Depends on |
|---|---|---|---|

## Data and state

*Every store, what it holds, who owns it, how it changes (one transaction? an event log?).*

## Main flows

*One sequence diagram per important flow, including the failure path.*

## Invariants

*Generated from architecture.json by `python3 scripts/check_architecture.py --sync-docs`; `make check` fails
if the two differ.*

| Id | Always true | Checked by |
|---|---|---|

## Trust boundaries and security

*Where requests cross from less to more trusted, what is checked there, where secrets live.*

## Failure handling

*What happens when a worker dies, a call times out, a write races another, a dependency is down.*

## Deployment

*Local, temporary public, hosted. Ports, processes, volumes.*

## Layering rules

*Which modules may not import which, and why. Checked by import_rules in architecture.json.*
