# CORE — Company

> Private/commercial. Not governed, not published.
> Filled from project knowledge. Decision-only gaps are marked GOVERNOR.

## One-liner
CORE is a deterministic governance runtime that supervises AI code generation —
making AI's output detectable, traceable, and fixable — so software can be built
by *governing* AI rather than trusting it.

## The longer line (for a technical reader)
AI writes code now, but it is non-deterministic and untrustworthy by nature.
CORE treats the AI as a component, never as an authority: every AI output passes
through a constitution, a rules engine, an audit pipeline, and an authorization
layer before anything executes. Mistakes become detectable, attributable, and
repairable inside a controlled loop instead of slipping into production.

## Mission / north star
A person who is not a professional programmer can build complete, correct,
production-grade software by writing *intent* and *governing* AI — instead of
writing code by hand. CORE is the governance layer that makes delegating to AI
safe enough to mean it.

## Strategic commitment (2026-06-01)
CORE is being built as a **company**, not a project, not a consulting vehicle,
not a hobby. The destination is the open-core five-tier product line stamped in
`CORE-Features.md` (33 open / 15 commercial) and described in
`CORE-Product-Tiers.md` (Audit → Solo → Team → Enterprise → Embedded).

The bridge from today's solo-founder state to that destination is
**services-first**: revenue from regulated qualification engagements (Eve
persona — see `CORE-Customer-Personas.md`), hosted runtime for non-regulated
buyers (Sam / Priya personas), and governance authoring for early adopters.
Service revenue funds runway and brings the early-team conversations into
paid roles or equity in something already paying.

Commercial features (F-20, F-31–F-40) are roadmap, not pre-build commitments.
They get built when team capacity allows *and/or* when a paying buyer
specifically pulls one — not on speculation.

The **MIT license on the engine is the floor**, permanent for the open
feature set. Any future reciprocal-license consideration is forward-only and
only if/when the team decides it serves the mission, per the constitutional
note in `CORE-Features.md` §1.

This commitment closes two prior open questions:
- *Product company vs. OSS-with-edge vs. consulting vehicle?* → **Company,
  with open-source engine and a commercial product line as the named
  destination.**
- *First commercial SKU?* → **Service engagement** (qualification +
  governance authoring) is the first revenue. **Hosted runtime** is the
  natural second when a non-regulated buyer asks for it.

## What it is — and what it deliberately is not
- **Is:** a constitutionally-governed software factory. `.intent/` is the
  blueprint and law; AI plus workers are labor; the audit system is quality
  control; remediators are the repair station; the human is the supervisor.
- **Is not:** an agent framework, a copilot, or prompt engineering. CORE's
  design lineage is compilers, operating systems, distributed systems, static
  analysis, and safety-critical systems. AI is never the trusted core.

## Trust model (the thing that makes CORE different)
Trusted: the constitution (`.intent/`), the rules engine, the audit system, the
execution/authorization system. **Not trusted:** AI outputs, generated code,
plans. AI is verified and corrected, never relied upon.

## Origin
- Sole architect and governor: Dariusz Newecki. Holds the *why* (intent, north
  star); the system holds the *how*.
- Built in the open, papers-and-decisions-first: every significant choice is an
  append-only ADR (126 to date) backed by a governance paper before any code.

## Current status
- **Autonomy level A3** — all four gates (G1–G4) closed; released as **v2.5.0**.
- The system runs an autonomous loop: it detects its own constitutional
  violations, proposes fixes, gets them authorized, executes them, and attributes
  the full consequence chain (finding -> proposal -> approval -> execution ->
  file change -> new findings).
- Operating phase: **Band E** — outward-facing. The inward engineering is mature
  enough that the current frontier is presentation and adoption, not core
  mechanics.
- GOVERNOR: the honest "can anyone but you run it today?" answer — onboarding
  friction, install story, required infra (Postgres, vector store, an LLM
  endpoint). State it plainly here.

## Public footprint
- **Website:** core-governance.com — the compound-brand domain. The
  canonical commercial brand is **"CORE Governance"**; "CORE" remains
  the short form for technical / repository / CLI contexts. Persona,
  demo, and customer-facing material continues to use "CORE" until the
  first paying customer is signed (see trademark note in GOVERNOR
  decisions below), at which point all customer-facing material
  switches to "CORE Governance" on first mention per document.
- GitHub: github.com/DariuszNewecki/CORE (public)
- Dev.to: 22 articles (the long-form thesis lives here)
- X: @DNewecki

## GOVERNOR decisions still open

- **Legal entity / IP ownership.** Load-bearing before the early-team
  conversations turn into cofounder commitments — jurisdiction (Polish sp. z o.o.,
  EU equivalent, Delaware C-corp, UK Ltd., etc.) shapes IP assignment and equity
  mechanics. The entity needs to own the codebase and the brand before equity is
  granted in it. Resolve this *before* bringing cofounders in.

- **Trademark filing for "CORE Governance."** *Brand shape resolved
  2026-06-01 via existing domain ownership (core-governance.com).* The
  bare word "CORE" is **not registrable as a word mark** in the software
  category (generic English word; Intel famously holds "**INTEL CORE**"
  and "**CORE INSIDE**" but not "CORE" alone, exactly because trademark
  offices won't grant the bare word) and is not being pursued. The
  compound mark "**CORE Governance**" is registrable in software classes
  9 / 42 — descriptive prefix + qualifying noun, the same pattern Intel
  uses. Open question is **timing**: file the compound mark before the
  first signed customer contract carrying the brand. Until then, the
  audit trail of public use (GitHub, Dev.to, X, core-governance.com) is
  the common-law backstop. Internal/technical contexts continue to use
  "CORE" as the short form (repo name, CLI, code references); a paying
  customer trigger flips customer-facing material — `CORE-Customer-
  Personas.md`, `CORE-Demo-Narrative.md`, GTM surfaces — to "CORE
  Governance" on first mention per document. Recommended filing scope:
  **EUIPO + USPTO, classes 9 and 42**.

- *(Resolved 2026-06-01: company vs. OSS vs. consulting — see Strategic
  commitment above.)*
