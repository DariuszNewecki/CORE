# CORE — What It Does

**Status:** Active
**Authority:** Northstar
**Scope:** System-level functional description
**Audience:** Governors, regulated-environment practitioners, new readers
**Last updated:** 2026-04-16

---

## The Problem

AI writes code. AI makes mistakes.

You cannot prevent the mistakes. A language model generating Python does not
know your architecture, does not know your constitutional boundaries, and does
not know what it broke last time. It will invent imports that violate layer
separation. It will generate plausible-looking code that contradicts your
existing design. It will do this confidently and repeatedly.

The standard response to this is better prompting, better models, or human
review of every line. None of these scale. Better prompting reduces mistakes
but does not eliminate them. Better models make different mistakes. Human
review of every AI-generated line defeats the purpose of using AI.

CORE takes a different position: **AI mistakes are not a quality problem.
They are a governance problem.**

The question is not "how do we make AI write better code?" The question is
"how do we detect, trace, and fix AI mistakes in a controlled loop — without
trusting the AI?"

---

## What CORE Does

CORE is a deterministic governance runtime that surrounds AI code generation.

It does not make AI smarter. It does not improve AI output quality directly.
It makes AI output **safe to use** by ensuring that every generated change
must pass constitutional governance, audit, and authorization before it
executes — and that every violation is detected, recorded, and resolved.

The constitutional principle at the core of everything:

> **CORE must never produce software it cannot defend.**

"Defend" means: every file change has a traceable cause, a known authorization,
and a recorded consequence. If you cannot explain why a line of code exists and
what rule permitted it to be written, CORE should not have written it.

---

## The Governor's Role

A person who uses CORE is not a programmer. They are a **governor**.

A governor does not write code. They do not debug. They do not read stack
traces or review diffs line by line. Their job is:

1. **Write intent.** Describe what the software should do, or stop doing,
   in constitutional terms. Rules, constraints, policies.

2. **Read signals.** Check the dashboard. Is the system converging toward
   a clean, compliant state? Does it need human judgment on something it
   cannot decide alone?

3. **Make decisions.** When CORE delegates — because a finding requires
   architectural judgment, or a proposal requires approval — the governor
   decides. Not the AI.

Everything else — finding violations, proposing fixes, executing approved
changes, verifying results — is CORE's job.

---

## What It Looks Like in Practice

**Today (A3 — partial autonomy):**

The governor checks the dashboard. The autonomous loop is running — seven
sensors scanning the codebase continuously, posting violations to the
Blackboard, proposing fixes, executing approved changes. The governor
handles what the loop cannot: approving proposals that require judgment,
reviewing delegation requests, amending the constitution when new rules
are needed.

There is still manual intervention at the edges. Not all violations have
automated remediation paths. Not all commands are fully working. The loop
is real but not yet complete.

**At full autonomy (A5):**

The governor checks the dashboard. All five panels are green. The loop
is running unattended. The codebase is converging continuously toward
constitutional compliance. When something genuinely requires human
judgment — a new architectural boundary, a constitutional amendment,
a delegation that requires a decision only a human can make — an item
appears in the Governor Inbox.

The governor's instrument panel is a single command:

```
core-admin runtime dashboard
```

Their steering wheel is the ConstitutionFactory: write new law, and the
system figures out how to enforce it.

---

## What CORE Is Not

CORE is not an AI agent. The AI is a component inside CORE — a code-producing
worker that is never trusted. Its output must pass ConservationGate,
IntentGuard, and Canary before anything executes. The AI does not govern
itself. CORE governs the AI.

CORE is not a framework or a library. It is a factory — a production line
with quality gates at every stage. The constitution is the factory law.
The workers are the production line. The governor is the supervisor.

CORE is not a prompt engineering system. Better prompts are not the answer
to AI unreliability. Deterministic governance is. The context build system
now emits constitutional layer constraints before any AI sees a target file —
not because prompting is important, but because the AI must know the law
before it can be held to it.

---

## Why This Matters for Regulated Environments

In regulated software development — pharma, medical devices, financial
systems — every change must be traceable, authorized, and defensible.
Manual review processes exist because no one trusts that the right rules
were followed without evidence.

CORE produces that evidence automatically. Every violation is detected by
a sensor, not a human. Every fix is proposed by the governance system, not
generated ad hoc. Every execution is authorized by rule, not by convention.
Every consequence is logged: which files changed, from which proposal,
authorized by which rule, resolving which finding.

This is not a side benefit. It is the architectural intent. CORE was
designed from the beginning to produce software that can be defended
in exactly the way regulated environments require.

---

## Where CORE Is Going

The autonomy roadmap has five phases. CORE is currently in Phase 3.

| Phase | What it means |
|-------|---------------|
| A1 | Single sensor + remediator loop proven |
| A2 | All sensors running, codebase converging |
| A3 | Capability gaps closed — delegation, test writing, full CLI health |
| A4 | CLI fully operational, requirements documented for every command |
| A5 | Dashboard green, governor steers by writing law |

Each phase represents more of the engine running without human hands on it.
The destination is a governor who wakes up, checks the dashboard, and either
goes about their day — or writes new constitutional law because the system
has earned the autonomy to enforce it.

---

## The Single Sentence

> A governor steers a software system by writing constitutional intent and
> reading convergence signals. They do not write code. They govern.
