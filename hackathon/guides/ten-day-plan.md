# A ten-day plan

A schedule template for Oct 26 to Nov 4, 2026. Copy it into your repo and change the work, not the gates.
Dates and the deadline come from [event/02-key-dates.md](../event/02-key-dates.md): submissions close
**Nov 4, 9:00 PM ET (Nov 5, 02:00 UTC)**, and US clocks fall back on Nov 1, so ET is UTC−5 from then on.
Aim to submit by midday Nov 4.

## Gates

| Gate | By | Passes when |
|---|---|---|
| G1 Skeleton | Oct 27 | One request goes end to end (interface, API, one model call) on your machine, and CI runs your checks |
| G2 Core | Oct 30 | The main flow works on real-looking made-up data and every task's `done_when` check passes |
| G3 Frozen | Oct 31 | Evaluation data frozen and hashed; nothing after this changes it |
| G4 Hosted | Nov 1 | The demo runs at a public address ([hosting.md](hosting.md)) and from an offline build |
| G5 Numbers | Nov 2 | Every number in the write-up comes from a script you can rerun; deploys freeze in the evening |
| G6 Recorded | Nov 3 | Demo video recorded and checked against [the checklist](../templates/demo-video-checklist.md) |
| G7 Submitted | Nov 4 midday | Form filled from [the description template](../templates/submission-description.md); repo frozen |

## Day by day

| Day | Date | Work |
|---|---|---|
| 1 | Mon Oct 26 | Read the rules and the [compliance checklist](compliance-checklist.md). Pick track and problem. Repos with agent rules, a guard hook, a secret scan and CI ([agent-workflow.md](agent-workflow.md)) |
| 2 | Tue Oct 27 | Walking skeleton (G1). Write the briefs for the core tasks with their `done_when` checks |
| 3 | Wed Oct 28 | Core build in atomic tasks; agents in parallel on separate worktrees |
| 4 | Thu Oct 29 | Core build; a fresh clone runs the quick start every evening |
| 5 | Fri Oct 30 | Finish the core (G2). Write the review docs ([reviewable-repo.md](reviewable-repo.md)) |
| 6 | Sat Oct 31 | Freeze evaluation data (G3). Local-first hosting, then hosted |
| 7 | Sun Nov 1 | Clocks change. Hosted demo and offline build (G4); evaluation runs |
| 8 | Mon Nov 2 | Numbers from scripts (G5); demo script; deploy freeze at night |
| 9 | Tue Nov 3 | Record the video (G6); write-up; someone else tries a fresh clone; decide which repo goes in the form |
| 10 | Wed Nov 4 | Submit by midday ET (G7). Don't change the repo after the deadline: that marks the project late |

## Rules of thumb

- Cut scope at each gate rather than slipping the gate.
- Keep one known-good build you could demo at any moment.
- Workshops run Oct 27 to Nov 4 ([event/15-schedule-and-workshops.md](../event/15-schedule-and-workshops.md));
  put the ones you need into the plan on day 1.
- Claim credits early and set spend alerts ([event/10-credits.md](../event/10-credits.md)).
