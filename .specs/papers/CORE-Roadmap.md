# CORE: Roadmap

**Document type:** Strategic reference
**Location:** `.specs/papers/CORE-Roadmap.md`
**Status:** Authoritative
**Author:** Dariusz Newecki
**Audience:** Internal — governance, commercial, investor
**Derived from:** `.specs/papers/CORE-Features.md`

---

## 1. Purpose

This document sequences CORE's unshipped features into a delivery order
governed by tier dependency and inter-feature dependency. It is the planning
surface for milestone and sprint decisions.

The feature registry (`CORE-Features.md`) is the vocabulary. This document
is the sequence. When a feature's status changes, update the registry first;
this document follows.

**Reading the roadmap:** Features within a tier are listed in recommended
build order — features that unblock others come first. Features that are
genuinely parallel within a tier are noted as such.

**Scope boundary.** This roadmap sequences *features* — registry entries, each
carrying an F-ID. CORE's internal capability and architecture milestones — the
A3 autonomy state, the API-as-governance-interface migration, and the
Constitutional Coherence Checker — are **not** features and are not sequenced
here. They appear in §2 only as the realized baseline the remaining feature
work builds on. Their canonical homes are `CORE-A3-plan.md`, the ADR ledger
(ADR-053 / ADR-054 / ADR-055), and ADR-067 respectively.

---

## 2. Current State

As of May 2026.

### Realized baseline

Since the previous roadmap revision, three internal milestones moved from plan
to fact. They are not features, but they define the floor every roadmap item
now builds on.

- **A3 governed autonomy achieved.** All four A3 gates are cleared and held:
  loop closure (G1), convergence (G2, closed 2026-05-12), consequence chain
  (G3, closed 2026-05-01), and governance-in-`.intent/` (G4, closed
  2026-05-10). The daemon finds, proposes, and fixes violations unattended;
  the human role is reviewer/governor. A3 is a state, not a feature — see
  `CORE-A3-plan.md`.

- **API as the single governed interface.** The CLI-to-HTTP migration
  (ADR-053) is live through its first two capability phases: `/audit` +
  `/proposals` (ADR-054) and `/fix` + `/quality` (ADR-055). The CLI is now a
  typed client over `api.*` rather than a direct caller of the engine. This is
  the load-bearing surface that F-34 (web dashboard) and F-40 (OEM API)
  require.

- **Constitutional Coherence Checker live.** A read-only instrument (ADR-067)
  that detects drift between the constitution and the codebase and surfaces
  triage candidates. It strengthens the evidentiary basis for F-37 (regulatory
  export) without itself being a tiered feature.

### Feature counts

Authoritative in `CORE-Features.md`:

- **23 features shipping** — full Solo reference implementation, including
  F-05 (default rule library), promoted from partial since the last revision.
- **1 feature partial** — F-27 (local LLM), opt-in via configuration.
- **19 features on roadmap** — distributed across Audit, Solo-completion,
  Team, Enterprise, and Embedded tiers.

The shipping baseline is the Solo tier minus F-27 completion. Every roadmap
item below is net-new capability.

---

## 3. Roadmap by Tier

### Tier 1 — Audit

The Audit tier has one unshipped feature. It is the entire delivery
mechanism for the tier — without it, Audit has no product.

---

**F-10 — CI/CD gate** `roadmap` `source-code instantiation`
*Blocked by: nothing. Blocks: nothing within Audit.*

Stateless audit packaged as a GitHub Action, GitLab CI step, and pre-commit
hook. This is the top-of-funnel entry point — the first thing a developer
encounters before they know what CORE is. Everything in the adoption funnel
depends on this existing.

**Build first.**

---

### Tier 2 — Solo (completions)

One feature remains partial in the Solo implementation. It does not block the
core governance loop; completing it improves deployment resilience and unlocks
the Enterprise air-gapped guarantee. (F-05 completed since the previous
revision and is now shipping; it no longer appears here.)

---

**F-27 — Local LLM support** `partial` `primitive`
*Blocked by: nothing. Required before F-38.*

Local model support exists but is opt-in via configuration. Completion means
making local execution a first-class deployment mode with documented model
requirements and fallback behaviour. Prerequisite for the guaranteed
air-gapped deployment at Enterprise (F-38).

---

### Tier 3 — Team

Five features. Two dependency chains:

- F-32 → F-31 (RBAC is the foundation for shared governance)
- F-20 → F-34 (convergence data before convergence UI)
- F-33 is independent

---

**F-32 — Role-based constitutional authority (RBAC)** `roadmap` `primitive`
*Blocked by: nothing. Blocks: F-31, F-35, F-36.*

Who can approve proposals. Who can amend `.intent/`. Enforced by the system,
not by convention. Foundation for every multi-user governance guarantee.
Build before anything else in Team — F-31 and the Enterprise identity
features (F-35, F-36) depend on it.

---

**F-31 — Shared consequence chain** `roadmap` `primitive`
*Blocked by: F-32. Blocks: nothing.*

All proposals, findings, and executions visible to every member of a shared
instance. Governance state becomes team-level. Requires RBAC to exist so
that visibility is governed, not open.

---

**F-33 — Multi-repository support** `roadmap` `primitive`
*Blocked by: nothing. Parallel with F-31 and F-32.*

Single CORE instance governing multiple repositories under a shared
Blackboard and worker pool. Each repository retains its own `.intent/`
constitution. No dependency on RBAC or shared consequence chain; can be
built in parallel.

---

**F-20 — Convergence graph dashboard** `roadmap` `primitive`
*Blocked by: nothing (data is already in the Blackboard). Blocks: F-34.*

The convergence metric (F-19) is shipping; the UI is not. Finding rate versus
resolution rate over time — the anchor KPI for Team adoption. Build before
the full web dashboard since the dashboard depends on this view existing.

---

**F-34 — Web dashboard** `roadmap` `primitive`
*Blocked by: F-20. Blocks: nothing.*

Browser-based governance interface: convergence graph, proposal queue, audit
history, worker health. Replaces CLI as the primary interface for governors
not working in a terminal. Depends on F-20 being the anchor view.

The HTTP service layer it renders over is now live (ADR-053 / ADR-054 /
ADR-055), so the remaining work is the browser interface itself, not the
underlying API. This lowers build risk; it does not change the F-20 → F-34
sequence.

---

### Tier 4 — Enterprise

Eight features across three dependency chains:

- F-32 (Team) → F-35 → F-37
- F-32 (Team) → F-36 → F-37
- F-27 (Solo completion) → F-38
- F-41 → F-42, F-43
- F-39 is commercial, no technical dependency

---

**F-35 — Federated constitution** `roadmap` `primitive`
*Blocked by: F-32. Blocks: F-37.*

Org-level root constitution that team-level constitutions inherit and cannot
override. The compliance floor for enterprise deployments. Requires RBAC
(F-32) to exist so that amendment authority at the org level is enforced.

---

**F-36 — SSO / SAML / OIDC** `roadmap` `primitive`
*Blocked by: F-32. Blocks: F-37.*

Enterprise identity integration. Role assignments bind to SSO identities.
Requires RBAC (F-32) to have a role model to bind to. Parallel with F-35.

---

**F-41 — Artifact type registry** `roadmap` `extension`
*Blocked by: nothing. Blocks: F-42, F-43.*

Declared model for registering governed artifact types beyond source code.
The enabling feature for non-code governance. Must exist before F-42 and F-43
can be built — they are its first consumers.

---

**F-42 — Pluggable sensor model** `roadmap` `extension`
*Blocked by: F-41. Blocks: nothing. Parallel with F-43.*

Abstract sensor interface making the audit loop extensible to non-code
artifact types. First consumer of F-41's artifact type registry.

---

**F-43 — Pluggable action model** `roadmap` `extension`
*Blocked by: F-41. Blocks: nothing. Parallel with F-42.*

Abstract action interface making the remediation loop extensible to non-code
artifact types. First consumer of F-41 alongside F-42.

---

**F-38 — Air-gapped deployment (guaranteed)** `roadmap` `primitive`
*Blocked by: F-27 (completion). Blocks: nothing.*

Local-only LLM with guaranteed network isolation. Builds on F-27's partial
local model support and promotes it from configuration option to
infrastructure guarantee. Required for defence, pharma, and financial
services deployments.

---

**F-37 — Regulatory export (GxP / EU AI Act)** `roadmap` `primitive`
*Blocked by: F-35, F-36. Blocks: nothing.*

Structured, signed export of the full consequence chain for regulatory
submission. The consequence chain data is already shipping (F-17); this
feature wraps it in a signed, timestamped, regulator-formatted package.
Requires federated constitution (F-35) and SSO (F-36) so that approvals
carry verified identity before submission.

Request-level identity attribution (ADR-053 D7) and the Constitutional
Coherence Checker (ADR-067) further strengthen the export's evidentiary
basis: attribution makes each approval traceable to an identity, and the
Coherence Checker provides a standing record that the constitution and the
governed codebase have not drifted apart. Neither is a prerequisite F-ID; both
raise the defensibility of the eventual export.

---

**F-39 — SLA support** `roadmap` `primitive`
*Blocked by: nothing technical. Parallel with all Enterprise features.*

Contractual support SLA. A commercial and operational commitment, not a
software feature. Can be established as soon as the Enterprise tier has
enough implemented features to support it.

---

### Tier 5 — Embedded

One feature. Depends on Team and Enterprise reaching sufficient maturity.

---

**F-40 — OEM API surface** `roadmap` `primitive`
*Blocked by: Team and Enterprise tier maturity. No specific F-ID dependency.*

Stable, versioned API for third-party platform integration. The FastAPI layer
is now load-bearing following the API migration (ADR-053 / ADR-054 / ADR-055),
which removes one prior prerequisite. The remaining prerequisites are
stabilising the atomic action registry as a public contract and versioning the
constitution schema for external authors. This is the distribution multiplier —
built last, after the product is stable enough to make integrations reliable.

---

## 4. Dependency Graph (summary)

```
F-10  (Audit gate)
  └── no dependencies

F-27  (local LLM completion)
  └── F-38  (air-gapped guaranteed)

F-32  (RBAC)
  ├── F-31  (shared consequence chain)
  ├── F-35  (federated constitution)
  │     └── F-37  (regulatory export)
  └── F-36  (SSO / SAML / OIDC)
        └── F-37  (regulatory export)

F-33  (multi-repository)          — independent
F-20  (convergence graph)
  └── F-34  (web dashboard)

F-41  (artifact type registry)
  ├── F-42  (pluggable sensor)
  └── F-43  (pluggable action)

F-39  (SLA support)               — commercial, parallel
F-40  (OEM API surface)           — follows tier maturity
```

---

## 5. Sequencing Principles

**F-10 before anything else.** Without the CI gate, the Audit tier has no
delivery mechanism and the adoption funnel has no entry point.

**F-32 before F-31, F-35, F-36.** RBAC is the foundation of every
multi-user governance guarantee. Building shared governance without role
enforcement produces a governance system that cannot be trusted.

**F-41 before F-42 and F-43.** The extension features are consumers of the
artifact type registry. Building them without the registry produces
point solutions, not an extensible platform.

**F-37 last among Enterprise features.** Regulatory export depends on
verified identity (F-36) and federated authority (F-35). Producing a
compliance package without those guarantees in place is not defensible.

**F-40 follows tier maturity, not a specific feature.** The OEM API surface
is only valuable when the product is stable enough to make integrations
reliable. Building it early produces an unstable contract.

**The API foundation is in place.** F-34 and F-40 previously carried an
implicit dependency on a load-bearing HTTP interface. That interface now
exists (ADR-053 / ADR-054 / ADR-055). Their remaining work is interface and
contract surface, not service-layer construction — this lowers their build
risk but does not change their position in the sequence.

---

*This document reflects roadmap state as of May 2026, following the A3
milestone, the API-as-governance-interface migration (ADR-053), and the
Constitutional Coherence Checker (ADR-067). Update when feature status changes.
Feature definitions are authoritative in `.specs/papers/CORE-Features.md`; this
document governs sequence only.*
