---
kind: adr
id: ADR-068
title: ADR-068 — Principal Role Taxonomy
status: accepted
---

# ADR-068 — Principal Role Taxonomy

**Date:** 2026-05-22
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Closes:** Track 3 (role taxonomy sub-decision)
**Related:** ADR-015, ADR-053, ADR-061, Track 10

---

## Context

CORE's governance chain requires every approved proposal to carry two
fields: `approved_by` (who) and `approval_authority` (under what
authority). Both are non-omittable once a proposal transitions out of
DRAFT (ADR-015 D2/D6; DB CHECK constraint).

The `proposal_approval_authority` enum currently contains two values:

| Value | Meaning |
|---|---|
| `risk_classification.safe_auto_approval` | Autonomous self-promotion — no human involved |
| `human.cli_operator` | A human approved via `core-admin proposals approve` |

`human.cli_operator` is not a role. It is a surface label — it records
*how* the approval was submitted, not *who* had authority to submit it.
A GxP auditor reading `approved_by = "darek"` and
`approval_authority = "human.cli_operator"` cannot answer the question
that 21 CFR Part 11 §11.50 requires: what is the *meaning* of this
signature — under what authority was this person entitled to approve?

Note also that `proposal_approval_authority` is a proposal lifecycle
vocabulary — it records who may approve a proposal. Not all roles in the
principal taxonomy have proposal approval authority. `principal.auditor`
and `principal.operator` are read-only roles; they never appear as
`approval_authority` on a proposal. The role taxonomy and the
`proposal_approval_authority` enum are therefore two distinct
vocabularies that must not be conflated.

The same conflation appears in the governance documentation. Existing
Tier A papers use language attributing constitutional authority to the
founder by name ("only by me", "solely at my discretion"). This is
functionally equivalent to the `human.cli_operator` problem: it records
a person where a role should stand. The language is not just a tone
problem — it is a governance model problem. If the constitutional
authority belongs to a named individual rather than a declared role,
CORE cannot be deployed with a second governor, and no regulated
customer can treat its audit trail as institutionally credible rather
than personally credible.

The EU AI Act Article 17(1)(m) requires an explicit "accountability
framework setting out the responsibilities of the management and other
staff." CORE's role taxonomy is that accountability framework — both for
CORE's own governance and as a template that GxP customers can reference
when their own auditors ask for it.

This ADR defines CORE's principal role taxonomy, establishes the three
constitutional layers that govern all role reasoning, corrects the
`approval_authority` vocabulary, and makes the document language fix
derivable from a governance definition rather than a style preference.

---

## Decisions

### D1 — Three-layer separation is constitutional

All role-related governance in CORE is organized across exactly three
layers. These layers are kept strictly separate; no layer may absorb
the concerns of another.

**Layer 1 — Role taxonomy (constitutional).**
What roles exist and what authority each carries. Defined once in
`.intent/`. Immutable except by governor-authored amendment. No
implementation code may define or extend this taxonomy.

**Layer 2 — Principal-to-role binding (deployment).**
Which principals hold which roles in a given deployment. Managed at
deployment time; not part of the constitution. In a single-governor
local deployment, this binding is trivial: one principal holds the
Governor role. In a Team or Enterprise deployment, this layer is
managed by the operator via the API access-control surface (Track 3
implementation, deferred — see D4).

**Layer 3 — Action-to-role requirement (enforcement).**
Which actions require which role to authorize. Expressed as enforcement
rules in `.intent/`. The `approval_authority` vocabulary is the primary
enforcement surface at the proposal lifecycle.

The role taxonomy is permanently flat. Roles carry no inheritance and
no hierarchy. Resource scoping — where needed at Team tier or above —
is expressed as a scope constraint on the Layer 2 principal-to-role
binding, not as a structural property of the role. This distinction is
irrevocable: Layer 1 will never be extended with role hierarchy.

Rationale: this mirrors the NIST RBAC model (Core RBAC, ANSI/INCITS
359-2004). Roles are authority classes, not people. The separation
prevents the "founder-sovereignty" failure mode: a role can outlive any
individual principal who holds it, can be transferred, and can be
audited without reference to a specific person's identity.

Role hierarchy is explicitly rejected. Every system that has introduced
role inheritance in a regulated context has produced the same audit
failure: "who has permission to approve this?" becomes a transitive
closure computation rather than a table lookup. A GxP auditor cannot
answer it by inspection. Flat roles make permission attribution a
one-sentence answer. AWS IAM, Kubernetes RBAC, and every major GxP
platform (Veeva Vault, MasterControl) converge on this pattern for the
same reason.

---

### D2 — Role taxonomy: four declared roles

The following roles are declared as the CORE principal role taxonomy.
This is the authoritative set. No implementation code, enforcement rule,
or external document may reference a principal role not in this taxonomy.

| Role ID | Display name | Authority |
|---|---|---|
| `principal.governor` | Governor | Full constitutional authority. May approve or reject proposals, accept ADRs, authorize `.intent/` changes, and trigger any governed operation. There is at most one Governor per deployment at any given time (see D3). |
| `principal.operator` | Operator | Read all system state; trigger read-only operations (audit runs, inspect, coverage). Cannot approve proposals or authorize constitutional changes. |
| `principal.auditor` | Auditor | Read audit findings, consequence chain, and compliance evidence. No write access of any kind. This role exists specifically for the GxP QA archetype: an external auditor who must inspect the trail without being able to influence it. |
| `principal.system` | System Agent | Autonomous system actors (workers, daemons). Distinct from human principals. The `risk_classification.safe_auto_approval` authority continues to belong to this role class. |

**Intentional omissions:**

- No "Admin" role. Administrative actions (API key lifecycle, deployment
  configuration) are Governor-gated; a separate Admin role would
  duplicate the Governor's authority at lower conceptual weight.
- No role hierarchy (no inheritance). Hierarchical RBAC introduces
  implicit permission grants that are hard to audit. Explicit flat roles
  are preferred for a system whose primary value proposition is
  traceability.
- No per-resource role scoping, ever, at Layer 1. "Operator on project
  X only" is not a new role — it is `principal.operator` with a scope
  constraint on the Layer 2 binding. The constraint is a deployment
  configuration concern (Track 3 implementation); the role taxonomy does
  not change to accommodate it. This is permanent: resource-scoped roles
  will never be added to Layer 1 at any product tier.

---

### D3 — Separation of duties: the Governor/Auditor constraint

A principal holding `principal.governor` authority may not simultaneously
serve as `principal.auditor` for the same governance action. Specifically:

> A proposal that was approved by a Governor cannot have its
> audit-verification record signed by the same principal who approved it.

This constraint is structural, not procedural. In the current
single-governor deployment it is moot — there is only one principal and
the system is trusted — but it must be declared now so that:

1. The Team and Enterprise tiers do not inherit a structural SoD gap.
2. The GxP positioning claim ("every action is attributable and
   independently verifiable") is constitutionally true, not just
   aspirationally true.

Implementation of this constraint is deferred to the first multi-operator
deployment. The ADR records the constraint; enforcement is a Track 3
sub-decision.

---

### D4 — Single-governor local deployment posture

A deployment in which exactly one principal exists and the system binds
exclusively to localhost is a constitutionally recognized deployment
topology: **Single-Governor Local**.

In this topology:

- The Governor role exists and is the authority for all proposals.
- Authentication is deferred: no credential verification is required
  when the only access path is the local process boundary.
- The SoD constraint (D3) is noted but not enforced — a single-principal
  deployment cannot structurally satisfy it.
- All `approval_authority` records are stamped `principal.governor` (the
  role), not a surface label and not a person's name.

This posture must be declared in the deployment configuration. It is not
the default for any other topology. When a remote access path is opened
(any non-localhost binding), authentication becomes mandatory and the
Single-Governor Local posture is no longer valid regardless of the number
of principals.

Rationale: the demo use case and the Solo product tier are both
Single-Governor Local deployments. This posture must be constitutional
— not a gap in the governance model — so that the audit trail it
produces is credible.

---

### D5 — `proposal_approval_authority` vocabulary correction

The `human.cli_operator` value in `proposal_approval_authority`
(`.intent/META/enums.json`) is retired and replaced by
`principal.governor`.

| Old value | Replacement | Rationale |
|---|---|---|
| `human.cli_operator` | `principal.governor` | CLI is the surface; Governor is the role. The audit trail must record authority, not input channel. |
| `risk_classification.safe_auto_approval` | Unchanged | This value correctly identifies the authority class (the risk classifier) for autonomous approvals. It belongs to `principal.system`. |

**Migration:** existing `autonomous_proposals` rows carrying
`approval_authority = 'human.cli_operator'` are backfilled to
`principal.governor` in the same migration that updates the DB CHECK
constraint. This is a pure data rename; no semantic change.

The DB CHECK constraint on `approval_authority` is updated to the new
closed vocabulary. The `ProposalStateManager.approve()` call site in
`src/` is updated to pass `principal.governor`.

Implementation is deferred; no `src/` changes are made at ADR
acceptance. This sub-decision is tracked as the implementation gate.

---

### D6 — Constitutional document language

The "only by me" and founder-sovereignty language in any Tier A document
(ADR, architecture paper, governance spec) is hereby superseded by the
following canonical replacement for all contexts where it appears:

> "CORE constitutional artifacts are version-governed and may be amended
> only by a principal holding `principal.governor` authority, as defined
> in ADR-068."

This replacement is not a softening of the governance intent — it
restores the correct structure. The governor role carries the same
authority that the founder-name formulations intended; the difference
is that the role can be audited, transferred, and institutionally
recognized in a way that a personal name cannot.

Track 10 document remediation uses this replacement as its template.
No Track 10 remediation work is required before this ADR is accepted;
the replacement text exists from ADR acceptance forward.

---

## State at ADR acceptance

| Item | State |
|---|---|
| Role taxonomy declared | D2 — four roles defined |
| Three-layer model codified | D1 |
| SoD constraint recorded | D3 — enforcement deferred to Track 3 |
| Single-Governor Local posture defined | D4 |
| `human.cli_operator` retirement decision | D5 — implementation deferred |
| Document language replacement | D6 — template established |
| `.intent/` role artifact | **Not yet authored** — required implementation step |
| `enums.json` updated | **Not yet** — required implementation step |
| DB CHECK constraint updated | **Not yet** — required implementation step |
| `ProposalStateManager` call site updated | **Not yet** — required implementation step |

---

## Consequences

**Positive:**

- The approval trail now records role authority, satisfying 21 CFR Part
  11 §11.50 (meaning of signature) and ALCOA+ Attributable (who + under
  what authority).
- EU AI Act Article 17(1)(m) accountability framework exists as a
  constitutional artifact, not just an aspiration.
- "Only by me" language has a canonical replacement grounded in a
  governance definition. Track 10 becomes a mechanical substitution, not
  an editorial judgment call.
- The Governor role can be held by any qualified principal — CORE is no
  longer constitutionally single-person.
- The SoD constraint is on record before the multi-operator tier ships,
  preventing a structural gap from being inherited silently.

**Negative:**

- `human.cli_operator` is a breaking change to the
  `proposal_approval_authority` vocabulary. Any external tooling or
  reporting that pattern-matches on this string must be updated.
  Mitigation: the value has never been exposed in a public API
  (API surface was loopback-only at ADR-054 D3). The blast radius is
  internal.
- The SoD constraint (D3) cannot be enforced in the current deployment
  topology. It exists as a declared-but-unenforced constraint, which is
  a known governance debt category (precedent: ADR-066 PENDING entries).

---

## Verification

Deferred to implementation. At implementation, verification is:

1. `.intent/governance/principal_roles.yaml` exists and declares all
   four roles with their authority descriptions.
2. `enums.json` `proposal_approval_authority` closed set is
   `["risk_classification.safe_auto_approval", "principal.governor"]`.
   `human.cli_operator` is absent. `principal.operator`,
   `principal.auditor`, and `principal.system` are absent — those roles
   have no proposal approval authority and must not appear in this enum.
   The full role taxonomy is a separate `.intent/` artifact (D2).
3. DB CHECK constraint on `core.autonomous_proposals.approval_authority`
   reflects the new closed set.
4. `core-admin code audit` produces no findings related to
   `proposal_approval_authority` vocabulary drift.
5. All `autonomous_proposals` rows previously carrying
   `approval_authority = 'human.cli_operator'` now carry
   `approval_authority = 'principal.governor'`.
6. `ProposalStateManager.approve()` passes `principal.governor`, not
   the retired string.

---

## References

- ADR-015 — Consequence chain attribution; D2/D6 established
  `approval_authority` as non-omittable with DB CHECK constraint.
- ADR-053 D7 — Request-level attribution for GxP readiness;
  `requested_by` attribution is the API-layer analogue of this ADR's
  proposal-layer concern.
- Track 3 — Full auth model (API key lifecycle, RBAC enforcement, mTLS);
  this ADR is the constitutional prerequisite, not the full Track 3
  delivery.
- Track 10 — Documentation governance alignment; D6 of this ADR provides
  the replacement template for founder-sovereignty language.
- NIST RBAC Standard (ANSI/INCITS 359-2004) — three-layer role model;
  flat role set; SoD constraint formal definition.
- 21 CFR Part 11 §11.50 — electronic signature must indicate the meaning
  of the signature (review, approval, authorship).
- EU AI Act Article 17(1)(m) — accountability framework requirement.
- `.intent/META/enums.json` — `proposal_approval_authority` vocabulary
  (current: `human.cli_operator`, `risk_classification.safe_auto_approval`).
- `src/body/services/proposal/state_manager.py` — `ProposalStateManager.approve()`
  call site carrying the retired string.
