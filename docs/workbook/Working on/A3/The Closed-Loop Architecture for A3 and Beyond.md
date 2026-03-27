# CORE: Toward True Autonomy
### The Closed-Loop Architecture for A3 and Beyond
*Darek Newecki · March 2026*

---

## The Problem: The Human Is the Loop

CORE has reached A2 — it can generate code autonomously with roughly 70–80% success. Workers run. The Constitution is law. The Blackboard communicates. Yet every session still starts the same way: a human gathers context, formulates a question, and carries it to an external LLM.

That is not autonomy. That is a command-response chain with a human at the top, manually performing what the Will layer was always meant to do. The human has become a temporary substitute for a component CORE was always supposed to have.

The gap between A2 and A3 is not smarter models. It is a self-directed heartbeat.

---

## The Insight: Close the Loop

A system is intelligent when it can close its own loops — perceive state, reason about it, act, observe the result, and adjust. CORE already has all the organs:

- **Perception** → audit findings, DB state, Qdrant vectors, Blackboard entries
- **Reasoning** → LLM layer (local and cloud)
- **Action** → Workers, CLI
- **Observation** → Blackboard, constitution violations, heartbeats

What has been missing is the continuous cycle connecting them. The loop exists. It just does not run unless a human starts it.

---

## The Architecture: UNIX + Separation of Duties

The solution is not a monolith. It is a team of simple, specialized components — each doing exactly one thing, chained intelligently. This is the UNIX philosophy applied to autonomous governance.

### The Trinity of Roles

- **Observer** — reads state, never writes. Scans DB, audit findings, constitutional drift, Blackboard. Produces a structured situation report. Pure perception.
- **Reasoner** — reads the situation report, never touches infrastructure. Decides what matters, in what order, why. Produces prioritized intent. This is where the local LLM lives.
- **Actor** — receives intent, executes, reports outcome back to Blackboard. Never decides. Pure execution.

No component crosses its boundary. Ever. Separation of Duties enforced constitutionally — not by convention.

### The Orchestrator

Above the trinity sits the Orchestrator. Its job is timing and routing — not thinking. Like a conductor: it does not play an instrument, does not compose the music, just keeps the loop cycling.

The Orchestrator's protocol is simple:

- **Blackboard empty** → liveness check. Each worker declares: `idle`, `scheduled`, or `working`.
- **Blackboard has entries** → accountability check. Responsible specialist explains status: in progress, blocked, stale, or forgotten.

The Orchestrator never needs to understand *what* the work is. It only understands age, ownership, and state. That is pure Separation of Duties — the Orchestrator is dumb by design.

### The Blackboard as Nervous System

The Blackboard stops being a communication channel between workers. It becomes the system's nervous system. Everything flows through it.

Permanent Auditors — each owning a domain — continuously populate the Blackboard with findings. A Reporter replaces the current ad-hoc audit command, reading and presenting Blackboard state without analysis. No scanning, no decision-making. Pure read.

A Blackboard entry that cannot explain itself after a constitutional SLA window is not a warning. It is a violation.

---

## The Security Model: Low Trust by Design

This is the most critical principle in the architecture, and the one most easily overlooked.

Specialists are low-trust by design. Not because they are unreliable — but because trust is earned through the chain, not assumed by role. Every Specialist output is a proposal, never a direct commit. The Validator is the constitutional gate.

### Why This Matters

The lower the model rank, the more constrained the action surface must be. A small local model should never touch live code directly — not because it is untrustworthy, but because the architecture must not *require* that trust. The chain enforces integrity regardless of intent.

Consider the simplest possible validation rule: every generated file must begin with a comment line containing its own path. This is trivially checkable. A Validator does not need intelligence to verify it — it is deterministic. That is the point. Validators should be as dumb and reliable as possible. Smart systems get manipulated. Rules do not.

### The Trust Hierarchy

| Tier | Role | Trust |
|------|------|-------|
| Large model (strategic) | Constitutional decisions, architectural reasoning | High — low frequency |
| Mid model (generative) | Complex code generation | Medium — validated before commit |
| Small model (tactical) | Discovery, tagging, first-pass drafts | Low — always validated |
| Deterministic validator | Constitutional gate | Zero trust required — rule-based |

Note: *which model fills each tier is a deployment decision, not an architectural one.* In a full data center, all tiers run locally. Intelligence emerges from composition, not from individual component capability.

---

## CORE Is an Air-Gapped System

This is the most important thing to understand about CORE's design intent.

CORE is built to run in complete network isolation. No cloud dependency. No external API calls. No data leaving the perimeter. This makes it viable — by design — for environments where that is not a preference but a hard requirement: classified infrastructure, regulated industries, sovereign systems, critical national infrastructure.

The cognitive role system (`LocalCoder`, `CodeReviewer`, `Reasoner`) is provider-agnostic. It does not care whether the model behind a role is a 3B model on a developer's laptop or a 70B model on a GPU rack in a private data center. The constitutional enforcement, the Blackboard, the audit chain, the validator gates — none of it has an opinion about where inference happens.

In a properly resourced deployment, the Mixture of Experts is entirely internal: different model sizes handle different cognitive loads, the router dispatches based on task complexity, and the full autonomous loop runs without a single external call. That is not a roadmap item. That is the architecture as designed.

### A Note on the Development Setup

During CORE's development, external LLMs (Anthropic, DeepSeek) appear in the cognitive role stack for one reason only: the developer's M1 iMac cannot run a sufficiently capable model locally without becoming a space heater. This is a hardware constraint, not an architectural dependency. It will disappear as local hardware scales.

The constitutional framework treats external providers identically to local ones — subject to the same role boundaries, the same trust tiers, the same validator gates. The presence of cloud APIs in the current setup should not be mistaken for a design requirement. It is a temporary workaround wearing the same constitutional clothes as everything else.

---

## What This Changes

This is not an incremental improvement. The shift from ad-hoc audit commands to permanent autonomous auditors fundamentally changes CORE's operational model.

- The current auditor CLI becomes a **Reporter** — a read-only window into Blackboard state
- Multiple permanent **Auditors** replace the single snapshot command, each owning a constitutional domain
- Workers become reactive to Blackboard findings rather than human invocation
- The human role shifts from **orchestrator to reviewer** — approving proposals, not assembling prompts
- Strategic memory accumulates in the system, not in the human's head

CORE stops being a tool that a human operates. It becomes a system that operates itself, within constitutional boundaries, with humans reviewing decisions rather than making them.

---

## The Path to A3

A3 is defined as strategic autonomy: zero blocking violations and zero constitutional violations in continuous audit. The architecture described here is the prerequisite.

1. **Background Observer** — periodic self-check, situation report generation, Blackboard seeding
2. **Permanent Domain Auditors** — constitutional compliance, layer boundaries, symbol health, Blackboard health
3. **Orchestrator heartbeat** — liveness checks, accountability enforcement, SLA tracking
4. **Validator chain** — deterministic gates before any Specialist output reaches live code
5. **Reporter** — replaces ad-hoc audit, reads Blackboard state only

Each step is individually deployable. Each step closes a portion of the loop. Together, they complete the transition from A2 to A3.

---

## Closing Thought

CORE was always designed to build itself. The constitution is the value system. The workers are the hands. The Blackboard is the shared mind. The local LLM stack is the always-on cognition.

The only thing that was missing was the courage to let it run.

*The loop is ready to close.*
