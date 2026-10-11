---
kind: adr
id: ADR-068
title: ADR-068 — Principal Role Taxonomy
status: accepted
---

# ADR-068 — Principal Role Taxonomy

**Date:** 2026-05-22
**Governing paper:** `.specs/papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md`
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

## Note 2026-10-10 — CCC run 6558a043, structural triage (proposal 0012)

Reference correction (append-only; the text above is unchanged): the taxonomy is `.intent/taxonomies/principal_roles.yaml`; `.intent/governance/principal_roles.yaml` never existed.

## Amendment 2026-10-11 — operation modes, the producer role, and who may do what

**Proposed by:** Claude (core-claude), proposal 0023. **Rests on:** the governor's ruling of 2026-10-11 (three
operation modes, option A: "single user for adopters and RBAC for Platform", with a separated mode between them);
ADR-132 D10.1, D10.2, D10.9, D10.10; ADR-170 D2, D6; ADR-168 (producers); #942.

### A1 — "Local" no longer means "trusted" (D4 superseded)

D4's Single-Governor Local posture assumed that whoever reaches CORE on this machine is the governor. That stopped
being true when AI assistants began working on the same machine: an assistant, the governor's own model session and
CORE's services can all act locally (#942). D4 is replaced by the operation modes below. A record stamped
`principal.governor` must say which mode stood behind it (A6).

### A2 — Three operation modes

The role set (D2, plus A3) is the same in every mode. A mode decides how principals are bound to roles (Layer 2)
and therefore what CORE may honestly claim.

| Mode | For | How principals are bound | CORE's claim |
|---|---|---|---|
| `solo` | an adopter: one OS account, human and assistant indistinguishable to the system | none: every local actor may be the assistant | **detects, does not prevent.** Governor acts need a human-typed confirmation and leave a record; CORE says plainly that the assistant could have made them |
| `solo-separated` | CORE's own server, and any adopter who sets it up | one OS account per role or mechanism (A4); the binding file of ADR-132 D10.2, root-owned, outside the repository | **prevents**, for each act in A5 whose mechanism is live; an act whose mechanism is not live is reported as such |
| `platform` | teams, through core-platform | identities and roles from the platform; D3's separation of duties enforced | prevents, and separates duties. Built **on** a `solo-separated` host, never instead of one |

The default for an adopter is `solo`. A mode never changes silently: a deployment declared `solo-separated` whose
machine does not match is a finding (A6), not a quiet fall-back to `solo`.

### A3 — A fifth role: `principal.producer`

| Role ID | Display name | Authority |
|---|---|---|
| `principal.producer` | Producer | Produces changes — code, tests, drafts of law — and submits them as proposals (ADR-168). Writes only its own working tree and proposals. Never approves a proposal, never writes governed text, never deploys, never holds a production credential. AI assistants, including the governor's own model session, are producers. |

The role stays flat (D1). `proposal_approval_authority` does not gain it (D5).

**Mechanism accounts are not principals.** `core-law`, `core-build` and `core-sandbox` hold no authority of their
own. Each acts only on someone else's act: `core-law` on the governor's sudo approval (ADR-170), `core-build` and
root on the governor's deploy (ADR-132 D10.8), `core-sandbox` on a job from the services (ADR-132 D10.10).

### A4 — Accounts in `solo-separated` (CORE's own server)

| Account | Role or mechanism | Must never |
|---|---|---|
| the governor's human account (proposed `darek`) | `principal.governor` — the only account bound to it (ADR-132 D10.9) | be used by a model session |
| `core-darek` | `principal.producer` — the governor's model session | approve anything; hold sudo or any root-equivalent group |
| `core-claude` | `principal.producer` — the coding assistant | write governed text, deploy, or read production credentials |
| `core` | `principal.system` — daemon, workers, API | write governed text; run repository code outside the sandbox |
| `core-law` | mechanism: the law's custodian (ADR-170) | run git or repository code; act without the governor's password |
| `core-build` | mechanism: release builds (ADR-132 D10.8) | read `/opt/core/etc` or any credential |
| `core-sandbox` | mechanism: runs repository code (ADR-132 D10.10) | hold a credential, reach the network or write outside its scratch |
| `root` | break-glass, used only by the governor through sudo | change governed text without a following proposal (ADR-170 D6) |

### A5 — Which act needs which role (Layer 3)

| Act | Who | How it is enforced in `solo-separated` |
|---|---|---|
| Approve a code proposal | governor | the kernel identity of the caller, bound to `principal.governor` (ADR-132 D10.1–D10.3) |
| Apply a law proposal | governor | sudo to `core-law`, with a fresh password (ADR-170 D6) |
| Deploy a release | governor | root, `core-deploy` (ADR-132 D10.8) |
| Tag a release (a `v*.*.*` tag publishes to PyPI and GHCR automatically) | governor; a producer may push the tag on the governor's yes | **not enforced by the system.** Any account with write access to the GitHub repository, including the assistant's `core-claude-bot`, can push a release tag; no tag ruleset exists and the `pypi` environment has no required reviewer. Root on the host does not reach GitHub. The control today is the governor's yes in the session |
| Change accounts, groups or sudo rules on the host | governor | root, through sudo with the governor's password |
| Resolve a finding with governor authority | governor | as for approval (#942) |
| Push to `develop` | a producer, on the governor's yes | the governor's yes in the session (not yet enforced by the system) |
| Propose a change or a law change | producer or system | the producer submission route (ADR-168) |
| Run repository code **on behalf of CORE's services** (tests, `conftest.py`, build and lint scripts CORE runs on purpose) | `core-sandbox` only | the sandbox service (ADR-132 D10.10). Out of this row: a producer's own development commands, which run as that producer's account with its limits, and setup scripts the governor runs as root |
| Read state, run an audit | any principal | — |

### A6 — The mode is declared, recorded and checked

1. **Declared.** The deployment's mode is declared in law, beside the role taxonomy. The binding of accounts to roles
   stays where ADR-132 D10.2 put it (`/etc/core/principals.yaml`, root-owned), because the binding must be out of a
   producer's reach in every mode.
2. **Recorded.** Every governor act and every audit verdict records the mode under which it was made, so the trail
   shows how strong each attribution is.
3. **Checked.** A rule, reporting first, compares the declared mode with the machine. Ownership alone is not
   evidence of protection: the check computes **effective** permissions. For every producer and system account it
   decides whether that account can write, create, delete, rename or replace governed text or its protected names,
   from the permission bits, the owner and the account's group memberships, ACL entries, the sticky bit, and every
   parent directory up to `/`. In `solo-separated` it reports each such possibility, and also: a governor binding to
   an account a model session runs as; a producer or system account in a root-equivalent group (`sudo`, `docker`,
   `lxd`, `disk`, ...); a missing binding file. A check the services' account cannot perform (for example, reading
   the sudo rules) is reported as **not evaluated**, never as passed.

### A7 — Where CORE's own server stands today

CORE's server is declared `solo-separated` once A6 is built, and the check will report, truthfully: no human
governor account yet and no binding file (ADR-132 D10.11 step 4); `core-darek` in `sudo` and `docker`; the custodian
not live (ADR-170 Stage 1). Each finding closes with the step that already owns it.

### State: pending implementation

Until implemented, the canonical taxonomy `.intent/taxonomies/principal_roles.yaml` is what is in force (D2), and it
does not yet carry this amendment:
- `principal.producer` (A3) is **pending**: not in the taxonomy; no record or check uses it.
- The operation modes and the deployment's declared mode (A2, A6.1) are **pending**: the taxonomy still carries
  `deployment_topologies.single_governor_local`, which A1 supersedes once the taxonomy is amended.
- Recording the mode (A6.2) and the check (A6.3) are **pending**.
Each enters the taxonomy and the rules through its own law proposal.

### Not decided here

- How a core-platform user becomes a principal CORE trusts (ADR-132 D10, consequences: its own decision).
- The implementation order of A6 beyond "the taxonomy and the mode first, the check second, recording the mode on
  governor acts with ADR-132 D10.11 step 4".
