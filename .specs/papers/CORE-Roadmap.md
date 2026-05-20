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

---

## 2. Current State

As of May 2026:

- **22 features shipping** — full Solo reference implementation active
- **2 features partial** — F-05 (rule library), F-27 (local LLM)
- **19 features on roadmap** — distributed across Audit, Solo, Team,
  Enterprise, and Embedded tiers

The shipping baseline is the Solo tier minus F-05 and F-27 at full completion.
Every roadmap item below is net-new capability.

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

Two features are partial in the current Solo implementation. Neither blocks
the core governance loop; both improve coverage and resilience.

---

**F-05 — Default rule library** `partial` `source-code instantiation`
*Blocked by: nothing. Parallel with F-27.*

121 rules active. Expanding to full coverage of the source-code governance
surface. Completion is ongoing work, not a discrete milestone.

---

**F-27 — Local LLM support** `partial` `primitive`
*Blocked by: nothing. Parallel with F-05. Required before F-38.*

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

Stable, versioned API for third-party platform integration. Requires the
atomic action registry to be stabilised as a public contract, the FastAPI
layer to be load-bearing, and the constitution schema to be versioned for
external authors. This is the distribution multiplier — built last, after
the product is stable enough to make integrations reliable.

---

## 4. Dependency Graph (summary)

```
F-10  (Audit gate)
  └── no dependencies

F-05  (rule library completion)   — parallel
F-27  (local LLM completion)      — parallel
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

---

*This document reflects roadmap state as of May 2026. Update when feature
status changes. Feature definitions are authoritative in
`.specs/papers/CORE-Features.md`; this document governs sequence only.*
