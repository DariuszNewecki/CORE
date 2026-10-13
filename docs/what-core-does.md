---
kind: northstar
title: "CORE — What It Does"
status: canonical
---

# CORE — What It Does

**Status:** Active
**Authority:** Northstar
**Scope:** System-level functional description (CORE at completion)
**Audience:** Governors, regulated-environment practitioners, new readers

---

## The Problem

AI produces work. AI makes mistakes.

You cannot prevent the mistakes. A language model generating an artifact —
a Python file, a procedure, a compliance record — does not know your
architecture, does not know your constitutional boundaries, and does not know
what it broke last time. It will invent things that violate your rules. It will
produce plausible-looking output that contradicts your existing design. It will
do this confidently and repeatedly.

The standard response is better prompting, better models, or human review of
every line. None of these scale. Better prompting reduces mistakes but does not
eliminate them. Better models make different mistakes. Human review of every
AI-generated line defeats the purpose of using AI.

CORE takes a different position: **AI mistakes are not a quality problem.
They are a governance problem.**

The question is not "how do we make AI produce better work?" The question is
"how do we detect, trace, and fix AI mistakes in a controlled loop — without
trusting the AI?"

---

## What CORE Does

CORE is a deterministic governance runtime that surrounds AI production.

It does not make AI smarter. It does not improve AI output quality directly.
It makes AI output **safe to use** by ensuring that every generated change must
pass constitutional governance, audit, and authorization before it executes —
and that every violation is detected, recorded, and resolved.

What CORE governs is an **artifact** against an **intent**. The intent is the
prescriptive law — a constitution, a regulation, a requirements set. The
artifact is the thing that must conform — and **source code is the first
artifact type CORE governs end-to-end.** The same engine extends, by design, to
documentation, internal procedures, regulatory requirements, and compliance
records: the rules engine makes no assumption about artifact type. Code is where
CORE proved itself first, not the limit of what it governs.

The constitutional principle at the core of everything:

> **CORE must never produce work it cannot defend.**

"Defend" means: every change has a traceable cause, a known authorization, and a
recorded consequence. If you cannot explain why an artifact exists and what rule
permitted it to be produced, CORE should not have produced it.

---

## The Governor's Role

A person who uses CORE is not a programmer. They are a **governor**.

A governor does not do the work by hand. They do not write the code, author the
procedure, or assemble the evidence line by line. Their job is:

1. **Write intent.** Describe what the system should do, or stop doing, in
   constitutional terms — rules, constraints, policies. In a regulated domain,
   this includes naming the requirements that must be met.

2. **Read signals.** Check the dashboard. Is the system converging toward a
   clean, compliant state? Does it need human judgment on something it cannot
   decide alone?

3. **Make decisions.** When CORE delegates — because a finding requires
   judgment, or a proposal requires approval — the governor decides. Not the AI.

Everything else — finding violations, proposing fixes, executing approved
changes, verifying results — is CORE's job.

---

## What It Looks Like in Practice

CORE's first proving ground is its **own codebase** — the code artifact type,
governed to autonomy. This is the "final exam": if CORE can analyze itself,
model its own intent, detect its own contradictions, and refuse illegitimate
change, then its principles are real and portable to any other artifact type.

That autonomy is reached in stages. At full autonomy:

The governor checks the dashboard. The panels are green. The loop is running
unattended. The governed corpus is converging continuously toward constitutional
compliance. When something genuinely requires human judgment — a new boundary, a
constitutional amendment, a delegation only a human can make — an item appears in
the Governor Inbox.

The governor's instrument panel is a single command:

```
core-admin runtime dashboard
```

Their steering wheel is the ConstitutionFactory: write new law, and the system
figures out how to enforce it.

---

## What CORE Is Not

CORE is not an AI agent. The AI is a component inside CORE — an artifact-producing
worker that is never trusted. Its output must pass ConservationGate, IntentGuard,
and Canary before anything executes. The AI does not govern itself. CORE governs
the AI.

CORE is not a framework or a library. It is a factory — a production line with
quality gates at every stage. The constitution is the factory law. The workers
are the production line. The governor is the supervisor.

CORE is not a prompt engineering system. Better prompts are not the answer to AI
unreliability. Deterministic governance is. The context build system emits
constitutional constraints before any AI sees a target — not because prompting is
important, but because the AI must know the law before it can be held to it.

---

## Why This Matters for Regulated Environments

This is not a side benefit. It is the architectural intent.

In regulated work — pharma, medical devices, financial systems — every change
must be traceable, authorized, and defensible. Manual review processes exist
because no one trusts that the right rules were followed without evidence. The
same shape recurs whether the artifact is code or a standard operating procedure:
a body of work on one side, a body of law (regulation, policy) on the other, and
an obligation to prove the first conforms to the second.

CORE produces that proof automatically. Every violation is detected by a sensor,
not a human. Every fix is proposed by the governance system, not generated ad
hoc. Every execution is authorized by rule, not by convention. Every consequence
is logged: what changed, from which proposal, authorized by which rule, resolving
which finding. This is exactly the evidence trail a GxP-class auditor expects —
and it is the same trail whether the corpus under governance is a source tree or
a controlled library of records.

---

## Where CORE Is Going

CORE matures along two independent axes.

**Autonomy** — how much of the loop runs without human hands, proven first on the
code artifact type:

| Phase | What it means |
|-------|---------------|
| A1 | Single sensor + remediator loop proven |
| A2 | All sensors running, corpus converging |
| A3 | Capability gaps closed — delegation, test writing, full CLI health |
| A4 | CLI fully operational, requirements documented for every command |
| A5 | Dashboard green, governor steers by writing law |

**Reach** — how many artifact types the one engine governs. Code is instance #1,
governed end-to-end. The roadmap extends the same constitution-under-law loop to
non-code domains — internal procedures, regulatory gap analysis, compliance
records — each arriving as a new artifact type against the same engine, not a new
engine. The autonomy ladder is climbed once per domain; the law is one.

The destination is a governor who wakes up, checks the dashboard, and either goes
about their day — or writes new constitutional law, in whatever domain, because
the system has earned the autonomy to enforce it.

---

## The Single Sentence

> A governor steers a system by writing constitutional intent and reading
> convergence signals. They do not do the work. They govern — and the work, in
> any domain, must be defensible against the law before it stands.
